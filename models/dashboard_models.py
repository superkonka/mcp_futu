from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DashboardSessionRequest(BaseModel):
    code: str = Field(..., description="股票代码，如 HK.00700")
    nickname: Optional[str] = Field(None, description="展示名称/备注，可选")


class DashboardSessionResponse(BaseModel):
    session_id: str = Field(..., description="会话ID")
    url: str = Field(..., description="可直接打开的看板地址")


class DashboardSessionItem(BaseModel):
    session_id: str
    code: str
    nickname: Optional[str] = None
    created_at: Optional[str]
    quote: Optional[Dict[str, Any]] = None
    strategy: Optional[str] = None
    last_signal_time: Optional[str] = None


class DashboardBootstrapResponse(BaseModel):
    code: str
    session: Optional[Dict[str, Any]] = None
    quote: Optional[Dict[str, Any]] = None
    signals: Dict[str, List[Dict[str, Any]]]
    recommendations: List[Dict[str, Any]]
    holding: Optional[dict]
    capital_flow: Optional[Dict[str, Any]] = None
    capital_distribution: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = None
    history_kline: Optional[List[Dict[str, Any]]] = None
