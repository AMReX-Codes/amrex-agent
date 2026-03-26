# Instructor Usage Map

This table tracks where instructor-based structured LLM calls are used and
what prompt templates and fallbacks are in play.

| Location | Purpose | Prompt Template Source | Response Mode |
| --- | --- | --- | --- |
| `src/services/architect.py` | Solver selection, schema scan, plan fallback | `ArchitectService._resolve_llm_prompt_template(...)` and solver config templates | Instructor + raw fallback |
| `src/services/cases.py` | Case selection (`find_best_match`) | Solver config templates | Instructor + raw fallback |
| `src/services/inputs_file_selector.py` | `llm_compare` inputs selection | `config_cls.get_prompt_templates().get("misc")["inputs_select"]` or inline | Instructor + raw fallback |
| `src/services/knowledge.py` | `generate_questions_from_prompt` | Solver config `knowledge.question_generator` | Instructor + raw fallback |
| `src/services/config_model_factory.py` | Remap failed modifications | Solver config `remap.template` or BaseAMReXConfig | Instructor only (exceptions caught) |
| `src/nodes/reviewer_node.py` | Retry guidance refinement | Solver config `misc.retry_guidance` | Instructor + raw JSON fallback |
| `src/nodes/analysis_node.py` | Retry guidance refinement | BaseAMReXConfig `misc.retry_guidance` | Instructor + raw JSON fallback |
| `src/services/config_service.py` | LLM connectivity check | `misc_prompts` or inline default | Raw only |
