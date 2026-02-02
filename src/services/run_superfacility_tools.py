"""NERSC Superfacility helpers for job submission."""

import os
from pathlib import Path
from typing import Any


def generate_slurm_script(
    params: dict[str, Any],
    run_dir: str,
    config: dict | None = None,
) -> str:
    """
    Generate SLURM batch script for GPU runs.

    Parameters
    ----------
    params : dict
        Submission parameters (nodes, walltime, account, qos, constraint, executable).
    run_dir : str
        Run directory containing inputs/executable.
    config : dict or None, optional
        Optional config payload for annotation.

    Returns
    -------
    str
        SLURM batch script content.
    """
    nodes = params["nodes"]
    walltime = params["walltime"]
    account = params["account"]
    qos = params["qos"]
    constraint = params["constraint"]
    executable = params["executable"]

    ntasks = nodes * 4

    exe_name = Path(executable).name
    run_dir_name = Path(run_dir).name

    script = f"""#!/bin/bash
#SBATCH --account={account}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node=4
#SBATCH -c 32
#SBATCH --gpus-per-task=1
#SBATCH --gpu-bind=none
#SBATCH --time={walltime}
#SBATCH --constraint={constraint}
#SBATCH --qos={qos}
#SBATCH --job-name=amrex_{run_dir_name}

# GPU environment
export MPICH_GPU_SUPPORT_ENABLED=1
export SLURM_CPU_BIND="cores"
export MPICH_OFI_NIC_POLICY=GPU

echo "========================================"
echo "AMReX GPU Simulation"
echo "Run: {run_dir_name}"
echo "Nodes: {nodes} | GPUs: {ntasks}"
echo "Grid: {config.get('amr', {}).get('n_cell', '?') if config else '?'}"
echo "========================================"
echo ""

# Run from this directory
cd {Path(run_dir).absolute()}

# Run simulation
echo "Starting at $(date)"
srun -n {ntasks} ./{exe_name} inputs >& run.out

echo ""
echo "Finished at $(date)"
echo "\u2713 Complete. Output: run.out"
echo ""
echo "Files:"
ls -lh run.out plt* 2>/dev/null || echo "  (no plotfiles yet)"
"""

    return script


def find_nersc_clients() -> dict[str, Any]:
    """
    Find NERSC OAuth client configs.

    Returns
    -------
    dict
        Mapping of client configs and tokens discovered.
    """
    search_paths = [
        Path.home() / ".nersc",
        Path.home() / ".config" / "nersc",
        Path.home() / ".superfacility",
        Path.home() / "sfapi",
    ]

    clients: dict[str, Any] = {}

    for base_path in search_paths:
        if not base_path.exists():
            continue

        for color in ["green", "orange", "red"]:
            for subdir in [f"{color}_client", color]:
                client_dir = base_path / subdir

                clientid_file = client_dir / "clientid.txt"
                privkey_file = client_dir / "priv_key.jwk"

                if clientid_file.exists() and privkey_file.exists():
                    clients[color] = str(client_dir)
                    break

    for base_path in search_paths:
        if not base_path.exists():
            continue
        token_file = base_path / "token"
        if token_file.exists():
            clients["token"] = token_file.read_text().strip()
            break

    if not clients.get("token"):
        env_token = os.getenv("NERSC_API_TOKEN") or os.getenv("SFAPI_TOKEN")
        if env_token:
            clients["token"] = env_token

    return clients


def _parse_sfapi_pem(key_str: str) -> tuple[str, str] | None:
    """Parse a PEM key string with client ID on the first line."""
    lines = key_str.splitlines(keepends=True)
    if not lines:
        return None
    first_line = lines[0].strip()
    if "BEGIN" in first_line:
        return None
    secret = "".join(lines[1:]).strip()
    if not secret:
        return None
    return first_line, secret


def _load_sfapi_key_file() -> tuple[str, str] | None:
    """Load Superfacility API client ID + key from a PEM file, if present."""
    env_paths = [
        os.getenv("SFAPI_KEY_PATH"),
        os.getenv("SUPERFACILITY_KEY_PATH"),
        os.getenv("NERSC_SFAPI_KEY_PATH"),
    ]
    search_paths = [Path(p) for p in env_paths if p]

    superfacility_dir = Path.home() / ".superfacility"
    if superfacility_dir.exists():
        search_paths.extend(sorted(superfacility_dir.glob("*.pem")))
        search_paths.append(superfacility_dir / "key.pem")
        search_paths.append(superfacility_dir / "priv_key.pem")

    search_paths.extend([
        Path.cwd() / "priv_key.pem",
        Path.home() / "sfapi" / "priv_key.pem",
    ])

    for path in search_paths:
        if path.exists():
            try:
                parsed = _parse_sfapi_pem(path.read_text())
                if parsed:
                    return parsed
            except Exception:
                continue
    return None


