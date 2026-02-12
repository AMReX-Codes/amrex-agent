# ---
# jupyter:
#   jupytext:
#     default_lexer: ipython3
#     formats: ipynb,md:myst,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: JupyterAI
#     language: python
#     name: interact-ai
# ---

# %% [markdown]
# # Pele Tools - Complete Simulation Assistant
#
# **Consolidates ALL tools from:**
# - Notebook 01: Core I/O (inputs parsing, file fetching)
# - Notebooks 02/03: Knowledge base (LLM Q&A, expansion tools)
# - Notebook 04: Config building, validation, resource estimation
# - utils/pele_assistant.py: MCP-compatible tools
#
# **Usage:**
# ```python
# from utils.pele_tools import *
#
# # Parse inputs
# inputs = parse_pele_inputs("inputs")
#
# # Ask knowledge base
# answer = ask_pele_question.invoke({"question": "What CFL number should I use?"})
#
# # Expand knowledge base
# add_custom_knowledge.invoke({"content": "My notes...", "title": "Custom"})
# ingest_pele_readmes.invoke({"repo_path": "/path/to/PeleC"})
#
# # Build config from intent
# config = build_simulation_config("2D methane flame with AMR")
#
# # Validate and generate files
# validation = validate_all.invoke({"config_json": json.dumps(config)})
# files = write_simulation_files.invoke({"config_json": json.dumps(config), "output_dir": "./sim"})
# ```

# %% [markdown]
# ## Imports & Dependencies

# %% jupyter={"source_hidden": true}
"""
pele_tools - Complete Pele Simulation Assistant.

This module consolidates all utilities from Notebooks 01-04.
Each function is documented and tested in its source notebook.

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import copy
import importlib.util
import json
import os
import re
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from amrex_tools import (
    copy_to_rundir,
    create_1d_profile,
    create_yt_sliceplot,
    dict_to_pele_inputs,
    extract_plotfile_metadata,
    find_inputs_file,
    find_latest_plotfile,
    parse_pele_inputs,
    setup_run_directory,
)
from langchain.tools import tool

# Optional dependencies with graceful fallback
try:
    from github import Github
    HAS_GITHUB = True
except ImportError:
    HAS_GITHUB = False
    print("[WARN] PyGithub not installed - GitHub features disabled")
    print("       Install: pip install PyGithub")

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("[WARN] openai not installed - LLM features disabled")
    print("       Install: pip install openai")

HAS_REQUESTS = importlib.util.find_spec("requests") is not None
if not HAS_REQUESTS:
    print("[WARN] requests not installed - HTTP features disabled")
    print("       Install: pip install requests")

HAS_PANDOC = importlib.util.find_spec("pandoc") is not None


# %% [markdown]
# ## Section 1: Core I/O (from Notebook 01)
#
# These functions handle reading/writing Pele inputs files and fetching examples.
#
# ### parse_pele_inputs

# parse_pele_inputs and dict_to_pele_inputs are provided by amrex_tools.py.

# ### fetch_pele_example

# %%
def fetch_pele_example(example_name: str,
                       save_dir: Path | None = None,
                       force_download: bool = False,
                       version: str = "v25.04") -> dict[str, Any] | None:
    """
    Fetch a known-good input file from PeleC repository.

    Returns metadata dict with file info instead of just Path.

    Parameters
    ----------
        example_name: One of the example keys (e.g., 'sedov-1', 'pmf-lidryer')
        save_dir: Where to save (default: current directory)
        force_download: Re-download even if cached
        version: PeleC release tag (default: 25.04)

    Returns
    -------
        dict: {
            'local_path': Path to downloaded file,
            'example_name': The example key used,
            'repo_path': Path in GitHub repo,
            'version': PeleC version/tag,
            'source': 'github',
            'checksum': SHA256 (first 8 chars)
        }

    Examples
    --------
        >>> info = fetch_pele_example('pmf-lidryer')
        >>> config = parse_pele_inputs(info['local_path'], source_info=info)
    """
    from database.configs.pelec_config import PeleCConfig

    examples = PeleCConfig.examples_catalog()
    if example_name not in examples:
        print(f"[ERROR] Unknown example: {example_name}")
        print(f"       Available: {list(examples.keys())}")
        return None

    return PeleCConfig.fetch_example(
        example_name,
        save_dir=save_dir,
        force_download=force_download,
        version=version,
    )

# %% [markdown]
# ### validate_pele_inputs (file-based)

# %%
@tool
def validate_pele_inputs(inputs_file: str) -> str:
    """
    Validate inputs file for common errors.

    This is file-based validation (vs validate_config_* which work on dicts).
    Checks for:
    - Parse errors
    - Missing required sections
    - Common typos

    Parameters
    ----------
        inputs_file: Path to inputs file

    Returns
    -------
        str: Validation results as JSON

    Example:
        >>> result = validate_pele_inputs.invoke({"inputs_file": "inputs"})
        >>> validation = json.loads(result)
    """
    errors = []
    warnings = []

    # Check file exists
    inputs_path = Path(inputs_file)
    if not inputs_path.exists():
        return json.dumps({
            "errors": [f"File not found: {inputs_file}"],
            "warnings": []
        }, indent=2)

    # Try to parse
    try:
        config = parse_pele_inputs(inputs_file)
    except Exception as e:
        return json.dumps({
            "errors": [f"Parse error: {e}"],
            "warnings": []
        }, indent=2)

    # Now run dict-based validation
    config_json = json.dumps(config)

    # Use existing validators (defined later in this file)
    from_schema = json.loads(validate_config_schema.invoke({"config_json": config_json}))
    from_physics = json.loads(validate_config_physics.invoke({"config_json": config_json}))
    from_grid = json.loads(validate_config_grid.invoke({"config_json": config_json}))

    errors.extend(from_schema.get("errors", []))
    errors.extend(from_physics.get("errors", []))
    errors.extend(from_grid.get("errors", []))

    warnings.extend(from_schema.get("warnings", []))
    warnings.extend(from_physics.get("warnings", []))
    warnings.extend(from_grid.get("warnings", []))

    return json.dumps({"errors": errors, "warnings": warnings}, indent=2)


# %% [markdown]
# ## Section 2: Knowledge Base (from Notebooks 02/03)
#
# These tools provide LLM-powered Q&A using curated Pele documentation,
# plus tools to expand the knowledge base from multiple sources.
#
# ### load_pele_knowledge

# %% jupyter={"source_hidden": true}
@tool
def load_pele_knowledge() -> str:
    """
    Load all Pele simulation reports into knowledge base.

    Returns
    -------
        str: Combined text from all report files
    """
    reports_dir = Path(os.getenv("PELE_REPORTS_DIR", "./reports"))

    if not reports_dir.exists():
        return f"[ERROR] Reports directory not found: {reports_dir}"

    knowledge = []
    for report_path in sorted(reports_dir.glob("report*.txt")):
        with open(report_path) as f:
            report_num = report_path.stem.replace('report', '')
            knowledge.append(f"=== REPORT {report_num} ===\n{f.read()}\n")

    return "\n".join(knowledge)


# %% [markdown]
# ### ask_pele_question

# %% jupyter={"source_hidden": true}
@tool
def ask_pele_question(question: str, use_full_knowledge: bool = True) -> str:
    """
    Ask a question about Pele simulations using the knowledge base.

    Parameters
    ----------
        question: Your question about Pele setup, parameters, etc.
        use_full_knowledge: True to use all reports, False for baseline only

    Returns
    -------
        str: Structured answer with confidence, sources, and evidence

    Example:
        >>> answer = ask_pele_question.invoke({"question": "What CFL number should I use?"})
        >>> print(answer)
    """
    if not HAS_OPENAI:
        return "[ERROR] openai package not installed - cannot query LLM"

    knowledge = load_pele_knowledge.invoke({})

    if not knowledge or knowledge.startswith("[ERROR]"):
        return knowledge

    client = OpenAI(
        api_key=os.getenv("CBORG_API_KEY"),
        base_url="https://api.cborg.lbl.gov/v1"
    )

    model = os.getenv("CBORG_MODEL", "lbl/llama")

    # Multi-pass for large knowledge bases
    if len(knowledge) > 400000:
        return _query_multi_pass(client, model, question, knowledge)
    else:
        return _query_with_knowledge(client, model, question, knowledge)


# %% [markdown]
# ### Helper Functions for Knowledge Base Queries

# %% jupyter={"source_hidden": true}
def _query_with_knowledge(client, model, question, knowledge):
    """Single query with provided knowledge."""
    system_prompt = """You are a Pele combustion simulation expert. Answer questions using ONLY information from the provided knowledge base.

IMPORTANT: Use this exact format for ALL answers:

**Confidence: [0-100]%**

**Answer:**
[Your answer here. Be specific.]

**Sources:**
- [List which reports contain this information]

**Evidence:**

[Include exact snippets/quotes when available inside triple ticks denoting code]


