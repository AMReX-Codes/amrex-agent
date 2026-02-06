"""
VisualizationService - Multi-backend AMReX plotfile visualization.

Purpose: Generate visualizations from AMReX plotfiles
Backends: AMReX native tools (preferred), pyamrex (optional), yt-project (fallback)

Phase 4: yt-only
Phase 5: Multi-backend with AMReX tools priority

Based on: Plan at /home/jmsexton/.claude/plans/dynamic-foraging-pond.md
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

class VisualizationService:
    """Multi-backend AMReX plotfile visualization.

    Features:
    - Auto-selects best available backend:
      1. AMReX Tools (fextract, fextrema, fsnapshot)
      2. PyAMReX (Python bindings) - optional
      3. yt-project (fallback)
    - Container-aware two-stage architecture (with yt backend)
    - Auto-detect available fields
    - Standard plots (Temp, density, species)

    Example:
        >>> viz = VisualizationService(config)
        >>> logger.debug(f"Backend: {viz.backend.__class__.__name__}")
        >>> images = viz.create_standard_plots(run_dir)
        >>> logger.debug(f"Generated {len(images)} plots")
    """

    def __init__(self, config):
        self.config = config
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)
        self.container_mode = getattr(config, 'container_mode', False)
        self.backend = self._select_backend()

    def _select_backend(self):
        """Auto-select best available backend."""
        from .amrex_tools_backend import AMReXToolsBackend
        from .yt_backend import YtBackend

        # Optional: pyamrex backend
        try:
            from .pyamrex_backend import PyAMReXBackend
            has_pyamrex = True
        except ImportError:
            has_pyamrex = False

        # Priority order
        backends = [
            ('amrex_tools', AMReXToolsBackend),  # Priority 1: Native C++ tools
        ]

        if has_pyamrex:
            backends.append(('pyamrex', PyAMReXBackend))  # Priority 2: Python bindings

        backends.append(('yt', YtBackend))  # Priority 3: Fallback

        for name, backend_class in backends:
            backend = backend_class(self.config)
            if backend.available():
                logger.debug(f" Selected visualization backend: {name}")
                return backend

        raise RuntimeError("No visualization backend available")

    def find_plotfiles(self, run_dir: Path) -> list[Path]:
        """
        Find all plt* directories in run directory.

        Call context: Used by visualization workflows to enumerate plotfiles.

        Parameters
        ----------
        run_dir : Path
            Run directory to search.

        Returns
        -------
        list of Path
            Plotfile directories found.
        """
        if isinstance(run_dir, str):
            run_dir = Path(run_dir)

        plotfiles = sorted(run_dir.glob('plt*'))
        plotfiles = [p for p in plotfiles if p.is_dir()]

        logger.debug(f" Found {len(plotfiles)} plotfiles in {run_dir}")
        return plotfiles

    def load_latest(self, run_dir: Path):
        """
        Load most recent plotfile with yt.

        Call context: Used by visualization workflows to inspect latest output.

        Parameters
        ----------
        run_dir : Path
            Run directory containing plotfiles.

        Returns
        -------
        object
            yt dataset for the latest plotfile.
        """
        import yt

        plotfiles = self.find_plotfiles(run_dir)
        if not plotfiles:
            raise FileNotFoundError(f"No plotfiles found in {run_dir}")

        latest = plotfiles[-1]
        logger.debug(f" Loading plotfile: {latest.name}")
        ds = yt.load(str(latest))
        return ds

    def create_standard_plots(self,
                             run_dir: Path,
                             output_dir: Path | None = None,
                             vis_config: dict | None = None) -> list[Path]:
        """
        Generate standard visualization suite using selected backend.

        Phase 5: Delegates to backend implementation.

        Call context: Primary entry point used by the Visualization node.

        Parameters
        ----------
        run_dir : Path
            Run directory containing plotfiles.
        output_dir : Path or None, optional
            Directory for generated images.
        vis_config : dict or None, optional
            Visualization configuration overrides.

        Returns
        -------
        list of Path
            Generated image paths.
        """
        if isinstance(run_dir, str):
            run_dir = Path(run_dir)

        if output_dir is None:
            output_dir = run_dir / 'visualization'
        elif isinstance(output_dir, str):
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"\n[INFO] Creating standard plots -> {output_dir}")
        logger.debug(f" Using backend: {self.backend.__class__.__name__}")
        logger.debug("vis_config: %s", vis_config)

        # Container mode uses extraction + rendering (yt backend only)
        if self.container_mode:
            return self._create_plots_container_mode(run_dir, output_dir, vis_config)

        # Find plotfiles
        plotfiles = self.find_plotfiles(run_dir)
        if not plotfiles:
            logger.warning("[WARN] No plotfiles found")
            return []

        # Use latest plotfile
        latest = plotfiles[-1]

        # Get available fields
        fields = self.backend.get_field_list(latest)
        logger.debug("available fields (%d): %s", len(fields), fields)

        # Determine which fields to plot
        plots = []
        if isinstance(vis_config, dict) and vis_config.get('plots'):
            plots = vis_config.get('plots', [])
        else:
            standard_fields = []
            if 'Temp' in fields or 'temperature' in fields:
                field_name = 'Temp' if 'Temp' in fields else 'temperature'
                standard_fields.append((field_name, 'hot'))

            if 'density' in fields:
                standard_fields.append(('density', 'viridis'))
            plots = [{'type': 'slice', 'field': f, 'axis': 'z', 'colormap': c} for f, c in standard_fields]

        # Create plots
        images = []
        logger.debug("plots to render (%d): %s", len(plots), plots)
        for plot_cfg in plots:
            try:
                if plot_cfg.get('type') != 'slice':
                    logger.debug(f"  Skipping unsupported plot type: {plot_cfg.get('type')}")
                    continue
                field = plot_cfg.get('field')
                axis = plot_cfg.get('axis', 'z')
                colormap = plot_cfg.get('colormap', 'viridis')
                if not field:
                    logger.debug("  Skipping plot with missing field")
                    continue

                output_path = output_dir / f"{field}_slice.png"

                self.backend.create_slice_plot(
                    plotfile=latest,
                    field=field,
                    axis=axis,
                    output_path=output_path,
                    colormap=colormap
                )

                images.append(output_path)
                logger.debug(f"  Created {field} slice")

            except Exception as e:
                logger.debug(f"  Failed to create {field} slice: {e}")

        logger.debug(f"\n[ OK ] Generated {len(images)} visualizations")

        return images

    def extract_data(self,
                    plotfile_path: Path,
                    config: dict,
                    output_path: Path) -> Path:
        """
        Stage 1: Extract data from plotfile (headless, container-safe).

        This runs on HPC/container without GUI requirements.
        Only needs yt for plotfile reading.

        Call context: Used by container-mode visualization workflows.

        Parameters
        ----------
        plotfile_path : Path
            Path to AMReX plotfile.
        config : dict
            Visualization configuration.
        output_path : Path
            Directory for extracted HDF5 file.

        Returns
        -------
        Path
            Extracted HDF5 file path.
        """
        import h5py
        import yt

        logger.debug(f"\n[INFO] Extracting data from {plotfile_path.name} (headless mode)")

        ds = yt.load(str(plotfile_path))

        extracted = {}

        # Extract slices requested in config
        for plot_config in config.get('plots', []):
            if plot_config['type'] == 'slice':
                axis = plot_config.get('axis', 'z')
                field = plot_config['field']

                try:
                    # Create slice at center
                    slc = ds.slice(axis, 0.5)

                    # Extract data as numpy arrays
                    x_coord = 'x' if axis != 'x' else 'y'
                    y_coord = 'y' if axis != 'z' else 'z'

                    extracted[f"slice_{field}_{axis}"] = {
                        'x': slc[x_coord].to_ndarray(),
                        'y': slc[y_coord].to_ndarray(),
                        'data': slc[field].to_ndarray(),
                        'units': str(slc[field].units),
                        'bounds': [float(slc[field].min()), float(slc[field].max())],
                        'field': field,
                        'axis': axis
                    }

                    logger.debug(f"   Extracted {field} slice along {axis}")

                except Exception as e:
                    logger.debug(f"   Failed to extract {field}: {e}")

        # Save to HDF5 (portable format)
        output_file = output_path / f"{plotfile_path.name}_extracted.h5"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(output_file, 'w') as f:
            for key, data in extracted.items():
                grp = f.create_group(key)

                for field_key, value in data.items():
                    if isinstance(value, np.ndarray):
                        grp.create_dataset(field_key, data=value)
                    else:
                        grp.attrs[field_key] = value

        logger.debug(f"[ OK ] Extracted data saved to {output_file.name}")
        logger.debug(f"       File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

        return output_file

    def render_from_extracted(self,
                             extracted_path: Path,
                             config: dict,
                             output_dir: Path) -> list[Path]:
        """
        Stage 2: Render plots from extracted data (local, with GUI stack).

        This runs locally with full matplotlib/GUI support.
        No yt required - just loads HDF5 and renders.

        Call context: Used by container-mode visualization workflows.

        Parameters
        ----------
        extracted_path : Path
            Path to HDF5 file from extract_data().
        config : dict
            Visualization configuration.
        output_dir : Path
            Output directory for images.

        Returns
        -------
        list of Path
            PNG file paths.
        """
        import h5py
        import matplotlib.pyplot as plt

        logger.debug(f"\n[INFO] Rendering plots from {extracted_path.name}")

        output_dir.mkdir(parents=True, exist_ok=True)

        images = []

        with h5py.File(extracted_path, 'r') as f:
            for key in f:
                if key.startswith('slice_'):
                    try:
                        grp = f[key]

                        # Load data
                        x = grp['x'][:]
                        y = grp['y'][:]
                        data = grp['data'][:]

                        # Load metadata
                        units = grp.attrs.get('units', '')
                        field = grp.attrs.get('field', 'unknown')
                        axis = grp.attrs.get('axis', 'z')

                        # Create plot
                        fig, ax = plt.subplots(figsize=(10, 8))

                        im = ax.pcolormesh(x, y, data, shading='auto')

                        ax.set_xlabel('x (cm)')
                        ax.set_ylabel('y (cm)')
                        ax.set_title(f'{field} slice (axis={axis})')

                        cbar = plt.colorbar(im, ax=ax)
                        cbar.set_label(f'{field} [{units}]')

                        # Apply colormap based on field
                        if 'Temp' in field:
                            im.set_cmap('hot')
                        elif 'density' in field:
                            im.set_cmap('viridis')
                        elif 'velocity' in field:
                            im.set_cmap('plasma')
                        else:
                            im.set_cmap('RdYlBu_r')

                        # Save
                        output_path = output_dir / f"{field}_slice.png"
                        plt.savefig(output_path, dpi=300, bbox_inches='tight')
                        plt.close()

                        images.append(output_path)

                        logger.debug(f"   Rendered {field} slice")

                    except Exception as e:
                        logger.debug(f"   Failed to render {key}: {e}")

        logger.debug(f"[ OK ] Rendered {len(images)} images")

        return images

    def detect_interesting_features(self, ds) -> dict:
        """
        Auto-detect features worth visualizing.

        Call context: Used to inform visualization defaults.

        Parameters
        ----------
        ds : object
            yt dataset.

        Returns
        -------
        dict
            Feature summary for plotting.
        """
        features = {
            'has_species': False,
            'species_list': [],
            'dimensions': 3 if ds.dimensionality == 3 else 2
        }

        # Check for species fields
        for field in ds.field_list:
            field_name = field[1] if isinstance(field, tuple) else field

            if field_name.startswith('Y(') and field_name.endswith(')'):
                species = field_name[2:-1]
                features['species_list'].append(species)
                features['has_species'] = True

        return features

    def _create_plots_container_mode(self,
                                    run_dir: Path,
                                    output_dir: Path,
                                    vis_config: dict | None) -> list[Path]:
        """
        Create plots in container mode (extraction + rendering split).

        This is the workflow for podman-hpc/shifter environments.
        """
        logger.debug(" Container mode: Using extraction + rendering workflow")

        plotfiles = self.find_plotfiles(run_dir)
        if not plotfiles:
            return []

        # Use latest plotfile
        latest = plotfiles[-1]

        # Default config if not provided
        if vis_config is None:
            vis_config = {
                'plots': [
                    {'type': 'slice', 'field': 'Temp', 'axis': 'z'},
                    {'type': 'slice', 'field': 'density', 'axis': 'z'},
                ]
            }

        # Stage 1: Extract data (headless)
        extracted_dir = output_dir / 'extracted'
        extracted_file = self.extract_data(latest, vis_config, extracted_dir)

        # Stage 2: Render locally
        images = self.render_from_extracted(extracted_file, vis_config, output_dir)

        return images

    def _create_profiles(self, ds, output_dir: Path, vis_config: dict) -> list[Path]:
        """Create 1D profile plots."""
        import matplotlib.pyplot as plt

        images = []

        for plot_cfg in vis_config.get('plots', []):
            if plot_cfg.get('type') != 'profile':
                continue

            field = plot_cfg['field']
            direction = plot_cfg.get('direction', 'x')

            try:
                # Create ray along direction
                if direction == 'x':
                    ray = ds.ray([0, 0.5, 0.5], [1, 0.5, 0.5])
                    coord = 'x'
                elif direction == 'y':
                    ray = ds.ray([0.5, 0, 0.5], [0.5, 1, 0.5])
                    coord = 'y'
                else:  # z
                    ray = ds.ray([0.5, 0.5, 0], [0.5, 0.5, 1])
                    coord = 'z'

                # Plot profile
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(ray[coord], ray[field])
                ax.set_xlabel(f'{coord} (cm)')
                ax.set_ylabel(f'{field}')
                ax.set_title(f'{field} profile along {direction}-axis')
                ax.grid(True, alpha=0.3)

                output_path = output_dir / f"{field}_profile_{direction}.png"
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                plt.close()

                images.append(output_path)

                logger.debug(f"   Created {field} profile along {direction}")

            except Exception as e:
                logger.debug(f"   Failed to create {field} profile: {e}")

        return images

    def _field_available(self, ds, field_name: str) -> bool:
        """Check if field is available in dataset."""
        # Try boxlib convention
        if ('boxlib', field_name) in ds.field_list:
            return True

        # Try plain name
        if field_name in ds.field_list:
            return True

        # Try derived field
        try:
            ds.all_data()[field_name]
            return True
        except Exception:
            return False
