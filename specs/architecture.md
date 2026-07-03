# RepoPilot AI — Architecture Specification

**Version**: 1.0.0-spec  
**Status**: Draft  
**Created**: 2026-07-03  
**Framework**: Google Agent Development Kit (ADK) 2.0

---

## 1. System Overview

RepoPilot AI is structured as a **two-agent sequential pipeline** built on ADK 2.0. The two agents communicate via ADK's shared session state. Both agents access repository data exclusively through MCP (Model Context Protocol) tool calls — never through direct I/O.

```
User Input (RepoAnalysisRequest)
         |
         v
+-------------------------+
|  RepositoryAnalysisAgent |  <-- ADK LlmAgent + 4 Skills
|  (Data Gathering)        |
|  Skills:                 |
|    ArchitectureSkill     |
|    DocumentationSkill    |
|    CodeQualitySkill      |
|    SecuritySkill         |
+-------------------------+
         |  (session state: AnalysisBundle)
         v
+-------------------------+
|      ReportAgent         |  <-- ADK LlmAgent
|  (Synthesis & Output)    |
+-------------------------+
         |
         v
EngineeringReport (Pydantic) + Markdown Report
```

---

## 2. ADK 2.0 Component Mapping

| ADK Concept | RepoPilot Usage |
|---|---|
| `LlmAgent` | Both `RepositoryAnalysisAgent` and `ReportAgent` |
| `SequentialAgent` | Top-level pipeline orchestrating the two agents |
| Agent Skills | Four analysis skills attached to `RepositoryAnalysisAgent` |
| Session State | Carries `AnalysisBundle` between the two agents |
| MCP Toolset | GitHub MCP or Filesystem MCP (swappable at runtime) |
| `InMemorySessionService` | Default session backend for single-run analysis |
| `Runner` | Entry point for executing the pipeline |

---

## 3. Directory Structure

```
repopilot/
|-- app/
|   |-- agents/
|   |   |-- __init__.py
|   |   |-- repository_analysis_agent.py   # RepositoryAnalysisAgent definition
|   |   |-- report_agent.py                # ReportAgent definition
|   |   `-- pipeline.py                    # SequentialAgent pipeline + Runner
|   |
|   |-- skills/
|   |   |-- __init__.py
|   |   |-- architecture_skill.py          # ArchitectureSkill
|   |   |-- documentation_skill.py         # DocumentationSkill
|   |   |-- code_quality_skill.py          # CodeQualitySkill
|   |   `-- security_skill.py              # SecuritySkill
|   |
|   |-- models/
|   |   |-- __init__.py
|   |   |-- request.py                     # RepoAnalysisRequest, AnalysisDimension
|   |   |-- analysis.py                    # DimensionScore, Finding, AnalysisBundle
|   |   `-- report.py                      # EngineeringReport
|   |
|   |-- mcp/
|   |   |-- __init__.py
|   |   |-- tool_registry.py               # Read-only MCP tool whitelist + factory
|   |   |-- github_mcp.py                  # GitHub MCP client configuration
|   |   `-- filesystem_mcp.py              # Filesystem MCP client configuration
|   |
|   `-- main.py                            # CLI entry point
|
|-- specs/
|   |-- repopilot_spec.md
|   |-- architecture.md
|   `-- repopilot.feature
|
|-- tests/
|   |-- unit/
|   |   |-- test_models.py
|   |   |-- test_skills.py
|   |   `-- test_security_patterns.py
|   `-- integration/
|       |-- test_pipeline_github.py
|       `-- test_pipeline_filesystem.py
|
|-- evals/
|   |-- repos/
|   |   |-- well_documented/
|   |   |-- minimal/
|   |   |-- secrets_planted/
|   |   `-- monorepo/
|   |-- golden_reports/
|   `-- run_evals.py
|
|-- docs/
|-- pyproject.toml
`-- README.md
```

---

## 4. Agent Specifications

### 4.1 RepositoryAnalysisAgent

**Type**: `LlmAgent` (ADK 2.0)  
**Responsibility**: Orchestrate the four analysis skills and aggregate their outputs into an `AnalysisBundle` stored in session state.

**Configuration**:
```python
RepositoryAnalysisAgent = LlmAgent(
    name="repository_analysis_agent",
    model="gemini-2.5-pro",
    description="Analyzes a software repository across four engineering dimensions.",
    instruction=ANALYSIS_AGENT_PROMPT,   # loaded from prompts/analysis_agent.md
    tools=[mcp_toolset],                 # read-only MCP tools only
    skills=[
        ArchitectureSkill,
        DocumentationSkill,
        CodeQualitySkill,
        SecuritySkill,
    ],
    output_key="analysis_bundle",        # written to session state
)
```

