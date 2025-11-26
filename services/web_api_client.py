import httpx
from typing import Any, Dict, Optional


class WebAPIClient:
    def __init__(self, base_url: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            if 'application/json' in response.headers.get('Content-Type', ''):
                return response.json()
            return {"content": response.text}

    async def create_dashboard_session(self, code: str, nickname: Optional[str] = None) -> Dict[str, Any]:
        payload = {"code": code}
        if nickname:
            payload["nickname"] = nickname
        return await self._request('POST', '/api/dashboard/session', json=payload)

    async def delete_dashboard_session(self, session_id: str) -> Dict[str, Any]:
        return await self._request('DELETE', f'/api/dashboard/session/{session_id}')

    async def list_dashboard_sessions(self) -> Dict[str, Any]:
        return await self._request('GET', '/api/dashboard/sessions')

    async def get_dashboard_bootstrap(self, session_id: str) -> Dict[str, Any]:
        return await self._request('GET', f'/api/dashboard/bootstrap?session={session_id}')

    async def save_recommendation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/recommendations', json=payload)

    async def query_recommendations(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/recommendations/query', json=payload)

    async def search_fundamental(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/fundamental/search', json=payload)

    async def search_stock_fundamental(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/fundamental/stock_search', json=payload)

    async def read_webpage(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/fundamental/read_webpage', json=payload)

    async def get_stock_quote(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/quote/stock_quote', json=payload)

    async def get_history_kline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/quote/history_kline', json=payload)

    async def get_stock_basic_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/quote/stock_basicinfo', json=payload)

    async def get_technical_indicators(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/analysis/technical_indicators', json=payload)

    async def get_macd_indicator(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/analysis/macd', json=payload)

    async def get_rsi_indicator(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/analysis/rsi', json=payload)

    async def get_cache_status(self, detailed: bool = False) -> Dict[str, Any]:
        params = {"detailed": str(detailed).lower()}
        return await self._request('GET', '/api/cache/status', params=params)

    async def preload_cache(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/cache/preload', json=payload)

    async def clear_cache(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('DELETE', '/api/cache/clear', json=payload)

    async def get_analysis_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request('POST', '/api/analysis/snapshot', json=payload)
