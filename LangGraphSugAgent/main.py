"""
SonarQube代码异味自动修复系统
使用LangGraph实现的多Agent协作系统

该系统包含以下主要组件：
- 总控制Agent：SonarQubeAutoFixOrchestrator
- 7个专业子Agent：分别负责异味分析、工作区设置、方案生成、修复执行、PR创建、记录保存和浏览器打开
- MCP服务器集成：SonarQube和AzureDevOps
- LLM后端：Kimi K2 API
"""

import asyncio
import atexit
import importlib
import json
import os
import sys
import threading
import traceback
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Callable, Coroutine, Dict, List, Optional, TypedDict

# 添加APIs目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'APIs'))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from uuid import uuid4

import git
import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent

# 导入Kimi API
from APIs.kimi_k2_api import call_kimi, initialize_kimi_client
from config import Config

# 初始化控制台
console = Console()

class WorkflowState(TypedDict):
    """工作流状态定义"""
    messages: Annotated[List[BaseMessage], add_messages]
    current_step: str
    smell_data: Optional[Dict[str, Any]]
    branch_name: Optional[str]
    fix_solution: Optional[Dict[str, Any]]
    pr_info: Optional[Dict[str, Any]]
    error_info: Optional[str]
    completed_steps: List[str]


@dataclass
class MCPServerSession:
    """维护单个MCP服务器的会话信息"""

    session: ClientSession
    stack: AsyncExitStack
    get_session_id: Optional[Callable[[], str]] = None


class MCPClient:
    """MCP客户端，用于与配置的MCP服务器通信"""

    def __init__(self, config_path: str = Config.MCP_CONFIG_PATH):
        self.config_path = config_path
        self.config = self._load_config()
        raw_servers = self.config.get("mcpServers", {})
        self.mcp_servers = {
            name: cfg for name, cfg in raw_servers.items() if not cfg.get("disabled", False)
        }
        self._sessions: Dict[str, MCPServerSession] = {}
        self._session_lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._loop_thread.start()
        self._closed = False
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        atexit.register(self.close)
        console.print(f"[green]MCP客户端初始化完成，启用 {len(self.mcp_servers)} 个服务器配置[/green]")

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            console.print("[yellow]未找到MCP配置文件，将使用空配置[/yellow]")
            return {}
        except json.JSONDecodeError as e:
            console.print(f"[red]解析MCP配置失败: {e}[/red]")
            return {}

    def close(self):
        """关闭所有MCP会话并停止事件循环"""

        if self._closed:
            return

        self._closed = True

        async def _shutdown():
            for name, entry in list(self._sessions.items()):
                try:
                    await entry.stack.aclose()
                    console.print(f"[dim]已关闭MCP服务器 {name} 会话[/dim]")
                except Exception as exc:
                    console.print(f"[yellow]关闭MCP服务器 {name} 会话时出现警告: {exc}[/yellow]")
            self._sessions.clear()

        future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        try:
            future.result(timeout=10)
        except Exception as exc:  # pragma: no cover - 关闭阶段仅记录
            console.print(f"[yellow]MCP客户端关闭时出现异常: {exc}[/yellow]")

        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5)
        try:
            self._loop.close()
        except Exception:
            pass

    def _run_async(self, coro: asyncio.Future | Coroutine[Any, Any, Any]) -> Any:
        """在内部事件循环中执行协程"""

        if self._closed:
            raise RuntimeError("MCP客户端已关闭，无法执行异步操作")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    async def _create_session(self, name: str, cfg: Dict[str, Any]) -> MCPServerSession:
        stack = AsyncExitStack()

        server_type = cfg.get("type") or ("stdio" if cfg.get("command") else "streamableHttp")
        server_type = server_type.lower()

        if server_type == "streamablehttp":
            url = cfg.get("url")
            if not url:
                raise ValueError(f"MCP服务器 {name} 缺少url配置")

            headers = cfg.get("headers")
            timeout = cfg.get("timeout", 30)
            sse_timeout = cfg.get("sseReadTimeout", 300)

            read_stream, write_stream, get_session_id = await stack.enter_async_context(
                streamablehttp_client(
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    sse_read_timeout=sse_timeout,
                )
            )
        else:
            command = cfg.get("command")
            if not command:
                raise ValueError(f"MCP服务器 {name} 缺少command配置")

            args = cfg.get("args", [])
            env = cfg.get("env")
            cwd = cfg.get("cwd")
            encoding = cfg.get("encoding", "utf-8")
            encoding_handler = cfg.get("encodingErrorHandler", "strict")

            params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
                cwd=cwd,
                encoding=encoding,
                encoding_error_handler=encoding_handler,
            )

            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            get_session_id = None

        session = ClientSession(read_stream, write_stream)
        session = await stack.enter_async_context(session)
        await session.initialize()
        console.print(f"[dim]MCP服务器 {name} 初始化完成[/dim]")
        return MCPServerSession(session=session, stack=stack, get_session_id=get_session_id)

    def _ensure_session(self, name: str) -> MCPServerSession:
        if name not in self.mcp_servers:
            raise KeyError(f"未配置MCP服务器: {name}")

        if name in self._sessions:
            return self._sessions[name]

        with self._session_lock:
            if name in self._sessions:
                return self._sessions[name]
            cfg = self.mcp_servers[name]
            entry = self._run_async(self._create_session(name, cfg))
            self._sessions[name] = entry
            return entry

    def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        entry = self._ensure_session(server_name)
        result = self._run_async(entry.session.list_tools())
        tools: List[Dict[str, Any]] = []
        for tool in result.tools:
            tools.append(tool.model_dump())
        self._tool_cache[server_name] = {tool["name"]: tool for tool in tools}
        return tools

    def _normalize_tool_result(self, result) -> Any:
        if result.isError:
            message = ""
            for item in result.content or []:
                if isinstance(item, TextContent):
                    message += item.text
            raise RuntimeError(f"MCP工具调用返回错误: {message or '未知错误'}")

        if result.structuredContent is not None:
            return result.structuredContent

        texts: List[str] = []
        for item in result.content or []:
            if isinstance(item, TextContent):
                texts.append(item.text)

        combined = "\n".join(texts).strip()
        if not combined:
            return {}
        try:
            return json.loads(combined)
        except json.JSONDecodeError:
            return {"text": combined}

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        entry = self._ensure_session(server_name)
        read_timeout = timedelta(seconds=timeout) if timeout is not None else None
        result = self._run_async(
            entry.session.call_tool(
                name=tool_name,
                arguments=arguments or {},
                read_timeout_seconds=read_timeout,
            )
        )
        return self._normalize_tool_result(result)

    def _resolve_tool_name(self, server_name: str, preferred: List[str], keywords: Optional[List[str]] = None) -> str:
        cache = self._tool_cache.get(server_name)
        if not cache:
            tools = self.list_tools(server_name)
            cache = self._tool_cache.get(server_name, {})
            if not cache and tools:
                cache = {tool["name"]: tool for tool in tools}
                self._tool_cache[server_name] = cache

        for candidate in preferred:
            if candidate in cache:
                return candidate

        if keywords:
            for name in cache.keys():
                if all(keyword.lower() in name.lower() for keyword in keywords):
                    return name

        available = ", ".join(cache.keys()) if cache else "无可用工具"
        raise RuntimeError(f"无法在服务器 {server_name} 上解析工具名称，已知工具: {available}")

    def call_sonarqube_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = self._resolve_tool_name(
            "sonarqube",
            preferred=["issues", "issues/search", "issues.search", "issues_search"],
            keywords=["issues"],
        )
        console.print(f"[cyan]通过MCP调用SonarQube工具 {tool_name}[/cyan]")
        result = self.call_tool("sonarqube", tool_name, params, timeout=120)
        if not isinstance(result, dict):
            raise RuntimeError("SonarQube工具返回的结果格式不正确")
        return result

    def call_azure_devops_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "create_pr":
            tool_name = self._resolve_tool_name(
                "azureDevOps",
                preferred=[
                    "pullRequests/create",
                    "pullrequests/create",
                    "createPullRequest",
                    "pull_request_create",
                    "create_pull_request",
                ],
                keywords=["pull", "create"],
            )
            console.print(f"[cyan]通过MCP调用Azure DevOps工具 {tool_name} 创建PR[/cyan]")
            result = self.call_tool("azureDevOps", tool_name, params, timeout=180)
            if not isinstance(result, dict):
                raise RuntimeError("Azure DevOps工具返回的结果格式不正确")
            return result

        raise ValueError(f"不支持的Azure DevOps操作: {action}")


