"""
Unit tests for Level2Searcher.
"""

from pathlib import Path

from database.indexing.level2_searcher import Level2Searcher


def test_compute_weighted_score():
    searcher = Level2Searcher("AMReX", Path("."), embedder=None)
    scores = {
        "physics_parameters": 0.5,
        "grid_specifications": 0.25,
    }
    expected = 0.5 * searcher.WEIGHTS["physics_parameters"]
    expected += 0.25 * searcher.WEIGHTS["grid_specifications"]
    assert searcher._compute_weighted_score(scores) == expected


def test_combine_scores_keeps_best_per_index():
    searcher = Level2Searcher("AMReX", Path("."), embedder=None)
    index_results = {
        "physics_parameters": [
            {"case": "Exec/CaseA", "score": 0.2, "metadata": {"repo_path": "Exec/CaseA"}},
            {"case": "Exec/CaseA", "score": 0.6, "metadata": {"repo_path": "Exec/CaseA"}},
        ],
        "grid_specifications": [
            {"case": "Exec/CaseA", "score": 0.4, "metadata": {"repo_path": "Exec/CaseA"}},
        ],
    }

    combined = searcher._combine_scores(index_results)
    assert combined["Exec/CaseA"]["breakdown"]["physics_parameters"] == 0.6
    assert combined["Exec/CaseA"]["breakdown"]["grid_specifications"] == 0.4


def test_search_all_cases_filters_submodules(monkeypatch, tmp_path):
    searcher = Level2Searcher("AMReX", tmp_path, embedder=None)
    searcher.available_indices = {
        "physics_parameters": tmp_path / "amrex_case_physics_parameters.faiss",
        "grid_specifications": tmp_path / "amrex_case_grid_specifications.faiss",
    }

    def fake_search(index_type, _query, top_k=10):
        if index_type == "physics_parameters":
            return [
                {"case": "Submodules/CaseX", "score": 0.9, "metadata": {"repo_path": "Submodules/CaseX"}},
                {"case": "Exec/CaseY", "score": 0.5, "metadata": {"repo_path": "Exec/CaseY"}},
            ]
        return [
            {"case": "Exec/CaseY", "score": 0.2, "metadata": {"repo_path": "Exec/CaseY"}},
        ]

    monkeypatch.setattr(searcher, "_search_index", fake_search)

    results = searcher.search_all_cases("query", top_k=2)

    assert len(results) == 1
    assert results[0]["case"] == "Exec/CaseY"
