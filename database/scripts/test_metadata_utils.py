#!/usr/bin/env python3
"""
Test metadata extraction utilities.

Quick validation that generic AMReX and Pele-specific utilities work.
"""

from pathlib import Path
import sys

import logging

# Import utilities
from amrex_metadata_utils import (
    extract_generic_build_config,
    catalog_generic_auxiliary_files,
    compare_inputs_variants,
)

from pele_metadata_utils import (
    extract_pele_build_config,
    catalog_pele_auxiliary_files,
    infer_combustion_regime,
    get_mechanism_info,
    get_fuel_from_mechanism,
)


logger = logging.getLogger(__name__)

def test_generic_utils():
    """
    Test generic AMReX utilities on the current directory.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Runs logging-based checks.
    """
    logger.debug("=" * 80)
    logger.debug("TEST: Generic AMReX Utilities")
    logger.debug("=" * 80)

    case_path = Path.cwd()
    logger.debug(f"\nTesting on: {case_path}\n")

    # Test build config extraction
    logger.debug("--- Generic Build Config ---")
    build_config = extract_generic_build_config(case_path)
    if build_config:
        for key, val in build_config.items():
            logger.debug(f"  {key}: {val}")
    else:
        logger.debug("  No GNUmakefile found")

    # Test file cataloging
    logger.debug("\n--- Generic Auxiliary Files ---")
    aux_files = catalog_generic_auxiliary_files(case_path)
    if aux_files:
        for f in aux_files[:5]:
            logger.debug(f"  {f['file']:30s} [{f['type']}] → {f['purpose']}")
        if len(aux_files) > 5:
            logger.debug(f"  ... and {len(aux_files) - 5} more")
    else:
        logger.debug("  No auxiliary files found")

    # Test input variants
    logger.debug("\n--- Input File Variants ---")
    variants = compare_inputs_variants(case_path)
    if variants:
        for v in variants:
            logger.debug(f"  {v['file']:20s} {v['grid']:15s} {v['dim_hint']:5s} AMR={v['max_level']}")
    else:
        logger.debug("  No inputs files found")

    logger.debug("\n[OK] Generic utilities test complete\n")


def test_pele_utils():
    """
    Test Pele-specific utilities on the current directory.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Runs logging-based checks.
    """
    logger.debug("=" * 80)
    logger.debug("TEST: Pele-Specific Utilities")
    logger.debug("=" * 80)

    case_path = Path.cwd()
    logger.debug(f"\nTesting on: {case_path}\n")

    # Test Pele build config extraction
    logger.debug("--- Pele Build Config ---")
    pele_config = extract_pele_build_config(case_path)
    if pele_config:
        for key, val in pele_config.items():
            logger.debug(f"  {key}: {val}")
    else:
        logger.debug("  No Pele-specific config found (not a Pele case?)")

    # Test Pele file cataloging
    logger.debug("\n--- Pele Auxiliary Files ---")
    pele_files = catalog_pele_auxiliary_files(case_path)
    if pele_files:
        for f in pele_files[:5]:
            logger.debug(f"  {f['file']:30s} [{f['type']}] → {f['purpose']}")
        if len(pele_files) > 5:
            logger.debug(f"  ... and {len(pele_files) - 5} more")
    else:
        logger.debug("  No Pele-specific files found")

    # Test combustion regime inference
    logger.debug("\n--- Combustion Regime Inference ---")
    metadata = pele_config.copy()
    metadata['case_name'] = case_path.name
    regime = infer_combustion_regime(case_path, metadata)
    if regime:
        logger.debug(f"  Inferred regime: {regime}")
    else:
        logger.debug("  Could not infer combustion regime")

    # Test mechanism info lookup
    if pele_config.get('chemistry_model'):
        logger.debug("\n--- Mechanism Information ---")
        mech = pele_config['chemistry_model']
        info = get_mechanism_info(mech)
        if info:
            logger.debug(f"  Name: {info['name']}")
            logger.debug(f"  Species: {info['species_count']}")
            logger.debug(f"  Fuel: {info['fuel']}")
            logger.debug(f"  Description: {info['description']}")
            logger.debug(f"  Reference: {info['reference']}")
        else:
            logger.debug(f"  No detailed info for mechanism: {mech}")

        fuel = get_fuel_from_mechanism(mech)
        logger.debug(f"  Primary fuel: {fuel}")

    logger.debug("\n[OK] Pele utilities test complete\n")


def test_mechanism_database():
    """
    Test mechanism database lookups.

    Parameters
    ----------
    None

    Returns
    -------
    None
        Runs logging-based checks.
    """
    logger.debug("=" * 80)
    logger.debug("TEST: Mechanism Database")
    logger.debug("=" * 80)

    test_mechanisms = ['drm19', 'lidryer', 'gri30', 'sandiego', 'dodecane_lu', 'unknown']

    logger.debug("\nTesting mechanism lookups:\n")
    for mech in test_mechanisms:
        info = get_mechanism_info(mech)
        fuel = get_fuel_from_mechanism(mech)

        if info:
            logger.debug(f"  {mech:20s} → {info['name']:20s} ({info['species_count']:3d} species, {fuel})")
        elif fuel:
            logger.debug(f"  {mech:20s} → (no details, fuel: {fuel})")
        else:
            logger.debug(f"  {mech:20s} → NOT FOUND")

    logger.debug("\n[OK] Mechanism database test complete\n")


def main():
    """
    Run all metadata utility tests.

    Returns
    -------
    None
        Executes the test suite.
    """
    logger.debug("\n" + "=" * 80)
    logger.debug("METADATA UTILITIES TEST SUITE")
    logger.debug("=" * 80 + "\n")

    # Run tests
    test_generic_utils()
    test_pele_utils()
    test_mechanism_database()

    logger.debug("=" * 80)
    logger.debug("ALL TESTS COMPLETE")
    logger.debug("=" * 80)
    logger.debug("\nNOTE: Some tests may show 'not found' if run outside a case directory.")
    logger.debug("For full testing, run from a PeleC case directory, e.g.:")
    logger.debug("  cd ~/amrex-repos/PeleC/Exec/RegTests/Sedov")
    logger.debug("  python /path/to/test_metadata_utils.py")


if __name__ == '__main__':
    main()
