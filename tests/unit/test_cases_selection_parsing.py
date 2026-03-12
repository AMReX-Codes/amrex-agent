from __future__ import annotations

from src.config import AMReXAgentConfig
from src.services.cases import AMReXCasesService


def _service() -> AMReXCasesService:
    return AMReXCasesService(AMReXAgentConfig())


def test_parse_case_selection_content_fenced_json() -> None:
    svc = _service()
    content = '```json\n{"code":"ERF","case":"Exec/CanonicalFlows/SquallLine_2D"}\n```'
    code, case = svc._parse_case_selection_content(content)
    assert code == "ERF"
    assert case == "Exec/CanonicalFlows/SquallLine_2D"


def test_parse_case_selection_content_case_insensitive_labels() -> None:
    svc = _service()
    content = "Code = ERF\nCase: Exec/CanonicalFlows/SquallLine_2D"
    code, case = svc._parse_case_selection_content(content)
    assert code == "ERF"
    assert case == "Exec/CanonicalFlows/SquallLine_2D"


def test_parse_case_selection_content_inline_json_with_extra_text() -> None:
    svc = _service()
    content = 'Answer: {"code":"ERF","case":"Exec/ABL"}'
    code, case = svc._parse_case_selection_content(content)
    assert code == "ERF"
    assert case == "Exec/ABL"


def test_merge_prompt_hinted_codes_adds_erf_when_quality_filter_excludes_it(monkeypatch) -> None:
    svc = _service()
    filtered = {"PeleC": ["Exec/RegTests/ChannelFlow"]}
    full = {
        "PeleC": ["Exec/RegTests/ChannelFlow"],
        "ERF": ["Exec/CanonicalFlows/SquallLine_2D"],
    }

    def fake_list_all_cases(*, quality_filter=None):
        return filtered if quality_filter else full

    monkeypatch.setattr(svc, "list_all_cases", fake_list_all_cases)
    merged = svc._merge_prompt_hinted_codes("Run a 2D squall line simulation", filtered)
    assert "ERF" in merged
