#!/usr/bin/env python3
"""
Generic AMReX metadata extraction utilities.

These functions work for ANY AMReX code (PeleC, PeleLMeX, ERF, WarpX, incflo, Castro, etc.)
Code-specific extraction should go in the respective config classes.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_generic_build_config(case_path: Path) -> dict[str, any]:
    """
    Extract generic AMReX build flags from a GNUmakefile.

    Parameters
    ----------
    case_path : Path
        Case directory containing a GNUmakefile.

    Returns
    -------
    Dict[str, any]
        Parsed build flags (dim, use_mpi, use_cuda, use_hip, use_omp, compiler).
    """
    makefile = case_path / 'GNUmakefile'
    if not makefile.exists():
        return {}

    config = {}

    try:
        with open(makefile) as f:
            content = f.read()

        # Extract DIM (universal across all AMReX codes)
        if match := re.search(r'DIM\s*[?:]?=\s*(\d)', content):
            config['dim'] = int(match.group(1))

        # Extract parallel/GPU flags (universal)
        config['use_mpi'] = bool(re.search(r'USE_MPI\s*[?:]?=\s*(TRUE|true|1)', content))
        config['use_cuda'] = bool(re.search(r'USE_CUDA\s*[?:]?=\s*(TRUE|true|1)', content))
        config['use_hip'] = bool(re.search(r'USE_HIP\s*[?:]?=\s*(TRUE|true|1)', content))
        config['use_omp'] = bool(re.search(r'USE_OMP\s*[?:]?=\s*(TRUE|true|1)', content))

        # Extract compiler (universal)
        if match := re.search(r'COMP\s*[?:]?=\s*(\w+)', content):
            config['compiler'] = match.group(1)

    except Exception as e:
        logger.debug(f"Warning: Could not parse GNUmakefile: {e}")

    return config


def catalog_generic_auxiliary_files(case_path: Path) -> list[dict[str, str]]:
    """
    Catalog common auxiliary files in an AMReX case directory.

    Parameters
    ----------
    case_path : Path
        Case directory to scan.

    Returns
    -------
    List[Dict[str, str]]
        File metadata entries with ``file``, ``type``, and ``purpose`` keys.
    """
    files = []

    # Problem setup files (universal to AMReX)
    # Case-insensitive patterns for Prob*.cpp, prob*.cpp, PROB*.cpp
    for prob_file in case_path.glob('[Pp][Rr][Oo][Bb]*.cpp'):
        files.append({
            'file': prob_file.name,
            'type': 'problem_setup',
            'purpose': 'Problem-specific initial/boundary conditions'
        })

    for prob_file in case_path.glob('[Pp][Rr][Oo][Bb]*.H'):
        files.append({
            'file': prob_file.name,
            'type': 'problem_header',
            'purpose': 'Problem-specific declarations'
        })

    # Fortran inputs (used by some AMReX codes)
    for probin in case_path.glob('probin*'):
        if probin.suffix not in ['.cpp', '.H']:
            files.append({
                'file': probin.name,
                'type': 'fortran_input',
                'purpose': 'Fortran namelist parameters'
            })

    # Embedded Boundary geometry (universal for EB-enabled codes)
    for geom_file in case_path.glob('*.stl'):
        files.append({
            'file': geom_file.name,
            'type': 'eb_geometry',
            'purpose': 'Embedded boundary geometry (STL)'
        })

    for geom_file in case_path.glob('*.ply'):
        files.append({
            'file': geom_file.name,
            'type': 'eb_geometry',
            'purpose': 'Embedded boundary geometry (PLY)'
        })

    # Generic data files (non-specific interpretation)
    for dat_file in case_path.glob('*.dat'):
        files.append({
            'file': dat_file.name,
            'type': 'data_file',
            'purpose': f'{dat_file.stem} data file'
        })

    # Generic YAML files (non-specific interpretation)
    for yaml_file in case_path.glob('*.yaml'):
        files.append({
            'file': yaml_file.name,
            'type': 'config_file',
            'purpose': f'{yaml_file.stem} configuration'
        })

    for yaml_file in case_path.glob('*.yml'):
        files.append({
            'file': yaml_file.name,
            'type': 'config_file',
            'purpose': f'{yaml_file.stem} configuration'
        })

    return files


def find_all_inputs_files(case_path: Path) -> list[Path]:
    """
    Find all inputs file variants in a case directory.

    Parameters
    ----------
    case_path : Path
        Case directory to scan.

    Returns
    -------
    List[Path]
        Sorted inputs files excluding backups.
    """
    inputs_files = []

    for pattern in ['inputs*', '*.inp']:
        inputs_files.extend(case_path.glob(pattern))

    # Filter out non-input files and backups
    inputs_files = [
        f for f in inputs_files
        if f.is_file() and not f.name.endswith(('.old', '.bak', '~'))
    ]

    return sorted(inputs_files)


def parse_inputs_file_simple(inputs_path: Path) -> dict[str, str]:
    """
    Parse a simple AMReX inputs file with ``key = value`` pairs.

    Parameters
    ----------
    inputs_path : Path
        Path to an inputs file.

    Returns
    -------
    Dict[str, str]
        Parsed parameter mapping.
    """
    params = {}

    try:
        with open(inputs_path) as f:
            for line in f:
                # Remove comments
                line = line.split('#')[0].strip()
                if not line or '=' not in line:
                    continue

                # Parse key = value
                key, value = line.split('=', 1)
                params[key.strip()] = value.strip()
    except Exception as e:
        logger.debug(f"Warning: Could not parse {inputs_path}: {e}")

    return params


def compare_inputs_variants(case_path: Path) -> list[dict[str, str]]:
    """
    Summarize inputs variants and their distinguishing hints.

    Parameters
    ----------
    case_path : Path
        Case directory to scan.

    Returns
    -------
    List[Dict[str, str]]
        Variant summaries with file name, grid, max_level, and notes.
    """
    variants = []
    inputs_files = find_all_inputs_files(case_path)

    for inputs_file in inputs_files:
        # Parse each inputs file
        params = parse_inputs_file_simple(inputs_file)

        variant = {
            'file': inputs_file.name,
            'grid': params.get('amr.n_cell', 'N/A'),
            'max_level': params.get('amr.max_level', '0'),
        }

        # Infer dimensionality
        if '2d' in inputs_file.name.lower():
            variant['dim_hint'] = '2D'
        elif '3d' in inputs_file.name.lower():
            variant['dim_hint'] = '3D'
        else:
            # Count dimensions from n_cell
            n_cell = variant['grid'].split()
            if len(n_cell) >= 2:
                variant['dim_hint'] = f"{len(n_cell)}D"
            else:
                variant['dim_hint'] = 'N/A'

        # Check for special purposes (generic patterns)
        notes = []
        if 'rt' in inputs_file.name.lower() or 'regtest' in inputs_file.name.lower():
            notes.append('Regression test')
        if 'production' in inputs_file.name.lower():
            notes.append('Production settings')
        if 'gpu' in inputs_file.name.lower():
            notes.append('GPU optimized')
        if 'debug' in inputs_file.name.lower():
            notes.append('Debug build')

        variant['notes'] = ', '.join(notes) if notes else ''

        variants.append(variant)

    return variants
