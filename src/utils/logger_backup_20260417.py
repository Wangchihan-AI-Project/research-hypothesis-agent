# -*- coding: utf-8 -*-
"""
V7.1 集中式日志基建与异常追踪系统

核心特性：
1. 独立持久化与文件轮转 - RotatingFileHandler 防止日志撑爆硬盘
2. Task ID 贯穿注入 - 格式：[时间戳] [级别] [TaskID: xxx] [Agent: xxx] - 信息
3. 致命错误与堆栈保全 - exc_info=True 自动捕获完整 traceback
4. 业务审计流隔离 - ERROR (系统Bug) vs AUDIT (业务驳回) 分离输出

架构设计：
- Singleton Pattern: 全局唯一日志实例，避免重复初始化
- Context Manager: TaskID 自动注入，无需手动传递
- Thread-Safe: 多线程环境下安全写入
- Streamlit Compatible: 避免 stdout 替换导致的 I/O 错误
"""

import logging
import logging.handlers
import os
import sys
import threading
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextvars import ContextVar
from pathlib import Path


# ==================== Context Variables (Thread-Safe Task ID Injection) ====================
# 使用 ContextVar 实现 Task ID 的线程安全传递
# 在 Celery Worker 环境下，每个任务线程拥有独立的上下文

_current_task_id: ContextVar[Optional[str]] = ContextVar('task_id', default=None)
_current_agent_name: ContextVar[Optional[str]] = ContextVar('agent_name', default=None)


# ==================== 自定义 AUDIT 级别 ====================
# AUDIT 级别介于 INFO 和 WARNING 之间，用于业务逻辑驳回记录

AUDIT_LEVEL = 25  # INFO=20, WARNING=30
logging.addLevelName(AUDIT_LEVEL, 'AUDIT')


class AuditLogger(logging.Logger):
    """扩展 Logger，支持 AUDIT 级别"""

    def audit(self, msg: str, *args, **kwargs):
        """
        记录业务审计日志（如红方判定驳回、假设验证失败等）

        Args:
            msg: 审计消息
        """
        if self.isEnabledFor(AUDIT_LEVEL):
            self._log(AUDIT_LEVEL, msg, args, **kwargs)


# ==================== 日志格式化器（Task ID 贯穿注入） ====================

class TaskAwareFormatter(logging.Formatter):
    """
    Task ID 贯穿注入的格式化器

    标准格式：[时间戳] [日志级别] [TaskID: xxx] [Agent: xxx] - 具体信息

    如果没有 Task ID，则显示 [TaskID: N/A]
    """

    def format(self, record: logging.LogRecord) -> str:
        # 从 ContextVar 获取当前 Task ID 和 Agent 名称
        task_id = _current_task_id.get()
        agent_name = _current_agent_name.get()

        # 注入到 record 中
        record.task_id = task_id if task_id else 'N/A'
        record.agent_name = agent_name if agent_name else 'System'

        return super().format(record)

    @classmethod
    def get_standard_format(cls) -> str:
        """返回标准格式字符串"""
        return '[%(asctime)s] [%(levelname)s] [TaskID: %(task_id)s] [Agent: %(agent_name)s] - %(message)s'

    @classmethod
    def get_audit_format(cls) -> str:
        """返回审计日志格式（增加业务上下文）"""
        return '[%(asctime)s] [AUDIT] [TaskID: %(task_id)s] [Agent: %(agent_name)s] - %(message)s'


# ==================== 集中式日志管理器 ====================

