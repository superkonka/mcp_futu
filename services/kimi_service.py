"""
火山引擎Kimi模型API服务
封装火山引擎ark API调用来实现智能对话功能
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from models.kimi_models import KimiChatRequest, KimiChatResponse, KimiChatMessage, KimiChatChoice, KimiChatUsage
from config import settings


class KimiService:
    """火山引擎Kimi模型服务"""
    
    def __init__(self):
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        self.api_key = settings.kimi_api_key  # 从本地环境读取
        self.timeout = 30
    
    def _require_api_key(self):
        if not self.api_key:
            raise Exception("Kimi API 密钥未配置。请在本地 .env 设置 KIMI_API_KEY。")
        
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
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 构建请求体
            payload = {
                "model": request.model,
                "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
                "stream": request.stream
            }
            
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            if request.max_tokens is not None:
                payload["max_tokens"] = request.max_tokens
            
            logger.debug(f"Kimi API请求: {json.dumps(payload, ensure_ascii=False)}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    
                    logger.debug(f"Kimi API响应状态: {response.status}")
                    logger.debug(f"Kimi API响应内容: {response_text}")
                    
                    if response.status == 200:
                        response_data = json.loads(response_text)
                        
                        # 解析响应数据
                        return KimiChatResponse(
                            id=response_data.get("id", ""),
                            object=response_data.get("object", "chat.completion"),
                            created=response_data.get("created", int(datetime.now().timestamp())),
                            model=response_data.get("model", request.model),
                            choices=[
                                KimiChatChoice(
                                    index=choice.get("index", 0),
                                    message=KimiChatMessage(
                                        role=choice["message"]["role"],
                                        content=choice["message"]["content"]
                                    ),
                                    finish_reason=choice.get("finish_reason")
                                )
                                for choice in response_data.get("choices", [])
                            ],
                            usage=KimiChatUsage(
                                prompt_tokens=response_data.get("usage", {}).get("prompt_tokens", 0),
                                completion_tokens=response_data.get("usage", {}).get("completion_tokens", 0),
                                total_tokens=response_data.get("usage", {}).get("total_tokens", 0)
                            )
                        )
                    else:
                        # 处理错误响应
                        error_msg = f"Kimi API返回错误状态码 {response.status}: {response_text}"
                        logger.error(error_msg)
                        
                        # 尝试解析错误信息
                        try:
                            error_data = json.loads(response_text)
                            if "error" in error_data:
                                error_code = error_data["error"].get("code", "Unknown")
                                error_message = error_data["error"].get("message", response_text)
                                error_msg = f"Kimi API错误 [{error_code}]: {error_message}"
                        except:
                            pass
                            
                        raise Exception(error_msg)
                        
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


# 全局服务实例
kimi_service = KimiService()