"""
Database building utilities for FAISS index creation.

Provides foam-agent proven patterns:
- Tokenization: Normalize case names for embedding matching
- Document formatting: XML-like structure for LLM parsing
- Metadata extraction helpers

These utilities are code-agnostic and work with any AMReX code via config classes.

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def tokenize(text: str) -> str:
    """
    Normalize text for embedding matching.

    Implements foam-agent's proven tokenization pattern:
    - Replace underscores with spaces: Taylor_Green → taylor green
    - Split camelCase: FlameSheet → flame sheet, PMF → pmf
    - Lowercase everything

    Critical for matching combustion case names!

    Parameters
    ----------
    text : str
        Input text to normalize.

    Returns
    -------
    str
        Normalized text.

    Examples
    --------
        >>> tokenize("Taylor_Green")
        'taylor green'
        >>> tokenize("PMF")
        'pmf'
        >>> tokenize("FlameSheet")
        'flame sheet'
        >>> tokenize("CounterFlow_CH4")
        'counter flow ch4'
    """
    if not text:
        return ""

    # Replace underscores with spaces
    text = text.replace('_', ' ')

    # Split camelCase: insert space before capital letters
    # FlameSheet → Flame Sheet
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # Lowercase
    text = text.lower()

    # Normalize whitespace
    text = ' '.join(text.split())

    return text


def format_case_document(metadata: dict[str, Any], details: dict[str, str] | None = None) -> str:
    """
    Format case information with XML-like structure for LLM parsing.

    Implements foam-agent's document structure pattern:
    <case_begin>
    <index>key: value pairs</index>
    <structure>...</structure>
    <parameters>...</parameters>
    </case_begin>

    Makes parsing and LLM consumption easier.

    Parameters
    ----------
    metadata : Dict[str, Any]
        Case metadata dict (from code config's extract_metadata).
    details : Optional[Dict[str, str]], optional
        Optional detail sections (structure, parameters, execution).

    Returns
    -------
    str
        Formatted document string.

    Example:
        >>> metadata = {
        ...     'code': 'PeleC',
        ...     'case_name': 'PMF',
        ...     'mechanism': 'drm19',
        ...     'fuel': 'methane'
        ... }
        >>> doc = format_case_document(metadata)
        >>> print(doc)
        <case_begin>
        <index>
        code: PeleC
        case: PMF
        mechanism: drm19
        fuel: methane
        </index>
        ...
        </case_begin>
    """
    details = details or {}

    # Build index section from metadata
    index_lines = []
    for key, value in metadata.items():
        if value is not None and key not in ['case_path']:  # Skip path in index
            # Format key: replace underscores, make readable
            display_key = key.replace('_', ' ')
            index_lines.append(f"{display_key}: {value}")

    index_content = '\n'.join(index_lines)

    # Build document
    doc_parts = [
        "<case_begin>",
        "<index>",
        index_content,
        "</index>",
    ]

    # Add structure section if available
    if 'structure' in details:
        doc_parts.extend([
            "<structure>",
            details['structure'],
            "</structure>",
        ])

    # Add parameters section if available
    if 'parameters' in details:
        doc_parts.extend([
            "<parameters>",
            details['parameters'],
            "</parameters>",
        ])

    # Add execution section if available
    if 'execution' in details:
        doc_parts.extend([
            "<execution>",
            details['execution'],
            "</execution>",
        ])

    doc_parts.append("</case_begin>")

    return '\n'.join(doc_parts)


def extract_directory_structure(case_path: Path, max_depth: int = 3) -> str:
    """
    Extract directory structure as a tree.

    Parameters
    ----------
    case_path : Path
        Path to case directory.
    max_depth : int, optional
        Maximum depth to traverse.

    Returns
    -------
    str
        Tree-formatted directory structure string.
    """
    def build_tree(path: Path, prefix: str = "", depth: int = 0) -> list[str]:
        """
        Build tree lines for a directory subtree.

        Parameters
        ----------
        path : Path
            Directory path to traverse.
        prefix : str, optional
            Prefix for tree formatting.
        depth : int, optional
            Current recursion depth.

        Returns
        -------
        List[str]
            Tree lines for the subtree.
        """
        if depth >= max_depth:
            return []

        lines = []
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                lines.append(f"{prefix}{current_prefix}{item.name}")

                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(item, prefix + extension, depth + 1))

        except PermissionError:
            pass

        return lines

    tree_lines = [case_path.name + "/"]
    tree_lines.extend(build_tree(case_path))

    return '\n'.join(tree_lines)


def extract_input_file_content(case_path: Path, max_lines: int = 100) -> str | None:
    """
    Extract content from inputs file.

    Parameters
    ----------
    case_path : Path
        Path to case directory.
    max_lines : int, optional
        Maximum lines to extract.

    Returns
    -------
    Optional[str]
        Inputs file content, or ``None`` if not found.
    """
    # Find inputs file
    for pattern in ['inputs*', '*.inp']:
        files = list(case_path.glob(pattern))
        if files:
            inputs_file = files[0]

            try:
                with open(inputs_file) as f:
                    lines = f.readlines()[:max_lines]
                return ''.join(lines)

            except Exception as e:
                logger.debug(f"Warning: Could not read {inputs_file}: {e}")
                return None

    return None


def extract_readme_content(case_path: Path) -> str | None:
    """
    Extract README content from case directory.

    Parameters
    ----------
    case_path : Path
        Path to case directory.

    Returns
    -------
    Optional[str]
        README content, or ``None`` if not found.
    """
    for readme_name in ['README.md', 'README', 'README.txt', 'readme.md']:
        readme_path = case_path / readme_name
        if readme_path.exists():
            try:
                with open(readme_path) as f:
                    return f.read()
            except Exception as e:
                logger.debug(f"Warning: Could not read {readme_path}: {e}")

    return None


def find_case_directories(source_dir: Path, case_patterns: list[str] | None = None) -> tuple[list[str], list[Path]]:
    """
    Find case directories using config-driven scanner.

    Uses the configuration class's scan_for_cases() method (Cases Service: Config-Driven Scanner).
    This eliminates hardcoded patterns and if/elif logic.

    Parameters
    ----------
    source_dir : Path
        Root directory to search (e.g., PeleC/).
    case_patterns : Optional[List[str]], optional
        Deprecated (ignored, kept for backward compatibility).

    Returns
    -------
    tuple[List[str], List[Path]]
        Relative paths and absolute paths.
    """
    from database.configs import discover_code_configs

    # 1. Find the config for this code
    code_name = source_dir.name
    config_class = None

    for cfg in discover_code_configs():
        if cfg.code_name == code_name:
            config_class = cfg
            break

    # 2. Use config's scanner (polymorphic behavior)
    if config_class:
        case_dirs = config_class.scan_for_cases(source_dir)
    else:
        # Fallback: Use base config's scanner
        from database.configs import BaseAMReXConfig
        logger.debug(f"Warning: No config for '{code_name}', using generic scanner")
        case_dirs = BaseAMReXConfig.scan_for_cases(source_dir)

    # 3. Format results
    sorted_case_dirs = sorted(case_dirs)

    try:
        relative_paths = [str(p.relative_to(source_dir)) for p in sorted_case_dirs]
    except ValueError:
        relative_paths = [p.name for p in sorted_case_dirs]

    return relative_paths, sorted_case_dirs



def combine_hierarchical_scores(
    structure_results: dict[str, Any],
    detail_results: dict[str, Any],
    case_path: str
) -> float:
    """
    Combine scores from hierarchical retrieval.

    Implements foam-agent's hierarchical scoring:
    - Level 1 (structure): 40% weight
    - Level 2 (details): 60% weight

    Parameters
    ----------
    structure_results : Dict[str, Any]
        Results from structure index.
    detail_results : Dict[str, Any]
        Results from details index.
    case_path : str
        Path to score.

    Returns
    -------
    float
        Combined score (lower is better for FAISS distance).
    """
    structure_score = None
    detail_score = None

    # Find matching results
    for result in structure_results.get('results', []):
        if result['metadata'].get('case_path') == case_path:
            structure_score = result['score']
            break

    for result in detail_results.get('results', []):
        if result['metadata'].get('case_path') == case_path:
            detail_score = result['score']
            break

    # Combine scores (weighted average)
    if structure_score is not None and detail_score is not None:
        return 0.4 * structure_score + 0.6 * detail_score
    elif structure_score is not None:
        return structure_score
    elif detail_score is not None:
        return detail_score
    else:
        return float('inf')  # Not found in any results
