"""ReportAgent definition."""
import json
import logging
import re
from datetime import datetime, timezone
from google.adk import Agent
from google.adk.workflow import node
from google.genai import types

from app.config import get_gemini_model
from app.models.analysis import AnalysisBundle
from app.models.report import EngineeringReport
from app.skills._agent_runner import run_agent_prompt

logger = logging.getLogger(__name__)

_REPORT_SYNTHESIS_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "executive_summary": types.Schema(type=types.Type.STRING),
        "recommendations": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
        ),
        "markdown_report": types.Schema(type=types.Type.STRING),
    },
    required=["executive_summary", "recommendations", "markdown_report"],
)

_REPORT_GENERATE_CONFIG = types.GenerateContentConfig(
    response_mime_type="application/json",
)


def _extract_json_text(raw: str) -> str:
    """Strip markdown code fences and isolate a JSON object from LLM text."""
    text = raw.strip()
    if not text:
        return text

    fence_match = re.search(
        r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        return fence_match.group(1).strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]

    return text


@node(name="report_agent")
async def report_agent(bundle: AnalysisBundle, ctx=None) -> EngineeringReport:
    """Node that synthesizes the AnalysisBundle into an EngineeringReport.
    
    This agent strictly enforces a security boundary by having ZERO access
    to repository reading tools. It relies entirely on the aggregated data
    provided in the AnalysisBundle.
    """
    
    # 1. Deterministic Score Calculation
    scores = []
    if bundle.architecture: scores.append(bundle.architecture.score)
    if bundle.documentation: scores.append(bundle.documentation.score)
    if bundle.security: scores.append(bundle.security.score)
    if bundle.code_quality: scores.append(bundle.code_quality.score)
    
    overall_score = sum(scores) / len(scores) if scores else 0.0
    
    dimensions = []
    if bundle.architecture: dimensions.append(bundle.architecture)
    if bundle.documentation: dimensions.append(bundle.documentation)
    if bundle.security: dimensions.append(bundle.security)
    if bundle.code_quality: dimensions.append(bundle.code_quality)
    
    # 2. Extract repository metadata from context state if available
    # Typically, the initial orchestrator sets this in ctx.state upon start.
    repo_target = "Unknown Repository"
    data_source = "filesystem"
    if ctx and hasattr(ctx, "state"):
        repo_target = ctx.state.get("repo_target", repo_target)
        data_source = ctx.state.get("data_source", data_source)
        
    # 3. Instantiate the specialized Report Synthesizer Agent
    # Notice that tools=[] is explicitly set.
    synthesizer = Agent(
        name="report_synthesizer",
        model=get_gemini_model(),
        description="Synthesizes analysis data into a structured engineering report.",
        instruction="""You are a Principal Staff Software Engineer.
You will be provided with a JSON payload containing analysis scores and findings across multiple engineering dimensions for a repository.
Your task is to synthesize this data into a professional engineering report.

You MUST respond with a RAW JSON object matching this exact schema:
{
  "executive_summary": "string (A high-level overview of the repository's health)",
  "recommendations": ["string (A prioritized list of actionable recommendations)"],
  "markdown_report": "string (A complete, well-formatted Markdown document incorporating all findings, scores, strengths, and weaknesses)"
}
Do NOT wrap the response in markdown blocks (```json). Just return the raw JSON object.""",
        tools=[],  # Strictly NO MCP tools provided
        output_schema=_REPORT_SYNTHESIS_SCHEMA,
        generate_content_config=_REPORT_GENERATE_CONFIG,
    )
    
    # 4. Execute the synthesis LLM call via a Runner (ADK 2.0 requires Runner
    # to invoke an Agent; Agent.run_async itself is an internal coroutine that
    # takes an InvocationContext, NOT a plain prompt string).
    prompt_payload = bundle.model_dump_json(indent=2)
    prompt = f"Analyze the following Repository Analysis Bundle and generate the final report:\n\n{prompt_payload}"

    try:
        response_text = await run_agent_prompt(
            synthesizer,
            prompt,
            app_name="repopilot_report",
            session_id="report-session",
        )
    except Exception as e:
        logger.error("Report synthesizer LLM call failed: %s", e)
        response_text = ""
        executive_summary = f"Report generation failed: {e}"
        recommendations = []
        markdown_report = f"# Error\n\nFailed to synthesize report: {e}"
        report = EngineeringReport(
            repo_target=repo_target,
            analyzed_at=datetime.now(timezone.utc),
            data_source=data_source,  # type: ignore
            overall_score=overall_score,
            dimensions=dimensions,
            executive_summary=executive_summary,
            recommendations=recommendations,
            markdown_report=markdown_report,
        )
        if ctx and hasattr(ctx, "state"):
            ctx.state["final_report"] = report.model_dump()
        return report
    
    # 5. Parse the LLM response and populate the validated model
    try:
        json_text = _extract_json_text(response_text)
        if json_text != response_text.strip():
            logger.info(
                "Stripped markdown fences from report response; extracted JSON (%d chars)",
                len(json_text),
            )
        data = json.loads(json_text)
        executive_summary = data.get("executive_summary", "Summary unavailable.")
        recommendations = data.get("recommendations", [])
        markdown_report = data.get("markdown_report", "# Engineering Report\n\nNo report generated.")
    except Exception as e:
        logger.error(
            "Failed to parse report synthesizer response: %s; raw=%r",
            e,
            response_text[:4000] if len(response_text) > 4000 else response_text,
        )
        executive_summary = "Report generation failed due to a parsing error."
        recommendations = []
        markdown_report = f"# Error\n\nFailed to synthesize report: {e}\n\nRaw output:\n{response_text}"

    # 6. Construct and return the final EngineeringReport
    report = EngineeringReport(
        repo_target=repo_target,
        analyzed_at=datetime.now(timezone.utc),
        data_source=data_source,  # type: ignore (Pydantic handles coercion or strict typing)
        overall_score=overall_score,
        dimensions=dimensions,
        executive_summary=executive_summary,
        recommendations=recommendations,
        markdown_report=markdown_report
    )
    
    # Optional: Persist final report to the workflow state
    if ctx and hasattr(ctx, "state"):
        ctx.state["final_report"] = report.model_dump()
        
    return report
