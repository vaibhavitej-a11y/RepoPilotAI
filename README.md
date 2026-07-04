<div align="center">

# 🚀 RepoPilot AI

**An AI-powered multi-agent repository analysis system built with Google's Agent Development Kit (ADK) and Model Context Protocol (MCP).**

Analyze any software repository and receive a comprehensive engineering report covering architecture, code quality, documentation, and security.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#-installation)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](#-license)
[![Built with ADK](https://img.shields.io/badge/built%20with-Google%20ADK-orange)](#-tech-stack)

</div>

---

# Why RepoPilot AI?

Understanding an unfamiliar software repository is one of the most time-consuming tasks in software engineering. Developers often spend hours exploring project structures, reading documentation, identifying architectural patterns, and assessing code quality before they can confidently contribute to or review a project.

RepoPilot AI automates this initial engineering review using a team of specialized AI agents. Instead of relying on a single generic prompt, the system decomposes repository analysis into focused engineering tasks—architecture, code quality, documentation, and security—before synthesizing the results into a comprehensive engineering report.

By combining Google's Agent Development Kit (ADK) with the Model Context Protocol (MCP), RepoPilot AI demonstrates how multiple specialized AI agents can collaborate to perform structured software engineering analysis while maintaining safe, read-only access to repository contents.

---

# What it does

RepoPilot AI analyzes a software repository using multiple specialized AI agents. Each agent focuses on one engineering dimension and independently evaluates the repository through controlled read-only access using MCP.

The generated report includes:

- 🏆 Overall Engineering Score
- 🏗️ Architecture Assessment
- 🧹 Code Quality Review
- 📚 Documentation Evaluation
- 🔒 Security Findings
- ✅ Actionable Recommendations

Example:

```text
📊 Overall Engineering Score: 7.4 / 10.0
├─ Architecture      8.0 / 10.0
├─ Code Quality      6.5 / 10.0
├─ Documentation     7.0 / 10.0
└─ Security          8.0 / 10.0
```

---

# ✨ Features

- Multi-agent repository analysis using Google ADK
- Specialized Architecture, Code Quality, Documentation, and Security agents
- Filesystem and GitHub repository support
- Safe read-only repository exploration through MCP
- Deterministic directory filtering (`.venv`, `.git`, `node_modules`, etc.)
- Hard enforcement of configurable file analysis limits
- Structured outputs using Pydantic models
- Automatic retry and graceful degradation for transient API failures
- Markdown engineering report generation
- CLI-first workflow for local and remote repositories

---

# 🏗️ Architecture

```text
                     RepoPilot CLI
                            │
                            ▼
              Repository Analysis Agent
                    (fan-out / fan-in)
                            │
      ┌───────────┬─────────┴─────────┬───────────┐
      ▼           ▼                   ▼           ▼
Architecture  Documentation      Code Quality   Security
   Skill          Skill             Skill        Skill
      │           │                   │           │
      └───────────┴─────────┬─────────┴───────────┘
                             ▼
                     Report Agent
                    (synthesizer)
                             │
                             ▼
                repopilot_report.md
```

The Repository Analysis Agent coordinates four specialized analysis skills. Each skill independently evaluates one engineering dimension before a Report Agent synthesizes all findings into a single engineering report.

---

# Why Google ADK?

RepoPilot AI is built using Google's Agent Development Kit (ADK), which provides the orchestration layer for coordinating multiple AI agents within a structured workflow.

Using ADK allows RepoPilot AI to:

- Coordinate multiple specialized agents
- Build deterministic workflows
- Exchange structured outputs using Pydantic models
- Integrate external tools through MCP
- Gracefully handle failures and API rate limits

Instead of relying on a single large prompt, ADK enables the project to decompose repository analysis into reusable, specialized engineering tasks.

---

# Why MCP?

RepoPilot AI uses the Model Context Protocol (MCP) to safely expose repository contents to AI agents.

Rather than granting unrestricted filesystem access, MCP provides structured tools for listing directories and reading files while enforcing read-only access.

This design keeps repository analysis modular, secure, and extensible while allowing future integrations such as GitHub repositories without changing the core agent architecture.

---

# 🛠️ Tech Stack

| Category | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Agent Framework | Google Agent Development Kit (ADK) |
| LLM | Gemini |
| Tool Protocol | Model Context Protocol (MCP) |
| Validation | Pydantic v2 |
| Package Manager | uv |
| CLI | Click |

---

# 📁 Project Structure

```text
app/
├── agents/          # Agent orchestration
├── mcp/             # Filesystem & GitHub tool integrations
├── models/          # Pydantic schemas
├── prompts/         # Agent prompts
└── skills/          # Architecture, Documentation, Security & Code Quality skills

docs/
specs/
tests/
```

---

# ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/<your-username>/RepoPilotAI.git
cd RepoPilotAI
```

Install dependencies:

```bash
uv sync
```

Create a `.env` file:

```env
GEMINI_API_KEY=YOUR_API_KEY
GEMINI_MODEL=gemini-2.5-flash
```

---

# 🚀 Usage

Analyze the current repository:

```bash
uv run -m app.main analyze . --max-files 50
```

Analyze another local repository:

```bash
uv run -m app.main analyze path/to/project
```

Analyze a GitHub repository:

```bash
uv run -m app.main analyze owner/repository --source github --branch main
```

---

# 📄 Output

Every analysis produces a Markdown engineering report containing:

- Overall Engineering Score
- Architecture Review
- Code Quality Assessment
- Documentation Evaluation
- Security Findings
- Improvement Recommendations

By default, the report is written to:

```text
repopilot_report.md
```

---

# 🧪 Testing

Run all tests:

```bash
pytest
```

The project includes unit and integration tests covering repository analysis workflows and MCP integration.

---

# Google ADK Concepts Demonstrated

RepoPilot AI demonstrates the following Google ADK concepts:

- Multi-agent orchestration
- Specialized AI agents
- Agent Skills
- Model Context Protocol (MCP)
- Tool-based reasoning
- Structured outputs using Pydantic
- Sequential workflow execution
- Graceful handling of API failures and rate limits

---

# 🔍 Current Limitations

- Depends on Gemini API availability and quota.
- Analysis quality depends on repository completeness.
- Large repositories may require higher API quotas.
- Skills currently execute sequentially to remain within API rate limits.

---

# 🔮 Future Improvements

- Parallel agent execution with adaptive rate limiting
- Git history analysis
- Pull request review generation
- Dependency vulnerability scanning
- Interactive web dashboard
- CI/CD integration
- Support for additional repository providers

---

# 📜 License

Apache License 2.0

---

# 👤 Author

**Vaibhavi Tej**

Built as part of the **Google Agent Development Kit (ADK) Capstone Project** to demonstrate multi-agent software engineering workflows using ADK, MCP, and Gemini.
