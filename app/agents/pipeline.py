"""Workflow pipeline orchestrating the agents."""
from google.adk.workflow import Workflow
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from app.agents.report_agent import report_agent
from app.agents.repository_analysis_agent import repository_analysis_agent
from app.models.report import EngineeringReport
from app.models.request import RepoAnalysisRequest

# ADK 2.0 Workflow definition.
# The graph structure strictly enforces: START -> Analysis -> Report -> END
pipeline = Workflow(
    name="repopilot_pipeline",
    edges=[
        ("START", repository_analysis_agent),
        (repository_analysis_agent, report_agent),
    ],
)


async def run_pipeline(request: RepoAnalysisRequest) -> EngineeringReport:
    """Entry point to run the workflow.
    
    Constructs a Runner with the pipeline Workflow as its node,
    then drains the async event stream to extract the final EngineeringReport output.
    """
    # 1. Seed the workflow's global state.
    # ADK FunctionNode uses parameter_binding='state' by default: it resolves
    # each function parameter by looking up ctx.state[<param_name>].
    # repository_analysis_agent has a parameter named 'request: RepoAnalysisRequest',
    # so we must store the serialised request under the key 'request'.
    # Pydantic's TypeAdapter (used internally by FunctionNode._bind_parameters)
    # will coerce the plain dict back to a RepoAnalysisRequest automatically.
    initial_state = {
        "request": request.model_dump(),
        "repo_target": request.repo_target,
        "data_source": request.data_source,
    }
    
    # 2. Create an in‑memory session and populate it with the initial state.
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="repopilot",
        user_id="repopilot-system",
        session_id="analysis-session",
        state=initial_state,
    )

    # 3. Build a Runner backed by the same session service.
    runner = Runner(
        app_name="repopilot",
        node=pipeline,
        session_service=session_service,
    )
    
    # 3. Drain the event stream.
    # For a Workflow node, Runner.run_async yields ADK Events as the graph executes.
    # The final Event from the terminal node contains the EngineeringReport as its .output.
    final_report: EngineeringReport | None = None
    async for event in runner.run_async(
        user_id="repopilot-system",
        session_id="analysis-session",
        state_delta={},
    ):
        # ADK's FunctionNode._to_event() serialises every BaseModel return value
        # to a plain dict via model_dump() before storing it in event.output
        # (see _function_node.py line ~411).  Therefore event.output is always
        # a dict here, never an EngineeringReport instance.  We must reconstruct
        # the model with model_validate().  We also guard against the unlikely
        # case where ADK changes this behaviour and passes the object directly.
        if event.output is not None:
            output = event.output
            if isinstance(output, EngineeringReport):
                final_report = output
            elif isinstance(output, dict):
                try:
                    final_report = EngineeringReport.model_validate(output)
                except Exception:
                    pass  # not the output event we want; keep draining
    
    if final_report is None:
        raise RuntimeError(
            "Pipeline completed but no EngineeringReport was produced. "
            "Check that report_agent returns a valid EngineeringReport."
        )
    
    return final_report
