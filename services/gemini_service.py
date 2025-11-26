import asyncio
from typing import Optional, Any, Dict, List

from google import genai
from loguru import logger

from config import settings


class GeminiService:
    """Google Gemini (GenAI SDK) 封装"""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = (settings.gemini_model or "models/gemini-3-pro-preview").strip()
        self.client: Optional[genai.Client] = None
        self.base_generation_config: Dict[str, Any] = {
            "max_output_tokens": 1024,
            "response_mime_type": "text/plain",
        }
        self.max_retries = 2
        self.retry_delay = 0.6
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as exc:
                logger.error(f"Gemini Client 初始化失败: {exc}")
                self.client = None

    def is_configured(self) -> bool:
        return self.client is not None

    async def generate_text(
        self,
        prompt: str,
        temperature: float = 1.0,
        thinking_level: Optional[str] = None,
    ) -> Optional[str]:
        if not self.client:
            return None
        loop = asyncio.get_running_loop()
        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < self.max_retries:
            attempt += 1
            try:
                result = await loop.run_in_executor(
                    None, self._sync_generate, prompt, temperature, thinking_level
                )
                if result:
                    return result
                logger.warning(f"Gemini 返回空结果 attempt={attempt}/{self.max_retries}")
            except Exception as exc:
                last_error = exc
                logger.warning(f"Gemini 调用异常 attempt={attempt}/{self.max_retries}: {exc}")
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)
        if last_error:
            logger.error(f"Gemini API 调用失败: {last_error}")
        return None

    def _sync_generate(
        self,
        prompt: str,
        temperature: float,
        thinking_level: Optional[str],
    ) -> Optional[str]:
        try:
            effective_temp = max(0.0, min(temperature, 2.0))
            config_payload: Dict[str, Any] = {
                **self.base_generation_config,
                "temperature": effective_temp,
            }
            if thinking_level:
                config_payload["thinking_level"] = thinking_level
            logger.debug(f"[Gemini] 请求参数: model={self.model}, config={config_payload}")
            response = self.client.models.generate_content(
                model=self.model,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config=config_payload,
            )
            self._log_response_meta(response)
            text = self._extract_text(response)
            if text:
                return text.strip()
            logger.warning(f"[Gemini] 响应未包含文本，finish={self._summarize_candidates(response)}")
            return None
        except Exception:
            logger.exception("[Gemini] 调用失败")
            return None

    def _extract_text(self, response: Any) -> Optional[str]:
        if getattr(response, "text", None):
            return response.text
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return None
        for cand in candidates:
            content = getattr(cand, "content", None) or cand.get("content") if isinstance(cand, dict) else None
            parts = getattr(content, "parts", None)
            if parts:
                for part in parts:
                    text = getattr(part, "text", None)
                    if text:
                        return text
                    if isinstance(part, dict):
                        text = part.get("text")
                        if text:
                            return text
                        if part.get("function_call"):
                            return str(part["function_call"])
            if isinstance(cand, dict):
                for part in cand.get("content", {}).get("parts", []):
                    text = part.get("text")
                    if text:
                        return text
        return None

    def _log_response_meta(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", None) if usage else None
        summary = self._summarize_candidates(response)
        summary_text = ", ".join(summary) if summary else "[]"
        if tokens is not None:
            logger.debug(f"[Gemini] finish={summary_text} tokens={tokens}")
        else:
            logger.debug(f"[Gemini] finish={summary_text}")

    def _summarize_candidates(self, response: Any) -> List[str]:
        candidates = getattr(response, "candidates", None)
        summaries: List[str] = []
        if not candidates:
            return summaries
        for cand in candidates:
            finish = getattr(cand, "finish_reason", None) or (cand.get("finish_reason") if isinstance(cand, dict) else None)
            safety = getattr(cand, "safety_ratings", None) or (cand.get("safety_ratings") if isinstance(cand, dict) else None)
            safety_info = ""
            if safety:
                blocked = [rating.category for rating in safety if getattr(rating, "probability", "") == "HIGH"]
                if not blocked and isinstance(safety, list):
                    blocked = [rating.get("category") for rating in safety if rating.get("probability") == "HIGH"]
                if blocked:
                    safety_info = f" safety={','.join(filter(None, blocked))}"
            summaries.append(f"{finish or 'unknown'}{safety_info}")
        return summaries

gemini_service = GeminiService()
