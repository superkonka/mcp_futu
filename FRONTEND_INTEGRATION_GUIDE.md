## 富途 HTTP 服务前端接入指南（SSE 单播推送）

面向前端工程的完整接入指南，适用于 Web 前端（React/Vue/原生 JS）通过 HTTP + SSE 单播方式接收服务端推送的实时报价更新。

---

### 1. 服务端能力概览

- **订阅接口（HTTP）**: 绑定前端 `client_id` 与标的列表
  - `POST /api/quote/subscribe_push`
  - Body: `{ "client_id": "fe-123", "symbols": ["HK.00700", "US.AAPL"] }`
- **单播流式推送（SSE）**: 按 `client_id` 单播推送订阅标的的实时报价
  - `GET /api/stream/sse?client_id=fe-123`
  - 事件类型：`welcome`、`quote`、`heartbeat`
- **健康检查（HTTP）**: 检查后台状态（OpenD 连接、缓存可用等）
  - `GET /health`

注意：需先调用“订阅接口”再建立SSE连接。

---

### 2. 端到端调用时序

1) 前端生成唯一 `client_id`（推荐用用户ID + 随机串/TabID，避免多标签页冲突）。
2) 调用订阅接口，绑定 `client_id` 与 `symbols`。
3) 建立 SSE 连接，开始接收 `quote` 单播事件。
4) 页面关闭或切换时关闭连接；若网络闪断，前端需自动重连（见第6节）。

---

### 3. 接口定义与事件格式

#### 3.1 订阅接口

请求：

```json
POST /api/quote/subscribe_push
Content-Type: application/json
{
  "client_id": "fe-123",
  "symbols": ["HK.00700", "US.AAPL"]
}
```

响应：

```json
{
  "ret_code": 0,
  "ret_msg": "订阅成功，开始接收SSE推送",
  "data": { "client_id": "fe-123", "symbols": ["HK.00700", "US.AAPL"] }
}
```

说明：
- 若需变更订阅列表，可再次调用本接口覆盖绑定（当前版本未提供取消订阅API）。

#### 3.2 SSE 推送接口

请求：

```
GET /api/stream/sse?client_id=fe-123
```

事件类型与数据：

```json
// event: welcome
// data: { "type": "welcome", "client_id": "fe-123", "timestamp": 1730000000.0 }

// event: heartbeat
// data: { "ts": 1730000015.0 }

// event: quote
// data: {
//   "type": "quote",
//   "code": "HK.00700",
//   "quote": { /* 实时报价字段，取决于富途返回 */ },
//   "timestamp": 1730000001.2
// }
```

---

### 4. 原生浏览器接入示例（含中文注释）

```html
<script>
  // 生成唯一 client_id（示例：使用时间戳+随机数；生产可用用户ID/TabID）
  const clientId = `fe-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  // 1) 先发起订阅，绑定 client_id 与标的列表
  async function subscribeSymbols(symbols) {
    await fetch('http://127.0.0.1:8002/api/quote/subscribe_push', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId, symbols })
    });
  }

  // 2) 建立 SSE 连接，单播接收本 client_id 的推送
  function connectSSE() {
    const es = new EventSource(`http://127.0.0.1:8002/api/stream/sse?client_id=${clientId}`);

    // 欢迎事件：可用于初始化状态
    es.addEventListener('welcome', (e) => {
      const data = JSON.parse(e.data);
      console.log('[welcome]', data);
    });

    // 报价事件：更新指定股票的实时UI
    es.addEventListener('quote', (e) => {
      const payload = JSON.parse(e.data);
      // payload: { type, code, quote, timestamp }
      console.log('[quote]', payload.code, payload.quote);
      // TODO: 根据 code 定位到页面对应的组件进行刷新
    });

    // 心跳事件：可用于显示连接状态
    es.addEventListener('heartbeat', (e) => {
      console.log('[heartbeat]', e.data);
    });

    es.onerror = () => {
      console.warn('SSE 连接异常，浏览器将自动尝试重连');
    };

    return es; // 返回 EventSource 实例，便于上层关闭连接
  }

  // 示例：订阅并连接
  (async () => {
    await subscribeSymbols(['HK.00700', 'US.AAPL']);
    window.es = connectSSE();
  })();