**Input**: `RepoAnalysisRequest` (via session state `"request"` key)  
**Output**: `AnalysisBundle` written to session state `"analysis_bundle"` key

**Skill Execution Order**: Architecture -> Documentation -> Code Quality -> Security  
Each skill reads from MCP tools and writes its `DimensionScore` to the bundle.

---

### 4.2 ReportAgent

**Type**: `LlmAgent` (ADK 2.0)  
**Responsibility**: Read the `AnalysisBundle` from session state, synthesize an executive summary and recommendations, render the Markdown report, and produce the final `EngineeringReport`.

**Configuration**:
```python
ReportAgent = LlmAgent(
    name="report_agent",
    model="gemini-2.5-pro",
    description="Synthesizes analysis results into a structured engineering report.",
    instruction=REPORT_AGENT_PROMPT,     # loaded from prompts/report_agent.md
    tools=[],                            # No MCP tools — reads session state only
    output_key="engineering_report",     # written to session state
)
```

**Input**: `AnalysisBundle` from session state `"analysis_bundle"` key  
**Output**: `EngineeringReport` written to session state `"engineering_report"` key

**Design rationale**: ReportAgent has **no MCP tools**. It is a pure synthesis agent that operates only on already-validated, already-collected data. This enforces the separation between data gathering and reporting, and eliminates any risk of the report agent making unauthorized repository accesses.

---

### 4.3 Pipeline

**Type**: `SequentialAgent` (ADK 2.0)

```python
pipeline = SequentialAgent(
    name="repopilot_pipeline",
    sub_agents=[RepositoryAnalysisAgent, ReportAgent],
)
```

**Session Flow**:
```
session.state["request"]           <- set by CLI / caller before pipeline.run()
session.state["analysis_bundle"]   <- set by RepositoryAnalysisAgent
session.state["engineering_report"]<- set by ReportAgent (final output)
```

---

## 5. MCP Architecture

### 5.1 Tool Registry

A central `MCPToolRegistry` enforces the read-only constraint at configuration time.

```python
ALLOWED_MCP_TOOLS = frozenset({
    "read_file",
    "list_directory",
    "search_files",
    "get_file_metadata",
})

def build_mcp_toolset(data_source: Literal["github", "filesystem"], config: MCPConfig) -> MCPToolset:
    """
    Returns an MCPToolset scoped to ALLOWED_MCP_TOOLS only.
    Raises ConfigurationError if any registered tool is outside the allowlist.
    """
```

### 5.2 GitHub MCP

- **Server**: `@modelcontextprotocol/server-github` (or equivalent ADK-compatible adapter)
- **Auth**: Personal Access Token (PAT) with `repo:read` scope only, supplied via environment variable `GITHUB_PAT`
- **Rate limiting**: Exponential backoff with max 3 retries, surfaced as `MCPRateLimitError`
- **Scope clamping**: All file operations are prefixed with the resolved `owner/repo/branch` path

### 5.3 Filesystem MCP

- **Server**: `@modelcontextprotocol/server-filesystem` (or equivalent ADK-compatible adapter)
- **Root clamping**: The MCP server is initialized with a root path equal to the validated `repo_target`; path traversal outside this root is rejected at the server level
- **No network access**: Filesystem MCP server runs in an isolated process with no outbound network permissions

---

## 6. Skill Architecture

Each skill follows the same interface contract:

```python
class BaseSkill(Protocol):
    name: str
    dimension: AnalysisDimension

    async def run(
        self,
        request: RepoAnalysisRequest,
        mcp_tools: MCPToolset,
    ) -> DimensionScore:
        ...
```

### Skill Execution Model

1. Skill receives the validated `RepoAnalysisRequest` and the active `MCPToolset`.
2. Skill calls MCP tools to gather file listings and file contents.
3. Skill performs purely in-memory, static analysis on the returned text.
4. Skill returns a `DimensionScore` with a numeric score, list of `Finding` objects, and `raw_signals` dict.
5. Skill MUST NOT call any tool outside the `MCPToolset` provided.
6. Skill MUST NOT spawn subprocesses or perform network I/O beyond MCP calls.

### Scoring Model

Each skill produces a score on a **0.0–10.0 scale** using a weighted signal model:

```
score = sum(signal_weight[i] * signal_value[i]) / sum(signal_weight[i])
```

Where `signal_value[i]` is either binary (0.0 or 1.0) for existence checks, or a normalized continuous value for quantitative signals (e.g., test file ratio).