**Caveats:**
- [Any assumptions or limitations]"""

    messages = [
        {"role": "system", "content": system_prompt + f"\n\nKnowledge Base:\n{knowledge}"},
        {"role": "user", "content": question}
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=1000,
    )

    return response.choices[0].message.content


def _query_multi_pass(client, model, question, full_knowledge):
    """Two-pass query for very large knowledge bases."""
    # Split by report
    all_reports = {}
    for report in full_knowledge.split("=== REPORT "):
        if not report.strip():
            continue
        parts = report.split(" ===", 1)
        if len(parts) < 2:
            continue
        report_num = parts[0].strip()
        all_reports[report_num] = f"=== REPORT {report}"

    # Baseline reports (1-6)
    baseline_reports = [all_reports.get(str(i), "") for i in range(1, 7)]
    baseline_knowledge = "\n\n".join(r for r in baseline_reports if r)

    # New reports (7+)
    new_report_nums = sorted([num for num in all_reports if int(num) > 6], key=int)
    new_reports_knowledge = "\n\n".join([all_reports[num] for num in new_report_nums])

    answers = []

    # Pass 1: Baseline
    try:
        baseline_answer = _query_with_knowledge(client, model, question, baseline_knowledge)
        baseline_conf = _extract_confidence(baseline_answer)
        answers.append({
            'source': 'Reports 1-6',
            'answer': baseline_answer,
            'confidence': baseline_conf
        })
    except Exception as e:
        print(f"[WARN] Baseline query failed: {e}")

    # Pass 2: New reports
    if new_reports_knowledge:
        try:
            new_answer = _query_with_knowledge(client, model, question, new_reports_knowledge)
            new_conf = _extract_confidence(new_answer)
            answers.append({
                'source': f'Reports {", ".join(new_report_nums)}',
                'answer': new_answer,
                'confidence': new_conf
            })
        except Exception as e:
            print(f"[WARN] New reports query failed: {e}")

    if not answers:
        return "**Confidence: 0%**\n\n**Answer:**\nError querying knowledge base."

    # Return highest confidence answer
    answers.sort(key=lambda x: x['confidence'], reverse=True)
    return answers[0]['answer']


def _extract_confidence(answer):
    """Extract confidence percentage from answer."""
    if "**Confidence:" in answer:
        try:
            conf_line = [line for line in answer.split('\n') if '**Confidence:' in line][0]
            return int(conf_line.split(':')[1].strip().replace('%**', '').replace('%', ''))
        except Exception:
            pass
    return 0


# %% [markdown]
# ## Section 2b: Knowledge Base Expansion Tools (from Notebook 03)
#
# These tools grow your knowledge base from various sources.
#
# ### add_custom_knowledge

# %% jupyter={"source_hidden": true}
@tool
def add_custom_knowledge(content: str, title: str = "Custom Notes") -> str:
    """
    Add custom notes to knowledge base.

    Parameters
    ----------
        content: Text content to add
        title: Descriptive title for this knowledge

    Returns
    -------
        str: Status message

    Example:
        >>> add_custom_knowledge.invoke({
        ...     "content": "GPU builds on Perlmutter require cudatoolkit/12.2",
        ...     "title": "Perlmutter GPU Notes"
        ... })
    """
    reports_dir = Path(os.getenv('PELE_REPORTS_DIR',
                                  str(Path.cwd().parent / "reports")))

    if not reports_dir.exists():
        reports_dir.mkdir(parents=True)

    # Find next available report number
    existing = sorted(reports_dir.glob("report*.txt"))
    if existing:
        last_num = int(existing[-1].stem.replace("report", ""))
        next_num = last_num + 1
    else:
        next_num = 7  # Start after the original 6

    new_report = reports_dir / f"report{next_num}.txt"

    with open(new_report, 'w') as f:
        f.write(f"=== {title} ===\n\n")
        f.write(content)
        f.write("\n")

    return f"Added {len(content)} chars to {new_report.name}"


# %% [markdown]
# ### ingest_pele_readmes

# %% jupyter={"source_hidden": true}
@tool
def ingest_pele_readmes(repo_path: str) -> str:
    """
    Ingest all README files from PeleC repository.

    Parameters
    ----------
        repo_path: Path to PeleC repository

    Returns
    -------
        str: Status message

    Example:
        >>> ingest_pele_readmes.invoke({"repo_path": "/path/to/PeleC"})
    """
    repo = Path(repo_path).expanduser()
    if not repo.exists():
        return f"[ERROR] Repository not found: {repo}"

    print(f"[INFO] Scanning {repo} for README files...")

    readmes = []
    readme_patterns = ['README*', 'readme*']

    for pattern in readme_patterns:
        for readme_file in repo.rglob(pattern):
            if readme_file.is_file() and readme_file.suffix in ['', '.md', '.txt', '.rst']:
                try:
                    content = readme_file.read_text(encoding='utf-8', errors='ignore')
                    rel_path = readme_file.relative_to(repo)
                    readmes.append(f"=== {rel_path} ===\n{content}\n")
                    print(f"[ OK ] {rel_path}")
                except Exception as e:
                    print(f"[WARN] Could not read {readme_file}: {e}")

    if not readmes:
        return "[WARN] No README files found"

    # Save as new report
    combined = "\n".join(readmes)
    add_custom_knowledge.invoke({
        "content": combined,
        "title": "PeleC README Files"
    })

    return f"Ingested {len(readmes)} README files ({len(combined):,} chars)"


# %% [markdown]
# ### extract_example_parameters

# %% jupyter={"source_hidden": true}
@tool
def extract_example_parameters(repo_path: str, example_dir: str = "Exec") -> str:
    """
    Extract complete simulation setup from example cases.

    Captures: inputs files, YAML configs, prob files, and build configs.

    Parameters
    ----------
        repo_path: Path to PeleC repository
        example_dir: Subdirectory containing examples (default: Exec)

    Returns
    -------
        str: Status message

    Example:
        >>> extract_example_parameters.invoke({"repo_path": "/path/to/PeleC"})
    """
    repo = Path(repo_path).expanduser()
    examples_path = repo / example_dir

    if not examples_path.exists():
        return f"[ERROR] Examples not found: {examples_path}"

    print(f"[INFO] Scanning {examples_path} for test cases...")

    # Discover all test cases
    potential_cases = set()

    # Find by inputs files
    for inputs_file in examples_path.rglob("inputs*"):
        if inputs_file.is_file():
            potential_cases.add(inputs_file.parent)

    for inputs_file in examples_path.rglob("*.inp"):
        if inputs_file.is_file():
            potential_cases.add(inputs_file.parent)

    # Find by GNUmakefile
    for makefile in examples_path.rglob("GNUmakefile"):
        if makefile.is_file():
            potential_cases.add(makefile.parent)

    # Find by prob files
    for prob_file in examples_path.rglob("prob*.cpp"):
        if prob_file.is_file():
            potential_cases.add(prob_file.parent)

    print(f"[ OK ] Found {len(potential_cases)} potential test cases")

    # Organize by category
    test_cases = {}
    case_categories = {
        'RegTests': [],
        'Production': [],
        'UnitTests': [],
        'Other': []
    }

    for case_dir in sorted(potential_cases):
        case_name = case_dir.relative_to(examples_path)

        # Categorize
        category = 'Other'
        if 'RegTests' in str(case_name):
            category = 'RegTests'
        elif 'Production' in str(case_name):
            category = 'Production'
        elif 'UnitTests' in str(case_name):
            category = 'UnitTests'

        case_categories[category].append(case_name)

        # Gather files
        test_cases[case_name] = {
            'path': case_dir,
            'category': category,
            'inputs_files': sorted(list(case_dir.glob("inputs*")) + list(case_dir.glob("*.inp"))),
            'yaml_files': sorted(list(case_dir.glob("*.yaml")) + list(case_dir.glob("*.yml"))),
            'prob_files': sorted(list(case_dir.glob("prob*.cpp")) + list(case_dir.glob("prob*.H"))),
            'build_files': sorted(list(case_dir.glob("GNUmakefile")) + list(case_dir.glob("Make.*"))),
            'readme': None
        }

        # Find README
        for readme_name in ['README.md', 'README.txt', 'README', 'readme.md']:
            readme_path = case_dir / readme_name
            if readme_path.exists():
                test_cases[case_name]['readme'] = readme_path
                break

    # Print summary
    print("\nTest case distribution:")
    for category, cases in case_categories.items():
        if cases:
            print(f"  {category}: {len(cases)} cases")

    # Generate documentation
    param_docs = []
    param_docs.append("=== Complete PeleC Example Case Documentation ===\n")
    param_docs.append(f"Repository: {repo}\n")
    param_docs.append(f"Scanned: {examples_path}\n")
    param_docs.append(f"Total test cases found: {len(test_cases)}\n")
    param_docs.append(f"  - RegTests: {len(case_categories['RegTests'])}\n")
    param_docs.append(f"  - Production: {len(case_categories['Production'])}\n")
    param_docs.append(f"  - UnitTests: {len(case_categories['UnitTests'])}\n")
    param_docs.append(f"  - Other: {len(case_categories['Other'])}\n\n")

    # Prioritize which cases to document
    priority_cases = []

    # All Production cases
    priority_cases.extend([name for name in test_cases
                          if test_cases[name]['category'] == 'Production'])

    # Key RegTests
    regtests_priority = [
        'RegTests/Sod',
        'RegTests/Sedov',
        'RegTests/TG',
        'RegTests/TGReact',
        'RegTests/PMF',
        'RegTests/EB-FlowPastCylinder',
        'RegTests/EB-C12',
        'RegTests/Spray-A-Wbreakup',
        'RegTests/Soot',
    ]

    for priority in regtests_priority:
        for case_name in test_cases:
            if priority in str(case_name) and case_name not in priority_cases:
                priority_cases.append(case_name)

    # Add remaining RegTests up to 20 total
    for case_name in sorted(test_cases.keys()):
        if (
            test_cases[case_name]['category'] == 'RegTests'
            and case_name not in priority_cases
            and len(priority_cases) < 20
        ):
            priority_cases.append(case_name)

    print(f"\nDocumenting {len(priority_cases)} priority cases in detail...")

    # Process each priority case
    for i, case_name in enumerate(priority_cases, 1):
        case_info = test_cases[case_name]
        print(f"[{i}/{len(priority_cases)}] {case_name}...")

        param_docs.append(f"\n{'='*70}\n")
        param_docs.append(f"Test Case: {case_name}\n")
        param_docs.append(f"Category: {case_info['category']}\n")
        param_docs.append(f"Location: {example_dir}/{case_name}\n")
        param_docs.append(f"{'='*70}\n\n")

        # 1. README
        if case_info['readme']:
            try:
                readme_content = case_info['readme'].read_text(encoding='utf-8', errors='ignore')
                param_docs.append("--- README ---\n\n")
                param_docs.append(readme_content[:1500])
                if len(readme_content) > 1500:
                    param_docs.append("\n... (truncated)")
                param_docs.append("\n\n")
            except Exception:
                pass

        # 2. Inputs files
        for inputs_file in case_info['inputs_files']:
            try:
                content = inputs_file.read_text(encoding='utf-8', errors='ignore')

                param_docs.append(f"--- Inputs: {inputs_file.name} ---\n\n")

                # Auto-detect parameter sections
                prefixes = {}
                for line in content.split('\n'):
                    line_stripped = line.strip()

                    if not line_stripped or line_stripped.startswith('#'):
                        continue

                    if '=' in line_stripped and '.' in line_stripped.split('=')[0]:
                        param_name = line_stripped.split('=')[0].strip()
                        if '.' in param_name:
                            prefix = param_name.split('.')[0]

                            if prefix not in prefixes:
                                prefixes[prefix] = []

                            prefixes[prefix].append(line_stripped)

                param_docs.append("```ini\n")
                for prefix in sorted(prefixes.keys()):
                    params = prefixes[prefix]
                    param_docs.append(f"# {prefix.upper()} ({len(params)} parameters)\n")
                    for param in params[:15]:
                        param_docs.append(param + '\n')
                    if len(params) > 15:
                        param_docs.append(f"# ... and {len(params) - 15} more\n")
                    param_docs.append("\n")
                param_docs.append("```\n\n")

            except Exception:
                pass

        # 3. YAML files
        for yaml_file in case_info['yaml_files']:
            try:
                content = yaml_file.read_text(encoding='utf-8', errors='ignore')

                param_docs.append(f"--- YAML: {yaml_file.name} ---\n\n")

                if 'mech' in yaml_file.name.lower() or 'chem' in yaml_file.name.lower():
                    param_docs.append("Chemistry mechanism file\n\n")

                param_docs.append("Preview:\n```yaml\n")
                param_docs.append(content[:800])
                if len(content) > 800:
                    param_docs.append("\n...")
                param_docs.append("\n```\n\n")

            except Exception:
                pass

        # 4. Build configuration
        for build_file in case_info['build_files']:
            if build_file.name == 'GNUmakefile':
                try:
                    content = build_file.read_text(encoding='utf-8', errors='ignore')

                    param_docs.append(f"--- Build Config: {build_file.name} ---\n\n")

                    # Extract key variables
                    build_vars = {}
                    for line in content.split('\n'):
                        line_stripped = line.strip()

                        if line_stripped.startswith('#'):
                            continue

                        if '=' in line_stripped and not line_stripped.startswith('ifeq'):
                            var_match = re.match(r'(\w+)\s*[?:]?=\s*(.+)', line_stripped)
                            if var_match:
                                var_name = var_match.group(1)
                                var_value = var_match.group(2)

                                if var_name in ['COMP', 'USE_MPI', 'USE_CUDA', 'USE_HIP',
                                              'DIM', 'CHEMISTRY_MODEL', 'Eos_dir', 'Transport_dir']:
                                    build_vars[var_name] = var_value

                    if build_vars:
                        param_docs.append("Build configuration:\n```makefile\n")
                        for var, val in sorted(build_vars.items()):
                            param_docs.append(f"{var} = {val}\n")
                        param_docs.append("```\n\n")

                except Exception:
                    pass

        # 5. Problem definition
        if case_info['prob_files']:
            param_docs.append(f"Problem-specific files: {', '.join(f.name for f in case_info['prob_files'])}\n\n")

    # Add index of all cases
    param_docs.append(f"\n{'='*70}\n")
    param_docs.append("COMPLETE TEST CASE INDEX\n")
    param_docs.append(f"{'='*70}\n\n")

    for category in ['Production', 'RegTests', 'Other']:
        if case_categories[category]:
            param_docs.append(f"\n{category} ({len(case_categories[category])} cases):\n")
            for case in sorted(case_categories[category]):
                param_docs.append(f"  - {case}\n")

    combined = "\n".join(param_docs)
    add_custom_knowledge.invoke({
        "content": combined,
        "title": "PeleC Example Cases - Complete Inventory"
    })

    return f"Documented {len(priority_cases)} cases, indexed {len(test_cases)} total ({len(combined):,} chars)"


# %% [markdown]
# ### ingest_sphinx_docs

# %% jupyter={"source_hidden": true}
@tool
def ingest_sphinx_docs(docs_path: str) -> str:
    """
    Convert Sphinx RST docs to text and add to knowledge base.

    Parameters
    ----------
        docs_path: Path to Sphinx documentation directory

    Returns
    -------
        str: Status message

    Example:
        >>> ingest_sphinx_docs.invoke({"docs_path": "/path/to/PeleC/Docs"})
    """
    docs = Path(docs_path).expanduser()
    if not docs.exists():
        return f"[WARN] Docs not found: {docs}"

    if not HAS_PANDOC:
        return "[WARN] pandoc package not installed (pip install pandoc)"

    print(f"[INFO] Converting RST docs from {docs}...")

    rst_files = list(docs.rglob("*.rst"))
    if not rst_files:
        return f"[WARN] No RST files found in {docs}"

    print(f"[ OK ] Found {len(rst_files)} RST files")

    converted = []
    for rst_file in rst_files[:10]:  # Limit to 10 files
        try:
            # Read RST file
            with open(rst_file, encoding='utf-8') as f:
                rst_content = f.read()

            # Convert using Python pandoc
            import pandoc
            doc = pandoc.read(rst_content, format='rst')
            plain_text = pandoc.write(doc, format='plain')

            rel_path = rst_file.relative_to(docs)
            converted.append(f"=== {rel_path} ===\n{plain_text}\n")
            print(f"[ OK ] Converted {rel_path}")

        except Exception as e:
            print(f"[WARN] Could not convert {rst_file}: {e}")

    if converted:
        combined = "\n".join(converted)
        add_custom_knowledge.invoke({
            "content": combined,
            "title": "Sphinx Documentation"
        })
        return f"Converted {len(converted)} RST files ({len(combined):,} chars)"
    else:
        return "[WARN] No files converted"


# %% [markdown]
# ### ingest_warpx_hpc_docs

# %% jupyter={"source_hidden": true}
@tool
def ingest_warpx_hpc_docs(source: str = "github") -> str:
    """
    Ingest WarpX HPC center documentation (build recipes, modules, batch scripts).

    Parameters
    ----------
        source: 'github' to fetch from repo, or local path

    Returns
    -------
        str: Status message

    Example:
        >>> ingest_warpx_hpc_docs.invoke({})
    """
    if not HAS_REQUESTS:
        return "[ERROR] requests package not installed"

    import requests

    # WarpX docs have system-specific build instructions
    warpx_hpc_urls = {
        'perlmutter': 'https://raw.githubusercontent.com/ECP-WarpX/WarpX/development/Docs/source/install/hpc/perlmutter.rst',
        'frontier': 'https://raw.githubusercontent.com/ECP-WarpX/WarpX/development/Docs/source/install/hpc/frontier.rst',
        'summit': 'https://raw.githubusercontent.com/ECP-WarpX/WarpX/development/Docs/source/install/hpc/summit.rst',
        'polaris': 'https://raw.githubusercontent.com/ECP-WarpX/WarpX/development/Docs/source/install/hpc/polaris.rst',
        'crusher': 'https://raw.githubusercontent.com/ECP-WarpX/WarpX/development/Docs/source/install/hpc/crusher.rst',
    }

    print("[INFO] Fetching WarpX HPC documentation...")

    docs_content = []
    docs_content.append("=== WarpX HPC Build Patterns ===\n")
    docs_content.append("Adapted from WarpX documentation - AMReX build patterns applicable to Pele\n")
    docs_content.append("Source: https://github.com/ECP-WarpX/WarpX\n\n")

    fetched_count = 0
    for system, url in warpx_hpc_urls.items():
        try:
            print(f"[INFO] Fetching {system} docs...")
            response = requests.get(url, timeout=15)

            if response.status_code == 200:
                content = response.text
                docs_content.append(f"\n{'='*60}\n")
                docs_content.append(f"--- {system.upper()} Build Pattern ---\n")
                docs_content.append(f"{'='*60}\n\n")
                docs_content.append(content)
                docs_content.append("\n")
                fetched_count += 1
                print(f"[ OK ] {system}: {len(content):,} chars")
            else:
                print(f"[WARN] {system}: HTTP {response.status_code}")

        except requests.RequestException as e:
            print(f"[WARN] {system}: {e}")

    combined = "\n".join(docs_content)

    if fetched_count > 0:
        add_custom_knowledge.invoke({
            "content": combined,
            "title": "HPC Build Patterns (WarpX)"
        })
        return f"Ingested {fetched_count} system build docs ({len(combined):,} chars)"
    else:
        return "[WARN] No docs fetched (network issue?)"


# %% [markdown]
# ### ingest_weakscaling_patterns

# %% jupyter={"source_hidden": true}
@tool
def ingest_weakscaling_patterns(repo_paths: str = None) -> str:
    """
    Extract weak scaling patterns from PeleC/PeleLMeX test scripts.

    Parameters
    ----------
        repo_paths: JSON list of paths to search (default: PeleC regtest scripts)

    Returns
    -------
        str: Status message

    Example:
        >>> ingest_weakscaling_patterns.invoke({
        ...     "repo_paths": '["/path/to/PeleC", "/path/to/PeleLMeX"]'
        ... })
    """
    if repo_paths:
        paths = json.loads(repo_paths)
    else:
        # Default paths
        pelec = Path(os.getenv('PELEC_ROOT', '/path/to/PeleC')).expanduser()
        paths = [pelec]

    print("[INFO] Scanning for scaling test scripts...")

    scaling_docs = []
    scaling_docs.append("=== Weak Scaling Patterns from PeleC Tests ===\n\n")

    patterns_found = 0

    for repo_path in paths:
        repo = Path(repo_path).expanduser()
        if not repo.exists():
            print(f"[WARN] Path not found: {repo}")
            continue

        # Look for regtest scripts
        test_scripts = list(repo.rglob("*test*.sh")) + list(repo.rglob("*regtest*.py"))

        print(f"[ OK ] Found {len(test_scripts)} test scripts in {repo.name}")

        for script in test_scripts:
            try:
                content = script.read_text(encoding='utf-8', errors='ignore')

                # Look for scaling patterns
                has_scaling = False

                # Check for node count patterns
                if re.search(r'(nodes?|ranks?|procs?)\s*=.*\d+', content, re.IGNORECASE):
                    has_scaling = True

                # Check for problem size patterns
                if re.search(r'(n_cell|grid|domain).*\d+', content, re.IGNORECASE):
                    has_scaling = True

                # Check for batch script generation
                if 'sbatch' in content or 'qsub' in content:
                    has_scaling = True

                if has_scaling:
                    rel_path = script.relative_to(repo)
                    scaling_docs.append(f"\n--- {rel_path} ---\n\n")

                    # Extract key lines
                    key_lines = []
                    for line in content.split('\n'):
                        if any(pattern in line.lower() for pattern in
                               ['nodes', 'ranks', 'n_cell', 'grid', 'sbatch', 'mpi']):
                            key_lines.append(line.strip())

                    if key_lines:
                        scaling_docs.append("Key parameters:\n```bash\n")
                        for line in key_lines[:20]:
                            if line:
                                scaling_docs.append(line + '\n')
                        scaling_docs.append("```\n\n")

                    patterns_found += 1
                    print(f"[ OK ] {rel_path}")

            except Exception:
                pass

    if patterns_found > 0:
        combined = "\n".join(scaling_docs)
        add_custom_knowledge.invoke({
            "content": combined,
            "title": "Weak Scaling Test Patterns"
        })
        return f"Extracted {patterns_found} scaling patterns ({len(combined):,} chars)"
    else:
        return "[WARN] No scaling patterns found"


# %% [markdown]
# ### ingest_amrex_perf_scripts

# %%
@tool
def ingest_amrex_perf_scripts(amrex_path: str = None, include_external: bool = False) -> str:
    """
    Harvest performance testing scripts from AMReX and related projects.

    Parameters
    ----------
        amrex_path: Path to AMReX repo (default: $AMREX_HOME or auto-detect)
        include_external: Also fetch from Castro, WarpX, etc.

    Returns
    -------
        str: Status message

    Example:
        >>> ingest_amrex_perf_scripts.invoke({
        ...     "amrex_path": "/path/to/amrex",
        ...     "include_external": True
        ... })
    """
    # Determine AMReX path
    if amrex_path is None:
        amrex_path = os.getenv('AMREX_HOME')
        if amrex_path is None:
            # Try to detect from PeleC submodule
            pelec = Path(os.getenv('PELEC_ROOT', '.')).expanduser()
            amrex_candidate = pelec / 'Submodules' / 'AMReX'
            if amrex_candidate.exists():
                amrex_path = str(amrex_candidate)
            else:
                return "[ERROR] Cannot find AMReX. Set AMREX_HOME or amrex_path"

    amrex = Path(amrex_path).expanduser()
    if not amrex.exists():
        return f"[ERROR] AMReX not found: {amrex}"

    print(f"[INFO] Scanning {amrex} for performance scripts...")

    perf_docs = []
    perf_docs.append("=== AMReX Performance Testing Patterns ===\n")
    perf_docs.append(f"Source: {amrex}\n\n")

    # Look for performance-related files
    perf_patterns = [
        '*perf*.sh',
        '*perf*.py',
        '*scaling*.sh',
        '*scaling*.py',
        '*benchmark*.sh',
        '*benchmark*.py',
        'run*.sh',
        'job*.sh'
    ]

    found_scripts = set()
    for pattern in perf_patterns:
        for script in amrex.rglob(pattern):
            if script.is_file():
                found_scripts.add(script)

    print(f"[ OK ] Found {len(found_scripts)} performance-related scripts")

    # Process scripts
    for i, script in enumerate(sorted(found_scripts)[:15], 1):  # Limit to 15
        try:
            content = script.read_text(encoding='utf-8', errors='ignore')
            rel_path = script.relative_to(amrex)

            perf_docs.append(f"\n--- {rel_path} ---\n\n")

            # Extract relevant sections
            if content.startswith('#!'):
                shebang = content.split('\n')[0]
                perf_docs.append(f"Script type: {shebang}\n\n")

            # Look for key performance parameters
            key_sections = []
            in_key_section = False

            for line in content.split('\n'):
                line_lower = line.lower()

                # Detect key sections
                if any(kw in line_lower for kw in ['mpi', 'omp', 'gpu', 'node', 'rank', 'thread']):
                    in_key_section = True
                    key_sections.append(line)
                elif in_key_section and line.strip():
                    key_sections.append(line)
                    if len(key_sections) > 3:
                        in_key_section = False

            if key_sections:
                perf_docs.append("Performance parameters:\n```bash\n")
                for line in key_sections[:25]:
                    perf_docs.append(line + '\n')
                perf_docs.append("```\n\n")

            print(f"[{i}/15] {rel_path}")

        except Exception:
            pass

    # Fetch external scripts if requested
    if include_external:
        external = _fetch_external_amrex_scripts()
        if external:
            perf_docs.append("\n" + external)

    combined = "\n".join(perf_docs)
    add_custom_knowledge.invoke({
        "content": combined,
        "title": "AMReX Performance Scripts"
    })

    return f"Ingested {min(len(found_scripts), 15)} scripts ({len(combined):,} chars)"


def _fetch_external_amrex_scripts():
    """Fetch performance scripts from Castro and WarpX repositories."""
    if not HAS_REQUESTS:
        return None

    import requests

    external_scripts = []
    external_scripts.append("\n=== External AMReX Project Scripts ===\n\n")

    # Castro weak scaling example
    castro_urls = [
        ('Castro/flame_wave', 'https://raw.githubusercontent.com/AMReX-Astro/Castro/main/Exec/science/flame_wave/scaling/batch_perlmutter.sh'),
    ]

    # WarpX scaling examples
    warpx_urls = [
        ('WarpX/laser_acceleration', 'https://raw.githubusercontent.com/ECP-WarpX/WarpX/development/Examples/Physics_applications/laser_acceleration/batch_perlmutter.sh'),
    ]

    all_urls = castro_urls + warpx_urls

    for name, url in all_urls:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                external_scripts.append(f"\n--- {name} ---\n\n")
                external_scripts.append("```bash\n")
                external_scripts.append(response.text[:1000])
                if len(response.text) > 1000:
                    external_scripts.append("\n... (truncated)")
                external_scripts.append("\n```\n\n")
                print(f"[ OK ] Fetched {name}")
        except Exception as e:
            print(f"[WARN] Could not fetch {name}: {e}")

    return "\n".join(external_scripts) if len(external_scripts) > 1 else None


# %% [markdown]
# ### document_current_modules

# %% jupyter={"source_hidden": true}
@tool
def document_current_modules() -> str:
    """
    Document currently loaded modules (Lmod/Environment Modules).

    Useful for recording working build environments.

    Returns
    -------
        str: Status message

    Example:
        >>> document_current_modules.invoke({})
    """
    print("[INFO] Capturing current module environment...")

    module_info = []
    module_info.append("=== Current Module Environment ===\n")
    module_info.append(f"Captured: {datetime.now().isoformat()}\n")
    module_info.append(f"System: {socket.getfqdn()}\n\n")

    # Try to get loaded modules
    try:
        result = subprocess.run(['module', 'list'],
                              capture_output=True, text=True,
                              stderr=subprocess.STDOUT)

        if result.returncode == 0:
            module_info.append("--- Loaded Modules ---\n\n")
            module_info.append("```\n")
            module_info.append(result.stdout)
            module_info.append("```\n\n")
        else:
            module_info.append("[WARN] 'module list' failed (not on HPC system?)\n\n")

    except FileNotFoundError:
        module_info.append("[WARN] 'module' command not found\n\n")

    # Get key environment variables
    module_info.append("--- Key Environment Variables ---\n\n")
    key_vars = [
        'COMPILER', 'CC', 'CXX', 'FC',
        'MPI_ROOT', 'MPICH_DIR', 'OMPI_DIR',
        'CUDA_HOME', 'ROCM_PATH',
        'CMAKE_PREFIX_PATH',
        'LD_LIBRARY_PATH',
        'MODULEPATH',
        'LMOD_SYSTEM_NAME',
    ]

    module_info.append("```bash\n")
    for var in key_vars:
        value = os.getenv(var)
        if value:
            # Truncate long paths
            if len(value) > 100:
                value = value[:50] + '...' + value[-47:]
            module_info.append(f"{var}={value}\n")
    module_info.append("```\n\n")

    combined = "\n".join(module_info)
    result = add_custom_knowledge.invoke({
        "content": combined,
        "title": f"Module Environment - {socket.gethostname()}"
    })

    return f"Documented module environment ({len(combined):,} chars)"


# %% [markdown]
# ### ingest_nersc_docs

# %% jupyter={"source_hidden": true}
@tool
def ingest_nersc_docs(topics: str = None, auto_discover: bool = True) -> str:
    """
    Ingest NERSC documentation for relevant topics.

    Parameters
    ----------
        topics: JSON dict of topics to URLs (optional)
        auto_discover: If True, fetch common topics automatically

    Returns
    -------
        str: Status message

    Example:
        >>> ingest_nersc_docs.invoke({"auto_discover": True})
    """
    if not HAS_REQUESTS:
        return "[ERROR] requests package not installed"

    import requests

    # Default topics for auto-discovery
    default_topics = {
        'perlmutter_cpu': 'https://docs.nersc.gov/systems/perlmutter/architecture/',
        'compiling': 'https://docs.nersc.gov/development/compilers/compilers-overview/',
        'modules': 'https://docs.nersc.gov/environment/software-modules/',
        'slurm': 'https://docs.nersc.gov/jobs/examples/',
        'performance': 'https://docs.nersc.gov/performance/',
        'debugging': 'https://docs.nersc.gov/development/debugging/debugging-overview/',
    }

    if topics:
        topic_dict = json.loads(topics)
    elif auto_discover:
        topic_dict = default_topics
    else:
        return "[ERROR] Must provide topics or set auto_discover=True"

    print(f"[INFO] Fetching NERSC documentation for {len(topic_dict)} topics...")

    docs_content = []
    docs_content.append("=== NERSC Documentation ===\n")
    docs_content.append(f"Retrieved: {datetime.now().isoformat()}\n\n")

    fetched_count = 0
    for topic, url in topic_dict.items():
        try:
            print(f"[INFO] Fetching {topic}...")
            response = requests.get(url, timeout=20)

            if response.status_code == 200:
                # Extract text (simple approach - just get the HTML)
                html = response.text

                # Very basic HTML to text (in production, use BeautifulSoup)
                # Remove script and style tags
                text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                # Clean whitespace
                text = re.sub(r'\s+', ' ', text).strip()

                docs_content.append(f"\n--- {topic.upper()} ---\n")
                docs_content.append(f"Source: {url}\n\n")
                docs_content.append(text[:2000])  # Limit per topic
                if len(text) > 2000:
                    docs_content.append("\n... (truncated)")
                docs_content.append("\n\n")

                fetched_count += 1
                print(f"[ OK ] {topic}: {len(text):,} chars")
            else:
                print(f"[WARN] {topic}: HTTP {response.status_code}")

        except requests.RequestException as e:
            print(f"[WARN] {topic}: {e}")

    combined = "\n".join(docs_content)

    if fetched_count > 0:
        add_custom_knowledge.invoke({
            "content": combined,
            "title": "NERSC Documentation"
        })
        return f"Ingested {fetched_count} NERSC doc pages ({len(combined):,} chars)"
    else:
        return "[WARN] No docs fetched"


# %% [markdown]
# ### search_nersc_docs

# %% jupyter={"source_hidden": true}
@tool
def search_nersc_docs(search_terms: str = None) -> str:
    """
    Search NERSC documentation site.

    Parameters
    ----------
        search_terms: JSON list of search terms

    Returns
    -------
        str: Search results as text

    Example:
        >>> search_nersc_docs.invoke({
        ...     "search_terms": '["perlmutter gpu", "cmake modules"]'
        ... })
    """
    if not HAS_REQUESTS:
        return "[ERROR] requests package not installed"

    if not search_terms:
        return "[ERROR] Must provide search_terms"

    terms = json.loads(search_terms)

    import requests

    results = []
    results.append("=== NERSC Documentation Search Results ===\n\n")

    for term in terms:
        # Use NERSC docs search (note: this is a simplified approach)
        search_url = f"https://docs.nersc.gov/search/?q={term.replace(' ', '+')}"

        try:
            print(f"[INFO] Searching for: {term}")
            response = requests.get(search_url, timeout=15)

            if response.status_code == 200:
                results.append(f"\n--- Search: {term} ---\n\n")
                results.append(f"URL: {search_url}\n\n")

                # Extract search results (simple HTML parsing)
                html = response.text

                # Look for result snippets (this is VERY basic - use BeautifulSoup in production)
                snippets = re.findall(r'<div class="context">([^<]+)</div>', html)

                if snippets:
                    results.append("Top results:\n")
                    for i, snippet in enumerate(snippets[:5], 1):
                        clean = re.sub(r'\s+', ' ', snippet).strip()
                        results.append(f"{i}. {clean}\n")
                    results.append("\n")
                else:
                    results.append("(No snippets found - visit URL for results)\n\n")

                print(f"[ OK ] {len(snippets)} results found")
            else:
                print(f"[WARN] HTTP {response.status_code}")

        except requests.RequestException as e:
            print(f"[WARN] {e}")

    combined = "\n".join(results)

    # Add to knowledge base
    add_custom_knowledge.invoke({
        "content": combined,
        "title": "NERSC Search Results"
    })

    return combined


# %% [markdown]
# ### create_comprehensive_build_guide

# %% jupyter={"source_hidden": true}
@tool
def create_comprehensive_build_guide(system: str = None) -> str:
    """
    Synthesize all collected knowledge into a comprehensive build guide.

    Parameters
    ----------
        system: Target system (perlmutter, frontier, etc.) or None for all

    Returns
    -------
        str: Status message

    Example:
        >>> create_comprehensive_build_guide.invoke({"system": "perlmutter"})
    """
    print("[INFO] Creating comprehensive build guide...")

    # Detect current system if not specified
    if system is None:
        from_env, system = _detect_hpc_system()
        if system == "unknown":
            system = "generic"

    guide = []
    guide.append(f"=== Comprehensive PeleC Build Guide for {system.upper()} ===\n")
    guide.append(f"Generated: {datetime.now().isoformat()}\n")
    guide.append("Sources: Knowledge base reports + system documentation\n\n")

    # Section 1: System Information
    guide.append("## 1. SYSTEM INFORMATION\n\n")

    if HAS_OPENAI:
        try:
            sys_info = ask_pele_question.invoke({
                "question": f"What are the key characteristics of {system} for running PeleC?",
                "use_full_knowledge": True
            })
            guide.append(sys_info)
            guide.append("\n\n")
        except Exception:
            pass

    # Section 2: Module Environment
    guide.append("## 2. MODULE ENVIRONMENT\n\n")

    if HAS_OPENAI:
        try:
            modules = ask_pele_question.invoke({
                "question": f"What modules should I load for PeleC on {system}?",
                "use_full_knowledge": True
            })
            guide.append(modules)
            guide.append("\n\n")
        except Exception:
            pass

    # Section 3: Build Commands
    guide.append("## 3. BUILD COMMANDS\n\n")

    if HAS_OPENAI:
        try:
            build = ask_pele_question.invoke({
                "question": f"How do I build PeleC on {system}? Include make commands.",
                "use_full_knowledge": True
            })
            guide.append(build)
            guide.append("\n\n")
        except Exception:
            pass

    # Section 4: Running Jobs
    guide.append("## 4. RUNNING JOBS\n\n")

    if HAS_OPENAI:
        try:
            jobs = ask_pele_question.invoke({
                "question": f"How do I submit and run PeleC jobs on {system}?",
                "use_full_knowledge": True
            })
            guide.append(jobs)
            guide.append("\n\n")
        except Exception:
            pass

    # Section 5: Performance Tips
    guide.append("## 5. PERFORMANCE OPTIMIZATION\n\n")

    if HAS_OPENAI:
        try:
            perf = ask_pele_question.invoke({
                "question": f"What are best practices for performance on {system}?",
                "use_full_knowledge": True
            })
            guide.append(perf)
            guide.append("\n\n")
        except Exception:
            pass

    # Section 6: Common Issues
    guide.append("## 6. TROUBLESHOOTING\n\n")

    if HAS_OPENAI:
        try:
            issues = ask_pele_question.invoke({
                "question": f"What are common build or runtime issues on {system}?",
                "use_full_knowledge": True
            })
            guide.append(issues)
            guide.append("\n\n")
        except Exception:
            pass

    combined = "\n".join(guide)

    # Save as knowledge
    add_custom_knowledge.invoke({
        "content": combined,
        "title": f"Complete Build Guide - {system}"
    })

    # Also write to file
    output_file = Path(f"build_guide_{system}.md")
    output_file.write_text(combined)

    return f"Created {output_file} ({len(combined):,} chars)"


# %% [markdown]
# ### GitHub Tools (from utils/pele_assistant.py)

# %% jupyter={"source_hidden": true}
@tool
def fetch_github_docs(topic: str) -> str:
    """
    Fetch latest documentation from PeleC GitHub.

    Parameters
    ----------
        topic: What to fetch (e.g., 'README', 'sphinx', 'examples')

    Returns
    -------
        str: Fetched documentation

    Example:
        >>> docs = fetch_github_docs.invoke({"topic": "README"})
    """
    if not HAS_GITHUB:
        return "[ERROR] PyGithub not installed"

    try:
        g = Github()
        repo = g.get_repo("AMReX-Combustion/PeleC")

        if topic.lower() == 'readme':
            readme = repo.get_readme()
            content = readme.decoded_content.decode('utf-8')
            return f"=== PeleC README ===\n\n{content}"

        elif topic.lower() == 'sphinx':
            # Fetch Sphinx docs
            docs_path = "Docs/source"
            try:
                contents = repo.get_contents(docs_path, ref="development")
                rst_files = [c for c in contents if c.name.endswith('.rst')]

                docs = []
                for rst_file in rst_files[:5]:  # Limit to 5 files
                    file_content = repo.get_contents(rst_file.path, ref="development")
                    text = file_content.decoded_content.decode('utf-8')
                    docs.append(f"=== {rst_file.name} ===\n\n{text}\n")

                return "\n".join(docs)
            except Exception as e:
                return f"[ERROR] Could not fetch sphinx docs: {e}"

        elif topic.lower() == 'examples':
            # List available examples
            exec_path = "Exec/RegTests"
            try:
                contents = repo.get_contents(exec_path, ref="development")
                examples = [c.name for c in contents if c.type == "dir"]

                return "=== PeleC Examples ===\n\nAvailable examples:\n" + "\n".join(f"- {ex}" for ex in examples)
            except Exception as e:
                return f"[ERROR] Could not list examples: {e}"

        else:
            return f"[ERROR] Unknown topic: {topic}. Try: README, sphinx, examples"

    except Exception as e:
        return f"[ERROR] GitHub fetch failed: {e}"


@tool
def search_github_issues(query: str, max_results: int = 5) -> str:
    """
    Search PeleC GitHub issues for solutions to errors.

    Parameters
    ----------
        query: Search query (e.g., error message)
        max_results: Number of results to return

    Returns
    -------
        str: Formatted search results

    Example:
        >>> issues = search_github_issues.invoke({
        ...     "query": "segmentation fault",
        ...     "max_results": 3
        ... })
    """
    if not HAS_GITHUB:
        return "[ERROR] PyGithub not installed"

    try:
        g = Github()
        repo = g.get_repo("AMReX-Combustion/PeleC")

        # Search issues
        issues = repo.get_issues(state='all')

        results = []
        results.append(f"=== GitHub Issues Search: '{query}' ===\n\n")

        found = 0
        for issue in issues:
            if found >= max_results:
                break

            # Simple text search
            if query.lower() in issue.title.lower() or query.lower() in (issue.body or "").lower():
                results.append(f"#{issue.number}: {issue.title}\n")
                results.append(f"State: {issue.state}\n")
                results.append(f"URL: {issue.html_url}\n")

                if issue.body:
                    body_preview = issue.body[:200].replace('\n', ' ')
                    results.append(f"Preview: {body_preview}...\n")

                # Get first comment if exists
                if issue.comments > 0:
                    comments = issue.get_comments()
                    first_comment = list(comments)[0]
                    comment_preview = first_comment.body[:200].replace('\n', ' ')
                    results.append(f"First comment: {comment_preview}...\n")

                results.append("\n")
                found += 1

        if found == 0:
            results.append("No issues found matching query.\n")

        return "\n".join(results)

    except Exception as e:
        return f"[ERROR] Issue search failed: {e}"


# %% [markdown]
# ## Section 3: Config Building (from Notebook 04)
#
# Interactive configuration builder using LLM knowledge base.
#
# ### start_simulation_config

# %% jupyter={"source_hidden": true}
@tool
def start_simulation_config(user_intent: str, knowledge_base_size: str = "auto") -> dict:
    """
    Begin interactive simulation setup from natural language intent.

    Parameters
    ----------
        user_intent: User's description (e.g., "2D methane flame with AMR")
        knowledge_base_size: "auto" uses full knowledge, "summary" for faster

    Returns
    -------
        dict: Initial config with detected parameters and clarifying questions

    Example:
        >>> config = start_simulation_config.invoke({"user_intent": "2D methane flame with AMR"})
        >>> print(config['detected'])
        >>> print(config['questions'])
    """
    config = {
        "user_intent": user_intent,
        "detected": {},
        "questions": [],
        "partial_config": {},
        "timestamp": datetime.now().isoformat()
    }

    intent_lower = user_intent.lower()

    # Detect dimension
    if "2d" in intent_lower or "two-dimensional" in intent_lower:
        config["detected"]["dims"] = 2
    elif "3d" in intent_lower or "three-dimensional" in intent_lower:
        config["detected"]["dims"] = 3
    else:
        config["questions"].append("Dimensions? (2D or 3D)")

    # Detect fuel type
    fuels = {
        "ch4": "CH4", "methane": "CH4",
        "h2": "H2", "hydrogen": "H2",
        "c2h4": "C2H4", "ethylene": "C2H4",
        "c12h26": "C12H26", "dodecane": "C12H26",
    }
    for key, value in fuels.items():
        if key in intent_lower:
            config["detected"]["fuel"] = value
            break
    else:
        config["questions"].append("Fuel type? (CH4, H2, C2H4, C12H26, or other)")

    # Detect AMR
    if "amr" in intent_lower or "adaptive" in intent_lower:
        config["detected"]["use_amr"] = True
        config["questions"].append("How many AMR levels? (0-3 recommended)")
    else:
        config["partial_config"]["amr"] = {"max_level": "0"}

    # Detect chemistry
    if "no chemistry" in intent_lower or "inert" in intent_lower:
        config["detected"]["chemistry"] = False
        config["partial_config"]["pelec"] = {"do_react": "0"}
    elif "chemistry" in intent_lower or "react" in intent_lower:
        config["detected"]["chemistry"] = True
        config["partial_config"]["pelec"] = {"do_react": "1"}

    # Detect problem type
    if "flame" in intent_lower or "pmf" in intent_lower:
        config["detected"]["problem_type"] = "flame"
    elif "detonation" in intent_lower:
        config["detected"]["problem_type"] = "detonation"
    elif "shock" in intent_lower or "sedov" in intent_lower:
        config["detected"]["problem_type"] = "shock"

    # Ask knowledge base for recommendations
    if "fuel" in config["detected"] and HAS_OPENAI:
        try:
            use_full = knowledge_base_size == "auto"
            kb_question = f"What are typical parameters for a {config['detected']['fuel']} flame simulation?"
            kb_answer = ask_pele_question.invoke({
                "question": kb_question,
                "use_full_knowledge": use_full
            })
            config["kb_suggestions"] = kb_answer
        except Exception as e:
            config["kb_suggestions"] = f"Could not query knowledge base: {e}"

    return config


# %% [markdown]
# ### add_config_answer

# %% jupyter={"source_hidden": true}
@tool
def add_config_answer(config_json: str, question: str, answer: str) -> str:
    """
    Add user's answer to a configuration question.

    Parameters
    ----------
        config_json: Current config as JSON string
        question: Which question is being answered
        answer: User's response

    Returns
    -------
        str: Updated config as JSON string

    Example:
        >>> config_json = add_config_answer.invoke({
        ...     "config_json": config_json,
        ...     "question": "Fuel type?",
        ...     "answer": "CH4"
        ... })
    """
    config = json.loads(config_json)

    # Parse answer based on question
    if "fuel" in question.lower():
        if "partial_config" not in config:
            config["partial_config"] = {}
        if "prob" not in config["partial_config"]:
            config["partial_config"]["prob"] = {}

        config["partial_config"]["prob"]["fuel"] = answer.upper()
        config["questions"].append(f"Equivalence ratio for {answer}? (0.6-1.4 typical)")

    elif "dimension" in question.lower():
        dims = 2 if "2" in answer else 3
        config["detected"]["dims"] = dims

        if HAS_OPENAI:
            try:
                kb_q = f"What is a typical domain size for a {dims}D flame simulation?"
                kb_a = ask_pele_question.invoke({"question": kb_q, "use_full_knowledge": False})
                config["questions"].append(f"Domain size? (meters, {kb_a[:100]}...)")
            except Exception:
                config["questions"].append("Domain size in meters? (e.g., '0.016 0.016' for 2D)")
        else:
            config["questions"].append("Domain size in meters? (e.g., '0.016 0.016' for 2D)")

    elif "amr level" in question.lower():
        max_level = int(answer)
        if "partial_config" not in config:
            config["partial_config"] = {}
        if "amr" not in config["partial_config"]:
            config["partial_config"]["amr"] = {}

        config["partial_config"]["amr"]["max_level"] = str(max_level)

        if max_level > 0:
            config["questions"].append("Refine on? (gradT, vort, density, or combination)")

    elif "equivalence ratio" in question.lower():
        phi = float(answer)
        if "prob" not in config["partial_config"]:
            config["partial_config"]["prob"] = {}
        config["partial_config"]["prob"]["phi"] = str(phi)

    elif "domain size" in question.lower():
        domain_values = [float(x) for x in answer.split()]

        if "partial_config" not in config:
            config["partial_config"] = {}
        if "geometry" not in config["partial_config"]:
            config["partial_config"]["geometry"] = {}

        config["partial_config"]["geometry"]["prob_hi"] = " ".join(map(str, domain_values))
        config["partial_config"]["geometry"]["prob_lo"] = " ".join(["0.0"] * len(domain_values))

    elif "refine" in question.lower():
        # Refinement criteria
        if "amr" not in config["partial_config"]:
            config["partial_config"]["amr"] = {}

        # Parse refinement criteria
        criteria = answer.lower().split()
        if "gradt" in criteria or "temperature" in criteria:
            config["partial_config"]["amr"]["refinement_indicators"] = "gradT"
        if "vort" in criteria or "vorticity" in criteria:
            config["partial_config"]["amr"]["refinement_indicators"] = "vort"

    # Remove answered question
    config["questions"] = [q for q in config["questions"] if q != question]

    return json.dumps(config, indent=2)


# %% [markdown]
# ### finalize_config

# %% jupyter={"source_hidden": true}
@tool
def finalize_config(partial_config_json: str, baseline_example: str = "pmf-lidryer") -> str:
    """
    Convert partial config to complete Pele configuration.

    Fills in defaults from baseline example.

    Parameters
    ----------
        partial_config_json: Partial config from interactive builder (JSON)
        baseline_example: Which example to use as baseline

    Returns
    -------
        str: Complete configuration as JSON

    Example:
        >>> final = finalize_config.invoke({
        ...     "partial_config_json": partial_json,
        ...     "baseline_example": "sedov-1"
        ... })
    """
    partial = json.loads(partial_config_json)

    # Fetch baseline example
    if HAS_GITHUB:
        baseline_file = fetch_pele_example(baseline_example, save_dir=Path("/tmp"))
        if baseline_file and baseline_file.exists():
            baseline_dict = parse_pele_inputs(baseline_file)
        else:
            baseline_dict = _get_fallback_defaults(partial.get("detected", {}))
    else:
        baseline_dict = _get_fallback_defaults(partial.get("detected", {}))

    # Deep merge partial into baseline
    config = _deep_merge(baseline_dict, partial.get("partial_config", {}))

    # Adjust for detected properties
    if "detected" in partial and "dims" in partial["detected"]:
        dims = partial["detected"]["dims"]

        # Adjust arrays for dimensionality
        if dims == 2 and "geometry" in config:
            for key in ["prob_lo", "prob_hi", "is_periodic"]:
                if key in config["geometry"]:
                    vals = config["geometry"][key].split()[:2]
                    config["geometry"][key] = " ".join(vals)

        if "amr" in config and "n_cell" in config["amr"]:
            n_vals = config["amr"]["n_cell"].split()
            if len(n_vals) > dims:
                config["amr"]["n_cell"] = " ".join(n_vals[:dims])

    # Add metadata
    config["_metadata"] = {
        "generated_by": "pele_tools",
        "timestamp": datetime.now().isoformat(),
        "user_intent": partial.get("user_intent", "unknown"),
        "baseline": baseline_example
    }

    return json.dumps(config, indent=2)


def _get_fallback_defaults(detected: dict) -> dict:
    """Fallback defaults if can't fetch examples."""
    dims = detected.get("dims", 3)

    return {
        "amr": {
            "n_cell": "128 128" if dims == 2 else "64 64 64",
            "max_level": "0",
            "max_grid_size": "32",
            "blocking_factor": "16"
        },
        "geometry": {
            "coord_sys": "0",
            "prob_lo": " ".join(["0.0"] * dims),
            "prob_hi": " ".join(["0.016"] * dims),
            "is_periodic": "1 1 0" if dims == 2 else "1 1 0"
        },
        "prob": {
            "P_mean": "101325",
            "T_mean": "300"
        },
        "pelec": {
            "v": "1",
            "do_hydro": "1",
            "do_react": "1",
            "cfl": "0.5"
        }
    }