</script>
```

---

### 5. React 接入示例（含中文注释）

```tsx
// React + TypeScript 示例
// 说明：在组件挂载时订阅标的，并建立 SSE 连接；卸载时释放连接。

import { useEffect, useRef } from 'react';

type QuotePayload = {
  type: 'quote';
  code: string;
  quote: Record<string, any>;
  timestamp: number;
};

const BASE_URL = 'http://127.0.0.1:8002';

export function useRealtimeQuotes(clientId: string, symbols: string[], onQuote: (p: QuotePayload) => void) {
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let closed = false;

    async function start() {
      // 先绑定订阅
      await fetch(`${BASE_URL}/api/quote/subscribe_push`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: clientId, symbols })
      });

      if (closed) return;

      // 建立 SSE 连接
      const es = new EventSource(`${BASE_URL}/api/stream/sse?client_id=${clientId}`);
      esRef.current = es;

      es.addEventListener('quote', (e) => {
        try {
          const payload = JSON.parse((e as MessageEvent).data) as QuotePayload;
          onQuote && onQuote(payload);
        } catch {}
      });

      es.addEventListener('heartbeat', () => {
        // 可选：更新连接状态
      });

      es.onerror = () => {
        // 浏览器默认会自动重连；如需更强重连策略，可在这里手动 close 并延迟重连
        console.warn('SSE error');
      };
    }

    start();

    return () => {
      closed = true;
      esRef.current?.close();
    };
  }, [clientId, JSON.stringify(symbols)]);
}

// 用法示例：
// const clientId = useMemo(() => genClientId(), []);
// useRealtimeQuotes(clientId, ['HK.00700', 'US.AAPL'], (p) => updateUI(p));
```

---

### 6. 稳健性与重连策略

- **先订阅后连接**：必须先 POST 订阅，再建立 SSE；否则可能只收到心跳没有报价。
- **唯一 client_id**：多标签页请使用不同的 `client_id`，避免消息路由冲突。
- **断线重连**：
  - 浏览器原生 EventSource 会自动重连；
  - 为更稳健，可在 `onerror` 中执行自定义策略：指数退避（1s/2s/4s/8s）后重建连接；
  - 重连前可重新调用订阅接口，确保订阅列表已同步。
- **空行情场景**：休市或 OpenD 侧无返回时，可能长时间仅有心跳，无 `quote` 事件。
- **性能建议**：在前端维护 `code -> latestQuote` 的 Map，落地 UI 增量刷新；避免全量列表重渲染。

---

### 7. TypeScript 类型参考

```ts
// 供前端项目复用的基础类型（可拷贝到前端代码库）

export type SubscribeRequest = {
  client_id: string;         // 前端唯一标识，建议：用户ID或TabID
  symbols: string[];         // 订阅的标的数组，例如：['HK.00700', 'US.AAPL']
};

export type WelcomeEvent = {
  type: 'welcome';
  client_id: string;
  timestamp: number;
};

export type HeartbeatEvent = { ts: number };

export type QuoteEvent = {
  type: 'quote';
  code: string;              // 例如：'HK.00700'
  quote: Record<string, any>;// 实时报价字典（字段取决于后端返回）
  timestamp: number;
};

