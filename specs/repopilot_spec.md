# RepoPilot AI — Product Specification

**Version**: 1.0.0-spec  
**Status**: Draft  
**Created**: 2026-07-03  
**Framework**: Google Agent Development Kit (ADK) 2.0

---

## 1. Overview

RepoPilot AI is an **AI-powered Software Engineering Intelligence Assistant** built on ADK 2.0. Given a GitHub repository URL or a local filesystem path, it performs a structured, read-only analysis across four engineering dimensions — architecture, documentation, code quality, and basic security — and produces a comprehensive, human-readable engineering report.

The system is composed of **exactly two agents** orchestrated by ADK's pipeline primitives:

| Agent | Role |
|---|---|
| `RepositoryAnalysisAgent` | Data gathering and multi-dimensional analysis via Agent Skills |
| `ReportAgent` | Structured synthesis and final report generation |

All analysis is **read-only**. No code is executed from the repository being analyzed. No secrets or tokens from the target repository are stored.

---

## 2. Goals & Non-Goals

### 2.1 Goals

- Provide actionable engineering insights for any public or permissioned GitHub repository.
- Support both **GitHub MCP** (remote API-based) and **Filesystem MCP** (local clone) as interchangeable data sources.
- Generate a deterministic, structured Markdown report that can be embedded in CI pipelines, wikis, or PR comments.
- Be secure by design: all external inputs are validated via Pydantic before any agent action.
- Support evaluation-driven development with measurable, automated success criteria.

### 2.2 Non-Goals

- Executing code, running tests, or building the analyzed repository.
- Storing or indexing repository content beyond the lifetime of a single analysis session.
- Writing back to any repository (no push, PR creation, or issue filing in scope for v1.0).
- Real-time monitoring or webhook-triggered analysis (future roadmap).

---

## 3. User Stories

### US-001 — Developer Self-Analysis
> As a **developer**, I want to point RepoPilot at my GitHub repo so I can receive a structured engineering report covering architecture health, documentation coverage, code quality signals, and security posture — without granting write access.

**Acceptance Criteria:**
- System accepts a GitHub URL or a local filesystem path as the sole required input.
- Report is generated within 120 seconds for repositories up to 500 files.
- Report sections map 1-to-1 with the four analysis dimensions.
- No repository credentials are persisted after the session ends.

### US-002 — CI/CD Integration
> As a **platform engineer**, I want to run RepoPilot in a CI pipeline and receive a structured JSON-compatible report alongside the Markdown version so automated gates can act on score thresholds.

**Acceptance Criteria:**
- Agent pipeline accepts a `RepoAnalysisRequest` Pydantic model as input.
- Output includes both a Markdown report and a structured `EngineeringReport` Pydantic model.
- Exit codes follow Unix conventions: `0` = success, `1` = analysis errors, `2` = input validation failure.

### US-003 — Security Review
> As a **security engineer**, I want RepoPilot to flag obvious security anti-patterns (hardcoded secrets patterns, dangerous dependency versions, missing security policy files) without executing any code from the target repo.

**Acceptance Criteria:**
- Security skill operates entirely on static file content (text matching, pattern detection).
- No subprocess calls or `eval`/`exec` constructs are used during analysis.
- All tool calls to MCP servers are read-only (GET-equivalent operations only).

### US-004 — Multi-Source Support
> As a **user**, I want to analyze either a GitHub-hosted repository via the GitHub MCP or a locally cloned repository via the Filesystem MCP, using the same agent interface.

**Acceptance Criteria:**
- A `data_source` field on `RepoAnalysisRequest` selects between `"github"` and `"filesystem"`.
- Both sources produce equivalent structured analysis output.
- Source selection does not change the agent interface or report schema.

---

## 4. Analysis Dimensions

The `RepositoryAnalysisAgent` executes the following four skills. Each skill returns a typed Pydantic model.

### 4.1 Architecture Analysis (ArchitectureSkill)