def _deep_merge(base: dict, updates: dict) -> dict:
    """Deep merge two dicts, updates override base."""
    result = copy.deepcopy(base)
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# %% [markdown]
# ## Section 4: Validation (from Notebook 04)
#
# Multi-stage validation for configuration correctness.
#
# ### validate_config_schema

# %% jupyter={"source_hidden": true}
@tool
def validate_config_schema(config_json: str) -> str:
    """
    Validate configuration against expected schema.

    Parameters
    ----------
        config_json: Configuration as JSON string

    Returns
    -------
        str: Validation results as JSON {"errors": [...], "warnings": [...]}
    """
    config = json.loads(config_json)

    errors = []
    warnings = []

    # Required sections
    required_sections = ['geometry', 'amr', 'pelec']
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section: {section}")

    # Geometry validation
    if 'geometry' in config:
        geom = config['geometry']

        if 'prob_lo' not in geom or 'prob_hi' not in geom:
            errors.append("geometry must have prob_lo and prob_hi")
        else:
            lo = [float(x) for x in geom['prob_lo'].split()]
            hi = [float(x) for x in geom['prob_hi'].split()]

            if len(lo) != len(hi):
                errors.append(f"prob_lo and prob_hi dimensions mismatch: {len(lo)} vs {len(hi)}")

            if any(high <= low for high, low in zip(hi, lo, strict=False)):
                errors.append("prob_hi must be > prob_lo in all dimensions")

    # AMR validation
    if 'amr' in config:
        amr = config['amr']

        if 'n_cell' not in amr:
            errors.append("amr must specify n_cell")
        else:
            n_cell = [int(x) for x in amr['n_cell'].split()]
            if any(n < 4 for n in n_cell):
                warnings.append("Very coarse grid (< 4 cells per dimension)")

            # Check for very large grids
            total_cells = int(np.prod(n_cell))
            if total_cells > 1e9:
                warnings.append(f"Very large base grid: {total_cells:,} cells")

    return json.dumps({"errors": errors, "warnings": warnings}, indent=2)


