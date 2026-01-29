"""
AMReX Native Tools Backend for visualization.

Uses AMReX C++ command-line tools:
- fvarnames: List variables in plotfile
- fextrema: Get min/max values
- fsnapshot: Generate 2D images
- fextract: Extract 1D slices

Based on: Plan at /home/jmsexton/.claude/plans/dynamic-foraging-pond.md
Tools: ~/amrex-repos/amrex/Tools/Plotfile/
"""

import logging
import os
import subprocess
from pathlib import Path

from .visualization_backend import VisualizationBackend

logger = logging.getLogger(__name__)

class AMReXToolsBackend(VisualizationBackend):
    """
    Backend using AMReX native C++ tools.

    Advantages:
    - No Python dependencies (yt, pyamrex)
    - Fast compiled executables
    - Works on HPC without Python packages
    - Native AMReX format support

    Requires:
    - AMReX tools compiled (fvarnames.ex, fextrema.ex, fsnapshot.ex)
    - Tools in PATH or specified via config

    Example:
        >>> backend = AMReXToolsBackend(config)
        >>> if backend.available():
        ...     logger.debug(f"Tools found at: {backend.tool_dir}")
        ...     fields = backend.get_field_list(plotfile)
    """

    def __init__(self, config):
        super().__init__(config)
        self.tool_dir = self._find_tools()

    def _find_tools(self) -> Path | None:
        """
        Find AMReX tools directory.

        Priority:
        1. Config setting (amrex_tools_path)
        2. Environment variable (AMREX_TOOLS_DIR)
        3. Derived from amrex_repo_path in config
        4. Search common locations relative to amrex_agent

        Returns
        -------
        Path | None
            Path to tools directory, or None if not found.
        """
        def _has_tool(local_path: Path, tool_name: str) -> bool:
            """Check if tool exists (handles .ex, .gnu.ex, .intel.ex suffixes)."""
            return any([
                (local_path / tool_name).exists(),
                (local_path / f"{tool_name.replace('.ex', '.gnu.ex')}").exists(),
                (local_path / f"{tool_name.replace('.ex', '.intel.ex')}").exists(),
            ])

        # Priority 1: Explicit config setting
        if hasattr(self.config, 'amrex_tools_path') and self.config.amrex_tools_path:
            path = Path(self.config.amrex_tools_path)
            if _has_tool(path, 'fvarnames.ex'):
                return path

        # Priority 2: Environment variable
        if tools_env := os.getenv('AMREX_TOOLS_DIR'):
            path = Path(tools_env)
            if _has_tool(path, 'fvarnames.ex'):
                return path

        # Priority 3: Derive from amrex_repo_path in config
        if hasattr(self.config, 'amrex_repo_path') and self.config.amrex_repo_path:
            amrex_tools = Path(self.config.amrex_repo_path) / 'Tools' / 'Plotfile'
            if amrex_tools.exists() and _has_tool(amrex_tools, 'fvarnames.ex'):
                return amrex_tools

        # Priority 4: Search common locations (relative to amrex_agent root)
        repo_root = Path(__file__).parent.parent.parent
        search_paths = [
            repo_root.parent / 'amrex' / 'Tools' / 'Plotfile',  # ../amrex (sibling)
            Path('/usr/local/bin'),
            Path.cwd() / 'Tools' / 'Plotfile'
        ]

        for path in search_paths:
            if path.exists() and _has_tool(path, 'fvarnames.ex'):
                return path

        return None

    def _get_tool_path(self, tool_name: str) -> Path | None:
        """
        Get actual path to tool executable (handles .ex, .gnu.ex, .intel.ex suffixes).

        Parameters
        ----------
        tool_name : str
            Base tool name (e.g., "fvarnames.ex").

        Returns
        -------
        Path | None
            Path to actual executable, or None if not found.
        """
        if self.tool_dir is None:
            return None

        # Try different naming conventions
        candidates = [
            self.tool_dir / tool_name,
            self.tool_dir / f"{tool_name.replace('.ex', '.gnu.ex')}",
            self.tool_dir / f"{tool_name.replace('.ex', '.intel.ex')}",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def available(self) -> bool:
        """
        Check if AMReX tools are available.

        Returns
        -------
        bool
            True if required AMReX tools are found.
        """
        if self.tool_dir is None:
            return False

        # Check key tools exist (handles .gnu.ex, .intel.ex suffixes)
        required_tools = ['fvarnames.ex', 'fextrema.ex', 'fsnapshot.ex']
        return all(self._get_tool_path(tool) is not None for tool in required_tools)

    def get_field_list(self, plotfile: Path) -> list[str]:
        """
        Get variable list using fvarnames.

        Runs: fvarnames.ex plotfile

        Output format:
            0 density
            1 Temp
            2 x_velocity
            ...

        Parameters
        ----------
        plotfile : Path
            Path to the plotfile directory.

        Returns
        -------
        list of str
            Field names available in the plotfile.
        """
        tool_path = self._get_tool_path('fvarnames.ex')
        if tool_path is None:
            raise RuntimeError("fvarnames tool not found")

        cmd = [str(tool_path), str(plotfile)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse output: "0 density\n1 temperature\n..."
        fields = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    fields.append(parts[1])

        return fields

    def get_extrema(self, plotfile: Path, field: str) -> dict[str, float]:
        """
        Get min/max using fextrema.

        Runs: fextrema.ex -v <field> plotfile

        Output format (table):
            time  variable  min  max
            0.0   Temp      298.15  2500.0

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
        tool_path = self._get_tool_path('fextrema.ex')
        if tool_path is None:
            raise RuntimeError("fextrema tool not found")

        cmd = [
            str(tool_path),
            '-v', field,
            str(plotfile)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse output table
        # Format: time  variable  min  max
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if field in line:
                parts = line.split()
                return {
                    'min': float(parts[-2]),
                    'max': float(parts[-1])
                }

        # Default fallback
        return {'min': 0.0, 'max': 1.0}

    def create_slice_plot(self,
                         plotfile: Path,
                         field: str,
                         axis: str,
                         output_path: Path,
                         **kwargs) -> Path:
        """
        Create slice plot using fsnapshot.

        fsnapshot is AMReX's native 2D image generator.

        Runs: fsnapshot.ex -v <field> -p <palette> -m <vmin> -M <vmax> -n <direction> plotfile

        Options:
            -v: variable name
            -p: palette file (colormap)
            -m/-M: min/max scaling
            -L: max AMR level
            -n: slice direction (0=x, 1=y, 2=z, 3=all)

        Parameters
        ----------
        plotfile : Path
            Path to the plotfile directory.
        field : str
            Field name to plot.
        axis : str
            Axis for the slice ("x", "y", or "z").
        output_path : Path
            Output image file path.
        **kwargs : dict
            Optional rendering overrides (palette, vmin, vmax, max_level).

        Returns
        -------
        Path
            Path to the generated image.
        """
        # Map axis to fsnapshot direction
        axis_map = {'x': 0, 'y': 1, 'z': 2}
        direction = axis_map.get(axis.lower(), 2)

        # Get extrema for scaling (unless overridden)
        vmin = kwargs.get('vmin')
        vmax = kwargs.get('vmax')
        if vmin is None or vmax is None:
            extrema = self.get_extrema(plotfile, field)
            vmin = vmin or extrema['min']
            vmax = vmax or extrema['max']

        # Get palette file
        palette = kwargs.get('palette', str(self.tool_dir / 'Palette'))

        # Max AMR level
        max_level = kwargs.get('max_level', -1)  # -1 = all levels

        # Get tool path
        tool_path = self._get_tool_path('fsnapshot.ex')
        if tool_path is None:
            raise RuntimeError("fsnapshot tool not found")

        # Build command
        cmd = [
            str(tool_path),
            '-v', field,
            '-p', palette,
            '-m', str(vmin),
            '-M', str(vmax),
            '-n', str(direction),
        ]

        if max_level >= 0:
            cmd.extend(['-L', str(max_level)])

        cmd.append(str(plotfile))

        # Run fsnapshot (outputs to stdout or file depending on build)
        # Note: May need to redirect output or capture binary
        result = subprocess.run(cmd, cwd=output_path.parent, check=True,
                               capture_output=True)

        # fsnapshot typically outputs to "snapshot.ppm" or similar
        # May need to rename/convert
        snapshot_file = output_path.parent / 'snapshot.ppm'
        if snapshot_file.exists():
            snapshot_file.rename(output_path)
        else:
            # If no PPM file, check if fsnapshot wrote directly to stdout
            # and save it ourselves (this depends on fsnapshot build)
            if result.stdout:
                output_path.write_bytes(result.stdout)

        return output_path

    def extract_1d_slice(self,
                        plotfile: Path,
                        field: str,
                        direction: str,
                        coord: dict[str, float] | None = None,
                        output_file: Path | None = None) -> Path:
        """
        Extract 1D slice using fextract.

        Useful for profile plots.

        Runs: fextract.ex -s <output> -d <axis> -v <field> [-x/-y/-z <coord>] plotfile

        Options:
            -s: output file
            -d: direction (0=x, 1=y, 2=z)
            -v: variable name
            -x/-y/-z: coordinate for slice position

        Parameters
        ----------
        plotfile : Path
            Path to the plotfile directory.
        field : str
            Field name to slice.
        direction : str
            Slice axis ("x", "y", or "z").
        coord : dict or None, optional
            Coordinate overrides for the slice position.
        output_file : Path or None, optional
            Output file path for the slice data.

        Returns
        -------
        Path
            Path to output text file with extracted data.
        """
        if output_file is None:
            output_file = plotfile.parent / f'{plotfile.name}_{field}_slice.txt'

        # Map direction to fextract axis
        axis_map = {'x': 0, 'y': 1, 'z': 2}
        axis = axis_map.get(direction.lower(), 0)

        # Get tool path
        tool_path = self._get_tool_path('fextract.ex')
        if tool_path is None:
            raise RuntimeError("fextract tool not found")

        cmd = [
            str(tool_path),
            '-s', str(output_file),
            '-d', str(axis),
            '-v', field
        ]

        # Add coordinate if specified
        if coord:
            if 'x' in coord:
                cmd.extend(['-x', str(coord['x'])])
            if 'y' in coord:
                cmd.extend(['-y', str(coord['y'])])
            if 'z' in coord:
                cmd.extend(['-z', str(coord['z'])])

        cmd.append(str(plotfile))

        subprocess.run(cmd, check=True)

        return output_file
