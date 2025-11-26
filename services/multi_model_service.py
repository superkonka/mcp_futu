import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from services.deepseek_service import DeepSeekService
from services.kimi_service import kimi_service
from services.gemini_service import gemini_service


def _safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    normalized = text.strip()
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
        return json.loads(normalized)
    except Exception:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = normalized[start : end + 1]
            for payload in (candidate, candidate.replace("'", '"')):
                try:
                    return json.loads(payload)
                except Exception:
                    continue
        return None


class MultiModelAnalysisService:
    def __init__(self, deepseek: Optional[DeepSeekService]):
        self.deepseek = deepseek

    async def run_analysis(
        self,
        *,
        code: str,
        models: List[str],
        judge_model: str,
        context_text: str,
        context_snapshot: Dict[str, Any],
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        context_snapshot = dict(context_snapshot)
        context_snapshot["context_text"] = context_text
        base_tasks = []
        for model in models:
            base_tasks.append(self._run_single_model(model.lower(), context_text, code, question))
        base_results = await asyncio.gather(*base_tasks, return_exceptions=False)

        judge = await self._run_judge(
            judge_model.lower(), context_text, base_results, code, question
        )
        finished_at = datetime.now(timezone.utc).isoformat()
        return {
            "code": code,
            "snapshot": {
                "quote": context_snapshot.get("quote"),
                "signals": context_snapshot.get("signals", {}),
                "recommendations": context_snapshot.get("recommendations", []),
            },
            "context_snapshot": context_snapshot,
            "models": base_results,
            "judge": judge,
            "started_at": started_at,
            "finished_at": finished_at,
        }

    async def run_single_analysis(
        self,
        *,
        code: str,
        model: str,
        context_text: str,
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._run_single_model(model.lower(), context_text, code, question)

    async def run_judge_only(
        self,
        *,
        code: str,
        judge_model: str,
        context_text: str,
        base_results: List[Dict[str, Any]],
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._run_judge(
            judge_model.lower(), context_text, base_results, code, question
        )

    async def _run_single_model(
        self, model: str, context_text: str, code: str, question: Optional[str]
    ) -> Dict[str, Any]:
        begin = datetime.now()
        prompt = self._build_model_prompt(model, context_text, code, question)
        try:
            if model == "deepseek":
                if not self.deepseek or not self.deepseek.is_configured():
                    return {
                        "model": model,
                        "status": "disabled",
                        "error": "DeepSeek API 未配置",
                    }
                content = await self.deepseek.chat("你是一名资深港股策略分析师。", prompt, temperature=0.2)
                if not content and getattr(self.deepseek, "fundamental_model", None):
                    logger.info("multi-model deepseek 使用降级模型重试")
                    content = await self.deepseek.chat(
                        "你是一名资深港股策略分析师。",
                        prompt,
                        temperature=0.2,
                        model=self.deepseek.fundamental_model,
                    )
            elif model == "kimi":
                if not getattr(kimi_service, "provider", None):
                    return {"model": model, "status": "disabled", "error": "Kimi API 未配置"}
                from models.kimi_models import KimiChatRequest, KimiChatMessage

                default_model = (
                    "moonshot-v1-8k"
                    if getattr(kimi_service, "provider", None) == "moonshot"
                    else "kimi-k2-thinking-turbo"
                )
                request_body = KimiChatRequest(
                    model=default_model,
                    messages=[
                        KimiChatMessage(role="system", content="你是一名专业的港股量化交易顾问。"),
                        KimiChatMessage(role="user", content=prompt),
                    ],
                    stream=False,
                    temperature=0.3,
                )
                resp = await kimi_service.chat_completion(request_body)
                content = resp.choices[0].message.content if resp.choices else None
            elif model == "gemini":
                if not gemini_service.is_configured():
                    return {"model": model, "status": "disabled", "error": "Gemini API 未配置"}
                content = await gemini_service.generate_text(prompt, temperature=0.2)
            else:
                return {"model": model, "status": "error", "error": f"未知模型 {model}"}

            if not content:
                error_detail = None
                if model == "deepseek" and self.deepseek:
                    error_detail = getattr(self.deepseek, "last_error_message", None)
                return {
                    "model": model,
                    "status": "error",
                    "error": error_detail or "模型未返回结果",
                }

            parsed = _safe_json_loads(content)
            return {
                "model": model,
                "status": "success",
                "result": parsed or {"raw": content},
                "raw_text": content,
                "duration": (datetime.now() - begin).total_seconds(),
            }
        except Exception as exc:
            logger.exception(f"multi-model {model} 调用失败: {exc}")
            return {"model": model, "status": "error", "error": str(exc)}

    async def _run_judge(
        self,
        model: str,
        context_text: str,
        base_results: List[Dict[str, Any]],
        code: str,
        question: Optional[str],
    ) -> Dict[str, Any]:
        prompt = self._build_judge_prompt(model, context_text, base_results, code, question)
        try:
            if model == "gemini" and gemini_service.is_configured():
                content = await gemini_service.generate_text(prompt, temperature=0.2)
            elif model == "deepseek" and self.deepseek and self.deepseek.is_configured():
                content = await self.deepseek.chat("你是量化策略评审专家。", prompt, temperature=0.2)
            elif model == "kimi" and getattr(kimi_service, "provider", None):
                from models.kimi_models import KimiChatRequest, KimiChatMessage

                default_model = (
                    "moonshot-v1-8k"
                    if getattr(kimi_service, "provider", None) == "moonshot"
                    else "kimi-k2-thinking-turbo"
                )
                request_body = KimiChatRequest(
                    model=default_model,
                    messages=[
                        KimiChatMessage(role="system", content="你是一名策略评审官，需整合多模型意见输出唯一执行方案。"),
                        KimiChatMessage(role="user", content=prompt),
                    ],
                    stream=False,
                    temperature=0.2,
                )
                resp = await kimi_service.chat_completion(request_body)
                content = resp.choices[0].message.content if resp.choices else None
            else:
                return {"model": model, "status": "disabled", "error": "评审模型未配置"}

            if not content:
                return {"model": model, "status": "error", "error": "评审模型无响应"}

            parsed = _safe_json_loads(content)
            return {
                "model": model,
                "status": "success",
                "result": parsed or {"raw": content},
                "raw_text": content,
            }
        except Exception as exc:
            logger.exception(f"judge {model} 调用失败: {exc}")
            return {"model": model, "status": "error", "error": str(exc)}

    def _build_model_prompt(self, model: str, context_text: str, code: str, question: Optional[str]) -> str:
        extra = f"\n额外请求：{question}" if question else ""
        return (
            f"你是一名资深港股策略顾问。请基于以下关于 {code} 的上下文，独立输出一个 JSON 格式的策略。"
            "如果信息不足或关键条件缺失，应将 action 设为 \"WATCH\" 并写明原因。"
            "请严格使用如下结构：\n"
            "{\n"
            '  "action": "BUY/SELL/HOLD/ADD/REDUCE/WATCH",\n'
            '  "timeframe": "intraday/short_term/mid_term/long_term",\n'
            '  "confidence": 0-1 的小数,\n'
            '  "rationale": "核心结论，引用关键证据",\n'
            '  "entry_price": 可操作价格或 null,\n'
            '  "target_price": 目标价或 null,\n'
            '  "stop_loss": 止损价或 null,\n'
            '  "position_sizing": "仓位建议(如 30% 仓)",\n'
            '  "conditions": ["策略成立所需条件1", ...],\n'
            '  "missing_conditions": ["缺失信息1", ...],\n'
            '  "risk_items": ["风险1", ...],\n'
            '  "opportunity_items": ["机会1", ...],\n'
            '  "data_gaps": ["检测到的数据缺口"],\n'
            '  "basis": ["引用的新闻或指标摘要"],\n'
            '  "tags": ["标签1", ...]\n'
            "}\n"
            f"上下文：\n{context_text}\n"
            "务必只输出 JSON，不要添加解释或 Markdown 代码框。"
            f"{extra}"
        )

    def _build_judge_prompt(
        self,
        model: str,
        context_text: str,
        base_results: List[Dict[str, Any]],
        code: str,
        question: Optional[str],
    ) -> str:
        valid_results = [res for res in base_results if res.get("status") == "success" and res.get("result")]
        summary = json.dumps(valid_results, ensure_ascii=False)
        extra = f"\n决策人补充：{question}" if question else ""
        return (
            f"你是最终策略评审官。给定股票 {code} 的上下文和多名模型的建议，"
            "需要评估信息完整性、识别冲突，并给出唯一可执行方案。"
            "如果所有建议都缺乏依据或关键信息，请返回 status=\"insufficient_data\" 并说明缺口。"
            "上下文：\n"
            f"{context_text}\n分析师建议：{summary}\n"
            "请输出 JSON：\n"
            "{\n"
            '  "recommended": {\n'
            '      "action": "...",\n'
            '      "rationale": "...",\n'
            '      "confidence": 0-1,\n'
            '      "timeframe": "...",\n'
            '      "entry_price": 数值或null,\n'
            '      "target_price": 数值或null,\n'
            '      "stop_loss": 数值或null,\n'
            '      "conditions": ["..."],\n'
            '      "basis": ["引用了哪些模型/证据"],\n'
            '      "tags": ["..."]\n'
            "  },\n"
            '  "summary": "整体观点",\n'
            '  "deciding_factors": ["做出裁决的关键因素"],\n'
            '  "referenced_models": [{"model": "deepseek", "weight": "高", "confidence": 0.7}, ...],\n'
            '  "risk_notes": ["...", "..."],\n'
            '  "opportunity_notes": ["...", "..."],\n'
            '  "warnings": ["条件不足提示"],\n'
            '  "status": "ok/insufficient_data"\n'
            "}\n"
            "严格输出 JSON，不要附加解释或 Markdown。"
            f"{extra}"
        )
