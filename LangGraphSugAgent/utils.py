"""
工具类模块
提供各种实用工具函数
"""

import json
import os
import logging
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

class FileUtils:
    """文件操作工具类"""
    
    @staticmethod
    def read_json(file_path: str, default: Any = None) -> Any:
        """
        读取JSON文件
        
        参数:
            file_path (str): 文件路径
            default (Any): 文件不存在或解析失败时的默认值
            
        返回:
            Any: JSON数据
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"读取JSON文件失败: {file_path}, 错误: {e}")
            return default if default is not None else {}
    
    @staticmethod
    def write_json(file_path: str, data: Any, indent: int = 2) -> bool:
        """
        写入JSON文件
        
        参数:
            file_path (str): 文件路径
            data (Any): 要写入的数据
            indent (int): 缩进空格数
            
        返回:
            bool: 是否写入成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            return True
        except Exception as e:
            logging.error(f"写入JSON文件失败: {file_path}, 错误: {e}")
            return False
    
    @staticmethod
    def ensure_directory(directory_path: str) -> bool:
        """
        确保目录存在，如不存在则创建
        
        参数:
            directory_path (str): 目录路径
            
        返回:
            bool: 是否成功
        """
        try:
            os.makedirs(directory_path, exist_ok=True)
            return True
        except Exception as e:
            logging.error(f"创建目录失败: {directory_path}, 错误: {e}")
            return False


class GitUtils:
    """Git操作工具类"""
    
    @staticmethod
    def is_git_repository(path: str = ".") -> bool:
        """
        检查指定路径是否为Git仓库
        
        参数:
            path (str): 要检查的路径
            
        返回:
            bool: 是否为Git仓库
        """
        git_path = os.path.join(path, ".git")
        return os.path.exists(git_path)
    
    @staticmethod
    def get_current_branch(repo_path: str = ".") -> Optional[str]:
        """
        获取当前Git分支名
        
        参数:
            repo_path (str): 仓库路径
            
        返回:
            Optional[str]: 当前分支名，失败时返回None
        """
        try:
            import git
            repo = git.Repo(repo_path)
            return repo.active_branch.name
        except Exception as e:
            logging.warning(f"获取当前分支失败: {e}")
            return None
    
    @staticmethod
    def generate_branch_name(smell_key: str) -> str:
        """
        生成分支名称
        
        参数:
            smell_key (str): 异味Key
            
        返回:
            str: 分支名称
        """
        # 清理异味Key，确保符合Git分支命名规范
        clean_key = smell_key.replace(":", "-").replace("/", "-")
        return f"fix-sonar-{clean_key}"


class DateTimeUtils:
    """日期时间工具类"""
    
    @staticmethod
    def now_iso() -> str:
        """
        获取当前时间的ISO格式字符串
        
        返回:
            str: ISO格式的当前时间
        """
        return datetime.now().isoformat()
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        格式化日期时间
        
        参数:
            dt (datetime): 要格式化的日期时间
            format_str (str): 格式字符串
            
        返回:
            str: 格式化后的字符串
        """
        return dt.strftime(format_str)


class ValidationUtils:
    """验证工具类"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        验证邮箱格式
        
        参数:
            email (str): 邮箱地址
            
        返回:
            bool: 是否为有效邮箱
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_guid(guid: str) -> bool:
        """
        验证GUID格式
        
        参数:
            guid (str): GUID字符串
            
        返回:
            bool: 是否为有效GUID
        """
        import re
        pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        return bool(re.match(pattern, guid))
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        验证URL格式
        
        参数:
            url (str): URL字符串
            
        返回:
            bool: 是否为有效URL
        """
        import re
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, url))


class LoggingUtils:
    """日志工具类"""
    
    @staticmethod
    def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
        """
        设置日志配置
        
        参数:
            level (str): 日志级别
            log_file (Optional[str]): 日志文件路径，为None时只输出到控制台
            
        返回:
            logging.Logger: 配置好的日志记录器
        """
        # 清除现有的处理器
        logging.getLogger().handlers.clear()
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 设置日志级别
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # 创建根日志记录器
        logger = logging.getLogger()
        logger.setLevel(log_level)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 添加文件处理器（如果指定了日志文件）
        if log_file:
            # 确保日志目录存在
            FileUtils.ensure_directory(os.path.dirname(log_file))
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger


class TextUtils:
    """文本处理工具类"""
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """
        截断文本
        
        参数:
            text (str): 原始文本
            max_length (int): 最大长度
            suffix (str): 截断后的后缀
            
        返回:
            str: 截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，移除不安全字符
        
        参数:
            filename (str): 原始文件名
            
        返回:
            str: 清理后的文件名
        """
        import re
        # 移除或替换不安全字符
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除前后空格和点号
        sanitized = sanitized.strip('. ')
        return sanitized
    
    @staticmethod
    def extract_file_extension(filename: str) -> str:
        """
        提取文件扩展名
        
        参数:
            filename (str): 文件名
            
        返回:
            str: 文件扩展名（包含点号）
        """
        return Path(filename).suffix


class ErrorHandler:
    """错误处理工具类"""
    
    @staticmethod
    def safe_execute(func, *args, default=None, **kwargs):
        """
        安全执行函数，捕获异常并返回默认值
        
        参数:
            func: 要执行的函数
            *args: 函数参数
            default: 异常时的默认返回值
            **kwargs: 函数关键字参数
            
        返回:
            执行结果或默认值
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"函数执行失败: {func.__name__}, 错误: {e}")
            return default
    
    @staticmethod
    def format_error(error: Exception) -> Dict[str, str]:
        """
        格式化错误信息
        
        参数:
            error (Exception): 异常对象
            
        返回:
            Dict[str, str]: 格式化的错误信息
        """
        import traceback
        return {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc()
        }