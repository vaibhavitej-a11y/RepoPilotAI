"""Architecture analysis skill."""
import json
from google.adk import Agent
from app.models.analysis import DimensionScore, Finding
from app.models.request import RepoAnalysisRequest, AnalysisDimension
from app.config import get_gemini_model
from app.mcp.tool_registry import build_mcp_toolset, MCPConfig
from app.skills._agent_runner import extract_json_text, run_agent_prompt

async def architecture_skill(request: RepoAnalysisRequest) -> DimensionScore:
    """Analyze the repository architecture autonomously using a sub-agent.
    
    Detects language, framework, package manager, and folder structure.
    """
    # 1. Dynamically build the read-only toolset scoped to this request
    mcp_toolset = build_mcp_toolset(
        data_source=request.data_source,
        config=MCPConfig(target_path=request.repo_target)
    )
    
    # 2. Instantiate a specialized sub-agent for architecture analysis
    analyzer = Agent(
        name="architecture_analyzer",
        model=get_gemini_model(),
        description="Analyzes software architecture by exploring local or remote filesystems.",
        instruction="""You are an expert software architect. Analyze the provided repository using your tools.
Explore the directory structure, package manifests (package.json, pyproject.toml, etc.), and main entry points.
Determine:
1. Primary programming language.
2. Main frameworks and libraries used.
3. Package manager (e.g., npm, pip, poetry).
4. High-level folder structure.

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
    "language": "string",
    "frameworks": ["string"],
    "package_manager": "string",
    "structure_summary": "string"
  }
}
Do NOT wrap the response in markdown blocks (```json). Just return the raw JSON object.""",
        tools=[mcp_toolset],
    )
    
    # 3. Execute the analysis flow
    prompt = f"Analyze the architecture for the repository at: {request.repo_target}. Maximum files to consider: {request.max_files_to_scan}."
    response_text = ""
    try:
        response_text = await run_agent_prompt(
            analyzer,
            prompt,
            app_name="repopilot_architecture",
            session_id="architecture-session",
        )
        data = json.loads(extract_json_text(response_text))
        return DimensionScore(
            dimension=AnalysisDimension.ARCHITECTURE,
            score=data.get("score", 0.0),
            findings=[Finding(**f) for f in data.get("findings", [])],
            raw_signals=data.get("raw_signals", {})
        )
    except Exception as e:
        # Fallback for parsing errors or tool failures
        return DimensionScore(
            dimension=AnalysisDimension.ARCHITECTURE,
            score=0.0,
            findings=[
                Finding(
                    severity="critical",
                    message=f"Architecture analysis failed or returned malformed data: {str(e)}"
                )
            ],
            raw_signals={"error": str(e), "raw_response": response_text}
        )

