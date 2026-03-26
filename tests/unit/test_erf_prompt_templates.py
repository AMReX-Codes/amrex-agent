from database.configs.base_amrex_config import BaseAMReXConfig
from database.configs.erf_config import ERFConfig


def test_erf_prompt_templates_override_inputs_select() -> None:
    base_prompt = BaseAMReXConfig.get_prompt_templates()["misc"]["inputs_select"]
    erf_prompt = ERFConfig.get_prompt_templates()["misc"]["inputs_select"]
    assert isinstance(erf_prompt, str)
    assert erf_prompt != base_prompt
    assert "ERF atmospheric case directory" in erf_prompt


def test_erf_prompt_templates_override_modification_extraction() -> None:
    base_prompt = BaseAMReXConfig.get_prompt_templates()["architect"]["modification_extraction"]
    erf_prompt = ERFConfig.get_prompt_templates()["architect"]["modification_extraction"]
    assert isinstance(erf_prompt, str)
    assert erf_prompt != base_prompt
    assert "stratification, forcing, terrain/ABL setup" in erf_prompt