| Signal | Description |
|---|---|
| Language detection | Top languages by file count and LOC |
| Framework fingerprinting | Detection of known frameworks via config file patterns |
| Dependency graph summary | Key direct dependencies from lockfiles / manifests |
| Project structure score | Depth, separation of concerns, presence of src/, tests/, docs/ |
| Entrypoint discovery | Detection of main, index, app entry files |

**Output model**: `ArchitectureReport`

### 4.2 Documentation Analysis (DocumentationSkill)

| Signal | Description |
|---|---|
| README quality | Existence, length, section coverage (install, usage, contributing, license) |
| Inline doc coverage | Presence of docstrings / JSDoc in sampled source files |
| Changelog / CHANGELOG | Existence and recency of a changelog |
| API documentation | Presence of OpenAPI / Swagger specs or doc generation config |
| Contributing guide | CONTRIBUTING.md and CODE_OF_CONDUCT.md existence |

**Output model**: `DocumentationReport`

### 4.3 Code Quality Analysis (CodeQualitySkill)

| Signal | Description |
|---|---|
| Linter configuration | Presence of .eslintrc, pyproject.toml [tool.ruff], .rubocop.yml, etc. |
| Test coverage signals | Presence of test directories, test files ratio to source files |
| CI/CD configuration | Presence and basic structure of .github/workflows, Jenkinsfile, etc. |
| Code complexity proxy | Average file length, presence of files >500 LOC |
| Dependency freshness | Flag dependencies pinned to obviously old major versions |

**Output model**: `CodeQualityReport`

### 4.4 Security Analysis (SecuritySkill)

| Signal | Description |
|---|---|
| Secret pattern detection | Static regex scan for common secret/token patterns in non-binary files |
| Security policy | Presence of SECURITY.md |
| Dependency advisories | Cross-reference known CVE-flagged package names from a static list |
| Permissions model | Review of CI workflow permissions declarations |
| .gitignore hygiene | Check for common secrets files excluded (.env, *.pem, etc.) |

**Output model**: `SecurityReport`

> **Security constraint**: All pattern matching is purely static (regex on file content). No subprocess execution. No network calls to CVE databases at runtime (offline static list only in v1.0).

---

## 5. Agent Skills Specification

Skills are implemented as Python callables attached to the RepositoryAnalysisAgent and sharing its MCP tool context.

```
RepositoryAnalysisAgent
+-- ArchitectureSkill      -> ArchitectureReport
+-- DocumentationSkill     -> DocumentationReport
+-- CodeQualitySkill       -> CodeQualityReport
+-- SecuritySkill          -> SecurityReport
```

Skills **must**:
- Accept only validated Pydantic models as arguments.
- Return only validated Pydantic models.
- Use MCP tool calls exclusively for file access (no direct open() on arbitrary paths).
- Be individually unit-testable in isolation.

---

## 6. Data Models (Pydantic v2)

### 6.1 Input

```python
class RepoAnalysisRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    data_source: Literal["github", "filesystem"]
    repo_target: str          # "owner/repo" or full URL or absolute path
    branch: str = "main"
    max_files_to_scan: int = Field(default=200, ge=1, le=1000)
    include_dimensions: list[AnalysisDimension] = Field(
        default_factory=lambda: list(AnalysisDimension)
    )

class AnalysisDimension(str, Enum):
    ARCHITECTURE  = "architecture"
    DOCUMENTATION = "documentation"
    CODE_QUALITY  = "code_quality"
    SECURITY      = "security"
```

### 6.2 Intermediate (per-skill output)

```python
class DimensionScore(BaseModel):
    dimension: AnalysisDimension
    score: float = Field(ge=0.0, le=10.0)
    findings: list[Finding]
    raw_signals: dict[str, Any]

class Finding(BaseModel):
    severity: Literal["info", "warning", "critical"]
    message: str
    file_path: str | None = None
    line_number: int | None = None
```

### 6.3 Final Output

```python
class EngineeringReport(BaseModel):
    repo_target: str
    analyzed_at: datetime
    data_source: Literal["github", "filesystem"]
    overall_score: float = Field(ge=0.0, le=10.0)
    dimensions: list[DimensionScore]
    executive_summary: str
    recommendations: list[str]
    markdown_report: str
```

