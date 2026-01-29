#!/usr/bin/env python3
"""
Pele-specific metadata extraction utilities.

These functions are specific to PelePhysics-based codes:
- PeleC (compressible reacting flow)
- PeleLMeX (low-Mach reacting flow)
- PeleMP (multiphase reacting flow)

Chemistry, EOS, and Transport are PelePhysics-specific concepts.

Related solvers: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import logging
import re
from pathlib import Path

# Comprehensive mechanism-to-fuel mapping (from architect.py)
MECHANISM_TO_FUEL = {
    # Methane mechanisms
    'drm19': ['methane', 'ch4', 'natural_gas'],
    'drm22': ['methane', 'ch4', 'natural_gas'],
    'gri30': ['methane', 'ch4'],
    'grimech30': ['methane', 'ch4'],
    'grimech12': ['methane', 'ch4'],
    'grimech30-noarn': ['methane', 'ch4'],
    'alzeta': ['methane', 'ch4'],
    'kolla': ['methane', 'ch4'],

    # Hydrogen mechanisms
    'lidryer': ['hydrogen', 'h2'],
    'burkedryer': ['hydrogen', 'h2'],
    'sandiego': ['hydrogen', 'h2'],
    'chem-h': ['hydrogen', 'h2'],
    'h2-co-co2-3spec': ['hydrogen', 'h2', 'syngas'],

    # Dodecane
    'dodecane_lu': ['dodecane', 'c12h26', 'diesel'],
    'dodecane_lu_qss': ['dodecane', 'c12h26', 'diesel'],

    # Decane
    'decane_3sp': ['decane', 'c10h22'],

    # Heptane
    'heptane_3sp': ['heptane', 'c7h16'],
    'heptane_fc': ['heptane', 'c7h16'],

    # Ethylene
    'luethylene': ['ethylene', 'c2h4'],
    'ethylene_af': ['ethylene', 'c2h4'],

    # Propane
    'propane_fc': ['propane', 'c3h8'],

    # Soot
    'sootreaction': ['soot', 'pah', 'polycyclic'],

    # Ions/Plasma
    'methaneions_direnzo': ['methane', 'ch4', 'plasma'],
    'ionizedair': ['air', 'plasma'],

    # Air/Null
    'air': ['air', 'nitrogen', 'oxygen'],
    'null': ['inert', 'air', 'non_reacting'],
}


# Detailed mechanism information
MECHANISM_DATABASE = {
    'drm19': {
        'name': 'DRM19',
        'species_count': 21,
        'fuel': 'methane',
        'description': 'Reduced methane mechanism from GRI-Mech',
        'reference': 'Kazakov & Frenklach (1994)'
    },
    'drm22': {
        'name': 'DRM22',
        'species_count': 24,
        'fuel': 'methane',
        'description': 'Slightly larger reduced methane mechanism',
        'reference': 'Kazakov & Frenklach (1994)'
    },
    'gri30': {
        'name': 'GRI-Mech 3.0',
        'species_count': 53,
        'fuel': 'methane',
        'description': 'Detailed natural gas combustion mechanism',
        'reference': 'Smith et al. (1999)'
    },
    'lidryer': {
        'name': 'Li-Dryer',
        'species_count': 9,
        'fuel': 'hydrogen',
        'description': 'Reduced hydrogen mechanism',
        'reference': 'Li et al. (2004)'
    },
    'burkedryer': {
        'name': 'Burke-Dryer',
        'species_count': 13,
        'fuel': 'hydrogen',
        'description': 'Detailed hydrogen mechanism',
        'reference': 'Burke et al. (2012)'
    },
    'sandiego': {
        'name': 'San Diego',
        'species_count': 20,
        'fuel': 'hydrogen',
        'description': 'Hydrogen/CO mechanism',
        'reference': 'UCSD Combustion Group'
    },
    'dodecane_lu': {
        'name': 'Lu Dodecane',
        'species_count': 106,
        'fuel': 'dodecane',
        'description': 'Reduced dodecane mechanism',
        'reference': 'Lu & Law (2009)'
    },
    'alzeta': {
        'name': 'Alzeta',
        'species_count': 23,
        'fuel': 'methane',
        'description': 'Reduced methane mechanism for lean combustion',
        'reference': 'Alzeta Corporation'
    },
    'kolla': {
        'name': 'Kolla',
        'species_count': 12,
        'fuel': 'methane',
        'description': 'Reduced methane mechanism for turbulent combustion',
        'reference': 'Kolla et al.'
    },
    'null': {
        'name': 'Null Chemistry',
        'species_count': 0,
        'fuel': 'inert',
        'description': 'No chemistry (inert flow)',
        'reference': 'N/A'
    },
}


logger = logging.getLogger(__name__)

def extract_pele_build_config(case_path: Path) -> dict[str, any]:
    """
    Extract Pele-specific build settings from a GNUmakefile.

    Parameters
    ----------
    case_path : Path
        Case directory containing a GNUmakefile.

    Returns
    -------
    Dict[str, any]
        Parsed PelePhysics settings (chemistry_model, eos_model, transport_model).
    """
    makefile = case_path / 'GNUmakefile'
    if not makefile.exists():
        return {}

    config = {}

    try:
        with open(makefile) as f:
            content = f.read()

        # Extract Chemistry_Model (PelePhysics-specific)
        if match := re.search(r'Chemistry_Model\s*[?:]?=\s*(\w+)', content, re.IGNORECASE):
            config['chemistry_model'] = match.group(1).lower()

        # Extract Eos_dir (PelePhysics-specific)
        if match := re.search(r'Eos_dir\s*[?:]?=\s*(\w+)', content, re.IGNORECASE):
            config['eos_model'] = match.group(1)

        # Extract Transport_dir (PelePhysics-specific)
        if match := re.search(r'Transport_dir\s*[?:]?=\s*(\w+)', content, re.IGNORECASE):
            config['transport_model'] = match.group(1)

    except Exception as e:
        logger.debug(f"Warning: Could not parse GNUmakefile: {e}")

    return config


def catalog_pele_auxiliary_files(case_path: Path) -> list[dict[str, str]]:
    """
    Catalog Pele-specific auxiliary files with domain hints.

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

    # Chemistry data files (*.dat)
    for dat_file in case_path.glob('*.dat'):
        stem_lower = dat_file.stem.lower()

        # Check if it's a known mechanism
        mech_info = None
        for mech in MECHANISM_DATABASE:
            if mech in stem_lower:
                mech_info = MECHANISM_DATABASE[mech]
                break

        if mech_info:
            files.append({
                'file': dat_file.name,
                'type': 'chemistry_data',
                'purpose': f'{mech_info["name"]} ({mech_info["species_count"]}-species {mech_info["fuel"]}) mechanism data'
            })
        else:
            files.append({
                'file': dat_file.name,
                'type': 'chemistry_data',
                'purpose': f'{dat_file.stem} mechanism data'
            })

    # Chemistry YAML configs (*.yaml, *.yml)
    for yaml_file in list(case_path.glob('*.yaml')) + list(case_path.glob('*.yml')):
        stem_lower = yaml_file.stem.lower()

        # Check if it's a known mechanism
        mech_info = None
        for mech in MECHANISM_DATABASE:
            if mech in stem_lower:
                mech_info = MECHANISM_DATABASE[mech]
                break

        if mech_info:
            files.append({
                'file': yaml_file.name,
                'type': 'chemistry_config',
                'purpose': f'{mech_info["name"]} chemistry configuration (Cantera format)'
            })
        else:
            files.append({
                'file': yaml_file.name,
                'type': 'chemistry_config',
                'purpose': f'{yaml_file.stem} chemistry configuration'
            })

    # Spray data files (PeleMP-specific)
    for spray_file in case_path.glob('*spray*.dat'):
        files.append({
            'file': spray_file.name,
            'type': 'spray_data',
            'purpose': 'Spray/particle injection data'
        })

    # Turbulence forcing (HIT cases)
    for forcing_file in case_path.glob('*forcing*.dat'):
        files.append({
            'file': forcing_file.name,
            'type': 'turbulence_forcing',
            'purpose': 'Turbulence forcing spectrum data'
        })

    return files


