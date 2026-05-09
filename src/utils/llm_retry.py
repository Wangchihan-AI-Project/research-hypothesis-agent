# -*- coding: utf-8 -*-
"""
LLM API 调用重试工具 — 处理 cloud.hongqiye.com 代理 500 错误

提供带指数退避的 Anthropic client 工厂函数。
500 错误自动重试 3 次（2s → 4s → 8s），重试过程写入日志。
"""

import time
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 重试配置
MAX_RETRIES = 3
BASE_DELAY = 2.0  # 首次重试等待秒数


def create_anthropic_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    """
    创建带自动重试的 Anthropic client。

    Args:
        api_key: Anthropic API key（默认读环境变量 ANTHROPIC_API_KEY）
        base_url: API 代理地址（默认读环境变量 ANTHROPIC_BASE_URL）

    Returns:
        anthropic.Anthropic: 带重试 transport 的 client 实例

    Retry 策略：
        - 仅对 5xx 错误和连接错误重试
        - 最多 3 次，指数退避: 2s → 4s → 8s
        - 4xx 错误（如 401/429）不重试
    """
    import httpx
    import anthropic

    transport = _RetryHTTPTransport()

    http_client = httpx.Client(
        transport=transport,
        timeout=httpx.Timeout(120.0, connect=30.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )

    kwargs = {}
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    kwargs["api_key"] = api_key

    if base_url is None:
        base_url = os.getenv("ANTHROPIC_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url

    kwargs["http_client"] = http_client

    # ⚠️ 禁止 SDK 发送遥测数据（减少不必要的网络请求）
    kwargs["default_headers"] = {"anthropic-beta": "disable-telemetry-events"}

    return anthropic.Anthropic(**kwargs)


class _RetryHTTPTransport:
    """
    包装 httpx.HTTPTransport，自动重试 5xx 错误和连接错误。

    注意：此为最小实现，仅覆盖标准的同步 HTTP 请求路径。
    """

    def __init__(self):
        # 延迟创建 transport，避免导入时初始化问题
        self._inner = None

    def _get_transport(self):
        if self._inner is None:
            import httpx
            self._inner = httpx.HTTPTransport()
        return self._inner

    def handle_request(self, request):
        """
        处理 HTTP 请求，5xx/连接错误时自动重试。

        Args:
            request: httpx.Request 对象

        Returns:
            httpx.Response

        Raises:
            httpx.HTTPStatusError: 非 5xx 错误或在重试耗尽后仍失败
        """
        import httpx

        last_exception = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                transport = self._get_transport()
                response = transport.handle_request(request)

                status = response.status_code

                # 2xx/3xx → 成功
                if status < 400:
                    if attempt > 0:
                        logger.info(f"[LLM Retry] 第 {attempt} 次重试成功 (HTTP {status})")
                    return response

                # 4xx → 客户端错误，不重试
                if 400 <= status < 500:
                    if status == 429 and attempt < MAX_RETRIES:
                        # 429 Too Many Requests → 特殊处理，等待后重试
                        delay = BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            f"[LLM Retry] HTTP 429 速率限制，{delay:.0f}s 后重试 (第 {attempt + 1}/{MAX_RETRIES} 次)"
                        )
                        time.sleep(delay)
                        continue
                    response.read()
                    raise httpx.HTTPStatusError(
                        f"HTTP {status}",
                        request=request,
                        response=response,
                    )

                # 5xx → 服务端错误，重试
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"[LLM Retry] HTTP {status} 服务端错误，{delay:.0f}s 后重试 (第 {attempt + 1}/{MAX_RETRIES} 次)"
                    )
                    response.read()  # 消费响应体
                    time.sleep(delay)
                    continue
                else:
                    response.read()
                    raise httpx.HTTPStatusError(
                        f"HTTP {status} (重试 {MAX_RETRIES} 次后仍失败)",
                        request=request,
                        response=response,
                    )

            except httpx.ConnectError as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"[LLM Retry] 连接错误: {e}，{delay:.0f}s 后重试 (第 {attempt + 1}/{MAX_RETRIES} 次)"
                    )
                    time.sleep(delay)
                    continue
                raise

            except httpx.ReadError as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"[LLM Retry] 读取错误: {e}，{delay:.0f}s 后重试 (第 {attempt + 1}/{MAX_RETRIES} 次)"
                    )
                    time.sleep(delay)
                    continue
                raise

        # 理论上不会到达这里
        if last_exception:
            raise last_exception
        raise RuntimeError("LLM retry: 未知错误")


__all__ = ["create_anthropic_client", "MAX_RETRIES", "BASE_DELAY"]
