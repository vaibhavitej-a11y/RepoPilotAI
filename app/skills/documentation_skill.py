"""Documentation analysis skill."""
import json
from google.adk import Agent
from app.models.analysis import DimensionScore, Finding
from app.models.request import RepoAnalysisRequest, AnalysisDimension
from app.config import get_gemini_model
from app.mcp.tool_registry import build_mcp_toolset, MCPConfig
from app.skills._agent_runner import extract_json_text, run_agent_prompt

async def documentation_skill(request: RepoAnalysisRequest) -> DimensionScore:
    """Analyze the repository documentation autonomously using a sub-agent.
    
    Checks README quality, inline doc coverage, changelog,
    API docs, and contributing guides.
    """
    # 1. Dynamically build the read-only toolset scoped to this request
    mcp_toolset = build_mcp_toolset(
        data_source=request.data_source,
        config=MCPConfig(target_path=request.repo_target)
    )
    
    # 2. Instantiate a specialized sub-agent for documentation analysis
    analyzer = Agent(
        name="documentation_analyzer",
        model=get_gemini_model(),
        description="Analyzes software documentation by exploring local or remote filesystems.",
        instruction="""You are an expert technical writer and developer advocate. Analyze the provided repository using your tools.
Explore the directory for standard documentation files (README.md, CONTRIBUTING.md, LICENSE, CHANGELOG.md, docs/ folder) and sample a few source files to check for docstrings/comments.
Evaluate:
1. README completeness (onboarding, installation instructions, usage examples).
2. Presence and quality of API documentation or external docs folders.
3. Presence of community files (CONTRIBUTING, LICENSE, CHANGELOG).
4. General code documentation (docstrings, comments).

You MUST respond with a RAW JSON object matching this exact schema:
{
  "score": float (0.0 to 10.0),
  "findings": [
    {
      "severity": "info" | "warning" | "critical",
      "message": "string",
      "file_path": "string or null",
      "line_number": "int or null"
    }
  ],
  "raw_signals": {
    "has_readme": boolean,
    "has_contributing": boolean,
    "has_license": boolean,
    "has_changelog": boolean,
    "docs_folder_present": boolean,
    "summary": "string"
  }
}
Do NOT wrap the response in markdown blocks (```json). Just return the raw JSON object.""",
        tools=mcp_toolset,
    )
    
    prompt = f"Analyze the documentation for the repository at: {request.repo_target}. Maximum files to consider: {request.max_files_to_scan}."
    response_text = ""
    try:
        response_text = await run_agent_prompt(
            analyzer,
            prompt,
            app_name="repopilot_documentation",
            session_id="documentation-session",
        )
        data = json.loads(extract_json_text(response_text))
        return DimensionScore(
            dimension=AnalysisDimension.DOCUMENTATION,
            score=data.get("score", 0.0),
            findings=[Finding(**f) for f in data.get("findings", [])],
            raw_signals=data.get("raw_signals", {})
        )
    except Exception as e:
        return DimensionScore(
            dimension=AnalysisDimension.DOCUMENTATION,
            score=0.0,
            findings=[
                Finding(
                    severity="critical",
                    message=f"Documentation analysis failed or returned malformed data: {str(e)}"
                )
            ],
            raw_signals={"error": str(e), "raw_response": response_text}
        )
