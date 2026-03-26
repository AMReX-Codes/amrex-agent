from pathlib import Path

from src.services.visualization import VisualizationService


class _FakeBackend:
    def available(self) -> bool:
        return True

    def get_field_list(self, plotfile: Path) -> list[str]:
        del plotfile
        return ["qc"]

    def create_slice_plot(
        self,
        plotfile: Path,
        field: str,
        axis: str,
        output_path: Path,
        **kwargs,
    ) -> Path:
        del plotfile, field, axis, kwargs
        output_path.write_text("fake image")
        return output_path


def _make_service(monkeypatch):
    monkeypatch.setattr(VisualizationService, "_select_backend", lambda self: _FakeBackend())
    config = type("Cfg", (), {"container_mode": False, "visualization_backend": "yt"})()
    return VisualizationService(config)


def test_create_standard_plots_latest_only(monkeypatch, tmp_path):
    service = _make_service(monkeypatch)
    run_dir = tmp_path / "run"
    (run_dir / "plt00001").mkdir(parents=True)
    (run_dir / "plt00002").mkdir(parents=True)

    images = service.create_standard_plots(
        run_dir=run_dir,
        vis_config={"plots": [{"type": "slice", "field": "qc", "axis": "y"}], "timesteps": "latest"},
    )

    assert len(images) == 1
    assert images[0].name == "qc_slice.png"


def test_create_standard_plots_all_timesteps(monkeypatch, tmp_path):
    service = _make_service(monkeypatch)
    run_dir = tmp_path / "run"
    (run_dir / "plt00001").mkdir(parents=True)
    (run_dir / "plt00002").mkdir(parents=True)

    images = service.create_standard_plots(
        run_dir=run_dir,
        vis_config={"plots": [{"type": "slice", "field": "qc", "axis": "y"}], "timesteps": "all"},
    )

    assert len(images) == 2
    names = sorted(image.name for image in images)
    assert names == ["plt00001_qc_slice.png", "plt00002_qc_slice.png"]
