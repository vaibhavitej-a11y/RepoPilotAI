"""Security analysis skill."""
import json
from google.adk import Agent
from app.models.analysis import DimensionScore, Finding
from app.models.request import RepoAnalysisRequest, AnalysisDimension
from app.config import get_gemini_model
from app.mcp.tool_registry import build_mcp_toolset, MCPConfig
from app.skills._agent_runner import extract_json_text, run_agent_prompt

async def security_skill(request: RepoAnalysisRequest) -> DimensionScore:
    """Analyze the repository security posture autonomously using a sub-agent.
    
    Checks for hardcoded secrets, security policies, dependency advisories,
    and permissive configurations.
    """
    # 1. Dynamically build the read-only toolset scoped to this request
    mcp_toolset = build_mcp_toolset(
        data_source=request.data_source,
        config=MCPConfig(target_path=request.repo_target)
    )
    
    # 2. Instantiate a specialized sub-agent for security analysis
    analyzer = Agent(
        name="security_analyzer",
        model=get_gemini_model(),
        description="Analyzes software security posture by statically exploring filesystems.",
        instruction="""You are an expert DevSecOps engineer and Application Security auditor. Analyze the provided repository using your tools.
Perform read-only static analysis on the directory. NEVER execute repository code.
Focus on identifying:
1. Hardcoded secrets, API keys, passwords, and tokens.
2. The presence of .env files, private keys (.pem, .key), and credential files that shouldn't be committed.
3. Insecure configuration patterns in source code (e.g., debug=True, permissive CORS, disabled SSL verification).
4. Dependency manifest files (requirements.txt, package.json, etc.) and check for general update hygiene.
5. Security-related project files like SECURITY.md, .gitignore (checking if sensitive dirs are ignored), and CODEOWNERS.

You MUST respond with a RAW JSON object matching this exact schema:
{
  "score": float (0.0 to 10.0, where 10.0 is perfectly secure),
  "findings": [
    {
      "severity": "info" | "warning" | "critical",
      "message": "string (Redact actual secrets if found)",
      "file_path": "string or null",
      "line_number": "int or null"
    }
  ],
  "raw_signals": {
    "has_security_policy": boolean,
    "has_gitignore": boolean,
    "secrets_found": boolean,
    "insecure_configs_found": boolean,
    "summary": "string"
  }
}
Do NOT wrap the response in markdown blocks (```json). Just return the raw JSON object.""",
        tools=mcp_toolset,
    )
    
    prompt = f"Analyze the security posture for the repository at: {request.repo_target}. Maximum files to consider: {request.max_files_to_scan}."
    response_text = ""
    try:
        response_text = await run_agent_prompt(
            analyzer,
            prompt,
            app_name="repopilot_security",
            session_id="security-session",
        )
        data = json.loads(extract_json_text(response_text))
        return DimensionScore(
            dimension=AnalysisDimension.SECURITY,
            score=data.get("score", 0.0),
            findings=[Finding(**f) for f in data.get("findings", [])],
            raw_signals=data.get("raw_signals", {})
        )
    except Exception as e:
        return DimensionScore(
            dimension=AnalysisDimension.SECURITY,
            score=0.0,
            findings=[
                Finding(
                    severity="critical",
                    message=f"Security analysis failed or returned malformed data: {str(e)}"
                )
            ],
            raw_signals={"error": str(e), "raw_response": response_text}
        )
