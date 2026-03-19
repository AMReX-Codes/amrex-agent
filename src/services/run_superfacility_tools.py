"""NERSC Superfacility helpers for job submission."""

import fnmatch
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

    exe_path = Path(executable)
    exe_name = exe_path.name
    use_absolute_exe = exe_path.is_absolute()
    exe_cmd = str(exe_path) if use_absolute_exe else f"./{exe_name}"
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
#SBATCH --output=job_stdout.log
#SBATCH --error=job_stderr.log

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
"""
    if not use_absolute_exe:
        script += f"""
# Ensure executable bit survives staging uploads.
chmod +x ./{exe_name} 2>/dev/null || true
"""

    script += f"""

# Run simulation
echo "Starting at $(date)"
srun -n {ntasks} {exe_cmd} inputs > stdout.log 2> stderr.log

echo ""
echo "Finished at $(date)"
echo "\u2713 Complete. Output: run.out"
echo ""
echo "Files:"
ls -lh stdout.log stderr.log job_stdout.log job_stderr.log plt* 2>/dev/null || echo "  (no plotfiles yet)"
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

        # Support flat layout (clientid.txt + priv_key.jwk in base path)
        clientid_file = base_path / "clientid.txt"
        privkey_file = base_path / "priv_key.jwk"
        if clientid_file.exists() and privkey_file.exists():
            clients.setdefault("default", str(base_path))

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


def _resolve_sfapi_key_path() -> Path | None:
    """Return the first available SFAPI PEM key path, if any."""
    env_paths = [
        os.getenv("SFAPI_KEY_PATH"),
        os.getenv("SUPERFACILITY_KEY_PATH"),
        os.getenv("NERSC_SFAPI_KEY_PATH"),
    ]
    search_paths = [Path(p) for p in env_paths if p]

    superfacility_dir = Path.home() / ".superfacility"
    if superfacility_dir.exists():
        search_paths.append(superfacility_dir / "key.pem")
        search_paths.append(superfacility_dir / "priv_key.pem")
        search_paths.extend(sorted(superfacility_dir.glob("*.pem")))

    search_paths.extend([
        Path.cwd() / "priv_key.pem",
        Path.home() / "sfapi" / "priv_key.pem",
    ])

    seen = set()
    for path in search_paths:
        if path in seen:
            continue
        seen.add(path)
        if path.exists():
            return path
    return None


