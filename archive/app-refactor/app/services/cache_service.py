import json
import sqlite3
import time
from typing import Dict, List, Optional, Any, Union
from loguru import logger
import redis.asyncio as redis
from app.config import settings

class DataCacheManager:
    """数据缓存管理器"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Any] = {}
        self.sqlite_conn = None
        self._init_redis()
        self._init_sqlite()
        
    def _init_redis(self):
        """初始化Redis连接"""
        if not settings.cache_enabled:
            return
            
        try:
            self.redis = redis.from_url(
                settings.redis_url, 
                encoding="utf-8", 
                decode_responses=True
            )
            logger.info("Redis连接初始化中...")
        except Exception as e:
            logger.warning(f"Redis初始化失败: {e}")
            self.redis = None

    def _init_sqlite(self):
        """初始化SQLite连接"""
        try:
            import os
            os.makedirs(os.path.dirname(settings.sqlite_path), exist_ok=True)
            self.sqlite_conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
            self._create_tables()
            logger.info(f"SQLite数据库已连接: {settings.sqlite_path}")
        except Exception as e:
            logger.error(f"SQLite初始化失败: {e}")

    def _create_tables(self):
        """创建必要的表"""
        cursor = self.sqlite_conn.cursor()
        
        # K线数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS kline_data (
            code TEXT,
            ktype TEXT,
            time_key TEXT,
            data JSON,
            update_time REAL,
            PRIMARY KEY (code, ktype, time_key)
        )
        ''')
        
        self.sqlite_conn.commit()

    async def get_kline_data(self, code: str, ktype: str, start: str, end: str) -> Optional[List[Dict]]:
        """获取K线数据"""
        # 简单实现：只从SQLite读取，暂不处理复杂的时间范围拼接
        # 实际生产中需要更复杂的逻辑来合并缓存和API数据
        try:
            cursor = self.sqlite_conn.cursor()
            query = "SELECT data FROM kline_data WHERE code=? AND ktype=? AND time_key >= ? AND time_key <= ? ORDER BY time_key"
            cursor.execute(query, (code, ktype, start, end))
            rows = cursor.fetchall()
            if rows:
                return [json.loads(row[0]) for row in rows]
            return None
        except Exception as e:
            logger.error(f"读取K线缓存失败: {e}")
            return None

    async def store_kline_data(self, code: str, ktype: str, data: List[Dict]):
        """存储K线数据"""
        if not data:
            return
            
        try:
            cursor = self.sqlite_conn.cursor()
            now = time.time()
            
            # 批量插入
            records = []
            for item in data:
                time_key = item.get('time_key')
                if time_key:
                    records.append((code, ktype, time_key, json.dumps(item), now))
            
            cursor.executemany(
                "INSERT OR REPLACE INTO kline_data (code, ktype, time_key, data, update_time) VALUES (?, ?, ?, ?, ?)",
                records
            )
            self.sqlite_conn.commit()
        except Exception as e:
            logger.error(f"存储K线缓存失败: {e}")

    async def get_quote_cache(self, codes: List[str]) -> Dict[str, Dict]:
        """获取报价缓存"""
        if not self.redis:
            return {}
            
        result = {}
        try:
            # 使用pipeline批量获取
            async with self.redis.pipeline() as pipe:
                for code in codes:
                    pipe.get(f"quote:{code}")
                values = await pipe.execute()
                
            for code, val in zip(codes, values):
                if val:
                    result[code] = json.loads(val)
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
            
        return result

    async def set_quote_cache(self, quotes: List[Dict]):
        """设置报价缓存"""
        if not self.redis:
            return
            
        try:
            async with self.redis.pipeline() as pipe:
                for quote in quotes:
                    code = quote.get('code')
                    if code:
                        pipe.setex(
                            f"quote:{code}", 
                            10,  # 10秒过期
                            json.dumps(quote)
                        )
                await pipe.execute()
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")

cache_manager = DataCacheManager()
