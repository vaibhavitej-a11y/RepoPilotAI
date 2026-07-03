"""RepositoryAnalysisAgent definition."""
import asyncio
import logging
from google.adk.workflow import node

from app.skills._agent_runner import SKILL_COOLDOWN_SECONDS

from app.models.request import RepoAnalysisRequest
from app.models.analysis import AnalysisBundle, DimensionScore
from app.skills.architecture_skill import architecture_skill
from app.skills.documentation_skill import documentation_skill
from app.skills.code_quality_skill import code_quality_skill
from app.skills.security_skill import security_skill

logger = logging.getLogger(__name__)

@node(name="repository_analysis_agent")
async def repository_analysis_agent(request: RepoAnalysisRequest, ctx=None) -> AnalysisBundle:
    """Orchestrates the repository analysis workflow node.
    
    This acts as a 'fan-out' / 'fan-in' orchestration node. It runs the four
    analysis skills concurrently and gathers their DimensionScore outputs.
    It performs NO language model summarization itself, acting purely as a
    deterministic router and aggregator to enforce the architecture specification.
    """
    
    # Note: In a production ADK 2.0 setup, if `ctx` is provided, we can log progress
    # or persist intermediate state to the database. For now, we focus on the orchestration.
    
    # 1. Run skills sequentially to reduce Gemini rate-limit pressure.
    skill_plan = (
        ("architecture", architecture_skill),
        ("documentation", documentation_skill),
        ("security", security_skill),
        ("code_quality", code_quality_skill),
    )

    results: list[DimensionScore | Exception] = []
    for name, skill_fn in skill_plan:
        try:
            result = await skill_fn(request)
            results.append(result)
        except Exception as exc:
            logger.error("Skill %s raised %s: %s", name, type(exc).__name__, exc)
            results.append(exc)
        await asyncio.sleep(SKILL_COOLDOWN_SECONDS)

    skill_names = tuple(name for name, _ in skill_plan)
    architecture, docs, security, code_quality = results

    for name, result in zip(skill_names, results):
        if isinstance(result, Exception):
            logger.error(
                "Skill %s raised %s: %s",
                name,
                type(result).__name__,
                result,
            )
        elif isinstance(result, DimensionScore):
            logger.info(
                "Skill %s returned DimensionScore(score=%.2f, findings=%d, raw_signals_keys=%s)",
                name,
                result.score,
                len(result.findings),
                list(result.raw_signals.keys()),
            )
        else:
            logger.warning(
                "Skill %s returned unexpected type %s: %r",
                name,
                type(result).__name__,
                result,
            )
    
    # 2. Fan-In: Collect results into the AnalysisBundle
    # In case of catastrophic skill failure (e.g., skill crashed without returning 
    # its fallback DimensionScore), we handle it safely here.
    bundle = AnalysisBundle()
    
    if not isinstance(architecture, Exception):
        bundle.architecture = architecture
    if not isinstance(docs, Exception):
        bundle.documentation = docs
    if not isinstance(security, Exception):
        bundle.security = security
    if not isinstance(code_quality, Exception):
        bundle.code_quality = code_quality

    logger.info(
        "AnalysisBundle built: architecture=%s, documentation=%s, security=%s, code_quality=%s",
        bundle.architecture is not None,
        bundle.documentation is not None,
        bundle.security is not None,
        bundle.code_quality is not None,
    )
        
    # 3. State Persistence
    # If the workflow context (ctx) is available, we write the bundle to the graph state
    # so downstream nodes (like ReportAgent) can access it globally if needed.
    if ctx and hasattr(ctx, "state"):
        ctx.state["bundle"] = bundle.model_dump()
        
    # Returning the bundle also allows it to be passed as direct input 
    # to the next node in the workflow edges.
    return bundle
