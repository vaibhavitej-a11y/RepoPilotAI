"""Data models for RepoPilot AI requests."""
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisDimension(str, Enum):
    ARCHITECTURE = "architecture"
    DOCUMENTATION = "documentation"
    CODE_QUALITY = "code_quality"
    SECURITY = "security"


class RepoAnalysisRequest(BaseModel):
    """Input request model for triggering repository analysis."""
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    data_source: Literal["github", "filesystem"]
    repo_target: str = Field(min_length=1)
    branch: str = "main"
    max_files_to_scan: int = Field(default=200, ge=1, le=1000)
    include_dimensions: list[AnalysisDimension] = Field(
        default_factory=lambda: list(AnalysisDimension)
    )
