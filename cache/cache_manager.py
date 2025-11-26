"""
智能数据缓存管理器
支持多层缓存策略：内存 + Redis + SQLite
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from loguru import logger
from dataclasses import dataclass
import hashlib

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    logger.warning("Redis not available, using memory cache only")
    REDIS_AVAILABLE = False

@dataclass
class CacheConfig:
    """缓存配置"""
    redis_url: str = "redis://localhost:6379"
    sqlite_path: str = "data/futu_cache.db"
    memory_max_size: int = 1000  # 内存缓存最大条目数
    redis_expire_seconds: int = 3600  # Redis缓存过期时间
    enable_compression: bool = True


class DataCacheManager:
    """智能数据缓存管理器"""
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.memory_cache = {}  # 内存缓存：{key: (data, timestamp)}
        self.redis_client = None
        self.sqlite_conn = None
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储系统"""
        # 初始化SQLite
        self._init_sqlite()
        
        # 初始化Redis（如果可用）
        if REDIS_AVAILABLE:
            asyncio.create_task(self._init_redis())
    
    def _init_sqlite(self):
        """初始化SQLite数据库"""
        try:
            import os
            os.makedirs(os.path.dirname(self.config.sqlite_path), exist_ok=True)
            
            self.sqlite_conn = sqlite3.connect(self.config.sqlite_path, check_same_thread=False)
            
            # 创建表结构
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS kline_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    ktype TEXT NOT NULL,
                    date_key TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code, ktype, date_key)
                )
            """)
            
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS quote_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    UNIQUE(code)
                )
            """)
            
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS indicator_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL UNIQUE,
                    indicator_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL
                )
            """)
            
            # 创建索引
            self.sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_kline_code_ktype ON kline_cache(code, ktype)")
            self.sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_quote_code ON quote_cache(code)")
            self.sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_indicator_key ON indicator_cache(cache_key)")
            
            self.sqlite_conn.commit()
            logger.info("SQLite缓存数据库初始化成功")
            
        except Exception as e:
            logger.error(f"SQLite初始化失败: {e}")
    
    async def _init_redis(self):
        """初始化Redis连接"""
        try:
            self.redis_client = redis.from_url(self.config.redis_url)
            await self.redis_client.ping()
            logger.info("Redis缓存连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败，使用本地缓存: {e}")
            self.redis_client = None
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [prefix]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{v}")
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _normalize_indicator_params(self, params: Dict) -> Dict:
        """提取并标准化影响技术指标结果的参数"""
        relevant_keys = [
            "indicators", "ktype", "period",
            "macd_fast", "macd_slow", "macd_signal",
            "rsi_period", "rsi_overbought", "rsi_oversold",
            "bollinger_period", "bollinger_std",
            "ma_periods", "kdj_k_period", "kdj_d_period", "kdj_j_period",
            "atr_period"
        ]
        
        def _enum_to_value(value):
            return value.value if hasattr(value, "value") else value
        
        normalized = {}
        for key in relevant_keys:
            if key not in params:
                continue
            value = params[key]
            if value is None:
                continue
            if key in ("indicators", "ma_periods") and isinstance(value, list):
                normalized[key] = tuple(
                    sorted(_enum_to_value(v) for v in value)
                )
            else:
                normalized[key] = _enum_to_value(value)
        
        return normalized
    
    async def get_kline_data(self, code: str, ktype: str, start: str, end: str) -> Optional[List[Dict]]:
        """智能获取K线数据"""
        cache_key = self._generate_cache_key("kline", code=code, ktype=ktype, start=start, end=end)
        
        # 1. 检查内存缓存
        memory_data = self._get_from_memory(cache_key)
        if memory_data:
            logger.debug(f"内存缓存命中: {cache_key}")
            return memory_data
        
        # 2. 检查Redis缓存
        if self.redis_client:
            redis_data = await self._get_from_redis(cache_key)
            if redis_data:
                logger.debug(f"Redis缓存命中: {cache_key}")
                self._store_to_memory(cache_key, redis_data)
                return redis_data
        
        # 3. 检查SQLite中的数据覆盖度
        sqlite_data = self._get_kline_from_sqlite(code, ktype, start, end)
        if sqlite_data:
            logger.debug(f"SQLite缓存命中: {cache_key}")
            # 存储到上层缓存
            await self._store_to_redis(cache_key, sqlite_data)
            self._store_to_memory(cache_key, sqlite_data)
            return sqlite_data
        
        logger.debug(f"缓存未命中: {cache_key}")
        return None
    
    async def store_kline_data(self, code: str, ktype: str, start: str, end: str, data: List[Dict]):
        """存储K线数据到缓存"""
        cache_key = self._generate_cache_key("kline", code=code, ktype=ktype, start=start, end=end)
        
        # 存储到所有缓存层
        self._store_to_memory(cache_key, data)
        await self._store_to_redis(cache_key, data)
        self._store_kline_to_sqlite(code, ktype, data)
        
        logger.debug(f"K线数据已缓存: {cache_key}, 数据量: {len(data)}")
    
    async def get_quote_data(self, codes: List[str]) -> Optional[List[Dict]]:
        """获取报价数据"""
        cache_key = self._generate_cache_key("quote", codes="|".join(sorted(codes)))
        
        # 检查内存缓存（报价数据时效性要求高，主要使用内存和Redis）
        memory_data = self._get_from_memory(cache_key)
        if memory_data and self._is_fresh(cache_key, seconds=10):
            return memory_data
        
        # 检查Redis缓存
        if self.redis_client:
            redis_data = await self._get_from_redis(cache_key)
            if redis_data:
                self._store_to_memory(cache_key, redis_data)
                return redis_data
        
        return None
    
    async def store_quote_data(self, codes: List[str], data: List[Dict]):
        """存储报价数据"""
        cache_key = self._generate_cache_key("quote", codes="|".join(sorted(codes)))
        
        # 报价数据只存储到内存和Redis（时效性高）
        self._store_to_memory(cache_key, data)
        await self._store_to_redis(cache_key, data, expire_seconds=30)
        
        logger.debug(f"报价数据已缓存: {cache_key}, 数据量: {len(data)}")
    
    async def get_indicator_data(self, indicator_type: str, code: str, params: Dict) -> Optional[Dict]:
        """获取技术指标数据"""
        normalized_params = self._normalize_indicator_params(params)
        cache_key = self._generate_cache_key("indicator", type=indicator_type, code=code, **normalized_params)
        
        # 检查内存缓存
        memory_data = self._get_from_memory(cache_key)
        if memory_data and self._is_fresh(cache_key, seconds=60):
            return memory_data
        
        # 检查Redis缓存
        if self.redis_client:
            redis_data = await self._get_from_redis(cache_key)
            if redis_data:
                self._store_to_memory(cache_key, redis_data)
                return redis_data
        
        return None
    
    async def store_indicator_data(self, indicator_type: str, code: str, params: Dict, data: Dict):
        """存储技术指标数据"""
        normalized_params = self._normalize_indicator_params(params)
        cache_key = self._generate_cache_key("indicator", type=indicator_type, code=code, **normalized_params)
        
        self._store_to_memory(cache_key, data)
        await self._store_to_redis(cache_key, data, expire_seconds=300)  # 5分钟过期
        
        # 存储到SQLite（用于长期缓存）
        try:
            expires_at = datetime.now() + timedelta(hours=1)
            self.sqlite_conn.execute("""
                INSERT OR REPLACE INTO indicator_cache 
                (cache_key, indicator_type, data, expires_at) VALUES (?, ?, ?, ?)
            """, (cache_key, indicator_type, json.dumps(data), expires_at))
            self.sqlite_conn.commit()
        except Exception as e:
            logger.warning(f"存储指标数据到SQLite失败: {e}")
    
    def _get_from_memory(self, key: str) -> Optional[Any]:
        """从内存缓存获取数据"""
        if key in self.memory_cache:
            data, timestamp = self.memory_cache[key]
            return data
        return None
    
    def _store_to_memory(self, key: str, data: Any):
        """存储数据到内存缓存"""
        # 简单的LRU策略：如果超过最大大小，删除最旧的条目
        if len(self.memory_cache) >= self.config.memory_max_size:
            oldest_key = min(self.memory_cache.keys(), 
                           key=lambda k: self.memory_cache[k][1])
            del self.memory_cache[oldest_key]
        
        self.memory_cache[key] = (data, datetime.now())
    
    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """从Redis获取数据"""
        if not self.redis_client:
            return None
        
        try:
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis获取数据失败: {e}")
        return None
    
    async def _store_to_redis(self, key: str, data: Any, expire_seconds: int = None):
        """存储数据到Redis"""
        if not self.redis_client:
            return
        
        try:
            expire_seconds = expire_seconds or self.config.redis_expire_seconds
            await self.redis_client.setex(key, expire_seconds, json.dumps(data, default=str))
        except Exception as e:
            logger.warning(f"Redis存储数据失败: {e}")
    
    def _get_kline_from_sqlite(self, code: str, ktype: str, start: str, end: str) -> Optional[List[Dict]]:
        """从SQLite获取K线数据"""
        try:
            cursor = self.sqlite_conn.execute("""
                SELECT data FROM kline_cache 
                WHERE code = ? AND ktype = ? AND date_key BETWEEN ? AND ?
                ORDER BY date_key
            """, (code, ktype, start, end))
            
            rows = cursor.fetchall()
            if rows:
                all_data = []
                for row in rows:
                    data = json.loads(row[0])
                    if isinstance(data, list):
                        all_data.extend(data)
                    else:
                        all_data.append(data)
                return all_data
        except Exception as e:
            logger.warning(f"SQLite获取K线数据失败: {e}")
        return None
    
    def _store_kline_to_sqlite(self, code: str, ktype: str, data: List[Dict]):
        """存储K线数据到SQLite"""
        try:
            for item in data:
                date_key = item.get('time_key', '').split(' ')[0]  # 提取日期部分
                self.sqlite_conn.execute("""
                    INSERT OR REPLACE INTO kline_cache 
                    (code, ktype, date_key, data) VALUES (?, ?, ?, ?)
                """, (code, ktype, date_key, json.dumps(item)))
            
            self.sqlite_conn.commit()
        except Exception as e:
            logger.warning(f"存储K线数据到SQLite失败: {e}")
    
    def _is_fresh(self, key: str, seconds: int) -> bool:
        """检查缓存数据是否新鲜"""
        if key in self.memory_cache:
            _, timestamp = self.memory_cache[key]
            return (datetime.now() - timestamp).total_seconds() < seconds
        return False
    
    async def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        stats = {
            "memory_cache_size": len(self.memory_cache),
            "memory_max_size": self.config.memory_max_size,
            "redis_available": self.redis_client is not None,
            "sqlite_available": self.sqlite_conn is not None
        }
        
        # SQLite统计
        if self.sqlite_conn:
            try:
                cursor = self.sqlite_conn.execute("SELECT COUNT(*) FROM kline_cache")
                stats["sqlite_kline_count"] = cursor.fetchone()[0]
                
                cursor = self.sqlite_conn.execute("SELECT COUNT(*) FROM indicator_cache")
                stats["sqlite_indicator_count"] = cursor.fetchone()[0]
            except Exception as e:
                logger.warning(f"获取SQLite统计失败: {e}")
        
        # Redis统计
        if self.redis_client:
            try:
                info = await self.redis_client.info()
                stats["redis_memory_usage"] = info.get("used_memory_human", "N/A")
                stats["redis_connected"] = True
            except Exception as e:
                logger.warning(f"获取Redis统计失败: {e}")
                stats["redis_connected"] = False
        
        return stats
    
    async def clear_cache(self, cache_type: str = "all"):
        """清理缓存"""
        if cache_type in ["all", "memory"]:
            self.memory_cache.clear()
            logger.info("内存缓存已清理")
        
        if cache_type in ["all", "redis"] and self.redis_client:
            try:
                await self.redis_client.flushdb()
                logger.info("Redis缓存已清理")
            except Exception as e:
                logger.warning(f"清理Redis缓存失败: {e}")
        
        if cache_type in ["all", "sqlite"] and self.sqlite_conn:
            try:
                self.sqlite_conn.execute("DELETE FROM kline_cache")
                self.sqlite_conn.execute("DELETE FROM quote_cache") 
                self.sqlite_conn.execute("DELETE FROM indicator_cache")
                self.sqlite_conn.commit()
                logger.info("SQLite缓存已清理")
            except Exception as e:
                logger.warning(f"清理SQLite缓存失败: {e}")
    
    async def preload_data(self, symbols: List[str], days: int = 30):
        """预加载数据"""
        from datetime import date
        end_date = date.today().strftime('%Y-%m-%d')
        start_date = (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        logger.info(f"开始预加载数据: {len(symbols)} 只股票, {days} 天数据")
        
        # 这里应该调用FutuService获取数据
        # 为了演示，我们只是记录日志
        for symbol in symbols:
            logger.debug(f"预加载 {symbol} 的数据: {start_date} 到 {end_date}")
            # await self.store_kline_data(symbol, "K_DAY", start_date, end_date, data)
        
        logger.info("数据预加载完成")
    
    def __del__(self):
        """清理资源"""
        if self.sqlite_conn:
            self.sqlite_conn.close() 
