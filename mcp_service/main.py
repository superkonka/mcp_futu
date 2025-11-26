import os
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, Field, ConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.web_api_client import WebAPIClient
from models.analysis_models import AnalysisSnapshotRequest


WEB_API_BASE_URL = os.getenv("WEB_API_BASE_URL", "http://localhost:8001")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "9001"))

app = FastAPI(title="MCP Wrapper Service")
router = APIRouter(prefix="/mcp", tags=["mcp"])

web_client = WebAPIClient(base_url=WEB_API_BASE_URL)


async def _proxy(callable_: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    try:
        return await callable_(*args, **kwargs)
    except httpx.HTTPStatusError as exc:  # pragma: no cover - pass detailed error upstream
        detail: Any
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except Exception as exc:  # pragma: no cover - unexpected runtime error
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class CreateSessionRequest(BaseModel):
    code: str = Field(..., description="Stock code, e.g. HK.00700")
    nickname: str | None = Field(None, description="Optional human-readable alias")


@router.post("/dashboard/session", operation_id="create_dashboard_session")
async def create_dashboard_session(req: CreateSessionRequest) -> Any:
    return await _proxy(web_client.create_dashboard_session, req.code, req.nickname)


@router.get("/dashboard/sessions", operation_id="list_dashboard_sessions")
async def list_dashboard_sessions() -> Any:
    return await _proxy(web_client.list_dashboard_sessions)


@router.delete("/dashboard/session/{session_id}", operation_id="delete_dashboard_session")
async def delete_dashboard_session(session_id: str) -> Any:
    return await _proxy(web_client.delete_dashboard_session, session_id)


@router.get("/dashboard/bootstrap/{session_id}", operation_id="get_dashboard_bootstrap")
async def get_dashboard_bootstrap(session_id: str) -> Any:
    return await _proxy(web_client.get_dashboard_bootstrap, session_id)


class RecommendationRequest(BaseModel):
    code: str
    action: str
    rationale: str
    confidence: float | None = None
    timeframe: str | None = None
    tags: list[str] = Field(default_factory=list)


@router.post("/recommendations", operation_id="save_recommendation")
async def save_recommendation(req: RecommendationRequest) -> Any:
    payload = req.model_dump()
    return await _proxy(web_client.save_recommendation, payload)


class RecommendationQuery(BaseModel):
    code: str
    limit: int = Field(20, ge=1, le=200)


@router.post("/recommendations/query", operation_id="query_recommendations")
async def query_recommendations(req: RecommendationQuery) -> Any:
    payload = req.model_dump()
    return await _proxy(web_client.query_recommendations, payload)


class FundamentalSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    q: str = Field(..., description="Search keywords")
    scope: str = Field("news", description="Search scope, defaults to news")
    size: int = Field(10, ge=1, le=50)
    include_summary: bool = Field(True, alias="includeSummary")
    concise_snippet: bool = Field(True, alias="conciseSnippet")


@router.post("/fundamental/search", operation_id="fundamental_search")
async def fundamental_search(req: FundamentalSearchRequest) -> Any:
    payload = req.model_dump(by_alias=True)
    return await _proxy(web_client.search_fundamental, payload)


class StockFundamentalSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    stock_code: str = Field(..., alias="stock_code")
    stock_name: str | None = Field("", alias="stock_name")


@router.post("/fundamental/stock-search", operation_id="stock_fundamental_search")
async def stock_fundamental_search(req: StockFundamentalSearchRequest) -> Any:
    payload = req.model_dump(by_alias=True)
    return await _proxy(web_client.search_stock_fundamental, payload)


class ReadWebpageRequest(BaseModel):
    url: str


@router.post("/fundamental/read-webpage", operation_id="read_webpage")
async def read_webpage(req: ReadWebpageRequest) -> Any:
    payload = req.model_dump()
    return await _proxy(web_client.read_webpage, payload)


@router.post("/analysis/snapshot", operation_id="get_analysis_snapshot")
async def get_analysis_snapshot(req: AnalysisSnapshotRequest) -> Any:
    payload = req.model_dump(mode="json")
    return await _proxy(web_client.get_analysis_snapshot, payload)


@router.get("/health", operation_id="health")
async def health() -> Any:
    await _proxy(web_client._request, "GET", "/health")
    return {"status": "ok"}


app.include_router(router)
mcp = FastApiMCP(app, name="mcp-wrapper", description="MCP wrapper that proxies Web API")
mcp.mount()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