def create_nersc_session(
    clients: dict[str, Any],
    color: str = "green",
    config: dict | None = None,
) -> dict[str, Any] | None:
    """
    Create authenticated NERSC API session.

    Parameters
    ----------
    clients : dict
        Client config mapping from ``find_nersc_clients``.
    color : str, optional
        OAuth client color ("green", "orange", "red").
    config : dict or None, optional
        Optional configuration overrides.

    Returns
    -------
    dict or None
        Session payload or None if authentication fails.
    """
    import json

    if color in clients and isinstance(clients[color], str):
        try:
            from authlib.integrations.requests_client import OAuth2Session
            from authlib.oauth2.rfc7523 import PrivateKeyJWT

            token_url = "https://oidc.nersc.gov/c2id/token"
            client_dir = Path(clients[color])

            with open(client_dir / "clientid.txt") as handle:
                client_id = handle.read().strip()
            with open(client_dir / "priv_key.jwk") as handle:
                private_key = json.load(handle)

            session = OAuth2Session(
                client_id,
                private_key,
                PrivateKeyJWT(token_url),
                grant_type="client_credentials",
                token_endpoint=token_url,
            )
            session.fetch_token()

            return {"session": session, "type": "oauth", "color": color}

        except ImportError:
            pass
        except Exception:
            pass

    if "token" in clients:
        return {"token": clients["token"], "type": "token"}

    return None


def submit_via_sfapi_client(
    script_path: str,
    system: str = "perlmutter",
    client_id: str | None = None,
    secret: str | None = None,
    config: dict | None = None,
) -> dict[str, Any]:
    """
    Submit via sfapi_client (official client library).

    Parameters
    ----------
    script_path : str
        Path to the submission script.
    system : str, optional
        Target system name.
    client_id : str or None, optional
        SFAPI OAuth client ID.
    secret : str or None, optional
        SFAPI private key (PEM).
    config : dict or None, optional
        Optional configuration overrides.

    Returns
    -------
    dict
        Submission result with job_id or error details.
    """
    try:
        from sfapi_client import Client
        from sfapi_client.compute import Machine
    except Exception:
        return {"error": "sfapi_client not available"}

    if not client_id or not secret:
        return {"error": "Missing SFAPI client credentials"}

    script = Path(script_path).read_text()

    machine = Machine.perlmutter
    if system and system != "perlmutter":
        return {"error": f"Unsupported system for sfapi_client: {system}"}

    try:
        with Client(client_id=client_id, secret=secret) as client:
            perlmutter = client.compute(machine)
            job = perlmutter.submit_job(script)
            job_id = getattr(job, "jobid", None) or getattr(job, "job_id", None)
            if job_id is None:
                job_id = getattr(job, "id", None)
            if job_id is None:
                return {"error": "SFAPI client submission returned no job id"}
            return {"job_id": str(job_id), "method": "sfapi_client"}
    except Exception as exc:
        return {"error": f"sfapi_client failed: {exc}"}


def submit_via_sfapi(
    script_path: str,
    system: str = "perlmutter",
    nersc_session: dict | None = None,
    config: dict | None = None,
) -> dict[str, Any]:
    """
    Submit via Superfacility API.

    Parameters
    ----------
    script_path : str
        Path to the submission script.
    system : str, optional
        Target system name.
    nersc_session : dict or None, optional
        Pre-authenticated session payload.
    config : dict or None, optional
        Optional configuration overrides.

    Returns
    -------
    dict
        Submission result with job_id or error details.
    """
    import requests

    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break

    if not nersc_session:
        return {"error": "No NERSC session", "suggestion": "Setup OAuth client or token"}

    script = Path(script_path).read_text()

    api_url = f"https://api.nersc.gov/api/v1.2/compute/jobs/{system}"
    payload = {"job": script, "isPath": False}

    if nersc_session["type"] == "oauth":
        response = nersc_session["session"].post(api_url, json=payload)
    else:
        headers = {
            "Authorization": f"Bearer {nersc_session['token']}",
            "Content-Type": "application/json",
        }
        response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        result = response.json()
        job_id = result.get("jobid") or result.get("task_id")
        return {"job_id": str(job_id), "method": "api"}

    return {
        "error": f"API failed: {response.status_code}",
        "details": response.text[:200],
    }


def submit_via_sbatch(script_path: str, config: dict | None = None) -> dict[str, Any]:
    """
    Submit via local sbatch.

    Parameters
    ----------
    script_path : str
        Path to the submission script.
    config : dict or None, optional
        Optional configuration overrides.

    Returns
    -------
    dict
        Submission result with job_id or error details.
    """
    import subprocess

    result = subprocess.run(["sbatch", str(script_path)], capture_output=True, text=True)

    if result.returncode == 0:
        job_id = result.stdout.strip().split()[-1]
        return {"job_id": job_id, "method": "sbatch"}

    return {"error": f"sbatch failed: {result.stderr}"}


