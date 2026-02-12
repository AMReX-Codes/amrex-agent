# utils/pele_assistant.py - Tool-first design

import os
from pathlib import Path
from typing import Any

from langchain.tools import tool

# Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.

# ============================================================================
# CONFIGURATION
# ============================================================================

REPORTS_DIR = os.getenv("PELE_REPORTS_DIR", "/global/cfs/cdirs/amsc014/superfacility/amrex-agent/database/reports")
PELEC_ROOT = os.getenv("PELEC_ROOT", "/global/cfs/cdirs/amsc014/superfacility/PeleC")

# ============================================================================
# PHASE 1: KNOWLEDGE BASE (as tools from start)
# ============================================================================

@tool
def load_pele_knowledge() -> str:
    """
    Load all Pele simulation reports into the knowledge base.

    Returns
    -------
    str
        Concatenated report text.
    """
    knowledge = []
    # Get ALL report files, not just 1-6
    for report_path in sorted(Path(REPORTS_DIR).glob("report*.txt")):
        with open(report_path) as f:
            report_num = report_path.stem.replace('report', '')
            knowledge.append(f"=== REPORT {report_num} ===\n{f.read()}\n")

    return "\n".join(knowledge)


@tool
def ask_pele_question(question: str, use_full_knowledge: str = "true") -> str:
    """
    Ask a question about Pele simulations using the knowledge base.

    Parameters
    ----------
    question : str
        Question about Pele setup, parameters, or results.
    use_full_knowledge : str, optional
        Whether to use all reports ("true"/"false").

    Returns
    -------
    str
        Structured answer with confidence, sources, and evidence.
    """
    import os
    import time

    from openai import OpenAI

    start_time = time.time()

    # Load knowledge
    knowledge = load_pele_knowledge.invoke({})
    print(f"[INFO] Loaded knowledge in {time.time()-start_time:.2f}s ({len(knowledge):,} chars)")

    client = OpenAI(
        api_key=os.getenv("CBORG_API_KEY"),
        base_url="https://api.cborg.lbl.gov/v1"
    )

    model = os.getenv("CBORG_MODEL", "lbl/llama")

    # If knowledge too large, use multi-pass
    if len(knowledge) > 400000:
        print("[INFO] Using multi-pass query (baseline + new reports)...")
        return query_multi_pass(client, model, question, knowledge)
    else:
        return query_with_knowledge(client, model, question, knowledge)


