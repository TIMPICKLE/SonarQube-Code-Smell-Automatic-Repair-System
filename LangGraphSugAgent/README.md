


# 🤖 SonarQube 代码异味自动修复系统

> 🌍 English version: [README_EN.md](./README_EN.md)

<div align="center">

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)

![Python](https://img.shields.io/badge/python-3.8+-green.svg)

![License](https://img.shields.io/badge/license-MIT-yellow.svg)

![Status](https://img.shields.io/badge/status-active-success.svg)

</div>

## 📖 项目简介

**一个基于 LangGraph 的智能化代码质量管理系统 🎯**

嘿！👋 欢迎来到 SonarQube 代码异味自动修复系统！

你是否曾经为 SonarQube 中堆积如山的代码异味而头疼？是否厌倦了手动修复这些重复性的代码质量问题？这个项目就是为你而生的！🎉

这是一个**智能化、自动化**的代码质量管理系统，它能够：

- 🔍 **自动扫描** SonarQube 中未处理的代码异味
- 🤖 **AI 驱动修复**：利用 Kimi K2 大模型智能生成修复方案
- 🌿 **全流程自动化**：从创建分支、代码修复到 PR 创建一气呵成
- 📊 **工作量统计**：自动追踪团队修复代码异味的累计工作量
- 💬 **智能通知**：通过飞书群组和私信精准推送给责任人
- 🎯 **精准分配**：基于邮箱→GUID→OpenID映射精确推送

[快速开始](#-快速开始) • [核心特性](#-核心特性) • [使用指南](#-使用指南) • [配置说明](#-配置说明) • [架构设计](#-架构设计)

---

## ✨ 核心特性

### 🎭 多 Agent 智能协作

系统采用 **7 个专业 Agent** 分工协作，每个 Agent 各司其职：

| Agent                      | 职责           | 亮点                               |
| -------------------------- | -------------- | ---------------------------------- |
| 🔍 **IssueAnalyzerAgent**   | 分析代码异味   | 支持分页查询、作者过滤、智能去重     |
| 🛠️ **WorkspaceSetupAgent**  | 设置工作区     | 自动创建 Git 分支、环境准备          |
| 💡 **SolutionGeneratorAgent** | 生成修复方案   | AI 驱动的智能修复建议                |
| ⚙️ **FixExecutorAgent**     | 执行代码修复   | 精确的代码变更、语法验证             |
| 📝 **PullRequestAgent**     | 创建拉取请求   | 自动 PR、智能审查者分配             |
| 💾 **RecordKeeperAgent**    | 保存处理记录   | 持久化追踪、历史管理                 |
| 🌐 **BrowserLauncherAgent**  | 打开浏览器     | 自动打开 PR 页面供审查               |

### 🚀 强大功能

- ✅ **分页智能查询**：支持处理海量代码异味，分页遍历避免内存溢出
- ✅ **作者精准过滤**：只处理有明确负责人的异味，确保责任到人
- ✅ **工作量统计系统**：实时追踪并累计团队修复代码的工作量（Effort）
- ✅ **双通道通知**：飞书群组广播 + 个人私信，确保消息送达
- ✅ **智能去重机制**：基于历史记录自动过滤已处理的异味
- ✅ **优雅错误处理**：完善的异常捕获和降级策略
- ✅ **美观的 UI**：基于 Rich 库的命令行界面，直观易用

### 🏗️ 技术栈

- **🧠 AI 引擎**：Kimi K2 API - 提供智能修复建议
- **🔄 工作流引擎**：LangGraph - 状态机管理和多 Agent 协作
- **🔌 服务集成**：MCP (Model Context Protocol) - 标准化外部服务接口
  - SonarQube MCP Server - 代码质量分析
  - Azure DevOps MCP Server - 项目管理和 CI/CD
- **📱 通知服务**：飞书 Webhook + Lark SDK - 团队协作通知
- **🐙 版本控制**：GitPython - Git 操作自动化

---

## 🎬 快速开始

### 📋 环境要求

在开始之前，请确保你的系统满足以下要求：

- **Python**: 3.8 或更高版本 🐍
- **Git**: 已安装并配置好 🔧
- **Node.js**: 用于运行 MCP 服务器（推荐 v16+）📦
- **网络**: 能够访问 SonarQube 和 Azure DevOps 服务 🌐

### 📥 安装步骤

#### 1️⃣ 克隆仓库

````bash
git clone https://github.com/your-username/LangGraphSugAgent.git
cd LangGraphSugAgent
````

#### 2️⃣ 安装 Python 依赖

````bash
pip install -r requirements.txt
````

**依赖包含：**

````text
langgraph==0.2.45        # 工作流引擎
langchain==0.3.7         # LLM 应用框架
requests==2.32.3         # HTTP 客户端
gitpython==3.1.43        # Git 操作
rich==13.9.4             # 命令行 UI
mcp==1.12.4              # MCP 协议支持
lark-oapi==1.0.37        # 飞书 SDK
````

> 提示：依赖列表已包含 `mcp` SDK，用于在Python侧建立MCP协议连接。

#### 3️⃣ 配置 MCP 服务器

编辑 mcp.json 文件，配置你的服务连接信息：

````json
{
  "mcpServers": {
    "sonarqube": {
      "command": "npx",
      "args": ["--yes", "sonarqube-mcp-server@latest"],
      "env": {
        "SONARQUBE_URL": "你的SonarQube地址",
        "SONARQUBE_USERNAME": "用户名",
        "SONARQUBE_PASSWORD": "密码"
      }
    },
    "azureDevOps": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@tiberriver256/mcp-server-azure-devops"],
      "env": {
        "AZURE_DEVOPS_ORG_URL": "你的Azure DevOps组织URL",
        "AZURE_DEVOPS_AUTH_METHOD": "pat",
        "AZURE_DEVOPS_PAT": "个人访问令牌",
        "AZURE_DEVOPS_DEFAULT_PROJECT": "项目名称"
      }
    }
  }
}
````

#### 4️⃣ 准备数据文件

系统需要以下 JSON 文件（首次运行会自动创建）：

- codeSmallList.json - 已处理异味记录（初始为空数组 `[]`）
- emailToGuid.json - 邮箱到 Azure DevOps GUID 的映射
- emialtoOpenId.json - 邮箱到飞书 OpenID 的映射
- effort_state.json - 工作量统计（初始为 `{"total_Effort_time": 0}`）

#### 5️⃣ 配置系统参数

编辑 config.py 文件，根据你的环境修改配置项（详见配置说明）。

### 🎮 运行系统

#### 方式一：使用批处理脚本（Windows）

双击运行 start.bat，进入交互式菜单：

````text
====================================
 SonarQube自动修复系统
====================================

请选择操作:
1. 运行系统测试
2. 查看系统状态
3. 启动自动修复
4. 重置处理记录
5. 查看帮助
0. 退出
````

#### 方式二：使用 Python 直接运行

````bash
# 运行主程序
python main.py

# 查看系统状态
python cli.py status

# 运行测试
python cli.py test

# 重置记录
python cli.py reset
````

#### 方式三：使用命令行工具

````bash
# 查看帮助
python cli.py help

# 干运行模式（不实际修复）
python cli.py run --dry-run
````

### 🎉 首次运行建议

1. **先运行测试**：`python cli.py test` 验证环境配置
2. **查看状态**：`python cli.py status` 检查配置文件
3. **干运行模式**：`python cli.py run --dry-run` 测试流程
4. **正式运行**：`python main.py` 开始自动修复

---

## ⚙️ 配置说明

### 📁 核心配置文件：config.py

这是系统的大脑 🧠，所有重要参数都在这里！

#### 🔧 基础路径配置

````python
class Config:
    # 项目根目录（自动检测，无需修改）
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

    # MCP 服务器配置文件路径
    MCP_CONFIG_PATH = os.path.join(PROJECT_ROOT, "localJSON", "mcp.json")

    # 数据文件路径
    CODE_SMELL_LIST_PATH = os.path.join(PROJECT_ROOT, "localJSON", "codeSmallList.json")
    EMAIL_TO_GUID_PATH = os.path.join(PROJECT_ROOT, "localJSON", "emailToGuid.json")
    EMAIL_TO_OPEN_ID_PATH = os.path.join(PROJECT_ROOT, "localJSON", "emialtoOpenId.json")
    TOTAL_EFFORT_STATE_PATH = os.path.join(PROJECT_ROOT, "localJSON", "effort_state.json")
````

**📌 说明**：

- 这些路径通常不需要修改，除非你想自定义数据文件存储位置
- 所有路径都是绝对路径，确保在任何工作目录下都能正确运行

#### 🎯 SonarQube 配置

````python
class Config:
    # SonarQube 配置
    SONARQUBE_PROJECT_KEY = "yourProject"  # 项目标识符
    SONARQUBE_BRANCH = "master"                         # 分析的分支
    SONARQUBE_SEVERITIES = ["INFO"]                     # 异味严重级别
    SONARQUBE_TYPES = ["CODE_SMELL"]                    # 异味类型
````

**📌 配置项详解**：

| 配置项                  | 说明                       | 可选值                                                     | 示例                     |
| ----------------------- | -------------------------- | ---------------------------------------------------------- | ------------------------ |
| `SONARQUBE_PROJECT_KEY` | SonarQube 中的项目标识符 | 任意字符串                                                 | `"my-awesome-project"`   |
| `SONARQUBE_BRANCH`      | 要分析的代码分支           | Git 分支名                                                 | `"master"`, `"develop"`  |
| `SONARQUBE_SEVERITIES`  | 要处理的异味严重级别       | `["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]`         | `["INFO", "MINOR"]`      |
| `SONARQUBE_TYPES`       | 异味类型                   | `["CODE_SMELL", "BUG", "VULNERABILITY"]`                   | `["CODE_SMELL"]`         |

**💡 提示**：

- `SONARQUBE_PROJECT_KEY` 可以在 SonarQube 项目页面找到
- 建议先从 `INFO` 级别开始，逐步处理更高级别的异味
- 不同类型可以组合使用，如 `["CODE_SMELL", "BUG"]`

#### 🔷 Azure DevOps 配置

````python
class Config:
    # Azure DevOps 配置
    AZURE_DEVOPS_PROJECT = "YourProject"                    # 项目名称
    AZURE_DEVOPS_REPOSITORY = "YourProject"                 # 仓库名称
    AZURE_DEVOPS_TARGET_BRANCH = "refs/heads/master"   # 目标分支（PR 合并到这里）
    AZURE_DEVOPS_TASK_ID = "12312"                    # 关联的工作项 ID
    DEFAULT_REVIEWER = "87790f0c-0021-4777-886a-ff6f7622a77b"  # 默认审查者 GUID
````

**📌 配置项详解**：

| 配置项                     | 说明                     | 格式                | 如何获取                               |
| -------------------------- | ------------------------ | ------------------- | ------------------------------------- |
| `AZURE_DEVOPS_PROJECT`     | Azure DevOps 项目名      | 字符串              | 在 Azure DevOps URL 中查看             |
| `AZURE_DEVOPS_REPOSITORY`  | Git 仓库名称             | 字符串              | Repos 页面中的仓库名                 |
| `AZURE_DEVOPS_TARGET_BRANCH` | PR 目标分支            | `refs/heads/分支名` | 通常是 `refs/heads/master` 或 `refs/heads/main` |
| `AZURE_DEVOPS_TASK_ID`     | 关联的任务 ID            | 数字字符串          | 工作项的 ID 编号                       |
| `DEFAULT_REVIEWER`         | 默认审查者               | GUID 格式           | 用户的 Azure DevOps GUID              |

**💡 提示**：

- GUID 可以在 Azure DevOps 用户资料页面找到
- `DEFAULT_REVIEWER` 在异味没有明确负责人时使用
- `TASK_ID` 用于关联 PR 和工作项，便于追踪

#### 💬 飞书通知配置

````python
class Config:
    # 飞书配置
    FEISHU_WEBHOOK_URL = "https://www.feishu.cn/flow/api/trigger-webhook/xxxxx"  # 群组 Webhook
    FEISHU_APP_ID = "cli_a8670ea0ab12345b"      # 飞书应用 ID
    FEISHU_APP_SECRET = "B9spcUNsZxhe12345zdVOg"  # 飞书应用密钥
````

**📌 配置项详解**：

| 配置项               | 说明                     | 获取方式                                                     |
| -------------------- | ------------------------ | ------------------------------------------------------------ |
| `FEISHU_WEBHOOK_URL` | 飞书群组机器人 Webhook 地址 | 群设置 → 机器人 → 添加机器人 → 获取 Webhook 地址             |
| `FEISHU_APP_ID`      | 飞书应用的唯一标识         | 飞书开放平台 → 应用管理 → 凭证与基础信息                     |
| `FEISHU_APP_SECRET`  | 飞书应用密钥             | 同上，注意保密 ⚠️                                          |

**💡 使用场景**：

- **Webhook**：用于向飞书群组发送通知（广播模式）
- **App ID/Secret**：用于发送私信给个人（精准推送）

**🔐 安全提示**：

- 不要将 `FEISHU_APP_SECRET` 提交到公共仓库
- 建议使用环境变量：`os.getenv("FEISHU_APP_SECRET")`

#### 🌿 Git 配置

````python
class Config:
    # Git 配置
    GIT_REPO_PATH = os.path.join(PROJECT_ROOT, "YourProject")  # Git 仓库路径
    GIT_BRANCH_NAME_TEMPLATE = "fix-sonar-{smell_key}"    # 分支命名模板
    GIT_COMMIT_MESSAGE_TEMPLATE = "fix: 解决SonarQube异味 {smell_key} - {description}"
````

**📌 配置项详解**：

| 配置项                      | 说明                 | 支持的变量            | 示例                                    |
| --------------------------- | -------------------- | ------------------- | --------------------------------------- |
| `GIT_REPO_PATH`             | 本地 Git 仓库的绝对路径 | 无                   | `/path/to/your/repo`                     |
| `GIT_BRANCH_NAME_TEMPLATE`    | 分支名称模板           | `{smell_key}`       | `fix-sonar-AYzqY123`                    |
| `GIT_COMMIT_MESSAGE_TEMPLATE` | 提交信息模板           | `{smell_key}`, `{description}` | `fix: 解决SonarQube异味 AYzqY123 - 删除未使用的变量` |

**💡 提示**：

- 分支名会自动清理特殊字符，确保 Git 兼容
- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范
- 支持在模板中使用变量进行动态替换

#### 📝 PR 配置

````python
class Config:
    # PR 配置
    PR_TITLE_TEMPLATE = "fix: 解决SonarQube异味 {smell_key}"
    PR_DESCRIPTION_TEMPLATE = """
## SonarQube代码异味修复

**异味Key:** {smell_key}
**修复描述:** {description}
**修复文件:** {file_path}

### 相关信息
- Task ID: {task_id}
- 自动化修复系统生成

### 检查清单
- [x] 代码修复已应用
- [x] 修复逻辑已验证
- [ ] 人工审核通过
"""
````

**📌 支持的变量**：

| 变量          | 说明             | 示例值                                  |
| ----------- | ---------------- | ------------------------------------- |
| `{smell_key}` | 异味的唯一标识     | `AYzqY1234567890`                      |
| `{description}` | 异味描述或修复说明 | `删除未使用的私有方法`                      |
| `{file_path}` | 修复的文件路径     | `src/Controllers/UserController.cs`     |
| `{task_id}` | 关联的任务 ID     | `283356`                                |

**💡 自定义建议**：

- 可以添加更多检查清单项
- 支持 Markdown 格式，让 PR 更美观
- 可以加入 GIF 或图片链接增强可读性

#### 📊 工作量统计配置

````python
class Config:
    # 工作量统计
    TOTAL_EFFORT_STATE_PATH = os.path.join(PROJECT_ROOT, "localJSON", "effort_state.json")
    total_Effort_time = 0  # 累计工作量（分钟）

    @classmethod
    def load_total_Effort_time(cls):
        """从文件加载累计工作量"""
        pass

    @classmethod
    def save_total_Effort_time(cls):
        """保存累计工作量到文件"""
        pass
````

**📌 工作量统计说明**：

- 每个 SonarQube 异味都有一个 `effort` 字段（预估修复时间）
- 系统会自动累加每次修复的工作量
- 数据持久化到 `effort_state.json` 文件
- 在飞书通知中会显示团队累计修复的总工作量

### 📄 数据文件详解

#### 1️⃣ `codeSmallList.json` - 已处理异味记录

**作用**：记录所有已处理的异味，用于去重避免重复修复

**格式示例**：

````json
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
````

**字段说明**：

| 字段            | 说明                     | 示例                                          |
| ------------- | ------------------------ | --------------------------------------------- |
| `key`         | 异味唯一标识             | `AYzqY1234567890`                              |
| `rule`        | SonarQube 规则 ID        | `csharpsquid:S1481`                           |
| `severity`    | 严重级别                 | `INFO`, `MINOR`, `MAJOR`, `CRITICAL`, `BLOCKER` |
| `component`   | 文件组件路径             | `yourProject:src/file.cs`          |
| `line`        | 行号                     | `45`                                          |
| `message`     | 异味描述                 | `Remove this unused field`                    |
| `author`      | 责任人邮箱               | `john.doe@company.com`                        |
| `creationDate`| 异味创建时间             | `2025-10-15T10:30:00+0800`                    |
| `processedDate`| 处理时间                 | `2025-10-15T14:20:00+0800`                    |
| `status`      | 处理状态                 | `FIXED`                                       |
| `prUrl`       | 关联的 PR 链接           | `https://...`                                  |

#### 2️⃣ `emailToGuid.json` - 邮箱到 GUID 映射

**作用**：将开发者邮箱映射到 Azure DevOps 的用户 GUID，用于分配 PR 审查者

**格式示例**：

````json
{
  "john.doe@company.com": "87790f0c-0021-4777-886a-ff6f7622a77b",
  "jane.smith@company.com": "a31b511e-6b0f-4894-9c33-c5df5c98608f"
}
````

**如何获取 GUID**：

1.  打开 Azure DevOps
2.  进入项目设置 → Team → 成员列表
3.  点击用户头像 → 查看个人资料
4.  URL 中包含 GUID：`https://xxx/_usersSettings/about?id=YOUR-GUID`

**💡 提示**：可以使用脚本批量获取团队成员的 GUID

#### 3️⃣ `emialtoOpenId.json` - 邮箱到 OpenID 映射

**作用**：将邮箱映射到飞书 OpenID，用于发送个人私信

**格式示例**：

````json
{
  "john.doe@company.com": "ou_xxxxxxxxxxxxxxxxxxxx",
  "jane.smith@company.com": "ou_yyyyyyyyyyyyyyyyyyyyyy"
}
````

**如何获取 OpenID**：

1.  使用飞书开放平台 API
2.  通过邮箱查询用户信息接口
3.  API 文档：[https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/contact-v3/user/batch_get_id](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/contact-v3/user/batch_get_id)

#### 4️⃣ `effort_state.json` - 工作量统计

**作用**：记录团队累计修复代码异味的总工作量

**格式示例**：

````json
{
  "total_Effort_time": 1250
}
````

**说明**：

*   单位：分钟
*   每次修复后自动累加
*   在飞书通知中显示
*   可以手动重置

#### 5️⃣ `mcp.json` - MCP 服务器配置

**作用**：配置系统需要连接的外部服务（SonarQube、Azure DevOps 等）

**完整示例**：

````json
{
  "mcpServers": {
    "sonarqube": {
      "command": "npx",
      "args": ["--yes", "sonarqube-mcp-server@latest"],
      "env": {
        "SONARQUBE_URL": "http://sonar-server:8000",
        "SONARQUBE_USERNAME": "admin",
        "SONARQUBE_PASSWORD": "your-password"
      }
    },
    "azureDevOps": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@tiberriver256/mcp-server-azure-devops"],
      "env": {
        "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/your-org",
        "AZURE_DEVOPS_AUTH_METHOD": "pat",
        "AZURE_DEVOPS_PAT": "your-personal-access-token",
        "AZURE_DEVOPS_DEFAULT_PROJECT": "YourProject"
      }
    }
  }
}
````

**字段说明**：

| 字段       | 说明           | 必填 |
| -------- | ------------ | -- |
| `command`| 启动命令         | ✅  |
| `args`   | 命令参数         | ✅  |
| `type`   | 服务类型         |    |
| `url`    | HTTP 服务地址    |    |
| `env`    | 环境变量         |    |
| `disabled`| 是否禁用         |    |

---

## 🏗️ 架构设计

### 🔄 系统工作流

````text
┌─────────────────────────────────────────────────────────────┐
│                   SonarQube 异味检测                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  IssueAnalyzerAgent: 分析异味、分页查询、作者过滤、去重      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  WorkspaceSetupAgent: 创建 Git 分支、环境准备               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  SolutionGeneratorAgent: AI 生成修复方案、匹配负责人        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  FixExecutorAgent: 执行代码修复、提交并推送                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  PullRequestAgent: 创建 PR、飞书通知、私信推送              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  RecordKeeperAgent: 保存处理记录、更新工作量统计            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  BrowserLauncherAgent: 打开浏览器查看 PR                    │
└─────────────────────────────────────────────────────────────┘
````

### 🧩 技术架构

````text
┌────────────────────────────────────────────────────────┐
│              SonarQubeAutoFixOrchestrator               │
│                    (总控制器)                           │
└─────────────────────┬──────────────────────────────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
┌─────▼─────┐  ┌──────▼──────┐  ┌────▼─────┐
│  LangGraph │  │ MCP Services │  │   Utils  │
│  StateGraph│  │   Client     │  │   Layer  │
└─────┬─────┘  └──────┬──────┘  └────┬─────┘
      │               │               │
      │        ┌──────┴──────┐        │
      │        │             │        │
   7 Agents  SonarQube  AzureDevOps  FileUtils
             MCP Server  MCP Server   GitUtils
                                      LLMUtils
````

---

## 📚 使用指南

### 🐛 常见问题

#### Q1: 运行时提示 "MCP 服务器连接失败"

**解决方案**：

1.  检查 mcp.json 配置是否正确
2.  确认网络能访问 SonarQube 和 Azure DevOps
3.  验证用户名密码或 PAT 是否有效
4.  查看 MCP 服务器日志

#### Q2: 找不到未处理的异味

**可能原因**：

*   所有异味都已处理
*   过滤条件太严格
*   异味没有明确作者

**解决方案**：

````bash
# 重置处理记录
python cli.py reset

# 修改过滤条件（编辑 config.py）
````

#### Q3: Git 操作失败

**常见错误**：

*   `fatal: not a git repository` - 检查 `GIT_REPO_PATH`
*   `Permission denied` - 确认仓库读写权限
*   `conflict` - 手动解决冲突后重试

#### Q4: PR 创建失败

**检查项**：

*   Azure DevOps PAT 权限
*   目标分支是否存在
*   用户 GUID 是否正确

#### Q5: 飞书通知发送失败

**检查项**：

*   Webhook URL 是否有效
*   App ID 和 Secret 是否正确
*   OpenID 映射是否完整

---

### 💡 最佳实践

#### 1. 渐进式处理

````text
第一天: 处理 INFO 级别 → 熟悉系统
第二天: 处理 MINOR 级别 → 验证修复质量
第三天: 处理 MAJOR 级别 → 解决重要问题
````

#### 2. 定期备份

````bash
# 备份处理记录
cp localJSON/codeSmallList.json localJSON/codeSmallList.backup.json

# 备份工作量统计
cp localJSON/effort_state.json localJSON/effort_state.backup.json
````

#### 3. 监控和审查

*   定期查看创建的 PR，确保修复质量
*   检查飞书通知，确认团队成员收到消息
*   分析工作量统计，评估团队效率

---

## 🎓 学习资源

### 📖 相关文档

*   **[LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)** - 深入了解状态图工作流
*   **[MCP 协议规范](https://modelcontextprotocol.io/)** - 理解 MCP 集成原理
*   **[SonarQube API 文档](https://docs.sonarqube.org/latest/extend/web-api/)** - 探索更多 SonarQube 功能
*   **[Azure DevOps API](https://docs.microsoft.com/en-us/rest/api/azure/devops/)** - 扩展 Azure DevOps 集成
*   **[飞书开放平台](https://open.feishu.cn/document/)** - 自定义飞书通知

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！🎉

### 🌟 贡献方式

*   **报告 Bug**：提交 [Issue](https://github.com/your-username/LangGraphSugAgent/issues)
*   **功能建议**：在 Issue 中描述你的想法
*   **代码贡献**：提交 Pull Request
*   **文档改进**：完善 README 或添加示例

### 📝 开发指南

````bash
# 1. Fork 本仓库
# 2. 创建功能分支
git checkout -b feature/amazing-feature

# 3. 提交更改
git commit -m "✨ Add amazing feature"

# 4. 推送到分支
git push origin feature/amazing-feature

# 5. 创建 Pull Request
````

### ✅ 代码规范

*   遵循 PEP 8 Python 代码风格
*   所有函数必须有详细的中文注释
*   添加必要的类型提示
*   编写单元测试

---

## 📜 开源协议

本项目基于 **MIT License** 开源。

这意味着你可以自由地：

*   ✅ 商业使用
*   ✅ 修改源码
*   ✅ 分发
*   ✅ 私用

---

## 🙏 致谢

感谢以下开源项目和服务：

*   **LangChain & LangGraph** - 强大的 LLM 应用开发框架
*   **Kimi K2** - 优秀的大语言模型
*   **MCP Protocol** - 标准化的服务集成协议
*   **SonarQube** - 专业的代码质量分析工具
*   **Azure DevOps** - 完善的项目管理平台
*   **飞书** - 高效的团队协作工具
*   **Rich** - 美观的终端 UI 库

---

## 📮 联系方式

有问题或建议？欢迎联系我们！

*   **GitHub Issues**: [提交 Issue](https://github.com/your-username/LangGraphSugAgent/issues)
*   **Email**: your-email@example.com

---

## 🎉 Star History

如果这个项目对你有帮助，请给我们一个 ⭐ Star！

你的支持是我们持续改进的动力！💪

---

<div align="center">

**Made with ❤️ by [Your Name/Team]**

**当前版本：v1.1.0** | **最后更新：2025-10-15**

⬆ 回到顶部

</div>