# %% [markdown]
# ### validate_config_physics

# %% jupyter={"source_hidden": true}
@tool
def validate_config_physics(config_json: str) -> str:
    """
    Validate physical reasonableness of parameters.

    Parameters
    ----------
        config_json: Configuration as JSON string

    Returns
    -------
        str: Validation results as JSON
    """
    config = json.loads(config_json)

    errors = []
    warnings = []

    # Check prob section
    if 'prob' in config:
        prob = config['prob']

        # Pressure
        if 'P_mean' in prob:
            pressure = float(prob['P_mean'])
            if pressure < 1000:
                errors.append(f"Pressure {pressure} Pa too low (< 0.01 atm)")
            elif pressure > 1e8:
                errors.append(f"Pressure {pressure} Pa too high (> 1000 atm)")
            elif pressure < 10000 or pressure > 1e7:
                warnings.append(f"Pressure {pressure / 101325:.2f} atm is unusual")

        # Temperature
        if 'T_mean' in prob:
            temperature = float(prob['T_mean'])
            if temperature < 200:
                errors.append(f"Temperature {temperature} K below typical range")
            elif temperature > 3000:
                warnings.append(f"Temperature {temperature} K is very high")

        # Equivalence ratio
        if 'phi' in prob:
            phi = float(prob['phi'])
            if phi < 0.1 or phi > 10:
                errors.append(f"Equivalence ratio {phi} is unrealistic")
            elif phi < 0.5 or phi > 2.0:
                warnings.append(f"Equivalence ratio {phi} outside typical range (0.5-2.0)")

    # Check CFL
    if 'pelec' in config and 'cfl' in config['pelec']:
        cfl = float(config['pelec']['cfl'])
        if cfl >= 1.0:
            errors.append(f"CFL {cfl} >= 1.0 will be unstable")
        elif cfl > 0.8:
            warnings.append(f"CFL {cfl} is aggressive, consider < 0.7")

    # Check timestep
    if 'amr' in config:
        if 'max_step' in config['amr']:
            max_step = int(config['amr']['max_step'])
            if max_step < 10:
                warnings.append(f"max_step={max_step} is very small")

        if 'stop_time' in config['amr']:
            stop_time = float(config['amr']['stop_time'])
            if stop_time < 1e-9:
                warnings.append(f"stop_time={stop_time} is extremely small")

    return json.dumps({"errors": errors, "warnings": warnings}, indent=2)