def query_with_knowledge(client, model, question, knowledge):
    """
    Run a single query with the provided knowledge context.

    Parameters
    ----------
    client : Any
        OpenAI client.
    model : str
        Model name.
    question : str
        User question.
    knowledge : str
        Knowledge base text.

    Returns
    -------
    str
        Model response content.
    """
    system_prompt = """You are a Pele combustion simulation expert. Answer questions using ONLY information from the provided knowledge base.

IMPORTANT: Use this exact format for ALL answers:

**Confidence: [0-100]%**

**Answer:**
[Your answer here. Be specific.]

**Sources:**
- [List which reports contain this information]

**Evidence:**
```
[Include exact snippets/quotes when available]
```

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


def query_multi_pass(client, model, question, full_knowledge):
    """
    Run a two-pass query over baseline and new reports.

    Parameters
    ----------
    client : Any
        OpenAI client.
    model : str
        Model name.
    question : str
        User question.
    full_knowledge : str
        Full knowledge base text.

    Returns
    -------
    str
        Combined response content.
    """
    # Split knowledge by report
    all_reports = {}
    for report in full_knowledge.split("=== REPORT "):
        if not report.strip():
            continue
        parts = report.split(" ===", 1)
        if len(parts) < 2:
            continue
        report_num = parts[0].strip()
        all_reports[report_num] = f"=== REPORT {report}"

    # Baseline: reports 1-6
    baseline_reports = [all_reports.get(str(i), "") for i in range(1, 7)]
    baseline_knowledge = "\n\n".join(r for r in baseline_reports if r)

    # New reports: 7+
    new_report_nums = sorted([num for num in all_reports if int(num) > 6], key=int)
    new_reports_knowledge = "\n\n".join([all_reports[num] for num in new_report_nums])

    print(f"[INFO] Pass 1: Reports 1-6 ({len(baseline_knowledge):,} chars)")
    print(f"[INFO] Pass 2: Reports {', '.join(new_report_nums)} ({len(new_reports_knowledge):,} chars)")

    answers = []

    # Pass 1: Baseline reports
    try:
        print("  Querying baseline reports...", end=" ")
        baseline_answer = query_with_knowledge(client, model, question, baseline_knowledge)

        # Extract confidence
        baseline_conf = extract_confidence(baseline_answer)
        print(f"confidence: {baseline_conf}%")

        answers.append({
            'source': 'Reports 1-6 (guides)',
            'answer': baseline_answer,
            'confidence': baseline_conf
        })
    except Exception as e:
        print(f"error: {e}")

    # Pass 2: New reports (examples/specifics)
    try:
        print("  Querying new reports...", end=" ")
        new_answer = query_with_knowledge(client, model, question, new_reports_knowledge)

        new_conf = extract_confidence(new_answer)
        print(f"confidence: {new_conf}%")

        answers.append({
            'source': f'Reports {", ".join(new_report_nums)} (examples)',
            'answer': new_answer,
            'confidence': new_conf
        })
    except Exception as e:
        print(f"error: {e}")

    # Combine answers
    if not answers:
        return "**Confidence: 0%**\n\n**Answer:**\nError querying knowledge base."

    # Sort by confidence
    answers.sort(key=lambda x: x['confidence'], reverse=True)
    best = answers[0]

    # If both have good confidence, merge them
    if len(answers) == 2 and answers[1]['confidence'] >= 50:
        return merge_answers(answers[0], answers[1])

    # Otherwise return best answer
    return best['answer']


def extract_confidence(answer):
    """
    Extract confidence percentage from an answer string.

    Parameters
    ----------
    answer : str
        Answer text containing a confidence line.

    Returns
    -------
    int
        Parsed confidence percentage.
    """
    if "**Confidence:" in answer:
        try:
            conf_line = [line for line in answer.split('\n') if '**Confidence:' in line][0]
            return int(conf_line.split(':')[1].strip().replace('%**', '').replace('%', ''))
        except Exception:
            pass
    return 0


def merge_answers(baseline_ans, new_ans):
    """
    Merge insights from baseline and new reports.

    Parameters
    ----------
    baseline_ans : Dict[str, Any]
        Baseline answer bundle.
    new_ans : Dict[str, Any]
        New answer bundle.

    Returns
    -------
    str
        Merged answer text.
    """
    # Use higher confidence as primary
    primary = baseline_ans if baseline_ans['confidence'] >= new_ans['confidence'] else new_ans
    secondary = new_ans if primary == baseline_ans else baseline_ans

    # Extract answer sections
    primary_answer = primary['answer']

    # Add secondary insights if they add new info
    merged = primary_answer

    # Add note about secondary source
    if "**Caveats:**" in merged:
        merged = merged.replace(
            "**Caveats:**",
            f"**Caveats:**\n- Combined insights from {primary['source']} (primary) and {secondary['source']}\n-"
        )
    else:
        merged += f"\n\n**Note:** Also checked {secondary['source']} (confidence: {secondary['confidence']}%)"

    return merged

# ============================================================================
# PHASE 2: INPUTS MANAGEMENT (as tools)
# ============================================================================

@tool
def read_pele_inputs(filepath: str) -> dict[str, Any]:
    """
    Read a Pele inputs file into a dictionary.

    Parameters
    ----------
    filepath : str
        Path to inputs file.

    Returns
    -------
    Dict[str, Any]
        Parsed inputs mapping.
    """
    from pypele import PeleInputs
    return PeleInputs.read(filepath)


@tool
def write_pele_inputs(config: dict[str, Any], filepath: str) -> str:
    """
    Write a dictionary to a Pele inputs file.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration mapping.
    filepath : str
        Output file path.

    Returns
    -------
    str
        Status message.
    """
    from pypele import PeleInputs
    PeleInputs.write(config, filepath)
    return f"Wrote inputs to {filepath}"


@tool
def json_to_pele_inputs(json_config: str, output_file: str = "inputs") -> str:
    """
    Convert JSON configuration to Pele inputs file.

    Parameters
    ----------
    json_config : str
        JSON string with simulation config.
    output_file : str, optional
        Output filename.

    Returns
    -------
    str
        Status message.
    """
    import json

    from pypele import json_to_inputs

    config = json.loads(json_config)
    json_to_inputs(config, output_file)
    return f"Created {output_file} from JSON config"


# ============================================================================
# PHASE 3: GITHUB DOCS (as tools)
# ============================================================================

@tool
def get_pele_boundary_conditions(code: str = "PeleC") -> dict[str, str]:
    """
    Get current boundary condition types from Pele documentation.

    Parameters
    ----------
    code : str, optional
        Which Pele code to query.

    Returns
    -------
    Dict[str, str]
        Boundary condition types.
    """
    from github_docs import get_boundary_condition_types
    return get_boundary_condition_types(code)


@tool
def get_pele_example(problem_type: str, code: str = "PeleC") -> str:
    """
    Fetch an example inputs file from Pele repository.

    Parameters
    ----------
    problem_type : str
        Problem name (e.g., "Sedov", "TG").
    code : str, optional
        Which Pele code to query.

    Returns
    -------
    str
        Example inputs content.
    """
    from github_docs import get_example_inputs
    return get_example_inputs(problem_type, code)


@tool
def search_pele_code(search_term: str, code: str = "PeleC") -> list[dict]:
    """
    Search Pele source code for usage examples.

    Parameters
    ----------
    search_term : str
        Search term (e.g., "cfl", "amr").
    code : str, optional
        Which Pele code to query.

    Returns
    -------
    List[Dict]
        Matching code usage entries.
    """
    from github_docs import find_code_usage
    return find_code_usage(search_term, code)


# ============================================================================
# PHASE 4: GITHUB ISSUES (as tools)
# ============================================================================

@tool
def search_pele_issues(query: str, repo: str = "PeleC", max_results: int = 5) -> list[dict]:
    """
    Search GitHub issues for Pele problems/solutions.

    Parameters
    ----------
    query : str
        Search terms.
    repo : str, optional
        Repository name.
    max_results : int, optional
        Maximum number of results.

    Returns
    -------
    List[Dict]
        Issue results.
    """
    from github_issues import search_github_issues
    return search_github_issues(query, repo, max_results=max_results)


@tool
def find_related_pele_issues(problem_description: str, repo: str = "PeleC") -> list[dict]:
    """
    Find GitHub issues related to your problem (LLM-ranked).

    Parameters
    ----------
    problem_description : str
        Description of the issue.
    repo : str, optional
        Repository name.

    Returns
    -------
    List[Dict]
        Related issue results.
    """
    from github_issues import find_related_issues
    return find_related_issues(problem_description, repo)


@tool
def summarize_pele_issue(issue_number: int, repo: str = "PeleC") -> dict:
    """
    Get a summary of a GitHub issue thread.

    Parameters
    ----------
    issue_number : int
        Issue number.
    repo : str, optional
        Repository name.

    Returns
    -------
    Dict
        Summary details.
    """
    from github_issues import summarize_issue_thread
    return summarize_issue_thread(issue_number, repo)
