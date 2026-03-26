"""Inputs file selection strategies using git and file metadata."""

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class InputsFileSelector:
    """Select inputs files using different strategies."""

    @staticmethod
    def score_by_age(file_path: Path) -> float:
        """
        Score by git age (oldest = most mature).

        Returns 0.0-1.0 where 1.0 = very old (5+ years)

        Parameters
        ----------
        file_path : Path
            Inputs file path to score.

        Returns
        -------
        float
            Age-based score in the range [0.0, 1.0].
        """
        try:
            result = subprocess.run(
                ['git', 'log', '--format=%ct', '--', file_path.name],
                cwd=file_path.parent,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                timestamps = [int(t) for t in result.stdout.strip().split('\n') if t]
                if timestamps:
                    import time
                    oldest_timestamp = min(timestamps)
                    age_years = (time.time() - oldest_timestamp) / (365.25 * 24 * 60 * 60)

                    # Normalize: 5+ years = 1.0
                    return min(1.0, age_years / 5.0)

        except Exception as e:
            logger.debug(f"Could not score age for {file_path}: {e}")

        return 0.5

    @staticmethod
    def score_by_recency(file_path: Path) -> float:
        """
        Score by git recency (newest = most up-to-date).

        Returns 0.0-1.0 where 1.0 = very recent (< 1 month)

        Parameters
        ----------
        file_path : Path
            Inputs file path to score.

        Returns
        -------
        float
            Recency-based score in the range [0.0, 1.0].
        """
        try:
            result = subprocess.run(
                ['git', 'log', '--format=%ct', '-1', '--', file_path.name],
                cwd=file_path.parent,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                import time
                last_modified = int(result.stdout.strip())
                age_days = (time.time() - last_modified) / (24 * 60 * 60)

                # Normalize: < 30 days = 1.0, > 365 days = 0.0
                if age_days < 30:
                    return 1.0
                elif age_days > 365:
                    return 0.0
                else:
                    return 1.0 - ((age_days - 30) / 335)

        except Exception as e:
            logger.debug(f"Could not score recency for {file_path}: {e}")

        return 0.5

    @staticmethod
    def score_by_size(file_path: Path) -> float:
        """
        Score by file size (smaller = simpler = better baseline).

        Returns 0.0-1.0 where 1.0 = very small (<5KB)

        Parameters
        ----------
        file_path : Path
            Inputs file path to score.

        Returns
        -------
        float
            Size-based score in the range [0.0, 1.0].
        """
        try:
            size_kb = file_path.stat().st_size / 1024

            # Normalize: <5KB = 1.0, >20KB = 0.0
            if size_kb < 5:
                return 1.0
            elif size_kb > 20:
                return 0.0
            else:
                return 1.0 - ((size_kb - 5) / 15)

        except Exception as e:
            logger.debug(f"Could not score size for {file_path}: {e}")

        return 0.5

    @classmethod
    def select_best_inputs_file(
        cls,
        case_dir: Path,
        strategy: str = "smallest",
        excluded_files: list[str] = None,
        available_files: list[Path] = None,
        config: Any | None = None,
        user_prompt: str | None = None,
    ) -> Path | None:
        """
        Select best inputs file from case directory.

        Parameters
        ----------
        case_dir : Path
            Case directory path.
        strategy : str, optional
            "oldest", "newest", "smallest", "llm_compare", or "override".
        excluded_files : list of str, optional
            Filenames to skip.
        available_files : list of Path, optional
            Pre-filtered candidate files.
        config : object, optional
            Config object (required for llm_compare).

        Returns
        -------
        Path or None
            Selected inputs file path, or None if not found.
        """
        excluded_files = excluded_files or []
        original_strategy = strategy
        fallback_reason = None

        # Find candidate files (use provided or discover)
        if available_files:
            candidates = available_files
        else:
            # Use config-based patterns
            from database.configs import get_config_for_path
            config_cls = get_config_for_path(str(case_dir))
            candidates = config_cls.find_inputs_files(case_dir)

        # Filter
        candidates = [
            f for f in candidates
            if f.exists()
            and not f.name.endswith(('.bak', '~', '.old'))
            and f.name not in excluded_files
        ]

        if not candidates:
            return None

        if strategy == "override":
            selected = cls._select_override(case_dir, config)
            if selected:
                logger.info(f"Selected inputs file: {selected.name} (strategy: override)")
                _record_inputs_selection(
                    strategy="override",
                    original_strategy=original_strategy,
                    selected=selected,
                    candidates=candidates,
                )
                return selected
            # Fallback to smallest if override didn't resolve
            fallback_reason = "override_unresolved"
            strategy = "smallest"

        if strategy == "llm_compare":
            selected = cls._select_with_llm(
                case_dir,
                candidates,
                config=config,
                user_prompt=user_prompt,
            )
            if selected:
                logger.info(f"Selected inputs file: {selected.name} (strategy: llm_compare)")
                _record_inputs_selection(
                    strategy="llm_compare",
                    original_strategy=original_strategy,
                    selected=selected,
                    candidates=candidates,
                )
                return selected
            # LLM unavailable or failed → fallback to smallest
            fallback_reason = "llm_unavailable"
            strategy = "smallest"

        # Score by strategy
        scoring_func = {
            'oldest': cls.score_by_age,
            'newest': cls.score_by_recency,
            'smallest': cls.score_by_size
        }.get(strategy, cls.score_by_size)

        scored = [(scoring_func(f), f) for f in candidates]
        scored.sort(reverse=True, key=lambda x: x[0])

        selected = scored[0][1]
        logger.info(f"Selected inputs file: {selected.name} (strategy: {strategy}, score: {scored[0][0]:.2f})")
        _record_inputs_selection(
            strategy=strategy,
            original_strategy=original_strategy,
            selected=selected,
            candidates=candidates,
            fallback_reason=fallback_reason,
            score=scored[0][0],
        )

        return selected

    @staticmethod
    def _build_inputs_summary(file_path: Path, max_lines: int = 40) -> str:
        try:
            lines = file_path.read_text().splitlines()
        except Exception:
            return f"{file_path.name}: <unreadable>"
        header = "\n".join(lines[:max_lines])
        return f"FILE: {file_path.name}\n{header}"

    @classmethod
    def _select_with_llm(
        cls,
        case_dir: Path,
        candidates: list[Path],
        config: Any | None = None,
        user_prompt: str | None = None,
    ) -> Path | None:
        if not config:
            logger.debug("LLM compare requested but no config provided")
            return None
        try:
            from src.config import get_llm_client
            client = get_llm_client(config)
        except Exception as exc:
            logger.debug(f"LLM compare unavailable: {exc}")
            return None

        summaries = [cls._build_inputs_summary(p) for p in candidates]
        case_hint = case_dir.name
        prompt = None
        try:
            from database.configs import get_config_for_path
            config_cls = get_config_for_path(str(case_dir))
            prompt = config_cls.get_prompt_templates().get("misc", {}).get("inputs_select")
        except Exception:
            prompt = None
        if not prompt:
            prompt = (
                "You are selecting the best inputs file for an AMReX case.\n"
                "Case directory: {case_name}\n\n"
                "Requested simulation prompt: {user_prompt}\n\n"
                "Choose the file that most closely matches the case based on file name and header.\n"
                "Prefer case-named .inp files over generic inputs.* when both are available.\n"
                "Return ONLY the filename from the list below.\n\n"
                "{candidates}\n"
            )
        prompt = prompt.format(
            case_name=case_hint,
            user_prompt=(user_prompt or "").strip(),
            candidates="\n\n".join(summaries),
        )

        try:
            from pydantic import BaseModel, Field
            from src.utils.llm_calls import LLMCallSpec, call_llm

            class InputsSelection(BaseModel):
                filename: str = Field(description="Selected inputs filename")

            spec = LLMCallSpec(
                model=config.llm_model,
                response_model=InputsSelection,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_retries=2,
                purpose="inputs_file_selection",
                template_name="inputs_select",
                template_source="solver_config.misc",
            )
            result = call_llm(client, spec, config=config)
            if hasattr(result, "filename"):
                content = result.filename.strip()
            else:
                content = result.choices[0].message.content.strip()
        except Exception as exc:
            logger.debug(f"LLM compare failed: {exc}")
            return None

        names = {p.name: p for p in candidates}
        for name in names:
            if name in content:
                return names[name]

        logger.debug(f"LLM compare returned no match: {content}")
        return None

    @staticmethod
    def _select_override(case_dir: Path, config: Any | None) -> Path | None:
        if not config:
            return None
        override = getattr(config, "inputs_file_override", None)
        if override:
            override_path = Path(override)
            if not override_path.is_absolute():
                override_path = case_dir / override
            if override_path.exists():
                return override_path
        default_path = case_dir / "inputs"
        if default_path.exists():
            return default_path
        return None


def _record_inputs_selection(
    *,
    strategy: str,
    original_strategy: str,
    selected: Path,
    candidates: list[Path],
    fallback_reason: str | None = None,
    score: float | None = None,
) -> None:
    try:
        from src.utils.metrics import metrics_collector

        metrics_collector.record_event(
            "retrieval_strategy",
            {
                "strategy": strategy,
                "original_strategy": original_strategy,
                "fallback_reason": fallback_reason,
                "selected": selected.name,
                "candidate_count": len(candidates),
                "score": score,
            },
        )
    except Exception:
        return
