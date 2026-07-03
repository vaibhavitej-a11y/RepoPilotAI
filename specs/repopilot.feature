# Feature: RepoPilot AI — Software Engineering Intelligence Assistant
#
# This file is the authoritative BDD specification for RepoPilot AI.
# All agent behavior must conform to these scenarios.
# Implementation MUST NOT be changed to make tests pass by weakening assertions.
#
# Format: Gherkin (compatible with pytest-bdd / behave)
# Last updated: 2026-07-03

Feature: Repository Analysis and Engineering Report Generation
  As an engineering team
  I want RepoPilot AI to analyze software repositories and generate structured engineering reports
  So that I can understand architectural health, documentation coverage, code quality, and security posture

  Background:
    Given the RepoPilot AI pipeline is initialized with ADK 2.0
    And the MCP toolset is configured with read-only permissions only
    And no write, execute, or delete MCP tools are registered

  # ---------------------------------------------------------------------------
  # INPUT VALIDATION
  # ---------------------------------------------------------------------------

  Scenario: Valid GitHub repository request is accepted
    Given a user provides a GitHub repository target "owner/repo"
    And the data source is "github"
    And the branch is "main"
    When the request is submitted to the pipeline
    Then the request passes Pydantic validation without errors
    And the pipeline begins analysis

  Scenario: Valid filesystem repository request is accepted
    Given a user provides a local filesystem path "/path/to/local/repo"
    And the data source is "filesystem"
    When the request is submitted to the pipeline
    Then the request passes Pydantic validation without errors
    And the pipeline begins analysis

  Scenario: Invalid repository target is rejected at input boundary
    Given a user provides an empty repository target ""
    When the request is submitted to the pipeline
    Then a Pydantic ValidationError is raised
    And the pipeline does not begin analysis
    And the process exits with code 2

  Scenario: max_files_to_scan above limit is rejected
    Given a user provides max_files_to_scan of 9999
    When the request is submitted to the pipeline
    Then a Pydantic ValidationError is raised indicating the value exceeds 1000

  Scenario: max_files_to_scan below minimum is rejected
    Given a user provides max_files_to_scan of 0
    When the request is submitted to the pipeline
    Then a Pydantic ValidationError is raised indicating the value is less than 1

  Scenario: Unknown data source type is rejected
    Given a user provides data_source as "sftp"
    When the request is submitted to the pipeline
    Then a Pydantic ValidationError is raised
    And the pipeline does not begin analysis

  # ---------------------------------------------------------------------------
  # AGENT PIPELINE STRUCTURE
  # ---------------------------------------------------------------------------

  Scenario: Pipeline consists of exactly two agents
    When the RepoPilot pipeline is inspected
    Then it contains exactly 2 sub-agents
    And the first agent is named "repository_analysis_agent"
    And the second agent is named "report_agent"

  Scenario: RepositoryAnalysisAgent runs before ReportAgent
    Given a valid repository analysis request
    When the pipeline executes
    Then "repository_analysis_agent" completes before "report_agent" begins
    And session state contains "analysis_bundle" before "report_agent" is invoked

  Scenario: ReportAgent has no MCP tools registered
    When the pipeline is inspected
    Then the "report_agent" has zero MCP tools in its tool registry

  Scenario: RepositoryAnalysisAgent has exactly four skills
    When the pipeline is inspected
    Then the "repository_analysis_agent" has exactly 4 skills registered
    And the skills are named "architecture_skill", "documentation_skill", "code_quality_skill", "security_skill"

  # ---------------------------------------------------------------------------
  # ARCHITECTURE SKILL
  # ---------------------------------------------------------------------------

  Scenario: Architecture skill detects primary programming language
    Given a repository containing primarily Python source files
    When the architecture skill executes
    Then the ArchitectureReport lists "Python" as the primary language
    And the architecture dimension score is between 0.0 and 10.0

  Scenario: Architecture skill detects presence of standard directory structure
    Given a repository containing "src/", "tests/", and "docs/" directories
    When the architecture skill executes
    Then the ArchitectureReport includes a finding noting structured layout
    And the architecture score is higher than for a repository without those directories

  Scenario: Architecture skill handles repository with no recognizable structure
    Given a repository with only a single file at the root
    When the architecture skill executes
    Then the ArchitectureReport includes a "warning" severity finding about minimal structure
    And the architecture score is less than 5.0

  Scenario: Architecture skill identifies dependency manifest files
    Given a repository containing "pyproject.toml" or "package.json" or "Gemfile"
    When the architecture skill executes
    Then the ArchitectureReport includes detected dependency manifest files

  # ---------------------------------------------------------------------------
  # DOCUMENTATION SKILL
  # ---------------------------------------------------------------------------

  Scenario: Documentation skill detects a well-formed README
    Given a repository with a README.md longer than 500 characters
    And the README contains sections for installation, usage, and license
    When the documentation skill executes
    Then the DocumentationReport marks README quality as "good"
    And the documentation score is at least 6.0

  Scenario: Documentation skill flags missing README
    Given a repository with no README file at the root
    When the documentation skill executes
    Then the DocumentationReport includes a "critical" severity finding about missing README
    And the documentation score is less than 4.0

  Scenario: Documentation skill detects CHANGELOG presence
    Given a repository containing a "CHANGELOG.md" or "CHANGELOG" file
    When the documentation skill executes
    Then the DocumentationReport marks changelog as "present"

  Scenario: Documentation skill detects contributing guide
    Given a repository containing "CONTRIBUTING.md"
    When the documentation skill executes
    Then the DocumentationReport marks contributing guide as "present"

  Scenario: Documentation skill flags absence of inline docstrings
    Given a repository with Python source files containing no docstrings
    When the documentation skill executes
    Then the DocumentationReport includes a "warning" severity finding about missing inline documentation

  # ---------------------------------------------------------------------------
  # CODE QUALITY SKILL
  # ---------------------------------------------------------------------------

  Scenario: Code quality skill detects linter configuration
    Given a repository containing ".eslintrc" or "pyproject.toml" with "[tool.ruff]"
    When the code quality skill executes
    Then the CodeQualityReport marks linter configuration as "present"
    And the code quality score receives a positive contribution from this signal

  Scenario: Code quality skill detects CI/CD pipeline configuration
    Given a repository containing ".github/workflows/" with at least one YAML file
    When the code quality skill executes
    Then the CodeQualityReport marks CI/CD as "configured"
    And the code quality score is at least 5.0

  Scenario: Code quality skill flags absence of test files
    Given a repository with no files matching "test_*.py" or "*_test.py" or "*.spec.*"
    When the code quality skill executes
    Then the CodeQualityReport includes a "warning" severity finding about missing tests
    And the code quality score is less than 5.0

  Scenario: Code quality skill detects oversized files
    Given a repository containing a source file with more than 500 lines
    When the code quality skill executes
    Then the CodeQualityReport includes an "info" severity finding about the oversized file
    And the finding includes the file path

  Scenario: Code quality skill measures test-to-source file ratio
    Given a repository with 10 source files and 8 test files
    When the code quality skill executes
    Then the CodeQualityReport raw_signals contains a "test_ratio" value of approximately 0.8

  # ---------------------------------------------------------------------------
  # SECURITY SKILL
  # ---------------------------------------------------------------------------

  Scenario: Security skill detects hardcoded secret pattern
    Given a repository containing a file with the pattern "AWS_SECRET_ACCESS_KEY=AKIA..."
    When the security skill executes
    Then the SecurityReport includes a "critical" severity finding about a potential hardcoded secret
    And the finding message does NOT contain the literal matched secret value
    And the finding includes the file path where the pattern was detected

  Scenario: Security skill detects missing SECURITY.md
    Given a repository with no "SECURITY.md" file
    When the security skill executes
    Then the SecurityReport includes a "warning" severity finding about missing security policy
    And the security score is reduced

  Scenario: Security skill detects .gitignore hygiene
    Given a repository with a ".gitignore" file that excludes ".env" and "*.pem"
    When the security skill executes
    Then the SecurityReport marks gitignore hygiene as "good"

  Scenario: Security skill flags missing .gitignore
    Given a repository with no ".gitignore" file
    When the security skill executes
    Then the SecurityReport includes a "warning" severity finding about missing .gitignore

  Scenario: Security skill detects CI workflow missing permissions declaration
    Given a repository with a GitHub Actions workflow file that has no "permissions:" key
    When the security skill executes
    Then the SecurityReport includes an "info" severity finding about undeclared workflow permissions

  Scenario: Security skill does not execute any subprocess
    Given a repository containing executable scripts
    When the security skill executes
    Then no subprocess is spawned
    And no shell command is invoked
    And analysis is completed using static file content only

  # ---------------------------------------------------------------------------
  # REPORT GENERATION
  # ---------------------------------------------------------------------------

  Scenario: Engineering report contains all seven required sections
    Given a complete AnalysisBundle with all four dimension scores
    When the report agent executes
    Then the generated Markdown report contains a "Header" section
    And the generated Markdown report contains an "Executive Summary" section
    And the generated Markdown report contains an "Architecture Analysis" section
    And the generated Markdown report contains a "Documentation Analysis" section
    And the generated Markdown report contains a "Code Quality Analysis" section
    And the generated Markdown report contains a "Security Analysis" section
    And the generated Markdown report contains a "Recommendations" section

  Scenario: Overall score is computed as mean of dimension scores
    Given dimension scores of 8.0 (architecture), 6.0 (documentation), 7.0 (code quality), 5.0 (security)
    When the report agent computes the overall score
    Then the overall score is 6.5

  Scenario: Recommendations are prioritized by severity
    Given an AnalysisBundle containing "critical", "warning", and "info" findings
    When the report agent generates recommendations
    Then the recommendations list begins with critical-severity items
    And warning-severity items appear before info-severity items

  Scenario: EngineeringReport is a valid Pydantic model
    Given a complete pipeline execution
    When the final output is retrieved from session state
    Then it can be deserialized into an EngineeringReport Pydantic model without errors
    And all required fields are populated

  Scenario: Report includes analysis timestamp
    Given a complete pipeline execution
    When the final EngineeringReport is inspected
    Then the "analyzed_at" field is a valid ISO 8601 datetime
    And the "analyzed_at" timestamp is within 10 seconds of the pipeline start time

  # ---------------------------------------------------------------------------
  # MULTI-SOURCE SUPPORT
  # ---------------------------------------------------------------------------

  Scenario: GitHub MCP and Filesystem MCP produce equivalent report structure
    Given the same repository content available via both GitHub MCP and Filesystem MCP
    When the pipeline is run with data_source="github"
    And the pipeline is run with data_source="filesystem"
    Then both reports contain the same four dimension sections
    And dimension scores differ by no more than 1.0 between sources

  Scenario: Switching data source does not change the agent interface
    Given a RepoAnalysisRequest with data_source="github"
    And a RepoAnalysisRequest with data_source="filesystem"
    When both are submitted to the pipeline
    Then both produce an EngineeringReport with identical schema

  # ---------------------------------------------------------------------------
  # SECURITY CONSTRAINTS
  # ---------------------------------------------------------------------------

  Scenario: No write MCP tool is accessible to any agent
    When the pipeline tool registry is inspected
    Then no tool with write semantics is registered for any agent
    And no tool with delete semantics is registered for any agent
    And no tool with execute semantics is registered for any agent

  Scenario: Path traversal attempt is rejected
    Given an attacker provides a file path containing "../../../etc/passwd"
    When the path is processed by the MCP tool layer
    Then the path traversal attempt is detected and rejected
    And a PathTraversalError is raised
    And the pipeline exits with code 2

  Scenario: Secret pattern match is never stored verbatim
    Given a repository containing a file with a hardcoded API key
    When the security skill processes the file
    Then the raw secret value does not appear in any Finding message
    And the raw secret value does not appear in the EngineeringReport JSON
    And the raw secret value does not appear in application logs

  # ---------------------------------------------------------------------------
  # PERFORMANCE & RELIABILITY
  # ---------------------------------------------------------------------------

  Scenario: Analysis completes within latency target for Filesystem MCP
    Given a repository with 200 files available via Filesystem MCP
    When the pipeline executes
    Then the total execution time is less than 30 seconds

  Scenario: Analysis completes within latency target for GitHub MCP
    Given a repository with 200 files available via GitHub MCP
    When the pipeline executes
    Then the total execution time is less than 120 seconds

  Scenario: A skill failure does not abort the entire pipeline
    Given one skill raises a SkillExecutionError during analysis
    When the pipeline continues execution
    Then the remaining skills still execute
    And the affected dimension is marked with score 0.0 and a "critical" finding
    And the report is still generated with the available dimensions

  Scenario: MCP connection failure triggers retry with backoff
    Given the MCP server is temporarily unavailable
    When an MCP tool call fails
    Then the system retries up to 3 times with exponential backoff
    And if all retries fail, an MCPConnectionError is surfaced in the report

  # ---------------------------------------------------------------------------
  # EVALUATION
  # ---------------------------------------------------------------------------

  Scenario Outline: Score accuracy on reference repositories
    Given the reference repository "<repo_name>"
    When the pipeline analyzes the repository
    Then the "<dimension>" score is within 1.0 of the human baseline "<baseline_score>"

    Examples:
      | repo_name        | dimension     | baseline_score |
      | well_documented  | architecture  | 8.5            |
      | well_documented  | documentation | 9.0            |
      | well_documented  | code_quality  | 8.0            |
      | well_documented  | security      | 7.5            |
      | minimal          | architecture  | 3.0            |
      | minimal          | documentation | 1.0            |
      | minimal          | code_quality  | 2.0            |
      | minimal          | security      | 2.5            |

  Scenario: Security false negative rate is below threshold
    Given the "secrets_planted" reference repository with 10 known secret patterns
    When the security skill executes
    Then at least 9 of the 10 secret patterns are detected
    And the false negative rate is less than 10%
