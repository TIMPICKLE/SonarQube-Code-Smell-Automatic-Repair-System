#!/usr/bin/env python3
"""
SonarQube自动修复系统 - 命令行界面
提供简单的命令行工具来管理和运行系统
"""

import argparse
import sys
import json
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def show_status():
    """显示系统状态"""
    console.print(Panel("[bold blue]SonarQube自动修复系统状态[/bold blue]"))
    
    # 检查配置文件
    config_files = {
        "MCP配置": "localJSON/mcp.json",
        "邮箱映射": "localJSON/emailToGuid.json", 
        "处理记录": "localJSON/codeSmallList.json"
    }
    
    table = Table(title="配置文件状态")
    table.add_column("文件", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("大小", style="yellow")
    
    for name, path in config_files.items():
        if Path(path).exists():
            size = Path(path).stat().st_size
            table.add_row(name, "✅ 存在", f"{size} bytes")
        else:
            table.add_row(name, "❌ 缺失", "0 bytes")
    
    console.print(table)
    
    # 显示处理历史
    try:
        with open("localJSON/codeSmallList.json", "r", encoding="utf-8") as f:
            records = json.load(f)
        console.print(f"\n📊 已处理异味数量: {len(records)}")
        
        if records:
            recent = records[-5:]  # 显示最近5条记录
            history_table = Table(title="最近处理记录")
            history_table.add_column("异味Key", style="cyan")
            history_table.add_column("处理时间", style="green")
            history_table.add_column("状态", style="yellow")
            
            for record in recent:
                history_table.add_row(
                    record.get("key", ""),
                    record.get("processedDate", "").split("T")[0],
                    record.get("status", "")
                )
            console.print(history_table)
            
    except Exception as e:
        console.print(f"[red]无法读取处理记录: {e}[/red]")

def run_system(dry_run=False):
    """运行自动修复系统"""
    if dry_run:
        console.print("[yellow]干运行模式：不会进行实际修复[/yellow]")
        # 这里可以实现干运行逻辑
        return
    
    console.print("[green]启动SonarQube自动修复系统...[/green]")
    try:
        from main import SonarQubeAutoFixOrchestrator
        orchestrator = SonarQubeAutoFixOrchestrator()
        result = orchestrator.run()
        
        if result["success"]:
            console.print("[green]系统执行成功！[/green]")
        else:
            console.print(f"[red]系统执行失败: {result['error']}[/red]")
            
    except Exception as e:
        console.print(f"[red]系统启动失败: {e}[/red]")

def test_system():
    """运行系统测试"""
    console.print("[blue]运行系统测试...[/blue]")
    try:
        from test_system import main as test_main
        success = test_main()
        if success:
            console.print("[green]所有测试通过![/green]")
        else:
            console.print("[red]部分测试失败![/red]")
    except Exception as e:
        console.print(f"[red]测试执行失败: {e}[/red]")

def reset_records():
    """重置处理记录"""
    console.print("[yellow]重置处理记录...[/yellow]")
    
    if console.input("确认要清空所有处理记录吗？(y/N): ").lower() == 'y':
        try:
            with open("localJSON/codeSmallList.json", "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            console.print("[green]处理记录已重置[/green]")
        except Exception as e:
            console.print(f"[red]重置失败: {e}[/red]")
    else:
        console.print("[yellow]操作已取消[/yellow]")

def show_help():
    """显示帮助信息"""
    help_text = """
[bold blue]SonarQube自动修复系统 - 命令行工具[/bold blue]

[green]可用命令:[/green]
  status    - 显示系统状态和配置
  run       - 运行自动修复流程
  test      - 运行系统测试
  reset     - 重置处理记录
  help      - 显示此帮助信息

[green]选项:[/green]
  --dry-run - 干运行模式（仅限run命令）
  --verbose - 详细输出

[green]示例:[/green]
  python cli.py status          # 显示系统状态
  python cli.py run            # 运行修复流程
  python cli.py run --dry-run  # 干运行模式
  python cli.py test           # 运行测试
"""
    console.print(Panel(help_text))

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SonarQube自动修复系统命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("command", nargs="?", default="help",
                       choices=["status", "run", "test", "reset", "help"],
                       help="要执行的命令")
    parser.add_argument("--dry-run", action="store_true",
                       help="干运行模式（不执行实际修复）")
    parser.add_argument("--verbose", action="store_true",
                       help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        console.print(f"[dim]执行命令: {args.command}[/dim]")
    
    try:
        if args.command == "status":
            show_status()
        elif args.command == "run":
            run_system(dry_run=args.dry_run)
        elif args.command == "test":
            test_system()
        elif args.command == "reset":
            reset_records()
        elif args.command == "help":
            show_help()
        else:
            show_help()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]操作被用户中断[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]执行失败: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()