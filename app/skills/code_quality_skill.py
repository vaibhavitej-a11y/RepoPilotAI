"""Code quality analysis skill."""
import json
from google.adk import Agent
from app.models.analysis import DimensionScore, Finding
from app.models.request import RepoAnalysisRequest, AnalysisDimension
from app.config import get_gemini_model
from app.mcp.tool_registry import build_mcp_toolset, MCPConfig
from app.skills._agent_runner import extract_json_text, run_agent_prompt

async def code_quality_skill(request: RepoAnalysisRequest) -> DimensionScore:
    """Analyze the repository code quality autonomously using a sub-agent.
    
    Checks for linters, formatters, CI/CD, tests, and overall maintainability.
    """
    # 1. Dynamically build the read-only toolset scoped to this request
    mcp_toolset = build_mcp_toolset(
        data_source=request.data_source,
        config=MCPConfig(target_path=request.repo_target)
    )
    
    # 2. Instantiate a specialized sub-agent for code quality analysis
    analyzer = Agent(
        name="code_quality_analyzer",
        model=get_gemini_model(),
        description="Analyzes software code quality and maintainability by statically exploring filesystems.",
        instruction="""You are an expert Staff Software Engineer. Analyze the provided repository using your tools.
Perform read-only static analysis on the directory. NEVER execute repository code.
Focus on identifying engineering quality indicators:
1. Presence of testing frameworks and the approximate ratio of test files to source files.
2. Linting and formatting configurations (e.g., .eslintrc, .prettierrc, ruff.toml, .flake8).
3. CI/CD pipeline configurations (.github/workflows, .gitlab-ci.yml).
4. Code maintainability indicators (excessively large files, deep nesting, unstructured code).
5. Presence of technical debt markers (e.g., TODO, FIXME comments).

You MUST respond with a RAW JSON object matching this exact schema:
{
  "score": float (0.0 to 10.0, where 10.0 is perfect quality/maintainability),
  "findings": [
    {
      "severity": "info" | "warning" | "critical",
      "message": "string",
      "file_path": "string or null",
      "line_number": "int or null"
    }
  ],
  "raw_signals": {
    "has_ci_cd": boolean,
    "has_tests": boolean,
    "has_linters": boolean,
    "technical_debt_markers_found": boolean,
    "summary": "string"
  }
}
Do NOT wrap the response in markdown blocks (```json). Just return the raw JSON object.""",
        tools=[mcp_toolset],
    )
    
    prompt = f"Analyze the code quality for the repository at: {request.repo_target}. Maximum files to consider: {request.max_files_to_scan}."
    response_text = ""
    try:
        response_text = await run_agent_prompt(
            analyzer,
            prompt,
            app_name="repopilot_code_quality",
            session_id="code-quality-session",
        )
        data = json.loads(extract_json_text(response_text))
        return DimensionScore(
            dimension=AnalysisDimension.CODE_QUALITY,
            score=data.get("score", 0.0),
            findings=[Finding(**f) for f in data.get("findings", [])],
            raw_signals=data.get("raw_signals", {})
        )
    except Exception as e:
        return DimensionScore(
            dimension=AnalysisDimension.CODE_QUALITY,
            score=0.0,
            findings=[
                Finding(
                    severity="critical",
                    message=f"Code quality analysis failed or returned malformed data: {str(e)}"
                )
            ],
            raw_signals={"error": str(e), "raw_response": response_text}
        )
