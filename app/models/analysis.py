"""Data models for intermediate analysis results."""
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.request import AnalysisDimension


class Finding(BaseModel):
    """A specific finding from a skill analysis."""
    severity: Literal["info", "warning", "critical"]
    message: str
    file_path: str | None = None
    line_number: int | None = None


class DimensionScore(BaseModel):
    """The output of a single analysis skill."""
    dimension: AnalysisDimension
    score: float = Field(ge=0.0, le=10.0)
    findings: list[Finding]
    raw_signals: dict[str, Any]


class AnalysisBundle(BaseModel):
    """Collection of all dimension scores from the RepositoryAnalysisAgent."""
    architecture: DimensionScore | None = None
    documentation: DimensionScore | None = None
    code_quality: DimensionScore | None = None
    security: DimensionScore | None = None
