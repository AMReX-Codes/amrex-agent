"""Knowledge base service for AMReX solvers."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add project root to path for optional knowledge backends.
AMREX_AGENT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(AMREX_AGENT_ROOT))

logger = logging.getLogger(__name__)

logger.debug(f"[DEBUG] knowledge.py location: {Path(__file__).resolve()}")
logger.debug(f"[DEBUG] AMREX_AGENT_ROOT: {AMREX_AGENT_ROOT.resolve()}")
logger.debug(f"[DEBUG] sys.path[0]: {sys.path[0]}")


class PeleKnowledgeService:
    """Knowledge base service.

    RAG system with FAISS.
    Future: Will use CBORG embeddings (lbl/nomic-embed-text) for enhanced RAG.

    Example:
        >>> kb = PeleKnowledgeService(config)
        >>> answer = kb.query("What CFL number should I use?")
        >>> print(answer['answer'])
    """

    def __init__(self, config):
        self.config = config
        self.knowledge_loaded = False
        self.default_solver_config = self._resolve_solver_config()
        self.knowledge_tools = self._get_knowledge_tools(self.default_solver_config)
        if not self.knowledge_tools:
            solver_name = getattr(self.default_solver_config, "code_name", "unknown")
            logger.debug("Knowledge tools not available for solver %s", solver_name)

        # Initialize FAISS embedding service for enhanced RAG (hybrid approach)
        from .embedding_service_factory import get_embedding_service

        self.embeddings = get_embedding_service(config)

        if self.embeddings.embeddings:
            logger.debug(" [OK] FAISS embeddings initialized for knowledge service")
        else:
            logger.debug("[WARN] FAISS embeddings not available")
            logger.debug("       Will use knowledge backend only")

        # Load knowledge base if available
        try:
            self._load_knowledge()
            self.knowledge_loaded = True
        except Exception as e:
            logger.debug(f"[WARN] Could not load knowledge base: {e}")
            logger.debug("       Knowledge queries may fail")

    def _load_knowledge(self):
        """Load knowledge base."""
        kb_path = self.config.knowledge_base_path
        logger.debug(f" Knowledge base path: {kb_path.resolve()}")
        logger.debug(f" Knowledge base exists: {kb_path.exists()}")

        if not kb_path.exists():
            logger.debug(f"[WARN] Knowledge base not found at {kb_path}")
            return

        tools = self.knowledge_tools
        if not tools or not tools.get("load"):
            logger.debug("[WARN] Knowledge tools missing load hook")
            return

        try:
            self._invoke_tool(tools["load"], {})
            logger.debug(f" [OK] Knowledge base loaded from {kb_path}")
        except Exception as e:
            logger.debug(f"[WARN] knowledge load failed: {e}")

    def query(self, question: str, context: dict | None = None) -> dict:
        """
        Query knowledge base with hybrid FAISS + LLM approach.

        Call context: Used by Architect to answer domain-specific questions.

        Parameters
        ----------
        question : str
            Natural language question.
        context : dict or None, optional
            Optional context to include in query.

        Returns
        -------
        dict
            Answer payload with sources and confidence.
        """
        # Try FAISS first if available
        faiss_result = None
        if self.embeddings and self.embeddings.indices_available() and self.config.faiss_fallback_to_llm:
            faiss_result = self._query_faiss(question, context)

            # If FAISS has high confidence, return it directly
            if faiss_result and faiss_result.get('confidence', 0) > 0.8:
                logger.debug(f" Using FAISS result (confidence: {faiss_result['confidence']:.2f})")
                _record_retrieval_metrics(
                    strategy="faiss",
                    confidence=faiss_result.get("confidence", 0.0),
                    source=faiss_result.get("source"),
                )
                return faiss_result

        tools, solver_config = self._get_tools_for_context(context)
        if not tools or not tools.get("ask"):
            solver_name = getattr(solver_config, "code_name", "unknown")
            if faiss_result:
                _record_retrieval_metrics(
                    strategy="faiss",
                    confidence=faiss_result.get("confidence", 0.0),
                    source=faiss_result.get("source"),
                )
                return faiss_result
            return {
                "answer": f"Knowledge tools not available for solver {solver_name}",
                "sources": [],
                "confidence": 0.0,
                "error": "missing_knowledge_tools",
            }

        # Fall back to solver-configured knowledge tools
        if not self.knowledge_loaded:
            if faiss_result:
                # Return FAISS result even if low confidence
                _record_retrieval_metrics(
                    strategy="faiss",
                    confidence=faiss_result.get("confidence", 0.0),
                    source=faiss_result.get("source"),
                )
                return faiss_result
            return {
                "answer": "Knowledge base not loaded",
                "sources": [],
                "confidence": 0.0
            }

        try:
            # Build enhanced question with context
            if context:
                enhanced_q = f"Context: {json.dumps(context)}\n\nQuestion: {question}"
            else:
                enhanced_q = question

            result = self._invoke_tool(tools["ask"], {"question": enhanced_q})

            # Parse result (format depends on knowledge backend implementation)
            if isinstance(result, dict):
                llm_result = {
                    "answer": result.get("answer", result.get("output", str(result))),
                    "sources": result.get("sources", []),
                    "confidence": result.get("confidence", 0.8),
                    "method": "llm"
                }
            else:
                llm_result = {
                    "answer": str(result),
                    "sources": [],
                    "confidence": 0.8,
                    "method": "llm"
                }

            # Combine FAISS and LLM results if both available
            if faiss_result:
                _record_retrieval_metrics(
                    strategy="hybrid",
                    confidence=llm_result.get("confidence", 0.0),
                    source=llm_result.get("method"),
                    faiss_confidence=faiss_result.get("confidence", 0.0),
                )
                return self._combine_results(faiss_result, llm_result)

            _record_retrieval_metrics(
                strategy="llm",
                confidence=llm_result.get("confidence", 0.0),
                source=llm_result.get("method"),
            )
            return llm_result

        except Exception as e:
            logger.error(f"[ERROR] LLM knowledge query failed: {e}")

            # Return FAISS result if available as fallback
            if faiss_result:
                logger.debug(" Using FAISS result as fallback after LLM failure")
                _record_retrieval_metrics(
                    strategy="faiss_fallback",
                    confidence=faiss_result.get("confidence", 0.0),
                    source=faiss_result.get("source"),
                )
                return faiss_result

            return {
                "answer": f"Error: {e}",
                "sources": [],
                "confidence": 0.0
            }

    def query_multiple(self, questions: list[str], context: dict | None = None) -> dict[str, dict]:
        """
        Query multiple questions at once.

        Call context: Used by Architect to batch knowledge queries.

        Parameters
        ----------
        questions : list of str
            Questions to query.
        context : dict or None, optional
            Optional context to include in each query.

        Returns
        -------
        dict
            Mapping from question to answer payload.
        """
        return {q: self.query(q, context) for q in questions}

    def _query_faiss(self, question: str, context: dict | None = None) -> dict | None:
        """
        Query FAISS indices for relevant documentation.

        Tries case_details index first, then chemistry index if relevant.

        Args:
            question: Natural language question (should be clean semantic query)
            context: Optional context (e.g., code name, fuel type, cases list)

        Returns
        -------
            Dict with answer, sources, confidence, or None if no results
        """
        if not self.embeddings:
            return None

        # Determine which code to query
        code_name = context['code'] if context and 'code' in context else self.config.default_solver
        if not code_name:
            raise ValueError("No solver provided for knowledge query")
        code_lower = code_name.lower()

        # Try case_details index first (most comprehensive)
        details_index = f"{code_lower}_case_details"
        chemistry_index = f"{code_lower}_chemistry"

        # Determine topk based on whether we're scoring cases or answering questions
        case_list = context.get('cases', []) if context else []
        topk = min(len(case_list), 50) if case_list else 5

        results = []

        # Query case details
        try:
            details_results = self.embeddings.retrieve_faiss(
                details_index,
                question,  # Now a clean semantic query
                topk=topk
            )
            results.extend(details_results.get('results', []))
            logger.debug(f"[DEBUG] FAISS retrieved {len(details_results.get('results', []))} case_details results")
        except Exception as e:
            logger.debug(f"[DEBUG] FAISS case_details query failed: {e}")

        # Query chemistry if question mentions fuels/mechanisms
        question_lower = question.lower()
        if any(keyword in question_lower for keyword in ['fuel', 'mechanism', 'chemistry', 'methane', 'hydrogen']):
            try:
                chem_results = self.embeddings.retrieve_faiss(
                    chemistry_index,
                    question,
                    topk=min(topk, 5)
                )
                results.extend(chem_results.get('results', []))
                logger.debug(f"[DEBUG] FAISS retrieved {len(chem_results.get('results', []))} chemistry results")
            except Exception as e:
                logger.debug(f"[DEBUG] FAISS chemistry query failed: {e}")

        if not results:
            return None

        # === FORMAT FOR CASE SCORING ===
        # Return raw sources with scores for batch scoring
        sources = []
        for result in results:
            metadata = result.get('metadata', {})

            # Get case path from metadata
            case_path = metadata.get('case', metadata.get('case_name', 'Unknown'))

            source_info = {
                'case': case_path,
                'score': result.get('score', float('inf')),
                'metadata': metadata,
                'content': result.get('content', '')
            }
            sources.append(source_info)

        # Calculate confidence based on top score
        top_score = results[0].get('score', float('inf'))
        # Convert distance to confidence (lower distance = higher confidence)
        import math
        confidence = math.exp(-top_score) if top_score != float('inf') else 0.0

        # Also format answer for non-scoring queries
        answer_parts = []
        for i, result in enumerate(results[:3]):  # Top 3 for answer
            content = result.get('content', '')
            metadata = result.get('metadata', {})
            case_name = metadata.get('case_name', 'Unknown')

            snippet = content[:200] + "..." if len(content) > 200 else content
            answer_parts.append(f"[{i+1}] {case_name}: {snippet}")

        answer = "\n\n".join(answer_parts)

        return {
            'answer': answer,
            'sources': sources,  # Raw sources with scores
            'confidence': confidence,
            'method': 'faiss'
        }

    def _combine_results(self, faiss_result: dict, llm_result: dict) -> dict:
        """
        Combine FAISS and LLM results intelligently.

        Strategy:
        - If confidence differs significantly, use higher confidence result
        - Otherwise, combine answers with FAISS as context for LLM

        Args:
            faiss_result: Result from FAISS query
            llm_result: Result from LLM query

        Returns
        -------
            Combined result dict
        """
        faiss_conf = faiss_result.get('confidence', 0.0)
        llm_conf = llm_result.get('confidence', 0.0)

        # [DEBUG]: Show what FAISS and LLM actually returned
        logger.debug("\n[SCAN] FAISS RESULT:")
        logger.debug(f"  Confidence: {faiss_conf:.2f}")
        if 'results' in faiss_result:
            logger.debug("  Top results:")
            for i, res in enumerate(faiss_result['results'][:5], 1):
                score = res.get('score', 0.0)
                case = res.get('case_name', 'N/A')
                logger.debug(f"    {i}. {score:.3f} - {case}")

        logger.debug("\n[SCAN] LLM RESULT:")
        logger.debug(f"  Confidence: {llm_conf:.2f}")
        if 'results' in llm_result:
            logger.debug("  Top results:")
            for i, res in enumerate(llm_result['results'][:5], 1):
                score = res.get('score', 0.0)
                case = res.get('case_name', 'N/A')
                logger.debug(f"    {i}. {score:.3f} - {case}")

        # If one is significantly better, use it
        if faiss_conf > llm_conf + 0.2:
            logger.debug(f" Using FAISS result (conf: {faiss_conf:.2f} vs LLM: {llm_conf:.2f})")
            return faiss_result
        elif llm_conf > faiss_conf + 0.5:
            logger.debug(f" Using LLM result (conf: {llm_conf:.2f} vs FAISS: {faiss_conf:.2f})")
            return llm_result

        # Otherwise, combine (FAISS provides context, LLM provides reasoning)
        combined_answer = f"""Based on case database:
{faiss_result.get('answer', '')}

