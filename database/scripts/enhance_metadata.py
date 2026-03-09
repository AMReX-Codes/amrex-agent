#!/usr/bin/env python3
"""
Enhanced metadata extraction and README generation for Pele cases.

Combines generic AMReX utilities with Pele-specific domain knowledge
to create comprehensive case documentation.

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.

Usage:
    python enhance_metadata.py /path/to/case/directory
    python enhance_metadata.py ~/amrex-repos/PeleC/Exec/RegTests/Sedov

    # Batch mode for multiple cases
    python enhance_metadata.py --batch ~/amrex-repos/PeleC/Exec/RegTests
"""

import logging
import sys
from pathlib import Path

# Import generic AMReX utilities
from amrex_metadata_utils import (
    catalog_generic_auxiliary_files,
    compare_inputs_variants,
    extract_generic_build_config,
    find_all_inputs_files,
    parse_inputs_file_simple,
)

# Import Pele-specific utilities
from pele_metadata_utils import (
    catalog_pele_auxiliary_files,
    extract_pele_build_config,
    get_mechanism_info,
    infer_combustion_regime,
)

# Check for clipboard support
try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

logger = logging.getLogger(__name__)

def extract_complete_metadata(case_path: Path) -> dict:
    """
    Extract combined AMReX and Pele metadata for a case.

    Parameters
    ----------
    case_path : Path
        Case directory to inspect.

    Returns
    -------
    Dict
        Metadata including build config, file catalog, inputs variants, and regime.
    """
    metadata = {}

    # Basic identification
    metadata['case_name'] = case_path.name
    metadata['case_path'] = str(case_path)

    # Generic AMReX build config
    generic_build = extract_generic_build_config(case_path)
    metadata.update(generic_build)

    # Pele-specific build config
    pele_build = extract_pele_build_config(case_path)
    metadata.update(pele_build)

    # Auxiliary files (Pele-specific interpretation takes precedence)
    pele_aux = catalog_pele_auxiliary_files(case_path)
    generic_aux = catalog_generic_auxiliary_files(case_path)

    # Merge: use Pele interpretation for chemistry files, generic for others
    pele_files = {f['file'] for f in pele_aux}
    combined_aux = pele_aux + [f for f in generic_aux if f['file'] not in pele_files]
    metadata['auxiliary_files'] = combined_aux

    # Input file variants
    metadata['input_variants'] = compare_inputs_variants(case_path)

    # Infer combustion regime
    metadata['combustion_regime'] = infer_combustion_regime(case_path, metadata)

    # Get mechanism details if available
    if 'chemistry_model' in metadata and metadata['chemistry_model']:
        mech_info = get_mechanism_info(metadata['chemistry_model'])
        if mech_info:
            metadata['mechanism_info'] = mech_info

    return metadata