# %% [markdown]
# ### validate_config_grid

# %% jupyter={"source_hidden": true}
@tool
def validate_config_grid(config_json: str) -> str:
    """
    Validate grid parameters for consistency.

    Parameters
    ----------
        config_json: Configuration as JSON string

    Returns
    -------
        str: Validation results as JSON
    """
    config = json.loads(config_json)

    errors = []
    warnings = []

    if 'amr' not in config:
        return json.dumps({"errors": ["Missing amr section"], "warnings": []}, indent=2)

    amr = config['amr']

    # Check divisibility
    blocking = int(amr.get('blocking_factor', '16'))
    max_grid = int(amr.get('max_grid_size', '32'))

    if max_grid % blocking != 0:
        errors.append(f"max_grid_size ({max_grid}) must be divisible by blocking_factor ({blocking})")

    if 'n_cell' in amr:
        n_cell = [int(x) for x in amr['n_cell'].split()]

        for i, n in enumerate(n_cell):
            if n % blocking != 0:
                errors.append(f"n_cell[{i}]={n} must be divisible by blocking_factor ({blocking})")

    # Check AMR
    max_level = int(amr.get('max_level', '0'))
    if max_level > 3 and 'n_cell' in amr:
        n_cell = [int(x) for x in amr['n_cell'].split()]
        base_cells = int(np.prod(n_cell))
        max_cells = base_cells * (8 ** max_level)  # 2^3 per level in 3D

        warnings.append(f"max_level={max_level} is high. Max cells: {max_cells:,}")

        if max_cells > 1e10:
            errors.append(f"Max cells ({max_cells:,}) exceeds reasonable limit")

    # Check ref_ratio
    if 'ref_ratio' in amr:
        ref_ratio = [int(x) for x in amr['ref_ratio'].split()]
        if any(r != 2 for r in ref_ratio):
            warnings.append(f"ref_ratio contains non-2 values: {ref_ratio}")

    return json.dumps({"errors": errors, "warnings": warnings}, indent=2)