LLM analysis:
{llm_result.get('answer', '')}"""

        combined_sources = self._dedupe_sources(
            faiss_result.get('sources', []) + llm_result.get('sources', [])
        )

        # Average confidence
        combined_conf = (faiss_conf + llm_conf) / 2

        return {
            'answer': combined_answer,
            'sources': combined_sources,
            'confidence': combined_conf,
            'method': 'hybrid'
        }

    @staticmethod
    def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate sources while preserving original ordering."""
        seen = set()
        deduped = []
        for source in sources:
            if not isinstance(source, dict):
                deduped.append(source)
                continue
            key = None
            for field in ("case", "source"):
                value = source.get(field)
                if value:
                    key = (field, value)
                    break
            if key is None:
                metadata = source.get("metadata") or {}
                for field in ("repo_path", "case", "case_name"):
                    value = metadata.get(field)
                    if value:
                        key = ("metadata", value)
                        break
            if key is None:
                deduped.append(source)
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return deduped

    def generate_questions_from_prompt(self, user_prompt: str, llm_client: Any) -> list[str]:
        """
        Use LLM to generate relevant questions from user prompt.

        Call context: Used by Architect to seed knowledge base queries.

        Parameters
        ----------
        user_prompt : str
            User's simulation description.
        llm_client : object
            OpenAI client from get_llm_client().

        Returns
        -------
        list of str
            Questions to ask the knowledge base.
        """
        prompt_template = self._get_knowledge_prompt_template("question_generator")
        if not prompt_template:
            logger.warning("[WARN] Missing knowledge question_generator prompt template")
            return self._get_knowledge_fallback_questions()
        prompt = prompt_template.format(user_prompt=user_prompt)

        try:
            from pydantic import BaseModel, Field
            from src.utils.llm_calls import LLMCallSpec, call_llm

            class QuestionList(BaseModel):
                questions: list[str] = Field(description="List of short questions")

            spec = LLMCallSpec(
                model=self.config.llm_model,
                response_model=QuestionList,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_retries=2,
                purpose="knowledge_question_generation",
                template_name="question_generator",
                template_source="solver_config.knowledge",
            )
            result = call_llm(llm_client, spec, config=self.config)
            if hasattr(result, "questions"):
                return result.questions
            response = result
            content = response.choices[0].message.content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            questions = json.loads(content)

            if isinstance(questions, list):
                return questions
            logger.warning(f"[WARN] LLM returned non-list: {questions}")
            return []
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate questions: {e}")
            return self._get_knowledge_fallback_questions()

    def _resolve_solver_config(self, solver_name: str | None = None):
        from database.configs import BaseAMReXConfig, discover_code_configs

        registry = {cfg.code_name: cfg for cfg in discover_code_configs()}
        if solver_name:
            return registry.get(solver_name, BaseAMReXConfig)
        return registry.get(self.config.default_solver, BaseAMReXConfig)

    def _get_knowledge_prompt_templates(self, solver_name: str | None = None) -> dict[str, Any]:
        solver_config = self._resolve_solver_config(solver_name)
        if solver_config and hasattr(solver_config, "get_prompt_templates"):
            templates = solver_config.get_prompt_templates()
            knowledge = templates.get("knowledge", {})
            if isinstance(knowledge, dict):
                return knowledge
        return {}

    def _get_knowledge_prompt_template(self, key: str, solver_name: str | None = None) -> str | None:
        templates = self._get_knowledge_prompt_templates(solver_name)
        return templates.get(key)

    def _get_knowledge_fallback_questions(self, solver_name: str | None = None) -> list[str]:
        templates = self._get_knowledge_prompt_templates(solver_name)
        fallback = templates.get("fallback_questions", [])
        if isinstance(fallback, list) and fallback:
            return fallback
        return [
            "What are recommended simulation parameters?",
            "What grid settings should I use?",
            "What boundary conditions are common?",
        ]

    def _get_knowledge_tools(self, solver_config) -> dict[str, Any] | None:
        if solver_config and hasattr(solver_config, "get_knowledge_tools"):
            return solver_config.get_knowledge_tools()
        return None

    def _get_tools_for_context(self, context: dict | None):
        solver_name = context.get("code") if context else None
        solver_config = self._resolve_solver_config(solver_name)
        return self._get_knowledge_tools(solver_config), solver_config

    @staticmethod
    def _invoke_tool(tool, payload: dict[str, Any]):
        if hasattr(tool, "invoke"):
            return tool.invoke(payload)
        return tool(**payload)

    def build_cborg_embeddings_rag(self, documents: list[str]) -> None:
        """
        Future feature: Build RAG with CBORG embeddings.

        Will use lbl/nomic-embed-text from CBORG:
        - Max Tokens: 8192
        - Embedding Dimensions: 768
        - Free to use

        This will replace the current knowledge base with a more powerful
        embedding-based retrieval system.

        Call context: Placeholder for future embedding-index build workflow.

        Parameters
        ----------
        documents : list of str
            Documents to embed and index.

        Returns
        -------
        None
            Placeholder; implementation pending.
        """
        # TODO: Implement CBORG embeddings RAG
        # See: https://api.cborg.lbl.gov/models for lbl/nomic-embed-text
        pass


