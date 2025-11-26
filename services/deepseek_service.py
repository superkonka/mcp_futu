import aiohttp
import asyncio
import json
from typing import Any, Dict, Optional
from loguru import logger


class DeepSeekService:
    """负责与DeepSeek模型交互的服务"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1/chat/completions",
        model: str = "deepseek-reasoner",
        fundamental_model: str = "deepseek-chat",
        max_tokens: int = 2048,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model or "deepseek-reasoner"
        self.fundamental_model = fundamental_model or "deepseek-chat"
        self.timeout = aiohttp.ClientTimeout(total=60)
        self.max_retries = 2
        self.max_tokens = max_tokens
        self.last_error_message: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def analyze_fundamental_news(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        system_prompt = (
            "You are DeepSeek-Fin, a professional sell-side fundamental analyst. "
            "Always reason about whether new information is priced in, how strong the signal is, "
            "and return strictly valid JSON."
        )
        user_prompt = (
            "请基于以下新闻，输出一份结构化JSON，字段如下：\n"
            "{\n"
            '  "sentiment": "利好/利空/中性",\n'
            '  "confidence": 0-1 数值,\n'
            '  "impact_horizon": "短期/中期/长期",\n'
            '  "volatility_bias": "上行/下行/中性",\n'
            '  "themes": ["主题1", ...],\n'
            '  "risk_factors": ["风险1", ...],\n'
            '  "opportunity_factors": ["机会1", ...],\n'
            '  "summary": "≤120字摘要",\n'
            '  "action_hint": "≤80字建议，若无新增建议则留空",\n'
            '  "event_type": "政策/财报/并购/交易等",\n'
            '  "effectiveness": "fresh/diminished/stale",\n'
            '  "impact_score": 0-100,\n'
            '  "novelty_score": 0-100,\n'
            '  "magnitude_score": 0-100,\n'
            '  "duration_days": 预计影响天数(可浮点),\n'
            '  "trigger_conditions": ["触发条件1", ...],\n'
            '  "market_sensitivity": "高/中/低",\n'
            '  "historical_response": {"avg_return": 数值, "avg_duration_days": 数值},\n'
            '  "related": true/false,  // 请判断该新闻是否与目标股票直接相关，只有提及目标公司的业务、股价、公告等才算相关\n'
            '  "related_reason": "若判定不相关，请说明原因"\n'
            "}\n"
            "impact_score综合考虑novelty与magnitude，effectiveness用于说明是否已被市场消化。"
            f"目标股票代码: {payload.get('code', '')}。\n请仅输出JSON。\n新闻内容: {json.dumps(payload, ensure_ascii=False)}"
        )

        content = await self.chat(
            system_prompt,
            user_prompt,
            temperature=0.2,
            model=self.fundamental_model,
            response_format={"type": "json_object"},
        )
        if not content:
            return None
        normalized = content.strip()
        if normalized.startswith("```"):
            parts = normalized.split("```")
            if len(parts) >= 3:
                normalized = parts[1]
            else:
                normalized = normalized.strip("`")
        normalized = normalized.strip()
        if normalized.lower().startswith("json"):
            normalized = normalized[4:].lstrip()
        try:
            analysis = json.loads(normalized)
            return analysis
        except json.JSONDecodeError:
            logger.warning(f"DeepSeek返回非JSON: {normalized}")
            return None

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        model: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.api_key:
            return None

        effective_model = model or self.model
        body = {
            "model": effective_model,
            "stream": False,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        if response_format:
            body["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < self.max_retries:
            attempt += 1
            try:
                logger.debug(
                    f"[DeepSeek] 请求: url={self.base_url}, model={effective_model}, temperature={temperature}, attempt={attempt}"
                )
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(self.base_url, headers=headers, json=body) as resp:
                        text = await resp.text()
                        if resp.status != 200:
                            logger.warning(f"DeepSeek API error {resp.status}: {text}")
                            last_error = RuntimeError(f"HTTP {resp.status}: {text[:200]}")
                            self.last_error_message = str(last_error)
                        else:
                            data = json.loads(text)
                            self.last_error_message = None
                            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            except asyncio.TimeoutError as exc:
                last_error = exc
                self.last_error_message = "请求超时"
                logger.warning(
                    f"DeepSeek 调用超时 attempt={attempt}/{self.max_retries} model={effective_model}"
                )
            except Exception as exc:
                last_error = exc
                self.last_error_message = str(exc)
                logger.warning(
                    f"DeepSeek 调用异常 attempt={attempt}/{self.max_retries}: {exc}"
                )
            if attempt < self.max_retries:
                await asyncio.sleep(0.8 * attempt)

        logger.error(f"调用DeepSeek失败: {last_error}")
        if self.last_error_message is None and last_error is not None:
            self.last_error_message = str(last_error)
        return None
