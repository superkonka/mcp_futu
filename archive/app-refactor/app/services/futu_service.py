import futu as ft
import pandas as pd
from typing import List, Dict, Any, Optional
from loguru import logger
from app.config import settings
from app.models.futu import *
from app.services.cache_service import cache_manager
from app.services.subscription_service import subscription_manager
import asyncio
import time

class FutuService:
    """富途API服务类"""
    
    def __init__(self):
        self.quote_ctx = None
        self.trade_ctx = None
        
    async def connect(self) -> bool:
        """连接到富途OpenD"""
        try:
            # 行情连接
            self.quote_ctx = ft.OpenQuoteContext(
                host=settings.futu_host,
                port=settings.futu_port
            )
            
            ret, data = self.quote_ctx.get_global_state()
            if ret == ft.RET_OK:
                logger.info(f"成功连接到富途OpenD行情: {settings.futu_host}:{settings.futu_port}")
            else:
                logger.error(f"连接富途OpenD行情失败: {data}")
                return False
            
            # 启动清理任务
            asyncio.create_task(subscription_manager.cleanup_stale_clients())
            
            # 交易连接 (可选)
            try:
                # 尝试连接交易上下文
                trade_ctx_cls = getattr(ft, "OpenSecTradeContext", None) or getattr(ft, "OpenTradeContext", None)
                if trade_ctx_cls:
                    init_kwargs = {
                        "host": settings.futu_host,
                        "port": settings.futu_port,
                    }
                    if trade_ctx_cls.__name__ == "OpenSecTradeContext":
                         init_kwargs["filter_trdmarket"] = ft.TrdMarket.HK
                         if hasattr(ft, "SecurityFirm"):
                             init_kwargs["security_firm"] = ft.SecurityFirm.FUTUSECURITIES
                    
                    self.trade_ctx = trade_ctx_cls(**init_kwargs)
                    
                    # 解锁
                    if settings.futu_pwd_unlock:
                        ret, msg = self.trade_ctx.unlock_trade(settings.futu_pwd_unlock)
                        if ret == ft.RET_OK:
                            logger.info("✅ 交易接口已解锁")
                        else:
                            logger.warning(f"⚠️ 交易解锁失败: {msg}")
            except Exception as e:
                logger.warning(f"交易连接初始化失败: {e}")
                
            return True
        except Exception as e:
            logger.error(f"连接富途OpenD异常: {e}")
            return False

    async def disconnect(self):
        if self.quote_ctx:
            self.quote_ctx.close()
        if self.trade_ctx:
            self.trade_ctx.close()

    def _check_connection(self):
        if not self.quote_ctx:
            raise Exception("富途OpenD行情未连接")

    # === 辅助转换方法 ===
    def _convert_kl_type(self, kl_type: KLType) -> ft.KLType:
        kl_map = {
            KLType.K_1M: ft.KLType.K_1M,
            KLType.K_3M: ft.KLType.K_3M,
            KLType.K_5M: ft.KLType.K_5M,
            KLType.K_15M: ft.KLType.K_15M,
            KLType.K_30M: ft.KLType.K_30M,
            KLType.K_60M: ft.KLType.K_60M,
            KLType.K_DAY: ft.KLType.K_DAY,
            KLType.K_WEEK: ft.KLType.K_WEEK,
            KLType.K_MON: ft.KLType.K_MON
        }
        return kl_map.get(kl_type, ft.KLType.K_DAY)

    def _convert_au_type(self, au_type: AuType) -> ft.AuType:
        au_map = {
            AuType.QFQ: ft.AuType.QFQ,
            AuType.HFQ: ft.AuType.HFQ,
            AuType.NONE: ft.AuType.NONE
        }
        return au_map.get(au_type, ft.AuType.QFQ)

    def _dataframe_to_dict(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        df = df.fillna('')
        return df.to_dict('records')

    # === 核心API方法 ===

    async def get_stock_quote(self, request: StockQuoteRequest) -> APIResponse:
        self._check_connection()
        try:
            # 1. 尝试缓存
            cached_data = await cache_manager.get_quote_cache(request.code_list)
            if len(cached_data) == len(request.code_list):
                return APIResponse(ret_code=0, ret_msg="OK (Cache)", data={"quotes": list(cached_data.values())})
            
            # 2. API请求
            ret, data = self.quote_ctx.get_market_snapshot(request.code_list)
            if ret == ft.RET_OK:
                quotes = self._dataframe_to_dict(data)
                # 3. 写入缓存
                await cache_manager.set_quote_cache(quotes)
                # 4. 广播报价
                await subscription_manager.broadcast_quotes(quotes)
                return APIResponse(ret_code=0, ret_msg="OK", data={"quotes": quotes})
            else:
                return APIResponse(ret_code=ret, ret_msg=data, data=None)
        except Exception as e:
            logger.error(f"get_stock_quote error: {e}")
            return APIResponse(ret_code=-1, ret_msg=str(e), data=None)

    async def get_history_kline(self, request: HistoryKLineRequest) -> APIResponse:
        self._check_connection()
        try:
            # 简单处理：如果有start/end，先查缓存，再查API（这里简化为直接查API并缓存）
            # 实际生产应做精细的时间段合并
            
            # 自动计算时间
            start_date = request.start
            end_date = request.end
            if not start_date:
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d') # 默认一年
            
            # 1. 查缓存 (仅演示，实际需要按时间段查)
            cached_kline = await cache_manager.get_kline_data(
                request.code, request.ktype.value, start_date, end_date
            )
            if cached_kline and len(cached_kline) > 0:
                 # 简单判断：如果缓存数据量足够，直接返回
                 # 这是一个简化的逻辑
                 pass

            ret, data, page_req_key = self.quote_ctx.request_history_kline(
                code=request.code,
                start=start_date,
                end=end_date,
                ktype=self._convert_kl_type(request.ktype),
                autype=self._convert_au_type(request.autype),
                fields=[ft.KL_FIELD.ALL],
                max_count=request.max_count
            )
            
            if ret == ft.RET_OK:
                kline_list = self._dataframe_to_dict(data)
                # 写入缓存
                await cache_manager.store_kline_data(request.code, request.ktype.value, kline_list)
                return APIResponse(ret_code=0, ret_msg="OK", data={"kline_data": kline_list})
            else:
                return APIResponse(ret_code=ret, ret_msg=data, data=None)
        except Exception as e:
            logger.error(f"get_history_kline error: {e}")
            return APIResponse(ret_code=-1, ret_msg=str(e), data=None)

    async def get_stock_basicinfo(self, request: StockBasicInfoRequest) -> APIResponse:
        self._check_connection()
        try:
             # 转换市场
            market_map = {
                Market.HK: ft.Market.HK,
                Market.US: ft.Market.US,
                Market.CN: ft.Market.SH,
                Market.SG: ft.Market.SG,
                Market.JP: ft.Market.JP
            }
            ft_market = market_map.get(request.market, ft.Market.HK)
            
            # 转换证券类型
            type_map = {
                SecurityType.STOCK: ft.SecurityType.STOCK,
                SecurityType.INDEX: ft.SecurityType.IDX,
                SecurityType.ETF: ft.SecurityType.ETF,
                SecurityType.WARRANT: ft.SecurityType.WARRANT,
                SecurityType.BOND: ft.SecurityType.BOND
            }
            ft_type = type_map.get(request.stock_type, ft.SecurityType.STOCK)

            ret, data = self.quote_ctx.get_stock_basicinfo(market=ft_market, stock_type=ft_type)
            if ret == ft.RET_OK:
                # 截取max_count
                if request.max_count:
                    data = data.head(request.max_count)
                result = self._dataframe_to_dict(data)
                return APIResponse(ret_code=0, ret_msg="OK", data={"basic_info": result})
            else:
                return APIResponse(ret_code=ret, ret_msg=data, data=None)
        except Exception as e:
            return APIResponse(ret_code=-1, ret_msg=str(e), data=None)

    async def get_position_list(self, request: PositionListRequest) -> APIResponse:
        """获取持仓列表"""
        if not self.trade_ctx:
             return APIResponse(ret_code=-1, ret_msg="交易接口未连接", data=None)
        
        try:
            # 转换交易环境
            trd_env_map = {
                TrdEnv.SIMULATE: ft.TrdEnv.SIMULATE,
                TrdEnv.REAL: ft.TrdEnv.REAL
            }
            ft_trd_env = trd_env_map.get(request.trd_env, ft.TrdEnv.SIMULATE)
            
            # 转换市场过滤
            ft_position_market = ft.TrdMarket.HK
            if request.position_market:
                market_map = {
                    TrdMarket.HK: ft.TrdMarket.HK,
                    TrdMarket.US: ft.TrdMarket.US,
                    TrdMarket.CN: ft.TrdMarket.CN,
                    TrdMarket.HKCC: ft.TrdMarket.HKCC
                }
                ft_position_market = market_map.get(request.position_market, ft.TrdMarket.HK)
            
            ret, data = self.trade_ctx.position_list_query(
                code=request.code if request.code else "",
                pl_ratio_min=request.pl_ratio_min,
                pl_ratio_max=request.pl_ratio_max,
                trd_env=ft_trd_env,
                acc_id=request.acc_id,
                acc_index=request.acc_index,
                refresh_cache=request.refresh_cache
            )
            
            if ret == ft.RET_OK:
                position_list = self._dataframe_to_dict(data)
                return APIResponse(ret_code=0, ret_msg="OK", data={"position_list": position_list})
            else:
                return APIResponse(ret_code=ret, ret_msg=data, data=None)
        except Exception as e:
            logger.error(f"get_position_list error: {e}")
            return APIResponse(ret_code=-1, ret_msg=str(e), data=None)

futu_service = FutuService()