def infer_combustion_regime(case_path: Path, metadata: dict) -> str | None:
    """
    Infer combustion regime from case name and metadata.

    Parameters
    ----------
    case_path : Path
        Case directory.
    metadata : Dict
        Extracted metadata (may include mechanism/chemistry model).

    Returns
    -------
    Optional[str]
        Regime label (premixed_flame, diffusion_flame, detonation, auto_ignition, inert),
        or ``None`` if no inference is possible.
    """
    case_name = case_path.name.lower()

    # Check case name patterns
    if any(kw in case_name for kw in ['pmf', 'premixed', 'flame_sheet', 'bunsen']):
        return 'premixed_flame'

    if any(kw in case_name for kw in ['jet', 'coflow', 'diffusion', 'counterflow']):
        return 'diffusion_flame'

    if any(kw in case_name for kw in ['det', 'odw', 'detonation', 'znd']):
        return 'detonation'

    if any(kw in case_name for kw in ['ignition', 'autoignition', 'homogeneous']):
        return 'auto_ignition'

    if any(kw in case_name for kw in ['sedov', 'sod', 'shock', 'riemann']):
        return 'inert'

    # Check metadata
    if metadata.get('mechanism') is None and metadata.get('chemistry_model') is None:
        return 'inert'

    return None


def get_mechanism_info(mechanism: str) -> dict[str, any] | None:
    """
    Get metadata for a chemistry mechanism key.

    Parameters
    ----------
    mechanism : str
        Mechanism name (e.g., drm19, lidryer).

    Returns
    -------
    Optional[Dict[str, any]]
        Mechanism metadata dict if known.
    """
    return MECHANISM_DATABASE.get(mechanism.lower())


def get_fuel_from_mechanism(mechanism: str) -> str | None:
    """
    Get the primary fuel for a mechanism name.

    Parameters
    ----------
    mechanism : str
        Mechanism name.

    Returns
    -------
    Optional[str]
        Primary fuel if available.
    """
    fuels = MECHANISM_TO_FUEL.get(mechanism.lower())
    return fuels[0] if fuels else None
