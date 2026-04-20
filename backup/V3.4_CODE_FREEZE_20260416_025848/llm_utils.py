# -*- coding: utf-8 -*-
"""
全局 LLM 解析工具类 (Global LLM Utils) - V3.2 增强版

提供防弹的 JSON/Markdown 解析、重试机制和错误处理
所有 Agent 都应该使用这些工具来确保稳定性

V3.2 新增功能：
1. TypeSafeCast - 类型安全转换器（防止 LLM 参数类型幻觉）
2. retry_with_exponential_backoff - 指数退避重试装饰器（防止 API 限流雪崩）
3. TokenHardCapManager - 全局 Token 硬上限管理器（防止幽灵 Token 消耗）
"""
import re
import json
import time
import random
import threading
from typing import Dict, List, Optional, Any, Union, Callable, TypeVar
from datetime import datetime


# ==============================================================================
# 类型安全转换器 (TypeSafeCast) - 防止 LLM 参数类型幻觉
# ==============================================================================

class TypeSafeCast:
    """
    类型安全转换器

    防止 LLM 传错参数类型导致代码崩溃。
    处理常见幻觉：
    - "A, B, C" → ["A", "B", "C"]
    - "123" → 123
    - "true" → True
    """

    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        """安全转换为整数"""
        try:
            if isinstance(value, (list, tuple)) and len(value) > 0:
                value = value[0]
            if isinstance(value, str):
                match = re.search(r'-?\d+', value)
                if match:
                    return int(match.group())
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def to_float(value: Any, default: float = 0.0) -> float:
        """安全转换为浮点数"""
        try:
            if isinstance(value, (list, tuple)) and len(value) > 0:
                value = value[0]
            if isinstance(value, str):
                match = re.search(r'-?\d+\.?\d*', value)
                if match:
                    return float(match.group())
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def to_str(value: Any, default: str = "") -> str:
        """安全转换为字符串"""
        try:
            if isinstance(value, (list, tuple)):
                return ", ".join(str(v) for v in value)
            return str(value)
        except Exception:
            return default

    @staticmethod
    def to_list(value: Any, default: list = None) -> list:
        """
        安全转换为列表

        处理常见幻觉：
        - "A, B, C" → ["A", "B", "C"]
        - "[A, B, C]" → ["A", "B", "C"]
        - "A" → ["A"]
        """
        if default is None:
            default = []

        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            value = value.strip()
            if value.startswith('[') and value.endswith(']'):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            if ',' in value:
                return [v.strip() for v in value.split(',') if v.strip()]
            return [value] if value else default
        return default

    @staticmethod
    def to_bool(value: Any, default: bool = False) -> bool:
        """安全转换为布尔值"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on', 'enabled')
        if isinstance(value, (int, float)):
            return bool(value)
        return default


# ==============================================================================
# 指数退避重试器 (Exponential Backoff) - 防止 API 限流雪崩
# ==============================================================================

def retry_with_exponential_backoff(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> Callable:
    """
    指数退避重试装饰器

    防止 API 限流雪崩 (429 Too Many Requests)

    用法:
        @retry_with_exponential_backoff()
        def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 检查是否为限流错误
                    is_rate_limit = (
                        '429' in str(e) or
                        'rate limit' in str(e).lower() or
                        'too many requests' in str(e).lower()
                    )

                    if not is_rate_limit:
                        if attempt == max_attempts - 1:
                            raise
                        time.sleep(base_delay)
                        continue

                    # 计算退避延迟
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # 添加随机抖动（避免雷击群效应）
                    if jitter:
                        jitter_amount = delay * 0.1
                        delay += random.uniform(-jitter_amount, jitter_amount)

                    print(f"[Retry] 指数退避: {delay:.1f}s 后进行第 {attempt + 2}/{max_attempts} 次尝试")
                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


# ==============================================================================
# 全局 Token 硬上限管理器 - 防止幽灵 Token 消耗
# ==============================================================================