def generate_readme_content(case_path: Path, metadata: dict) -> str:
    """
    Generate README.md content from extracted metadata.

    Parameters
    ----------
    case_path : Path
        Case directory.
    metadata : Dict
        Extracted metadata for the case.

    Returns
    -------
    str
        Rendered README content.
    """
    lines = [
        f"# {metadata.get('case_name', case_path.name)}",
        "",
        "**[One sentence physics description - TO BE FILLED]**",
        "",
    ]

    # Add combustion regime if detected
    if metadata.get('combustion_regime'):
        regime = metadata['combustion_regime'].replace('_', ' ').title()
        lines.extend([
            f"*Combustion Regime:* {regime}",
            "",
        ])

    lines.extend([
        "## Case Configuration",
        "",
        "| Parameter | Value |",
        "|:----------|:------|",
    ])

    # Dimensionality
    if metadata.get('dim'):
        lines.append(f"| Dimensionality | {metadata['dim']}D |")

    # Grid (from primary inputs file or first variant)
    variants = metadata.get('input_variants', [])
    if variants:
        lines.append(f"| Grid | {variants[0]['grid']} |")
        lines.append(f"| AMR levels | {variants[0]['max_level']} |")

    # Physics models (Pele-specific)
    if metadata.get('chemistry_model'):
        chem = metadata['chemistry_model']
        # Add detailed info if available
        if 'mechanism_info' in metadata:
            info = metadata['mechanism_info']
            lines.append(f"| Chemistry | {info['name']} ({info['species_count']} species, {info['fuel']}) |")
        else:
            lines.append(f"| Chemistry | {chem} |")

    if metadata.get('eos_model'):
        lines.append(f"| EOS | {metadata['eos_model']} |")

    if metadata.get('transport_model'):
        lines.append(f"| Transport | {metadata['transport_model']} |")

    # Compiler and parallelism (generic AMReX)
    if metadata.get('compiler'):
        lines.append(f"| Compiler | {metadata['compiler']} |")

    parallel = []
    if metadata.get('use_mpi'):
        parallel.append('MPI')
    if metadata.get('use_omp'):
        parallel.append('OpenMP')
    if metadata.get('use_cuda'):
        parallel.append('CUDA')
    if metadata.get('use_hip'):
        parallel.append('HIP')
    if parallel:
        lines.append(f"| Parallelism | {', '.join(parallel)} |")

    # Files section
    lines.extend(["", "## Files", ""])

    # Core files
    if (case_path / 'inputs').exists():
        lines.append("- **inputs**: Main configuration")
    if (case_path / 'GNUmakefile').exists():
        lines.append("- **GNUmakefile**: Build configuration")

    # Auxiliary files (sorted by type)
    aux_files = metadata.get('auxiliary_files', [])
    if aux_files:
        lines.append("")

        # Group by type
        by_type = {}
        for aux in aux_files:
            ftype = aux['type']
            if ftype not in by_type:
                by_type[ftype] = []
            by_type[ftype].append(aux)

        # Chemistry files first (if present)
        for ftype in ['chemistry_config', 'chemistry_data', 'problem_setup',
                      'problem_header', 'eb_geometry', 'data_file', 'config_file']:
            if ftype in by_type:
                for aux in by_type[ftype]:
                    lines.append(f"- **{aux['file']}**: {aux['purpose']}")

    # Input variants section (if multiple)
    if len(variants) > 1:
        lines.extend([
            "",
            "## Input File Variants",
            "",
            "| File | Grid | AMR Levels | Notes |",
            "|:-----|:-----|:-----------|:------|"
        ])
        for var in variants:
            notes = var.get('notes', '')
            lines.append(
                f"| {var['file']} | {var['grid']} ({var['dim_hint']}) | "
                f"{var['max_level']} | {notes} |"
            )

    # Physics section (template)
    lines.extend([
        "",
        "## Physics",
        "",
    ])

    # Add regime-specific template
    regime = metadata.get('combustion_regime')
    if regime == 'premixed_flame':
        lines.extend([
            "**[Premixed combustion case]**",
            "",
            "Describe the premixed flame configuration:",
            "- Flame type (1D, 2D, or 3D)",
            "- Fuel-air mixture composition",
            "- Flame stabilization mechanism",
            "- Expected flame speed/thickness",
        ])
    elif regime == 'diffusion_flame':
        lines.extend([
            "**[Diffusion (non-premixed) combustion case]**",
            "",
            "Describe the diffusion flame configuration:",
            "- Fuel and oxidizer injection",
            "- Mixing characteristics",
            "- Flame location/structure",
        ])
    elif regime == 'detonation':
        lines.extend([
            "**[Detonation wave case]**",
            "",
            "Describe the detonation:",
            "- Initiation mechanism",
            "- Expected detonation velocity",
            "- Wave structure (ZND, cellular, etc.)",
        ])
    elif regime == 'inert':
        lines.extend([
            "**[Inert flow case]**",
            "",
            "Describe the fluid dynamics:",
            "- Flow regime (shock, expansion, vortex, etc.)",
            "- Key phenomena",
            "- Governing equations",
        ])
    else:
        lines.extend([
            "**[TO BE FILLED]**",
            "",
            "Describe the physics being simulated:",
            "- Flow regime (compressible/low-Mach, laminar/turbulent)",
            "- Key phenomena (shocks, flames, mixing, etc.)",
            "- Governing equations",
        ])

    # Keywords section
    lines.extend([
        "",
        "## Keywords",
        "",
    ])

    # Auto-generate some keywords from metadata
    keywords = []
    if metadata.get('dim') == 2:
        keywords.append("2D")
    elif metadata.get('dim') == 3:
        keywords.append("3D")

    if regime:
        keywords.append(regime.replace('_', ' '))

    if 'mechanism_info' in metadata:
        keywords.append(metadata['mechanism_info']['fuel'])

    if keywords:
        lines.append(f"**Suggested:** {', '.join(keywords)}")
        lines.append("")

    lines.append("**[ADD MORE]**: shock, flame, turbulence, detonation, etc.")

    # Use cases section
    lines.extend([
        "",
        "## Use Cases",
        "",
        "**Good for:**",
        "- [Problem type 1]",
        "- [Problem type 2]",
        "",
        "**Not suitable for:**",
        "- [What this doesn't cover]",
        "",
        "## References",
        "",
    ])

    # Add mechanism reference if available
    if 'mechanism_info' in metadata:
        info = metadata['mechanism_info']
        lines.append(f"- Chemistry mechanism: {info['reference']}")

    lines.extend([
        "- [Additional paper citations if applicable]",
        "- [External documentation links]",
        ""
    ])

    return '\n'.join(lines)


