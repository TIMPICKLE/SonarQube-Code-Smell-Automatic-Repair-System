"""
配置文件
存储系统运行所需的各种配置参数
"""

import os
from typing import Dict, Any
import json

class Config:
    """系统配置类"""
    
    # 基础配置
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    
    # MCP配置
    MCP_CONFIG_PATH = os.path.join(PROJECT_ROOT, "localJSON", "mcp.json")
    
    # 本地JSON文件路径
    CODE_SMELL_LIST_PATH = os.path.join(PROJECT_ROOT, "localJSON", "codeSmallList.json")
    EMAIL_TO_GUID_PATH = os.path.join(PROJECT_ROOT, "localJSON", "emailToGuid.json")
    
    # SonarQube配置
    SONARQUBE_PROJECT_KEY = "SONARQUBE_PROJECT_KEY"
    SONARQUBE_BRANCH = "SONARQUBE_BRANCH"
    SONARQUBE_SEVERITIES = ["INFO"]
    SONARQUBE_TYPES = ["CODE_SMELL"]
    
    # Azure DevOps配置
    AZURE_DEVOPS_TARGET_BRANCH = "refs/heads/master"
    AZURE_DEVOPS_TASK_ID = "88888"
    AZURE_DEVOPS_PROJECT = "PROJECT_NAME"
    
    # 飞书配置
    FEISHU_WEBHOOK_URL = "FEISHU_WEBHOOK_URL"
    FEISHU_APP_ID = "FEISHU_APP_ID"
    FEISHU_APP_SECRET = "FEISHU_APP_SECRET"
    
    # Git配置
    GIT_COMMIT_MESSAGE_TEMPLATE = "fix: 解决SonarQube异味 {smell_key} - {description}"
    GIT_BRANCH_NAME_TEMPLATE = "fix-sonar-{smell_key}"
    GIT_REPO_PATH = os.path.join(PROJECT_ROOT, "yourProject")
    
    # PR配置
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
    
    # 日志配置
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Azure DevOps额外配置
    AZURE_DEVOPS_REPOSITORY = "AZURE_DEVOPS_REPOSITORY"

    MCP_CONFIG_PATH = os.path.join(PROJECT_ROOT, "localJSON", "mcp.json")

    CODE_SMELL_LIST_PATH = os.path.join(PROJECT_ROOT, "localJSON", "codeSmallList.json")

    # 默认审查者 NIHAO.DONG
    DEFAULT_REVIEWER = "99990f0c-0000-1111-888a-ff6f7622a566"

    # feishu webhook url
    FEISHU_WEBHOOK_URL = "FEISHU_WEBHOOK_URL"

    TOTAL_EFFORT_STATE_PATH = os.path.join(PROJECT_ROOT, "localJSON", "effort_state.json")

    total_Effort_time = 0

    # "localJSON/emailToGuid.json"
    EMAIL_TO_GUID_PATH = os.path.join(PROJECT_ROOT, "localJSON", "emailToGuid.json")
    EMAIL_TO_OPEN_ID_PATH = os.path.join(PROJECT_ROOT, "localJSON", "emialtoOpenId.json")

    @classmethod
    def load_total_Effort_time(cls):
        try:
            with open(cls.TOTAL_EFFORT_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cls.total_Effort_time = int(data.get("total_Effort_time", 0))
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            cls.total_Effort_time = 0

    @classmethod
    def save_total_Effort_time(cls):
        os.makedirs(os.path.dirname(cls.TOTAL_EFFORT_STATE_PATH), exist_ok=True)
        payload = {"total_Effort_time": int(cls.total_Effort_time)}
        with open(cls.TOTAL_EFFORT_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


    @classmethod
    def get_sonarqube_params(cls) -> Dict[str, Any]:
        """获取SonarQube查询参数"""
        # 代码中已经做分页处理，此处不再重复处理分页逻辑，直接返回所有参数即可。
        params = {
            "project_key": cls.SONARQUBE_PROJECT_KEY,
            "branch": cls.SONARQUBE_BRANCH,
            "severities": cls.SONARQUBE_SEVERITIES,
            "types": cls.SONARQUBE_TYPES,
            "s": "CREATION_DATE",
            "asc": False,
            "page": "1",
            "page_size": "50",
            "status":"OPEN"
        }
        return {k: v for k, v in params.items() if v is not None}
    
    @classmethod
    def get_pr_labels(cls) -> list:
        """获取PR标签"""
        return ["bug-fix", "sonarqube", "automated"]