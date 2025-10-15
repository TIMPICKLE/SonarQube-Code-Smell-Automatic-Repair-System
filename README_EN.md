# 🤖 SonarQube Code Smell Auto-Fix System

> 🇨🇳 中文版: [README.md](./README.md) | 🌍 English: README_EN.md

<div align="center">

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

</div>

## 📖 Overview

**An intelligent, automation-first code quality management system powered by LangGraph.**

Tired of endless SonarQube code smells piling up? Fed up with fixing repetitive low‑value issues manually? This project exists to solve exactly that. 🎉

This system is **intelligent** and **fully automated**. It can:

- 🔍 Automatically scan unhandled code smells from SonarQube
- 🤖 Generate AI-driven remediation suggestions (Kimi K2 model)
- 🌿 Orchestrate the full lifecycle: branch creation → code modification → PR creation
- 📊 Track cumulative remediation effort for your team
- 💬 Send smart notifications (Feishu group + direct messages)
- 🎯 Precisely map responsibility via email → GUID → OpenID mappings

[Quick Start](#-quick-start) • [Key Features](#-key-features) • [Usage Guide](#-usage-guide) • [Configuration](#-configuration) • [Architecture](#-architecture)

---

## ✨ Key Features

### 🎭 Multi-Agent Collaboration

Seven specialized Agents work together—each with a single responsibility:

| Agent | Role | Highlights |
|-------|------|-----------|
| 🔍 **IssueAnalyzerAgent** | Analyze code smells | Pagination, author filtering, intelligent dedupe |
| 🛠️ **WorkspaceSetupAgent** | Prepare workspace | Auto-create Git branches, environment prep |
| 💡 **SolutionGeneratorAgent** | Propose fixes | AI-driven contextual remediation suggestions |
| ⚙️ **FixExecutorAgent** | Apply changes | Precise file edits, syntax verification |
| 📝 **PullRequestAgent** | Open PRs | Automated PR creation, reviewer assignment |
| 💾 **RecordKeeperAgent** | Persist records | Historical tracking, effort accumulation |
| 🌐 **BrowserLauncherAgent** | Open PR UI | Automatically launches PR page for review |

### 🚀 Powerful Workflow

- ✅ **Paginated queries**: Handles large SonarQube datasets without memory spikes
- ✅ **Author-based filtering**: Only process issues with identifiable owners
- ✅ **Effort accounting**: Aggregates SonarQube effort estimates (minutes)
- ✅ **Dual-channel notifications**: Feishu group + individual DMs
- ✅ **Duplicate avoidance**: Historical record filtering
- ✅ **Robust error handling**: Graceful fallbacks & retries
- ✅ **Rich UI**: TUI built with `rich`

### 🏗️ Tech Stack

- **🧠 AI Engine**: Kimi K2 API (LLM-based suggestion generation)
- **🔄 Workflow Engine**: LangGraph (state graph driven orchestration)
- **🔌 Integration Layer**: MCP (Model Context Protocol)
  - SonarQube MCP Server
  - Azure DevOps MCP Server
- **📱 Notifications**: Feishu Webhook + Lark SDK
- **🐙 VCS Automation**: GitPython

---

## 🎬 Quick Start

### 📋 Prerequisites

- **Python** ≥ 3.8
- **Git** installed and configured
- **Node.js** (for MCP servers; recommended ≥ v16)
- Network access to SonarQube & Azure DevOps

### 📥 Installation

#### 1️⃣ Clone the repository

```bash
git clone https://github.com/your-username/LangGraphSugAgent.git
cd LangGraphSugAgent
```

#### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

Included dependencies:

```text
langgraph==0.2.45       # Workflow engine
langchain==0.3.7        # LLM application framework
requests==2.32.3        # HTTP client
gitpython==3.1.43       # Git automation
rich==13.9.4            # Terminal UI
mcp==1.12.4             # MCP protocol support
lark-oapi==1.0.37       # Feishu SDK
```

> Note: `mcp` SDK enables Python-side MCP connections.

#### 3️⃣ Configure MCP servers

Edit `localJSON/mcp.json`:

```json
{
  "mcpServers": {
    "sonarqube": {
      "command": "npx",
      "args": ["--yes", "sonarqube-mcp-server@latest"],
      "env": {
        "SONARQUBE_URL": "YOUR_SONAR_URL",
        "SONARQUBE_USERNAME": "USERNAME",
        "SONARQUBE_PASSWORD": "PASSWORD"
      }
    },
    "azureDevOps": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@tiberriver256/mcp-server-azure-devops"],
      "env": {
        "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/your-org",
        "AZURE_DEVOPS_AUTH_METHOD": "pat",
        "AZURE_DEVOPS_PAT": "YOUR_PAT",
        "AZURE_DEVOPS_DEFAULT_PROJECT": "YourProject"
      }
    }
  }
}
```

#### 4️⃣ Prepare data files

On first run they will be auto-created if missing:

- `codeSmallList.json` — processed smell records (start with `[]`)
- `emailToGuid.json` — email → Azure DevOps GUID map
- `emialtoOpenId.json` — email → Feishu OpenID map
- `effort_state.json` — effort accumulator (`{"total_Effort_time": 0}`)

#### 5️⃣ Adjust configuration

Edit `config.py` according to your environment (see below).

### 🎮 Run

#### Option A: Windows batch script

Double-click `start.bat`:

```text
====================================
 SonarQube Auto Fix System
====================================

Select an action:
1. Run system tests
2. Show system status
3. Start auto-fix
4. Reset processed records
5. Help
0. Exit
```

#### Option B: Direct Python

```bash
python main.py          # Run orchestrator
python cli.py status    # Show status
python cli.py test      # Run tests
python cli.py reset     # Reset record state
```

#### Option C: CLI dry run

```bash
python cli.py help
python cli.py run --dry-run
```

### ✅ First Run Checklist

1. Run tests: `python cli.py test`
2. Check status: `python cli.py status`
3. Perform dry run: `python cli.py run --dry-run`
4. Launch full run: `python main.py`

---

## ⚙️ Configuration

### 📁 Core Paths (`config.py` excerpt)

```python
class Config:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    MCP_CONFIG_PATH = os.path.join(PROJECT_ROOT, "localJSON", "mcp.json")
    CODE_SMELL_LIST_PATH = os.path.join(PROJECT_ROOT, "localJSON", "codeSmallList.json")
    EMAIL_TO_GUID_PATH = os.path.join(PROJECT_ROOT, "localJSON", "emailToGuid.json")
    EMAIL_TO_OPEN_ID_PATH = os.path.join(PROJECT_ROOT, "localJSON", "emialtoOpenId.json")
    TOTAL_EFFORT_STATE_PATH = os.path.join(PROJECT_ROOT, "localJSON", "effort_state.json")
```

All are absolute paths; customize only if relocating storage.

### 🎯 SonarQube Settings

```python
class Config:
    SONARQUBE_PROJECT_KEY = "yourProject"
    SONARQUBE_BRANCH = "master"
    SONARQUBE_SEVERITIES = ["INFO"]
    SONARQUBE_TYPES = ["CODE_SMELL"]
```

| Field | Description | Allowed | Example |
|-------|-------------|---------|---------|
| `SONARQUBE_PROJECT_KEY` | Project key | Any string | `my-project` |
| `SONARQUBE_BRANCH` | Branch to analyze | Git branch | `master` |
| `SONARQUBE_SEVERITIES` | Severities to include | BLOCKER/CRITICAL/MAJOR/MINOR/INFO | `["INFO","MINOR"]` |
| `SONARQUBE_TYPES` | Issue types | CODE_SMELL/BUG/VULNERABILITY | `["CODE_SMELL"]` |

### 🔷 Azure DevOps

```python
class Config:
    AZURE_DEVOPS_PROJECT = "yourProject"
    AZURE_DEVOPS_REPOSITORY = "yourProject"
    AZURE_DEVOPS_TARGET_BRANCH = "refs/heads/master"
    AZURE_DEVOPS_TASK_ID = "283356"
    DEFAULT_REVIEWER = "87790f0c-0021-4777-886a-ff6f7622a77b"
```

| Field | Description | Format | Notes |
|-------|-------------|--------|-------|
| `AZURE_DEVOPS_PROJECT` | Project name | string | Appears in URL |
| `AZURE_DEVOPS_REPOSITORY` | Repo name | string | Must exist locally |
| `AZURE_DEVOPS_TARGET_BRANCH` | PR target ref | `refs/heads/<branch>` | Usually master/main |
| `AZURE_DEVOPS_TASK_ID` | Work item ID | numeric string | For traceability |
| `DEFAULT_REVIEWER` | Fallback reviewer GUID | GUID | Used if no author mapping |

### 💬 Feishu (Lark) Notifications

```python
class Config:
    FEISHU_WEBHOOK_URL = "https://www.feishu.cn/flow/api/trigger-webhook/xxxxx"
    FEISHU_APP_ID = "cli_xxxxxxxxxxxxxxxxx"
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "<SET_ME>")
```

| Field | Purpose | Retrieval |
|-------|---------|-----------|
| `FEISHU_WEBHOOK_URL` | Group broadcast | Group settings → Bot → Webhook |
| `FEISHU_APP_ID` | App identifier | Feishu open platform |
| `FEISHU_APP_SECRET` | App secret | Keep secret—use env var |

Use Webhook for group messages; App credentials for DMs.

### 🌿 Git Settings

```python
class Config:
    GIT_REPO_PATH = os.path.join(PROJECT_ROOT, "yourProject")
    GIT_BRANCH_NAME_TEMPLATE = "fix-sonar-{smell_key}"
    GIT_COMMIT_MESSAGE_TEMPLATE = "fix: Resolve SonarQube smell {smell_key} - {description}"
```

| Field | Role | Variables | Example |
|-------|------|-----------|---------|
| `GIT_BRANCH_NAME_TEMPLATE` | Branch naming | `{smell_key}` | `fix-sonar-AYzqY123` |
| `GIT_COMMIT_MESSAGE_TEMPLATE` | Commit message | `{smell_key}`, `{description}` | `fix: Resolve SonarQube smell AYz... - Remove unused var` |

### 📝 Pull Request Templates

```python
class Config:
    PR_TITLE_TEMPLATE = "fix: Resolve SonarQube smell {smell_key}"
    PR_DESCRIPTION_TEMPLATE = """
## SonarQube Code Smell Fix

**Smell Key:** {smell_key}
**Description:** {description}
**File:** {file_path}

### Context
- Task ID: {task_id}
- Generated by Auto-Fix System

### Checklist
- [x] Patch applied
- [x] Syntax validated
- [ ] Manual review complete
"""
```

### 📊 Effort Tracking

Each SonarQube issue has an `effort` (estimated minutes). The system sums these into `effort_state.json`:

```json
{ "total_Effort_time": 1250 }
```

Used in notifications to show cumulative impact.

---

## 📄 Data File Details

### 1️⃣ `codeSmallList.json`

Tracks processed smells to avoid duplicate work.

```json
[
  {
    "key": "AYzqY1234567890",
    "rule": "csharpsquid:S1481",
    "severity": "INFO",
    "component": "yourProject:src/Controllers/UserController.cs",
    "line": 45,
    "message": "Remove this unused private field 'userName'.",
    "author": "john.doe@company.com",
    "creationDate": "2025-10-15T10:30:00+0800",
    "processedDate": "2025-10-15T14:20:00+0800",
    "status": "FIXED",
    "prUrl": "https://azure-devops.com/project/pullrequest/12345"
  }
]
```

### 2️⃣ `emailToGuid.json`

Email → Azure DevOps GUID mapping for PR reviewers.

### 3️⃣ `emialtoOpenId.json`

Email → Feishu OpenID for DM notifications.

### 4️⃣ `effort_state.json`

Cumulative minutes of resolved effort.

### 5️⃣ `mcp.json`

External MCP service definitions (SonarQube, Azure DevOps, etc.).

---

## 🏗️ Architecture

### 🔄 Workflow

```text
SonarQube Scan
   │
   ▼
IssueAnalyzerAgent (filter/paginate/dedupe)
   │
   ▼
WorkspaceSetupAgent (branch/env)
   │
   ▼
SolutionGeneratorAgent (AI proposal)
   │
   ▼
FixExecutorAgent (apply + commit + push)
   │
   ▼
PullRequestAgent (PR + notifications)
   │
   ▼
RecordKeeperAgent (persist + effort)
   │
   ▼
BrowserLauncherAgent (open PR UI)
```

### 🧩 Logical Layout

```text
┌────────────────────────────────────────┐
│      SonarQubeAutoFixOrchestrator      │
└───────────────┬────────────────────────┘
                │
     ┌──────────┴──────────┐
     │                     │
 LangGraph StateGraph   MCP Clients
     │                     │
  7 Agents          SonarQube / Azure DevOps
     │                     │
  Utils Layer: Git / File / LLM / Notification
```

---

## 📚 Usage Guide

### 🐛 Common Issues

**MCP connection failed**:
1. Verify `mcp.json`
2. Check service reachability
3. Validate credentials / PAT permissions
4. View server logs

**No unprocessed smells**:
- All done already
- Filters too restrictive
- Missing author

Reset tracking:

```bash
python cli.py reset
```

**Git errors**:
- Not a repository → Check `GIT_REPO_PATH`
- Permission denied → Fix credentials
- Merge conflict → Resolve manually then retry

**PR creation failed**:
- PAT scope insufficient
- Target branch missing
- Reviewer GUID invalid

**Feishu notification failed**:
- Webhook revoked
- App credentials invalid
- OpenID mapping incomplete

### 💡 Best Practices

Incremental rollout:

```text
Day 1: INFO
Day 2: MINOR
Day 3: MAJOR & above
```

Backups:

```bash
copy localJSON\codeSmallList.json localJSON\codeSmallList.backup.json
copy localJSON\effort_state.json localJSON\effort_state.backup.json
```

Review cadence:
- Periodically audit generated PRs
- Monitor Feishu delivery
- Analyze cumulative effort metrics

---

## 🎓 Resources

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **SonarQube Web API**: https://docs.sonarqube.org/latest/extend/web-api/
- **Azure DevOps REST**: https://learn.microsoft.com/en-us/rest/api/azure/devops/
- **Feishu Platform**: https://open.feishu.cn/document/

---

## 🤝 Contributing

We welcome contributions! ✨

**How to contribute**:
1. Open an Issue (bug/feature)
2. Fork & branch: `git checkout -b feature/amazing-feature`
3. Commit: `git commit -m "✨ Add amazing feature"`
4. Push & open PR

**Standards**:
- PEP 8 style
- Chinese or bilingual docstrings (if aligning with existing codebase)
- Type hints encouraged
- Include unit tests

---

## 📜 License

Released under the **MIT License**. You are free to use, modify, distribute, and private-host.

---

## 🙏 Acknowledgements

- LangChain & LangGraph
- Kimi K2 Model
- MCP Protocol
- SonarQube
- Azure DevOps
- Feishu
- Rich

---

## 📮 Contact

- **GitHub Issues**: https://github.com/your-username/LangGraphSugAgent/issues
- **Email**: your-email@example.com

---

## ⭐ Star History

If this project helps you, please give it a ⭐—your support keeps it evolving! 💪

---

<div align="center">
Made with ❤️ by Your Name / Team  
Current Version: v1.1.0 | Last Updated: 2025-10-15  

⬆ Back to Top
</div>