def process_single_case(case_path: Path, save: bool = False, interactive: bool = True) -> dict:
    """
    Process a single case and optionally write README.md.

    Parameters
    ----------
    case_path : Path
        Case directory.
    save : bool, optional
        Whether to write README.md automatically.
    interactive : bool, optional
        Whether to prompt before saving.

    Returns
    -------
    Dict
        Extracted metadata for the case.
    """
    logger.debug(f"Analyzing case: {case_path}")
    logger.debug("=" * 80)

    # Extract complete metadata
    metadata = extract_complete_metadata(case_path)

    # Display metadata
    logger.debug("\n=== Build Configuration ===")
    for key in ['dim', 'chemistry_model', 'eos_model', 'transport_model',
                'compiler', 'use_mpi', 'use_cuda', 'use_hip']:
        if key in metadata and metadata[key]:
            logger.debug(f"  {key}: {metadata[key]}")

    # Display auxiliary files
    aux_files = metadata.get('auxiliary_files', [])
    if aux_files:
        logger.debug(f"\n=== Auxiliary Files ({len(aux_files)} found) ===")
        for f in aux_files[:10]:  # Show first 10
            logger.debug(f"  {f['file']:30s} → {f['purpose']}")
        if len(aux_files) > 10:
            logger.debug(f"  ... and {len(aux_files) - 10} more")

    # Display input variants
    variants = metadata.get('input_variants', [])
    if variants:
        logger.debug(f"\n=== Input File Variants ({len(variants)} found) ===")
        for v in variants:
            notes = f" ({v['notes']})" if v['notes'] else ""
            logger.debug(f"  {v['file']:20s} {v['grid']:20s} {v['dim_hint']:5s} AMR={v['max_level']}{notes}")

    # Display combustion regime
    if metadata.get('combustion_regime'):
        logger.debug("\n=== Combustion Regime ===")
        logger.debug(f"  {metadata['combustion_regime']}")

    # Generate README
    readme = generate_readme_content(case_path, metadata)

    logger.debug("\n" + "=" * 80)
    logger.debug("Generated README.md:")
    logger.debug("=" * 80)
    logger.info(readme)

    # Save README with options
    if save:
        # Auto-save in batch mode
        readme_path = case_path / 'README.md'
        if readme_path.exists():
            backup = readme_path.with_suffix('.md.bak')
            readme_path.rename(backup)
            logger.debug(f"Backed up existing README to {backup.name}")

        with open(readme_path, 'w') as f:
            f.write(readme)
        logger.debug(f"[OK] Saved to {readme_path}")

    elif interactive:
        # Interactive mode with LLM option
        logger.debug("\nOptions:")
        logger.debug("  y - Save README as-is")
        logger.debug("  n - Don't save")
        if HAS_CLIPBOARD:
            logger.debug("  l - Get LLM help (copies prompt to clipboard)")

        choice = input("\nChoice [y/n/l]: ").strip().lower()

        if choice == 'l' and HAS_CLIPBOARD:
            # PHASE 1: Fill in physics descriptions (excluding references)
            code_context = _extract_code_context(case_path)

            # Remove References section from template for Phase 1
            readme_no_refs = readme.rsplit('## References', 1)[0] + "## References\n\n[WILL BE FILLED IN PHASE 2]\n"

            llm_prompt_phase1 = f"""Fill in the [TO BE FILLED] sections in this PeleC test case README (Physics descriptions only - references will be added separately).

**Case:** {case_path.name}
**Path:** {case_path}

**Metadata:**
- Dimensionality: {metadata.get('dim', 'N/A')}D
- Grid: {metadata.get('n_cell', 'N/A')}
- Chemistry: {metadata.get('chemistry_model', 'None')}
- Regime: {metadata.get('combustion_regime', 'Unknown')}

**Code Context:**
{code_context}

**README to complete:**
```markdown
{readme_no_refs}
```

**Instructions:**
1. Replace all [TO BE FILLED] sections with accurate technical descriptions based on the code context
2. Focus on: Physics description, Keywords, Use cases
3. Leave the References section as "[WILL BE FILLED IN PHASE 2]"
4. Return ONLY the completed markdown (no explanations)
"""

            pyperclip.copy(llm_prompt_phase1)
            logger.debug("\n[LIST] PHASE 1: PHYSICS DESCRIPTION PROMPT COPIED")
            logger.debug("\nSteps:")
            logger.debug("1. Paste into Claude/GPT web interface")
            logger.debug("2. Copy the LLM's completed README response")
            logger.debug("3. Press ENTER here...")
            input()

            # Get Phase 1 response
            filled_readme = pyperclip.paste()

            if filled_readme.startswith('#') or '##' in filled_readme:
                logger.debug("\n[OK] Got filled README from clipboard")
                logger.debug("\nPreview:")
                logger.info(filled_readme[:300] + "...\n")

                # PHASE 2: Get references
                if input("Proceed to Phase 2 (References)? [Y/n]: ").strip().lower() != 'n':
                    llm_prompt_phase2 = f"""Find academic references with DOI links for this test case.

**Case:** {case_path.name}
**Case Type:** {metadata.get('combustion_regime', 'Unknown')}
**Chemistry:** {metadata.get('chemistry_model', 'None')}

**Instructions:**
1. Search for and provide citations in this format:
   - Author et al. (Year). Title. *Journal*, Volume(Issue), pages. https://doi.org/10.xxxx/xxxxx
2. Include:
   - Original paper for classic test cases (Sedov, Sod, Taylor-Green, etc.)
   - Chemistry mechanism development papers (if applicable)
   - Relevant validation or benchmark papers
3. If DOI not available, provide Google Scholar search URL
4. Return ONLY a markdown list of references (no explanations)

Example format:
- Sedov, L. I. (1959). *Similarity and Dimensional Methods in Mechanics*. Academic Press.
- Smith, J. et al. (2020). Validation study. *Combustion and Flame*, 220, 123-145. https://doi.org/10.1016/j.combustflame.2020.06.123
"""

                    pyperclip.copy(llm_prompt_phase2)
                    logger.debug("\n[LIST] PHASE 2: REFERENCES PROMPT COPIED")
                    logger.debug("\nSteps:")
                    logger.debug("1. Paste into Claude/GPT (or use web search if available)")
                    logger.debug("2. Copy the references list")
                    logger.debug("3. Press ENTER here...")
                    input()

                    # Get Phase 2 response
                    references = pyperclip.paste()

                    if references.strip().startswith('-') or references.strip().startswith('*'):
                        logger.debug("\n[OK] Got references from clipboard")
                        logger.debug("\n" + "="*80)
                        logger.debug("FILTERING REFERENCES:")
                        logger.debug("="*80)

                        import re
                        import shutil
                        import subprocess

                        # Parse references into individual entries
                        ref_lines = [line.strip() for line in references.strip().split('\n') if line.strip()]
                        ref_entries = []
                        current_ref = []

                        for line in ref_lines:
                            if line.startswith('-') or line.startswith('*'):
                                if current_ref:
                                    ref_entries.append(' '.join(current_ref))
                                current_ref = [line[1:].strip()]  # Remove leading - or *
                            else:
                                current_ref.append(line)

                        if current_ref:
                            ref_entries.append(' '.join(current_ref))

                        logger.debug(f"\nFound {len(ref_entries)} reference(s)")

                        # Detect browser command
                        browser_cmd = None
                        if shutil.which('wslview'):
                            browser_cmd = 'wslview'
                        elif shutil.which('xdg-open'):
                            browser_cmd = 'xdg-open'

                        # Interactive filtering
                        kept_refs = []
                        for i, ref in enumerate(ref_entries, 1):
                            logger.debug(f"\n[{i}/{len(ref_entries)}]")
                            # Show truncated reference
                            display_ref = ref if len(ref) <= 120 else ref[:117] + "..."
                            logger.debug(f"  {display_ref}")

                            # Extract URL if present
                            url_match = re.search(r'https?://[^\s\)]+', ref)

                            if url_match and browser_cmd:
                                url = url_match.group(0)
                                action = input("  Open URL and decide? [y/N/s(kip)/q(uit)]: ").strip().lower()

                                if action == 'y':
                                    try:
                                        subprocess.run([browser_cmd, url], check=False)
                                        logger.debug(f"  Opened: {url[:60]}...")
                                    except Exception as e:
                                        logger.debug(f"  [WARN]  Failed to open: {e}")

                                    keep = input("  Keep this reference? [Y/n]: ").strip().lower()
                                    if keep != 'n':
                                        kept_refs.append(ref)
                                        logger.debug("  [OK] Kept")
                                    else:
                                        logger.debug("  [FAIL] Discarded")

                                elif action == 's':
                                    # Skip (don't open, but ask to keep)
                                    keep = input("  Keep without opening? [Y/n]: ").strip().lower()
                                    if keep != 'n':
                                        kept_refs.append(ref)
                                        logger.debug("  [OK] Kept")
                                    else:
                                        logger.debug("  [FAIL] Discarded")

                                elif action == 'q':
                                    logger.debug("  Quitting filter - keeping all remaining")
                                    kept_refs.extend(ref_entries[i-1:])
                                    break
                                else:
                                    # Default: don't open, don't keep
                                    logger.debug("  [FAIL] Skipped")

                            else:
                                # No URL or no browser - just ask to keep
                                if not url_match:
                                    logger.debug("  (No URL found)")
                                if not browser_cmd:
                                    logger.debug("  (No browser command: wslview/xdg-open)")

                                keep = input("  Keep this reference? [Y/n/q(uit)]: ").strip().lower()
                                if keep == 'q':
                                    logger.debug("  Quitting filter - keeping all remaining")
                                    kept_refs.extend(ref_entries[i-1:])
                                    break
                                elif keep != 'n':
                                    kept_refs.append(ref)
                                    logger.debug("  [OK] Kept")
                                else:
                                    logger.debug("  [FAIL] Discarded")

                        # Format kept references
                        if kept_refs:
                            formatted_refs = '\n'.join(f"- {ref}" for ref in kept_refs)
                            logger.debug(f"\n[OK] Kept {len(kept_refs)}/{len(ref_entries)} references")
                        else:
                            formatted_refs = "- [No references selected]"
                            logger.debug("\n[WARN]  No references kept")

                        # Combine: filled README + filtered references
                        if '## References' in filled_readme:
                            readme_with_refs = filled_readme.rsplit('## References', 1)[0]
                            readme_with_refs += f"## References\n\n{formatted_refs}\n"
                        else:
                            readme_with_refs = filled_readme + f"\n## References\n\n{formatted_refs}\n"

                        filled_readme = readme_with_refs
                    else:
                        logger.warning("[WARN]  References don't look right - keeping Phase 1 only")

                # Final preview and save
                logger.debug("\n" + "="*80)
                logger.debug("FINAL README PREVIEW:")
                logger.debug("="*80)
                logger.info(filled_readme[:500] + "...\n")

                if input("Save this version? [Y/n]: ").strip().lower() != 'n':
                    readme = filled_readme
                    choice = 'y'
                else:
                    logger.debug("Keeping original skeleton")
            else:
                logger.warning("[WARN]  Clipboard doesn't look like markdown - keeping original")

        if choice == 'y':
            readme_path = case_path / 'README.md'
            if readme_path.exists():
                backup = readme_path.with_suffix('.md.bak')
                readme_path.rename(backup)
                logger.debug(f"Backed up existing README to {backup.name}")

            with open(readme_path, 'w') as f:
                f.write(readme)
            logger.debug(f"[OK] Saved to {readme_path}")

    return metadata


