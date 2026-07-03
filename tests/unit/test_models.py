"""Unit tests for RepoPilot data models."""
import pytest
from pydantic import ValidationError
from datetime import datetime, timezone

from app.models.request import RepoAnalysisRequest, AnalysisDimension
from app.models.analysis import Finding, DimensionScore, AnalysisBundle
from app.models.report import EngineeringReport


def test_analysis_dimension_enum():
    """Verify that all four required dimensions are supported."""
    assert AnalysisDimension.ARCHITECTURE == "architecture"
    assert AnalysisDimension.DOCUMENTATION == "documentation"
    assert AnalysisDimension.CODE_QUALITY == "code_quality"
    assert AnalysisDimension.SECURITY == "security"
    assert len(list(AnalysisDimension)) == 4


def test_repo_analysis_request_valid_filesystem():
    """Test valid filesystem analysis request validation."""
    req = RepoAnalysisRequest(
        data_source="filesystem",
        repo_target="/absolute/path/to/repo",
        max_files_to_scan=150
    )
    assert req.data_source == "filesystem"
    assert req.repo_target == "/absolute/path/to/repo"
    assert req.branch == "main"
    assert req.max_files_to_scan == 150
    assert len(req.include_dimensions) == 4


def test_repo_analysis_request_valid_github():
    """Test valid github analysis request validation."""
    req = RepoAnalysisRequest(
        data_source="github",
        repo_target="owner/repo",
        branch="develop",
        max_files_to_scan=500
    )
    assert req.data_source == "github"
    assert req.repo_target == "owner/repo"
    assert req.branch == "develop"
    assert req.max_files_to_scan == 500


def test_repo_analysis_request_invalid_source():
    """Test validation errors for invalid data source."""
    with pytest.raises(ValidationError):
        RepoAnalysisRequest(
            data_source="invalid_source",  # type: ignore
            repo_target="owner/repo"
        )


def test_repo_analysis_request_invalid_max_files():
    """Test validation boundaries for max_files_to_scan."""
    # Under minimum (1)
    with pytest.raises(ValidationError):
        RepoAnalysisRequest(
            data_source="filesystem",
            repo_target="/path",
            max_files_to_scan=0
        )

    # Over maximum (1000)
    with pytest.raises(ValidationError):
        RepoAnalysisRequest(
            data_source="filesystem",
            repo_target="/path",
            max_files_to_scan=1001
        )


def test_finding_model():
    """Test Finding Pydantic model validation."""
    f = Finding(
        severity="critical",
        message="Hardcoded API Key found",
        file_path="src/config.py",
        line_number=42
    )
    assert f.severity == "critical"
    assert f.message == "Hardcoded API Key found"
    assert f.file_path == "src/config.py"
    assert f.line_number == 42

    # Verify default fields
    f_min = Finding(severity="info", message="Just a note")
    assert f_min.file_path is None
    assert f_min.line_number is None


def test_dimension_score_model():
    """Test DimensionScore validation."""
    score = DimensionScore(
        dimension=AnalysisDimension.SECURITY,
        score=8.5,
        findings=[
            Finding(severity="warning", message="Missing SECURITY.md")
        ],
        raw_signals={"has_security_policy": False}
    )
    assert score.dimension == AnalysisDimension.SECURITY
    assert score.score == 8.5
    assert len(score.findings) == 1
    assert score.raw_signals["has_security_policy"] is False


def test_engineering_report_model():
    """Test EngineeringReport validation."""
    now = datetime.now(timezone.utc)
    report = EngineeringReport(
        repo_target="owner/repo",
        analyzed_at=now,
        data_source="github",
        overall_score=7.5,
        dimensions=[
            DimensionScore(
                dimension=AnalysisDimension.ARCHITECTURE,
                score=7.5,
                findings=[],
                raw_signals={}
            )
        ],
        executive_summary="Highly structured project.",
        recommendations=["Add tests"],
        markdown_report="# Repo Report"
    )
    assert report.repo_target == "owner/repo"
    assert report.analyzed_at == now
    assert report.overall_score == 7.5
    assert len(report.dimensions) == 1
    assert report.executive_summary == "Highly structured project."
