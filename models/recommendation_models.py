from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class RecommendationWriteRequest(BaseModel):
    code: str = Field(..., description="股票代码，如 HK.00700")
    action: Literal["BUY", "SELL", "HOLD", "EXIT", "ADD", "REDUCE", "WATCH"] = Field(..., description="操作类型")
    rationale: str = Field(..., description="建议依据/理由")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="信心度(0-1)")
    timeframe: Optional[str] = Field(None, description="适用时间框架，如 swing/position/1w-1m")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签，如 ['突破','财报']")
    source: Optional[str] = Field(None, description="来源，如 model_name 或 analyst")
    evidence: Optional[List[Any]] = Field(default_factory=list, description="证据列表，文本/结构化对象")
    status: Literal["draft", "ready", "running", "paused", "completed", "cancelled"] = Field("draft", description="策略状态")
    monitor_config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"price_interval": 60, "fundamental_interval": 1800, "enable_fundamental": False},
        description="盯盘配置"
    )
    entry_price: Optional[float] = Field(None, description="参考入场价，便于后续对比")
    target_price: Optional[float] = Field(None, description="目标价/预期价位")
    stop_loss: Optional[float] = Field(None, description="止损价位")
    valid_until: Optional[str] = Field(None, description="策略适用截止时间(UTC ISO8601)")
    eval_status: Optional[str] = Field(None, description="策略评估状态：pending/completed/invalid")
    eval_pnl_pct: Optional[float] = Field(None, description="策略回测盈亏百分比，单位：小数")
    eval_summary: Optional[str] = Field(None, description="策略评估摘要（来自LLM或程序）")
    eval_generated_at: Optional[str] = Field(None, description="评估时间")
    eval_detail: Optional[Dict[str, Any]] = Field(None, description="评估过程或详细记录")
    analysis_context: Optional[Dict[str, Any]] = Field(None, description="策略生成时的上下文快照")
    model_results: Optional[List[Dict[str, Any]]] = Field(None, description="多模型原始结果列表")
    judge_result: Optional[Dict[str, Any]] = Field(None, description="评审模型输出")


class RecommendationQueryRequest(BaseModel):
    code: Optional[str] = Field(None, description="按代码过滤")
    action: Optional[str] = Field(None, description="按操作过滤")
    adopted: Optional[bool] = Field(None, description="按是否采纳过滤")
    start: Optional[str] = Field(None, description="开始时间(UTC ISO8601)")
    end: Optional[str] = Field(None, description="结束时间(UTC ISO8601)")
    tag: Optional[str] = Field(None, description="包含某标签")
    source: Optional[str] = Field(None, description="来源过滤")
    limit: Optional[int] = Field(50, ge=1, le=200, description="返回条数上限")
    offset: Optional[int] = Field(0, ge=0, description="偏移量")


class RecommendationUpdateRequest(BaseModel):
    adopted: Optional[bool] = Field(None, description="更新采纳状态")
    adopted_at: Optional[str] = Field(None, description="采纳时间(UTC ISO8601)")
    eval_status: Optional[str] = Field(None, description="评估状态更新")
    eval_pnl_pct: Optional[float] = Field(None, description="更新策略评估收益")
    eval_summary: Optional[str] = Field(None, description="评估摘要")
    eval_generated_at: Optional[str] = Field(None, description="评估更新时间")
    eval_detail: Optional[Any] = Field(None, description="评估过程记录（对象或字符串）")
    status: Optional[str] = Field(None, description="策略状态更新")
    monitor_config: Optional[Dict[str, Any]] = Field(None, description="盯盘配置更新")


class RecommendationReevaluateRequest(BaseModel):
    models: List[str] = Field(default_factory=lambda: ["deepseek", "kimi"], description="重新评估使用的模型列表")
    judge_model: str = Field("gemini", description="评审模型")
    question: Optional[str] = Field(None, description="补充关注点或问题")