The `overall_score` on `EngineeringReport` is the unweighted mean of the four dimension scores.

---

## 7. Data Flow Diagram

```
[CLI / API Caller]
      |
      | RepoAnalysisRequest (validated Pydantic)
      v
[SequentialAgent Pipeline]
      |
      +-> [RepositoryAnalysisAgent]
      |         |
      |         |-- ArchitectureSkill --> MCP.list_directory()
      |         |                    --> MCP.read_file()
      |         |                    --> ArchitectureReport
      |         |
      |         |-- DocumentationSkill --> MCP.search_files()
      |         |                     --> MCP.read_file()
      |         |                     --> DocumentationReport
      |         |
      |         |-- CodeQualitySkill --> MCP.list_directory()
      |         |                   --> MCP.read_file()
      |         |                   --> CodeQualityReport
      |         |
      |         +-- SecuritySkill --> MCP.search_files()
      |                          --> MCP.read_file()
      |                          --> SecurityReport
      |
      |    [session.state["analysis_bundle"] = AnalysisBundle]
      |
      +-> [ReportAgent]
                |
                | (reads session.state["analysis_bundle"])
                |
                v
          EngineeringReport
          (Markdown + Pydantic JSON)
```

---

## 8. Configuration & Environment

All runtime configuration is supplied via environment variables. No configuration values are hardcoded.

| Variable | Required | Description |
|---|---|---|
| `GITHUB_PAT` | If data_source=github | GitHub Personal Access Token (repo:read scope) |
| `GEMINI_API_KEY` | Yes | Gemini API key for LLM agents |
| `MCP_DATA_SOURCE` | No | Default data source: "github" or "filesystem" |
| `LOG_LEVEL` | No | Logging verbosity: DEBUG, INFO, WARNING (default: INFO) |
| `MAX_FILES_TO_SCAN` | No | Override default max files (default: 200) |

---

## 9. Error Handling Strategy

| Error Type | Handling |
|---|---|
| `ValidationError` (Pydantic) | Caught at pipeline entry; return structured error with exit code 2 |
| `MCPConnectionError` | Retry with exponential backoff (max 3); then surface as `AnalysisError` |
| `MCPRateLimitError` | Backoff and retry; if persistent, partial report with affected dimension marked "unavailable" |
| `SkillExecutionError` | Dimension marked as score=0 with a critical Finding; pipeline continues |
| `PathTraversalError` | Immediate halt; logged as security event; exit code 2 |
| Unhandled exceptions | Caught at pipeline level; structured error report; exit code 1 |

**Design principle**: The pipeline is fault-tolerant at the skill level (one failed skill does not abort all analysis) but fail-fast at the input validation and path security level.

---

## 10. Testing Strategy

### 10.1 Unit Tests

- All Pydantic models: valid/invalid input coverage
- Each skill in isolation using a mock `MCPToolset`
- Security regex patterns against known-positive and known-negative fixtures
- Scoring algorithm correctness

### 10.2 Integration Tests

- Full pipeline run against `evals/repos/well_documented/` using Filesystem MCP
- Full pipeline run against a known public GitHub repo using GitHub MCP (requires PAT in CI secrets)
- Latency benchmarks for P95 targets

### 10.3 Evaluation Tests

- Automated eval runner in `evals/run_evals.py`
- Compares generated reports against golden reports using structured scoring
- Must pass all targets defined in `repopilot_spec.md § 9`

---

## 11. ADK 2.0 Version Constraints

| Dependency | Version Constraint | Rationale |
|---|---|---|
| `google-adk` | `>=2.0.0,<3.0.0` | ADK 2.0 API required |
| `pydantic` | `>=2.0.0` | v2 API used throughout |
| `python` | `>=3.11` | Required for `str | None` syntax and `tomllib` |
| `mcp` | Compatible with ADK 2.0 MCP adapter | Tool protocol compatibility |

---

## 12. Security Architecture Summary

```
[User Input]
     |
     | Pydantic validation (boundary enforcement)
     v
[Pipeline Entry] -- ValidationError? --> [Halt, exit 2]
     |
     | Validated RepoAnalysisRequest
     v
[RepositoryAnalysisAgent]
     |
     | MCP calls ONLY (no direct I/O)
     | ALLOWED_MCP_TOOLS whitelist enforced
     | Path validated against repo_root
     v
[Skills] -- static analysis only, no subprocess, no eval
     |
     | DimensionScore (secrets REDACTED in findings)
     v
[ReportAgent] -- no MCP tools, no I/O, pure synthesis
     |
     v
[EngineeringReport] -- validated Pydantic output
```