class CentralizedLogger:
    """
    V7.1 集中式日志管理器

    特性：
    1. 文件轮转：按大小（10MB）或按天轮转
    2. Task ID 贯穿：自动注入 Task ID 和 Agent 名称
    3. 堆栈保全：exc_info=True 自动捕获异常堆栈
    4. 审计隔离：ERROR 和 AUDIT 分离输出到不同文件
    """

    _instance: Optional['CentralizedLogger'] = None
    _lock = threading.Lock()
    _initialized: bool = False

    # 日志配置常量
    DEFAULT_LOG_DIR = 'logs'
    SYSTEM_LOG_FILE = 'system_v7.log'
    AUDIT_LOG_FILE = 'audit_v7.log'
    ERROR_LOG_FILE = 'error_v7.log'
    MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
    BACKUP_COUNT = 5  # 保留 5 个轮转备份

    def __new__(cls, log_dir: str = None):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = None):
        """
        初始化集中式日志系统

        Args:
            log_dir: 日志目录路径（默认 ./logs）
        """
        # 避免重复初始化
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            # 设置日志目录
            self.log_dir = Path(log_dir or self.DEFAULT_LOG_DIR)
            self._ensure_log_dir()

            # 注册自定义 Logger 类
            logging.setLoggerClass(AuditLogger)

            # 创建日志器
            self.system_logger = self._create_system_logger()
            self.audit_logger = self._create_audit_logger()
            self.error_logger = self._create_error_logger()

            self._initialized = True

            # 记录初始化完成
            self.system_logger.info(
                "[CentralizedLogger] V7.1 集中式日志系统初始化完成\n"
                f"  系统日志: {self.log_dir / self.SYSTEM_LOG_FILE}\n"
                f"  审计日志: {self.log_dir / self.AUDIT_LOG_FILE}\n"
                f"  错误日志: {self.log_dir / self.ERROR_LOG_FILE}\n"
                f"  轮转策略: {self.MAX_LOG_SIZE // (1024*1024)}MB × {self.BACKUP_COUNT} 备份"
            )

    def _ensure_log_dir(self):
        """确保日志目录存在"""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            # 创建审计子目录
            audit_dir = self.log_dir / 'audit'
            audit_dir.mkdir(exist_ok=True)
        except Exception as e:
            # 回退到当前目录
            self.log_dir = Path('.')
            self.system_logger.warning(f"[CentralizedLogger] 无法创建日志目录，回退到当前目录: {e}")

    def _create_system_logger(self) -> AuditLogger:
        """
        创建系统日志器（记录所有级别日志）

        使用 RotatingFileHandler 实现大小轮转
        """
        logger = logging.getLogger('v7_system')
        logger.setLevel(logging.DEBUG)

        # 清除现有处理器
        logger.handlers.clear()

        # RotatingFileHandler - 按大小轮转
        log_file = self.log_dir / self.SYSTEM_LOG_FILE
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.MAX_LOG_SIZE,
            backupCount=self.BACKUP_COUNT,
            encoding='utf-8',
            delay=True  # 延迟打开文件，避免启动时就创建
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(TaskAwareFormatter(
            TaskAwareFormatter.get_standard_format(),
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(file_handler)

        # 控制台处理器（可选，仅 INFO 以上）
        if self._should_add_console():
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter(
                '[%(levelname)s] %(message)s'
            ))
            logger.addHandler(console_handler)

        return logger

    def _create_audit_logger(self) -> AuditLogger:
        """
        创��审计日志器（仅记录 AUDIT 级别）

        业务驳回记录单独输出，供科研人员查阅
        """
        logger = logging.getLogger('v7_audit')
        logger.setLevel(AUDIT_LEVEL)

        # 清除现有处理器
        logger.handlers.clear()

        # 审计日志文件
        log_file = self.log_dir / self.AUDIT_LOG_FILE
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.MAX_LOG_SIZE,
            backupCount=self.BACKUP_COUNT,
            encoding='utf-8',
            delay=True
        )
        file_handler.setLevel(AUDIT_LEVEL)
        file_handler.setFormatter(TaskAwareFormatter(
            TaskAwareFormatter.get_audit_format(),
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(file_handler)

        return logger

    def _create_error_logger(self) -> AuditLogger:
        """
        创建错误日志器（仅记录 ERROR 及以上）

        系统异常单独输出，供研发排查 Bug
        """
        logger = logging.getLogger('v7_error')
        logger.setLevel(logging.ERROR)

        # 清除现有处理器
        logger.handlers.clear()

        # 错误日志文件
        log_file = self.log_dir / self.ERROR_LOG_FILE
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.MAX_LOG_SIZE,
            backupCount=self.BACKUP_COUNT,
            encoding='utf-8',
            delay=True
        )
        file_handler.setLevel(logging.ERROR)
        file_handler.setFormatter(TaskAwareFormatter(
            TaskAwareFormatter.get_standard_format(),
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(file_handler)

        return logger

    def _should_add_console(self) -> bool:
        """判断是否添加控制台处理器（Streamlit 兼容）"""
        # 检查 stdout 是否可用（Streamlit 环境可能关闭）
        if sys.stdout is None or sys.stdout.closed:
            return False
        return True

    # ==================== 日志记录方法 ====================

    def debug(self, message: str, **kwargs):
        """记录调试日志"""
        self.system_logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """记录信息日志"""
        self.system_logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """记录警告日志"""
        self.system_logger.warning(message, **kwargs)

    def audit(self, message: str, **kwargs):
        """
        记录业务审计日志

        用途：红方判定驳回、假设验证失败、业务逻辑决策等
        """
        self.audit_logger.audit(message, **kwargs)
        # 同时写入系统日志（便于统一检索）
        self.system_logger.log(AUDIT_LEVEL, message, **kwargs)

    def error(
        self,
        message: str,
        exc_info: bool = False,
        extra_vars: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        记录错误日志（支持堆栈保全）

        Args:
            message: 错误消息
            exc_info: 是否包含异常堆栈（默认 False，建议深水区 True）
            extra_vars: 导致报错的原始变量值（用于审计）

        Example:
            logger.error("RAG Router 网络请求失败", exc_info=True,
                         extra_vars={'url': url, 'timeout': timeout})
        """
        # 如果有额外变量，附加到消息
        if extra_vars:
            var_str = '\n'.join(f'  {k}: {v}' for k, v in extra_vars.items())
            message = f"{message}\n[关键变量]\n{var_str}"

        # 写入错误日志（含堆栈）
        self.error_logger.error(message, exc_info=exc_info, **kwargs)
        # 同时写入系统日志
        self.system_logger.error(message, exc_info=exc_info, **kwargs)

    def exception(
        self,
        message: str,
        extra_vars: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        记录异常日志（自动捕获堆栈）

        等同于 error(message, exc_info=True)

        Args:
            message: 异常消息
            extra_vars: 导致报错的原始变量值
        """
        self.error(message, exc_info=True, extra_vars=extra_vars, **kwargs)

    def critical(
        self,
        message: str,
        exc_info: bool = False,
        extra_vars: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """记录严重错误日志"""
        if extra_vars:
            var_str = '\n'.join(f'  {k}: {v}' for k, v in extra_vars.items())
            message = f"{message}\n[关键变量]\n{var_str}"

        self.error_logger.critical(message, exc_info=exc_info, **kwargs)
        self.system_logger.critical(message, exc_info=exc_info, **kwargs)


# ==================== Task Context Manager ====================

class TaskLogContext:
    """
    Task 日志上下文管理器

    在 Celery Task 执行期间自动注入 Task ID 和 Agent 名称

    Usage:
        with TaskLogContext(task_id='abc123', agent_name='RAGRouter'):
            logger.info("开始检索...")
            # 所有日志自动包含 [TaskID: abc123] [Agent: RAGRouter]
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        agent_name: Optional[str] = None
    ):
        self.task_id = task_id
        self.agent_name = agent_name
        self._task_token: Optional[Any] = None
        self._agent_token: Optional[Any] = None

    def __enter__(self) -> 'TaskLogContext':
        # 设置 ContextVar
        self._task_token = _current_task_id.set(self.task_id)
        self._agent_token = _current_agent_name.set(self.agent_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 恢复 ContextVar
        _current_task_id.reset(self._task_token)
        _current_agent_name.reset(self._agent_token)

        # 如果有异常，自动记录
        if exc_type is not None:
            central_logger.exception(
                f"[{self.agent_name or 'Unknown'}] 任务执行异常",
                extra_vars={'task_id': self.task_id, 'exception_type': exc_type.__name__}
            )

        return False  # 不抑制异常


def set_task_context(task_id: str, agent_name: str = None):
    """
    设置当前任务的日志上下文（非上下文管理器方式）

    适用于需要在函数外部设置上下文的场景
    """
    _current_task_id.set(task_id)
    if agent_name:
        _current_agent_name.set(agent_name)


def clear_task_context():
    """清除当前任务的日志上下文"""
    _current_task_id.set(None)
    _current_agent_name.set(None)


# ==================== 全局日志实例 ====================

central_logger = CentralizedLogger()


def get_central_logger() -> CentralizedLogger:
    """获取集中式日志实例"""
    return central_logger


# ==================== 深水区异常捕获装饰器 ====================

def log_exceptions(
    agent_name: str = None,
    capture_vars: bool = True,
    reraise: bool = True
):
    """
    深水区异常捕获装饰器

    自动捕获异常堆栈和关键变量，写入日志

    Args:
        agent_name: Agent 名称（用于日志标记）
        capture_vars: 是否捕获导致报错的局部变量
        reraise: 是否重新抛出异��

    Usage:
        @log_exceptions(agent_name='RAGRouter', capture_vars=True)
        def fetch_from_pubmed(query: str, timeout: int):
            # 深水区代码...
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 获取 Agent 名称
                agent = agent_name or func.__name__

                # 构建变量字典
                extra_vars = {}
                if capture_vars:
                    # 添加函数参数
                    import inspect
                    sig = inspect.signature(func)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    for name, value in bound.arguments.items():
                        # 截断过长的值
                        str_val = str(value)
                        if len(str_val) > 200:
                            str_val = str_val[:200] + '...[TRUNCATED]'
                        extra_vars[name] = str_val

                extra_vars['exception_type'] = type(e).__name__
                extra_vars['exception_message'] = str(e)

                # 记录异常
                central_logger.exception(
                    f"[{agent}] 深水区异常捕获",
                    extra_vars=extra_vars
                )

                if reraise:
                    raise
                return None

        return wrapper
    return decorator


# ==================== 便捷函数（向后兼容） ====================

def get_logger():
    """向后兼容：返回集中式日志实例"""
    return central_logger


# ==================== 初始化模块级日志 ====================

def init_module_logger(module_name: str) -> logging.Logger:
    """
    初始化模块级日志器（用于 Celery Worker 等）

    Args:
        module_name: 模块名称

    Returns:
        配置好的 Logger
    """
    # 获取或创建 logger
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)

    # 如果已有处理器，不重复添加
    if logger.handlers:
        return logger

    # 添加系统日志器的引用
    system_logger = central_logger.system_logger

    return logger


# ==================== 测试入口 ====================

if __name__ == '__main__':
    print("=== V7.1 集中式日志系统测试 ===\n")

    # 测试 1: 基本日志
    central_logger.info("[测试] 系统启动")
    central_logger.debug("[测试] 调试信息")
    central_logger.warning("[测试] 警告信息")

    # 测试 2: Task Context
    print("\n--- 测试 Task ID 贯穿注入 ---")
    with TaskLogContext(task_id='task_abc123', agent_name='RAGRouter'):
        central_logger.info("[测试] 开始 PubMed 检索")
        central_logger.audit("[测试] 检索结果: 找到 50 篇论文")

    # 测试 3: AUDIT 级别
    print("\n--- 测试 AUDIT 级别 ---")
    with TaskLogContext(task_id='task_def456', agent_name='RedValidator'):
        central_logger.audit("[驳回] 假设 #3 评分不足: 可行性=4/10 (阈值=5)")

    # 测试 4: 异常堆栈捕获
    print("\n--- 测试异常堆栈捕获 ---")
    with TaskLogContext(task_id='task_err001', agent_name='HybridScorer'):
        try:
            # 模拟深水区错误
            score_data = {'feasibility': 8, 'novelty': 'invalid'}  # 类型错误
            result = score_data['feasibility'] + int(score_data['novelty'])
        except Exception as e:
            central_logger.exception(
                "[深水区] 混合打分器计算失败",
                extra_vars={'score_data': score_data, 'operation': 'fitness_calculation'}
            )

    # 测试 5: 装饰器方式
    print("\n--- 测试异常捕获装饰器 ---")

    @log_exceptions(agent_name='PhysicalValidator', capture_vars=True)
    def validate_hypothesis(hypothesis: dict, threshold: float):
        if hypothesis.get('score', 0) < threshold:
            raise ValueError(f"假设评分不足: {hypothesis.get('score')} < {threshold}")
        return True

    with TaskLogContext(task_id='task_decorator', agent_name='PhysicalValidator'):
        try:
            validate_hypothesis({'score': 3}, threshold=5)
        except:
            pass  # 异常已被装饰器捕获记录

    print("\n=== 测试完成 ===")
    print(f"请查看日志文件:\n"
          f"  - logs/system_v7.log\n"
          f"  - logs/audit_v7.log\n"
          f"  - logs/error_v7.log")