def _load_sfapi_key_file() -> tuple[str, str] | None:
    """Load Superfacility API client ID + key from a PEM file, if present."""
    key_path = _resolve_sfapi_key_path()
    if not key_path:
        return None
    try:
        parsed = _parse_sfapi_pem(key_path.read_text())
        if parsed:
            return parsed
    except Exception:
        return None
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
    key_path: str | Path | None = None,
    is_path: bool = False,
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
    key_path : str or Path or None, optional
        SFAPI key file path (first line client_id, remainder PEM).
    config : dict or None, optional
        Optional configuration overrides.

    Returns
    -------
    dict
        Submission result with job_id or error details.
    """
    import logging

    try:
        from sfapi_client import Client
        from sfapi_client.compute import Machine
    except Exception:
        return {"error": "sfapi_client not available"}

    if not key_path and (not client_id or not secret):
        return {"error": "Missing SFAPI client credentials"}

    machine = Machine.perlmutter
    if system and system != "perlmutter":
        return {"error": f"Unsupported system for sfapi_client: {system}"}

    try:
        logger = logging.getLogger(__name__)
        if key_path:
            client = Client(key=Path(key_path))
        else:
            client = Client(client_id=client_id, secret=secret)
        with client:
            perlmutter = client.compute(machine)
            if is_path:
                job = perlmutter.submit_job(script_path)
            else:
                script = Path(script_path).read_text()
                job = perlmutter.submit_job(script)
            job_id = getattr(job, "jobid", None) or getattr(job, "job_id", None)
            if job_id is None:
                job_id = getattr(job, "id", None)
            if job_id is None:
                logger.debug(
                    "SFAPI client submission returned no job id (job type=%s).",
                    type(job),
                )
                return {"error": "SFAPI client submission returned no job id"}
            return {"job_id": str(job_id), "method": "sfapi_client"}
    except Exception as exc:
        return {"error": f"sfapi_client failed: {exc}"}


def submit_via_sfapi(
    script_path: str,
    system: str = "perlmutter",
    nersc_session: dict | None = None,
    is_path: bool = False,
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
    import logging
    import requests

    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["default", "green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break

    if not nersc_session:
        return {"error": "No NERSC session", "suggestion": "Setup OAuth client or token"}

    api_url = f"https://api.nersc.gov/api/v1.2/compute/jobs/{system}"
    if is_path:
        payload = {"job": script_path, "isPath": True}
    else:
        script = Path(script_path).read_text()
        payload = {"job": script, "isPath": False}

    if nersc_session["type"] == "oauth":
        response = nersc_session["session"].post(api_url, json=payload)
    else:
        headers = {
            "Authorization": f"Bearer {nersc_session['token']}",
            "Content-Type": "application/json",
        }
        response = requests.post(api_url, headers=headers, json=payload)

    logger = logging.getLogger(__name__)
    logger.debug("SFAPI submit response status=%s", response.status_code)

    if response.status_code == 200:
        result = response.json()
        logger.debug(
            "SFAPI submit response keys=%s",
            sorted(result.keys()) if isinstance(result, dict) else type(result),
        )
        job_id = result.get("jobid") or result.get("task_id")
        return {"job_id": str(job_id), "method": "api"}

    logger.warning(
        "SFAPI submit failed: status=%s body=%s",
        response.status_code,
        response.text[:500],
    )
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
    import shutil

    if shutil.which("sbatch") is None:
        return {
            "error": "sbatch not found in PATH",
            "suggestion": "Load the Slurm module or use the Superfacility API submission.",
        }

    try:
        result = subprocess.run(
            ["sbatch", str(script_path)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {
            "error": "sbatch not found in PATH",
            "suggestion": "Load the Slurm module or use the Superfacility API submission.",
        }

    if result.returncode == 0:
        job_id = result.stdout.strip().split()[-1]
        return {"job_id": job_id, "method": "sbatch"}

    return {"error": f"sbatch failed: {result.stderr}"}


def submit_job(
    script_path: str,
    system: str = "perlmutter",
    nersc_session: dict | None = None,
    is_path: bool = False,
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
    import logging

    logger = logging.getLogger(__name__)
    client_id = None
    secret = None
    key_path = None
    if config is not None:
        client_id = config.get("superfacility_client_id")
        secret = config.get("superfacility_secret")
    key_path = _resolve_sfapi_key_path()
    if not client_id or not secret:
        parsed = _load_sfapi_key_file()
        if parsed:
            client_id, secret = parsed
    if key_path or (client_id and secret):
        result = submit_via_sfapi_client(
            script_path=script_path,
            system=system,
            client_id=client_id,
            secret=secret,
            key_path=key_path,
            is_path=is_path,
            config=config,
        )
        if "job_id" in result:
            return (result["job_id"], result["method"])
        logger.warning("SFAPI client submission failed: %s", result)

    if nersc_session or find_nersc_clients():
        try:
            result = submit_via_sfapi(
                script_path=script_path,
                system=system,
                nersc_session=nersc_session,
                is_path=is_path,
            )

            if "job_id" in result:
                return (result["job_id"], result["method"])
            logger.warning("SFAPI REST submission failed: %s", result)
        except Exception:
            pass

    result = submit_via_sbatch(script_path=script_path)

    if "job_id" in result:
        return (result["job_id"], result["method"])
    logger.warning("sbatch submission failed: %s", result)

    raise RuntimeError(f"Submission failed: {result.get('error')}")


def stage_run_directory_sfapi_client(
    local_run_dir: str | Path,
    remote_run_dir: str,
    client_id: str | None = None,
    secret: str | None = None,
    key_path: str | Path | None = None,
    exclude_names: list[str] | None = None,
    upload_host: str = "perlmutter",
) -> None:
    """
    Stage a local run directory to a remote filesystem via sfapi_client.

    Parameters
    ----------
    local_run_dir : str or Path
        Local run directory to upload.
    remote_run_dir : str
        Remote destination directory (must exist or be creatable).
    client_id : str or None
        SFAPI OAuth client ID.
    secret : str or None
        SFAPI private key (PEM).
    """
    try:
        from sfapi_client import Client
        from sfapi_client.compute import Machine
    except Exception as exc:
        raise RuntimeError("sfapi_client not available for staging") from exc

    if not key_path and (not client_id or not secret):
        raise RuntimeError("Missing SFAPI client credentials for staging")

    local_run_dir = Path(local_run_dir)
    exclude = set(exclude_names or [])
    if not local_run_dir.exists():
        raise FileNotFoundError(f"Local run directory not found: {local_run_dir}")

    if key_path:
        client = Client(key=Path(key_path))
    else:
        client = Client(client_id=client_id, secret=secret)
    with client:
        perlmutter = client.compute(Machine.perlmutter)

        target_dir = None
        try:
            [target_dir] = perlmutter.ls(remote_run_dir, directory=True)
        except Exception:
            target_dir = None

        if target_dir is None:
            try:
                ensure_remote_directory_rest(
                    remote_run_dir=remote_run_dir,
                    upload_host=upload_host,
                )
                [target_dir] = perlmutter.ls(remote_run_dir, directory=True)
            except Exception as exc:
                raise FileNotFoundError(
                    f"Remote run directory not found: {remote_run_dir}. "
                    "Create it on Perlmutter or via the SFAPI client."
                ) from exc

        for item in sorted(local_run_dir.iterdir()):
            if not item.is_file():
                continue
            if item.name in exclude:
                continue
            with open(item, "rb") as handle:
                handle.filename = item.name  # sfapi_client expects filename attribute
                target_dir.upload(handle)


def stage_run_directory_rest(
    local_run_dir: str | Path,
    remote_run_dir: str,
    nersc_session: dict | None = None,
    upload_host: str = "perlmutter",
    exclude_names: list[str] | None = None,
) -> None:
    """
    Stage a local run directory to a remote filesystem via REST upload.

    Uses the NERSC utilities upload endpoint; creates subdirectories as needed.
    """
    import requests

    local_run_dir = Path(local_run_dir)
    exclude = set(exclude_names or [])
    if not local_run_dir.exists():
        raise FileNotFoundError(f"Local run directory not found: {local_run_dir}")

    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["default", "green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break

    if not nersc_session:
        raise RuntimeError("No NERSC session for REST upload staging")

    upload_url = f"https://api.nersc.gov/api/v1.2/utilities/upload/{upload_host}"

    for item in sorted(local_run_dir.iterdir()):
        if not item.is_file():
            continue
        if item.name in exclude:
            continue
        remote_path = str(Path(remote_run_dir) / item.name)
        with open(item, "rb") as handle:
            if nersc_session["type"] == "oauth":
                response = nersc_session["session"].put(
                    upload_url,
                    data={"file": remote_path},
                    files={"file": handle},
                )
            else:
                headers = {"Authorization": f"Bearer {nersc_session['token']}"}
                response = requests.put(
                    upload_url,
                    headers=headers,
                    data={"file": remote_path},
                    files={"file": handle},
                )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"REST upload failed for {item.name}: {response.status_code} {response.text}"
            )


def ensure_remote_directory_rest(
    remote_run_dir: str,
    nersc_session: dict | None = None,
    upload_host: str = "perlmutter",
) -> None:
    """
    Ensure remote directory exists by uploading a placeholder file via REST.
    """
    import io
    import json
    import requests
    import shlex
    import time

    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break

    if not nersc_session:
        key_path = _resolve_sfapi_key_path()
        if key_path:
            try:
                from authlib.integrations.requests_client import OAuth2Session
                from authlib.oauth2.rfc7523 import PrivateKeyJWT

                key_path = Path(key_path)
                key_lines = key_path.read_text().splitlines()
                if key_lines:
                    client_id = key_lines[0].strip()
                    private_key = "\n".join(key_lines[1:]).strip() or None
                    if client_id and private_key:
                        token_url = "https://oidc.nersc.gov/c2id/token"
                        session = OAuth2Session(
                            client_id,
                            private_key,
                            PrivateKeyJWT(token_url),
                            grant_type="client_credentials",
                            token_endpoint=token_url,
                        )
                        session.fetch_token()
                        nersc_session = {"type": "oauth", "session": session}
            except Exception:
                pass

    if not nersc_session:
        raise RuntimeError("No NERSC session for REST upload staging")

    if nersc_session["type"] == "oauth":
        try:
            command_url = f"https://api.nersc.gov/api/v1.2/utilities/command/{upload_host}"
            executable = f"bash -lc {shlex.quote(f'mkdir -p {remote_run_dir}')}"
            response = nersc_session["session"].post(
                command_url,
                data={"executable": executable},
            )
            response.raise_for_status()
            payload = response.json()
            task_id = payload.get("task_id")
            if task_id:
                tasks_url = f"https://api.nersc.gov/api/v1.2/tasks/{task_id}"
                for _ in range(15):
                    task_resp = nersc_session["session"].get(tasks_url)
                    task_resp.raise_for_status()
                    task = task_resp.json()
                    if task.get("status") == "completed":
                        result = task.get("result")
                        if isinstance(result, str):
                            result = json.loads(result)
                        if isinstance(result, dict) and result.get("status") == "ok":
                            return
                        raise RuntimeError(f"REST mkdir task failed: {result}")
                    time.sleep(1)
                raise RuntimeError(f"REST mkdir task did not complete: {task_id}")
        except Exception:
            pass

    upload_url = f"https://api.nersc.gov/api/v1.2/utilities/upload/{upload_host}"
    remote_path = str(Path(remote_run_dir) / ".keep")
    payload = io.BytesIO(b"")

    if nersc_session["type"] == "oauth":
        response = nersc_session["session"].put(
            upload_url,
            data={"file": remote_path},
            files={"file": payload},
        )
    else:
        headers = {"Authorization": f"Bearer {nersc_session['token']}"}
        response = requests.put(
            upload_url,
            headers=headers,
            data={"file": remote_path},
            files={"file": payload},
        )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"REST mkdir failed for {remote_path}: {response.status_code} {response.text}"
        )


def stage_run_directory(
    local_run_dir: str | Path,
    remote_run_dir: str,
    client_id: str | None = None,
    secret: str | None = None,
    key_path: str | Path | None = None,
    method: str = "auto",
    nersc_session: dict | None = None,
    exclude_names: list[str] | None = None,
) -> None:
    """
    Stage a local run directory to a remote filesystem.

    method:
      - auto: try sfapi_client, then REST upload
      - sfapi_client: require sfapi_client credentials
      - rest_upload: use REST upload endpoint (token/OAuth)
    """
    if key_path is None:
        key_path = _resolve_sfapi_key_path()

    if method == "sfapi_client":
        stage_run_directory_sfapi_client(
            local_run_dir=local_run_dir,
            remote_run_dir=remote_run_dir,
            client_id=client_id,
            secret=secret,
            key_path=key_path,
            exclude_names=exclude_names,
        )
        return

    if method == "rest_upload":
        stage_run_directory_rest(
            local_run_dir=local_run_dir,
            remote_run_dir=remote_run_dir,
            nersc_session=nersc_session,
            exclude_names=exclude_names,
        )
        return

    if method == "auto":
        # Try REST mkdir, then sfapi_client for bulk upload, fall back to REST upload.
        try:
            ensure_remote_directory_rest(
                remote_run_dir=remote_run_dir,
                nersc_session=nersc_session,
            )
        except Exception:
            pass
        try:
            stage_run_directory_sfapi_client(
                local_run_dir=local_run_dir,
                remote_run_dir=remote_run_dir,
                client_id=client_id,
                secret=secret,
                key_path=key_path,
                exclude_names=exclude_names,
            )
            return
        except Exception:
            stage_run_directory_rest(
                local_run_dir=local_run_dir,
                remote_run_dir=remote_run_dir,
                nersc_session=nersc_session,
                exclude_names=exclude_names,
            )
            return

    if method != "auto":
        raise ValueError(f"Unknown staging method: {method}")


def list_remote_files(
    remote_dir: str,
    nersc_session: dict | None = None,
    system: str = "perlmutter",
) -> list[str]:
    """
    List files in a remote directory using the SFAPI utilities endpoint.
    """
    import logging
    import requests

    logger = logging.getLogger(__name__)
    key_path = _resolve_sfapi_key_path()
    client_id, secret = _resolve_sfapi_credentials()
    if key_path or (client_id and secret):
        try:
            from sfapi_client import Client
            from sfapi_client.compute import Machine
        except Exception:
            client_id = None
            secret = None
        else:
            if system == "perlmutter":
                try:
                    if key_path:
                        client = Client(key=Path(key_path))
                    else:
                        client = Client(client_id=client_id, secret=secret)
                    with client:
                        perlmutter = client.compute(Machine.perlmutter)
                        entries = perlmutter.ls(remote_dir, directory=False)
                        names: list[str] = []
                        for entry in entries:
                            name = getattr(entry, "name", None) or getattr(entry, "path", None)
                            if name:
                                names.append(str(name))
                        return names
                except Exception as exc:
                    logger.warning("sfapi_client ls failed for %s: %s", remote_dir, exc)

    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["default", "green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break

    if not nersc_session:
        raise RuntimeError("No NERSC session for REST directory listing")

    api_url = f"https://api.nersc.gov/api/v1.2/utilities/ls/{system}/{remote_dir}"

    if nersc_session["type"] == "oauth":
        response = nersc_session["session"].get(api_url)
    else:
        headers = {"Authorization": f"Bearer {nersc_session['token']}"}
        response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(
            f"REST ls failed for {remote_dir}: {response.status_code} {response.text}"
        )

    result = response.json()
    names: list[str] = []
    items: list = []
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        logger.debug("Remote ls response keys=%s", sorted(result.keys()))
        for key in ("entries", "files", "contents", "items", "data"):
            if isinstance(result.get(key), list):
                items = result[key]
                break
        if items:
            logger.debug(
                "Remote ls entries count=%s sample=%s",
                len(items),
                items[0] if items else None,
            )

    for item in items:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("path")
            if name:
                names.append(str(name))
    return names


def list_remote_entries(
    remote_dir: str,
    nersc_session: dict | None = None,
    system: str = "perlmutter",
) -> list[dict]:
    """
    Return directory entries from the SFAPI utilities endpoint.
    """
    import requests

    key_path = _resolve_sfapi_key_path()
    client_id, secret = _resolve_sfapi_credentials()
    if key_path or (client_id and secret):
        try:
            from sfapi_client import Client
            from sfapi_client.compute import Machine
        except Exception:
            client_id = None
            secret = None
        else:
            if system == "perlmutter":
                try:
                    if key_path:
                        client = Client(key=Path(key_path))
                    else:
                        client = Client(client_id=client_id, secret=secret)
                    with client:
                        perlmutter = client.compute(Machine.perlmutter)
                        entries = perlmutter.ls(remote_dir, directory=True)
                        return [
                            {"name": getattr(entry, "name", None) or getattr(entry, "path", "")}
                            for entry in entries
                            if entry
                        ]
                except Exception:
                    pass

    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["default", "green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break

    if not nersc_session:
        raise RuntimeError("No NERSC session for REST directory listing")

    api_url = f"https://api.nersc.gov/api/v1.2/utilities/ls/{system}/{remote_dir}"

    if nersc_session["type"] == "oauth":
        response = nersc_session["session"].get(api_url)
    else:
        headers = {"Authorization": f"Bearer {nersc_session['token']}"}
        response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(
            f"REST ls failed for {remote_dir}: {response.status_code} {response.text}"
        )

    result = response.json()
    if isinstance(result, list):
        return [{"name": item} if isinstance(item, str) else item for item in result if item]

    if isinstance(result, dict):
        for key in ("entries", "files", "contents", "items", "data"):
            if isinstance(result.get(key), list):
                return [
                    {"name": item} if isinstance(item, str) else item
                    for item in result[key]
                    if item
                ]

    return []


def _is_remote_dir(entry: dict) -> bool:
    name = str(entry.get("name", ""))
    if entry.get("type") in ("directory", "dir", "d"):
        return True
    if entry.get("is_dir") or entry.get("isdir"):
        return True
    if name.startswith("plt"):
        return True
    if name.startswith("Level_"):
        return True
    if name == "particles":
        return True
    return False


def _resolve_sfapi_credentials() -> tuple[str | None, str | None]:
    import os

    client_id = os.getenv("SUPERFACILITY_CLIENT_ID")
    secret = os.getenv("SUPERFACILITY_SECRET")
    if client_id and secret:
        return client_id, secret
    parsed = _load_sfapi_key_file()
    if parsed:
        return parsed
    return None, None


def _superfacility_suffix(local_path: Path) -> str | None:
    parts = local_path.parts
    for idx, part in enumerate(parts):
        if part == "superfacility":
            suffix_parts = parts[idx + 1 :]
            return str(Path(*suffix_parts)) if suffix_parts else ""
    return None


def resolve_remote_output_dir(
    preferred_output_dir: str | None,
    account: str,
    user: str | None = None,
    system: str = "perlmutter",
    nersc_session: dict | None = None,
) -> Path:
    """
    Resolve a writable remote output directory with shared->user fallback.
    """
    import logging
    import os

    logger = logging.getLogger(__name__)
    candidates: list[Path] = []
    suffix: str | None = None
    key_path = _resolve_sfapi_key_path()
    client_id, secret = _resolve_sfapi_credentials()
    sfapi_available = bool(key_path or (client_id and secret))
    if preferred_output_dir:
        preferred_path = Path(os.path.expandvars(str(preferred_output_dir)))
        if not str(preferred_path).startswith("/global/cfs/cdirs/"):
            logger.info("Using local output dir for staging: %s", preferred_path)
            return preferred_path
        candidates.append(preferred_path)
        suffix = _superfacility_suffix(preferred_path)

    shared_root = Path(f"/global/cfs/cdirs/{account}/superfacility")
    user_root = (
        Path(f"/global/cfs/cdirs/{account}/{user}/superfacility") if user else None
    )
    for root in [shared_root, user_root]:
        if not root:
            continue
        candidate = root
        if suffix is not None:
            candidate = root / suffix if suffix else root
        if candidate not in candidates:
            candidates.append(candidate)

    create_budget = 2
    for candidate in candidates:
        try:
            list_remote_entries(str(candidate), nersc_session=nersc_session, system=system)
        except Exception as exc:
            if create_budget > 0:
                try:
                    ensure_remote_directory_rest(
                        remote_run_dir=str(candidate),
                        nersc_session=nersc_session,
                        upload_host=system,
                    )
                    create_budget -= 1
                    list_remote_entries(str(candidate), nersc_session=nersc_session, system=system)
                except Exception as mkdir_exc:
                    logger.debug("Remote output dir check failed for %s: %s", candidate, mkdir_exc)
                    continue
            else:
                logger.debug("Remote output dir check failed for %s: %s", candidate, exc)
                continue
        if sfapi_available and not nersc_session:
            logger.debug("Using SFAPI credentials for %s; skipping REST mkdir check", candidate)
            logger.info("Using remote output dir: %s", candidate)
            return candidate
        try:
            ensure_remote_directory_rest(
                remote_run_dir=str(candidate),
                nersc_session=nersc_session,
                upload_host=system,
            )
        except Exception as exc:
            logger.debug("Remote output dir not writable for %s: %s", candidate, exc)
            continue
        logger.info("Using remote output dir: %s", candidate)
        return candidate

    raise RuntimeError(
        "No writable remote output dir found. Checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _download_remote_file_sfapi(
    remote_path: str,
    local_path: str | Path,
    client_id: str,
    secret: str,
    system: str = "perlmutter",
) -> bool:
    try:
        from sfapi_client import Client
        from sfapi_client.compute import Machine
    except Exception:
        return False

    if system != "perlmutter":
        return False

    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    with Client(client_id=client_id, secret=secret) as client:
        perlmutter = client.compute(Machine.perlmutter)
        try:
            [file_obj] = perlmutter.ls(remote_path)
        except Exception:
            return False
        if not hasattr(file_obj, "download"):
            return False
        try:
            handle = file_obj.download()
        except Exception:
            return False
        if hasattr(handle, "read"):
            data = handle.read()
            if isinstance(data, str):
                local_path.write_text(data)
            else:
                local_path.write_bytes(data)
            return True
        return False


def download_remote_file(
    remote_path: str,
    local_path: str | Path,
    nersc_session: dict | None = None,
    system: str = "perlmutter",
    client_id: str | None = None,
    secret: str | None = None,
) -> None:
    """
    Download a single remote file via the SFAPI utilities endpoint.
    """
    import requests

    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["default", "green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break

    if client_id and secret:
        if _download_remote_file_sfapi(
            remote_path=remote_path,
            local_path=local_path,
            client_id=client_id,
            secret=secret,
            system=system,
        ):
            return
    import logging
    logging.getLogger(__name__).debug(
        "SFAPI client download unavailable or failed for %s", remote_path
    )

    if not nersc_session:
        raise RuntimeError("No NERSC session for REST download")

    api_url = f"https://api.nersc.gov/api/v1.2/utilities/download/{system}"

    headers = None
    if nersc_session["type"] != "oauth":
        headers = {"Authorization": f"Bearer {nersc_session['token']}"}

    def _do_download(remote_path_param: str) -> requests.Response:
        params = {"file": remote_path_param}
        if nersc_session["type"] == "oauth":
            response = nersc_session["session"].get(
                api_url,
                params=params,
                stream=True,
                allow_redirects=False,
            )
        else:
            response = requests.get(
                api_url,
                headers=headers,
                params=params,
                stream=True,
                allow_redirects=False,
            )

        if response.status_code in (301, 302, 307, 308) and response.headers.get("Location"):
            redirect_url = response.headers["Location"].replace("http://", "https://")
            if nersc_session["type"] == "oauth":
                response = nersc_session["session"].get(
                    redirect_url,
                    stream=True,
                    allow_redirects=False,
                )
            else:
                response = requests.get(
                    redirect_url,
                    headers=headers,
                    stream=True,
                    allow_redirects=False,
                )
        return response

    response = _do_download(remote_path)
    if response.status_code == 200:
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                payload = response.json()
            except Exception:
                payload = {}
            if isinstance(payload, dict) and payload.get("status") == "ERROR":
                response = _do_download(remote_path.lstrip("/"))
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    payload = response.json()
                except Exception:
                    payload = {}
                if isinstance(payload, dict) and payload.get("status") == "ERROR":
                    raise RuntimeError(
                        f"REST download failed for {remote_path}: {payload}"
                    )

    if response.status_code != 200:
        raise RuntimeError(
            f"REST download failed for {remote_path}: {response.status_code} {response.text}"
        )

    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)


def stage_out_outputs(
    remote_run_dir: str,
    local_run_dir: str | Path,
    nersc_session: dict | None = None,
    system: str = "perlmutter",
    text_extensions: tuple[str, ...] = (".out", ".err", ".log", ".txt"),
) -> dict[str, Any]:
    """
    Stage back output text files and the last plotfile.
    """
    local_run_dir = Path(local_run_dir)
    import logging

    logger = logging.getLogger(__name__)
    if nersc_session is None:
        clients = find_nersc_clients()
        if clients:
            for color in ["default", "green", "orange", "red"]:
                nersc_session = create_nersc_session(clients, color=color)
                if nersc_session:
                    break
    client_id, secret = _resolve_sfapi_credentials()
    logger.debug(
        "Stage-out SFAPI client creds available=%s", bool(client_id and secret)
    )
    if not nersc_session:
        raise RuntimeError("No NERSC session for stage-out downloads")

    entries = list_remote_entries(remote_run_dir, nersc_session=nersc_session, system=system)
    downloaded: list[str] = []
    errors: list[str] = []

    plot_dirs: list[str] = []
    for entry in entries:
        name = Path(entry.get("name", "")).name
        if not name:
            continue
        if name in (".", ".."):
            continue
        if name.startswith("plt") and _is_remote_dir(entry):
            if ".old." in name:
                continue
            plot_dirs.append(name)
            continue
        if name.lower().endswith(text_extensions) and not _is_remote_dir(entry):
            remote_path = str(Path(remote_run_dir) / name)
            local_path = local_run_dir / name
            try:
                download_remote_file(
                    remote_path=remote_path,
                    local_path=local_path,
                    nersc_session=nersc_session,
                    system=system,
                    client_id=client_id,
                    secret=secret,
                )
                downloaded.append(str(local_path))
            except Exception as exc:
                errors.append(f"{remote_path}: {exc}")
                logger.warning("Stage-out failed for %s: %s", remote_path, exc)

    if plot_dirs:
        plot_dirs.sort()
        plot_dir = plot_dirs[-1]
        try:
            _download_plotfile_recursive(
                remote_dir=str(Path(remote_run_dir) / plot_dir),
                local_dir=local_run_dir / plot_dir,
                nersc_session=nersc_session,
                system=system,
                client_id=client_id,
                secret=secret,
            )
            downloaded.append(str(local_run_dir / plot_dir))
        except Exception as exc:
            errors.append(f"{plot_dir}: {exc}")
            logger.warning("Stage-out failed for plotfile %s: %s", plot_dir, exc)

    return {"downloaded": downloaded, "errors": errors}


def _download_plotfile_recursive(
    remote_dir: str,
    local_dir: Path,
    nersc_session: dict | None = None,
    system: str = "perlmutter",
    client_id: str | None = None,
    secret: str | None = None,
) -> None:
    entries = list_remote_entries(remote_dir, nersc_session=nersc_session, system=system)
    for entry in entries:
        name = Path(entry.get("name", "")).name
        if not name:
            continue
        if name in (".", ".."):
            continue
        remote_path = str(Path(remote_dir) / name)
        local_path = local_dir / name
        if _is_remote_dir(entry):
            _download_plotfile_recursive(
                remote_dir=remote_path,
                local_dir=local_path,
                nersc_session=nersc_session,
                system=system,
                client_id=client_id,
                secret=secret,
            )
        else:
            download_remote_file(
                remote_path=remote_path,
                local_path=local_path,
                nersc_session=nersc_session,
                system=system,
                client_id=client_id,
                secret=secret,
            )


def find_remote_executable(
    remote_case_dir: str,
    nersc_session: dict | None = None,
    system: str = "perlmutter",
    build_system_preference: str = "gnumake",
    cmake_executable_names: list[str] | None = None,
    gnumake_executable_globs: list[str] | None = None,
) -> str | None:
    """
    Find a remote executable using policy branch ordering.
    """
    files = list_remote_files(remote_case_dir, nersc_session=nersc_session, system=system)
    file_names = [Path(item).name for item in files if Path(item).name]
    name_set = set(file_names)

    preference = str(build_system_preference).strip().lower()
    branch_order = ["cmake", "gnumake"] if preference == "cmake" else ["gnumake", "cmake"]
    cmake_names = [str(name) for name in (cmake_executable_names or [])]
    gnumake_globs = [str(pattern) for pattern in (gnumake_executable_globs or ["*.ex"])]

    for branch in branch_order:
        if branch == "cmake":
            for name in cmake_names:
                if name in name_set:
                    return str(Path(remote_case_dir) / name)
        else:
            candidates: list[str] = []
            for name in file_names:
                if any(fnmatch.fnmatch(name, pattern) for pattern in gnumake_globs):
                    candidates.append(str(Path(remote_case_dir) / name))
            if not candidates:
                continue
            cuda_candidates = [c for c in candidates if "CUDA" in Path(c).name]
            if cuda_candidates:
                return sorted(cuda_candidates)[0]
            return sorted(candidates)[0]

    return None


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
            logger.debug("Monitoring via sfapi_client")
        if not nersc_session:
            clients = find_nersc_clients()
            if clients:
                for color in ["green", "orange", "red"]:
                    nersc_session = create_nersc_session(clients, color=color)
                    if nersc_session:
                        break
        if nersc_session and not (client_id and secret):
            logger.debug("Monitoring via REST API (token/OAuth)")

    for _ in range(max_polls):
        poll_start = time.perf_counter()
        outcome = "RUNNING"
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
                                outcome = str(state)
                                logger.info(
                                    "Job poll method=sfapi_client job_id=%s outcome=%s latency_ms=%.3f",
                                    job_id,
                                    outcome,
                                    (time.perf_counter() - poll_start) * 1000.0,
                                )
                                return outcome

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
                    outcome = state
                    logger.info(
                        "Job poll method=api job_id=%s outcome=%s latency_ms=%.3f",
                        job_id,
                        outcome,
                        (time.perf_counter() - poll_start) * 1000.0,
                    )
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
                    outcome = "COMPLETED"
                    logger.info(
                        "Job poll method=sbatch job_id=%s outcome=%s latency_ms=%.3f",
                        job_id,
                        outcome,
                        (time.perf_counter() - poll_start) * 1000.0,
                    )
                    return outcome
                outcome = state
                logger.info(
                    "Job poll method=sbatch job_id=%s outcome=%s latency_ms=%.3f",
                    job_id,
                    outcome,
                    (time.perf_counter() - poll_start) * 1000.0,
                )
                if state not in ["RUNNING", "PENDING"]:
                    return state

        except Exception as exc:
            logger.warning(
                "Job poll method=%s job_id=%s outcome=exception error=%s latency_ms=%.3f",
                method,
                job_id,
                exc,
                (time.perf_counter() - poll_start) * 1000.0,
            )

        time.sleep(poll_interval)

    return "RUNNING"