def _extract_code_context(case_path: Path) -> str:
    """Extract code snippets for LLM context."""
    context = []

    # prob.cpp initialization
    prob_cpp = case_path / 'prob.cpp'
    if prob_cpp.exists():
        try:
            with open(prob_cpp) as f:
                content = f.read()
                # Find probinit or pc_initdata
                for func in ['probinit', 'pc_initdata']:
                    if func in content.lower():
                        start = content.lower().find(func)
                        snippet = content[start:start+600]
                        context.append(f"=== prob.cpp ({func}) ===\n{snippet[:600]}")
                        break
        except Exception as e:
            context.append(f"Could not read prob.cpp: {e}")

    # Key input parameters
    inputs = find_all_inputs_files(case_path)
    if inputs:
        params = parse_inputs_file_simple(inputs[0])
        # Filter to physics-relevant params
        key_params = {k: v for k, v in params.items()
                     if any(word in k.lower() for word in
                           ['prob', 'bc', 'velocity', 'pressure', 'temperature',
                            'fuel', 'mach', 'reynolds'])}
        if key_params:
            params_str = '\n'.join(f"{k} = {v}" for k, v in sorted(key_params.items()))
            context.append(f"=== {inputs[0].name} (key params) ===\n{params_str}")

    return '\n\n'.join(context) if context else "No additional code context available"