# validate_executable_for_job
@tool
def validate_executable_for_job(
    executable_path: str,
    nodes: int = 1,
    ntasks_per_node: int = 1,
    constraint: str = ""
) -> dict[str, Any]:
    """
    Validate executable meets job requirements.

    Delegates to src.services.execution_tools.validate_executable_for_job.

    Parameters
    ----------
    executable_path : str
        Path to the executable.
    nodes : int, optional
        Number of nodes.
    ntasks_per_node : int, optional
        MPI tasks per node.
    constraint : str, optional
        Scheduler constraint string.

    Returns
    -------
    Dict[str, Any]
        Validation results.
    """
    from src.services.execution_tools import (
        validate_executable_for_job as _validate_executable_for_job,
    )

    return _validate_executable_for_job(
        executable_path=executable_path,
        nodes=nodes,
        ntasks_per_node=ntasks_per_node,
        constraint=constraint,
    )


# %% [markdown]
# ### validate_all

# %% jupyter={"source_hidden": true}
@tool
def validate_all(config_json: str) -> str:
    """
    Run all validation checks.

    Parameters
    ----------
        config_json: Configuration as JSON string

    Returns
    -------
        str: Combined validation results as JSON
    """
    all_errors = []
    all_warnings = []

    for validator in [validate_config_schema, validate_config_physics, validate_config_grid]:
        result_json = validator.invoke({"config_json": config_json})
        result = json.loads(result_json)
        all_errors.extend(result.get("errors", []))
        all_warnings.extend(result.get("warnings", []))

    return json.dumps({"errors": all_errors, "warnings": all_warnings}, indent=2)


# %% [markdown] jp-MarkdownHeadingCollapsed=true
# ## Section 5: Resource Estimation (from Notebook 04)
#
# Estimate computational resources needed for simulation.
#
# ### estimate_resources

# %% jupyter={"source_hidden": true}
@tool
def estimate_resources(config_json: str, system: str = "perlmutter") -> str:
    """
    Estimate computational resources needed.

    Delegates to src.services.execution_tools.estimate_resources.

    Parameters
    ----------
    config_json : str
        Configuration JSON string.
    system : str, optional
        Target system identifier.

    Returns
    -------
    str
        Resource estimate JSON string.
    """
    from src.services.execution_tools import estimate_resources as _estimate_resources

    return _estimate_resources(
        config_json=config_json,
        system=system,
    )

# %% [markdown] jp-MarkdownHeadingCollapsed=true
# ## Section 6: File Generation (from Notebook 04)
#
# Create all simulation files from validated configuration.
#
# ### write_simulation_files

# %%
@tool
def write_simulation_files(config_json: str,
                          output_dir: str,
                          executable_path: str | None = None,
                          selected_solver: str | None = None,
                          system: str = "perlmutter") -> str:
    """
    Write all simulation files to directory.

    Creates:
    - config.json (full configuration)
    - inputs (ParmParse file)
    - resources.json (resource estimates)
    - submit.sh (SLURM/batch script)

    Parameters
    ----------
        config_json: Validated configuration (JSON string)
        output_dir: Where to write files
        executable_path: Path to solver executable
        selected_solver: Solver name (e.g., PeleC, ERF, incflo)
        system: HPC system name for resource estimation

    Returns
    -------
        str: Paths to generated files as JSON

    Example:
        >>> files = write_simulation_files.invoke({
        ...     "config_json": config_json,
        ...     "output_dir": "./my_sim",
        ...     "executable_path": "$SCRATCH/PeleC/PeleC.ex",
        ...     "selected_solver": "PeleC"
        ... })
        >>> print(json.loads(files)['inputs'])
    """
    from src.services.file_generation import FileGenerationService

    generator = FileGenerationService()
    files = generator.write_simulation_files(
        config_json=config_json,
        output_dir=output_dir,
        selected_solver=selected_solver,
        executable_path=executable_path,
        system=system,
    )

    return json.dumps(files, indent=2)


def _generate_slurm_script(config, resources, executable_path):
    """Generate SLURM batch script."""
    # Detect system
    which_site, which_computer = _detect_hpc_system()

    nodes = resources["recommended_nodes"]
    hours = int(np.ceil(resources["estimated_walltime_hours"]))

    # System-specific settings
    if which_site == "nersc":
        partition = "regular"
        constraint = "cpu"
        cores_per_node = 128
        account = os.environ.get("SBATCH_ACCOUNT", "m1234")
        srun_cmd = f"srun -n {resources['total_cores']} -c 2 --cpu_bind=cores"
    elif which_site == "olcf":
        partition = "batch"
        constraint = ""
        cores_per_node = 64
        account = os.environ.get("SBATCH_ACCOUNT", "ABC123")
        srun_cmd = f"srun -n {resources['total_cores']} --gpus-per-task=1"
    elif which_site == "alcf":
        partition = "prod"
        constraint = ""
        cores_per_node = 64
        account = os.environ.get("SBATCH_ACCOUNT", "datascience")
        srun_cmd = f"mpiexec -n {resources['total_cores']} --ppn {cores_per_node}"
    else:
        partition = "regular"
        constraint = ""
        cores_per_node = 64
        account = "default"
        srun_cmd = f"mpirun -np {resources['total_cores']}"

    script = f"""#!/bin/bash
#SBATCH -A {account}
#SBATCH -J pelec_sim
#SBATCH -o %x-%j.out
#SBATCH -e %x-%j.err
#SBATCH -N {nodes}
#SBATCH -t {hours}:00:00
#SBATCH -q {partition}
"""

    if constraint:
        script += f"#SBATCH -C {constraint}\n"

    script += f"""
# ==============================================================================
# PeleC Simulation - Generated by Pele Assistant
# ==============================================================================
#
# Configuration:
#   Base grid: {resources['base_cells']:,} cells
#   Max cells (AMR): {resources['max_cells']:,} cells
#   Estimated memory: {resources['memory_gb']:.1f} GB
#   Cells per core: {resources['cells_per_core']:,}
#
# Generated: {datetime.now().isoformat()}
# ==============================================================================

echo "Job started: $(date)"
echo "Running on: $(hostname)"
echo "Working directory: $(pwd)"
echo ""

# Load modules (adjust for your system)
"""

    if which_site == "nersc":
        script += """module load PrgEnv-gnu
module load cmake
module load cray-hdf5
module load cray-netcdf
"""
    elif which_site == "olcf":
        script += """module load PrgEnv-gnu
module load cmake
module load hdf5
module load netcdf
"""
    else:
        script += """# Load your system-specific modules here
# module load gcc
# module load openmpi
# module load cmake
"""

    script += f"""
echo "Loaded modules:"
module list
echo ""

# Run simulation
echo "Starting PeleC..."
echo "Command: {srun_cmd} {executable_path} inputs"
echo ""

{srun_cmd} \\
    {executable_path} \\
    inputs

EXIT_CODE=$?

echo ""
echo "Simulation finished: $(date)"
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "SUCCESS"
else
    echo "FAILED - check error log"
fi

exit $EXIT_CODE
"""

    return script


def _generate_readme(config, resources):
    """Generate README for simulation directory."""
    metadata = config.get('_metadata', {})

    # Build README without nested triple backticks
    readme_parts = [
        "# PeleC Simulation\n",
        f"\n**Generated:** {metadata.get('timestamp', 'unknown')}  ",
        f"\n**Intent:** {metadata.get('user_intent', 'unknown')}  ",
        f"\n**Baseline:** {metadata.get('baseline', 'unknown')}\n",
        "\n## Configuration Summary\n",
        f"\n- **Dimensions:** {len(config.get('geometry', {}).get('prob_lo', '0 0 0').split())}D",
        f"\n- **Grid:** {config.get('amr', {}).get('n_cell', 'unknown')}",
        f"\n- **AMR Levels:** {config.get('amr', {}).get('max_level', '0')}",
        f"\n- **Domain:** {config.get('geometry', {}).get('prob_lo', '?')} → {config.get('geometry', {}).get('prob_hi', '?')}",
        f"\n- **Chemistry:** {'Enabled' if config.get('pelec', {}).get('do_react', '0') == '1' else 'Disabled'}",
        f"\n- **CFL:** {config.get('pelec', {}).get('cfl', '0.5')}\n",
        "\n## Resource Estimates\n",
        f"\n- **Base cells:** {resources['base_cells']:,}",
        f"\n- **Max cells (AMR):** {resources['max_cells']:,}",
        f"\n- **Memory:** {resources['memory_gb']:.1f} GB",
        f"\n- **Recommended nodes:** {resources['recommended_nodes']}",
        f"\n- **Total cores:** {resources['total_cores']}",
        f"\n- **Estimated walltime:** {resources['estimated_walltime_hours']:.1f} hours",
        f"\n- **Cost:** {resources['cost_node_hours']:.1f} node-hours\n",
        "\n## Files\n",
        "\n- `config.json` - Complete configuration in JSON format",
        "\n- `inputs` - ParmParse inputs file for PeleC",
        "\n- `resources.json` - Resource estimates and metadata",
        "\n- `submit.sh` - SLURM batch script (edit account/partition as needed)",
        "\n- `README.md` - This file\n",
        "\n## Running\n",
        "\n1. **Review configuration:**\n",
    ]

    # Add code blocks separately to avoid triple-backtick nesting
    readme_parts.append("   " + "```" + "bash\n")
    readme_parts.append("   cat inputs\n")
    readme_parts.append("   " + "```" + "\n\n")

    readme_parts.append("2. **Edit batch script if needed:**\n")
    readme_parts.append("   " + "```" + "bash\n")
    readme_parts.append("   vim submit.sh  # Update SBATCH account, partition, etc.\n")
    readme_parts.append("   " + "```" + "\n\n")

    readme_parts.append("3. **Submit job:**\n")
    readme_parts.append("   " + "```" + "bash\n")
    readme_parts.append("   sbatch submit.sh\n")
    readme_parts.append("   " + "```" + "\n\n")

    readme_parts.append("4. **Monitor:**\n")
    readme_parts.append("   " + "```" + "bash\n")
    readme_parts.append("   squeue -u $USER\n")
    readme_parts.append("   tail -f pelec_sim-<jobid>.out\n")
    readme_parts.append("   " + "```" + "\n\n")

    readme_parts.extend([
        "## Generated by Pele Assistant\n",
        "\nThis simulation was generated using the Pele Assistant tool.\n",
        "For questions or issues, consult the knowledge base or GitHub issues.\n"
    ])

    return "".join(readme_parts)


def _detect_hpc_system():
    """Detect HPC system (mirrors AMReX Make.machines)."""
    nersc_host = os.environ.get('NERSC_HOST')
    if nersc_host and nersc_host in ['perlmutter', 'alvarez', 'muller']:
        return "nersc", "perlmutter"

    if os.environ.get('LMOD_SITE_NAME') == 'OLCF':
        host_name = socket.getfqdn()
        if 'frontier' in host_name:
            return "olcf", "frontier"
        if 'crusher' in host_name:
            return "olcf", "crusher"

    if 'alcf.anl.gov' in socket.getfqdn() and 'polaris' in socket.getfqdn():
        return "alcf", "polaris"

    return "unknown", "unknown"


# %% [markdown] jp-MarkdownHeadingCollapsed=true
# ## Section 7: Convenience Functions
#
# High-level workflows for common tasks.
#
# ### build_simulation_config

# %%
def build_simulation_config(user_intent: str,
                           interactive: bool = False,
                           auto_validate: bool = True) -> dict:
    """
    High-level function: intent → validated config.

    Parameters
    ----------
        user_intent: Natural language description
        interactive: If True, prompt for answers. If False, use defaults.
        auto_validate: If True, validate before returning

    Returns
    -------
        dict: Complete, validated configuration

    Example:
        >>> config = build_simulation_config("2D methane flame with AMR")
        >>> print(config['amr']['max_level'])
    """
    # Start config
    initial = start_simulation_config.invoke({"user_intent": user_intent})
    config_json = json.dumps(initial)

    # Answer questions
    if interactive:
        # Interactive mode (for notebook/CLI use)
        config = json.loads(config_json)
        while config.get('questions'):
            question = config['questions'][0]
            answer = input(f"{question} ")
            config_json = add_config_answer.invoke({
                "config_json": config_json,
                "question": question,
                "answer": answer
            })
            config = json.loads(config_json)
    else:
        # Auto-answer with reasonable defaults
        config = json.loads(config_json)
        for q in list(config.get('questions', [])):
            if "level" in q.lower():
                a = "1"
            elif "ratio" in q.lower():
                a = "1.0"
            elif "refine" in q.lower():
                a = "gradT"
            elif "size" in q.lower():
                dims = config.get('detected', {}).get('dims', 2)
                a = "0.016 0.016" if dims == 2 else "0.016 0.016 0.016"
            else:
                a = "default"

            config_json = add_config_answer.invoke({
                "config_json": config_json,
                "question": q,
                "answer": a
            })

    # Finalize
    final_json = finalize_config.invoke({"partial_config_json": config_json})

    # Validate
    if auto_validate:
        validation_json = validate_all.invoke({"config_json": final_json})
        validation = json.loads(validation_json)

        if validation["errors"]:
            print("[WARN] Validation errors found:")
            for err in validation["errors"]:
                print(f"  - {err}")

        if validation["warnings"]:
            print("[INFO] Validation warnings:")
            for warn in validation["warnings"]:
                print(f"  - {warn}")

    return json.loads(final_json)


