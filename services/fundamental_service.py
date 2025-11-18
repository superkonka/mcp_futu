"""
基本面搜索服务
封装metaso API调用来获取股票基本面信息
"""

import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
from urllib.parse import urlparse
from config import settings

from models.fundamental_models import (
    FundamentalSearchRequest, 
    FundamentalSearchResponse, 
    SearchResultItem
)
from models.futu_models import APIResponse


class FundamentalService:
    """基本面搜索服务"""
    
    def __init__(self):
        self.base_url = "https://metaso.cn/api/v1/search"
        self.api_key = settings.metaso_api_key  # 从本地环境读取
        self.timeout = 30

    def _require_api_key(self):
        if not self.api_key:
            raise Exception("Metaso API 密钥未配置。请在本地 .env 设置 METASO_API_KEY。")
        
    async def search_fundamental_info(self, request: FundamentalSearchRequest) -> FundamentalSearchResponse:
        """
        搜索基本面信息
        
        Args:
            request: 搜索请求参数
            
        Returns:
            FundamentalSearchResponse: 搜索结果响应
            
        Raises:
            Exception: 搜索失败时抛出异常
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"开始基本面搜索: {request.q}")
            self._require_api_key()
            
            # 构建请求参数
            params = {
                "q": request.q,
                "scope": request.scope,
                "includeSummary": request.includeSummary,
                "size": request.size,
                "includeRawContent": request.includeRawContent,
                "conciseSnippet": request.conciseSnippet
            }
            
            # 构建请求头
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            # 发送请求
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.base_url,
                    headers=headers,
                    json=params
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"metaso API返回错误状态码 {response.status}: {error_text}")
                        raise Exception(f"搜索API返回错误状态码: {response.status}")
                    
                    result_data = await response.json()
                    
                    # 解析响应数据
                    search_response = self._parse_search_response(result_data, request.q)
                    
                    # 计算搜索耗时
                    search_time = (datetime.now() - start_time).total_seconds()
                    search_response.search_time = search_time
                    
                    logger.info(f"基本面搜索完成: {request.q}, 找到 {search_response.total_results} 条结果, 耗时 {search_time:.2f}s")
                    
                    return search_response
                    
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {e}")
            raise Exception(f"搜索请求网络失败: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise Exception(f"搜索结果解析失败: {e}")
        except Exception as e:
            logger.error(f"搜索过程发生错误: {e}")
            raise Exception(f"基本面搜索失败: {e}")
    
    def _parse_search_response(self, raw_data: Dict[str, Any], query: str) -> FundamentalSearchResponse:
        """
        解析metaso API响应数据
        """
        try:
            results = []
            total_results = 0

            # 1) Metaso常见结构：webpages
            if "webpages" in raw_data and isinstance(raw_data["webpages"], list):
                items = raw_data["webpages"]
                total_results = len(items)

                score_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
                for item in items:
                    url = item.get("link", "")
                    # 尝试提取域名作为来源
                    source = None
                    try:
                        source = urlparse(url).netloc or None
                    except Exception:
                        pass

                    score_val = item.get("score")
                    relevance_score = None
                    if isinstance(score_val, (int, float)):
                        relevance_score = float(score_val)
                    elif isinstance(score_val, str):
                        relevance_score = score_map.get(score_val.lower())

                    # 优先使用 snippet，其次兼容 summary
                    snippet = item.get("snippet")
                    if not snippet:
                        snippet = item.get("summary", "")

                    search_item = SearchResultItem(
                        title=item.get("title", ""),
                        url=url,
                        snippet=snippet,
                        source=source,
                        publish_time=item.get("date"),  # 原样保留字符串日期
                        relevance_score=relevance_score
                    )
                    results.append(search_item)

            # 2) 旧结构：results
            elif "results" in raw_data and isinstance(raw_data["results"], list):
                items = raw_data["results"]
                total_results = len(items)
                for item in items:
                    search_item = SearchResultItem(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        source=item.get("source"),
                        publish_time=item.get("publish_time"),
                        relevance_score=item.get("relevance_score")
                    )
                    results.append(search_item)

            # 3) 另一种嵌套结构：data.results
            elif "data" in raw_data and isinstance(raw_data["data"], dict) and "results" in raw_data["data"]:
                items = raw_data["data"]["results"]
                total_results = raw_data["data"].get("total", len(items))
                for item in items:
                    search_item = SearchResultItem(
                        title=item.get("title", item.get("name", "")),
                        url=item.get("url", item.get("link", "")),
                        snippet=item.get("snippet", item.get("description", "")),
                        source=item.get("source"),
                        publish_time=item.get("publish_time"),
                        relevance_score=item.get("score") if isinstance(item.get("score"), (int, float)) else None
                    )
                    results.append(search_item)

            else:
                # 兜底：记录原始结构并尽量提取
                logger.warning(f"未知的响应结构: {raw_data}")
                if isinstance(raw_data, list):
                    total_results = len(raw_data)
                    for item in raw_data:
                        if isinstance(item, dict):
                            url = item.get("url", item.get("link", ""))
                            source = None
                            try:
                                source = urlparse(url).netloc or None
                            except Exception:
                                pass
                            search_item = SearchResultItem(
                                title=item.get("title", str(item)),
                                url=url,
                                snippet=item.get("snippet", item.get("summary", item.get("description", str(item)))),
                                source=source,
                                publish_time=item.get("publish_time", item.get("date")),
                                relevance_score=item.get("score") if isinstance(item.get("score"), (int, float)) else None
                            )
                            results.append(search_item)

            return FundamentalSearchResponse(
                query=query,
                total_results=total_results,
                results=results,
                search_time=0.0
            )

        except Exception as e:
            logger.error(f"解析搜索响应失败: {e}, 原始数据: {raw_data}")
            return FundamentalSearchResponse(
                query=query,
                total_results=0,
                results=[],
                search_time=0.0
            )
    
    async def search_stock_fundamental(self, stock_code: str, stock_name: str = "") -> APIResponse:
        """
        搜索特定股票的基本面信息
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选）
            
        Returns:
            APIResponse: 统一格式的API响应
        """
        try:
            # 构建搜索关键词
            if stock_name:
                query = f"影响{stock_name}({stock_code})股价的相关信息 基本面 财务 新闻"
            else:
                query = f"影响{stock_code}股价的相关信息 基本面 财务 新闻"
            
            # 创建搜索请求
            request = FundamentalSearchRequest(
                q=query,
                scope="webpage",
                includeSummary=True,
                size=10,
                includeRawContent=False,
                conciseSnippet=True
            )
            
            # 执行搜索
            response = await self.search_fundamental_info(request)
            
            return APIResponse(
                ret_code=0,
                ret_msg="基本面搜索成功",
                data=response.dict()
            )
            
        except Exception as e:
            logger.error(f"股票基本面搜索失败: {e}")
            return APIResponse(
                ret_code=-1,
                ret_msg=f"股票基本面搜索失败: {e}",
                data=None
            )


    async def read_webpage(self, url: str) -> str:
        """
        读取网页内容
        
        Args:
            url: 要读取的网页URL
            
        Returns:
            str: 网页纯文本内容
            
        Raises:
            Exception: 读取失败时抛出异常
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"开始读取网页: {url}")
            
            # 构建请求数据
            request_data = {
                "url": url
            }
            
            # 构建请求头
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "text/plain",
                "Content-Type": "application/json"
            }
            
            # 发送请求
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    "https://metaso.cn/api/v1/reader",
                    headers=headers,
                    json=request_data
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"metaso reader API返回错误状态码 {response.status}: {error_text}")
                        raise Exception(f"网页读取API返回错误状态码: {response.status}")
                    
                    # 获取纯文本内容
                    content = await response.text()
                    
                    read_time = (datetime.now() - start_time).total_seconds()
                    content_length = len(content)
                    
                    logger.info(f"网页读取成功: {url}, 内容长度: {content_length} 字符, 耗时: {read_time:.2f}s")
                    
                    return content
                    
        except aiohttp.ClientError as e:
            logger.error(f"网页读取网络请求失败: {e}")
            raise Exception(f"网页读取请求网络失败: {e}")
        except Exception as e:
            logger.error(f"网页读取过程发生错误: {e}")
            raise Exception(f"网页读取失败: {e}")
    
    async def chat_completion(self, messages: List[Dict[str, str]], model: str = "fast", stream: bool = True) -> str:
        """
        问答对话完成
        
        Args:
            messages: 对话消息列表，格式：[{"role": "user", "content": "问题内容"}]
            model: 模型类型，默认"fast"
            stream: 是否流式响应，默认True
            
        Returns:
            str: 回答内容（流式只返回第一条非空chunk）
            
        Raises:
            Exception: 问答失败时抛出异常
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"开始问答对话，模型: {model}, 流式: {stream}")
            
            # 构建请求数据
            request_data = {
                "model": model,
                "stream": stream,
                "messages": messages
            }
            
            # 构建请求头
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            # 发送请求
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    "https://metaso.cn/api/v1/chat/completions",
                    headers=headers,
                    json=request_data
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"metaso chat API返回错误状态码 {response.status}: {error_text}")
                        raise Exception(f"问答API返回错误状态码: {response.status}")
                    
                    if stream:
                        # 流式响应，读取第一条非空chunk
                        answer = ""
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: '):
                                chunk_data = line[6:]  # 去掉 "data: " 前缀
                                if chunk_data and chunk_data != '[DONE]':
                                    try:
                                        chunk_json = json.loads(chunk_data)
                                        if 'choices' in chunk_json and len(chunk_json['choices']) > 0:
                                            delta = chunk_json['choices'][0].get('delta', {})
                                            content = delta.get('content', '')
                                            if content:
                                                answer += content
                                                # 只取第一条非空chunk
                                                break
                                    except json.JSONDecodeError:
                                        continue
                        
                        if not answer:
                            # 如果没有获取到内容，尝试解析完整响应
                            full_response = await response.text()
                            logger.warning(f"流式响应未获取到内容，尝试解析完整响应: {full_response}")
                            try:
                                data = json.loads(full_response)
                                if 'choices' in data and len(data['choices']) > 0:
                                    answer = data['choices'][0].get('message', {}).get('content', '')
                            except:
                                answer = full_response
                        
                        response_time = (datetime.now() - start_time).total_seconds()
                        logger.info(f"问答完成，模型: {model}, 流式响应, 耗时: {response_time:.2f}s, 回答长度: {len(answer)} 字符")
                        return answer
                    
                    else:
                        # 非流式响应
                        data = await response.json()
                        if 'choices' in data and len(data['choices']) > 0:
                            answer = data['choices'][0].get('message', {}).get('content', '')
                        else:
                            answer = str(data)
                        
                        response_time = (datetime.now() - start_time).total_seconds()
                        logger.info(f"问答完成，模型: {model}, 非流式响应, 耗时: {response_time:.2f}s, 回答长度: {len(answer)} 字符")
                        return answer
                        
        except aiohttp.ClientError as e:
            logger.error(f"问答网络请求失败: {e}")
            raise Exception(f"问答请求网络失败: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"问答JSON解析失败: {e}")
            raise Exception(f"问答结果解析失败: {e}")
        except Exception as e:
            logger.error(f"问答过程发生错误: {e}")
            raise Exception(f"问答失败: {e}")


# 创建全局服务实例
fundamental_service = FundamentalService()