def process_batch(root_path: Path, pattern: str = "*/", save: bool = False) -> None:
    """
    Process multiple cases in batch mode.

    Parameters
    ----------
    root_path : Path
        Root directory to search.
    pattern : str, optional
        Glob pattern for subdirectories.
    save : bool, optional
        Whether to save README.md files without prompting.

    Returns
    -------
    None
        Processes cases and optionally writes README.md files.
    """
    logger.debug(f"Searching for cases in: {root_path}")

    # Find all subdirectories with GNUmakefile or inputs file
    case_dirs = []
    for subdir in root_path.glob(pattern):
        if subdir.is_dir():
            has_makefile = (subdir / 'GNUmakefile').exists()
            has_inputs = any(subdir.glob('inputs*'))
            if has_makefile or has_inputs:
                case_dirs.append(subdir)

    logger.debug(f"Found {len(case_dirs)} potential cases\n")

    # Process each case
    results = []
    for i, case_dir in enumerate(case_dirs, 1):
        logger.debug(f"\n{'='*80}")
        logger.debug(f"[{i}/{len(case_dirs)}] Processing: {case_dir.name}")
        logger.debug(f"{'='*80}\n")

        try:
            metadata = process_single_case(case_dir, save=save, interactive=False)
            results.append({
                'case': case_dir.name,
                'status': 'success',
                'metadata': metadata
            })
        except Exception as e:
            logger.debug(f"ERROR: {e}")
            results.append({
                'case': case_dir.name,
                'status': 'failed',
                'error': str(e)
            })

    # Summary
    logger.debug("\n" + "="*80)
    logger.debug("BATCH PROCESSING SUMMARY")
    logger.debug("="*80)
    successful = sum(1 for r in results if r['status'] == 'success')
    logger.debug(f"Processed: {len(results)} cases")
    logger.debug(f"Successful: {successful}")
    logger.debug(f"Failed: {len(results) - successful}")

    if save:
        logger.debug(f"\n[OK] Saved {successful} README.md files")


def main() -> None:
    """
    Run the metadata enhancement CLI.

    Returns
    -------
    None
        Executes the CLI workflow.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract metadata and generate READMEs for Pele cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single case (interactive)
  python enhance_metadata.py ~/amrex-repos/PeleC/Exec/RegTests/Sedov

  # Batch mode (all subdirectories)
  python enhance_metadata.py --batch ~/amrex-repos/PeleC/Exec/RegTests

  # Batch mode with auto-save
  python enhance_metadata.py --batch --save ~/amrex-repos/PeleC/Exec/Production
        """
    )

    parser.add_argument('path', type=Path, help='Case directory or root path for batch mode')
    parser.add_argument('--batch', action='store_true', help='Process multiple cases')
    parser.add_argument('--save', action='store_true', help='Save READMEs without prompting')
    parser.add_argument('--pattern', default='*/', help='Glob pattern for batch mode (default: */)')

    args = parser.parse_args()

    if not args.path.exists():
        logger.debug(f"Error: {args.path} does not exist")
        sys.exit(1)

    if args.batch:
        process_batch(args.path, pattern=args.pattern, save=args.save)
    else:
        process_single_case(args.path, save=args.save, interactive=True)


if __name__ == '__main__':
    main()
