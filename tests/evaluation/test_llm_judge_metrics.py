from unittest.mock import MagicMock

from memory_with_receipts.evaluation.metrics import (
    answer_relevance,
    claim_coverage,
    faithfulness,
)
from memory_with_receipts.llm.base import BaseLLMProvider, GenerationResult
from memory_with_receipts.rag.search_service import SearchResultData


class TestLLMJudgeMetrics:
    def setup_method(self) -> None:
        self.mock_llm = MagicMock(spec=BaseLLMProvider)
        self.chunks = [
            SearchResultData(
                chunk_id="chunk1",
                document_id="doc1",
                document_title="Title 1",
                source_type="text",
                uri=None,
                chunk_index=0,
                content="The capital of France is Paris.",
                section_title="Intro",
                heading_path="Intro",
                start_char=0,
                end_char=30,
            )
        ]

    def test_faithfulness_pass(self) -> None:
        self.mock_llm.generate.return_value = GenerationResult(
            answer='{"score": 1.0, "reason": "All claims are supported."}',
            raw_prompt="...",
            model="mock-llm",
            provider="mock",
        )
        
        result = faithfulness(
            answer="France's capital is Paris.",
            context_chunks=self.chunks,
            llm_provider=self.mock_llm,
        )
        
        assert result.name == "faithfulness"
        assert result.passed is True
        assert result.score == 1.0
        assert "All claims are supported" in result.detail
        self.mock_llm.generate.assert_called_once()

    def test_faithfulness_fail(self) -> None:
        self.mock_llm.generate.return_value = GenerationResult(
            answer='{"score": 0.2, "reason": "Claims are hallucinated."}',
            raw_prompt="...",
            model="mock-llm",
            provider="mock",
        )
        
        result = faithfulness(
            answer="The capital of France is Rome.",
            context_chunks=self.chunks,
            llm_provider=self.mock_llm,
        )
        
        assert result.name == "faithfulness"
        assert result.passed is False
        assert result.score == 0.2
        assert "Rome" in result.detail or "hallucinated" in result.detail

    def test_answer_relevance_pass(self) -> None:
        self.mock_llm.generate.return_value = GenerationResult(
            answer='{"score": 0.95, "reason": "Directly answers the query."}',
            raw_prompt="...",
            model="mock-llm",
            provider="mock",
        )
        
        result = answer_relevance(
            answer="Paris is the capital of France.",
            query="What is the capital of France?",
            llm_provider=self.mock_llm,
        )
        
        assert result.name == "answer_relevance"
        assert result.passed is True
        assert result.score == 0.95

    def test_claim_coverage_pass(self) -> None:
        self.mock_llm.generate.return_value = GenerationResult(
            answer='{"score": 0.8, "reason": "Covers key details."}',
            raw_prompt="...",
            model="mock-llm",
            provider="mock",
        )
        
        result = claim_coverage(
            answer="Paris is the capital of France.",
            context_chunks=self.chunks,
            llm_provider=self.mock_llm,
        )
        
        assert result.name == "claim_coverage"
        assert result.passed is True
        assert result.score == 0.8

    def test_parsing_fallback_on_malformed_json(self) -> None:
        # LLM returns some random text with a score at the end
        self.mock_llm.generate.return_value = GenerationResult(
            answer="This answer gets a score of 0.85 because it is good.",
            raw_prompt="...",
            model="mock-llm",
            provider="mock",
        )
        
        result = faithfulness(
            answer="Paris is the capital.",
            context_chunks=self.chunks,
            llm_provider=self.mock_llm,
        )
        
        assert result.score == 0.85
        assert result.passed is True

    def test_eval_runner_runs_llm_judge_metrics(self) -> None:
        from memory_with_receipts.evaluation.runner import EvalRunner
        from memory_with_receipts.evaluation.schemas import GoldenCase

        # Mock GenerationService
        mock_gen_svc = MagicMock()
        mock_ask_result = MagicMock()
        mock_ask_result.answer = "LLM answer"
        mock_ask_result.citations = []
        mock_ask_result.context_chunks_used = 0
        mock_ask_result.is_insufficient = False
        mock_ask_result.model = "test-model"
        mock_ask_result.provider = "test-provider"
        mock_ask_result.retrieval_time_ms = 10
        mock_ask_result.generation_time_ms = 20
        mock_ask_result._retrieved_chunks = self.chunks
        mock_gen_svc.ask.return_value = mock_ask_result

        # Mock LLM response for judge calls
        self.mock_llm.generate.return_value = GenerationResult(
            answer='{"score": 0.8, "reason": "Good."}',
            raw_prompt="...",
            model="mock-llm",
            provider="mock",
        )

        case = GoldenCase(
            id="case1",
            query="test query",
            expected_source_titles=["Title 1"],
            must_include_terms=[],
            must_not_include_terms=[],
            min_citation_count=0,
        )

        # 1. Without llm_provider
        runner_no_llm = EvalRunner(generation_service=mock_gen_svc, session=MagicMock())
        result_no_llm = runner_no_llm.run_case(case)
        metric_names_no_llm = [m.name for m in result_no_llm.metrics]
        assert "faithfulness" not in metric_names_no_llm
        assert "answer_relevance" not in metric_names_no_llm
        assert "claim_coverage" not in metric_names_no_llm

        # 2. With llm_provider
        runner_with_llm = EvalRunner(
            generation_service=mock_gen_svc,
            session=MagicMock(),
            llm_provider=self.mock_llm,
        )
        result_with_llm = runner_with_llm.run_case(case)
        metric_names_with_llm = [m.name for m in result_with_llm.metrics]
        assert "faithfulness" in metric_names_with_llm
        assert "answer_relevance" in metric_names_with_llm
        assert "claim_coverage" in metric_names_with_llm
        assert self.mock_llm.generate.call_count == 3