export type SSEEvent = WelcomeEvent | QuoteEvent | HeartbeatEvent;
```

---

### 8. 常见问题（FAQ）

- 只收到心跳没收到报价？
  - 确保先调用了订阅接口；
  - 检查 `/health` 中 `futu_connected` 是否为 `true`；
  - 确认标的代码格式正确（如 `HK.00700`、`US.AAPL`）。

- 如何变更订阅标的？
  - 重新调用 `POST /api/quote/subscribe_push`，传入新的 `symbols` 列表；
  - 服务端会覆盖旧的订阅映射，后续推送只包含新列表内的标的。

- 多标签页如何处理？
  - 每个标签页使用不同的 `client_id`；
  - 如果需要账号级广播，可自行在前端桥接，将同账号多个标签页的 `quote` 聚合。

---

### 9. 本地联调清单

```bash
# 1) 启动服务
python main_enhanced_simple_alternative.py

# 2) 健康检查
curl http://127.0.0.1:8002/health

# 3) 订阅
curl -X POST http://127.0.0.1:8002/api/quote/subscribe_push \
  -H "Content-Type: application/json" \
  -d '{"client_id":"fe-123","symbols":["HK.00700","US.AAPL"]}'

# 4) 建立 SSE（终端观察）
curl -N "http://127.0.0.1:8002/api/stream/sse?client_id=fe-123"
```

---

### 11. 实时增量分析与历史合并策略（含 LLM 选择）

目标：当收到股票价格变动的推送（quote 事件）时，基于“增量”进行快速判断，结合历史分析记录（如果有），输出“最新的信息依据 + 操作建议等级”，若判断需要补充信息则提示并通过接口拉取更多数据再二次判断。

核心策略与流程：

1) 关注列表与订阅
   - 前端维护关注列表（watchlist）。新增关注的股票自动调用“订阅接口”绑定到当前 client_id。
   - 开市期间对关注列表内的标的进行实时分析与保存；闭市期间可暂停分析或以低频模式运行（可通过市场状态接口判断）。

2) 增量分析触发点
   - 每次收到 quote 事件，对比上一次同标的的报价快照，计算增量（例如：价格变动幅度、成交量变化、盘口变化等）。
   - 无历史快照时，执行基线分析并保存。

3) 历史分析合并
   - 通过后端接口获取该标的最近 N 条历史分析（若无则跳过）。
   - 将“最新增量 + 最近历史判断摘要”作为上下文输入 LLM，得到当前结论与建议等级。

4) LLM 决策与信息补充
   - LLM 模型可选：DeepSeek、kimi、豆包。通过接口传参 model 实现动态选择。
   - LLM 输出包含：
     - 最新依据（latest_basis）：解释为何给当前结论
     - 操作建议等级（level）：'urgent' | 'consider' | 'observe'
     - 是否需要更多信息（need_more_info）：boolean
     - 信息请求清单（info_requests）：例如 ['news', 'filings', 'calendar', 'tech', 'macro']
   - 若 need_more_info=true，前端调用后端信息拉取接口（见第13节），得到补充数据后再次调用 LLM 复评，形成最终结论。

5) 保存与UI呈现
   - 将最终分析结果保存（后端接口），便于历史回溯与后续合并。
   - 主页面按等级分三类展示：紧急（urgent）、考虑（consider）、观望（observe），其中紧急项采用“强推”（大字号/置顶/提示条/铃铛提醒等）。

6) 对信息来源更新的提示
   - 当 LLM 判断信息迟滞或有关键数据缺失时，返回 need_more_info=true 并给出 info_requests。
   - 前端根据返回进行显式提示（如黄色条“建议补充最新财报/新闻”），或自动调用对应接口拉取最新数据后复评。

推荐类型与接口契约

```ts
// TypeScript 参考类型

export type AnalysisLevel = 'urgent' | 'consider' | 'observe';

export type InfoType =
  | 'news'        // 实时新闻
  | 'filings'     // 财报/公告
  | 'calendar'    // 交易日/财报日程
  | 'tech'        // 技术指标
  | 'macro';      // 宏观信息