def submit_job(
    script_path: str,
    system: str = "perlmutter",
    nersc_session: dict | None = None,
    config: dict | None = None,
) -> tuple[str, str]:
    """
    Submit job (API with sbatch fallback).

    Parameters
    ----------
    script_path : str
        Path to the submission script.
    system : str, optional
        Target system name.
    nersc_session : dict or None, optional
        Pre-authenticated session payload.
    config : dict or None, optional
        Optional configuration overrides.

    Returns
    -------
    tuple of (str, str)
        Job ID and submission method.
    """
    client_id = None
    secret = None
    if config is not None:
        client_id = config.get("superfacility_client_id")
        secret = config.get("superfacility_secret")
    if not client_id or not secret:
        parsed = _load_sfapi_key_file()
        if parsed:
            client_id, secret = parsed
    if client_id and secret:
        result = submit_via_sfapi_client(
            script_path=script_path,
            system=system,
            client_id=client_id,
            secret=secret,
            config=config,
        )
        if "job_id" in result:
            return (result["job_id"], result["method"])

    if nersc_session or find_nersc_clients():
        try:
            result = submit_via_sfapi(
                script_path=script_path,
                system=system,
                nersc_session=nersc_session,
            )

            if "job_id" in result:
                return (result["job_id"], result["method"])
        except Exception:
            pass

    result = submit_via_sbatch(script_path=script_path)

    if "job_id" in result:
        return (result["job_id"], result["method"])

    raise RuntimeError(f"Submission failed: {result.get('error')}")


def monitor_job(
    job_id: str,
    method: str = "sbatch",
    poll_interval: int = 10,
    max_polls: int = 30,
    nersc_session: dict | None = None,
    config: dict | None = None,
) -> str:
    """
    Monitor job status.

    Parameters
    ----------
    job_id : str
        Job ID to monitor.
    method : str, optional
        Submission method ("api" or "sbatch").
    poll_interval : int, optional
        Seconds between checks.
    max_polls : int, optional
        Maximum number of checks.
    nersc_session : dict or None, optional
        Pre-authenticated session payload.
    config : dict or None, optional
        Optional configuration overrides.

    Returns
    -------
    str
        Final job state.
    """
    import subprocess
    import time

    import logging

    logger = logging.getLogger(__name__)
    client_id = None
    secret = None
    if method == "sfapi_client":
        if config is not None:
            client_id = config.get("superfacility_client_id")
            secret = config.get("superfacility_secret")
        if not client_id or not secret:
            parsed = _load_sfapi_key_file()
            if parsed:
                client_id, secret = parsed
        if client_id and secret:
            logger.info("Monitoring via sfapi_client")
        if not nersc_session:
            clients = find_nersc_clients()
            if clients:
                for color in ["green", "orange", "red"]:
                    nersc_session = create_nersc_session(clients, color=color)
                    if nersc_session:
                        break
        if nersc_session and not (client_id and secret):
            logger.info("Monitoring via REST API (token/OAuth)")

    for _ in range(max_polls):
        try:
            if method == "sfapi_client" and client_id and secret:
                try:
                    from sfapi_client import Client
                    from sfapi_client.compute import Machine
                except Exception:
                    method = "api"
                else:
                    with Client(client_id=client_id, secret=secret) as client:
                        perlmutter = client.compute(Machine.perlmutter)
                        job = None
                        for attr in ("job", "jobs", "get_job", "job_by_id"):
                            if hasattr(perlmutter, attr):
                                job = getattr(perlmutter, attr)(job_id)
                                break
                        if job is None:
                            for attr in ("job", "jobs", "get_job", "job_by_id"):
                                if hasattr(client, attr):
                                    job = getattr(client, attr)(job_id)
                                    break
                        if job is None:
                            raise RuntimeError("Unable to fetch SFAPI job by id")
                        if hasattr(job, "update"):
                            job.update()
                        state = getattr(job, "state", None) or getattr(job, "status", None)
                        if hasattr(state, "value"):
                            state = state.value
                        if state:
                            state_str = str(state).upper()
                            if state_str not in ["RUNNING", "PENDING"]:
                                return str(state)

            if method == "api" and nersc_session:
                logger.debug("Polling via REST API for job %s", job_id)
                api_url = f"https://api.nersc.gov/api/v1.2/compute/jobs/perlmutter/{job_id}"

                if nersc_session["type"] == "oauth":
                    response = nersc_session["session"].get(api_url)
                else:
                    import requests

                    headers = {"Authorization": f"Bearer {nersc_session['token']}"}
                    response = requests.get(api_url, headers=headers)

                if response.status_code == 200:
                    state = response.json().get("status", "UNKNOWN")
                    if state not in ["RUNNING", "PENDING"]:
                        return state

            else:
                result = subprocess.run(
                    ["squeue", "-j", str(job_id), "-h", "-o", "%T"],
                    capture_output=True,
                    text=True,
                )
                state = result.stdout.strip()

                if not state:
                    return "COMPLETED"
                if state not in ["RUNNING", "PENDING"]:
                    return state

        except Exception:
            pass

        time.sleep(poll_interval)

    return "RUNNING"
