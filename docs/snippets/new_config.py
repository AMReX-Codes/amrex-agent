from database.configs.base_amrex_config import BaseAMReXConfig


class MyCodeConfig(BaseAMReXConfig):
    """Minimal config template for a new AMReX-based solver."""

    code_name = "mycode"
    github_repo = "MyOrg/MyCode"
    physics_domains = []
    default_repo_env_var = "MYCODE_REPO_PATH"

    github_search_paths = [
        "Exec",
        "Exec/SuperDirectoryOfProblemDirs",
    ]  # Example: finds Exec/ProblemA, Exec/ProblemB, Exec/SuperDirectoryOfProblemDirs/ProblemC (but not Exec/DevTests/ProblemD).

    inputs_file_patterns = [
        "inputs",
        "inputs*",
    ]  # Special input names/patterns for baseline discovery.

    documentation_map = {
        "solver_readme": ["README.md", "README.rst"],
    }  # See Pele configs for report-style documentation maps.