export type AnalysisRecord = {
  id?: string;
  code: string;
  timestamp: number;
  llm_model: 'deepseek' | 'kimi' | 'doubao';
  latest_basis: string;          // 最新信息依据（给出简明解释）
  level: AnalysisLevel;          // 操作建议等级
  need_more_info?: boolean;      // 是否需要补充信息
  info_requests?: InfoType[];    // 请求的补充信息类型
  used_sources?: string[];       // 实际使用的信息来源（可选）
  deltas?: Record<string, any>;  // 此次分析的增量字段（例如价格涨跌幅等）
};

export type LLMAnalyzeRequest = {
  model: 'deepseek' | 'kimi' | 'doubao';
  code: string;
  latestQuote: Record<string, any>;
  deltas?: Record<string, any>;
  history?: AnalysisRecord[];       // 最近分析记录
  extraInfo?: Record<string, any>;  // 拉取到的额外信息（news/filings/...）
  goal?: string;                    // 可选：分析目标偏好，如“短线风险控制”
};

export type LLMAnalyzeResponse = {
  latest_basis: string;
  level: AnalysisLevel;
  need_more_info?: boolean;
  info_requests?: InfoType[];
};
```

前端分析管线示例（React/TS）

```tsx
import { useMemo, useRef, useState } from 'react';
import { useRealtimeQuotes } from './useRealtimeQuotes'; // 参考第5节中的 SSE Hook

const BASE_URL = 'http://127.0.0.1:8002';

async function fetchAnalysisHistory(code: string, limit = 20) {
  const res = await fetch(`${BASE_URL}/api/analysis/history?code=${encodeURIComponent(code)}&limit=${limit}`);
  return (await res.json()) as { ret_code: number; data: AnalysisRecord[] };
}

async function fetchExtraInfo(code: string, types: InfoType[]) {
  const res = await fetch(`${BASE_URL}/api/info/fetch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, types })
  });
  return (await res.json()) as { ret_code: number; data: Record<string, any> };
}

async function analyzeWithLLM(req: LLMAnalyzeRequest) {
  const res = await fetch(`${BASE_URL}/api/llm/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req)
  });
  return (await res.json()) as { ret_code: number; data: LLMAnalyzeResponse };
}

