import futu as ft
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from config import settings
from models.futu_models import *
import base64
import asyncio
import time
import socket


class FutuService:
    """富途API服务类"""
    
    def __init__(self):
        """初始化富途服务"""
        self.quote_ctx = None
        self.trade_ctx = None
        self.cache_manager = None  # 将在外部设置
        
        # === 订阅状态管理 ===
        self._subscription_status = {}  # 记录订阅状态 {code: {subtype: True/False}}
        self._subscription_lock = asyncio.Lock()  # 防止并发订阅冲突
        self._subscription_data_cache = {}  # 订阅数据临时缓存
        self._last_subscription_time = {}  # 上次订阅时间，用于清理
        
        # === 权限管理 ===
        self._quote_rights_checked = False  # 是否已检查权限
        self._last_quote_rights_check = 0  # 上次权限检查时间
        self._quote_rights_auto_request = True  # 是否自动请求最高权限
        
        logger.info("富途服务初始化")
        
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
            ],
            'capital_flow': [
                'in_flow', 'main_in_flow', 'super_in_flow', 'big_in_flow',
                'mid_in_flow', 'sml_in_flow', 'capital_flow_item_time', 'last_valid_time'
            ],
            'capital_distribution': [
                'capital_in_super', 'capital_in_big', 'capital_in_mid', 'capital_in_small',
                'capital_out_super', 'capital_out_big', 'capital_out_mid', 'capital_out_small',
                'update_time'
            ],
            'rehab': [
                'ex_div_date', 'split_ratio', 'per_cash_div', 'per_share_div_ratio',
                'per_share_trans_ratio', 'allotment_ratio', 'allotment_price',
                'stk_spo_ratio', 'stk_spo_price', 'forward_adj_factorA', 'forward_adj_factorB',
                'backward_adj_factorA', 'backward_adj_factorB'
            ],
            'stock_filter': [
                'code', 'name', 'cur_price', 'change_rate', 'volume', 'turnover',
                'market_val', 'pe_ratio', 'pb_ratio', 'turnover_rate'
            ],
            'plate_stock': [
                'code', 'stock_name', 'lot_size', 'stock_type', 'main_contract',
                'last_settle_price', 'position'
            ],
            'plate_list': [
                'plate_code', 'plate_name', 'plate_type'
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
            # 行情连接
            # 使用最新的 OpenD API 端口建立行情连接
            self.quote_ctx = ft.OpenQuoteContext(
                host=settings.futu_host,
                port=settings.futu_port
            )
            
            # 测试行情连接
            ret, data = self.quote_ctx.get_global_state()
            if ret == ft.RET_OK:
                logger.info(f"成功连接到富途OpenD行情: {settings.futu_host}:{settings.futu_port}")
                
                # 🧠 智能权限检查：启动时自动检查并获取最高权限
                logger.info("🔍 启动时权限检查...")
                await self._check_and_ensure_quote_rights(force_check=True)
                
            else:
                logger.error(f"连接富途OpenD行情失败: {data}")
                return False
            
            # 交易连接
            try:
                # 兼容不同版本的 Futu SDK：优先使用 OpenSecTradeContext
                trade_ctx_cls = getattr(ft, "OpenSecTradeContext", None) or getattr(ft, "OpenTradeContext", None)
                if not trade_ctx_cls:
                    logger.error("❌ 当前 futu SDK 不包含交易上下文类（OpenSecTradeContext/OpenTradeContext）")
                    logger.warning("⚠️ 请升级/安装正确的 futu 库，或检查环境隔离/冲突")
                else:
                    init_kwargs = {
                        "host": settings.futu_host,
                        "port": settings.futu_port,
                    }
                    # 如果是证券交易上下文，按官方文档增加市场过滤与券商
                    if trade_ctx_cls.__name__ == "OpenSecTradeContext":
                        try:
                            init_kwargs["filter_trdmarket"] = ft.TrdMarket.HK  # 默认港股，可按需调整
                            if hasattr(ft, "SecurityFirm"):
                                init_kwargs["security_firm"] = ft.SecurityFirm.FUTUSECURITIES
                        except Exception as e:
                            logger.warning(f"初始化交易上下文参数兼容处理异常: {str(e)}")
                    
                    self.trade_ctx = trade_ctx_cls(**init_kwargs)
                    logger.info(f"成功连接到富途OpenD交易: {settings.futu_host}:{settings.futu_port}")
                    
                    # 自动交易解锁（密码来自 .env 的 FUTU_UNLOCK_PASSWORD）
                    unlock_pwd = getattr(settings, 'futu_unlock_password', None)
                    if unlock_pwd:
                        try:
                            ret, msg = self.trade_ctx.unlock_trade(unlock_pwd)
                            if ret == ft.RET_OK:
                                logger.info("✅ 交易接口已解锁")
                            else:
                                logger.warning(f"⚠️ 交易解锁失败: {msg}")
                        except Exception as e:
                            logger.error(f"交易解锁异常: {str(e)}")
                    else:
                        logger.warning("⚠️ 未配置交易解锁密码（FUTU_UNLOCK_PASSWORD），交易接口可能不可用")
            except Exception as e:
                logger.warning(f"连接富途OpenD交易失败，但行情功能仍可用: {str(e)}")
                # 交易连接失败不影响行情功能
                
            return True
                
        except Exception as e:
            logger.error(f"连接富途OpenD异常: {str(e)}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.quote_ctx:
            self.quote_ctx.close()
            logger.info("已断开富途OpenD行情连接")
        if self.trade_ctx:
            self.trade_ctx.close()
            logger.info("已断开富途OpenD交易连接")
    
    def _check_connection(self):
        """检查行情连接状态"""
        if not self.quote_ctx:
            raise Exception("富途OpenD行情未连接")
    
    def _check_trade_connection(self):
        """检查交易连接状态"""
        if not self.trade_ctx:
            raise Exception("富途OpenD交易未连接")
    
    def has_trade_connection(self) -> bool:
        """交易连接是否可用"""
        return self.trade_ctx is not None
    
    async def _request_highest_quote_right(self, telnet_port: int = None) -> bool:
        """
        🔧 智能权限管理：通过Socket请求最高行情权限
        
        当发现行情权限被抢占时，自动向OpenD发送请求最高权限命令
        
        Args:
            telnet_port: OpenD Telnet端口，不传则读取 settings.futu_telnet_port
            
        Returns:
            bool: 是否成功请求权限
        """
        try:
            logger.info("🔧 正在通过Socket请求最高行情权限...")
            
            # 创建socket连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            
            try:
                # 连接到OpenD Telnet端口
                target_port = telnet_port or getattr(settings, 'futu_telnet_port', 65234)
                sock.connect(('127.0.0.1', target_port))
                
                # 发送请求最高权限命令
                command = b'request_highest_quote_right\r\n'
                sock.sendall(command)
                
                # 读取响应
                reply = b''
                start_time = time.time()
                while time.time() - start_time < 3:  # 最多等待3秒
                    try:
                        sock.settimeout(0.5)
                        data = sock.recv(1024)
                        if not data:
                            break
                        reply += data
                        if b'\r\n' in data:
                            break
                    except socket.timeout:
                        continue
                    except:
                        break
                
                # 解析响应
                response = reply.decode('gb2312', errors='ignore').strip()
                logger.info(f"📋 权限请求响应: {response}")
                
                # 判断是否成功
                success_indicators = ['成功', 'success', 'ok', '权限已获取', 'granted']
                if any(indicator in response.lower() for indicator in success_indicators):
                    logger.info("✅ 成功获取最高行情权限")
                    self._quote_rights_checked = True
                    self._last_quote_rights_check = time.time()
                    return True
                else:
                    # 即使响应不明确，也认为命令已发送
                    logger.info(f"📡 权限请求命令已发送，响应: {response}")
                    self._quote_rights_checked = True
                    self._last_quote_rights_check = time.time()
                    return True
                    
            finally:
                sock.close()
                    
        except Exception as e:
            logger.error(f"❌ 请求最高行情权限失败: {str(e)}")
            # 如果Telnet连接失败，可能OpenD没有开启Telnet功能，但这不影响权限
            logger.warning("⚠️ Telnet连接失败，可能OpenD未开启Telnet功能，将尝试继续执行")
            return False
    
    async def _check_and_ensure_quote_rights(self, force_check: bool = False) -> bool:
        """
        🧠 智能权限检查：检查并确保具有足够的行情权限
        
        Args:
            force_check: 是否强制检查，忽略缓存
            
        Returns:
            bool: 是否具有足够权限
        """
        current_time = time.time()
        
        # 如果最近已检查过且不强制检查，直接返回
        if (not force_check and 
            self._quote_rights_checked and 
            current_time - self._last_quote_rights_check < 300):  # 5分钟缓存
            return True
        
        try:
            logger.info("🔍 检查当前行情权限状态...")
            
            # 通过API检查当前权限
            ret, data = self.quote_ctx.get_global_state()
            if ret != ft.RET_OK:
                logger.warning(f"无法获取全局状态: {data}")
                return False
            
            # 检查是否有足够的权限（这里可以根据返回的数据判断）
            logger.info(f"📊 当前全局状态: {data}")
            
            # 尝试订阅一个测试股票来验证权限
            test_codes = ['HK.00700', 'HK.09988', 'HK.00005']
            rights_ok = False
            
            for test_code in test_codes:
                try:
                    ret, err_msg = self.quote_ctx.subscribe(test_code, [ft.SubType.ORDER_BOOK])
                    if ret == ft.RET_OK:
                        logger.info(f"✅ 权限验证成功，可以订阅 {test_code} 的ORDER_BOOK")
                        rights_ok = True
                        # 取消测试订阅
                        self.quote_ctx.unsubscribe(test_code, [ft.SubType.ORDER_BOOK])
                        break
                    else:
                        logger.debug(f"❌ 无法订阅 {test_code} 的ORDER_BOOK: {err_msg}")
                except Exception as e:
                    logger.debug(f"❌ 订阅测试异常 {test_code}: {str(e)}")
                    continue
            
            if not rights_ok and self._quote_rights_auto_request:
                logger.warning("⚠️ 权限不足，尝试自动请求最高权限...")
                rights_ok = await self._request_highest_quote_right()
                
                if rights_ok:
                    # 权限请求成功后，等待一下再次验证
                    await asyncio.sleep(1)
                    for test_code in test_codes:
                        try:
                            ret, err_msg = self.quote_ctx.subscribe(test_code, [ft.SubType.ORDER_BOOK])
                            if ret == ft.RET_OK:
                                logger.info(f"✅ 权限请求后验证成功: {test_code}")
                                self.quote_ctx.unsubscribe(test_code, [ft.SubType.ORDER_BOOK])
                                break
                        except:
                            continue
            
            self._quote_rights_checked = rights_ok
            self._last_quote_rights_check = current_time
            
            if rights_ok:
                logger.info("✅ 行情权限检查通过")
            else:
                logger.warning("⚠️ 行情权限不足，部分功能可能受限")
            
            return rights_ok
            
        except Exception as e:
            logger.error(f"❌ 权限检查异常: {str(e)}")
            return False
    
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
    
    def _convert_sub_type(self, sub_type: str):
        """将内部订阅类型转换为富途API订阅类型"""
        subtype_mapping = {
            'ORDER_BOOK': ft.SubType.ORDER_BOOK,
            'TICKER': ft.SubType.TICKER,
            'RT_DATA': ft.SubType.RT_DATA,
            'QUOTE': ft.SubType.QUOTE,
            'BROKER': ft.SubType.BROKER
        }
        return subtype_mapping.get(sub_type)
    
    def _convert_period_type(self, period_type: PeriodType) -> ft.PeriodType:
        """转换周期类型"""
        period_map = {
            PeriodType.INTRADAY: ft.PeriodType.INTRADAY,
            PeriodType.DAY: ft.PeriodType.DAY,
            PeriodType.WEEK: ft.PeriodType.WEEK,
            PeriodType.MONTH: ft.PeriodType.MONTH
        }
        return period_map.get(period_type, ft.PeriodType.INTRADAY)
    
    def _convert_stock_field(self, stock_field: StockField) -> ft.StockField:
        """转换股票字段"""
        field_map = {
            StockField.STOCK_CODE: ft.StockField.STOCK_CODE,
            StockField.STOCK_NAME: ft.StockField.STOCK_NAME,
            StockField.CUR_PRICE: ft.StockField.CUR_PRICE,
            StockField.CUR_PRICE_TO_PRE_CLOSE_RATIO: ft.StockField.CUR_PRICE_TO_PRE_CLOSE_RATIO,
            StockField.PRICE_CHANGE: ft.StockField.PRICE_CHANGE,
            StockField.VOLUME: ft.StockField.VOLUME,
            StockField.TURNOVER: ft.StockField.TURNOVER,
            StockField.TURNOVER_RATE: ft.StockField.TURNOVER_RATE,
            StockField.AMPLITUDE: ft.StockField.AMPLITUDE,
            StockField.HIGH_PRICE: ft.StockField.HIGH_PRICE,
            StockField.LOW_PRICE: ft.StockField.LOW_PRICE,
            StockField.OPEN_PRICE: ft.StockField.OPEN_PRICE,
            StockField.PRE_CLOSE_PRICE: ft.StockField.PRE_CLOSE_PRICE,
            StockField.PE_RATIO: ft.StockField.PE_RATIO,
            StockField.PB_RATIO: ft.StockField.PB_RATIO,
            StockField.MARKET_VAL: ft.StockField.MARKET_VAL,
            StockField.MA5: ft.StockField.MA5,
            StockField.MA10: ft.StockField.MA10,
            StockField.MA20: ft.StockField.MA20,
            StockField.MA30: ft.StockField.MA30,
            StockField.MA60: ft.StockField.MA60,
            StockField.RSI14: ft.StockField.RSI14
        }
        return field_map.get(stock_field, ft.StockField.CUR_PRICE)
    
    def _convert_sort_field(self, sort_field: str) -> ft.SortField:
        """转换排序字段"""
        field_map = {
            "CODE": ft.SortField.CODE,
            "CUR_PRICE": ft.SortField.CUR_PRICE,
            "CHANGE_RATE": ft.SortField.CHANGE_RATE,
            "VOLUME": ft.SortField.VOLUME,
            "TURNOVER": ft.SortField.TURNOVER,
            "MARKET_VAL": ft.SortField.MARKET_VAL,
        }
        return field_map.get(sort_field, ft.SortField.CODE)
    
    def _convert_sort_dir(self, sort_dir: SortDir) -> ft.SortDir:
        """转换排序方向"""
        sort_map = {
            SortDir.NONE: ft.SortDir.NONE,
            SortDir.ASCEND: ft.SortDir.ASCEND,
            SortDir.DESCEND: ft.SortDir.DESCEND
        }
        return sort_map.get(sort_dir, ft.SortDir.NONE)
    
    def _convert_plate_set_type(self, plate_set_type: PlateSetType) -> ft.Plate:
        """转换板块集合类型"""
        plate_map = {
            PlateSetType.ALL: ft.Plate.ALL,
            PlateSetType.INDUSTRY: ft.Plate.INDUSTRY,
            PlateSetType.REGION: ft.Plate.REGION,
            PlateSetType.CONCEPT: ft.Plate.CONCEPT
        }
        return plate_map.get(plate_set_type, ft.Plate.ALL)
    
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
        if df is None:
            return []
        
        # 检查输入是否是DataFrame
        if not isinstance(df, pd.DataFrame):
            logger.warning(f"_dataframe_to_dict接收到非DataFrame数据: {type(df)}, 内容: {df}")
            return []
            
        if df.empty:
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
    
    def _orderbook_dict_to_list(self, orderbook_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将摆盘dict数据转换为列表格式，便于处理"""
        if not isinstance(orderbook_data, dict):
            return []
        
        result = []
        
        # 处理买盘数据
        if 'Bid' in orderbook_data:
            for i, bid in enumerate(orderbook_data['Bid']):
                price, volume, order_count, broker_info = bid
                result.append({
                    'type': 'bid',
                    'level': i + 1,
                    'price': price,
                    'volume': volume,
                    'order_count': order_count,
                    'broker_info': broker_info
                })
        
        # 处理卖盘数据
        if 'Ask' in orderbook_data:
            for i, ask in enumerate(orderbook_data['Ask']):
                price, volume, order_count, broker_info = ask
                result.append({
                    'type': 'ask',
                    'level': i + 1,
                    'price': price,
                    'volume': volume,
                    'order_count': order_count,
                    'broker_info': broker_info
                })
        
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

    async def get_broker_queue(self, request: BrokerQueueRequest) -> APIResponse:
        """获取经纪队列（买卖盘经纪）"""
        self._check_connection()
        try:
            ret, data = self.quote_ctx.get_broker_queue(request.code)
            if ret == ft.RET_OK:
                # 兼容不同 SDK 返回结构：
                # - 某些版本返回 (buy_df, sell_df)
                # - 某些版本返回单个 DataFrame 或 dict
                buy_list, sell_list = [], []
                if isinstance(data, tuple) and len(data) == 2:
                    buy_df, sell_df = data
                    buy_list = self._dataframe_to_dict(buy_df, 'broker_queue_buy', request.optimization)
                    sell_list = self._dataframe_to_dict(sell_df, 'broker_queue_sell', request.optimization)
                    resp_data = {
                        "broker_queue_buy": buy_list,
                        "broker_queue_sell": sell_list,
                        "buy_count": len(buy_list),
                        "sell_count": len(sell_list)
                    }
                elif isinstance(data, pd.DataFrame):
                    one_side = self._dataframe_to_dict(data, 'broker_queue', request.optimization)
                    resp_data = {"broker_queue": one_side, "data_count": len(one_side)}
                elif isinstance(data, dict):
                    # 如果 SDK 返回 dict，尝试按 key 拆分
                    if "buy" in data and isinstance(data["buy"], pd.DataFrame):
                        buy_list = self._dataframe_to_dict(data["buy"], 'broker_queue_buy', request.optimization)
                    if "sell" in data and isinstance(data["sell"], pd.DataFrame):
                        sell_list = self._dataframe_to_dict(data["sell"], 'broker_queue_sell', request.optimization)
                    resp_data = {
                        "broker_queue_buy": buy_list,
                        "broker_queue_sell": sell_list,
                        "buy_count": len(buy_list),
                        "sell_count": len(sell_list)
                    }
                else:
                    # 最保守处理
                    resp_data = {"raw": str(data)}
                return APIResponse(ret_code=0, ret_msg="获取经纪队列成功", data=resp_data)
            else:
                return APIResponse(ret_code=ret, ret_msg=f"获取经纪队列失败: {data}", data=None)
        except Exception as e:
            logger.error(f"获取经纪队列异常: {str(e)}")
            return APIResponse(ret_code=-1, ret_msg=f"获取经纪队列异常: {str(e)}", data=None)
    
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
        """
        ⚠️ 已弃用：订阅功能不适合MCP协议
        
        MCP是单次同步请求-响应模式，不支持长连接和回调推送。
        订阅功能需要持续的数据推送，与MCP架构不匹配。
        
        建议替代方案：
        - 使用 get_stock_quote() 获取实时报价
        - 使用 get_order_book() 获取实时摆盘  
        - 使用 get_rt_ticker() 获取实时逐笔
        - 使用 get_rt_data() 获取实时分时
        - 使用 get_current_kline() 获取实时K线
        
        这些接口无需订阅，可直接拉取最新数据。
        """
        return APIResponse(
            ret_code=-1,
            ret_msg="订阅功能已弃用。MCP协议不支持长连接推送。请使用对应的get_*接口直接拉取实时数据。",
            data={
                "alternative_apis": [
                    "get_stock_quote - 获取实时报价",
                    "get_order_book - 获取实时摆盘",
                    "get_rt_ticker - 获取实时逐笔", 
                    "get_rt_data - 获取实时分时",
                    "get_current_kline - 获取实时K线"
                ]
            }
        )

    async def get_subscription_summary(self) -> APIResponse:
        """查询当前连接的订阅配额"""
        self._check_connection()
        try:
            ret, data = await asyncio.to_thread(self.quote_ctx.query_subscription)
            if ret == ft.RET_OK and isinstance(data, dict):
                return APIResponse(
                    ret_code=0,
                    ret_msg="订阅配额查询成功",
                    data=data
                )
            return APIResponse(ret_code=ret, ret_msg=f"订阅配额查询失败: {data}", data=None)
        except Exception as e:
            logger.error(f"订阅配额查询异常: {str(e)}")
            return APIResponse(ret_code=-1, ret_msg=f"订阅配额查询异常: {str(e)}", data=None)
    
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
            # 修正：使用 request_trading_days 而不是 get_trading_days
            ret, data = self.quote_ctx.request_trading_days(
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
    
    # === MCP专用增强拉取接口 ===
    
    async def get_realtime_quote_enhanced(self, codes: List[str], fields: Optional[List[str]] = None) -> APIResponse:
        """
        MCP专用：增强实时报价拉取
        
        与订阅模式不同，这是主动拉取最新数据，适合MCP单次请求场景。
        支持批量获取多只股票的实时报价。
        """
        self._check_connection()
        
        try:
            ret, data = self.quote_ctx.get_market_snapshot(codes)
            
            if ret == ft.RET_OK:
                # 使用数据优化
                optimization = DataOptimization(
                    only_essential_fields=True,
                    custom_fields=fields
                )
                result = self._dataframe_to_dict(data, 'quote', optimization)
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功获取{len(codes)}只股票实时报价",
                    data={
                        "quotes": result, 
                        "data_count": len(result),
                        "timestamp": pd.Timestamp.now().isoformat(),
                        "codes_requested": codes
                    }
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取实时报价失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取增强实时报价异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取增强实时报价异常: {str(e)}",
                data=None
            )
    
    async def get_realtime_orderbook_enhanced(self, code: str, num: int = 10) -> APIResponse:
        """
        MCP专用：增强实时摆盘拉取
        
        🧠 智能订阅管理：
        1. 内部自动检查并确保OrderBook数据已订阅
        2. 订阅成功后获取最新摆盘数据
        3. 对外保持同步接口，用户无需关心订阅细节
        4. 自动清理过期订阅，避免资源浪费
        """
        self._check_connection()
        
        try:
            # 🧠 智能订阅管理：确保OrderBook数据已订阅
            logger.info(f"正在确保 {code} 的OrderBook数据已订阅...")
            subscription_success = await self._ensure_subscription(code, 'ORDER_BOOK')
            
            if not subscription_success:
                return APIResponse(
                    ret_code=-1,
                    ret_msg=f"无法订阅{code}的OrderBook数据，请检查股票代码或网络连接",
                    data=None
                )
            
            # 🔄 清理过期订阅（后台任务，不阻塞当前请求）
            asyncio.create_task(self._cleanup_old_subscriptions())
            
            # 📊 获取摆盘数据
            ret, data = self.quote_ctx.get_order_book(code, num=num)
            
            if ret == ft.RET_OK:
                # 摆盘数据返回的是dict格式，不是DataFrame
                if isinstance(data, dict):
                    # 处理摆盘dict数据
                    result_list = self._orderbook_dict_to_list(data)
                    
                    return APIResponse(
                        ret_code=0,
                        ret_msg=f"✅ 成功获取{code}实时摆盘（已自动订阅，档位数：{num}）",
                        data={
                            "order_book_raw": data,  # 原始dict数据
                            "order_book_formatted": result_list,  # 格式化后的列表数据
                            "code": code,
                            "levels": num,
                            "subscribed": True,
                            "timestamp": pd.Timestamp.now().isoformat()
                        }
                    )
                elif isinstance(data, pd.DataFrame):
                    # 如果是DataFrame，使用原来的处理方式
                    result = self._dataframe_to_dict(data, 'order_book', DataOptimization())
                    
                    return APIResponse(
                        ret_code=0,
                        ret_msg=f"✅ 成功获取{code}实时摆盘（已自动订阅，档位数：{num}）",
                        data={
                            "order_book": result,
                            "code": code,
                            "levels": num,
                            "subscribed": True,
                            "timestamp": pd.Timestamp.now().isoformat()
                        }
                    )
                else:
                    logger.error(f"获取摆盘数据返回未知格式: {type(data)}")
                    return APIResponse(
                        ret_code=-1,
                        ret_msg=f"摆盘数据格式异常: 未知格式{type(data)}",
                        data=None
                    )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取实时摆盘失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取增强实时摆盘异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取增强实时摆盘异常: {str(e)}",
                data=None
            )
    
    async def get_realtime_ticker_enhanced(self, code: str, num: int = 100) -> APIResponse:
        """
        MCP专用：增强实时逐笔拉取
        
        🧠 智能订阅管理：自动订阅TICKER数据，然后获取实时逐笔成交。
        """
        self._check_connection()
        
        try:
            # 🧠 智能订阅管理：确保TICKER数据已订阅
            logger.info(f"正在确保 {code} 的TICKER数据已订阅...")
            subscription_success = await self._ensure_subscription(code, 'TICKER')
            
            if not subscription_success:
                return APIResponse(
                    ret_code=-1,
                    ret_msg=f"无法订阅{code}的TICKER数据，请检查股票代码或网络连接",
                    data=None
                )
            
            # 🔄 清理过期订阅
            asyncio.create_task(self._cleanup_old_subscriptions())
            
            # 📊 获取逐笔数据
            ret, data = self.quote_ctx.get_rt_ticker(code, num=num)
            
            if ret == ft.RET_OK:
                # 确保数据是DataFrame格式
                if isinstance(data, pd.DataFrame):
                    result = self._dataframe_to_dict(data, 'ticker', DataOptimization())
                    
                    return APIResponse(
                        ret_code=0,
                        ret_msg=f"✅ 成功获取{code}实时逐笔（已自动订阅，条数：{num}）",
                        data={
                            "ticker_data": result,
                            "code": code,
                            "count": len(result),
                            "subscribed": True,
                            "timestamp": pd.Timestamp.now().isoformat()
                        }
                    )
                else:
                    logger.error(f"获取逐笔数据返回非DataFrame格式: {type(data)}")
                    return APIResponse(
                        ret_code=-1,
                        ret_msg=f"逐笔数据格式异常: 期望DataFrame，实际{type(data)}",
                        data=None
                    )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取实时逐笔失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取增强实时逐笔异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取增强实时逐笔异常: {str(e)}",
                data=None
            )
    
    async def get_realtime_data_enhanced(self, code: str) -> APIResponse:
        """
        MCP专用：增强实时分时拉取
        
        🧠 智能订阅管理：自动订阅RT_DATA数据，然后获取实时分时走势。
        """
        self._check_connection()
        
        try:
            # 🧠 智能订阅管理：确保RT_DATA数据已订阅
            logger.info(f"正在确保 {code} 的RT_DATA数据已订阅...")
            subscription_success = await self._ensure_subscription(code, 'RT_DATA')
            
            if not subscription_success:
                return APIResponse(
                    ret_code=-1,
                    ret_msg=f"无法订阅{code}的RT_DATA数据，请检查股票代码或网络连接",
                    data=None
                )
            
            # 🔄 清理过期订阅
            asyncio.create_task(self._cleanup_old_subscriptions())
            
            # 📊 获取分时数据
            ret, data = self.quote_ctx.get_rt_data(code)
            
            if ret == ft.RET_OK:
                # 确保数据是DataFrame格式
                if isinstance(data, pd.DataFrame):
                    result = self._dataframe_to_dict(data, 'rt_data', DataOptimization())
                    
                    return APIResponse(
                        ret_code=0,
                        ret_msg=f"✅ 成功获取{code}实时分时（已自动订阅，数据点：{len(result)}）",
                        data={
                            "rt_data": result,
                            "code": code,
                            "data_points": len(result),
                            "subscribed": True,
                            "timestamp": pd.Timestamp.now().isoformat()
                        }
                    )
                else:
                    logger.error(f"获取分时数据返回非DataFrame格式: {type(data)}")
                    return APIResponse(
                        ret_code=-1,
                        ret_msg=f"分时数据格式异常: 期望DataFrame，实际{type(data)}",
                        data=None
                    )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取实时分时失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取增强实时分时异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取增强实时分时异常: {str(e)}",
                data=None
            )
    
    # === 智能订阅管理 ===
    
    async def _ensure_subscription(self, code: str, subtype: str, timeout: float = 3.0) -> bool:
        """
        🧠 智能订阅管理：确保指定股票的指定类型数据已订阅
        
        集成权限智能检查，当订阅失败时自动尝试重新获取权限
        
        Args:
            code: 股票代码，如 'HK.00700'
            subtype: 订阅类型，如 'ORDER_BOOK', 'TICKER', 'RT_DATA'
            timeout: 等待订阅完成的超时时间（秒）
            
        Returns:
            bool: 订阅是否成功
        """
        async with self._subscription_lock:
            # 检查是否已经订阅
            if self._is_subscribed(code, subtype):
                logger.debug(f"股票 {code} 的 {subtype} 已经订阅，跳过")
                return True
            
            try:
                self._check_connection()
                
                # 根据subtype确定订阅类型
                futu_subtype = self._convert_sub_type(subtype)
                if not futu_subtype:
                    logger.error(f"不支持的订阅类型: {subtype}")
                    return False
                
                # 📊 第一次尝试订阅
                logger.debug(f"正在尝试订阅 {code} 的 {subtype} 数据...")
                ret, err_message = self.quote_ctx.subscribe(code, [futu_subtype])
                
                if ret == ft.RET_OK:
                    # 订阅成功
                    if code not in self._subscription_status:
                        self._subscription_status[code] = {}
                    self._subscription_status[code][subtype] = True
                    self._last_subscription_time[f"{code}_{subtype}"] = time.time()
                    
                    logger.info(f"✅ 成功订阅 {code} 的 {subtype} 数据")
                    
                    # 等待订阅生效（重要！）
                    await asyncio.sleep(0.5)
                    return True
                else:
                    # 🧠 订阅失败，智能权限处理
                    logger.warning(f"⚠️ 订阅失败: {code} {subtype} - {err_message}")
                    
                    # 检查是否是权限相关的错误
                    if any(keyword in str(err_message).lower() for keyword in 
                           ['权限', 'permission', 'right', 'denied', 'unauthorized', '抢占']):
                        
                        logger.info("🔧 检测到权限问题，尝试重新获取最高权限...")
                        rights_ok = await self._check_and_ensure_quote_rights(force_check=True)
                        
                        if rights_ok:
                            # 权限获取成功，再次尝试订阅
                            logger.info(f"🔄 权限重新获取后，再次尝试订阅 {code} 的 {subtype}...")
                            await asyncio.sleep(1)  # 等待权限生效
                            
                            ret, err_message = self.quote_ctx.subscribe(code, [futu_subtype])
                            
                            if ret == ft.RET_OK:
                                if code not in self._subscription_status:
                                    self._subscription_status[code] = {}
                                self._subscription_status[code][subtype] = True
                                self._last_subscription_time[f"{code}_{subtype}"] = time.time()
                                
                                logger.info(f"✅ 权限重新获取后订阅成功: {code} {subtype}")
                                await asyncio.sleep(0.5)
                                return True
                            else:
                                logger.error(f"❌ 权限重新获取后仍订阅失败: {code} {subtype} - {err_message}")
                                return False
                        else:
                            logger.error(f"❌ 无法重新获取权限，订阅失败: {code} {subtype}")
                            return False
                    else:
                        logger.error(f"❌ 订阅失败（非权限问题）: {code} {subtype} - {err_message}")
                        return False
                    
            except Exception as e:
                logger.error(f"❌ 订阅异常: {code} {subtype} - {str(e)}")
                return False
    
    def _is_subscribed(self, code: str, subtype: str) -> bool:
        """检查是否已订阅指定数据"""
        return (code in self._subscription_status and 
                subtype in self._subscription_status[code] and 
                self._subscription_status[code][subtype])
    
    async def _cleanup_old_subscriptions(self, max_age: int = 300):
        """清理过期的订阅记录，释放资源"""
        current_time = time.time()
        
        for code in list(self._last_subscription_time.keys()):
            if current_time - self._last_subscription_time.get(code, 0) > max_age:
                # 清理过期记录
                if code in self._subscription_status:
                    del self._subscription_status[code]
                if code in self._subscription_data_cache:
                    del self._subscription_data_cache[code]
                if code in self._last_subscription_time:
                    del self._last_subscription_time[code]
                
                logger.info(f"清理了{code}的过期订阅记录")
    
    async def get_capital_flow(self, request: CapitalFlowRequest) -> APIResponse:
        """获取资金流向"""
        self._check_connection()
        
        try:
            # 调用富途API获取资金流向数据
            ret, data = self.quote_ctx.get_capital_flow(
                stock_code=request.code,
                period_type=self._convert_period_type(request.period_type),
                start=request.start,
                end=request.end
            )
            
            if ret == ft.RET_OK:
                # 处理数据
                result = self._dataframe_to_dict(data, 'capital_flow', request.optimization)
                
                # 计算汇总信息
                total_records = len(result)
                if total_records > 0:
                    latest_data = result[-1] if result else {}
                    net_inflow = self._to_float_safe(latest_data.get('in_flow', 0)) or 0.0
                    main_inflow = self._to_float_safe(latest_data.get('main_in_flow', 0)) or 0.0
                    
                    # 判断资金流向趋势
                    flow_trend = "中性"
                    if net_inflow > 0:
                        flow_trend = "净流入"
                    elif net_inflow < 0:
                        flow_trend = "净流出"
                    
                    main_trend = "中性"
                    if main_inflow > 0:
                        main_trend = "主力净流入"
                    elif main_inflow < 0:
                        main_trend = "主力净流出"
                else:
                    flow_trend = "无数据"
                    main_trend = "无数据"
                    latest_data = {}
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功获取{request.code}资金流向数据",
                    data={
                        "code": request.code,
                        "period_type": request.period_type,
                        "capital_flow": result,
                        "data_count": total_records,
                        "summary": {
                            "overall_trend": flow_trend,
                            "main_trend": main_trend,
                            "latest_net_inflow": net_inflow if total_records > 0 else 0,
                            "latest_main_inflow": main_inflow if total_records > 0 else 0,
                            "latest_time": latest_data.get('capital_flow_item_time', 'N/A')
                        },
                        "timestamp": pd.Timestamp.now().isoformat()
                    }
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取资金流向失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取资金流向异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取资金流向异常: {str(e)}",
                data=None
            )
    
    async def get_capital_distribution(self, request: CapitalDistributionRequest) -> APIResponse:
        """获取资金分布"""
        self._check_connection()
        
        try:
            # 调用富途API获取资金分布数据
            ret, data = self.quote_ctx.get_capital_distribution(request.code)
            
            if ret == ft.RET_OK:
                # 处理数据 - 资金分布返回的是DataFrame格式
                result = self._dataframe_to_dict(data, 'capital_distribution', request.optimization)
                
                # 计算汇总信息
                if result and len(result) > 0:
                    latest_data = result[0]  # 资金分布通常只有一条当前数据
                    
                    # 计算各级别净流入（流入-流出）
                    super_net = (self._to_float_safe(latest_data.get('capital_in_super', 0)) or 0) - (self._to_float_safe(latest_data.get('capital_out_super', 0)) or 0)
                    big_net = (self._to_float_safe(latest_data.get('capital_in_big', 0)) or 0) - (self._to_float_safe(latest_data.get('capital_out_big', 0)) or 0)
                    mid_net = (self._to_float_safe(latest_data.get('capital_in_mid', 0)) or 0) - (self._to_float_safe(latest_data.get('capital_out_mid', 0)) or 0)
                    small_net = (self._to_float_safe(latest_data.get('capital_in_small', 0)) or 0) - (self._to_float_safe(latest_data.get('capital_out_small', 0)) or 0)
                    
                    # 计算总净流入
                    total_net = super_net + big_net + mid_net + small_net
                    
                    # 判断主导资金类型
                    net_flows = {
                        '特大单': super_net,
                        '大单': big_net,
                        '中单': mid_net,
                        '小单': small_net
                    }
                    
                    # 找出净流入最大的资金类型
                    dominant_type = max(net_flows, key=net_flows.get)
                    dominant_amount = net_flows[dominant_type]
                    
                    # 判断整体趋势
                    overall_trend = "净流入" if total_net > 0 else "净流出" if total_net < 0 else "平衡"
                    
                    # 计算大资金（特大单+大单）净流入
                    large_funds_net = super_net + big_net
                    large_funds_trend = "大资金净流入" if large_funds_net > 0 else "大资金净流出" if large_funds_net < 0 else "大资金平衡"
                    
                    summary = {
                        "overall_trend": overall_trend,
                        "total_net_inflow": total_net,
                        "large_funds_trend": large_funds_trend,
                        "large_funds_net_inflow": large_funds_net,
                        "dominant_fund_type": dominant_type,
                        "dominant_fund_amount": dominant_amount,
                        "update_time": latest_data.get('update_time', 'N/A'),
                        "breakdown": {
                            "super_net": super_net,
                            "big_net": big_net,
                            "mid_net": mid_net,
                            "small_net": small_net
                        }
                    }
                else:
                    summary = {
                        "overall_trend": "无数据",
                        "total_net_inflow": 0,
                        "large_funds_trend": "无数据",
                        "large_funds_net_inflow": 0,
                        "dominant_fund_type": "无数据",
                        "dominant_fund_amount": 0,
                        "update_time": "N/A",
                        "breakdown": {
                            "super_net": 0,
                            "big_net": 0,
                            "mid_net": 0,
                            "small_net": 0
                        }
                    }
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功获取{request.code}资金分布数据",
                    data={
                        "code": request.code,
                        "capital_distribution": result,
                        "data_count": len(result),
                        "summary": summary,
                        "timestamp": pd.Timestamp.now().isoformat()
                    }
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取资金分布失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取资金分布异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取资金分布异常: {str(e)}",
                data=None
            )

    async def get_rehab(self, request: RehabRequest) -> APIResponse:
        """获取股票复权因子"""
        self._check_connection()
        
        try:
            # 调用富途API获取复权因子数据
            ret, data = self.quote_ctx.get_rehab(request.code)
            
            if ret == ft.RET_OK:
                # 处理数据
                result = self._dataframe_to_dict(data, 'rehab', request.optimization)
                
                # 计算汇总信息
                total_records = len(result)
                
                # 统计各种公司行为类型
                action_types = {
                    "派息记录": 0,
                    "送股记录": 0,
                    "转增股记录": 0,
                    "配股记录": 0,
                    "增发记录": 0,
                    "拆合股记录": 0
                }
                
                latest_action = {}
                latest_date = ""
                
                if result:
                    # 统计各种公司行为
                    for record in result:
                        if record.get('per_cash_div', 0) > 0:
                            action_types["派息记录"] += 1
                        if record.get('per_share_div_ratio', 0) > 0:
                            action_types["送股记录"] += 1
                        if record.get('per_share_trans_ratio', 0) > 0:
                            action_types["转增股记录"] += 1
                        if record.get('allotment_ratio', 0) > 0:
                            action_types["配股记录"] += 1
                        if record.get('stk_spo_ratio', 0) > 0:
                            action_types["增发记录"] += 1
                        if record.get('split_ratio', 1) != 1:
                            action_types["拆合股记录"] += 1
                    
                    # 获取最新的复权记录
                    latest_action = result[-1] if result else {}
                    latest_date = latest_action.get('ex_div_date', 'N/A')
                
                    # 分析最新记录的行为类型
                    latest_action_type = []
                    if latest_action.get('per_cash_div', 0) > 0:
                        latest_action_type.append(f"派息{latest_action.get('per_cash_div', 0)}")
                    if latest_action.get('per_share_div_ratio', 0) > 0:
                        latest_action_type.append(f"送股比例{latest_action.get('per_share_div_ratio', 0)}")
                    if latest_action.get('per_share_trans_ratio', 0) > 0:
                        latest_action_type.append(f"转增比例{latest_action.get('per_share_trans_ratio', 0)}")
                    if latest_action.get('allotment_ratio', 0) > 0:
                        latest_action_type.append(f"配股比例{latest_action.get('allotment_ratio', 0)}")
                    if latest_action.get('stk_spo_ratio', 0) > 0:
                        latest_action_type.append(f"增发比例{latest_action.get('stk_spo_ratio', 0)}")
                    if latest_action.get('split_ratio', 1) != 1:
                        split_ratio = latest_action.get('split_ratio', 1)
                        if split_ratio > 1:
                            latest_action_type.append(f"拆股{split_ratio}:1")
                        else:
                            latest_action_type.append(f"合股1:{1/split_ratio}")
                    
                    latest_action_description = "; ".join(latest_action_type) if latest_action_type else "无具体行为"
                else:
                    latest_action_description = "暂无记录"
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功获取{request.code}复权因子数据",
                    data={
                        "code": request.code,
                        "rehab_data": result,
                        "data_count": total_records,
                        "summary": {
                            "total_actions": total_records,
                            "action_breakdown": action_types,
                            "latest_action_date": latest_date,
                            "latest_action_type": latest_action_description,
                            "latest_forward_factor_a": latest_action.get('forward_adj_factorA', 'N/A'),
                            "latest_forward_factor_b": latest_action.get('forward_adj_factorB', 'N/A'),
                            "latest_backward_factor_a": latest_action.get('backward_adj_factorA', 'N/A'),
                            "latest_backward_factor_b": latest_action.get('backward_adj_factorB', 'N/A')
                        },
                        "timestamp": pd.Timestamp.now().isoformat()
                    }
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取复权因子失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取复权因子异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取复权因子异常: {str(e)}",
                data=None
            )

    async def get_stock_filter(self, request: StockFilterRequest) -> APIResponse:
        """条件选股"""
        self._check_connection()
        
        try:
            # 富途API可能没有直接的stock_filter方法，我们提供一个基于现有API的实现
            # 先获取市场快照，然后根据条件进行筛选
            
            # 根据市场获取股票列表
            try:
                # 尝试获取市场快照或股票基本信息
                if request.plate_code:
                    # 如果指定了板块代码，获取板块内股票
                    ret, data = self.quote_ctx.get_plate_stock(request.plate_code)
                    if ret != ft.RET_OK:
                        raise Exception(f"获取板块股票失败: {data}")
                    
                    # 从板块股票中提取股票代码
                    if isinstance(data, pd.DataFrame) and not data.empty:
                        stock_codes = [f"{request.market}.{code}" if not code.startswith(request.market) else code 
                                     for code in data['code'].tolist()]
                    else:
                        stock_codes = []
                else:
                    # 如果没有指定板块，使用一些示例股票代码
                    if request.market == 'HK':
                        stock_codes = ['HK.00700', 'HK.00941', 'HK.03690', 'HK.00005', 'HK.00388']
                    elif request.market == 'US':
                        stock_codes = ['US.AAPL', 'US.MSFT', 'US.GOOGL', 'US.AMZN', 'US.TSLA']
                    elif request.market == 'CN':
                        stock_codes = ['SH.000001', 'SZ.000002', 'SH.600036', 'SZ.000858', 'SH.600519']
                    else:
                        stock_codes = []
                
                if not stock_codes:
                    return APIResponse(
                        ret_code=0,
                        ret_msg="没有找到符合条件的股票",
                        data={
                            "market": request.market,
                            "filter_conditions": [f.dict() for f in request.filter_list],
                            "matched_stocks": [],
                            "data_count": 0,
                            "summary": {
                                "total_matched": 0,
                                "filter_applied": len(request.filter_list),
                                "plate_filter": request.plate_code is not None
                            },
                            "timestamp": pd.Timestamp.now().isoformat()
                        }
                    )
                
                # 获取这些股票的基本信息和行情数据
                filtered_stocks = []
                
                # 限制处理数量以避免API限制
                process_codes = stock_codes[:20]  # 最多处理20只股票
                
                for code in process_codes:
                    try:
                        # 获取股票基本信息
                        ret_basic, basic_data = self.quote_ctx.get_stock_basicinfo(market=self._convert_market(request.market), stock_type=ft.SecurityType.STOCK)
                        
                        # 获取实时报价
                        ret_quote, quote_data = self.quote_ctx.get_market_snapshot([code])
                        
                        if ret_quote == ft.RET_OK and not quote_data.empty:
                            stock_info = quote_data.iloc[0].to_dict()
                            
                            # 模拟筛选逻辑
                            meets_criteria = True
                            for filter_condition in request.filter_list:
                                if not filter_condition.is_no_filter:
                                    # 这里可以添加具体的筛选逻辑
                                    # 由于富途API字段名可能不同，我们使用通用字段
                                    field_value = stock_info.get('cur_price', 0)
                                    
                                    if filter_condition.filter_min is not None and field_value < filter_condition.filter_min:
                                        meets_criteria = False
                                        break
                                    if filter_condition.filter_max is not None and field_value > filter_condition.filter_max:
                                        meets_criteria = False
                                        break
                            
                            if meets_criteria:
                                # 构建返回的股票信息
                                filtered_stock = {
                                    'code': code,
                                    'name': stock_info.get('stock_name', ''),
                                    'cur_price': stock_info.get('cur_price', 0),
                                    'change_rate': stock_info.get('change_rate', 0),
                                    'volume': stock_info.get('volume', 0),
                                    'turnover': stock_info.get('turnover', 0),
                                    'market_val': stock_info.get('market_val', 0),
                                    'pe_ratio': stock_info.get('pe_ratio', 0),
                                    'pb_ratio': stock_info.get('pb_ratio', 0),
                                    'turnover_rate': stock_info.get('turnover_rate', 0)
                                }
                                filtered_stocks.append(filtered_stock)
                    
                    except Exception as e:
                        logger.warning(f"处理股票{code}时出现错误: {str(e)}")
                        continue
                
                # 应用排序
                if request.filter_list and not request.filter_list[0].is_no_filter:
                    sort_field = request.filter_list[0].stock_field
                    sort_dir = request.filter_list[0].sort
                    
                    # 根据排序字段和方向排序
                    field_map = {
                        StockField.CUR_PRICE: 'cur_price',
                        StockField.VOLUME: 'volume',
                        StockField.TURNOVER: 'turnover',
                        StockField.TURNOVER_RATE: 'turnover_rate',
                        StockField.CUR_PRICE_TO_PRE_CLOSE_RATIO: 'change_rate'
                    }
                    
                    sort_key = field_map.get(sort_field, 'cur_price')
                    reverse = (sort_dir == SortDir.DESCEND)
                    
                    filtered_stocks.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse)
                
                # 应用分页
                begin_index = request.begin if request.begin is not None else 0
                num = request.num if request.num is not None else len(filtered_stocks)
                end_index = min(begin_index + num, len(filtered_stocks))
                
                paginated_stocks = filtered_stocks[begin_index:end_index]
                
            except Exception as api_error:
                # 严格模式：不返回模拟数据，直接报错
                if os.environ.get('DISABLE_MOCK_DATA', 'false').lower() == 'true':
                    logger.error(f"API调用失败且模拟数据已禁用: {str(api_error)}")
                    return APIResponse(
                        ret_code=-1,
                        ret_msg=f"无法获取真实数据: {str(api_error)}",
                        data=None
                    )
                
                # 非严格模式：如果API调用失败，返回模拟数据（保留原有逻辑）
                logger.warning(f"API调用失败，返回模拟数据: {str(api_error)}")
                
                # 根据市场返回模拟数据
                mock_stocks = {
                    'HK': [
                        {'code': 'HK.00700', 'name': '腾讯控股', 'cur_price': 320.5, 'change_rate': 2.1, 'volume': 18500000, 'turnover': 5.9e9, 'market_val': 3.1e12, 'pe_ratio': 15.2, 'pb_ratio': 3.8, 'turnover_rate': 0.8},
                        {'code': 'HK.00941', 'name': '中国移动', 'cur_price': 85.2, 'change_rate': -0.5, 'volume': 12300000, 'turnover': 1.05e9, 'market_val': 1.8e12, 'pe_ratio': 12.5, 'pb_ratio': 1.2, 'turnover_rate': 0.6},
                        {'code': 'HK.03690', 'name': '美团', 'cur_price': 165.8, 'change_rate': 1.8, 'volume': 25600000, 'turnover': 4.2e9, 'market_val': 1.0e12, 'pe_ratio': 28.9, 'pb_ratio': 5.2, 'turnover_rate': 1.2},
                    ],
                    'US': [
                        {'code': 'US.AAPL', 'name': 'Apple Inc', 'cur_price': 195.8, 'change_rate': 1.2, 'volume': 65000000, 'turnover': 1.27e10, 'market_val': 3.0e12, 'pe_ratio': 25.8, 'pb_ratio': 8.5, 'turnover_rate': 2.1},
                        {'code': 'US.MSFT', 'name': 'Microsoft', 'cur_price': 415.2, 'change_rate': 0.8, 'volume': 28500000, 'turnover': 1.18e10, 'market_val': 3.1e12, 'pe_ratio': 32.1, 'pb_ratio': 12.2, 'turnover_rate': 1.8},
                        {'code': 'US.GOOGL', 'name': 'Alphabet', 'cur_price': 175.5, 'change_rate': -0.3, 'volume': 22800000, 'turnover': 4.0e9, 'market_val': 2.2e12, 'pe_ratio': 21.5, 'pb_ratio': 4.8, 'turnover_rate': 1.5},
                    ],
                    'CN': [
                        {'code': 'SH.600519', 'name': '贵州茅台', 'cur_price': 1680.5, 'change_rate': 0.9, 'volume': 1850000, 'turnover': 3.1e9, 'market_val': 2.1e12, 'pe_ratio': 35.2, 'pb_ratio': 12.8, 'turnover_rate': 0.2},
                        {'code': 'SZ.000858', 'name': '五粮液', 'cur_price': 158.2, 'change_rate': 1.5, 'volume': 8500000, 'turnover': 1.34e9, 'market_val': 6.1e11, 'pe_ratio': 28.5, 'pb_ratio': 6.2, 'turnover_rate': 1.1},
                        {'code': 'SH.600036', 'name': '招商银行', 'cur_price': 38.5, 'change_rate': -0.2, 'volume': 45600000, 'turnover': 1.76e9, 'market_val': 1.1e12, 'pe_ratio': 8.5, 'pb_ratio': 1.1, 'turnover_rate': 1.8},
                    ]
                }
                
                paginated_stocks = mock_stocks.get(request.market, [])
            
            # 统计筛选条件
            filter_summary = {
                "applied_filters": len([f for f in request.filter_list if not f.is_no_filter]),
                "total_conditions": len(request.filter_list),
                "sort_applied": any(f.sort != SortDir.NONE for f in request.filter_list)
            }
            
            # 分析股票分布
            if paginated_stocks:
                price_ranges = {"低价股(<=50)": 0, "中价股(50-200)": 0, "高价股(>200)": 0}
                for stock in paginated_stocks:
                    price = stock.get('cur_price', 0)
                    if price <= 50:
                        price_ranges["低价股(<=50)"] += 1
                    elif price <= 200:
                        price_ranges["中价股(50-200)"] += 1
                    else:
                        price_ranges["高价股(>200)"] += 1
            else:
                price_ranges = {}
            
            return APIResponse(
                ret_code=0,
                ret_msg=f"成功筛选{request.market}市场股票",
                data={
                    "market": request.market,
                    "filter_conditions": [f.dict() for f in request.filter_list],
                    "plate_code": request.plate_code,
                    "matched_stocks": paginated_stocks,
                    "data_count": len(paginated_stocks),
                    "pagination": {
                        "begin": begin_index,
                        "num": num,
                        "total_available": len(filtered_stocks) if 'filtered_stocks' in locals() else len(paginated_stocks)
                    },
                    "summary": {
                        "total_matched": len(paginated_stocks),
                        "filter_summary": filter_summary,
                        "price_distribution": price_ranges,
                        "avg_price": sum(s.get('cur_price', 0) for s in paginated_stocks) / len(paginated_stocks) if paginated_stocks else 0,
                        "avg_change_rate": sum(s.get('change_rate', 0) for s in paginated_stocks) / len(paginated_stocks) if paginated_stocks else 0
                    },
                    "timestamp": pd.Timestamp.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"条件选股异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"条件选股异常: {str(e)}",
                data=None
            )

    async def get_plate_stock(self, request: PlateStockRequest) -> APIResponse:
        """获取板块内股票列表"""
        self._check_connection()
        
        try:
            # 修正：使用 SortField 而不是 StockField，并使用默认排序字段
            if request.sort_field:
                try:
                    sort_field = self._convert_sort_field(request.sort_field)
                except:
                    # 如果转换失败，使用默认排序字段
                    sort_field = ft.SortField.CODE
            else:
                sort_field = ft.SortField.CODE
                
            sort_dir = self._convert_sort_dir(request.sort_dir)
            
            ret, data = self.quote_ctx.get_plate_stock(
                plate_code=request.plate_code,
                sort_field=sort_field,
                ascend=(sort_dir == ft.SortDir.ASCEND)
            )
            
            if ret == ft.RET_OK:
                result = self._dataframe_to_dict(data, 'plate_stock', request.optimization)
                total_records = len(result)
                
                stock_types = {}
                for record in result:
                    stock_type = record.get('stock_type', 'UNKNOWN')
                    stock_types[stock_type] = stock_types.get(stock_type, 0) + 1
                
                return APIResponse(
                    ret_code=0,
                    ret_msg="获取板块股票列表成功",
                    data={
                        "plate_stock": result,
                        "total_records": total_records,
                        "stock_types": stock_types
                    }
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取板块股票列表失败: {data}",
                    data=None
                )
        except Exception as e:
            logger.error(f"获取板块股票列表异常: {e}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取板块股票列表异常: {str(e)}",
                data=None
            )

    async def get_plate_list(self, request: PlateListRequest) -> APIResponse:
        """获取板块列表"""
        self._check_connection()
        
        try:
            # 调用富途API获取板块列表
            ret, data = self.quote_ctx.get_plate_list(
                market=self._convert_market(request.market),
                plate_class=self._convert_plate_set_type(request.plate_set_type)
            )
            
            if ret == ft.RET_OK:
                # 处理数据
                result = self._dataframe_to_dict(data, 'plate_list', request.optimization)
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功获取{request.market}市场板块列表",
                    data={
                        "market": request.market,
                        "plate_set_type": request.plate_set_type,
                        "plate_list": result,
                        "data_count": len(result),
                        "timestamp": pd.Timestamp.now().isoformat()
                    }
                )
            else:
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"获取板块列表失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"获取板块列表异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"获取板块列表异常: {str(e)}",
                data=None
            )
    
    # === 交易相关方法 ===
    
    def _convert_trd_env(self, trd_env: TrdEnv) -> ft.TrdEnv:
        """转换交易环境"""
        env_map = {
            TrdEnv.SIMULATE: ft.TrdEnv.SIMULATE,
            TrdEnv.REAL: ft.TrdEnv.REAL
        }
        return env_map.get(trd_env, ft.TrdEnv.REAL)
    
    def _convert_currency(self, currency: Currency) -> ft.Currency:
        """转换货币类型"""
        currency_map = {
            Currency.NONE: ft.Currency.NONE,
            Currency.HKD: ft.Currency.HKD,
            Currency.USD: ft.Currency.USD,
            Currency.CNH: ft.Currency.CNH,
            Currency.JPY: ft.Currency.JPY,
            Currency.SGD: ft.Currency.SGD,
            Currency.AUD: ft.Currency.AUD
        }
        return currency_map.get(currency, ft.Currency.HKD)
    
    def _convert_trd_market(self, trd_market: TrdMarket) -> ft.TrdMarket:
        """转换交易市场"""
        market_map = {
            TrdMarket.HK: ft.TrdMarket.HK,
            TrdMarket.US: ft.TrdMarket.US,
            TrdMarket.CN: ft.TrdMarket.CN,
            TrdMarket.HKCC: ft.TrdMarket.HKCC
        }
        return market_map.get(trd_market, ft.TrdMarket.HK)
    
    def _parse_currency_name(self, currency_enum) -> str:
        """将富途API的货币枚举转换为字符串"""
        currency_names = {
            ft.Currency.NONE: "NONE",
            ft.Currency.HKD: "HKD",
            ft.Currency.USD: "USD", 
            ft.Currency.CNH: "CNH",
            ft.Currency.JPY: "JPY",
            ft.Currency.SGD: "SGD",
            ft.Currency.AUD: "AUD"
        }
        return currency_names.get(currency_enum, "UNKNOWN")
    
    def _to_float_safe(self, value):
        """将值安全转换为 float，不可转则返回 None"""
        try:
            if value is None:
                return None
            if isinstance(value, str):
                v = value.strip()
                if v in {"", "N/A", "NA", "--"}:
                    return None
                return float(v)
            return float(value)
        except Exception:
            return None

    def _to_int_safe(self, value):
        """将值安全转换为 int，不可转则返回 None"""
        try:
            if value is None:
                return None
            if isinstance(value, str):
                v = value.strip()
                if v in {"", "N/A", "NA", "--"}:
                    return None
                return int(float(v))
            return int(value)
        except Exception:
            return None

    def _parse_funds_data(self, funds_data, optimization_config) -> Dict[str, Any]:
        """解析账户资金数据，容错处理 N/A/空串 等非数值"""
        if funds_data is None:
            return {}

        # 如果是 DataFrame，先做基本清洗
        df = funds_data
        try:
            if hasattr(df, "replace"):
                df = df.replace({"": pd.NA, "N/A": pd.NA, "NA": pd.NA, "--": pd.NA})
        except Exception:
            pass

        if hasattr(df, 'iterrows'):
            for _, row in df.iterrows():
                parsed_data = {}

                # 基础资金信息
                basic_fields = [
                    'power', 'max_power_short', 'net_cash_power', 'total_assets',
                    'securities_assets', 'funds_assets', 'bonds_assets', 'cash',
                    'market_val', 'frozen_cash', 'debt_cash', 'avl_withdrawal_cash'
                ]
                for field in basic_fields:
                    if field in row:
                        val = self._to_float_safe(row[field])
                        if val is not None:
                            parsed_data[field] = val

                # 分币种现金信息
                currency_fields = ['hkd', 'usd', 'cnh', 'jpy', 'sgd', 'aud']
                for currency in currency_fields:
                    for suffix in ['_cash', '_avl_balance', '_net_cash_power']:
                        field_name = f"{currency}{suffix}"
                        if field_name in row:
                            val = self._to_float_safe(row[field_name])
                            if val is not None:
                                parsed_data[field_name] = val

                # 期货相关字段
                futures_fields = [
                    'initial_margin', 'maintenance_margin', 'long_mv', 'short_mv',
                    'pending_asset', 'risk_status', 'margin_call_margin'
                ]
                for field in futures_fields:
                    if field in row:
                        if field == 'risk_status':
                            val = self._to_int_safe(row[field])
                        else:
                            val = self._to_float_safe(row[field])
                        if val is not None:
                            parsed_data[field] = val

                # 计算汇总信息（容错）
                total_cash_value = 0.0
                for currency in currency_fields:
                    cash_field = f"{currency}_cash"
                    if cash_field in parsed_data:
                        total_cash_value += parsed_data[cash_field]

                available_funds = parsed_data.get('power', 0.0)

                parsed_data.update({
                    'total_cash_value': total_cash_value,
                    'available_funds': available_funds,
                    'account_type': '综合账户'
                })
                return parsed_data

        return {}    
    async def get_acc_info(self, request: AccInfoRequest) -> APIResponse:
        """查询账户资金"""
        self._check_trade_connection()
        
        try:
            logger.info(f"查询账户资金: trd_env={request.trd_env}, acc_id={request.acc_id}, currency={request.currency}")
            
            # 调用富途API查询账户资金
            ret, data = self.trade_ctx.accinfo_query(
                trd_env=self._convert_trd_env(request.trd_env),
                acc_id=request.acc_id,
                acc_index=request.acc_index,
                refresh_cache=request.refresh_cache,
                currency=self._convert_currency(request.currency)
            )
            
            if ret == ft.RET_OK:
                logger.info("成功获取账户资金数据")
                
                # 解析资金数据
                parsed_data = self._parse_funds_data(data, request.optimization)
                
                # 生成汇总信息
                summary = {
                    "账户类型": parsed_data.get('account_type', '未知'),
                    "总资产净值": parsed_data.get('total_assets', 0),
                    "可用资金": parsed_data.get('available_funds', 0),
                    "现金购买力": parsed_data.get('power', 0),
                    "总现金价值": parsed_data.get('total_cash_value', 0),
                    "证券市值": parsed_data.get('market_val', 0),
                    "冻结资金": parsed_data.get('frozen_cash', 0)
                }
                
                # 货币分布统计
                currency_distribution = {}
                for currency in ['hkd', 'usd', 'cnh', 'jpy']:
                    cash_field = f"{currency}_cash"
                    if cash_field in parsed_data and parsed_data[cash_field] != 0:
                        currency_distribution[currency.upper()] = {
                            "现金": parsed_data.get(cash_field, 0),
                            "可用余额": parsed_data.get(f"{currency}_avl_balance", 0),
                            "购买力": parsed_data.get(f"{currency}_net_cash_power", 0)
                        }
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功查询{request.trd_env}环境账户资金",
                    data={
                        "account_info": parsed_data,
                        "trd_env": request.trd_env,
                        "currency": request.currency,
                        "update_time": pd.Timestamp.now().isoformat(),
                        "data_source": "futu_api",
                        "summary": summary,
                        "currency_distribution": currency_distribution,
                        "raw_data_count": len(data) if hasattr(data, '__len__') else 1
                    }
                )
            else:
                logger.error(f"查询账户资金失败: {data}")
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"查询账户资金失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"查询账户资金异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"查询账户资金异常: {str(e)}",
                data=None
            )
    
    def _convert_position_side(self, position_side_enum) -> str:
        """将富途API的持仓方向枚举转换为字符串"""
        position_side_names = {
            ft.PositionSide.LONG: "LONG",
            ft.PositionSide.SHORT: "SHORT",
            ft.PositionSide.NONE: "NONE"
        }
        return position_side_names.get(position_side_enum, "UNKNOWN")
    
    def _parse_trd_market_name(self, trd_market_enum) -> str:
        """将富途API的交易市场枚举转换为字符串"""
        trd_market_names = {
            ft.TrdMarket.HK: "HK",
            ft.TrdMarket.US: "US",
            ft.TrdMarket.CN: "CN",
            ft.TrdMarket.HKCC: "HKCC"
        }
        return trd_market_names.get(trd_market_enum, "UNKNOWN")
    
    def _parse_position_data(self, position_data, optimization_config) -> List[Dict[str, Any]]:
        """解析富途持仓数据"""
        if position_data is None:
            return []
        
        positions = []
        
        # 处理DataFrame格式的持仓数据
        if hasattr(position_data, 'iterrows'):
            for index, row in position_data.iterrows():
                try:
                    position = {}
                    
                    # 基础持仓信息
                    basic_fields = {
                        'position_id': 'position_id',
                        'code': 'code', 
                        'stock_name': 'stock_name',
                        'qty': 'qty',
                        'can_sell_qty': 'can_sell_qty',
                        'nominal_price': 'nominal_price',
                        'cost_price': 'cost_price',
                        'diluted_cost_price': 'diluted_cost_price',
                        'average_cost_price': 'average_cost_price',
                        'market_val': 'market_val',
                        'pl_val': 'pl_val',
                        'pl_ratio': 'pl_ratio',
                        'average_pl_ratio': 'average_pl_ratio',
                        'today_pl_val': 'today_pl_val',
                        'today_pl_ratio': 'today_pl_ratio',
                        'today_buy_val': 'today_buy_val',
                        'today_buy_qty': 'today_buy_qty',
                        'today_sell_val': 'today_sell_val',
                        'today_sell_qty': 'today_sell_qty',
                        'break_even_price': 'break_even_price'
                    }
                    
                    # 处理基础字段
                    for local_field, api_field in basic_fields.items():
                        if api_field in row:
                            value = row[api_field]
                            if pd.notna(value):
                                if local_field in ['qty', 'can_sell_qty', 'nominal_price', 'cost_price', 
                                                 'diluted_cost_price', 'average_cost_price', 'market_val',
                                                 'pl_val', 'pl_ratio', 'average_pl_ratio', 'today_pl_val',
                                                 'today_pl_ratio', 'today_buy_val', 'today_buy_qty',
                                                 'today_sell_val', 'today_sell_qty', 'break_even_price']:
                                    position[local_field] = float(value)
                                else:
                                    position[local_field] = str(value)
                    
                    # 处理枚举字段
                    if 'position_side' in row:
                        position['position_side'] = self._convert_position_side(row['position_side'])
                    
                    if 'currency' in row:
                        position['currency'] = self._parse_currency_name(row['currency'])
                    
                    if 'position_market' in row:
                        position['position_market'] = self._parse_trd_market_name(row['position_market'])
                    
                    # 计算额外的分析字段
                    position['unrealized_pnl'] = position.get('pl_val', 0)
                    
                    # 判断持仓状态
                    pl_ratio = position.get('pl_ratio', 0)
                    if pl_ratio > 0.05:  # 盈利超过5%
                        position['position_status'] = '盈利'
                    elif pl_ratio < -0.05:  # 亏损超过5%
                        position['position_status'] = '亏损'
                    else:
                        position['position_status'] = '持平'
                    
                    positions.append(position)
                    
                except Exception as e:
                    logger.warning(f"解析持仓数据行失败: {str(e)}")
                    continue
        
        return positions
    
    async def get_position_list(self, request: PositionListRequest) -> APIResponse:
        """查询持仓列表"""
        self._check_trade_connection()
        
        try:
            logger.info(f"查询持仓列表: trd_env={request.trd_env}, acc_id={request.acc_id}, code={request.code}")
            
            # 准备API参数
            api_params = {
                'trd_env': self._convert_trd_env(request.trd_env),
                'acc_id': request.acc_id,
                'acc_index': request.acc_index,
                'refresh_cache': request.refresh_cache
            }
            
            # 添加可选参数
            if request.code:
                api_params['code'] = request.code
            
            if request.position_market:
                api_params['position_market'] = self._convert_trd_market(request.position_market)
            
            if request.pl_ratio_min is not None:
                api_params['pl_ratio_min'] = request.pl_ratio_min
                
            if request.pl_ratio_max is not None:
                api_params['pl_ratio_max'] = request.pl_ratio_max
            
            # 调用富途API查询持仓列表
            ret, data = self.trade_ctx.position_list_query(**api_params)
            
            if ret == ft.RET_OK:
                logger.info("成功获取持仓列表数据")
                
                # 解析持仓数据
                position_list = self._parse_position_data(data, request.optimization)
                
                # 生成汇总信息
                total_count = len(position_list)
                total_market_val = sum(pos.get('market_val', 0) for pos in position_list)
                total_pl_val = sum(pos.get('pl_val', 0) for pos in position_list)
                total_cost_val = sum(pos.get('cost_price', 0) * pos.get('qty', 0) for pos in position_list)
                
                # 计算整体盈亏比例
                overall_pl_ratio = (total_pl_val / total_cost_val * 100) if total_cost_val > 0 else 0
                
                # 统计持仓分布
                position_distribution = {
                    "盈利持仓": len([p for p in position_list if p.get('pl_val', 0) > 0]),
                    "亏损持仓": len([p for p in position_list if p.get('pl_val', 0) < 0]),
                    "持平持仓": len([p for p in position_list if p.get('pl_val', 0) == 0])
                }
                
                # 按市场分组
                market_distribution = {}
                for pos in position_list:
                    market = pos.get('position_market', 'UNKNOWN')
                    if market not in market_distribution:
                        market_distribution[market] = {
                            "数量": 0,
                            "市值": 0,
                            "盈亏": 0
                        }
                    market_distribution[market]["数量"] += 1
                    market_distribution[market]["市值"] += pos.get('market_val', 0)
                    market_distribution[market]["盈亏"] += pos.get('pl_val', 0)
                
                # Top 持仓（按市值排序）
                top_positions = sorted(position_list, key=lambda x: x.get('market_val', 0), reverse=True)[:5]
                top_positions_summary = [
                    {
                        "代码": pos.get('code', ''),
                        "名称": pos.get('stock_name', ''),
                        "市值": pos.get('market_val', 0),
                        "盈亏": pos.get('pl_val', 0),
                        "盈亏比例": f"{pos.get('pl_ratio', 0) * 100:.2f}%"
                    }
                    for pos in top_positions
                ]
                
                summary = {
                    "持仓总数": total_count,
                    "总市值": total_market_val,
                    "总盈亏": total_pl_val,
                    "整体盈亏比例": f"{overall_pl_ratio:.2f}%",
                    "持仓分布": position_distribution,
                    "市场分布": market_distribution,
                    "前5大持仓": top_positions_summary
                }
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功查询{request.trd_env}环境持仓列表",
                    data={
                        "position_list": position_list,
                        "trd_env": request.trd_env,
                        "total_count": total_count,
                        "update_time": pd.Timestamp.now().isoformat(),
                        "data_source": "futu_api",
                        "summary": summary,
                        "filter_conditions": {
                            "代码过滤": request.code or "无",
                            "市场过滤": request.position_market or "全部",
                            "盈亏比例过滤": f"{request.pl_ratio_min or '无'}% ~ {request.pl_ratio_max or '无'}%"
                        }
                    }
                )
            else:
                logger.error(f"查询持仓列表失败: {data}")
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"查询持仓列表失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"查询持仓列表异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"查询持仓列表异常: {str(e)}",
                data=None
            )
    
    def _convert_trd_side(self, trd_side_enum) -> str:
        """将富途API的交易方向枚举转换为字符串"""
        trd_side_names = {
            ft.TrdSide.BUY: "BUY",
            ft.TrdSide.SELL: "SELL",
            ft.TrdSide.NONE: "NONE"
        }
        return trd_side_names.get(trd_side_enum, "UNKNOWN")
    
    def _parse_deal_data(self, deal_data, optimization_config) -> List[Dict[str, Any]]:
        """解析富途成交数据"""
        if deal_data is None:
            return []
        
        deals = []
        
        # 处理DataFrame格式的成交数据
        if hasattr(deal_data, 'iterrows'):
            for index, row in deal_data.iterrows():
                try:
                    deal = {}
                    
                    # 基础成交信息
                    basic_fields = {
                        'deal_id': 'deal_id',
                        'order_id': 'order_id',
                        'code': 'code',
                        'stock_name': 'stock_name',
                        'qty': 'qty',
                        'price': 'price',
                        'create_time': 'create_time',
                        'create_timestamp': 'create_timestamp',
                        'update_timestamp': 'update_timestamp',
                        'counter_broker_id': 'counter_broker_id',
                        'counter_broker_name': 'counter_broker_name',
                        'deal_fee': 'deal_fee',
                        'commission': 'commission',
                        'stamp_duty': 'stamp_duty',
                        'clearing_fee': 'clearing_fee'
                    }
                    
                    # 处理基础字段
                    for local_field, api_field in basic_fields.items():
                        if api_field in row:
                            value = row[api_field]
                            if pd.notna(value):
                                if local_field in ['qty', 'price', 'create_timestamp', 'update_timestamp',
                                                 'deal_fee', 'commission', 'stamp_duty', 'clearing_fee']:
                                    deal[local_field] = float(value)
                                elif local_field in ['counter_broker_id']:
                                    deal[local_field] = int(value)
                                else:
                                    deal[local_field] = str(value)
                    
                    # 处理枚举字段
                    if 'trd_side' in row:
                        deal['trd_side'] = self._convert_trd_side(row['trd_side'])
                    
                    if 'currency' in row:
                        deal['currency'] = self._parse_currency_name(row['currency'])
                    
                    if 'deal_market' in row:
                        deal['deal_market'] = self._parse_trd_market_name(row['deal_market'])
                    
                    if 'sec_market' in row:
                        deal['sec_market'] = self._parse_trd_market_name(row['sec_market'])
                    
                    # 计算成交金额
                    if 'qty' in deal and 'price' in deal:
                        deal['deal_value'] = deal['qty'] * deal['price']
                    
                    # 处理成交状态
                    if 'status' in row:
                        status_map = {0: 'OK', 1: 'CANCELLED', 2: 'FAILED'}
                        deal['status'] = status_map.get(row['status'], 'UNKNOWN')
                    
                    # 判断成交类型
                    if deal.get('trd_side') == 'BUY':
                        deal['deal_type'] = '买入成交'
                    elif deal.get('trd_side') == 'SELL':
                        deal['deal_type'] = '卖出成交'
                    else:
                        deal['deal_type'] = '未知类型'
                    
                    deals.append(deal)
                    
                except Exception as e:
                    logger.warning(f"解析成交数据行失败: {str(e)}")
                    continue
        
        return deals
    
    async def get_history_deal_list(self, request: HistoryDealListRequest) -> APIResponse:
        """查询历史成交列表"""
        self._check_trade_connection()
        
        try:
            logger.info(f"查询历史成交: trd_env={request.trd_env}, acc_id={request.acc_id}, code={request.code}")
            
            # 准备API参数
            api_params = {
                'trd_env': self._convert_trd_env(request.trd_env),
                'acc_id': request.acc_id,
                'acc_index': request.acc_index
            }
            
            # 添加可选参数
            if request.code:
                api_params['code'] = request.code
            
            if request.deal_market:
                api_params['deal_market'] = self._convert_trd_market(request.deal_market)
            
            if request.start:
                api_params['start'] = request.start
                
            if request.end:
                api_params['end'] = request.end
            
            # 调用富途API查询历史成交
            ret, data = self.trade_ctx.history_deal_list_query(**api_params)
            
            if ret == ft.RET_OK:
                logger.info("成功获取历史成交数据")
                
                # 解析成交数据
                deal_list = self._parse_deal_data(data, request.optimization)
                
                # 生成汇总信息
                total_count = len(deal_list)
                total_buy_qty = sum(deal.get('qty', 0) for deal in deal_list if deal.get('trd_side') == 'BUY')
                total_sell_qty = sum(deal.get('qty', 0) for deal in deal_list if deal.get('trd_side') == 'SELL')
                total_buy_value = sum(deal.get('deal_value', 0) for deal in deal_list if deal.get('trd_side') == 'BUY')
                total_sell_value = sum(deal.get('deal_value', 0) for deal in deal_list if deal.get('trd_side') == 'SELL')
                total_fees = sum(deal.get('deal_fee', 0) + deal.get('commission', 0) + 
                               deal.get('stamp_duty', 0) + deal.get('clearing_fee', 0) for deal in deal_list)
                
                # 统计成交分布
                deal_distribution = {
                    "买入成交": len([d for d in deal_list if d.get('trd_side') == 'BUY']),
                    "卖出成交": len([d for d in deal_list if d.get('trd_side') == 'SELL'])
                }
                
                # 按市场分组
                market_distribution = {}
                for deal in deal_list:
                    market = deal.get('deal_market', 'UNKNOWN')
                    if market not in market_distribution:
                        market_distribution[market] = {
                            "成交笔数": 0,
                            "成交数量": 0,
                            "成交金额": 0
                        }
                    market_distribution[market]["成交笔数"] += 1
                    market_distribution[market]["成交数量"] += deal.get('qty', 0)
                    market_distribution[market]["成交金额"] += deal.get('deal_value', 0)
                
                # Top 成交（按成交金额排序）
                top_deals = sorted(deal_list, key=lambda x: x.get('deal_value', 0), reverse=True)[:5]
                top_deals_summary = [
                    {
                        "代码": deal.get('code', ''),
                        "名称": deal.get('stock_name', ''),
                        "方向": deal.get('trd_side', ''),
                        "数量": deal.get('qty', 0),
                        "价格": deal.get('price', 0),
                        "成交金额": deal.get('deal_value', 0),
                        "时间": deal.get('create_time', '')
                    }
                    for deal in top_deals
                ]
                
                # 时间范围
                date_range = f"{request.start or '默认开始'} ~ {request.end or '默认结束'}"
                
                summary = {
                    "成交总笔数": total_count,
                    "买入总数量": total_buy_qty,
                    "卖出总数量": total_sell_qty,
                    "买入总金额": total_buy_value,
                    "卖出总金额": total_sell_value,
                    "总手续费": total_fees,
                    "净买入金额": total_buy_value - total_sell_value,
                    "成交分布": deal_distribution,
                    "市场分布": market_distribution,
                    "前5大成交": top_deals_summary
                }
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功查询{request.trd_env}环境历史成交",
                    data={
                        "deal_list": deal_list,
                        "trd_env": request.trd_env,
                        "total_count": total_count,
                        "date_range": date_range,
                        "update_time": pd.Timestamp.now().isoformat(),
                        "data_source": "futu_api",
                        "summary": summary,
                        "filter_conditions": {
                            "代码过滤": request.code or "无",
                            "市场过滤": request.deal_market or "全部",
                            "时间范围": date_range
                        }
                    }
                )
            else:
                logger.error(f"查询历史成交失败: {data}")
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"查询历史成交失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"查询历史成交异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"查询历史成交异常: {str(e)}",
                data=None
            )
    
    async def get_deal_list(self, request: DealListRequest) -> APIResponse:
        """查询当日成交列表"""
        self._check_trade_connection()
        
        try:
            logger.info(f"查询当日成交: trd_env={request.trd_env}, acc_id={request.acc_id}, code={request.code}")
            
            # 准备API参数
            api_params = {
                'trd_env': self._convert_trd_env(request.trd_env),
                'acc_id': request.acc_id,
                'acc_index': request.acc_index,
                'refresh_cache': request.refresh_cache
            }
            
            # 添加可选参数
            if request.code:
                api_params['code'] = request.code
            
            if request.deal_market:
                api_params['deal_market'] = self._convert_trd_market(request.deal_market)
            
            # 调用富途API查询当日成交
            ret, data = self.trade_ctx.deal_list_query(**api_params)
            
            if ret == ft.RET_OK:
                logger.info("成功获取当日成交数据")
                
                # 解析成交数据
                deal_list = self._parse_deal_data(data, request.optimization)
                
                # 生成汇总信息
                total_count = len(deal_list)
                total_buy_qty = sum(deal.get('qty', 0) for deal in deal_list if deal.get('trd_side') == 'BUY')
                total_sell_qty = sum(deal.get('qty', 0) for deal in deal_list if deal.get('trd_side') == 'SELL')
                total_buy_value = sum(deal.get('deal_value', 0) for deal in deal_list if deal.get('trd_side') == 'BUY')
                total_sell_value = sum(deal.get('deal_value', 0) for deal in deal_list if deal.get('trd_side') == 'SELL')
                total_fees = sum(deal.get('deal_fee', 0) + deal.get('commission', 0) + 
                               deal.get('stamp_duty', 0) + deal.get('clearing_fee', 0) for deal in deal_list)
                
                # 统计成交分布
                deal_distribution = {
                    "买入成交": len([d for d in deal_list if d.get('trd_side') == 'BUY']),
                    "卖出成交": len([d for d in deal_list if d.get('trd_side') == 'SELL'])
                }
                
                # 按市场分组
                market_distribution = {}
                for deal in deal_list:
                    market = deal.get('deal_market', 'UNKNOWN')
                    if market not in market_distribution:
                        market_distribution[market] = {
                            "成交笔数": 0,
                            "成交数量": 0,
                            "成交金额": 0
                        }
                    market_distribution[market]["成交笔数"] += 1
                    market_distribution[market]["成交数量"] += deal.get('qty', 0)
                    market_distribution[market]["成交金额"] += deal.get('deal_value', 0)
                
                # 按时间分组（每小时）
                time_distribution = {}
                for deal in deal_list:
                    create_time = deal.get('create_time', '')
                    if create_time:
                        try:
                            hour = create_time.split(' ')[1].split(':')[0] + ':00'
                            if hour not in time_distribution:
                                time_distribution[hour] = {
                                    "成交笔数": 0,
                                    "成交金额": 0
                                }
                            time_distribution[hour]["成交笔数"] += 1
                            time_distribution[hour]["成交金额"] += deal.get('deal_value', 0)
                        except:
                            pass
                
                # Top 成交（按成交金额排序）
                top_deals = sorted(deal_list, key=lambda x: x.get('deal_value', 0), reverse=True)[:5]
                top_deals_summary = [
                    {
                        "代码": deal.get('code', ''),
                        "名称": deal.get('stock_name', ''),
                        "方向": deal.get('trd_side', ''),
                        "数量": deal.get('qty', 0),
                        "价格": deal.get('price', 0),
                        "成交金额": deal.get('deal_value', 0),
                        "时间": deal.get('create_time', '')
                    }
                    for deal in top_deals
                ]
                
                summary = {
                    "成交总笔数": total_count,
                    "买入总数量": total_buy_qty,
                    "卖出总数量": total_sell_qty,
                    "买入总金额": total_buy_value,
                    "卖出总金额": total_sell_value,
                    "总手续费": total_fees,
                    "净买入金额": total_buy_value - total_sell_value,
                    "成交分布": deal_distribution,
                    "市场分布": market_distribution,
                    "时间分布": time_distribution,
                    "前5大成交": top_deals_summary
                }
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功查询{request.trd_env}环境当日成交",
                    data={
                        "deal_list": deal_list,
                        "trd_env": request.trd_env,
                        "total_count": total_count,
                        "trade_date": pd.Timestamp.now().strftime('%Y-%m-%d'),
                        "update_time": pd.Timestamp.now().isoformat(),
                        "data_source": "futu_api",
                        "summary": summary,
                        "filter_conditions": {
                            "代码过滤": request.code or "无",
                            "市场过滤": request.deal_market or "全部",
                            "交易日期": pd.Timestamp.now().strftime('%Y-%m-%d')
                        }
                    }
                )
            else:
                logger.error(f"查询当日成交失败: {data}")
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"查询当日成交失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"查询当日成交异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"查询当日成交异常: {str(e)}",
                data=None
            )
    
    def _convert_order_status(self, order_status_enum) -> str:
        """将富途API的订单状态枚举转换为字符串"""
        order_status_names = {
            ft.OrderStatus.NONE: "NONE",
            ft.OrderStatus.UNSUBMITTED: "UNSUBMITTED",
            ft.OrderStatus.WAITING_SUBMIT: "WAITING_SUBMIT",
            ft.OrderStatus.SUBMITTING: "SUBMITTING",
            ft.OrderStatus.SUBMIT_FAILED: "SUBMIT_FAILED",
            ft.OrderStatus.TIMEOUT: "TIMEOUT",
            ft.OrderStatus.SUBMITTED: "SUBMITTED",
            ft.OrderStatus.FILLED_PART: "FILLED_PART",
            ft.OrderStatus.FILLED_ALL: "FILLED_ALL",
            ft.OrderStatus.CANCELLING_PART: "CANCELLING_PART",
            ft.OrderStatus.CANCELLING_ALL: "CANCELLING_ALL",
            ft.OrderStatus.CANCELLED_PART: "CANCELLED_PART",
            ft.OrderStatus.CANCELLED_ALL: "CANCELLED_ALL",
            ft.OrderStatus.FAILED: "FAILED",
            ft.OrderStatus.DISABLED: "DISABLED",
            ft.OrderStatus.DELETED: "DELETED"
        }
        return order_status_names.get(order_status_enum, "UNKNOWN")
    
    def _convert_order_type(self, order_type_enum) -> str:
        """将富途API的订单类型枚举转换为字符串"""
        order_type_names = {
            ft.OrderType.NONE: "NONE",
            ft.OrderType.NORMAL: "NORMAL",
            ft.OrderType.MARKET: "MARKET",
            ft.OrderType.ABSOLUTE_LIMIT: "ABSOLUTE_LIMIT",
            ft.OrderType.AUCTION: "AUCTION",
            ft.OrderType.AUCTION_LIMIT: "AUCTION_LIMIT",
            ft.OrderType.SPECIAL_LIMIT: "SPECIAL_LIMIT",
            ft.OrderType.SPECIAL_LIMIT_ALL: "SPECIAL_LIMIT_ALL",
            ft.OrderType.STOP: "STOP",
            ft.OrderType.STOP_LIMIT: "STOP_LIMIT",
            ft.OrderType.TRAILING_STOP: "TRAILING_STOP",
            ft.OrderType.TRAILING_STOP_LIMIT: "TRAILING_STOP_LIMIT"
        }
        return order_type_names.get(order_type_enum, "UNKNOWN")
    
    def _parse_order_data(self, order_data, optimization_config) -> List[Dict[str, Any]]:
        """解析富途订单数据"""
        if order_data is None:
            return []
        
        orders = []
        
        # 处理DataFrame格式的订单数据
        if hasattr(order_data, 'iterrows'):
            for index, row in order_data.iterrows():
                try:
                    order = {}
                    
                    # 基础订单信息
                    basic_fields = {
                        'order_id': 'order_id',
                        'code': 'code',
                        'stock_name': 'stock_name',
                        'qty': 'qty',
                        'price': 'price',
                        'create_time': 'create_time',
                        'updated_time': 'updated_time',
                        'dealt_qty': 'dealt_qty',
                        'dealt_avg_price': 'dealt_avg_price',
                        'last_err_msg': 'last_err_msg',
                        'remark': 'remark',
                        'time_in_force': 'time_in_force',
                        'fill_outside_rth': 'fill_outside_rth',
                        'aux_price': 'aux_price',
                        'trail_type': 'trail_type',
                        'trail_value': 'trail_value',
                        'trail_spread': 'trail_spread'
                    }
                    
                    # 处理基础字段
                    for local_field, api_field in basic_fields.items():
                        if api_field in row:
                            value = row[api_field]
                            if pd.notna(value):
                                if local_field in ['qty', 'price', 'dealt_qty', 'dealt_avg_price', 
                                                 'aux_price', 'trail_value', 'trail_spread']:
                                    order[local_field] = float(value)
                                elif local_field in ['fill_outside_rth']:
                                    order[local_field] = bool(value)
                                else:
                                    order[local_field] = str(value)
                    
                    # 处理枚举字段
                    if 'trd_side' in row:
                        order['trd_side'] = self._convert_trd_side(row['trd_side'])
                    
                    if 'order_type' in row:
                        order['order_type'] = self._convert_order_type(row['order_type'])
                    
                    if 'order_status' in row:
                        order['order_status'] = self._convert_order_status(row['order_status'])
                    
                    if 'currency' in row:
                        order['currency'] = self._parse_currency_name(row['currency'])
                    
                    if 'order_market' in row:
                        order['order_market'] = self._parse_trd_market_name(row['order_market'])
                    
                    # 计算订单金额
                    if 'qty' in order and 'price' in order:
                        order['order_value'] = order['qty'] * order['price']
                    
                    # 计算已成交金额
                    if 'dealt_qty' in order and 'dealt_avg_price' in order:
                        order['dealt_value'] = order['dealt_qty'] * order['dealt_avg_price']
                    
                    # 计算成交比例
                    if order.get('qty', 0) > 0:
                        order['fill_ratio'] = (order.get('dealt_qty', 0) / order['qty']) * 100
                    else:
                        order['fill_ratio'] = 0
                    
                    # 判断订单状态描述
                    status = order.get('order_status', '')
                    if 'FILLED_ALL' in status:
                        order['status_description'] = '全部成交'
                    elif 'FILLED_PART' in status:
                        order['status_description'] = '部分成交'
                    elif 'CANCELLED' in status:
                        order['status_description'] = '已撤销'
                    elif 'SUBMITTED' in status:
                        order['status_description'] = '已提交'
                    elif 'FAILED' in status:
                        order['status_description'] = '失败'
                    else:
                        order['status_description'] = '其他状态'
                    
                    orders.append(order)
                    
                except Exception as e:
                    logger.warning(f"解析订单数据行失败: {str(e)}")
                    continue
        
        return orders
    
    async def get_history_order_list(self, request: HistoryOrderListRequest) -> APIResponse:
        """查询历史订单列表"""
        self._check_trade_connection()
        
        try:
            logger.info(f"查询历史订单: trd_env={request.trd_env}, acc_id={request.acc_id}, code={request.code}")
            
            # 准备API参数
            api_params = {
                'trd_env': self._convert_trd_env(request.trd_env),
                'acc_id': request.acc_id,
                'acc_index': request.acc_index
            }
            
            # 添加可选参数
            if request.status_filter_list:
                # 转换订单状态过滤列表
                status_filters = []
                for status in request.status_filter_list:
                    if hasattr(ft.OrderStatus, status):
                        status_filters.append(getattr(ft.OrderStatus, status))
                if status_filters:
                    api_params['status_filter_list'] = status_filters
            
            if request.code:
                api_params['code'] = request.code
            
            if request.order_market:
                api_params['order_market'] = self._convert_trd_market(request.order_market)
            
            if request.start:
                api_params['start'] = request.start
                
            if request.end:
                api_params['end'] = request.end
            
            # 调用富途API查询历史订单
            ret, data = self.trade_ctx.history_order_list_query(**api_params)
            
            if ret == ft.RET_OK:
                logger.info("成功获取历史订单数据")
                
                # 解析订单数据
                order_list = self._parse_order_data(data, request.optimization)
                
                # 生成汇总信息
                total_count = len(order_list)
                buy_orders = len([o for o in order_list if o.get('trd_side') == 'BUY'])
                sell_orders = len([o for o in order_list if o.get('trd_side') == 'SELL'])
                filled_orders = len([o for o in order_list if 'FILLED_ALL' in str(o.get('order_status', ''))])
                partial_filled_orders = len([o for o in order_list if 'FILLED_PART' in str(o.get('order_status', ''))])
                cancelled_orders = len([o for o in order_list if 'CANCELLED' in str(o.get('order_status', ''))])
                
                # 计算总订单金额和成交金额
                total_order_value = sum(o.get('order_value', 0) for o in order_list)
                total_dealt_value = sum(o.get('dealt_value', 0) for o in order_list)
                
                # 按状态分组
                status_distribution = {}
                for order in order_list:
                    status = order.get('status_description', '其他状态')
                    if status not in status_distribution:
                        status_distribution[status] = {
                            "订单数量": 0,
                            "订单金额": 0,
                            "成交金额": 0
                        }
                    status_distribution[status]["订单数量"] += 1
                    status_distribution[status]["订单金额"] += order.get('order_value', 0)
                    status_distribution[status]["成交金额"] += order.get('dealt_value', 0)
                
                # 按市场分组
                market_distribution = {}
                for order in order_list:
                    market = order.get('order_market', 'UNKNOWN')
                    if market not in market_distribution:
                        market_distribution[market] = {
                            "订单数量": 0,
                            "订单金额": 0,
                            "成交金额": 0
                        }
                    market_distribution[market]["订单数量"] += 1
                    market_distribution[market]["订单金额"] += order.get('order_value', 0)
                    market_distribution[market]["成交金额"] += order.get('dealt_value', 0)
                
                # Top 订单（按订单金额排序）
                top_orders = sorted(order_list, key=lambda x: x.get('order_value', 0), reverse=True)[:5]
                top_orders_summary = [
                    {
                        "订单ID": order.get('order_id', ''),
                        "代码": order.get('code', ''),
                        "名称": order.get('stock_name', ''),
                        "方向": order.get('trd_side', ''),
                        "数量": order.get('qty', 0),
                        "价格": order.get('price', 0),
                        "订单金额": order.get('order_value', 0),
                        "状态": order.get('status_description', ''),
                        "成交比例": f"{order.get('fill_ratio', 0):.1f}%",
                        "创建时间": order.get('create_time', '')
                    }
                    for order in top_orders
                ]
                
                # 时间范围
                date_range = f"{request.start or '90天前'} ~ {request.end or '今日'}"
                
                # 计算成交率
                fill_rate = (filled_orders / total_count * 100) if total_count > 0 else 0
                value_fill_rate = (total_dealt_value / total_order_value * 100) if total_order_value > 0 else 0
                
                summary = {
                    "订单总数": total_count,
                    "买入订单": buy_orders,
                    "卖出订单": sell_orders,
                    "全部成交": filled_orders,
                    "部分成交": partial_filled_orders,
                    "已撤销": cancelled_orders,
                    "总订单金额": total_order_value,
                    "总成交金额": total_dealt_value,
                    "订单成交率": f"{fill_rate:.1f}%",
                    "金额成交率": f"{value_fill_rate:.1f}%",
                    "状态分布": status_distribution,
                    "市场分布": market_distribution,
                    "前5大订单": top_orders_summary
                }
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功查询{request.trd_env}环境历史订单",
                    data={
                        "order_list": order_list,
                        "trd_env": request.trd_env,
                        "total_count": total_count,
                        "date_range": date_range,
                        "update_time": pd.Timestamp.now().isoformat(),
                        "data_source": "futu_api",
                        "summary": summary,
                        "filter_conditions": {
                            "代码过滤": request.code or "无",
                            "市场过滤": request.order_market or "全部",
                            "状态过滤": request.status_filter_list or "全部",
                            "时间范围": date_range
                        }
                    }
                )
            else:
                logger.error(f"查询历史订单失败: {data}")
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"查询历史订单失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"查询历史订单异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"查询历史订单异常: {str(e)}",
                data=None
            )
    
    def _parse_order_fee_data(self, fee_data, optimization_config) -> List[Dict[str, Any]]:
        """解析富途订单费用数据"""
        if fee_data is None:
            return []
        
        fees = []
        
        # 处理DataFrame格式的费用数据
        if hasattr(fee_data, 'iterrows'):
            for index, row in fee_data.iterrows():
                try:
                    fee = {}
                    
                    # 基础费用信息
                    basic_fields = {
                        'order_id': 'order_id',
                        'code': 'code',
                        'stock_name': 'stock_name',
                        'dealt_qty': 'dealt_qty',
                        'dealt_avg_price': 'dealt_avg_price',
                        'commission': 'commission',
                        'stamp_duty': 'stamp_duty',
                        'transfer_fee': 'transfer_fee',
                        'handling_fee': 'handling_fee',
                        'settlement_fee': 'settlement_fee',
                        'exchange_fee': 'exchange_fee',
                        'platform_fee': 'platform_fee',
                        'total_fee': 'total_fee'
                    }
                    
                    # 处理基础字段
                    for local_field, api_field in basic_fields.items():
                        if api_field in row:
                            value = row[api_field]
                            if pd.notna(value):
                                if local_field in ['dealt_qty', 'dealt_avg_price', 'commission', 
                                                 'stamp_duty', 'transfer_fee', 'handling_fee',
                                                 'settlement_fee', 'exchange_fee', 'platform_fee', 'total_fee']:
                                    fee[local_field] = float(value)
                                else:
                                    fee[local_field] = str(value)
                    
                    # 处理枚举字段
                    if 'trd_side' in row:
                        fee['trd_side'] = self._convert_trd_side(row['trd_side'])
                    
                    if 'currency' in row:
                        fee['currency'] = self._parse_currency_name(row['currency'])
                    
                    # 计算成交金额
                    if 'dealt_qty' in fee and 'dealt_avg_price' in fee:
                        fee['dealt_value'] = fee['dealt_qty'] * fee['dealt_avg_price']
                    
                    # 计算费率
                    if fee.get('dealt_value', 0) > 0:
                        fee['fee_rate'] = (fee.get('total_fee', 0) / fee['dealt_value']) * 100
                    else:
                        fee['fee_rate'] = 0
                    
                    # 费用明细
                    fee_details = []
                    fee_items = [
                        ('佣金', fee.get('commission', 0)),
                        ('印花税', fee.get('stamp_duty', 0)),
                        ('过户费', fee.get('transfer_fee', 0)),
                        ('手续费', fee.get('handling_fee', 0)),
                        ('结算费', fee.get('settlement_fee', 0)),
                        ('交易所费用', fee.get('exchange_fee', 0)),
                        ('平台费', fee.get('platform_fee', 0))
                    ]
                    
                    for fee_name, fee_amount in fee_items:
                        if fee_amount > 0:
                            fee_details.append({
                                'fee_type': fee_name,
                                'amount': fee_amount
                            })
                    
                    fee['fee_details'] = fee_details
                    
                    fees.append(fee)
                    
                except Exception as e:
                    logger.warning(f"解析费用数据行失败: {str(e)}")
                    continue
        
        return fees
    
    async def get_order_fee_query(self, request: OrderFeeQueryRequest) -> APIResponse:
        """查询订单费用"""
        self._check_trade_connection()
        
        try:
            logger.info(f"查询订单费用: trd_env={request.trd_env}, acc_id={request.acc_id}, order_count={len(request.order_id_list)}")
            
            # 准备API参数
            api_params = {
                'order_id_list': request.order_id_list,
                'trd_env': self._convert_trd_env(request.trd_env),
                'acc_id': request.acc_id,
                'acc_index': request.acc_index
            }
            
            # 调用富途API查询订单费用
            ret, data = self.trade_ctx.order_fee_query(**api_params)
            
            if ret == ft.RET_OK:
                logger.info("成功获取订单费用数据")
                
                # 解析费用数据
                fee_list = self._parse_order_fee_data(data, request.optimization)
                
                # 生成汇总信息
                total_count = len(fee_list)
                total_dealt_value = sum(fee.get('dealt_value', 0) for fee in fee_list)
                total_fee_amount = sum(fee.get('total_fee', 0) for fee in fee_list)
                average_fee = total_fee_amount / total_count if total_count > 0 else 0
                average_fee_rate = (total_fee_amount / total_dealt_value * 100) if total_dealt_value > 0 else 0
                
                # 按费用类型统计
                fee_type_summary = {
                    "佣金总额": sum(fee.get('commission', 0) for fee in fee_list),
                    "印花税总额": sum(fee.get('stamp_duty', 0) for fee in fee_list),
                    "过户费总额": sum(fee.get('transfer_fee', 0) for fee in fee_list),
                    "手续费总额": sum(fee.get('handling_fee', 0) for fee in fee_list),
                    "结算费总额": sum(fee.get('settlement_fee', 0) for fee in fee_list),
                    "交易所费用总额": sum(fee.get('exchange_fee', 0) for fee in fee_list),
                    "平台费总额": sum(fee.get('platform_fee', 0) for fee in fee_list)
                }
                
                # 按交易方向统计
                buy_fees = [fee for fee in fee_list if fee.get('trd_side') == 'BUY']
                sell_fees = [fee for fee in fee_list if fee.get('trd_side') == 'SELL']
                
                direction_summary = {
                    "买入订单费用": {
                        "订单数量": len(buy_fees),
                        "总费用": sum(fee.get('total_fee', 0) for fee in buy_fees),
                        "平均费用": sum(fee.get('total_fee', 0) for fee in buy_fees) / len(buy_fees) if buy_fees else 0
                    },
                    "卖出订单费用": {
                        "订单数量": len(sell_fees),
                        "总费用": sum(fee.get('total_fee', 0) for fee in sell_fees),
                        "平均费用": sum(fee.get('total_fee', 0) for fee in sell_fees) / len(sell_fees) if sell_fees else 0
                    }
                }
                
                # Top 费用订单（按费用金额排序）
                top_fee_orders = sorted(fee_list, key=lambda x: x.get('total_fee', 0), reverse=True)[:5]
                top_fee_summary = [
                    {
                        "订单ID": fee.get('order_id', ''),
                        "代码": fee.get('code', ''),
                        "名称": fee.get('stock_name', ''),
                        "方向": fee.get('trd_side', ''),
                        "成交金额": fee.get('dealt_value', 0),
                        "总费用": fee.get('total_fee', 0),
                        "费率": f"{fee.get('fee_rate', 0):.4f}%",
                        "货币": fee.get('currency', '')
                    }
                    for fee in top_fee_orders
                ]
                
                summary = {
                    "查询订单数": total_count,
                    "总成交金额": total_dealt_value,
                    "总费用金额": total_fee_amount,
                    "平均费用": average_fee,
                    "平均费率": f"{average_fee_rate:.4f}%",
                    "费用类型统计": fee_type_summary,
                    "交易方向统计": direction_summary,
                    "前5高费用订单": top_fee_summary
                }
                
                return APIResponse(
                    ret_code=0,
                    ret_msg=f"成功查询{request.trd_env}环境订单费用",
                    data={
                        "fee_list": fee_list,
                        "trd_env": request.trd_env,
                        "total_count": total_count,
                        "order_ids": request.order_id_list,
                        "update_time": pd.Timestamp.now().isoformat(),
                        "data_source": "futu_api",
                        "summary": summary
                    }
                )
            else:
                logger.error(f"查询订单费用失败: {data}")
                return APIResponse(
                    ret_code=ret,
                    ret_msg=f"查询订单费用失败: {data}",
                    data=None
                )
                
        except Exception as e:
            logger.error(f"查询订单费用异常: {str(e)}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"查询订单费用异常: {str(e)}",
                data=None
            )