def _record_retrieval_metrics(
    *,
    strategy: str,
    confidence: float | None = None,
    source: str | None = None,
    faiss_confidence: float | None = None,
) -> None:
    try:
        from src.utils.metrics import metrics_collector

        metrics_collector.record_event(
            "retrieval_strategy",
            {
                "strategy": strategy,
                "confidence": confidence,
                "faiss_confidence": faiss_confidence,
                "source": source,
            },
        )
    except Exception:
        return


# Test the service
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_llm_client, load_config

    logger.debug("\n=== Testing Knowledge Service ===\n")

    config = load_config()

    try:
        kb = PeleKnowledgeService(config)

        # Test 1: Direct query
        logger.debug("\n[Test 1] Direct query:")
        answer = kb.query("What CFL number should I use for methane flames?")
        logger.debug(f"Answer: {answer['answer'][:200]}...")
        logger.debug(f"Confidence: {answer['confidence']}\n")

        # Test 2: Generate questions from prompt
        logger.debug("[Test 2] Generate questions from prompt:")
        llm_client = get_llm_client(config)
        questions = kb.generate_questions_from_prompt(
            "2D methane flame with AMR, 512x512 base grid",
            llm_client
        )
        logger.debug(f"Generated {len(questions)} questions:")
        for i, q in enumerate(questions, 1):
            logger.debug(f"  {i}. {q}")

        # Test 3: Batch queries
        logger.debug("\n[Test 3] Batch query generated questions:")
        answers = kb.query_multiple(questions[:3])  # Query first 3
        for q, ans in answers.items():
            logger.debug(f"\nQ: {q}")
            logger.debug(f"A: {ans['answer'][:150]}...")

    except Exception as e:
        logger.debug(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