class BaseAgent:
    """基础Agent类"""
    
    def __init__(self, name: str, mcp_client: MCPClient):
        """
        初始化基础Agent
        
        参数:
            name (str): Agent名称
            mcp_client (MCPClient): MCP客户端实例
        """
        self.name = name
        self.mcp_client = mcp_client
        self.kimi_client = initialize_kimi_client()
        console.print(f"[green]Agent {name} 初始化完成[/green]")
    
    def call_llm(self, prompt: str, system_prompt: str = "你是一个有用的AI助手。") -> str:
        """
        调用LLM获取响应
        
        参数:
            prompt (str): 用户提示
            system_prompt (str): 系统提示
            
        返回:
            str: LLM响应
        """
        return call_kimi(prompt, system_prompt, self.kimi_client)

    def _format_state_snapshot(self, state: WorkflowState) -> str:
        """格式化状态摘要用于日志输出"""
        smell = state.get("smell_data") or {}
        fix = state.get("fix_solution") or {}
        pr_info = state.get("pr_info") or {}
        summary = {
            "current_step": state.get("current_step"),
            "smell_key": smell.get("key"),
            "branch": state.get("branch_name"),
            "fix_file": fix.get("filePath"),
            "pr_url": pr_info.get("url"),
            "error": state.get("error_info")
        }
        try:
            return json.dumps(summary, ensure_ascii=False)
        except TypeError:
            # 回退为简单字符串表示
            return str(summary)

    def log_state_entry(self, state: WorkflowState):
        """记录Agent执行前的状态信息"""
        console.print(f"[dim]↘️ 输入状态: {self._format_state_snapshot(state)}[/dim]")

    def log_state_exit(self, state: WorkflowState, next_step: Optional[str] = None):
        """记录Agent执行后的状态信息"""
        snapshot = self._format_state_snapshot(state)
        target = next_step or state.get("current_step") or "END"
        console.print(f"[dim]↗️ 输出状态: {snapshot}，下一节点: {target}[/dim]")


