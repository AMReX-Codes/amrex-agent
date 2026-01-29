"""
Abstract backend interface for AMReX plotfile visualization.

Supports multiple backends:
- AMReXToolsBackend: Native C++ tools (fextract, fextrema, fsnapshot)
- PyAMReXBackend: Python bindings (pyamrex)
- YtBackend: yt-project (fallback)

Based on: Plan at /home/jmsexton/.claude/plans/dynamic-foraging-pond.md
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

class VisualizationBackend(ABC):
    """Abstract base class for visualization backends.

    All backends must implement:
    - available(): Check if backend is usable
    - create_slice_plot(): Generate 2D slice visualization
    - get_field_list(): List available fields in plotfile
    - get_extrema(): Get min/max values for scaling

    Example:
        >>> backend = AMReXToolsBackend(config)
        >>> if backend.available():
        ...     fields = backend.get_field_list(plotfile)
        ...     backend.create_slice_plot(plotfile, 'Temp', 'z', output_path)
    """

    def __init__(self, config):
        """
        Initialize backend with configuration.

        Args:
            config: AMReXAgentConfig instance
        """
        self.config = config

    @abstractmethod
    def available(self) -> bool:
        """
        Check if backend is available.

        Returns
        -------
        bool
            True if backend can be used, False otherwise.

        Example:
            AMReXToolsBackend checks if fvarnames.ex exists
            YtBackend checks if yt can be imported
        """
        pass

    @abstractmethod
    def create_slice_plot(self,
                         plotfile: Path,
                         field: str,
                         axis: str,
                         output_path: Path,
                         **kwargs) -> Path:
        """
        Create 2D slice plot.

        Parameters
        ----------
        plotfile : Path
            Path to AMReX plotfile directory.
        field : str
            Variable name to plot (e.g., 'Temp', 'density').
        axis : str
            Slice axis ('x', 'y', or 'z').
        output_path : Path
            Where to save PNG image.
        **kwargs : dict
            Backend-specific options such as vmin, vmax, colormap, max_level.

        Returns
        -------
        Path
            Path to generated image file.
        """
        pass

    @abstractmethod
    def get_field_list(self, plotfile: Path) -> list[str]:
        """
        Get list of available fields in plotfile.

        Parameters
        ----------
        plotfile : Path
            Path to AMReX plotfile directory.

        Returns
        -------
        list of str
            Field names (e.g., ['Temp', 'density', 'x_velocity']).

        Example:
            >>> fields = backend.get_field_list(Path('plt00100'))
            >>> print(fields)
            ['density', 'Temp', 'x_velocity', 'y_velocity', 'z_velocity']
        """
        pass

    @abstractmethod
    def get_extrema(self, plotfile: Path, field: str) -> dict[str, float]:
        """
        Get min/max values for field (for colormap scaling).

        Parameters
        ----------
        plotfile : Path
            Path to AMReX plotfile directory.
        field : str
            Variable name.

        Returns
        -------
        dict
            Dictionary with 'min' and 'max' keys.

        Example:
            >>> extrema = backend.get_extrema(Path('plt00100'), 'Temp')
            >>> print(extrema)
            {'min': 298.15, 'max': 2500.0}
        """
        pass