class TokenHardCapManager:
    """
    全局 Token 硬上限管理器

    防止 Fail-Fast 循环或重试机制消耗过多 Token
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.max_total_tokens: int = 100000  # 默认硬上限：10 万 tokens
        self.max_total_calls: int = 50  # 默认最大 API 调用次数
        self.current_tokens: int = 0
        self.current_calls: int = 0
        self.session_start_time: float = time.time()

    def configure(self, max_tokens: int = None, max_calls: int = None):
        """配置硬上限"""
        if max_tokens is not None:
            self.max_total_tokens = max_tokens
        if max_calls is not None:
            self.max_total_calls = max_calls

    def record_call(self, tokens_used: int = 0) -> bool:
        """
        记录一次 API 调用

        Returns:
            bool: 是否允许继续（True=继续，False=已达上限）
        """
        self.current_tokens += tokens_used
        self.current_calls += 1

        if self.current_calls >= self.max_total_calls:
            print(f"[Token Hard Cap] ⛔ 已达最大调用次数: {self.current_calls}/{self.max_total_calls}")
            return False

        if self.current_tokens >= self.max_total_tokens:
            print(f"[Token Hard Cap] ⛔ 已达最大 Token 消耗: {self.current_tokens:,}/{self.max_total_tokens:,}")
            return False

        return True

    def can_continue(self) -> bool:
        """检查是否可以继续"""
        return (
            self.current_calls < self.max_total_calls and
            self.current_tokens < self.max_total_tokens
        )

    def should_terminate_generation(self) -> tuple[bool, str]:
        """
        判断是否应该强制终止生成

        Returns:
            (should_terminate, reason)
        """
        if self.current_calls >= self.max_total_calls:
            return True, f"已达最大 API 调用次数 ({self.current_calls}/{self.max_total_calls})"

        if self.current_tokens >= self.max_total_tokens:
            return True, f"已达最大 Token 消耗 ({self.current_tokens:,}/{self.max_total_tokens:,})"

        # 预警阈值：80%
        if self.current_tokens >= self.max_total_tokens * 0.8:
            return False, f"警告: Token 消耗已达 80% ({self.current_tokens:,}/{self.max_total_tokens:,})"

        return False, ""

    def get_remaining_allowance(self) -> Dict[str, int]:
        """获取剩余配额"""
        return {
            'remaining_tokens': max(0, self.max_total_tokens - self.current_tokens),
            'remaining_calls': max(0, self.max_total_calls - self.current_calls),
            'elapsed_seconds': int(time.time() - self.session_start_time)
        }

    def reset(self):
        """重置计数器（用于新会话）"""
        self.current_tokens = 0
        self.current_calls = 0
        self.session_start_time = time.time()


# 全局单例
token_hard_cap = TokenHardCapManager()


# ==============================================================================
# 原有功能（保持向后兼容）
# ==============================================================================

from functools import wraps


class LLMParseError(Exception):
    """LLM 解析失败异常"""
    pass


class SafeExtractor:
    """
    安全提取器 - 防弹的 LLM 响应解析

    支持从混乱的 LLM 输出中提取干净的 JSON、Markdown 内容
    """

    @staticmethod
    def safe_extract_json(response_text: str) -> Dict:
        """
        安全提取 JSON 内容

        能够处理以下情况：
        - ```json ... ``` 代码块
        - ``` ... ``` 代码块
        - 前言后语混在一起
        - 多个 JSON 对象
        - 格式错误的 JSON（尝试修复）
        - LaTeX 中的反斜杠（如 $X \cdot Y$）

        Args:
            response_text: LLM 响应文本

        Returns:
            解析后的字典

        Raises:
            LLMParseError: 无法提取有效 JSON
        """
        if not response_text or not isinstance(response_text, str):
            raise LLMParseError("响应文本为空或不是字符串")

        response_text = response_text.strip()

        # 策略1: 提取所有 ```json 代码块，优先返回 dict 格式
        # 使用通用正则匹配所有代码块内容
        block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        block_matches = re.findall(block_pattern, response_text)

        if block_matches:
            # 优先尝试解析为 dict
            for match in block_matches:
                match = match.strip()
                if match.startswith('{'):
                    # 清理 LaTeX 中的无效反斜杠
                    cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', match)
                    try:
                        result = json.loads(cleaned)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        continue

            # 如果没有 dict，尝试解析为 array
            for match in block_matches:
                match = match.strip()
                if match.startswith('['):
                    cleaned = re.sub(r'\\(?![nrtbf\"\\/])', '', match)
                    try:
                        result = json.loads(cleaned)
                        if isinstance(result, list):
                            return result
                    except json.JSONDecodeError:
                        continue

        # 策略2: 查找完整的 JSON 对象或数组，优先返回 dict
        # 首先尝试匹配完整对象（以 { 开头，以 } 结尾）- 优先
        obj_start = response_text.find('{')
        obj_end = response_text.rfind('}')
        if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
            obj_text = response_text[obj_start:obj_end+1]
            try:
                parsed = json.loads(obj_text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # 然后尝试匹配完整数组（以 [ 开头，以 ] 结尾）
        array_start = response_text.find('[')
        array_end = response_text.rfind(']')
        if array_start != -1 and array_end != -1 and array_end > array_start:
            array_text = response_text[array_start:array_end+1]
            try:
                parsed = json.loads(array_text)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        # 策略4: 尝试修复常见的 JSON 错误
        try:
            return SafeExtractor._fix_and_parse_json(response_text)
        except Exception:
            pass

        # 策略5: 尝试直接解析整个文本
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        raise LLMParseError(f"无法从响应中提取有效 JSON。响应长度: {len(response_text)}")

    @staticmethod
    def _fix_and_parse_json(text: str) -> Dict:
        """
        尝试修复常见的 JSON 错误并解析

        常见错误：
        - 尾随逗号
        - 单引号代替双引号
        - 注释
        - 未转义的换行符
        """
        # 移除注释
        text = re.sub(r'//.*?\n', '\n', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

        # 单引号转双引号（小心处理字符串内的单引号）
        text = re.sub(r"'([^']*)'", r'"\1"', text)

        # 移除尾随逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)

        # 尝试解析
        return json.loads(text)

    @staticmethod
    def safe_extract_markdown(response_text: str, min_length: int = 100) -> str:
        """
        安全提取 Markdown 内容

        能够处理：
        - ```markdown ... ``` 代码块
        - LLM 的前言后语
        - 多个代码块

        Args:
            response_text: LLM 响应文本
            min_length: 最小内容长度

        Returns:
            提取的 Markdown 内容

        Raises:
            LLMParseError: 无法提取有效内容
        """
        if not response_text or not isinstance(response_text, str):
            raise LLMParseError("响应文本为空或不是字符串")

        response_text = response_text.strip()

        # 策略1: 提取 ```markdown 代码块
        md_pattern = r'```(?:markdown)?\s*([\s\S]*?)\s*```'
        matches = re.findall(md_pattern, response_text, re.IGNORECASE)
        if matches:
            # 取最长的匹配
            longest = max(matches, key=len)
            if len(longest) >= min_length:
                return longest.strip()

        # 策略2: 查找以 # 开头的内容
        heading_pattern = r'^(#{1,6}\s+.+?)(?=#{1,6}\s+|\Z)'
        matches = re.findall(heading_pattern, response_text, re.MULTILINE | re.DOTALL)
        if matches:
            combined = '\n\n'.join(matches)
            if len(combined) >= min_length:
                return combined.strip()

        # 策略3: 直接返回整个文本
        if len(response_text) >= min_length:
            return response_text

        raise LLMParseError(f"提取的 Markdown 内容过短: {len(response_text)} < {min_length}")

    @staticmethod
    def safe_extract_code_block(response_text: str, language: str = "") -> str:
        """
        安全提取代码块内容

        Args:
            response_text: LLM 响应文本
            language: 代码语言（如 python, json）

        Returns:
            提取的代码内容

        Raises:
            LLMParseError: 无法提取代码块
        """
        if not response_text:
            raise LLMParseError("响应文本为空")

        # 构建模式
        if language:
            pattern = rf'```{language}\s*([\s\S]*?)\s*```'
        else:
            pattern = r'```\s*([\s\S]*?)\s*```'

        matches = re.findall(pattern, response_text)
        if matches:
            return matches[0].strip()

        raise LLMParseError(f"无法找到代码块 (语言: {language or '任意'})")

    @staticmethod
    def extract_list_items(response_text: str, item_pattern: str = r'[-*]\s*(.+)') -> List[str]:
        """
        从响应中提取列表项

        Args:
            response_text: LLM 响应文本
            item_pattern: 列表项的正则模式

        Returns:
            提取的列表项
        """
        matches = re.findall(item_pattern, response_text)
        return [m.strip() for m in matches if m.strip()]


class RetryExecutor:
    """
    重试执行器 - 带 LLM 友好的错误反馈

    当重试时，会将错误信息追加到 Prompt 中
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay

    def execute_with_retry(
        self,
        func,
        prompt: str,
        error_context: str = "",
        *args,
        **kwargs
    ) -> Any:
        """
        带重试的执行

        Args:
            func: 要执行的函数（接收 prompt 作为第一个参数）
            prompt: 提示词
            error_context: 错误上下文（用于调试）
            *args, **kwargs: 传递给 func 的其他参数

        Returns:
            func 的返回值

        Raises:
            Exception: 重试次数用尽后仍失败
        """
        last_error = None
        original_prompt = prompt

        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    # 添加重试提示
                    prompt = self._add_retry_prompt(
                        original_prompt,
                        last_error,
                        attempt + 1,
                        self.max_retries
                    )

                result = func(prompt, *args, **kwargs)

                # 验证结果
                if self._is_valid_result(result):
                    return result
                else:
                    raise LLMParseError("返回结果验证失败（可能为空或格式错误）")

            except (LLMParseError, json.JSONDecodeError, ValueError) as e:
                last_error = e
                print(f"[RetryExecutor] 第 {attempt + 1}/{self.max_retries} 次尝试失败: {e}")

                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (attempt + 1)
                    print(f"[RetryExecutor] {delay}秒后重试...")
                    time.sleep(delay)
                else:
                    raise Exception(
                        f"[{error_context}] 经过 {self.max_retries} 次尝试后仍失败: "
                        f"最后错误: {last_error}"
                    ) from last_error

            except Exception as e:
                # 非 LLM 解析错误直接抛出
                raise Exception(f"[{error_context}] 执行异常: {e}") from e

        raise Exception(f"[{error_context}] 未知错误（重试次数用尽）")

    def _add_retry_prompt(self, original_prompt: str, error: Exception,
                          attempt: int, max_retries: int) -> str:
        """添加重试提示"""
        error_msg = str(error)

        retry_instruction = f"""


---

【重要】你之前的输出有误，请修正：

**错误信息**: {error_msg}

**这是第 {attempt}/{max_retries} 次尝试**

请确保：
1. 输出格式完全符合要求（JSON/Markdown）
2. 内容长度充足（不要简短带过）
3. 不要使用占位符如"XX"或"待定"
4. 如果是 JSON，确保可以被 json.loads() 解析

请重新生成完整、正确的输出：
"""

        return original_prompt + retry_instruction

    def _is_valid_result(self, result: Any) -> bool:
        """验证结果是否有效"""
        if result is None:
            return False

        if isinstance(result, dict):
            # 空字典无效
            if not result:
                return False
            # 检查是否全是空值
            if all(not v for v in result.values()):
                return False
            return True

        if isinstance(result, str):
            # 字符串需要有实际内容
            return len(result.strip()) >= 50

        if isinstance(result, list):
            return len(result) > 0

        return True


def safe_extract_json(response_text: str) -> Dict:
    """便捷函数：安全提取 JSON"""
    return SafeExtractor.safe_extract_json(response_text)


def safe_extract_markdown(response_text: str, min_length: int = 100) -> str:
    """便捷函数：安全提取 Markdown"""
    return SafeExtractor.safe_extract_markdown(response_text, min_length)


def safe_extract_code_block(response_text: str, language: str = "") -> str:
    """便捷函数：安全提取代码块"""
    return SafeExtractor.safe_extract_code_block(response_text, language)


# 测试代码
if __name__ == "__main__":
    # 测试 safe_extract_json
    test_cases = [
        '```json\n{"key": "value"}\n```',
        'Here is the result:\n{"key": "value"}\nThat\'s it!',
        '{"key": "value"}',
        '```json\n{"key": "value",}\n```',  # 尾随逗号
    ]

    for i, test in enumerate(test_cases):
        print(f"测试用例 {i + 1}:")
        try:
            result = safe_extract_json(test)
            print(f"  成功: {result}")
        except LLMParseError as e:
            print(f"  失败: {e}")
        print()