---

## 7. MCP Tool Contracts

The agents interact with the repository exclusively through MCP tools. The tool interface is identical regardless of which MCP server is active.

| Tool Name | Permission | Description |
|---|---|---|
| `read_file` | READ | Read raw content of a single file by path |
| `list_directory` | READ | List files and subdirectories under a path |
| `search_files` | READ | Regex/glob search across repository files |
| `get_file_metadata` | READ | File size, extension, last-modified timestamp |

> **Constraint**: No MCP tool with write, delete, execute, or network-fetch semantics is permitted in the agent's tool registry.

---

## 8. Security Design Principles

1. **Input validation at boundary**: Every user-supplied string passes through a Pydantic model before reaching any agent or MCP call. Invalid inputs raise `ValidationError` and halt the pipeline.
2. **Read-only MCP surface**: The MCP tool registry for both agents is restricted to read-only operations. This is enforced at configuration time, not runtime.
3. **No code execution**: No `subprocess`, `exec`, `eval`, or dynamic import of repository code. Skills perform static analysis only.
4. **Path traversal prevention**: All file paths returned by MCP tools are validated against the declared repository root before use.
5. **Secret non-persistence**: Any secret patterns detected by `SecuritySkill` are reported as redacted finding messages; the literal matched string is never stored or logged.
6. **Least-privilege MCP**: When using GitHub MCP, only the `repo:read` OAuth scope is requested. When using Filesystem MCP, the root is clamped to the declared repo path.

---

## 9. Evaluation Criteria

RepoPilot uses evaluation-driven development. The following metrics define a passing implementation.

| Metric | Target | Measurement |
|---|---|---|
| Dimension Coverage | All 4 dimensions populated in every report | Automated eval: assert len(report.dimensions) == 4 |
| Score Accuracy | Scoring on known reference repos within +/-1.0 of human baseline | Eval suite: 5 labeled reference repos |
| Security False Negative Rate | < 10% on known-bad repos | Eval: repos with planted secret patterns |
| Latency (GitHub MCP) | P95 < 120s for repos <= 200 files | Integration test timing |
| Latency (Filesystem MCP) | P95 < 30s for repos <= 200 files | Integration test timing |
| Report Completeness | All 7 required sections present in Markdown report | Regex eval on output |
| Pydantic Validation Pass Rate | 100% — no unvalidated data enters agents | Unit tests on all models |
| No Code Execution | Zero subprocess / exec calls in agent trace | Static analysis + eval trace inspection |

### 9.1 Evaluation Datasets

| Dataset | Description | Use |
|---|---|---|
| `evals/repos/well_documented/` | Reference repo with high scores across all dimensions | Sanity / regression |
| `evals/repos/minimal/` | Bare-bones repo with no docs, tests, or CI | Low-score baseline |
| `evals/repos/secrets_planted/` | Repo with intentionally injected secret patterns | Security skill eval |
| `evals/repos/monorepo/` | Large multi-language monorepo structure | Stress / edge case |
| `evals/golden_reports/` | Human-labeled expected reports for above repos | Score comparison |

---

## 10. Report Structure (Markdown Template)

Every generated report must include the following seven sections in order:

1. **Header** — repo name, analysis timestamp, data source, overall score badge
2. **Executive Summary** — 3-5 sentence prose summary
3. **Architecture Analysis** — score, findings table, language breakdown
4. **Documentation Analysis** — score, findings table, coverage checklist
5. **Code Quality Analysis** — score, findings table, CI/CD status
6. **Security Analysis** — score, findings table (with redacted secrets), recommendations
7. **Recommendations** — prioritized action list (critical -> warning -> info)

---

## 11. Versioning & Change Policy

- This spec is versioned alongside the codebase in `specs/`.
- Any change to a Pydantic model interface requires a spec version bump and a migration note.
- Evaluation baselines must be re-validated after any change to skill scoring logic.
- The `repopilot.feature` BDD file is the authoritative source of behavioral truth; code must conform to it, not vice versa.