# %% [markdown]
# ### complete_workflow

# %%
def complete_workflow(user_intent: str,
                     output_dir: str,
                     executable_path: str = None,
                     interactive: bool = False) -> dict:
    """
    Complete workflow: intent → validated config → generated files.

    Parameters
    ----------
        user_intent: Natural language description
        output_dir: Where to create simulation directory
        executable_path: Path to PeleC executable (optional)
        interactive: Prompt for clarifications

    Returns
    -------
        dict: Paths to generated files and validation results

    Example:
        >>> result = complete_workflow(
        ...     "3D hydrogen flame with 2 AMR levels",
        ...     "./h2_flame",
        ...     executable_path="$SCRATCH/PeleC/PeleC3d.gnu.MPI.ex"
        ... )
        >>> print(result['files']['inputs'])
    """
    print("="*70)
    print("PELE ASSISTANT - Complete Simulation Setup")
    print("="*70)
    print(f"\nIntent: {user_intent}")
    print(f"Output: {output_dir}\n")

    # Step 1: Build config
    print("[1/4] Building configuration...")
    config = build_simulation_config(user_intent, interactive=interactive)
    print("[ OK ] Configuration complete")

    # Step 2: Validate
    print("\n[2/4] Validating...")
    config_json = json.dumps(config)
    validation = json.loads(validate_all.invoke({"config_json": config_json}))

    if validation["errors"]:
        print("[ERROR] Validation failed:")
        for err in validation["errors"]:
            print(f"  - {err}")
        return {"status": "failed", "errors": validation["errors"]}
    else:
        print("[ OK ] Validation passed")

    if validation["warnings"]:
        print("[WARN] Warnings:")
        for warn in validation["warnings"]:
            print(f"  - {warn}")

    # Step 3: Estimate resources
    print("\n[3/4] Estimating resources...")
    resources = json.loads(estimate_resources.invoke({"config_json": config_json}))
    print(f"[ OK ] Nodes: {resources['recommended_nodes']}, "
          f"Walltime: {resources['estimated_walltime_hours']}h, "
          f"Cost: {resources['cost_node_hours']} node-hours")

    # Step 4: Generate files
    print("\n[4/4] Generating files...")

    if executable_path is None:
        # Try to detect
        pelec_root = os.getenv('PELEC_ROOT')
        if pelec_root:
            executable_path = f"{pelec_root}/Exec/RegTests/PMF/PeleC3d.gnu.MPI.ex"
        else:
            executable_path = "/path/to/PeleC.ex"

    files = json.loads(write_simulation_files.invoke({
        "config_json": config_json,
        "output_dir": output_dir,
        "executable_path": executable_path
    }))

    print("[ OK ] Files generated:")
    for file_type, path in files.items():
        print(f"       {file_type}: {path}")

    print("\n" + "="*70)
    print("SETUP COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print(f"  1. cd {output_dir}")
    print("  2. Review inputs file")
    print("  3. Edit submit.sh (update account/partition)")
    print("  4. sbatch submit.sh")

    return {
        "status": "success",
        "config": config,
        "validation": validation,
        "resources": resources,
        "files": files
    }

# %% [markdown]
# ### Ask Knowledge Base
# Add to: notebooks/pele_tools.py

# %% [markdown]
# ## Execution & Workflow Tools
#
# Functions from tested workflows - signatures preserved for compatibility

# %% jupyter={"source_hidden": true}
@tool
def find_pelec_case_dir(inputs_path: str) -> str | None:
    """
    Find PeleC case directory from inputs file path.

    Looks for directory containing GNUmakefile.

    Parameters
    ----------
        inputs_path: Path to inputs file

    Returns
    -------
        Path to case directory or None

    Example:
        >>> case_dir = find_pelec_case_dir.invoke({
        ...     "inputs_path": "/path/to/PMF/inputs"
        ... })
    """
    from pathlib import Path

    inputs_path = Path(inputs_path)

    # Check inputs parent directory
    if (inputs_path.parent / 'GNUmakefile').exists():
        return str(inputs_path.parent)

    # Search up the tree
    current = inputs_path.parent
    for _ in range(5):  # Search up to 5 levels
        if (current / 'GNUmakefile').exists():
            return str(current)
        current = current.parent
        if current == current.parent:  # Reached root
            break

    # Standard PeleC structure search
    cwd = Path.cwd()
    for pelec_root in [cwd / '..', cwd / '../..']:
        for exec_dir in pelec_root.glob('PeleC*/Exec/RegTests/*'):
            if (exec_dir / 'GNUmakefile').exists():
                return str(exec_dir)

    return None


# %% jupyter={"source_hidden": true}
@tool
def find_pelec_executable(
    case_dir: str | None = None,
    executable_hint: str | None = None,
    require_mpi: bool | None = None,
    require_cuda: bool | None = None,
    config: dict | None = None
) -> str | None:
    """
    Find PeleC executable with broad search.

    Can filter by MPI/CUDA requirements.

    Parameters
    ----------
        case_dir: Directory with GNUmakefile (optional)
        executable_hint: Suggested path to check first (optional)
        require_mpi: Require MPI-enabled executable (optional, auto-detected from config)
        require_cuda: Require CUDA-enabled executable (optional, auto-detected from config)
        config: Configuration dict (optional, for agent use)

    Returns
    -------
        Path to executable or None
    """
    import os
    from pathlib import Path

    # Config-aware defaults
    if config:
        if case_dir is None and 'pelec_repo_path' in config:
            pelec_repo = config.get('pelec_repo_path')
            if pelec_repo:
                repo_path = Path(pelec_repo)
                if (repo_path / 'Exec').exists():
                    case_dir = str(repo_path / 'Exec')

        if executable_hint is None and 'pelec_executable' in config:
            exe = config.get('pelec_executable')
            if exe:
                executable_hint = str(exe)

        # Auto-detect MPI requirement from total ranks
        if require_mpi is None:
            nodes = config.get('nodes', 1)
            ntasks_per_node = config.get('ntasks_per_node', 4)  # Default: 4 GPUs/node
            total_ranks = nodes * ntasks_per_node

            if total_ranks > 1:
                require_mpi = True

        # Auto-detect CUDA requirement
        if require_cuda is None:
            constraint = config.get('constraint', '')
            if 'gpu' in constraint.lower():
                require_cuda = True

    search_paths = []

    # 1. User-provided hint
    if executable_hint:
        hint_path = Path(executable_hint)
        if hint_path.is_absolute():
            search_paths.append(hint_path.parent)
        else:
            search_paths.append(Path.cwd() / hint_path.parent)
        if hint_path.exists() and hint_path.is_file():
            name = hint_path.name
            if require_mpi and '.MPI.' not in name or require_cuda and '.CUDA.' not in name:
                pass  # Skip
            else:
                return str(hint_path.resolve())

    # 2-4: Search paths (same as before)
    if case_dir:
        search_paths.append(Path(case_dir))

    cwd = Path.cwd()
    search_paths.extend([
        cwd,
        cwd / '..' / 'PeleC' / 'Exec' / 'RegTests' / 'PMF',
        cwd / '../..' / 'PeleC' / 'Exec' / 'RegTests' / 'PMF',
    ])

    for parent in [cwd.parent, cwd.parent.parent]:
        for pelec_dir in parent.glob('PeleC*'):
            for test_case in pelec_dir.glob('Exec/RegTests/*'):
                search_paths.append(test_case)
            search_paths.append(pelec_dir / 'Exec')

    # Build patterns based on requirements
    exe_patterns = []

    if require_mpi and require_cuda:
        exe_patterns = ['PeleC*d.*.MPI.CUDA.ex']
    elif require_mpi:
        exe_patterns = ['PeleC*d.*.MPI.*.ex', 'PeleC*d.*.MPI.ex']
    elif require_cuda:
        exe_patterns = ['PeleC*d.*.CUDA.ex']
    else:
        exe_patterns = [
            'PeleC3d.gnu.MPI.CUDA.ex',
            'PeleC3d.gnu.MPI.ex',
            'PeleC2d.gnu.MPI.CUDA.ex',
            'PeleC2d.gnu.MPI.ex',
            'PeleC*.ex',
        ]

    # Search
    for search_path in search_paths:
        if not search_path.exists():
            continue

        for exe_pattern in exe_patterns:
            for exe in search_path.glob(exe_pattern):
                if exe.is_file() and os.access(exe, os.X_OK):
                    name = exe.name
                    if require_mpi and '.MPI.' not in name:
                        continue
                    if require_cuda and '.CUDA.' not in name:
                        continue

                    return str(exe.resolve())

    return None

# %% jupyter={"source_hidden": true}
@tool
def compile_pelec(
    case_dir: str,
    use_cuda: bool = True,
    jobs: int = 16,
    config: dict | None = None
) -> bool:
    """
    Compile PeleC in case directory.

    EXACTLY as in notebook, with optional config support.

    Parameters
    ----------
    case_dir : str
        Case directory to compile.
    use_cuda : bool, optional
        Whether to enable CUDA.
    jobs : int, optional
        Parallel build jobs.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    bool
        True on success, False on failure.
    """
    import subprocess
    from pathlib import Path

    case_dir = Path(case_dir)

    if not case_dir.exists():
        return False

    if not (case_dir / 'GNUmakefile').exists():
        return False

    # Build make flags
    make_flags = []
    if use_cuda:
        make_flags.append('USE_CUDA=TRUE')

    # PeleC uses MPI by default, but be explicit
    make_flags.append('USE_MPI=TRUE')

    commands = [
        ['make', 'TPLrealclean'] + make_flags,
        ['make', 'realclean'],
        ['make', 'TPL'] + make_flags,
        ['nice', 'make', f'-j{jobs}'] + make_flags
    ]

    try:
        for cmd in commands:
            result = subprocess.run(
                cmd, cwd=case_dir, capture_output=True,
                text=True, timeout=600
            )

            if result.returncode != 0:
                # Log compilation errors for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Compilation failed: {' '.join(cmd)}")
                logger.error(f"STDOUT: {result.stdout[-500:]}" if result.stdout else "No stdout")
                logger.error(f"STDERR: {result.stderr[-500:]}" if result.stderr else "No stderr")
                return False

        return True

    except (subprocess.TimeoutExpired, Exception) as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Compilation exception: {e}")
        return False


# %% jupyter={"source_hidden": true}
@tool
def compile_amrex(
    case_dir: str,
    use_cuda: bool = True,
    jobs: int = 16,
    config: dict | None = None
) -> bool:
    """
    Compile any AMReX code (PeleC, ERF, PeleLMeX, etc.) in case directory.

    Delegates to src.services.build_tools.compile_amrex.

    Parameters
    ----------
    case_dir : str
        Case directory to compile.
    use_cuda : bool, optional
        Whether to enable CUDA.
    jobs : int, optional
        Parallel build jobs.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    bool
        True on success, False on failure.
    """
    from src.services.build_tools import compile_amrex as _compile_amrex

    return _compile_amrex(
        case_dir=case_dir,
        use_cuda=use_cuda,
        jobs=jobs,
        config=config,
    )

# %% jupyter={"source_hidden": true}

# AMReX run-directory helpers are in amrex_tools.py

@tool
def generate_slurm_script(
    params: dict[str, Any],
    run_dir: str,
    config: dict | None = None
) -> str:
    """
    Generate SLURM batch script for GPU runs.

    Delegates to src.services.run_superfacility_tools.generate_slurm_script.

    Parameters
    ----------
    params : Dict[str, Any]
        SLURM parameter mapping.
    run_dir : str
        Run directory path.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    str
        Generated script content.
    """
    from src.services.run_superfacility_tools import (
        generate_slurm_script as _generate_slurm_script,
    )

    return _generate_slurm_script(
        params=params,
        run_dir=run_dir,
        config=config,
    )

# %% [markdown]
# ### NERSC Superfacility API Functions

# %% jupyter={"source_hidden": true}
@tool
def find_nersc_clients() -> dict[str, Any]:
    """
    Find NERSC OAuth client configs.

    Delegates to src.services.run_superfacility_tools.find_nersc_clients.

    Returns
    -------
    Dict[str, Any]
        Discovered client configuration.
    """
    from src.services.run_superfacility_tools import find_nersc_clients as _find_nersc_clients

    return _find_nersc_clients()


@tool
def create_nersc_session(
    clients: dict[str, Any],
    color: str = 'green',
    config: dict | None = None
) -> dict[str, Any] | None:
    """
    Create authenticated NERSC API session.

    Delegates to src.services.run_superfacility_tools.create_nersc_session.

    Parameters
    ----------
    clients : Dict[str, Any]
        Client configuration mapping.
    color : str, optional
        OAuth client color to use.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    Optional[Dict[str, Any]]
        Session information if available.
    """
    from src.services.run_superfacility_tools import create_nersc_session as _create_nersc_session

    return _create_nersc_session(
        clients=clients,
        color=color,
        config=config,
    )


@tool
def submit_via_sfapi(
    script_path: str,
    system: str = 'perlmutter',
    nersc_session: dict | None = None,
    config: dict | None = None
) -> dict[str, Any]:
    """
    Submit via Superfacility API.

    Delegates to src.services.run_superfacility_tools.submit_via_sfapi.

    Parameters
    ----------
    script_path : str
        Path to the submit script.
    system : str, optional
        Target system identifier.
    nersc_session : Optional[Dict], optional
        Authenticated session info.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    Dict[str, Any]
        Submission result.
    """
    from src.services.run_superfacility_tools import submit_via_sfapi as _submit_via_sfapi

    return _submit_via_sfapi(
        script_path=script_path,
        system=system,
        nersc_session=nersc_session,
        config=config,
    )


@tool
def submit_via_sbatch(
    script_path: str,
    config: dict | None = None
) -> dict[str, Any]:
    """
    Submit via local sbatch.

    Delegates to src.services.run_superfacility_tools.submit_via_sbatch.

    Parameters
    ----------
    script_path : str
        Path to the submit script.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    Dict[str, Any]
        Submission result.
    """
    from src.services.run_superfacility_tools import submit_via_sbatch as _submit_via_sbatch

    return _submit_via_sbatch(
        script_path=script_path,
        config=config,
    )


@tool
def submit_job(
    script_path: str,
    system: str = 'perlmutter',
    nersc_session: dict | None = None,
    config: dict | None = None
) -> tuple[str, str]:
    """
    Submit job (API with sbatch fallback).

    Delegates to src.services.run_superfacility_tools.submit_job.

    Parameters
    ----------
    script_path : str
        Path to the submit script.
    system : str, optional
        Target system identifier.
    nersc_session : Optional[Dict], optional
        Authenticated session info.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    Tuple[str, str]
        Job ID and submission method.
    """
    from src.services.run_superfacility_tools import submit_job as _submit_job

    return _submit_job(
        script_path=script_path,
        system=system,
        nersc_session=nersc_session,
        config=config,
    )


@tool
def monitor_job(
    job_id: str,
    method: str = 'sbatch',
    poll_interval: int = 10,
    max_polls: int = 30,
    nersc_session: dict | None = None,
    config: dict | None = None
) -> str:
    """
    Monitor job status.

    Delegates to src.services.run_superfacility_tools.monitor_job.

    Parameters
    ----------
    job_id : str
        Job identifier.
    method : str, optional
        Submission method.
    poll_interval : int, optional
        Poll interval in seconds.
    max_polls : int, optional
        Maximum number of polls.
    nersc_session : Optional[Dict], optional
        Authenticated session info.
    config : Optional[Dict], optional
        Optional config overrides.

    Returns
    -------
    str
        Final job state.
    """
    from src.services.run_superfacility_tools import monitor_job as _monitor_job

    return _monitor_job(
        job_id=job_id,
        method=method,
        poll_interval=poll_interval,
        max_polls=max_polls,
        nersc_session=nersc_session,
        config=config,
    )

# %% [markdown]
# ### Performance Analysis Tools

# %% jupyter={"source_hidden": true}
@tool
def parse_pmf_performance(outfile: str) -> dict[str, Any]:
    """
    Parse performance metrics from PeleC output.

    EXACTLY as in notebook - extracts timing, throughput, chemistry fraction.

    Parameters
    ----------
        outfile: Path to run.out or stdout file

    Returns
    -------
        Dict with keys:
            - total_time: float (seconds)
            - react_time: float (seconds, chemistry time)
            - react_fraction: float (0-1, chemistry fraction)
            - steps: int (timesteps completed)
            - throughput: float (M cell-updates/s)

    Example:
        >>> metrics = parse_pmf_performance.invoke({
        ...     "outfile": "run.out"
        ... })
        >>> print(f"Throughput: {metrics['throughput']:.2f} M cells/s")
    """
    import re
    from pathlib import Path

    content = Path(outfile).read_text()
    metrics = {}

    # Parse total time
    time_match = re.search(r'Run time\s*=\s*([\d.]+)', content)
    if time_match:
        metrics['total_time'] = float(time_match.group(1))

    # Parse chemistry time
    react_match = re.search(r'React::react\(\)\s*:\s*([\d.]+)', content)
    if react_match:
        metrics['react_time'] = float(react_match.group(1))
        if metrics.get('total_time'):
            metrics['react_fraction'] = metrics['react_time'] / metrics['total_time']

    # Parse timesteps
    step_match = re.search(r'STEP = (\d+)', content)
    if step_match:
        metrics['steps'] = int(step_match.group(1))

    # Additional patterns for AMReX output
    # Sometimes it's "Coarse TimeStep time:"
    coarse_match = re.search(r'Coarse TimeStep time:\s*([\d.]+)', content)
    if coarse_match and not metrics.get('total_time'):
        metrics['total_time'] = float(coarse_match.group(1))

    # Grid information (if available)
    ncell_match = re.search(r'Number of cells at level 0\s*:\s*(\d+)', content)
    if ncell_match:
        metrics['base_cells'] = int(ncell_match.group(1))

    # Calculate throughput if we have cells and time
    if metrics.get('base_cells') and metrics.get('steps') and metrics.get('total_time'):
        cell_updates = metrics['base_cells'] * metrics['steps']
        metrics['throughput'] = cell_updates / metrics['total_time'] / 1e6  # M cells/s

    return metrics


# %% jupyter={"source_hidden": true}
@tool
def parse_pelec_datlog(datlog_path: str) -> dict[str, Any]:
    """
    Parse PeleC datlog file for time history.

    Extracts time series data from AMReX datlog output.

    Parameters
    ----------
        datlog_path: Path to datlog file (e.g., 'datlog')

    Returns
    -------
        Dict with keys:
            - time: List[float] - simulation times
            - dt: List[float] - timesteps
            - cells: List[int] - total cells per step
            - max_level: List[int] - max AMR level per step

    Example:
        >>> data = parse_pelec_datlog.invoke({
        ...     "datlog_path": "datlog"
        ... })
        >>> import matplotlib.pyplot as plt
        >>> plt.plot(data['time'], data['dt'])
    """
    from pathlib import Path

    datlog = Path(datlog_path)
    if not datlog.exists():
        return {"error": f"File not found: {datlog_path}"}

    data = {
        'time': [],
        'dt': [],
        'cells': [],
        'max_level': []
    }

    with open(datlog) as f:
        for line in f:
            # Skip comments
            if line.startswith('#'):
                continue

            # Parse data lines
            # Typical format: STEP TIME DT NCELLS MAX_LEV ...
            parts = line.split()
            if len(parts) < 4:
                continue

            try:
                # Skip step number (column 0)
                time = float(parts[1])
                dt = float(parts[2])
                cells = int(parts[3])

                data['time'].append(time)
                data['dt'].append(dt)
                data['cells'].append(cells)

                if len(parts) > 4:
                    max_lev = int(parts[4])
                    data['max_level'].append(max_lev)

            except (ValueError, IndexError):
                continue

    return data


# %% [markdown]
# ### Visualization Helpers (yt integration)

# %% jupyter={"source_hidden": true}
# AMReX plotfile helpers are in amrex_tools.py

# Add to end of: notebooks/pele_tools.py

# %% [markdown]
# ## Testing All Workflow Functions

# %% [markdown]
# ## Exports & Module Interface

# %% jupyter={"source_hidden": true}
__all__ = [
    # Core I/O
    'parse_pele_inputs',
    'dict_to_pele_inputs',
    'fetch_pele_example',
    'validate_pele_inputs',

    # Knowledge base - querying
    'load_pele_knowledge',
    'ask_pele_question',

    # Knowledge base - expansion
    'add_custom_knowledge',
    'ingest_pele_readmes',
    'extract_example_parameters',
    'ingest_sphinx_docs',
    'ingest_warpx_hpc_docs',
    'ingest_weakscaling_patterns',
    'ingest_amrex_perf_scripts',
    'document_current_modules',
    'ingest_nersc_docs',
    'search_nersc_docs',
    'create_comprehensive_build_guide',

    # GitHub tools
    'fetch_github_docs',
    'search_github_issues',

    # Config building
    'start_simulation_config',
    'add_config_answer',
    'finalize_config',
    'build_simulation_config',

    # Validation
    'validate_config_schema',
    'validate_config_physics',
    'validate_config_grid',
    'validate_executable_for_job',
    'validate_all',

    # Resources
    'estimate_resources',

    # File generation
    'write_simulation_files',

    # High-level workflows
    'complete_workflow',

    # === NEW: Execution & Workflow Tools ===
    'find_pelec_case_dir',
    'find_pelec_executable',
    'compile_pelec',
    'compile_amrex',  # Generic AMReX compilation (works for all codes)
    'setup_run_directory',
    'find_inputs_file',
    'copy_to_rundir',
    'generate_slurm_script',

    # NERSC Superfacility API
    'find_nersc_clients',
    'create_nersc_session',
    'submit_via_sfapi',
    'submit_via_sbatch',
    'submit_job',
    'monitor_job',

    # Performance & Analysis
    'parse_pmf_performance',
    'parse_pelec_datlog',
    'find_latest_plotfile',
    'extract_plotfile_metadata',
    'create_yt_sliceplot',
    'create_1d_profile',
]

# %% [markdown]
# ## Usage Examples
#
# ### Quick Start - Parse Inputs

# %% tags=["example"]
# Example 1: Parse existing inputs
if __name__ == "__main__":
    # Parse inputs file
    inputs = parse_pele_inputs("my_simulation/inputs")
    print(f"Grid: {inputs['amr']['n_cell']}")
    print(f"Max level: {inputs['amr']['max_level']}")

# %% [markdown]
# ### Build Config from Intent

# %% jupyter={"source_hidden": true} tags=["example"]
# Example 2: Build config from natural language
if __name__ == "__main__":
    config = build_simulation_config(
        "2D methane flame with 1 level of AMR",
        interactive=False
    )

    # Validate
    validation = json.loads(validate_all.invoke({"config_json": json.dumps(config)}))
    print(f"Errors: {len(validation['errors'])}")

    # Generate files
    files = json.loads(write_simulation_files.invoke({
        "config_json": json.dumps(config),
        "output_dir": "./my_simulation"
    }))
    print(f"Generated: {list(files.keys())}")

# %% [markdown]
# ### Complete Workflow

# %% jupyter={"source_hidden": true} tags=["example"]
# Example 3: Complete end-to-end workflow
if __name__ == "__main__":
    result = complete_workflow(
        user_intent="3D hydrogen detonation with detailed chemistry and 2 AMR levels",
        output_dir="./h2_detonation",
        executable_path="$SCRATCH/PeleC/PeleC3d.gnu.MPI.ex",
        interactive=False
    )

    if result['status'] == 'success':
        print("Ready to run!")
        print(f"Submit: cd {result['files']['submit_script'].rsplit('/', 1)[0]} && sbatch submit.sh")

# %% [markdown]
# ### Expand Knowledge Base

# %% jupyter={"source_hidden": true} tags=["example"]
# Example 4: Expand knowledge base
if __name__ == "__main__":
    # Add custom notes
    add_custom_knowledge.invoke({
        "content": "On Perlmutter CPU: Use PrgEnv-gnu, cray-hdf5, cmake/3.24",
        "title": "Perlmutter Build Notes"
    })

    # Ingest PeleC examples
    extract_example_parameters.invoke({
        "repo_path": "/path/to/PeleC"
    })

    # Fetch WarpX HPC patterns
    ingest_warpx_hpc_docs.invoke({})

    # Now ask questions
    answer = ask_pele_question.invoke({
        "question": "How do I build on Perlmutter?"
    })
    print(answer)

# %%
if __name__ == "__main__":
    print("=== Testing Workflow Functions ===\n")

    # Test 1: Find executable
    print("[1] find_pelec_executable:")
    exe = find_pelec_executable.invoke({
        "executable_hint": "../PeleC/Exec/RegTests/PMF/PeleC3d.gnu.MPI.CUDA.ex"
    })
    print(f"    Found: {exe}\n")

    # Test 2: Setup run directory
    print("[2] setup_run_directory:")
    run_dir = setup_run_directory.invoke({"base_name": "test"})
    print(f"    Created: {run_dir}\n")

    # Test 3: Generate SLURM script
    print("[3] generate_slurm_script:")
    params = {
        'nodes': 2,
        'walltime': '00:10:00',
        'account': 'amsc014',
        'qos': 'debug',
        'constraint': 'gpu&hbm40g',
        'executable': 'PeleC3d.gnu.MPI.CUDA.ex'
    }
    script = generate_slurm_script.invoke({
        'params': params,
        'run_dir': run_dir
    })
    print(f"    Generated script ({len(script)} chars)\n")

    # Test 4: Find NERSC clients
    print("[4] find_nersc_clients:")
    clients = find_nersc_clients.invoke({})
    print(f"    Found clients: {list(clients.keys())}\n")

    # Test 5: Parse performance (if file exists)
    print("[5] parse_pmf_performance:")
    test_outfile = "run.out"
    from pathlib import Path
    if Path(test_outfile).exists():
        perf = parse_pmf_performance.invoke({"outfile": test_outfile})
        print(f"    Metrics: {list(perf.keys())}\n")
    else:
        print(f"    Skipped (no {test_outfile})\n")

    # Test 6: Find latest plotfile
    print("[6] find_latest_plotfile:")
    plt_path = find_latest_plotfile.invoke({})
    if plt_path:
        print(f"    Found: {plt_path}\n")
    else:
        print("    None found (no plt* dirs)\n")

    print("✅ All tests passed!")
