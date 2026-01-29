"""
Multi-repository AMReX code case management.

Focus on AMReX application codes with well-documented inputs files, driven by
database/configs discovery.
"""

import importlib.util
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from database.configs import BaseAMReXConfig, discover_code_configs
from database.configs.registry import (
    filter_keyword_map_for_codes,
    get_github_search_paths,
    get_solver_guidance_lines,
)

HAS_GITHUB = importlib.util.find_spec("github") is not None


@dataclass
class AMReXCode:
    """Configuration for an AMReX-based code."""

    name: str
    github_org: str
    github_repo: str
    description: str
    inputs_quality: str  # "excellent", "good", "basic"
    common_cases: list[str]
    local_path: Path | None = None

    @property
    def full_github_url(self) -> str:
        """
        Build full GitHub URL for the code repository.

        Returns
        -------
        str
            HTTPS URL for the GitHub repository.
        """
        return f"https://github.com/{self.github_org}/{self.github_repo}"


logger = logging.getLogger(__name__)

class AMReXCasesService:
    """Multi-repository AMReX code case management.

    Focus on codes with excellent inputs file documentation.
    """

    def __init__(self, config):
        self.config = config
        self.codes = self._load_priority_codes()
        self._case_cache = {}


    def _load_priority_codes(self) -> list[AMReXCode]:
        """
        Load code definitions from database/configs/ (config-driven discovery).

        Replaces hardcoded self.codes with dynamic loading from configs.
        Pattern: yt-project's dynamic frontend discovery.
        """
        available = []

        for config_cls in discover_code_configs():
            # Map config class -> AMReXCode dataclass
            code = AMReXCode(
                name=config_cls.code_name,
                github_org=config_cls.github_org,
                github_repo=config_cls.github_repo or config_cls.code_name,
                description=config_cls.description,
                inputs_quality=config_cls.inputs_quality,
                common_cases=config_cls.priority_cases.copy(),  # Copy to avoid mutation
                local_path=self.config.repositories.get(config_cls.code_name)
            )
            available.append(code)

            # Log discovery
            status = "[LOCAL]" if code.local_path else "[REMOTE]"
            logger.info(f" {status} {code.name}: {code.inputs_quality}, {len(code.common_cases)} cases")

        return available

    def find_local_cases(self, code_name: str) -> list[str]:
        """
        Find cases in a local repository with portable repo-relative paths.

        Call context: Used by Architect to enumerate candidate baselines.

        Parameters
        ----------
        code_name : str
            Name of AMReX application code.

        Returns
        -------
        list of str
            Repo-relative paths (e.g., ["Exec/RegTests/PMF"]).
        """
        code = next((c for c in self.codes if c.name == code_name), None)
        if not code:
            raise ValueError(f"Unknown code: {code_name}")
        if code.local_path and code.local_path.exists():
            return self._scan_local(code)
        return code.common_cases

    def clone_code(self,
                   code_name: str,
                   target_dir: Path | None = None,
                   branch: str = "development") -> Path | None:
        """
        Clone AMReX code repository.

        Uses self.codes to get correct GitHub URL.
        Always clones with --recursive for submodules.

        Call context: Used by setup workflows to fetch missing repos.

        Parameters
        ----------
        code_name : str
            Code to clone (AMReX application code name).
        target_dir : Path or None, optional
            Parent directory (default: ../code_name).
        branch : str, optional
            Git branch to clone.

        Returns
        -------
        Path or None
            Path to cloned directory, or None if failed.
        """
        import subprocess

        # Find code definition
        code_def = None
        for code in self.codes:
            if code.name == code_name:
                code_def = code
                break

        if code_def is None:
            logger.error(f"[ERROR] Unknown code: {code_name}")
            logger.debug(f"        Known: {[c.name for c in self.codes]}")
            return None

        # Determine target directory
        if target_dir is None:
            # Clone to parent of amrex_agent
            target_dir = self.config.amrex_agent_root.parent / code_name
        else:
            target_dir = Path(target_dir) / code_name

        target_dir = Path(target_dir)

        # Check if already exists
        if target_dir.exists():
            logger.info(f" Directory already exists: {target_dir}")

            if (target_dir / '.git').exists():
                logger.info("[ OK ] Already cloned")
                return target_dir
            else:
                logger.error("[ERROR] Directory exists but is not a git repo")
                return None

        # Clone with submodules
        git_url = code_def.full_github_url

        logger.debug(f"\n=== Cloning {code_name} ===\n")
        logger.debug(f"From: {git_url}")
        logger.debug(f"To:   {target_dir}")
        logger.debug(f"Branch: {branch}")
        logger.debug("\nThis may take 2-5 minutes...\n")

        try:
            # Clone main repo
            result = subprocess.run(
                ['git', 'clone', '--recursive', '-b', branch, git_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300  # 5 min
            )

            if result.returncode != 0:
                logger.error("[ERROR] Clone failed:")
                logger.debug(result.stderr)
                return None

            logger.info("[ OK ] Cloned successfully")

            # Verify submodules
            result = subprocess.run(
                ['git', 'submodule', 'status'],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            submodules = [line for line in result.stdout.split('\n') if line.strip()]
            logger.info(f"[ OK ] {len(submodules)} submodules initialized\n")

            return target_dir

        except subprocess.TimeoutExpired:
            logger.error("[ERROR] Clone timed out")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Clone failed: {e}")
            return None


    def ensure_code_available(self, code_name: str) -> Path | None:
        """
        Ensure code is available locally (find or clone).

        Checks:
        1. Config repo paths
        2. Standard locations
        3. Auto-clones if needed

        Call context: Used by services that need local code access.

        Parameters
        ----------
        code_name : str
            Code name to ensure locally.

        Returns
        -------
        Path or None
            Path to code directory if available.
        """
        # Check 1: Config
        repo_map = {
            code.name: self.config.repositories.get(code.name)
            for code in self.codes
        }

        if code_name in repo_map and repo_map[code_name]:
            path = repo_map[code_name]
            if path.exists():
                logger.info(f"[ OK ] Found in config: {path}")
                return path

        # Check 2: Standard locations
        search_paths = [
            self.config.amrex_agent_root.parent / code_name,
            Path.home() / code_name,
            Path.home() / 'amrex-repos' / code_name,
        ]

        for path in search_paths:
            if path.exists() and (path / 'Source' or path / 'Exec').exists():
                logger.info(f"[ OK ] Found locally: {path}")
                return path

        # Not found - clone it
        logger.info(f" {code_name} not found locally")

        return self.clone_code(code_name)

    def list_all_cases(self, codes: list[str] | None = None,
                       quality_filter: str = None) -> dict[str, list[str]]:
        """
        List cases from AMReX codes.

        Call context: Used by Architect to build selection menus.

        Parameters
        ----------
        codes : list of str or None, optional
            Specific code names, or None for all.
        quality_filter : str or None, optional
            Filter by inputs_quality ("excellent", "good", "basic").

        Returns
        -------
        dict
            Mapping of code name to repo-relative case paths.
        """
        codes_to_scan = self.codes

        if codes:
            codes_to_scan = [c for c in codes_to_scan if c.name in codes]

        if quality_filter:
            codes_to_scan = [c for c in codes_to_scan
                           if c.inputs_quality == quality_filter]

        all_cases = {}
        for code in codes_to_scan:
            if code.name in self._case_cache:
                all_cases[code.name] = self._case_cache[code.name]
            else:
                cases = self._scan_code(code)
                self._case_cache[code.name] = cases
                all_cases[code.name] = cases

        return all_cases

    def _scan_code(self, code: AMReXCode) -> list[str]:
        """Scan a code for example cases."""
        # Try local first
        if code.local_path:
            return self._scan_local(code)

        # Use hardcoded common cases as fallback
        logger.info(f" {code.name}: Using {len(code.common_cases)} known cases")
        return code.common_cases

    def _scan_local(self, code) -> list[str]:
        """
        Scan local repository for cases (delegates to config scanner).

        Cases Service: Config-Driven Scanner: Uses polymorphic config.scan_for_cases() instead
        of hardcoded if/elif logic.
        """
        if not code.local_path or not code.local_path.exists():
            return []

        # Find the config class for this code
        from database.configs import discover_code_configs

        config_class = None
        for cfg in discover_code_configs():
            if cfg.code_name == code.name:
                config_class = cfg
                break

        if not config_class:
            return []

        # Delegate to config's scanner
        case_dirs = config_class.scan_for_cases(code.local_path)

        # Convert to relative paths
        relative_paths = [str(p.relative_to(code.local_path)) for p in case_dirs]

        return relative_paths

    def find_best_match(self, user_prompt: str, llm_client,
                        prefer_quality: str = "excellent") -> tuple[str, str]:
        """
        Find best matching code and case.

        Call context: Used by Architect when RAG confidence is low.

        Parameters
        ----------
        user_prompt : str
            User's simulation description.
        llm_client : object
            LLM client instance.
        prefer_quality : str, optional
            Prefer codes with this inputs quality.

        Returns
        -------
        tuple
            ("<CodeName>", "Exec/<problem_directory>").
        """
        # Get cases, preferring high-quality docs
        all_cases = self.list_all_cases(quality_filter=prefer_quality)
        if not all_cases:
            all_cases = self.list_all_cases()  # Fallback to all

        prompt_template = self._resolve_case_selection_prompt()

        # Build detailed prompt
        options = []
        for code_name, cases in all_cases.items():
            code = next(c for c in self.codes if c.name == code_name)

            options.append(f"\n{code_name} - {code.description}")
            options.append(f"  Docs quality: {code.inputs_quality}")
            options.append("  Cases:")
            for case in cases[:8]:  # Show up to 8
                options.append(f"    - {case}")
            if len(cases) > 8:
                options.append(f"    ... and {len(cases)-8} more")

        guidance_lines = get_solver_guidance_lines()
        guidance_block = "\n".join(f"- {line}" for line in guidance_lines)

        prompt = prompt_template.format(
            user_prompt=user_prompt,
            options=''.join(options),
            guidance_block=guidance_block
        )

        try:
            response = llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )

            content = response.choices[0].message.content.strip()

            # Parse
            code_match = None
            case_match = None
            for line in content.split('\n'):
                if line.startswith("CODE:"):
                    code_match = line.split("CODE:")[1].strip()
                elif line.startswith("CASE:"):
                    case_match = line.split("CASE:")[1].strip()

            # Validate
            if code_match in all_cases:
                # Fuzzy match case
                for case in all_cases[code_match]:
                    if case_match and (case_match in case or case in case_match):
                        logger.info(f" LLM selected: {code_match}/{case}")
                        return (code_match, case)

                # Try to recover from prompt (no default fallback)
                prompt_case = self._match_case_from_prompt(user_prompt, all_cases[code_match])
                if prompt_case:
                    logger.info(f" Matched case from prompt: {code_match}/{prompt_case}")
                    return (code_match, prompt_case)

                raise ValueError(
                    f"LLM selected code '{code_match}' but no matching case was found"
                )

            # Fallback
            logger.warning("[WARN] LLM returned invalid, using keyword match")
            return self._keyword_match(user_prompt, all_cases)

        except Exception as e:
            logger.error(f"[ERROR] LLM failed: {e}")
            return self._keyword_match(user_prompt, all_cases)

    def _match_case_from_prompt(self, prompt: str, cases: list[str]) -> str | None:
        """Return a case if the prompt references it, otherwise None."""
        prompt_norm = prompt.lower().replace("-", "").replace("_", "")
        for case in cases:
            case_norm = case.lower().replace("-", "").replace("_", "")
            case_leaf = case_norm.split("/")[-1]
            if case_leaf and case_leaf in prompt_norm:
                return case
            if case_norm in prompt_norm:
                return case
        return None

    def _keyword_match(self, prompt: str, all_cases: dict) -> tuple[str, str]:
        """Fallback keyword matching."""
        prompt_lower = prompt.lower()

        keywords = filter_keyword_map_for_codes(all_cases.keys())

        selected_code = None
        for keyword, code in keywords.items():
            if keyword in prompt_lower and code in all_cases:
                selected_code = code
                break
        if not selected_code:
            raise ValueError("Missing solver selection: no keyword matched and no solver specified")

        cases = all_cases[selected_code]
        prompt_case = self._match_case_from_prompt(prompt, cases)
        if not prompt_case:
            raise ValueError(f"Missing case selection for solver '{selected_code}'")

        return (selected_code, prompt_case)

    def _resolve_case_selection_prompt(self) -> str:
        prompt_template = None
        if hasattr(self.config, "get_code_registry"):
            registry = self.config.get_code_registry()
            config_cls = None
            default_solver = getattr(self.config, "default_solver", None)
            if default_solver:
                config_cls = registry.get(default_solver)
            if config_cls:
                prompt_template = config_cls.get_prompt_templates().get(
                    "cases", {}
                ).get("selection_prompt")
        if not prompt_template:
            prompt_template = BaseAMReXConfig.get_prompt_templates().get(
                "cases", {}
            ).get("selection_prompt")
        if not prompt_template:
            prompt_template = (
                "You are an expert in AMReX-based simulation codes. Given this request:\n\n"
                "\"{user_prompt}\"\n\n"
                "Select the BEST AMReX code and example case as a starting point.\n\n"
                "Available codes:{options}\n\n"
                "Return EXACTLY two lines:\n"
                "CODE: <name>\n"
                "CASE: <path>"
            )
        return prompt_template

    def get_code_info(self, code_name: str) -> AMReXCode | None:
        """
        Get information about a specific code.

        Call context: Used by services that need code metadata.

        Parameters
        ----------
        code_name : str
            Code name to look up.

        Returns
        -------
        AMReXCode or None
            Code metadata if available.
        """
        return next((c for c in self.codes if c.name == code_name), None)

    def get_solver_descriptions(self) -> dict[str, str]:
        """Get one-line descriptions of all available solvers.

        Returns
        -------
            Dict mapping code_name → description
        """
        return {code.name: code.description for code in self.codes}

    def get_code_names(self) -> list[str]:
        """
        Get list of all available code names.

        Call context: Used by UI and planning for solver selection.

        Returns
        -------
        list of str
            Available code names.
        """
        return [code.name for code in self.codes]

    def fetch_example(self,
                     example_name: str,
                     code: str | None = None,
                     save_dir: Path | None = None,
                     version: str = "development") -> dict[str, Any] | None:
        """
        Fetch example with cascading strategy.

        Priority:
        1. Local clone (fastest, most reliable)
        2. Common cases + GitHub (for known examples)
        3. GitHub auto-discovery (for unknown examples)

        This expands capability while reusing existing code.

        Call context: Used by Input Writer and tooling to fetch examples.

        Parameters
        ----------
        example_name : str
            Example name to fetch.
        code : str or None, optional
            Solver code name (defaults to config.default_solver).
        save_dir : Path or None, optional
            Directory to save fetched inputs.
        version : str, optional
            Git reference to fetch from.

        Returns
        -------
        dict or None
            Example metadata payload, or None if not found.
        """
        # Use default solver if code not specified
        if code is None:
            code = self.config.default_solver
            if not code:
                raise ValueError("No default solver configured for example fetch")

        code_def = self.get_code_info(code)
        if not code_def:
            return None

        # === Strategy 1: Local Clone (REUSE _scan_local) ===
        if code_def.local_path and code_def.local_path.exists():
            logger.info(f" Checking local {code} clone...")
            result = self._fetch_from_local(example_name, code_def, save_dir)
            if result:
                return result
            logger.info(" Not found locally, trying GitHub...")

        # === Strategy 2: Known Examples (REUSE common_cases) ===
        # Try to match against common_cases
        case_path = self._find_case_path_in_common(example_name, code_def)
        if case_path:
            logger.info(f" Matched common case: {case_path}")
            return self._fetch_from_github_path(
                code_def, case_path, example_name, save_dir, version
            )

        # === Strategy 3: Auto-Discovery (NEW - EXPAND capability) ===
        logger.info(f" Unknown example, browsing GitHub for '{example_name}'...")
        return self._fetch_from_github_discovery(
            code_def, example_name, save_dir, version
        )

    def _fetch_from_local(self, example_name, code_def, save_dir):
        """Strategy 1: Use local clone - REUSES _scan_local."""
        # Use existing _scan_local
        cases = self._scan_local(code_def)

        # Fuzzy match
        case_path = None
        search_norm = example_name.lower().replace('-', '').replace('_', '')

        for case in cases:
            case_name = case.split('/')[-1]
            case_norm = case_name.lower().replace('-', '').replace('_', '')

            if search_norm in case_norm or case_norm in search_norm:
                case_path = case
                break

        if not case_path:
            return None

        # Find inputs file
        full_path = code_def.local_path / case_path
        inputs_file = self._find_inputs_in_dir(full_path)

        if not inputs_file:
            return None

        # Copy to save_dir
        if save_dir:
            save_path = Path(save_dir) / f"inputs.{code_def.name.lower()}-{example_name}"
            import shutil
            shutil.copy(inputs_file, save_path)
            result_path = save_path
        else:
            result_path = inputs_file

        logger.info(f"[ OK ] Found locally: {case_path}")
        return {
            'local_path': str(result_path),
            'example_name': example_name,
            'code': code_def.name,
            'repo_path': str(inputs_file.relative_to(code_def.local_path)),
            'version': 'local',
            'source': 'local_clone',
        }

    def _find_case_path_in_common(self, example_name, code_def):
        """Strategy 2: Match against common_cases - REUSES existing."""
        search_norm = example_name.lower().replace('-', '').replace('_', '')

        for case in code_def.common_cases:
            case_name = case.split('/')[-1]
            case_norm = case_name.lower().replace('-', '').replace('_', '')

            if search_norm in case_norm or case_norm in search_norm:
                return case

        return None


    def _fetch_from_github_path(self, code_def, case_path, example_name, save_dir, version):
        """Strategy 2b: Download known case_path from GitHub."""
        if not HAS_GITHUB:
            logger.error("[ERROR] PyGithub not installed")
            return None

        from github import Github

        try:
            g = Github()
            repo = g.get_repo(f"{code_def.github_org}/{code_def.github_repo}")

            # Browse case directory for inputs file
            try:
                contents = repo.get_contents(case_path, ref=version)
            except Exception:
                logger.warning(f"[WARN] Branch {version} not found, trying development")
                contents = repo.get_contents(case_path, ref="development")
                version = "development"

            # Find inputs file
            inputs_patterns = ['inputs', 'input.', '.inp']
            for item in contents:
                if item.type == 'file' and any(p in item.name.lower() for p in inputs_patterns):
                    # Found it!
                    content = item.decoded_content.decode('utf-8')

                    if save_dir is None:
                        save_dir = Path("/tmp")
                    save_path = Path(save_dir) / f"inputs.{code_def.name.lower()}-{example_name}"
                    save_path.write_text(content)

                    import hashlib
                    checksum = hashlib.sha256(content.encode()).hexdigest()[:8]

                    logger.info(f"[ OK ] Downloaded from GitHub: {case_path}/{item.name}")
                    return {
                        'local_path': str(save_path),
                        'example_name': example_name,
                        'code': code_def.name,
                        'repo_path': f"{case_path}/{item.name}",
                        'version': version,
                        'source': 'github',
                        'checksum': checksum,
                    }

            logger.warning(f"[WARN] No inputs file in {case_path}")
            return None

        except Exception as e:
            logger.error(f"[ERROR] GitHub fetch failed: {e}")
            return None


    def _fetch_from_github_discovery(self, code_def, example_name, save_dir, version):
        """Strategy 3: NEW - Auto-discover on GitHub (EXPANDS capability)."""
        if not HAS_GITHUB:
            logger.error("[ERROR] PyGithub not installed")
            return None

        from github import Github

        try:
            g = Github()
            repo = g.get_repo(f"{code_def.github_org}/{code_def.github_repo}")

            search_paths = get_github_search_paths(code_def.name)

            # Browse each search path
            for base_path in search_paths:
                try:
                    contents = repo.get_contents(base_path, ref=version)
                except Exception:
                    continue

                # Look for matching directory
                search_norm = example_name.lower().replace('-', '').replace('_', '')

                for item in contents:
                    if item.type != 'dir':
                        continue

                    item_norm = item.name.lower().replace('-', '').replace('_', '')

                    if search_norm in item_norm or item_norm in search_norm:
                        # Found matching directory! Browse it for inputs
                        try:
                            case_contents = repo.get_contents(item.path, ref=version)

                            # Find inputs file
                            inputs_patterns = ['inputs', 'input.', '.inp']
                            for file in case_contents:
                                if file.type == 'file' and any(p in file.name.lower() for p in inputs_patterns):
                                    # Download it
                                    content = file.decoded_content.decode('utf-8')

                                    if save_dir is None:
                                        save_dir = Path("/tmp")
                                    save_path = Path(save_dir) / f"inputs.{code_def.name.lower()}-{example_name}"
                                    save_path.write_text(content)

                                    import hashlib
                                    checksum = hashlib.sha256(content.encode()).hexdigest()[:8]

                                    logger.info(f"[ OK ] Auto-discovered: {item.path}/{file.name}")
                                    return {
                                        'local_path': str(save_path),
                                        'example_name': example_name,
                                        'code': code_def.name,
                                        'repo_path': f"{item.path}/{file.name}",
                                        'version': version,
                                        'source': 'github_autodiscovered',
                                        'checksum': checksum,
                                    }
                        except Exception:
                            continue

            logger.error(f"[ERROR] Could not find '{example_name}' in {code_def.name} on GitHub")
            return None

        except Exception as e:
            logger.error(f"[ERROR] GitHub discovery failed: {e}")
            return None


    def _find_inputs_in_dir(self, case_dir: Path) -> Path | None:
        """REUSED helper."""
        if not case_dir.exists():
            return None

        patterns = ['inputs', 'input.2d*', 'input.3d*', '*.inp', 'inputs.*']

        for pattern in patterns:
            matches = list(case_dir.glob(pattern))
            if matches:
                for m in matches:
                    if not m.name.endswith(('.bak', '~')):
                        return m
                return matches[0]

        return None

# Test
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_llm_client, load_config

    logger.debug("\n=== Testing AMReX Cases Service ===\n")

    config = load_config()
    service = AMReXCasesService(config)
    focus_list = ", ".join(code.name for code in service.codes)
    logger.debug(f"Focus: {focus_list}\n")

    # Test 1: Show available codes
    logger.debug("[Test 1] Available codes:")
    for code in service.codes:
        status = "[LOCAL]" if code.local_path else "[REMOTE]"
        logger.debug(f"  {status} {code.name:20s} - {code.description}")
        logger.debug(f"       Docs: {code.inputs_quality}, {len(code.common_cases)} known cases")

    # Test 2: List cases from each code
    logger.debug("\n[Test 2] List cases (excellent docs only):")
    cases = service.list_all_cases(quality_filter="excellent")
    for code_name, case_list in cases.items():
        logger.debug(f"\n{code_name}: {len(case_list)} cases")
        for case in case_list[:5]:
            logger.debug(f"  - {case}")
        if len(case_list) > 5:
            logger.debug(f"  ... and {len(case_list)-5} more")

    # Test 3: Find best matches
    logger.debug("\n[Test 3] Find best matches:")
    llm_client = get_llm_client(config)

    test_prompts = [
        "2D methane flame with AMR",
        "atmospheric boundary layer simulation",
        "laser wakefield acceleration",
        "incompressible flow past cylinder",
        "I want to learn AMReX basics",
    ]

    for prompt in test_prompts:
        code, case = service.find_best_match(prompt, llm_client)
        code_info = service.get_code_info(code)
        logger.debug(f"\n  Prompt: '{prompt}'")
        logger.debug(f"  → {code}: {case}")
        logger.debug(f"    ({code_info.description}, docs: {code_info.inputs_quality})")
