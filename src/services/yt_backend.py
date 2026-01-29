"""
yt-project Backend for visualization.

Uses yt-project Python library for AMReX plotfile visualization.

Based on: Existing implementation in visualization.py (Phase 4)
Docs: https://yt-project.org/

This is the fallback backend when AMReX native tools are not available.
"""

import logging
from pathlib import Path

from .visualization_backend import VisualizationBackend

logger = logging.getLogger(__name__)

class YtBackend(VisualizationBackend):
    """
    yt-project backend (Phase 4 implementation).

    Advantages:
    - Mature Python library
    - Works with many simulation codes
    - Rich plotting capabilities
    - Good documentation

    Disadvantages:
    - Requires yt installation
    - Heavier than native tools
    - May have issues with some AMReX features

    Example:
        >>> backend = YtBackend(config)
        >>> if backend.available():
        ...     backend.create_slice_plot(plotfile, 'Temp', 'z', output_path)
    """

    def available(self) -> bool:
        """
        Check if yt is installed.

        Returns
        -------
        bool
            True if yt is available.
        """
        import importlib.util

        return importlib.util.find_spec("yt") is not None

    def get_field_list(self, plotfile: Path) -> list[str]:
        """
        Get field list using yt.

        Parameters
        ----------
        plotfile : Path
            Path to the plotfile directory.

        Returns
        -------
        list of str
            Field names in the plotfile.
        """
        import yt

        ds = yt.load(str(plotfile))

        # Extract field names from tuples like ('boxlib', 'density')
        # Return just the field name part
        fields = []
        for field in ds.field_list:
            if isinstance(field, tuple):
                fields.append(field[1])
            else:
                fields.append(field)

        return fields

    def get_extrema(self, plotfile: Path, field: str) -> dict[str, float]:
        """
        Get min/max using yt.

        Parameters
        ----------
        plotfile : Path
            Path to the plotfile directory.
        field : str
            Field name to query.

        Returns
        -------
        dict
            Mapping with "min" and "max" values.
        """
        import yt

        ds = yt.load(str(plotfile))
        ad = ds.all_data()

        # Try field with boxlib prefix first
        try:
            field_data = ad[('boxlib', field)]
        except KeyError:
            # Fall back to bare field name
            field_data = ad[field]

        return {
            'min': float(field_data.min()),
            'max': float(field_data.max())
        }

    def create_slice_plot(self,
                         plotfile: Path,
                         field: str,
                         axis: str,
                         output_path: Path,
                         **kwargs) -> Path:
        """
        Create slice plot using yt.

        Uses yt.SlicePlot for 2D slice visualization.

        Parameters
        ----------
        plotfile : Path
            Path to the plotfile directory.
        field : str
            Field name to plot.
        axis : str
            Slice axis ("x", "y", or "z").
        output_path : Path
            Output image file path.
        **kwargs : dict
            Optional overrides such as vmin, vmax, and colormap.

        Returns
        -------
        Path
            Path to the generated image.
        """
        import yt

        ds = yt.load(str(plotfile))

        # Prefer explicit field type when available (AMReX plotfiles use "boxlib")
        field_key = field
        if isinstance(field, str):
            candidate = ('boxlib', field)
            if candidate in ds.field_list:
                field_key = candidate

        # Create slice plot
        slc = yt.SlicePlot(ds, axis, field_key, center='c')

        # Apply scaling if provided
        if 'vmin' in kwargs and 'vmax' in kwargs:
            slc.set_zlim(field_key, kwargs['vmin'], kwargs['vmax'])

        # Apply colormap if provided
        if 'colormap' in kwargs:
            slc.set_cmap(field_key, kwargs['colormap'])

        # Save to file
        # yt saves with filename without extension, adds _Slice_<axis>_<field>.png
        # We need to handle this naming convention
        base_name = output_path.stem
        saved_files = slc.save(str(output_path.parent / base_name))
        logger.debug("yt save returned: %s", saved_files)

        # yt returns the generated filenames; use them directly when available
        if saved_files:
            for saved in saved_files:
                saved_path = Path(saved)
                if saved_path.exists():
                    logger.debug("yt saved file exists: %s", saved_path)
                    saved_path.replace(output_path)
                    logger.debug("renamed to: %s", output_path)
                    return output_path
                logger.debug("yt saved file missing on disk: %s", saved_path)

        # Fallbacks if the returned list is empty or missing
        yt_output_pattern = output_path.parent / f"{base_name}_Slice_{axis}_{field}.png"
        if yt_output_pattern.exists():
            logger.debug("fallback pattern matched: %s", yt_output_pattern)
            yt_output_pattern.replace(output_path)
            logger.debug("renamed to: %s", output_path)
            return output_path

        png_files = list(output_path.parent.glob(f"{base_name}*.png"))
        if png_files:
            logger.debug("fallback glob matched: %s", [str(p) for p in png_files])
            png_files[0].replace(output_path)
            logger.debug("renamed to: %s", output_path)
        else:
            logger.debug("no png files matched for base_name=%s in %s", base_name, output_path.parent)

        return output_path