async function saveAnalysis(record: AnalysisRecord) {
  await fetch(`${BASE_URL}/api/analysis/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record)
  });
}

type Categorized = {
  urgent: AnalysisRecord[];
  consider: AnalysisRecord[];
  observe: AnalysisRecord[];
};

export function useAnalysisEngine(
  clientId: string,
  watchlist: string[],
  llmModel: 'deepseek' | 'kimi' | 'doubao'
) {
  const [categorized, setCategorized] = useState<Categorized>({ urgent: [], consider: [], observe: [] });
  const lastQuoteRef = useRef<Map<string, Record<string, any>>>(new Map());

  useRealtimeQuotes(clientId, watchlist, async (p) => {
    const { code, quote } = p;

    // 1) 计算增量
    const last = lastQuoteRef.current.get(code) || {};
    const deltas = computeDeltas(last, quote);
    lastQuoteRef.current.set(code, quote);

    // 2) 拉取历史分析
    const histRes = await fetchAnalysisHistory(code, 20);
    const history = histRes?.data || [];

    // 3) 首次 LLM 判断
    const r1 = await analyzeWithLLM({
      model: llmModel,
      code,
      latestQuote: quote,
      deltas,
      history,
      goal: '以短线为主，关注剧烈波动与公告事件'
    });

    let finalResp = r1?.data;
    let extraInfo: Record<string, any> | undefined;

    // 4) 如需补充信息，调用信息拉取接口并复评
    if (finalResp?.need_more_info && finalResp.info_requests?.length) {
      const infoRes = await fetchExtraInfo(code, finalResp.info_requests);
      extraInfo = infoRes?.data;

      const r2 = await analyzeWithLLM({
        model: llmModel,
        code,
        latestQuote: quote,
        deltas,
        history,
        extraInfo
      });
      finalResp = r2?.data || finalResp;
    }

    // 5) 形成并保存分析记录
    const record: AnalysisRecord = {
      code,
      timestamp: Date.now(),
      llm_model: llmModel,
      latest_basis: finalResp?.latest_basis || '无',
      level: finalResp?.level || 'observe',
      need_more_info: finalResp?.need_more_info,
      info_requests: finalResp?.info_requests,
      deltas
    };
    await saveAnalysis(record);

    // 6) UI 分类并“强推”紧急项
    setCategorized((prev) => {
      const next: Categorized = { urgent: [], consider: [], observe: [] };
      for (const lvl of ['urgent', 'consider', 'observe'] as const) {
        next[lvl] = [...prev[lvl]];
      }
      next[record.level].unshift(record);

      // 可选：对 urgent 做强提醒（如 toast/modal/铃铛）
      if (record.level === 'urgent') {
        strongPush(record);
      }
      return next;
    });
  });

  return { categorized };
}

// 计算增量（示意）
function computeDeltas(last: Record<string, any>, curr: Record<string, any>) {
  const deltas: Record<string, any> = {};
  if (last.price != null && curr.price != null) {
    const change = curr.price - last.price;
    const pct = last.price ? change / last.price : null;
    deltas.price_change = change;
    deltas.price_change_pct = pct;
  }
  if (last.volume != null && curr.volume != null) {
    deltas.volume_diff = curr.volume - last.volume;
  }
  // 可扩展更多字段（bid/ask/spread/turnover 等）
  return deltas;
}

// 紧急“强推”示意
function strongPush(record: AnalysisRecord) {
  // 例如：显示置顶红条、通知提醒、声音提示等
  console.warn('URGENT:', record.code, record.latest_basis);
}
```

主页面分区与排序建议

- 展示结构：三栏或三卡片区域（紧急/考虑/观望）；每栏按时间倒序或“紧急度打分”排序。
- 强推策略：紧急项优先置顶展示 + 弹窗/Toast；当紧急项消化后可降级进入“考虑”或“观望”。
- 操作建议文案模板：短、准、可执行，例如：“受盘前财报影响，短线波动加剧，建议观望；若突破 X 元则考虑轻仓”。

---

### 12. 关注列表与开市期间自动分析保存

关注列表管理建议

- 新增关注：前端将 code 加入 watchlist，并调用“订阅接口”绑定当前 client_id 的推送标的。
- 移除关注：将 code 从 watchlist 移除，重新调用订阅接口覆盖绑定。
- watchlist 可选持久化：本地存储（localStorage）或后端保存账号级关注列表（可选接口见第13节）。

开市期间自动分析

- 通过后端“市场状态接口”判断是否开市（is_open）。
- 若开市则启用分析管线（useAnalysisEngine），闭市则降频或暂停。

接口调用示例（判断开市）

```ts
async function isMarketOpen() {
  const res = await fetch(`${BASE_URL}/api/market/status`);
  const data = await res.json();
  return !!data?.data?.is_open;
}
```

---

### 13. 服务器新增接口需求文档（供 futu 侧实现）

说明：为满足“增量分析 + 历史合并 + 信息补充 + LLM 决策 + 自动保存 + 强推”的前端体验，需要以下后端接口支持。若可由前端自行实现，可按需恢复到前端；但建议由后端统一聚合以便鉴权、限流与密钥保护。

1) 市场状态
- GET /api/market/status
- Response:
```json
{
  "ret_code": 0,
  "data": {
    "is_open": true,
    "session": "regular",          // 例如：pre/regular/after
    "market": "HK|US|CN",
    "server_time": 1730000000.0
  }
}
```

2) 分析历史查询
- GET /api/analysis/history?code=HK.00700&limit=20
- Response:
```json
{
  "ret_code": 0,
  "data": [ /* AnalysisRecord[]，见第11节类型定义 */ ]
}
```

