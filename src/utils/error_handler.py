"""
全局异常处理和错误恢复
"""
from functools import wraps
from typing import Callable, Any
from utils.logger import get_logger


def handle_errors(operation_name: str = None):
    """
    错误处理装饰器

    Args:
        operation_name: 操作名称

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                op_name = operation_name or func.__name__
                logger.error(f"{op_name}失败", e)

                # 返回标准错误响应
                return {
                    'success': False,
                    'error': f'{op_name}失败: {str(e)}',
                    'operation': op_name
                }

        return wrapper
    return decorator


class ResearchSystemError(Exception):
    """研究系统基础异常"""
    pass


class DatabaseError(ResearchSystemError):
    """数据库错误"""
    pass


class APIError(ResearchSystemError):
    """API调用错误"""
    pass


class ValidationError(ResearchSystemError):
    """验证错误"""
    pass


class ConfigError(ResearchSystemError):
    """配置错误"""
    pass


class ErrorRecovery:
    """错误恢复工具"""

    @staticmethod
    def retry_on_failure(func: Callable, max_retries: int = 3, delay: float = 1.0) -> Any:
        """
        失败重试机制

        Args:
            func: 要执行的函数
            max_retries: 最大重试次数
            delay: 重试延迟（秒）

        Returns:
            函数结果
        """
        import time
        logger = get_logger()

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"操作失败，{delay}秒后重试 "
                        f"(尝试 {attempt + 1}/{max_retries}): {str(e)}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"操作失败，已达最大重试次数 {max_retries}", e)
                    raise

    @staticmethod
    def fallback_to_default(primary_func: Callable, fallback_func: Callable) -> Any:
        """
        主函数失败时回退到备用函数

        Args:
            primary_func: 主函数
            fallback_func: 备用函数

        Returns:
            函数结果
        """
        logger = get_logger()

        try:
            return primary_func()
        except Exception as e:
            logger.warning(f"主函数失败，切换到备用方案: {str(e)}")
            logger.error_recovery(type(e).__name__, "使用备用函数")
            return fallback_func()


if __name__ == '__main__':
    # 测试错误处理
    logger = get_logger()

    @handle_errors("测试操作")
    def test_function(should_fail: bool = False):
        if should_fail:
            raise ValueError("这是一个测试错误")
        return {'success': True, 'data': '测试成功'}

    # 测试正常情况
    result1 = test_function(should_fail=False)
    print(f"正常结果: {result1}")

    # 测试错误情况
    result2 = test_function(should_fail=True)
    print(f"错误结果: {result2}")

    # 测试重试机制
    attempt_count = 0

    def flaky_function():
        global attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("暂时失败")
        return "成功"

    result3 = ErrorRecovery.retry_on_failure(flaky_function, max_retries=3)
    print(f"重试结果: {result3}")

    print("\n错误处理测试完成")