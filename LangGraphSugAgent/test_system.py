"""
测试脚本 - 验证SonarQube自动修复系统
"""

import os
import sys
import json
from pathlib import Path

from config import Config

def setup_test_environment():
    """设置测试环境"""
    print("🔧 设置测试环境...")
    
    # 确保localJSON目录存在
    local_json_dir = Path("localJSON")
    local_json_dir.mkdir(exist_ok=True)
    
    # 初始化codeSmallList.json（如果为空）
    code_smell_file = local_json_dir / "codeSmallList.json"
    if not code_smell_file.exists() or code_smell_file.stat().st_size == 0:
        with open(code_smell_file, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print(f"✅ 已初始化 {code_smell_file}")
    
    # 检查必要文件
    required_files = [
        "localJSON/mcp.json",
        "localJSON/emailToGuid.json",
        "APIs/kimi_k2_api.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ 缺少必要文件: {missing_files}")
        return False
    
    print("✅ 测试环境设置完成")
    return True

def test_imports():
    """测试导入"""
    print("📦 测试模块导入...")
    
    try:
        # 测试基础库导入
        import langgraph
        import langchain
        import git
        import requests
        import rich
        print("✅ 基础库导入成功")
        
        # 测试自定义模块导入
        sys.path.append(os.path.join(os.path.dirname(__file__), 'APIs'))
        from APIs.kimi_k2_api import call_kimi, initialize_kimi_client
        print("✅ Kimi API模块导入成功")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_kimi_api():
    """测试Kimi API连接"""
    print("🤖 测试Kimi API连接...")
    
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'APIs'))
        from APIs.kimi_k2_api import call_kimi, initialize_kimi_client
        
        # 测试API连接
        client = initialize_kimi_client()
        response = call_kimi("你好，请回复'测试成功'", "你是一个测试助手", client)
        
        if response and "测试" in response:
            print("✅ Kimi API连接成功")
            print(f"   响应: {response[:50]}...")
            return True
        else:
            print(f"⚠️ Kimi API响应异常: {response}")
            return False
            
    except Exception as e:
        print(f"❌ Kimi API测试失败: {e}")
        return False

def test_file_operations():
    """测试文件操作"""
    print("📁 测试文件操作...")
    
    try:
        # 测试JSON文件读取
        with open("localJSON/emailToGuid.json", "r", encoding="utf-8") as f:
            email_data = json.load(f)
        print(f"✅ 读取邮箱映射文件成功，包含 {len(email_data)} 条记录")
        
        with open("localJSON/mcp.json", "r", encoding="utf-8") as f:
            mcp_data = json.load(f)
        print(f"✅ 读取MCP配置文件成功，包含 {len(mcp_data.get('mcpServers', {}))} 个服务器")
        
        return True
        
    except Exception as e:
        print(f"❌ 文件操作测试失败: {e}")
        return False

def test_git_environment():
    """测试Git环境"""
    print("🔀 测试Git环境...")
    
    try:
        import git
        
        repo_path = Path(Config.GIT_REPO_PATH)
        if (repo_path / ".git").exists():
            repo = git.Repo(repo_path)
            current_branch = repo.active_branch.name
            print(f"✅ Git仓库检测成功[{repo_path}]，当前分支: {current_branch}")
            return True
        else:
            print(f"⚠️ 指定目录 {repo_path} 不是Git仓库，Git操作将被跳过")
            return True
            
    except Exception as e:
        print(f"❌ Git环境测试失败: {e}")
        return False

def run_dry_test():
    """运行干燥测试（不执行实际修复）"""
    print("🧪 运行系统干燥测试...")
    
    try:
        # 导入主模块
        from main import SonarQubeAutoFixOrchestrator
        
        # 创建总控制器实例
        orchestrator = SonarQubeAutoFixOrchestrator()
        print("✅ 总控制器初始化成功")
        
        # 测试工作流创建
        workflow = orchestrator._create_workflow()
        print("✅ 工作流创建成功")
        
        # 显示工作流节点
        nodes = list(workflow.nodes.keys())
        print(f"✅ 工作流包含节点: {nodes}")
        
        return True
        
    except Exception as e:
        print(f"❌ 干燥测试失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False

def main():
    """主测试函数"""
    print("🚀 SonarQube自动修复系统测试开始")
    print("=" * 50)
    
    tests = [
        ("环境设置", setup_test_environment),
        ("模块导入", test_imports),
        ("文件操作", test_file_operations),
        ("Git环境", test_git_environment),
        ("Kimi API", test_kimi_api),
        ("系统初始化", run_dry_test)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 执行测试: {test_name}")
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ 测试失败: {test_name}")
        except Exception as e:
            print(f"❌ 测试异常: {test_name} - {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统准备就绪。")
        print("\n💡 运行系统命令: python main.py")
    else:
        print("⚠️ 部分测试失败，请检查配置和环境。")
    
    return passed == total

if __name__ == "__main__":
    main()