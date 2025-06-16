import futu as ft
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from config import settings
from models.futu_models import *
import base64


class FutuService:
    """富途API服务类"""
    
    def __init__(self):
        self.quote_ctx: Optional[ft.OpenQuoteContext] = None
        self.is_connected = False
        
        # 定义各种数据类型的有效字段集合
        self.ESSENTIAL_FIELDS = {
            'kline': [
                'code', 'name', 'time_key', 'open', 'close', 'high', 'low', 
                'volume', 'turnover', 'change_rate', 'last_close'
            ],
            'quote': [
                'code', 'stock_name', 'last_price', 'open_price', 'high_price', 
                'low_price', 'prev_close_price', 'volume', 'turnover', 
                'change_rate', 'update_time'
            ],
            'market_snapshot': [
                'code', 'stock_name', 'last_price', 'open_price', 'high_price',
                'low_price', 'prev_close_price', 'volume', 'turnover',
                'change_rate', 'update_time', 'lot_size'
            ],
            'basic_info': [
                'code', 'name', 'lot_size', 'stock_type', 'listing_date', 
                'delisting', 'exchange_type'
            ]
        }
        
        # 定义应该过滤的无意义值
        self.MEANINGLESS_VALUES = {
            'pe_ratio': [0.0, -1.0],
            'turnover_rate': [0.0, -1.0],
            'pb_ratio': [0.0, -1.0],
            'dividend_yield': [0.0, -1.0],
            'option_type': ['N/A', '', None],
            'strike_price': ['N/A', '', None, 0.0],
            'suspension': ['N/A', '', None],
            'stock_child_type': ['N/A', '', None],
            'index_option_type': ['N/A', '', None]
        }
        
    async def connect(self) -> bool:
        """连接到富途OpenD"""
        try:
            self.quote_ctx = ft.OpenQuoteContext(
                host=settings.futu_host, 
                port=settings.futu_port
            )
            
            # 测试连接
            ret, data = self.quote_ctx.get_global_state()
            if ret == ft.RET_OK:
                self.is_connected = True
                logger.info(f"成功连接到富途OpenD: {settings.futu_host}:{settings.futu_port}")
                return True
            else:
                logger.error(f"连接富途OpenD失败: {data}")
                return False
                
        except Exception as e:
            logger.error(f"连接富途OpenD异常: {str(e)}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.quote_ctx:
            self.quote_ctx.close()
            self.is_connected = False
            logger.info("已断开富途OpenD连接")
    
    def _check_connection(self):
        """检查连接状态"""
        if not self.is_connected or not self.quote_ctx:
            raise Exception("富途OpenD未连接")
    
    def _convert_market(self, market: Market) -> ft.Market:
        """转换市场类型"""
        market_map = {
            Market.HK: ft.Market.HK,
            Market.US: ft.Market.US,
            Market.CN: ft.Market.SH,  # 修复：使用上海市场枚举而不是CN_SH
            Market.SG: ft.Market.SG,
            Market.JP: ft.Market.JP
        }
        return market_map.get(market, ft.Market.HK)
    
    def _convert_security_type(self, security_type: SecurityType) -> ft.SecurityType:
        """转换证券类型"""
        type_map = {
            SecurityType.STOCK: ft.SecurityType.STOCK,
            SecurityType.INDEX: ft.SecurityType.IDX,
            SecurityType.ETF: ft.SecurityType.ETF,
            SecurityType.WARRANT: ft.SecurityType.WARRANT,
            SecurityType.BOND: ft.SecurityType.BOND
        }
        return type_map.get(security_type, ft.SecurityType.STOCK)
    
    def _convert_kl_type(self, kl_type: KLType) -> ft.KLType:
        """转换K线类型"""
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
        """转换复权类型"""
        au_map = {
            AuType.QFQ: ft.AuType.QFQ,
            AuType.HFQ: ft.AuType.HFQ,
            AuType.NONE: ft.AuType.NONE
        }
        return au_map.get(au_type, ft.AuType.QFQ)
    
    def _convert_sub_type(self, sub_type: SubType) -> ft.SubType:
        """转换订阅类型"""
        sub_map = {
            SubType.QUOTE: ft.SubType.QUOTE,
            SubType.ORDER_BOOK: ft.SubType.ORDER_BOOK,
            SubType.TICKER: ft.SubType.TICKER,
            SubType.K_DAY: ft.SubType.K_DAY,
            SubType.K_1M: ft.SubType.K_1M,
            SubType.RT_DATA: ft.SubType.RT_DATA,
            SubType.BROKER: ft.SubType.BROKER
        }
        return sub_map.get(sub_type, ft.SubType.QUOTE)
    
    def _calculate_days_back(self, ktype: KLType, max_count: int) -> int:
        """根据K线类型和数据量计算需要往前推的天数"""
        if ktype == KLType.K_DAY:
            # 日K：考虑交易日，通常每周5个交易日，为保险起见乘以1.5
            return int(max_count * 1.5)
        elif ktype == KLType.K_WEEK:
            # 周K：每周一根，按自然周计算
            return max_count * 7 + 7  # 多加7天保险
        elif ktype == KLType.K_MON:
            # 月K：每月一根，按30天计算
            return max_count * 30 + 30  # 多加30天保险
        elif ktype in [KLType.K_1M, KLType.K_3M, KLType.K_5M, KLType.K_15M, KLType.K_30M, KLType.K_60M]:
            # 分钟K：只在交易时间内有数据，保守估计每天6小时交易时间
            if ktype == KLType.K_1M:
                bars_per_day = 6 * 60  # 每天约360根1分钟K线
            elif ktype == KLType.K_3M:
                bars_per_day = 6 * 20  # 每天约120根3分钟K线
            elif ktype == KLType.K_5M:
                bars_per_day = 6 * 12  # 每天约72根5分钟K线
            elif ktype == KLType.K_15M:
                bars_per_day = 6 * 4   # 每天约24根15分钟K线
            elif ktype == KLType.K_30M:
                bars_per_day = 6 * 2   # 每天约12根30分钟K线
            elif ktype == KLType.K_60M:
                bars_per_day = 6       # 每天约6根60分钟K线
            
            days_needed = max_count / bars_per_day
            # 考虑只有交易日有数据，按1.5倍计算（一周5个交易日）
            return max(int(days_needed * 1.5) + 5, 10)  # 最少10天
        else:
            # 默认情况
            return max_count + 10
    
    def _clean_meaningless_data(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """清理无意义的数据"""
        cleaned_record = {}
        
        for key, value in record.items():
            # 检查是否是无意义的值
            if key in self.MEANINGLESS_VALUES:
                if value in self.MEANINGLESS_VALUES[key]:
                    continue  # 跳过无意义的值
            
            # 处理空字符串和None值
            if value in ['', None] or (isinstance(value, str) and value.strip() == ''):
                continue
                
            # 处理数值类型的特殊情况
            if isinstance(value, (int, float)):
                # 跳过明显异常的数值
                if key.endswith('_price') and value <= 0:
                    continue
                if key == 'volume' and value <= 0:
                    continue
                    
            cleaned_record[key] = value
            
        return cleaned_record
    
    def _filter_fields(self, record: Dict[str, Any], field_type: str, 
                      requested_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """根据字段类型和请求字段过滤数据"""
        if requested_fields:
            # 如果用户指定了特定字段，只返回这些字段
            return {k: v for k, v in record.items() if k in requested_fields}
        
        # 否则返回预定义的核心字段
        essential_fields = self.ESSENTIAL_FIELDS.get(field_type, [])
        if essential_fields:
            return {k: v for k, v in record.items() if k in essential_fields}
        
        # 如果没有预定义字段，返回所有字段
        return record
    
    def _optimize_binary_data(self, data: Any) -> Any:
        """优化二进制数据"""
        if isinstance(data, bytes):
            try:
                # 尝试解码为UTF-8
                return data.decode('utf-8', errors='ignore')
            except:
                # 如果解码失败，转换为base64
                return base64.b64encode(data).decode('ascii')
        return data
    
    def _dataframe_to_dict(self, df: pd.DataFrame, field_type: str = 'default',
                          optimization_config = None) -> List[Dict[str, Any]]:
        """将DataFrame转换为字典列表，支持数据优化"""
        if df is None or df.empty:
            return []
        
        # 处理NaN值 - 先用空字符串填充，然后在后续处理中转换为None
        df = df.fillna('')
        
        result = []
        for _, row in df.iterrows():
            record = row.to_dict()
            
            if optimization_config and optimization_config.enable_optimization:
                # 清理无意义数据
                if optimization_config.remove_meaningless_values:
                    record = self._clean_meaningless_data(record)
                
                # 过滤字段
                requested_fields = optimization_config.custom_fields
                if not requested_fields and optimization_config.only_essential_fields:
                    record = self._filter_fields(record, field_type, None)
                elif requested_fields:
                    record = self._filter_fields(record, field_type, requested_fields)
            
            result.append(record)
        
        return result
        
    async def get_stock_quote(self, request: StockQuoteRequest) -> APIResponse:
        """获取股票报价"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_market_snapshot(request.code_list)
            
            if ret == ft.RET_OK:
                # 使用优化配置
                result = self._dataframe_to_dict(data, 'quote', request.optimization)
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取股票报价成功",
                    data={"quotes": result, "data_count": len(result)}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取股票报价失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取股票报价异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取股票报价异常: {str(e)}",
                data=None
            )
    
    async def get_history_kline(self, request: HistoryKLineRequest) -> APIResponse:
        """获取历史K线数据"""
        self._check_connection()
        
        try:
            # 智能处理时间范围：如果没有指定start和end，自动设置为最近的时间范围
            start_date = request.start
            end_date = request.end
            
            if not start_date and not end_date:
                # 没有指定时间范围，设置为最近的数据
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime('%Y-%m-%d')
                
                # 根据K线类型和max_count计算开始日期
                days_back = self._calculate_days_back(request.ktype, request.max_count)
                start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
                
                logger.info(f"自动设置时间范围: {start_date} 到 {end_date} (请求{request.max_count}条{request.ktype}数据)")
            
            # 使用富途API的默认字段
            fields = [ft.KL_FIELD.ALL] if request.fields is None else [ft.KL_FIELD.ALL]
            
            ret, data, page_req_key = self.quote_ctx.request_history_kline(
                code=request.code,
                start=start_date,
                end=end_date,
                ktype=self._convert_kl_type(request.ktype),
                autype=self._convert_au_type(request.autype),
                fields=fields,
                max_count=request.max_count
            )
            
            if ret == ft.RET_OK:
                # 使用优化配置
                kline_list = self._dataframe_to_dict(data, 'kline', request.optimization)
                
                # 优化page_req_key的处理
                page_key_str = None
                if page_req_key is not None and request.optimization.optimize_binary_data:
                    page_key_str = self._optimize_binary_data(page_req_key)
                elif page_req_key is not None:
                    page_key_str = str(page_req_key)
                
                result_data = {
                    "kline_data": kline_list,
                    "data_count": len(kline_list)
                }
                
                # 只有在page_req_key有意义时才包含它
                if page_key_str and len(page_key_str) > 0:
                    result_data["page_req_key"] = page_key_str
                
                return APIResponse(
                    ret_code=0,
                    ret_msg="成功",
                    data=result_data
                )
            else:
                return APIResponse(
                    ret_code=-1,
                    ret_msg=f"获取历史K线失败: {data}",
                    data=None
                )
                
        except Exception as e:
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取历史K线异常: {str(e)}",
                data=None
            )
    
    async def get_current_kline(self, request: CurrentKLineRequest) -> APIResponse:
        """获取当前K线数据"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_cur_kline(
                code=request.code,
                num=request.num,
                ktype=self._convert_kl_type(request.ktype),
                autype=self._convert_au_type(request.autype)
            )
            
            if ret == ft.RET_OK:
                result = self._dataframe_to_dict(data, 'kline', request.optimization)
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取当前K线成功",
                    data={"kline_data": result, "data_count": len(result)}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取当前K线失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取当前K线异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取当前K线异常: {str(e)}",
                data=None
            )
    
    async def get_market_snapshot(self, request: MarketSnapshotRequest) -> APIResponse:
        """获取市场快照"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_market_snapshot(request.code_list)
            
            if ret == ft.RET_OK:
                result = self._dataframe_to_dict(data, 'market_snapshot', request.optimization)
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取市场快照成功",
                    data={"snapshots": result, "data_count": len(result)}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取市场快照失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取市场快照异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取市场快照异常: {str(e)}",
                data=None
            )
    
    async def get_stock_basicinfo(self, request: StockBasicInfoRequest) -> APIResponse:
        """获取股票基本信息"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_stock_basicinfo(
                market=self._convert_market(request.market),
                stock_type=self._convert_security_type(request.stock_type)
            )
            
            if ret == ft.RET_OK:
                # 应用数据量限制，避免token超出
                total_count = len(data) if data is not None else 0
                if request.max_count and request.max_count > 0 and total_count > request.max_count:
                    data = data.head(request.max_count)
                    logger.info(f"数据量限制: 原始{total_count}只股票，限制为{request.max_count}只")
                
                result = self._dataframe_to_dict(data, 'basic_info', request.optimization)
                
                response_data = {
                    "basic_info": result, 
                    "data_count": len(result),
                    "total_available": total_count
                }
                
                # 如果应用了数量限制，在返回消息中提示
                msg = "获取股票基本信息成功"
                if request.max_count and total_count > request.max_count:
                    msg += f"（已限制返回{request.max_count}/{total_count}只股票）"
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=msg,
                    data=response_data
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取股票基本信息失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取股票基本信息异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取股票基本信息异常: {str(e)}",
                data=None
            )
    
    async def subscribe(self, request: SubscribeRequest) -> APIResponse:
        """订阅数据"""
        self._check_connection()
        
        try:
            subtype_list = [self._convert_sub_type(sub) for sub in request.subtype_list]
            ret, err_message = self.quote_ctx.subscribe(request.code_list, subtype_list)
            
            if ret == ft.RET_OK:
                return APIResponse(
                    ret_code=0,
                    ret_msg="订阅成功",
                    data={"subscribed_codes": request.code_list}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"订阅失败: {err_message}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"订阅异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"订阅异常: {str(e)}",
                data=None
            )
    
    async def get_order_book(self, request: OrderBookRequest) -> APIResponse:
        """获取摆盘数据"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_order_book(request.code, num=request.num)
            
            if ret == ft.RET_OK:
                result = self._dataframe_to_dict(data, 'order_book', request.optimization)
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取摆盘成功",
                    data={"order_book": result, "data_count": len(result)}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取摆盘失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取摆盘异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取摆盘异常: {str(e)}",
                data=None
            )
    
    async def get_rt_ticker(self, request: TickerRequest) -> APIResponse:
        """获取逐笔数据"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_rt_ticker(request.code, num=request.num)
            
            if ret == ft.RET_OK:
                result = self._dataframe_to_dict(data, 'ticker', request.optimization)
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取逐笔数据成功",
                    data={"ticker_data": result, "data_count": len(result)}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取逐笔数据失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取逐笔数据异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取逐笔数据异常: {str(e)}",
                data=None
            )
    
    async def get_rt_data(self, request: RTDataRequest) -> APIResponse:
        """获取分时数据"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_rt_data(request.code)
            
            if ret == ft.RET_OK:
                result = self._dataframe_to_dict(data, 'rt_data', request.optimization)
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取分时数据成功",
                    data={"rt_data": result, "data_count": len(result)}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取分时数据失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取分时数据异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取分时数据异常: {str(e)}",
                data=None
            )
    
    async def get_trading_days(self, request: TradingDaysRequest) -> APIResponse:
        """获取交易日"""
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_trading_days(
                market=self._convert_market(request.market),
                start=request.start,
                end=request.end
            )
            
            if ret == ft.RET_OK:
                result = self._dataframe_to_dict(data, 'trading_days', request.optimization)
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取交易日成功",
                    data={"trading_days": result, "data_count": len(result)}
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取交易日失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取交易日异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取交易日异常: {str(e)}",
                data=None
            ) 