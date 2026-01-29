"""
Input Writer: Inputs File Writer: Inputs File Writer.

Ghostwriter pattern: Preserve formatting while modifying values.
Pure serialization - no I/O, no side effects.

Architecture:
  Input: Pydantic model (from Input Writer: Config Model Factory) + optional original text
  Output: AMReX inputs file text

Responsibilities:
  ✅ Serialize Pydantic model to inputs format
  ✅ Preserve comments and formatting
  ✅ Handle array values (list → "64 64 64")
  ✅ Maintain parameter ordering

Not Responsible For:
  ❌ File I/O (no Path.write_text)
  ❌ Auxiliary files (probin, chemistry)
  ❌ Directory management
  ❌ Service orchestration
"""

import logging
import re
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class InputsFileWriter:
    """
    Stateless serializer for AMReX inputs files.

    Implements the "Ghostwriter" pattern from Amendment C:
    - Preserves user formatting and comments
    - Modifies only the values
    - Appends new parameters at end
    """

    @staticmethod
    def serialize(
        model: BaseModel,
        original_text: str = "",
        modified_keys: set[str] | None = None
    ) -> str:
        """
        Serialize Pydantic model to AMReX inputs format.

        Parameters
        ----------
        model : BaseModel
            Hydrated config model (from ConfigModelFactory).
        original_text : str, optional
            Original inputs file (for Ghostwriter mode).
        modified_keys : set of str or None, optional
            Keys that were modified during planning.

        Returns
        -------
        str
            AMReX inputs file text.
        """
        # Get model data with AMReX parameter names (aliases)
        data = model.model_dump(by_alias=True, exclude_defaults=True, exclude_none=True)
        sample_keys = list(data.keys())[:10]
        logger.info(f"[DEBUG] Sample model keys: {sample_keys}")
        logger.info(f"[DEBUG] Total keys in model: {len(data)}")
        if not original_text:
            # Scratch generation - no Ghostwriter
            return InputsFileWriter._generate_clean(data)

        # Ghostwriter mode - preserve formatting
        return InputsFileWriter._ghostwrite(data, original_text, modified_keys=modified_keys)

    @staticmethod
    def _generate_clean(data: dict[str, Any]) -> str:
        """
        Generate clean inputs file from scratch.

        Used when no original_text provided.
        """
        lines = []
        for key, value in data.items():
            formatted_value = InputsFileWriter._format_value(value)
            lines.append(f"{key} = {formatted_value}")

        return "\n".join(lines)

    @staticmethod
    def _ghostwrite(
        data: dict[str, Any],
        original_text: str,
        modified_keys: set[str] | None = None
    ) -> str:
        """
        Preserve original formatting while updating values.

        Ghostwriter algorithm:
        1. Parse each line of original
        2. If line has a parameter in data, update value
        3. Preserve exact spacing and comments
        4. Track which parameters we've seen
        5. Append unseen parameters at end
        """
        lines = original_text.split('\n')
        output = []
        seen_keys = set()

        # Regex to capture components with exact spacing
        # Matches: "  key  =  value  # comment"
        # Group 1: prefix (before =, including key and spaces)
        # Group 2: spacing between = and value
        # Group 3: value itself
        # Group 4: spacing after value
        # Group 5: comment (if present)
        param_pattern = re.compile(r'^([^#=]+?)\s*=\s*([^#\s]+(?:\s+[^#\s]+)*)(\s*)(#.*)?$')

        for line in lines:
            match = param_pattern.match(line)

            if match:
                # Line contains a parameter
                prefix = match.group(1)  # "amr.n_cell" or "solver.cfl     "
                trailing_space = match.group(3) or ""  # "  " or ""
                comment = match.group(4) or ""  # "# comment" or ""

                key = prefix.strip()

                if key in data and (modified_keys is None or key in modified_keys):
                    # Update value, preserve exact spacing and comment
                    new_value = InputsFileWriter._format_value(data[key])

                    # Reconstruct with exact spacing
                    # Find original spacing after prefix
                    original_line = line
                    equals_idx = original_line.find('=')
                    prefix_with_spaces = original_line[:equals_idx]

                    # Preserve spacing between = and value
                    value_start = equals_idx + 1
                    while value_start < len(original_line) and original_line[value_start] == ' ':
                        value_start += 1
                    spaces_after_equals = ' ' * (value_start - equals_idx - 1)

                    # Reconstruct line
                    output.append(f"{prefix_with_spaces}={spaces_after_equals}{new_value}{trailing_space}{comment}")
                    seen_keys.add(key)
                else:
                    # Parameter not in model - preserve as-is
                    output.append(line)
            else:
                # Not a parameter line (comment, blank, etc.) - preserve
                output.append(line)

        # Append new parameters not in original
        for key, value in data.items():
            if key not in seen_keys and (modified_keys is None or key in modified_keys):
                formatted_value = InputsFileWriter._format_value(value)
                output.append(f"{key} = {formatted_value}")

        logger.info(f"[DEBUG] Seen {len(seen_keys)} keys in original")
        logger.info(f"[DEBUG] Sample seen keys: {list(seen_keys)[:10]}")

        return '\n'.join(output)

    @staticmethod
    def _format_value(value: Any) -> str:
        """
        Format a value for AMReX inputs file.

        Args:
            value: Python value (int, float, str, list, etc.)

        Returns
        -------
            AMReX-formatted string

        Examples
        --------
            64 → "64"
            0.5 → "0.5"
            [64, 64, 64] → "64 64 64"
            True → "true"
        """
        if isinstance(value, list):
            # Array: join with spaces
            return " ".join(str(v) for v in value)
        elif isinstance(value, bool):
            # Boolean: lowercase
            return str(value).lower()
        else:
            # Scalar: direct conversion
            return str(value)