3) 分析结果保存
- POST /api/analysis/save
- Body: AnalysisRecord
- Response:
```json
{ "ret_code": 0, "ret_msg": "ok", "data": { "id": "rec_123" } }
```

4) 信息来源拉取（补充数据）
- POST /api/info/fetch
- Body:
```json
{ "code": "HK.00700", "types": ["news", "filings", "calendar", "tech", "macro"] }
```
- Response:
```json
{
  "ret_code": 0,
  "data": {
    "news": [ /* 新闻摘要列表 */ ],
    "filings": [ /* 最近公告/财报关键点 */ ],
    "calendar": { /* 财报日程/停牌信息等 */ },
    "tech": { /* 指标，如RSI/MACD/MA交叉等 */ },
    "macro": { /* 相关宏观信息摘要 */ }
  }
}
```

5) LLM 分析聚合（保护密钥，统一路由）
- POST /api/llm/analyze
- Body: LLMAnalyzeRequest（含 model: 'deepseek' | 'kimi' | 'doubao'）
- 行为：
  - 根据 model 路由到对应大模型服务
  - 注入统一的系统指令，确保输出包含 latest_basis / level / need_more_info / info_requests
  - 可加入审计与速率限制
- Response:
```json
{
  "ret_code": 0,
  "data": {
    "latest_basis": "受盘中公告影响，成交量显著放大...",
    "level": "urgent",
    "need_more_info": true,
    "info_requests": ["filings", "news"]
  }
}
```

6) 关注列表（账号级，选配）
- GET /api/watchlist?client_id=fe-123
- POST /api/watchlist/set
```json
{ "client_id": "fe-123", "codes": ["HK.00700","US.AAPL"] }
```
- 服务端可在变更后自动调用内部逻辑绑定 SSE 路由，或要求前端仍调用现有的订阅接口覆盖绑定。

7) 信息源更新状态（选配）
- GET /api/info/source_status?code=HK.00700
- Response:
```json
{
  "ret_code": 0,
  "data": {
    "news_last_ts": 1730000000.0,
    "filings_last_ts": 1730000000.0,
    "calendar_last_ts": 1729999000.0,
    "tech_last_ts": 1730000000.0,
    "macro_last_ts": 1729980000.0,
    "stale": ["macro"] // 过期或未拉取的来源
  }
}
```

鉴权与限流建议
- 鉴权方式：Cookie/Token/签名，沿用现有生产策略。
- 限流策略：对 /api/llm/analyze 与 /api/info/fetch 设置每账号/每 IP 的速率限制。
- 合规与审计：对 LLM 请求与返回进行审计记录，包括模型类型与成本。

本地联调建议（在原清单基础上补充）
```bash
# 拉取市场状态
curl http://127.0.0.1:8002/api/market/status

# 查询历史分析
curl "http://127.0.0.1:8002/api/analysis/history?code=HK.00700&limit=5"

# 保存分析记录
curl -X POST http://127.0.0.1:8002/api/analysis/save \
  -H "Content-Type: application/json" \
  -d '{"code":"HK.00700","timestamp":1730000000,"llm_model":"deepseek","latest_basis":"示例","level":"consider"}'

# 拉取补充信息
curl -X POST http://127.0.0.1:8002/api/info/fetch \
  -H "Content-Type: application/json" \
  -d '{"code":"HK.00700","types":["news","filings"]}'

# 调用 LLM 聚合
curl -X POST http://127.0.0.1:8002/api/llm/analyze \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek","code":"HK.00700","latestQuote":{"price":320},"deltas":{"price_change":3}}'
```
- ... existing code ...

### 10. 安全与上线建议
- 在生产环境为 SSE 与订阅接口加上鉴权（Cookie/Token/签名）
- 为 `client_id` 做合法性校验，避免被随意冒用
- 通过反向代理（Nginx）启用 `X-Accel-Buffering: no`，关闭缓冲
- 若存在高并发，可在前端聚合 UI 刷新（节流/去抖），减少渲染压力