class IssueAnalyzerAgent(BaseAgent):
    """代码异味分析Agent"""
    
    def __init__(self, mcp_client: MCPClient):
        super().__init__("IssueAnalyzerAgent", mcp_client)
    
    def analyze_issues(self, state: WorkflowState) -> WorkflowState:
        """
        分析代码异味，找出未处理的异味
        
        参数:
            state (WorkflowState): 当前工作流状态
            
        返回:
            WorkflowState: 更新后的工作流状态
        """
        try:
            console.print(Panel(f"[bold blue]{self.name} 开始执行异味分析[/bold blue]"))
            self.log_state_entry(state)
            
            # 读取已处理的异味列表
            processed_smells = self._load_processed_smells()
            console.print(f"[cyan]已加载 {len(processed_smells)} 个已处理异味[/cyan]")
            
            # 调用SonarQube API获取异味列表，支持分页
            sonar_params = Config.get_sonarqube_params()
            page_size = int(sonar_params.get("page_size") or sonar_params.get("pageSize") or 50)
            page = 1
            unprocessed_issue = None

            while True:
                sonar_params["page"] = str(page)
                console.print(f"[dim]查询SonarQube第 {page} 页[/dim]")
                response = self.mcp_client.call_sonarqube_api(sonar_params)
                issues = response.get("issues", [])

                if not issues:
                    console.print(f"[yellow]第 {page} 页未返回任何异味[/yellow]")
                    break

                for issue in issues:
                    author = issue.get("author")
                    print(f"正在检查 issue {issue.get('key')}, 作者: '{author}' (类型: {type(author)})")
                    if (
                        issue.get("key") not in processed_smells
                        and issue.get("status") == "OPEN"
                        and author is not None
                        and author.strip()
                    ):
                        unprocessed_issue = issue
                        break

                if unprocessed_issue:
                    break

                paging = response.get("paging") or {}
                total_raw = paging.get("total")
                page_index_raw = paging.get("pageIndex") or paging.get("page_index")
                page_size_from_paging = paging.get("pageSize") or paging.get("page_size")

                try:
                    total = int(total_raw) if total_raw is not None else None
                except (TypeError, ValueError):
                    total = None

                try:
                    page_index_value = int(page_index_raw) if page_index_raw is not None else page
                except (TypeError, ValueError):
                    page_index_value = page

                effective_page_size = page_size
                if page_size_from_paging is not None:
                    try:
                        effective_page_size = int(page_size_from_paging)
                    except (TypeError, ValueError):
                        effective_page_size = page_size

                if total is not None and effective_page_size:
                    max_page = (total + effective_page_size - 1) // effective_page_size
                    if page_index_value >= max_page:
                        console.print("[yellow]所有分页均已检查，未找到新的开放异味[/yellow]")
                        break
                else:
                    if effective_page_size and len(issues) < effective_page_size:
                        console.print("[yellow]已读取最后一页异味，但未找到新的开放异味[/yellow]")
                        break

                page += 1
            
            if unprocessed_issue:
                console.print(f"[green]找到未处理异味: {unprocessed_issue['key']}[/green]")
                state["smell_data"] = unprocessed_issue
                state["current_step"] = "workspace_setup"
                state["completed_steps"].append("issue_analysis")
                state["messages"].append(AIMessage(content=f"找到未处理的代码异味：{unprocessed_issue['key']}"))
                self.log_state_exit(state, "workspace_setup")
            else:
                state["error_info"] = "未找到需要处理的新异味"
                console.print("[yellow]未找到需要处理的新异味[/yellow]")
                self.log_state_exit(state, "END")
            
            return state
            
        except Exception as e:
            error_msg = f"异味分析失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            state["error_info"] = error_msg
            self.log_state_exit(state, "END")
            return state
    
    def _load_processed_smells(self) -> set:
        """加载已处理的异味Key集合"""
        try:
            with open(Config.CODE_SMELL_LIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {item.get("key") for item in data if "key" in item}
                return set()
        except (FileNotFoundError, json.JSONDecodeError):
            return set()


class WorkspaceSetupAgent(BaseAgent):
    """工作区设置Agent"""
    
    def __init__(self, mcp_client: MCPClient):
        super().__init__("WorkspaceSetupAgent", mcp_client)
    
    def setup_workspace(self, state: WorkflowState) -> WorkflowState:
        """
        设置工作区，创建新分支
        
        参数:
            state (WorkflowState): 当前工作流状态
            
        返回:
            WorkflowState: 更新后的工作流状态
        """
        try:
            console.print(Panel(f"[bold blue]{self.name} 开始设置工作区[/bold blue]"))
            self.log_state_entry(state)
            
            if not state.get("smell_data"):
                state["error_info"] = "缺少异味数据，无法设置工作区"
                self.log_state_exit(state, "END")
                return state
            
            smell_key = state["smell_data"]["key"]
            branch_name = f"fix-sonar-{smell_key}"
            
            repo_path = Config.GIT_REPO_PATH
            repo_git_dir = Path(repo_path) / ".git"

            if not repo_git_dir.exists():
                error_msg = f"指定Git仓库不存在: {repo_path}"
                console.print(f"[red]{error_msg}[/red]")
                state["error_info"] = error_msg
                self.log_state_exit(state, "END")
                return state

            console.print(f"[cyan]Git仓库路径: {repo_path}[/cyan]")
            repo = git.Repo(repo_path)
            
            # 切换到master分支并拉取最新代码
            console.print("[cyan]切换到master分支...[/cyan]")
            repo.git.checkout("master")
            repo.git.pull("origin", "master")
            
            # 创建新分支
            console.print(f"[cyan]创建新分支: {branch_name}[/cyan]")
            # 获取当前时间，并添加到branch_name中，以避免分支名重复
            branch_name += "-" + datetime.now().strftime("%Y%m%d%H%M%S")
            repo.git.checkout("-b", branch_name)
            
            state["branch_name"] = branch_name
            state["current_step"] = "solution_generation"
            state["completed_steps"].append("workspace_setup")
            state["messages"].append(AIMessage(content=f"工作区设置完成，已创建分支：{branch_name}"))
            
            console.print(f"[green]工作区设置完成，当前分支：{branch_name}[/green]")
            self.log_state_exit(state, "solution_generation")
            return state
            
        except Exception as e:
            error_msg = f"工作区设置失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            state["error_info"] = error_msg
            self.log_state_exit(state, "END")
            return state


class SolutionGeneratorAgent(BaseAgent):
    """解决方案生成Agent"""
    
    def __init__(self, mcp_client: MCPClient):
        super().__init__("SolutionGeneratorAgent", mcp_client)
    
    def generate_solution(self, state: WorkflowState) -> WorkflowState:
        """
        生成代码修复方案
        
        参数:
            state (WorkflowState): 当前工作流状态
            
        返回:
            WorkflowState: 更新后的工作流状态
        """
        try:
            console.print(Panel(f"[bold blue]{self.name} 开始生成修复方案[/bold blue]"))
            self.log_state_entry(state)
            
            if not state.get("smell_data"):
                state["error_info"] = "缺少异味数据，无法生成修复方案"
                self.log_state_exit(state, "END")
                return state
            
            smell_data = state["smell_data"]
            
            # 加载邮箱到GUID的映射
            email_to_guid = self._load_email_to_guid_mapping()
            assignee_guid = email_to_guid.get(smell_data.get("author", ""), "")
            
            # 使用LLM生成修复方案
            prompt = f"""
根据以下SonarQube代码异味信息，生成具体的修复方案：

异味信息：
- Key: {smell_data.get('key')}
- 规则: {smell_data.get('rule')}
- 文件: {smell_data.get('component')}
- 行号: {smell_data.get('line')}
- 消息: {smell_data.get('message')}
- 类型: {smell_data.get('type')}

请分析这个代码异味，并提供具体的修复建议。
输出格式应该是JSON，包含以下字段：
- filePath: 相对文件路径
- codeDiff: 具体的代码修复内容
- description: 修复说明

请直接返回JSON，不要包含其他文本。
"""
            
            system_prompt = "你是一个代码修复专家，专门分析SonarQube代码异味并提供修复方案。"
            
            response = self.call_llm(prompt, system_prompt)
            
            try:
                # 尝试解析LLM返回的JSON
                solution_data = json.loads(response)
            except json.JSONDecodeError:
                # 如果解析失败，创建默认方案
                solution_data = {
                    "filePath": smell_data.get("component", "").replace("yourProject:", ""),
                    "codeDiff": f"// TODO: 修复异味 {smell_data.get('key')}\\n// {smell_data.get('message')}",
                    "description": f"修复SonarQube异味: {smell_data.get('message')}"
                }
            
            # 构建完整的修复方案
            fix_solution = {
                "filePath": solution_data.get("filePath"),
                "assignee": assignee_guid,
                "codeDiff": solution_data.get("codeDiff"),
                "smellKey": smell_data.get("key"),
                "description": solution_data.get("description"),
                # 添加行号
                "line": smell_data.get("line"),
                # 添加effort
                "effort": smell_data.get("effort"),
            }
            
            state["fix_solution"] = fix_solution
            state["current_step"] = "fix_execution"
            state["completed_steps"].append("solution_generation")
            state["messages"].append(AIMessage(content=f"修复方案生成完成，文件：{fix_solution['filePath']}"))
            
            console.print(f"[green]修复方案生成完成[/green]")
            self.log_state_exit(state, "fix_execution")
            return state
            
        except Exception as e:
            error_msg = f"修复方案生成失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            state["error_info"] = error_msg
            self.log_state_exit(state, "END")
            return state
    
    def _load_email_to_guid_mapping(self) -> Dict[str, str]:
        """加载邮箱到GUID的映射"""
        try:
            with open(Config.EMAIL_TO_GUID_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


class FixExecutorAgent(BaseAgent):
    """修复执行Agent"""
    
    def __init__(self, mcp_client: MCPClient):
        super().__init__("FixExecutorAgent", mcp_client)
    
    def execute_fix(self, state: WorkflowState) -> WorkflowState:
        """
        执行代码修复
        
        参数:
            state (WorkflowState): 当前工作流状态
            
        返回:
            WorkflowState: 更新后的工作流状态
        """
        try:
            console.print(Panel(f"[bold blue]{self.name} 开始执行代码修复[/bold blue]"))
            self.log_state_entry(state)
            
            if not state.get("fix_solution"):
                state["error_info"] = "缺少修复方案，无法执行修复"
                self.log_state_exit(state, "END")
                return state
            
            fix_solution = state["fix_solution"]
            file_path = fix_solution["filePath"]
            repo_path = Path(Config.GIT_REPO_PATH)
            target_path: Optional[Path] = None

            if file_path:
                candidate = Path(file_path)
                if not candidate.is_absolute():
                    candidate = (repo_path / candidate).resolve()
                target_path = candidate
                try:
                    target_path.relative_to(repo_path)
                except ValueError:
                    console.print(f"[yellow]警告：修复文件不在仓库内，将按绝对路径处理：{target_path}[/yellow]")

            llm_fix_summary: Optional[str] = None
            file_updated = False

            if not target_path:
                console.print("[yellow]未提供有效的文件路径，跳过文件写入操作[/yellow]")
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)

                original_content = ""
                if target_path.exists():
                    console.print(f"[cyan]准备修复文件：{target_path}[/cyan]")
                    try:
                        with open(target_path, "r", encoding="utf-8") as f:
                            original_content = f.read()
                    except UnicodeDecodeError:
                        console.print(f"[yellow]文件 {target_path} 不是UTF-8编码，无法自动修复[/yellow]")
                        original_content = ""
                else:
                    console.print(f"[yellow]文件不存在，LLM将生成新的内容：{target_path}[/yellow]")

                code_diff = (fix_solution.get("codeDiff") or "").strip() or "无具体代码片段，请根据描述修复"
                system_prompt = "你是一位经验丰富的高级软件工程师，擅长根据SonarQube修复建议安全地修改代码。"

                language_hint = target_path.suffix.lstrip(".") or "text"

                original_lines = original_content.splitlines()
                original_has_trailing_newline = original_content.endswith("\n")

                snippet_mode = False
                start_idx = 0
                end_idx = len(original_lines)
                context_snippet = original_content
                snippet_note = "未提供具体行号，以下为完整文件内容。"

                if original_lines:
                    provided_line = fix_solution.get("line")
                    if provided_line is not None:
                        try:
                            line_no = max(int(provided_line), 1)
                        except (TypeError, ValueError):
                            line_no = 1
                        total_lines = len(original_lines)
                        radius = 10
                        start_idx = max(line_no - radius - 1, 0)
                        end_idx = min(line_no + radius, total_lines)
                        context_segment = original_lines[start_idx:end_idx]
                        if context_segment:
                            context_snippet = "\n".join(context_segment)
                            snippet_note = (
                                f"片段范围：第 {start_idx + 1} 行到第 {end_idx} 行，共 {total_lines} 行。"
                            )
                            snippet_mode = True
                        else:
                            snippet_note = "指定行号超出范围，以下为完整文件内容。"
                    else:
                        snippet_note = "未提供行号，以下为完整文件内容。"

                print(fix_solution.get('description'))

                if snippet_mode:
                    llm_prompt = (
                        "请基于给定的修复方案更新目标代码文件（仅限指定片段）。\n"
                        "输出必须是JSON，不包含额外文本。\n"
                        "字段要求：\n"
                        "- updatedSnippet: 替换后的完整片段字符串（包含必要的新代码）。\n"
                        "- summary: 简要说明生成的修改。\n"
                        "- warnings: 可选，其他注意事项。\n"
                        "如果无法只修改该片段，请额外提供 newContent 字段，包含整个文件的最新内容。\n"
                        "\n"
                        f"### 修复目标\n"
                        f"- 文件: {target_path}\n"
                        f"- 异味Key: {fix_solution.get('smellKey')}\n"
                        f"- 修复描述: {fix_solution.get('description')}\n"
                        "\n"
                        f"### 推荐修改\n{code_diff}\n"
                        "\n"
                        f"### 当前文件片段（{snippet_note}）\n"
                        f"起始行号: {start_idx + 1}\n结束行号: {end_idx}\n"
                        f"```{language_hint}\n{context_snippet}\n```\n"
                        "\n"
                        "请仅在片段内部做必要调整，保持片段外代码完全不变。\n"
                        "返回合法JSON。"
                    )
                else:
                    llm_prompt = (
                        "请基于给定的修复方案更新目标代码文件。\n"
                        "输出必须是JSON，不包含额外文本。\n"
                        "字段要求：\n"
                        "- newContent: 更新后的完整文件内容字符串。\n"
                        "- summary: 简要说明生成的修改。\n"
                        "如果修复方案不足以完成修改，请结合上下文进行合理补充，但务必保证现有功能不被破坏。\n"
                        "\n"
                        f"### 修复目标\n"
                        f"- 文件: {target_path}\n"
                        f"- 异味Key: {fix_solution.get('smellKey')}\n"
                        f"- 修复描述: {fix_solution.get('description')}\n"
                        "\n"
                        f"### 推荐修改\n{code_diff}\n"
                        "\n"
                        "### 当前文件内容\n"
                        f"```{language_hint}\n{original_content}\n```\n"
                        "\n"
                        "请直接返回合法JSON。"
                    )

                llm_response = self.call_llm(llm_prompt, system_prompt).strip()

                parsed_response: Optional[Dict[str, Any]] = None
                if llm_response:
                    try:
                        parsed_response = json.loads(llm_response)
                    except json.JSONDecodeError:
                        json_start = llm_response.find("{")
                        json_end = llm_response.rfind("}")
                        if json_start != -1 and json_end != -1 and json_start < json_end:
                            try:
                                parsed_response = json.loads(llm_response[json_start : json_end + 1])
                            except json.JSONDecodeError:
                                parsed_response = None

                if parsed_response and isinstance(parsed_response, dict):
                    new_content_to_write: Optional[str] = None

                    if snippet_mode:
                        updated_snippet = parsed_response.get("updatedSnippet")
                        fallback_full = parsed_response.get("newContent")

                        if isinstance(fallback_full, str) and fallback_full.strip():
                            new_content_to_write = fallback_full
                        elif isinstance(updated_snippet, str) and updated_snippet.strip():
                            updated_lines = updated_snippet.splitlines()
                            new_lines = original_lines[:start_idx] + updated_lines + original_lines[end_idx:]
                            new_content_to_write = "\n".join(new_lines)
                            if original_has_trailing_newline and new_content_to_write and not new_content_to_write.endswith("\n"):
                                new_content_to_write += "\n"
                        else:
                            console.print("[yellow]LLM未返回有效的updatedSnippet，保留原文件[/yellow]")
                    else:
                        new_content = parsed_response.get("newContent")
                        if isinstance(new_content, str) and new_content.strip():
                            new_content_to_write = new_content
                        else:
                            console.print("[yellow]LLM未返回有效的newContent，保留原文件[/yellow]")

                    if new_content_to_write is not None:
                        with open(target_path, "w", encoding="utf-8") as f:
                            f.write(new_content_to_write)
                        llm_fix_summary = parsed_response.get("summary")
                        file_updated = True
                        console.print(f"[green]LLM修复已写入文件：{target_path}[/green]")
                else:
                    console.print("[yellow]LLM返回结果无法解析为JSON，未对文件进行修改[/yellow]")

            # Git操作（如果在Git仓库中）
            if (repo_path / ".git").exists():
                try:
                    repo = git.Repo(repo_path)

                    if target_path and target_path.exists() and file_updated:
                        repo_root = Path(repo.working_tree_dir)
                        try:
                            rel_path = target_path.relative_to(repo_root)
                        except ValueError:
                            rel_path = target_path
                        repo.git.add(str(rel_path))

                    if file_updated:
                        commit_summary = llm_fix_summary or fix_solution["description"]
                        commit_message = f"fix: 解决SonarQube异味 {fix_solution['smellKey']} - {commit_summary}"
                        repo.git.commit("-m", commit_message)

                        branch_name = state.get("branch_name")
                        if branch_name:
                            repo.git.push("origin", branch_name)
                            console.print(f"[green]代码已推送到远程分支：{branch_name}[/green]")
                    else:
                        console.print("[yellow]未检测到文件修改，跳过Git提交[/yellow]")

                except Exception as git_error:
                    console.print(f"[yellow]Git操作警告: {git_error}[/yellow]")
            
            if llm_fix_summary:
                state.setdefault("fix_solution", {})["executionSummary"] = llm_fix_summary

            state["current_step"] = "pr_creation"
            state["completed_steps"].append("fix_execution")
            if file_updated:
                final_message = "代码修复执行完成"
                if llm_fix_summary:
                    final_message += f"：{llm_fix_summary}"
            else:
                final_message = "代码修复执行完成：LLM未返回有效内容，未修改文件"
            state["messages"].append(AIMessage(content=final_message))
            
            console.print("[green]代码修复执行完成[/green]")
            self.log_state_exit(state, "pr_creation")
            return state
            
        except Exception as e:
            error_msg = f"代码修复执行失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            state["error_info"] = error_msg
            self.log_state_exit(state, "END")
            return state


class PullRequestAgent(BaseAgent):
    """拉取请求Agent"""
    
    def __init__(self, mcp_client: MCPClient):
        super().__init__("PullRequestAgent", mcp_client)
    
    def create_pull_request(self, state: WorkflowState) -> WorkflowState:
        """
        创建拉取请求
        
        参数:
            state (WorkflowState): 当前工作流状态
            
        返回:
            WorkflowState: 更新后的工作流状态
        """
        try:
            console.print(Panel(f"[bold blue]{self.name} 开始创建拉取请求[/bold blue]"))
            self.log_state_entry(state)
            
            if not state.get("fix_solution") or not state.get("branch_name"):
                state["error_info"] = "缺少修复方案或分支信息，无法创建PR"
                self.log_state_exit(state, "END")
                return state
            
            fix_solution = state["fix_solution"]
            branch_name = state["branch_name"]
            smell_key = fix_solution["smellKey"]
            
            # 准备PR参数
            pr_description = Config.PR_DESCRIPTION_TEMPLATE.format(
                smell_key=smell_key,
                description=fix_solution["description"],
                file_path=fix_solution["filePath"],
                task_id=Config.AZURE_DEVOPS_TASK_ID,
            )

            reviewers = []
            if fix_solution["assignee"]:
                reviewers.append(fix_solution["assignee"])
            else:
                print("[yellow]警告：未指定Assignee，将使用默认Reviewer[/yellow]")
                reviewers.append(Config.DEFAULT_REVIEWER)

            work_item_refs: List[int] = []
            if Config.AZURE_DEVOPS_TASK_ID:
                try:
                    work_item_refs.append(int(Config.AZURE_DEVOPS_TASK_ID))
                except ValueError:
                    console.print(
                        f"[yellow]警告：Task ID {Config.AZURE_DEVOPS_TASK_ID} 无法转换为数字，将跳过工作项关联[/yellow]"
                    )

            pr_params = {
                "projectId": Config.AZURE_DEVOPS_PROJECT,
                "repositoryId": Config.AZURE_DEVOPS_REPOSITORY,
                "title": Config.PR_TITLE_TEMPLATE.format(smell_key=smell_key),
                "description": pr_description.strip(),
                "sourceRefName": f"refs/heads/{branch_name}",
                "targetRefName": Config.AZURE_DEVOPS_TARGET_BRANCH,
                "reviewers": reviewers or None,
                "workItemRefs": work_item_refs or None,
            }
            pr_params = {k: v for k, v in pr_params.items() if v not in (None, [], "")}
            
            # 调用Azure DevOps API创建PR
            pr_response = self.mcp_client.call_azure_devops_api("create_pr", pr_params)

            # 解析 pr_response.get("url")，取最后一个 "\" 后的内容作为PR的ID，然后基于"https://navi.united-imaging.com/RT/yourProject/_git/yourProject/pullrequest/xxxxx"的格式拼接URL
            pr_id = pr_response.get("url").split("/")[-1]
            pr_url = f"https://navi.united-imaging.com/RT/yourProject/_git/yourProject/pullrequest/{pr_id}"

            if pr_response:
                pr_info = {
                    "id": pr_response.get("pullRequestId"),
                    "url": pr_url,
                    "title": pr_response.get("title"),
                    "status": pr_response.get("status")
                }
                
                state["pr_info"] = pr_info
                state["current_step"] = "record_keeping"
                state["completed_steps"].append("pr_creation")
                state["messages"].append(AIMessage(content=f"PR创建成功：{pr_info['url']}"))
                
                console.print(f"[green]PR创建成功：{pr_info['url']}[/green]")
                
                # 发送飞书通知
                self._send_feishu_notification(fix_solution["assignee"], pr_info["url"],fix_solution["effort"])
                self.log_state_exit(state, "record_keeping")

                # 然后通知到个人 调用_send_message_to_user 方法
                self._send_message_to_user(
                    fix_solution.get("assignee", ""),
                    pr_info["url"],
                    smell_key,
                    fix_solution.get("description", ""),
                )
                
            else:
                state["error_info"] = "PR创建失败"
                self.log_state_exit(state, "END")
            
            return state
            
        except Exception as e:
            error_msg = f"PR创建失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            state["error_info"] = error_msg
            self.log_state_exit(state, "END")
            return state
    
    def _send_feishu_notification(self, assignee: str, pr_url: str, effort: str):
        """发送飞书通知"""
        try:
            webhook_url = Config.FEISHU_WEBHOOK_URL
            user_email = self._resolve_email_from_guid(assignee)
            if user_email:
                console.print(f"[dim]已解析通知邮箱：{user_email}[/dim]")
            else:
                console.print("[yellow]未在映射中找到对应邮箱，将使用默认负责人[/yellow]")
                user_email = "sonarQube未标记负责人，分配至负责人dong.nihao@united-imaging.com"

            # 如果effort的值是"0min" 则强制改为"5min"
            if effort == "0min":
                effort = "5min"

            # 维护配置文件中total_Effort_time的值，用于后续统计总耗时
            Config.load_total_Effort_time()
            Config.total_Effort_time += int(effort.split("min")[0])
            Config.save_total_Effort_time()
            console.print(f"[dim]总耗时更新为：{Config.total_Effort_time}分钟[/dim]")
            
            payload = {
                "user": user_email or assignee,
                "prLink": pr_url,
                "timeStamp": datetime.now().isoformat(),
                "effort": effort,
                "total_Effort_time": Config.total_Effort_time
            }
            
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 200:
                console.print("[green]飞书通知发送成功[/green]")
                

            else:
                console.print(f"[yellow]飞书通知发送失败: {response.status_code}[/yellow]")

            
                
        except Exception as e:
            console.print(f"[yellow]飞书通知发送异常: {e}[/yellow]")

    def _resolve_email_from_guid(self, guid: str) -> Optional[str]:
        """根据GUID查找邮箱地址"""
        if not guid:
            return None
        try:
            with open(Config.EMAIL_TO_GUID_PATH, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                if isinstance(mapping, dict):
                    for email, mapped_guid in mapping.items():
                        if mapped_guid == guid:
                            return email
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            console.print(f"[yellow]邮箱映射文件读取失败: {exc}[/yellow]")
        return None
    
    def _send_message_to_user(
        self,
        assignee_guid: str,
        pr_url: str,
        smell_key: str,
        description: str,
    ) -> None:
        """通过飞书私信通知具体负责人处理新的PR."""

        try:
            if not assignee_guid:
                console.print("[yellow]未提供负责人GUID，跳过飞书私信通知[/yellow]")
                return

            email = self._resolve_email_from_guid(assignee_guid)
            if not email:
                console.print("[yellow]未从GUID解析到邮箱，无法发送飞书私信[/yellow]")
                return

            open_id = self._resolve_open_id_from_email(email)
            if not open_id:
                console.print(f"[yellow]邮箱 {email} 未找到对应的OpenID，无法发送飞书私信[/yellow]")
                return

            try:
                lark = importlib.import_module("lark_oapi")
                im_v1 = importlib.import_module("lark_oapi.api.im.v1")
                CreateMessageRequest = getattr(im_v1, "CreateMessageRequest")
                CreateMessageRequestBody = getattr(im_v1, "CreateMessageRequestBody")
            except ImportError as exc:
                console.print(
                    f"[yellow]未安装lark-oapi SDK，无法发送飞书私信: {exc}。请运行 `pip install lark-oapi`[/yellow]"
                )
                return
            except AttributeError as exc:
                console.print(
                    f"[yellow]lark-oapi SDK 版本不兼容，缺少必要类：{exc}。请检查依赖版本[/yellow]"
                )
                return

            client = (
                lark.Client.builder()
                .app_id(Config.FEISHU_APP_ID)
                .app_secret(Config.FEISHU_APP_SECRET)
                .log_level(lark.LogLevel.ERROR)
                .build()
            )

            message_lines = [
                "你有新的SonarQube自动修复PR待处理：",
                pr_url,
                f"异味Key：{smell_key}" if smell_key else None,
                f"修复说明：{description}" if description else None,
            ]
            message_text = "\n".join(filter(None, message_lines))

            request = (
                CreateMessageRequest.builder()
                .receive_id_type("open_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(open_id)
                    .msg_type("text")
                    .content(json.dumps({"text": message_text}, ensure_ascii=False))
                    .uuid(str(uuid4()))
                    .build()
                )
                .build()
            )

            response = client.im.v1.message.create(request)

            if not response.success():
                try:
                    error_detail = json.dumps(
                        json.loads(response.raw.content),
                        indent=2,
                        ensure_ascii=False,
                    )
                except Exception:
                    error_detail = str(response.raw.content)
                console.print(
                    f"[yellow]飞书私信发送失败，code: {response.code}, msg: {response.msg}, detail: {error_detail}[/yellow]"
                )
                return

            console.print(f"[green]已向 {email} 发送飞书私信通知[/green]")

        except Exception as exc:
            console.print(f"[yellow]发送飞书私信时出现异常: {exc}[/yellow]")

    def _resolve_open_id_from_email(self, email: str) -> Optional[str]:
        """根据邮箱查找飞书OpenID"""
        if not email:
            return None
        try:
            with open(Config.EMAIL_TO_OPEN_ID_PATH, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                if isinstance(mapping, dict):
                    return mapping.get(email)
        except FileNotFoundError as exc:
            console.print(f"[yellow]OpenID映射文件不存在: {exc}[/yellow]")
        except json.JSONDecodeError as exc:
            console.print(f"[yellow]OpenID映射文件解析失败: {exc}[/yellow]")
        return None



class RecordKeeperAgent(BaseAgent):
    """记录保存Agent"""
    
    def __init__(self, mcp_client: MCPClient):
        super().__init__("RecordKeeperAgent", mcp_client)
    
    def keep_record(self, state: WorkflowState) -> WorkflowState:
        """
        保存处理记录
        
        参数:
            state (WorkflowState): 当前工作流状态
            
        返回:
            WorkflowState: 更新后的工作流状态
        """
        try:
            console.print(Panel(f"[bold blue]{self.name} 开始保存处理记录[/bold blue]"))
            self.log_state_entry(state)
            
            if not state.get("smell_data") or not state.get("pr_info"):
                state["error_info"] = "缺少异味数据或PR信息，无法保存记录"
                self.log_state_exit(state, "END")
                return state
            
            smell_data = state["smell_data"]
            pr_info = state["pr_info"]
            fix_solution = state.get("fix_solution", {})
            
            # 准备记录数据
            record = {
                "key": smell_data["key"],
                "processedDate": datetime.now().isoformat(),
                "assignee": fix_solution.get("assignee", ""),
                "prUrl": pr_info["url"],
                "status": "completed",
                "component": smell_data.get("component", "")
            }
            
            # 读取现有记录
            records_file = Config.CODE_SMELL_LIST_PATH
            try:
                with open(records_file, "r", encoding="utf-8") as f:
                    existing_records = json.load(f)
                    if not isinstance(existing_records, list):
                        existing_records = []
            except (FileNotFoundError, json.JSONDecodeError):
                existing_records = []
            
            # 添加新记录
            existing_records.append(record)
            
            # 保存更新后的记录
            with open(records_file, "w", encoding="utf-8") as f:
                json.dump(existing_records, f, ensure_ascii=False, indent=2)
            
            state["current_step"] = "browser_launch"
            state["completed_steps"].append("record_keeping")
            state["messages"].append(AIMessage(content="处理记录保存成功"))
            
            console.print(f"[green]处理记录保存成功，异味Key：{record['key']}[/green]")
            self.log_state_exit(state, "browser_launch")
            return state
            
        except Exception as e:
            error_msg = f"记录保存失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            state["error_info"] = error_msg
            self.log_state_exit(state, "END")
            return state


class BrowserLauncherAgent(BaseAgent):
    """浏览器启动Agent"""
    
    def __init__(self, mcp_client: MCPClient):
        super().__init__("BrowserLauncherAgent", mcp_client)
    
    def launch_browser(self, state: WorkflowState) -> WorkflowState:
        """
        启动浏览器打开PR页面
        
        参数:
            state (WorkflowState): 当前工作流状态
            
        返回:
            WorkflowState: 更新后的工作流状态
        """
        try:
            console.print(Panel(f"[bold blue]{self.name} 开始启动浏览器[/bold blue]"))
            self.log_state_entry(state)
            
            if not state.get("pr_info"):
                state["error_info"] = "缺少PR信息，无法打开浏览器"
                self.log_state_exit(state, "END")
                return state
            
            pr_url = state["pr_info"]["url"]
            
            # 使用系统默认浏览器打开URL
            import webbrowser
            webbrowser.open(pr_url)
            
            state["current_step"] = "completed"
            state["completed_steps"].append("browser_launch")
            state["messages"].append(AIMessage(content=f"浏览器已打开PR页面：{pr_url}"))
            
            console.print(f"[green]浏览器已打开PR页面：{pr_url}[/green]")
            self.log_state_exit(state, "completed")
            return state
            
        except Exception as e:
            error_msg = f"浏览器启动失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            state["error_info"] = error_msg
            self.log_state_exit(state, "END")
            return state


class SonarQubeAutoFixOrchestrator:
    """SonarQube自动修复总控制器"""
    
    def __init__(self):
        """初始化总控制器"""
        console.print(Panel("[bold green]SonarQube自动修复系统启动[/bold green]"))
        
        # 初始化MCP客户端
        self.mcp_client = MCPClient()
        
        # 初始化所有子Agent
        self.issue_analyzer = IssueAnalyzerAgent(self.mcp_client)
        self.workspace_setup = WorkspaceSetupAgent(self.mcp_client)
        self.solution_generator = SolutionGeneratorAgent(self.mcp_client)
        self.fix_executor = FixExecutorAgent(self.mcp_client)
        self.pr_agent = PullRequestAgent(self.mcp_client)
        self.record_keeper = RecordKeeperAgent(self.mcp_client)
        self.browser_launcher = BrowserLauncherAgent(self.mcp_client)
        
        # 创建LangGraph工作流
        self.workflow = self._create_workflow()
        
        console.print("[green]总控制器初始化完成[/green]")
    
    def _create_workflow(self) -> StateGraph:
        """创建LangGraph工作流"""
        
        # 这是一个有向无环图（DAG），可进行拓扑排序，但本质类型仍是DAG。
        
        # 创建状态图
        workflow = StateGraph(WorkflowState)
        
        # 添加节点
        workflow.add_node("issue_analysis", self.issue_analyzer.analyze_issues)
        workflow.add_node("workspace_setup", self.workspace_setup.setup_workspace)
        workflow.add_node("solution_generation", self.solution_generator.generate_solution)
        workflow.add_node("fix_execution", self.fix_executor.execute_fix)
        workflow.add_node("pr_creation", self.pr_agent.create_pull_request)
        workflow.add_node("record_keeping", self.record_keeper.keep_record)
        workflow.add_node("browser_launch", self.browser_launcher.launch_browser)
        
        # 设置入口点
        workflow.add_edge(START, "issue_analysis")
        
        # 添加条件边
        def route_after_issue_analysis(state: WorkflowState) -> str:
            if state.get("error_info"):
                return END
            return "workspace_setup"
        
        def route_after_workspace_setup(state: WorkflowState) -> str:
            if state.get("error_info"):
                return END
            return "solution_generation"
        
        def route_after_solution_generation(state: WorkflowState) -> str:
            if state.get("error_info"):
                return END
            return "fix_execution"
        
        def route_after_fix_execution(state: WorkflowState) -> str:
            if state.get("error_info"):
                return END
            return "pr_creation"
        
        def route_after_pr_creation(state: WorkflowState) -> str:
            if state.get("error_info"):
                return END
            return "record_keeping"
        
        def route_after_record_keeping(state: WorkflowState) -> str:
            if state.get("error_info"):
                return END
            return "browser_launch"
        
        # 设置路由
        workflow.add_conditional_edges("issue_analysis", route_after_issue_analysis)
        workflow.add_conditional_edges("workspace_setup", route_after_workspace_setup)
        workflow.add_conditional_edges("solution_generation", route_after_solution_generation)
        workflow.add_conditional_edges("fix_execution", route_after_fix_execution)
        workflow.add_conditional_edges("pr_creation", route_after_pr_creation)
        workflow.add_conditional_edges("record_keeping", route_after_record_keeping)
        workflow.add_edge("browser_launch", END)
        
        return workflow
    
    #NIHAO TODO: 处理多种异味类型:
    # 问题描述: 当前流程是为一种特定类型的代码异味设计的，如果要处理多种类型的异味，就需要根据不同的异味类型走向不同的分支。
    # 优化思路: 可以根据异味类型（例如，命名规范、逻辑重构等）将流程拆分成多个分支，每个分支处理一种类型的异味。
    # 实现: 在 issue_analysis 节点之后，根据分析出的异味类型决定走向不同的分支。例如，如果分析出的是命名规范问题，就走向命名规范分支；如果是逻辑重构问题，就走向逻辑重构分支。

    
    def run(self) -> Dict[str, Any]:
        """
        运行自动修复流程
        
        返回:
            Dict: 执行结果
        """
        try:
            console.print(Panel("[bold yellow]开始执行自动修复流程[/bold yellow]"))
            
            # 初始化状态
            initial_state = WorkflowState(
                messages=[HumanMessage(content="开始SonarQube代码异味自动修复流程")],
                current_step="issue_analysis",
                smell_data=None,
                branch_name=None,
                fix_solution=None,
                pr_info=None,
                error_info=None,
                completed_steps=[]
            )
            
            # 编译并运行工作流
            app = self.workflow.compile(checkpointer=MemorySaver())
            
            # 执行工作流
            config = {"configurable": {"thread_id": "sonarqube_autofix"}}
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task(description="执行自动修复流程...", total=None)
                
                final_state = None
                for step in app.stream(initial_state, config):
                    step_name = list(step.keys())[0]
                    step_data = step[step_name]
                    progress.update(task, description=f"执行步骤: {step_name}")
                    next_hop = step_data.get("current_step") or "END"
                    if step_data.get("error_info"):
                        console.print(f"[red]节点 {step_name} 出现错误，终止于: {step_data.get('error_info')}[/red]")
                    else:
                        console.print(f"[bold magenta]节点 {step_name} 完成，下一节点: {next_hop}[/bold magenta]")
                    final_state = step_data
            
            # 生成执行结果
            result = {
                "success": not bool(final_state.get("error_info")),
                "error": final_state.get("error_info"),
                "completed_steps": final_state.get("completed_steps", []),
                "smell_data": final_state.get("smell_data"),
                "pr_info": final_state.get("pr_info")
            }
            
            # 显示执行结果
            self._display_result(result)
            
            return result
            
        except Exception as e:
            error_msg = f"工作流执行失败: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            console.print(f"[red]详细错误信息：{traceback.format_exc()}[/red]")
            return {
                "success": False,
                "error": error_msg,
                "completed_steps": [],
                "smell_data": None,
                "pr_info": None
            }
    
    def _display_result(self, result: Dict[str, Any]):
        """显示执行结果"""
        
        if result["success"]:
            console.print(Panel("[bold green]✅ 自动修复流程执行成功！[/bold green]"))
            
            table = Table(title="执行摘要")
            table.add_column("项目", style="cyan")
            table.add_column("值", style="green")
            
            table.add_row("状态", "成功")
            table.add_row("完成步骤数", str(len(result["completed_steps"])))
            
            if result["smell_data"]:
                table.add_row("处理的异味Key", result["smell_data"]["key"])
            
            if result["pr_info"]:
                table.add_row("PR链接", result["pr_info"]["url"])
            
            console.print(table)
            
        else:
            console.print(Panel(f"[bold red]❌ 自动修复流程执行失败[/bold red]"))
            console.print(f"[red]错误信息：{result['error']}[/red]")
            
            if result["completed_steps"]:
                console.print(f"[yellow]已完成步骤：{', '.join(result['completed_steps'])}[/yellow]")


def main():
    """主函数"""
    try:
        # 创建总控制器并运行
        orchestrator = SonarQubeAutoFixOrchestrator()
        result = orchestrator.run()
        
        # 根据结果设置退出码
        exit_code = 0 if result["success"] else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断执行[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]系统错误: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()