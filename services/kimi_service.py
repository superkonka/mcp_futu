"""
Kimi 模型 API 服务（月之暗面官方接口）
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from models.kimi_models import (
    KimiChatRequest,
    KimiChatResponse,
    KimiChatMessage,
    KimiChatChoice,
    KimiChatUsage,
)
from config import settings


class KimiService:
    """Kimi 模型服务，仅使用月之暗面官方 API"""

    def __init__(self):
        self.api_key = settings.kimi_moonshot_key
        self.base_url = "https://api.moonshot.cn/v1/chat/completions" if self.api_key else None
        self.timeout = 60

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _require_api_key(self):
        if not self.api_key:
            raise Exception("Kimi API 密钥未配置。请在 .env 中设置 KIMI_MOONSHOT_KEY。")

    async def chat_completion(self, request: KimiChatRequest) -> KimiChatResponse:
        """
        调用Kimi模型进行对话
        
        Args:
            request: 对话请求参数
            
        Returns:
            KimiChatResponse: 对话响应
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        start_time = datetime.now()

        try:
            logger.info(f"开始Kimi对话请求，消息数量: {len(request.messages)}")
            self._require_api_key()

            return await self._chat_moonshot(request)

        except asyncio.TimeoutError:
            logger.error("Kimi API请求超时")
            raise Exception("Kimi API请求超时，请稍后重试")
        except aiohttp.ClientError as e:
            logger.error(f"Kimi API网络错误: {e}")
            raise Exception(f"Kimi API网络错误: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Kimi API响应解析错误: {e}")
            raise Exception(f"Kimi API响应格式错误: {str(e)}")
        except Exception as e:
            logger.error(f"Kimi API调用失败: {e}")
            raise Exception(f"Kimi API调用失败: {str(e)}")

        finally:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Kimi对话请求完成，耗时: {execution_time:.3f}s")

    async def _chat_moonshot(self, request: KimiChatRequest) -> KimiChatResponse:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": request.model or "moonshot-v1-8k",
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "stream": request.stream,
            "temperature": request.temperature if request.temperature is not None else 0.3,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        logger.debug(f"Kimi Moonshot API请求: {json.dumps(payload, ensure_ascii=False)}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(self.base_url, headers=headers, json=payload) as response:
                response_text = await response.text()
                logger.debug(f"Kimi Moonshot 响应状态: {response.status}")
                logger.debug(f"Kimi Moonshot 响应内容: {response_text}")

                if response.status == 200:
                    response_data = json.loads(response_text)
                    return self._parse_moonshot_response(response_data, request)

                error_msg = f"Kimi Moonshot API返回错误 {response.status}: {response_text}"
                try:
                    error_data = json.loads(response_text)
                    if "error" in error_data:
                        error_msg = f"Kimi Moonshot 错误 [{error_data['error'].get('type', 'Unknown')}]: {error_data['error'].get('message', response_text)}"
                except Exception:
                    pass
                raise Exception(error_msg)

    def _parse_moonshot_response(self, response_data: Dict[str, Any], request: KimiChatRequest) -> KimiChatResponse:
        return KimiChatResponse(
            id=response_data.get("id", ""),
            object=response_data.get("object", "chat.completion"),
            created=response_data.get("created", int(datetime.now().timestamp())),
            model=response_data.get("model", request.model),
            choices=[
                KimiChatChoice(
                    index=idx,
                    message=KimiChatMessage(
                        role=choice.get("message", {}).get("role", "assistant"),
                        content=choice.get("message", {}).get("content", ""),
                    ),
                    finish_reason=choice.get("finish_reason"),
                )
                for idx, choice in enumerate(response_data.get("choices", []))
            ],
            usage=KimiChatUsage(
                prompt_tokens=response_data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=response_data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=response_data.get("usage", {}).get("total_tokens", 0),
            ),
        )


# 全局服务实例
kimi_service = KimiService()
