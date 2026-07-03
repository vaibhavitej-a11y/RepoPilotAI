"""Unit tests for the ReportAgent and Pipeline Orchestration."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.models.analysis import AnalysisBundle, DimensionScore
from app.models.request import AnalysisDimension, RepoAnalysisRequest
from app.models.report import EngineeringReport
from app.agents.report_agent import report_agent
from app.agents.pipeline import run_pipeline, pipeline


def _make_bundle(arch=8.0, docs=6.0, quality=7.0, sec=5.0) -> AnalysisBundle:
    """Helper to create an AnalysisBundle with known scores."""
    return AnalysisBundle(
        architecture=DimensionScore(
            dimension=AnalysisDimension.ARCHITECTURE,
            score=arch,
            findings=[],
            raw_signals={}
        ),
        documentation=DimensionScore(
            dimension=AnalysisDimension.DOCUMENTATION,
            score=docs,
            findings=[],
            raw_signals={}
        ),
        code_quality=DimensionScore(
            dimension=AnalysisDimension.CODE_QUALITY,
            score=quality,
            findings=[],
            raw_signals={}
        ),
        security=DimensionScore(
            dimension=AnalysisDimension.SECURITY,
            score=sec,
            findings=[],
            raw_signals={}
        )
    )


@pytest.mark.asyncio
async def test_report_agent_overall_score_math():
    """Verify that overall score is computed as the mean of dimension scores.

    The report_agent FunctionNode wraps an async function. We access it via
    report_agent.__private_attributes__ -> _func, which is the decorated coroutine.
    The correct private attribute accessor on a Pydantic model uses _func directly.
    """
    # Patch Agent at the location where report_agent.py imported it
    mock_response = MagicMock()
    mock_response.text = (
        '{"executive_summary": "Test Summary", '
        '"recommendations": ["Do something"], '
        '"markdown_report": "# Test Report"}'
    )

    mock_agent_instance = AsyncMock()
    mock_agent_instance.run_async = AsyncMock(return_value=mock_response)

    bundle = _make_bundle(arch=8.0, docs=6.0, quality=7.0, sec=5.0)

    # Patch Agent where it is actually used (the local import in report_agent module)
    with patch("app.agents.report_agent.Agent", return_value=mock_agent_instance):
        # Access the wrapped coroutine via the FunctionNode's private _func attribute
        func = report_agent._func  # type: ignore[attr-defined]
        report = await func(bundle)

    # Verify score is mean of 8.0, 6.0, 7.0, 5.0 = 26.0 / 4 = 6.5
    assert report.overall_score == 6.5
    assert report.executive_summary == "Test Summary"
    assert report.recommendations == ["Do something"]
    assert report.markdown_report == "# Test Report"
    assert len(report.dimensions) == 4


@pytest.mark.asyncio
async def test_report_agent_graceful_json_parse_failure():
    """Verify that report_agent handles malformed LLM JSON gracefully."""
    mock_response = MagicMock()
    mock_response.text = "NOT VALID JSON {{{{{"

    mock_agent_instance = AsyncMock()
    mock_agent_instance.run_async = AsyncMock(return_value=mock_response)

    bundle = _make_bundle(arch=5.0, docs=5.0, quality=5.0, sec=5.0)

    with patch("app.agents.report_agent.Agent", return_value=mock_agent_instance):
        func = report_agent._func  # type: ignore[attr-defined]
        report = await func(bundle)

    # The agent should return a fallback report, not raise
    assert report.overall_score == 5.0
    assert "parsing error" in report.executive_summary.lower() or report.executive_summary
    assert isinstance(report.recommendations, list)
    assert "# Error" in report.markdown_report or isinstance(report.markdown_report, str)


@pytest.mark.asyncio
async def test_run_pipeline_returns_engineering_report():
    """Verify run_pipeline builds a Runner with node=pipeline and returns the report.

    run_pipeline uses Runner.run_async (an async generator) to drain ADK Events.
    The final Event whose .output is an EngineeringReport is returned.
    """
    from datetime import datetime, timezone
    from google.adk import Runner

    expected_report = EngineeringReport(
        repo_target="/path/to/repo",
        analyzed_at=datetime.now(timezone.utc),
        data_source="filesystem",
        overall_score=7.5,
        dimensions=[
            DimensionScore(
                dimension=AnalysisDimension.ARCHITECTURE,
                score=7.5,
                findings=[],
                raw_signals={}
            )
        ],
        executive_summary="Test summary",
        recommendations=[],
        markdown_report="# Test"
    )

    # Simulate the ADK event stream: one event carrying the report
    mock_event = MagicMock()
    mock_event.output = expected_report

    # run_async is an async generator; replace with an async generator function
    async def fake_run_async(self, **kwargs):
        yield mock_event

    req = RepoAnalysisRequest(
        data_source="filesystem",
        repo_target="/path/to/repo"
    )

    with patch.object(Runner, "run_async", fake_run_async):
        report = await run_pipeline(req)

    assert report == expected_report


@pytest.mark.asyncio
async def test_run_pipeline_raises_if_no_report_produced():
    """Verify run_pipeline raises RuntimeError when no EngineeringReport event is produced."""
    from google.adk import Runner

    # Emit a non-report event (output is not an EngineeringReport)
    mock_event = MagicMock()
    mock_event.output = None

    async def fake_run_async(self, **kwargs):
        yield mock_event

    req = RepoAnalysisRequest(
        data_source="filesystem",
        repo_target="/path/to/repo"
    )

    with patch.object(Runner, "run_async", fake_run_async):
        with pytest.raises(RuntimeError, match="no EngineeringReport was produced"):
            await run_pipeline(req)
