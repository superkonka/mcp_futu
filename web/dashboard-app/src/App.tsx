import { useEffect, useMemo, useRef, useState } from 'react'
import type { CandlestickData, HistogramData, UTCTimestamp } from 'lightweight-charts'
import KLineChart from './components/KLineChart'

const DASHBOARD_MODULES = ['core', 'signals', 'recommendations', 'capital', 'kline'] as const
type DashboardModule = (typeof DASHBOARD_MODULES)[number]

type ModuleStatus = {
  loading: boolean
  error: string | null
}

type ModuleStatusMap = Record<DashboardModule, ModuleStatus>

const createModuleStatusMap = (): ModuleStatusMap =>
  DASHBOARD_MODULES.reduce(
    (acc, module) => {
      acc[module] = { loading: false, error: null }
      return acc
    },
    {} as ModuleStatusMap
  )

interface QuoteDetail {
  code?: string
  name?: string
  price?: number
  last_price?: number
  close?: number
  change_rate?: number
  change_value?: number
  open?: number
  high?: number
  low?: number
  prev_close?: number
  volume?: number
  turnover?: number
  update_time?: string
}

interface FundamentalAnalysis {
  sentiment?: 'bullish' | 'bearish' | 'neutral'
  confidence?: number
  impact_horizon?: string
  volatility_bias?: string
  themes?: string[]
  risk_factors?: string[]
  opportunity_factors?: string[]
  summary?: string
  action_hint?: string
  event_type?: string
  effectiveness?: string
  impact_score?: number
  novelty_score?: number
  magnitude_score?: number
  duration_days?: number
  market_sensitivity?: string
  trigger_conditions?: string[]
  historical_response?: {
    avg_return?: number
    avg_duration_days?: number
  }
  analysis_provider?: string
}

interface SignalItem {
  title?: string
  snippet?: string
  source?: string
  url?: string
  publish_time?: string
  published_at?: string
  sentiment?: string
  analysis?: FundamentalAnalysis
}

interface SignalMap {
  bullish?: SignalItem[]
  bearish?: SignalItem[]
  neutral?: SignalItem[]
  daily_metrics?: DailyMetric[]
}

interface DailyMetric {
  date: string
  bullish: number
  bearish: number
  neutral: number
  score: number
  weighted_score?: number
}

type TimelineNewsItem = SignalItem & {
  code?: string
  sentiment: 'bullish' | 'bearish' | 'neutral'
  timestamp: number
}

interface TimelineGroup {
  key: string
  displayDate: string
  weekday: string
  metric?: DailyMetric
  items: TimelineNewsItem[]
}

type SentimentFilter = 'all' | 'bullish' | 'bearish' | 'neutral'
interface RecommendationItem {
  id?: number
  action?: string
  rationale?: string
  confidence?: number
  timeframe?: string
  created_at?: string
  adopted?: boolean
  source?: string
  tags?: string[]
  entry_price?: number
  target_price?: number
  stop_loss?: number
  valid_until?: string
  eval_status?: string
  eval_pnl_pct?: number
  eval_summary?: string
  eval_generated_at?: string
  analysis_context?: Record<string, any>
  model_results?: MultiModelModelResult[]
  judge_result?: MultiModelJudgeResult
  eval_detail?: any
  status?: string
  monitor_config?: Record<string, any>
}

interface StrategyEvaluationRecord {
  id: number
  created_at: string
  summary?: string
  pnl?: number
  detail?: any
  models?: string[]
  judge_model?: string
}

interface StrategyAlertRecord {
  id: number
  alert_type: string
  level?: string
  message?: string
  payload?: any
  created_at: string
}

interface CapitalFlowSummary {
  overall_trend?: string
  main_trend?: string
  latest_net_inflow?: number
  latest_main_inflow?: number
  latest_time?: string
}

interface CapitalFlowData {
  summary?: CapitalFlowSummary
}

interface CapitalDistributionSummary {
  overall_trend?: string
  total_net_inflow?: number
  large_funds_trend?: string
  large_funds_net_inflow?: number
  dominant_fund_type?: string
  dominant_fund_amount?: number
  update_time?: string
  breakdown?: {
    super_net?: number
    big_net?: number
    mid_net?: number
    small_net?: number
  }
}

interface CapitalDistributionData {
  summary?: CapitalDistributionSummary
}

type ApiResponse<T> = {
  ret_code: number
  ret_msg?: string
  data?: T
}

interface SessionWindow {
  market: string
  open_time: string
  close_time: string
  break_start?: string
  break_end?: string
  previous_close?: number
}

type HoldingInfo = Record<string, string>

type HistoryPoint = {
  ts?: number
  price?: number | string
}

type KLinePoint = {
  time_key: string
  open?: number | string | null
  high?: number | string | null
  low?: number | string | null
  close?: number | string | null
  volume?: number | string | null
  turnover?: number | string | null
}

interface DashboardData {
  code: string
  session?: {
    session_id: string
    nickname?: string
    created_at?: string
  }
  quote?: QuoteDetail
  signals?: SignalMap
  recommendations?: RecommendationItem[]
  holding?: HoldingInfo | null
  capital_flow?: CapitalFlowData | null
  capital_distribution?: CapitalDistributionData | null
  history?: HistoryPoint[]
  history_kline?: KLinePoint[]
  session_window?: SessionWindow
}

interface SessionItem {
  session_id: string
  code: string
  nickname?: string | null
  created_at: string
  quote?: QuoteDetail
  strategy?: string
  last_signal_time?: string
}

interface MultiModelAction {
  action?: string
  rationale?: string
  confidence?: number
  timeframe?: string
  entry_price?: number
  target_price?: number
  stop_loss?: number
  position_sizing?: string
  tags?: string[]
  risk_items?: string[]
  opportunity_items?: string[]
  conditions?: string[]
  missing_conditions?: string[]
  data_gaps?: string[]
  basis?: string[]
}

interface MultiModelModelResult {
  model: string
  status: string
  duration?: number
  result?: MultiModelAction | Record<string, unknown>
  raw_text?: string
  error?: string
  context_snapshot?: Record<string, any>
}

interface MultiModelJudgeResult {
  model: string
  status: string
  result?: {
    recommended?: MultiModelAction
    summary?: string
    risk_notes?: string[]
    opportunity_notes?: string[]
    deciding_factors?: string[]
    referenced_models?: { model: string; weight?: string; confidence?: number }[]
    warnings?: string[]
    status?: string
  }
  raw_text?: string
  error?: string
  context_snapshot?: Record<string, any>
}

interface MultiModelAnalysisResponse {
  code: string
  models: MultiModelModelResult[]
  judge?: MultiModelJudgeResult
  started_at?: string
  finished_at?: string
  context_snapshot?: Record<string, any>
  snapshot?: Record<string, any>
}

interface QuotaInfo {
  total_used?: number
  remain?: number
  own_used?: number
  raw?: Record<string, unknown>
}

type StreamStatus = 'idle' | 'connecting' | 'connected' | 'disconnected'

interface StreamPayload {
  code?: string
  timestamp?: string | number
  quote?: QuoteDetail
  rt_data?: Array<Record<string, unknown>>
  kline?: Array<Record<string, unknown>>
}

const toNumeric = (value: unknown): number | null => {
  if (value === null || value === undefined) return null
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }
  if (typeof value === 'string') {
    const num = Number(value)
    return Number.isFinite(num) ? num : null
  }
  return null
}

const parseTimeToUtcSeconds = (value?: string): number | null => {
  if (!value) return null
  const [datePart, timePart] = value.trim().split(/[ T]/)
  if (!datePart || !timePart) return null
  const [year, month, day] = datePart.split(/[./-]/).map((v) => Number(v))
  const [hour, minute, second] = timePart.split(':').map((v) => Number(v))
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null
  const utc = Date.UTC(year, (month || 1) - 1, day, hour || 0, minute || 0, second || 0)
  return Math.floor(utc / 1000)
}

const parseIsoToSeconds = (value?: string): number | null => {
  if (!value) return null
  const ms = Date.parse(value)
  if (Number.isNaN(ms)) return null
  return Math.floor(ms / 1000)
}

const parseLooseJsonText = (value?: string | null): Record<string, any> | null => {
  if (!value) return null
  let normalized = value.trim()
  if (normalized.startsWith('```')) {
    const parts = normalized.split('```')
    if (parts.length >= 3) {
      normalized = parts[1]
    } else {
      normalized = normalized.replace(/`/g, '')
    }
  }
  normalized = normalized.trim()
  const attemptParse = (input: string) => {
    try {
      return JSON.parse(input)
    } catch (err) {
      return null
    }
  }
  const direct = attemptParse(normalized)
  if (direct) return direct
  const start = normalized.indexOf('{')
  const end = normalized.lastIndexOf('}')
  if (start !== -1 && end !== -1 && end > start) {
    const candidate = normalized.slice(start, end + 1)
    return attemptParse(candidate) || attemptParse(candidate.replace(/'/g, '"'))
  }
  return null
}

const formatPlainText = (text?: string | null) => {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

const normalizeSentiment = (value?: string | null): 'bullish' | 'bearish' | 'neutral' => {
  if (!value) return 'neutral'
  const lower = value.toString().trim().toLowerCase()
  if (['bullish', '利好', '看多', '多头', 'positive'].includes(lower)) return 'bullish'
  if (['bearish', '利空', '看空', '空头', 'negative'].includes(lower)) return 'bearish'
  return 'neutral'
}

const toStringArray = (value?: unknown): string[] => {
  if (!value) return []
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') return item.trim()
        if (typeof item === 'number' && Number.isFinite(item)) return item.toString()
        return ''
      })
      .filter(Boolean)
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed ? [trimmed] : []
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return [value.toString()]
  }
  return []
}

const normalizeKLineRecords = (records: Array<Record<string, unknown>> | undefined): KLinePoint[] => {
  if (!Array.isArray(records)) return []
  const normalized: KLinePoint[] = []
  for (const raw of records) {
    const record = raw as Record<string, unknown>
    const rawTime =
      (record.time_key as string) ||
      (record.timeKey as string) ||
      (record.time as string) ||
      (record.timestamp as string) ||
      ''
    if (!rawTime) continue
    const open = toNumeric(record.open ?? record.open_price ?? record.Open)
    const high = toNumeric(record.high ?? record.high_price ?? record.High)
    const low = toNumeric(record.low ?? record.low_price ?? record.Low)
    const close = toNumeric(record.close ?? record.cur_price ?? record.last_price ?? record.Close)
    if (open === null || high === null || low === null || close === null) continue
    const volume = toNumeric(record.volume ?? record.Volume ?? record.turnover ?? record.Turnover)
    normalized.push({
      time_key: rawTime,
      open,
      high,
      low,
      close,
      volume,
      turnover: toNumeric(record.turnover ?? record.Turnover)
    })
  }
  return normalized.sort((a, b) => {
    const aTime = parseTimeToUtcSeconds(a.time_key) || 0
    const bTime = parseTimeToUtcSeconds(b.time_key) || 0
    return aTime - bTime
  })
}

const buildCandlesFromPoints = (points: KLinePoint[]): CandlestickData[] => {
  const candles: CandlestickData[] = []
  for (const point of points) {
    const parsed = parseTimeToUtcSeconds(point.time_key)
    if (parsed === null) continue
    const toNumber = (value?: number | string | null) => {
      if (value === undefined || value === null) return null
      if (typeof value === 'number') return value
      const num = Number(value)
      return Number.isFinite(num) ? num : null
    }
    const open = toNumber(point.open)
    const high = toNumber(point.high)
    const low = toNumber(point.low)
    const close = toNumber(point.close)
    if ([open, high, low, close].some((num) => num === null)) continue
    candles.push({
      time: parsed as UTCTimestamp,
      open: open as number,
      high: high as number,
      low: low as number,
      close: close as number
    })
  }
  return candles
}

const mergeKlineSeries = (base: KLinePoint[], updates: KLinePoint[]): KLinePoint[] => {
  if (!updates.length) return base
  const map = new Map<string, KLinePoint>()
  for (const point of base) {
    map.set(point.time_key, { ...point })
  }
  for (const point of updates) {
    map.set(point.time_key, { ...map.get(point.time_key), ...point })
  }
  return Array.from(map.values()).sort((a, b) => {
    const aTime = parseTimeToUtcSeconds(a.time_key) || 0
    const bTime = parseTimeToUtcSeconds(b.time_key) || 0
    return aTime - bTime
  })
}

const normalizeVolumeSeries = (points: KLinePoint[]): Map<number, number> => {
  const sorted = [...points].sort((a, b) => {
    const aTime = parseTimeToUtcSeconds(a.time_key) || 0
    const bTime = parseTimeToUtcSeconds(b.time_key) || 0
    return aTime - bTime
  })
  const map = new Map<number, number>()
  let prevRawVolume: number | null = null
  let maybeCumulative = true
  for (const point of sorted) {
    const timestamp = parseTimeToUtcSeconds(point.time_key)
    if (timestamp === null) continue
    const rawVolume = toNumeric(point.volume) ?? 0
    let deltaVolume = rawVolume
    if (maybeCumulative && prevRawVolume !== null) {
      if (rawVolume >= prevRawVolume) {
        deltaVolume = rawVolume - prevRawVolume
      } else {
        maybeCumulative = false
        deltaVolume = rawVolume
      }
    }
    prevRawVolume = rawVolume
    map.set(timestamp, Math.max(deltaVolume, 0))
  }
  return map
}

const buildVolumeSeries = (points: KLinePoint[], candles: CandlestickData[]): HistogramData[] => {
  if (!points.length) return []
  const map = normalizeVolumeSeries(points)
  const volumes: HistogramData[] = []
  for (const candle of candles) {
    const value = map.get(candle.time as number)
    if (value == null) continue
    volumes.push({
      time: candle.time,
      value,
      color: candle.close >= candle.open ? '#16a34a' : '#dc2626'
    })
  }
  return volumes
}


const formatPrice = (value?: number | string | null, digits = 2) => {
  if (value === undefined || value === null) return '--'
  const numeric = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(numeric)) return '--'
  return Number(numeric).toFixed(digits)
}

const formatPercent = (value?: number | string | null) => {
  if (value === undefined || value === null) return '--'
  const numeric = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(numeric)) return '--'
  const prefix = numeric > 0 ? '+' : ''
  return `${prefix}${numeric.toFixed(2)}%`
}

const formatAmount = (value?: number | string | null) => {
  if (value === undefined || value === null) return '--'
  const numeric = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(numeric)) return '--'
  const abs = Math.abs(numeric)
  if (abs >= 1e8) {
    return `${(numeric / 1e8).toFixed(2)} 亿`
  }
  if (abs >= 1e4) {
    return `${(numeric / 1e4).toFixed(2)} 万`
  }
  return numeric.toFixed(0)
}

const strategyLabelMap: Record<string, string> = {
  BUY: '买入',
  SELL: '卖出',
  HOLD: '持有',
  WATCH: '观察',
  ADD: '加仓',
  REDUCE: '减仓',
  EXIT: '清仓'
}

const formatStrategyLabel = (value?: string | null) => {
  if (!value) return '未设置'
  const key = value.toUpperCase()
  return strategyLabelMap[key] || value
}

const getSessionDisplayName = (item: SessionItem) => {
  return item.nickname || item.quote?.name || item.code
}

const classifyStrategyState = (strategy?: string | null) => {
  const key = (strategy || '').toUpperCase()
  if (!key) {
    return {
      state: '未设置',
      badge: 'bg-slate-100 text-slate-600',
      tone: 'text-slate-500'
    }
  }
  if (key === 'WATCH') {
    return {
      state: '待采纳',
      badge: 'bg-amber-50 text-amber-700',
      tone: 'text-amber-600'
    }
  }
  if (key === 'SELL' || key === 'REDUCE' || key === 'EXIT') {
    return {
      state: '已结束',
      badge: 'bg-rose-50 text-rose-700',
      tone: 'text-rose-600'
    }
  }
  return {
    state: '执行中',
    badge: 'bg-emerald-50 text-emerald-700',
    tone: 'text-emerald-600'
  }
}

const formatDateTime = (value?: string) => {
  if (!value) return '--'
  let normalized = value
  if (!/[zZ]|[+\-]\d{2}:?\d{2}$/.test(value)) {
    normalized = value.includes('T') ? `${value}Z` : `${value.replace(' ', 'T')}Z`
  }
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

const formatDateLabel = (dateKey?: string) => {
  if (!dateKey || dateKey === 'unknown') {
    return { label: '未识别日期', weekday: '' }
  }
  const date = new Date(`${dateKey}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return { label: dateKey, weekday: '' }
  }
  const label = date.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
  const weekday = date.toLocaleDateString('zh-CN', { weekday: 'long' })
  return { label, weekday }
}

const formatChangeText = (rate?: number | string | null, changeValue?: number | string | null) => {
  if (rate === undefined && changeValue === undefined) {
    return '--'
  }
  const parts: string[] = []
  if (changeValue !== undefined && changeValue !== null) {
    const numeric = typeof changeValue === 'string' ? Number(changeValue) : changeValue
    if (Number.isFinite(numeric)) {
      const prefix = numeric >= 0 ? '+' : ''
      parts.push(`${prefix}${numeric.toFixed(2)}`)
    }
  }
  if (rate !== undefined && rate !== null) {
    const numeric = typeof rate === 'string' ? Number(rate) : rate
    if (Number.isFinite(numeric)) {
      const prefix = numeric >= 0 ? '+' : ''
      parts.push(`${prefix}${numeric.toFixed(2)}%`)
    }
  }
  return parts.length ? parts.join(' / ') : '--'
}

const getChangeColor = (value?: number | string | null) => {
  if (value === undefined || value === null) return 'text-slate-500'
  const numeric = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(numeric)) return 'text-slate-500'
  return numeric >= 0 ? 'text-emerald-500' : 'text-rose-500'
}

const formatPriceDelta = (delta: number) => {
  if (!Number.isFinite(delta) || delta === 0) {
    return null
  }
  const prefix = delta > 0 ? '+' : ''
  return `${prefix}${delta.toFixed(2)}`
}

const sentimentStyles = {
  bullish: {
    dot: 'bg-emerald-500',
    badge: 'bg-emerald-50 text-emerald-600',
    border: 'hover:border-emerald-200/80'
  },
  bearish: {
    dot: 'bg-rose-500',
    badge: 'bg-rose-50 text-rose-500',
    border: 'hover:border-rose-200/80'
  },
  neutral: {
    dot: 'bg-slate-400',
    badge: 'bg-slate-100 text-slate-500',
    border: 'hover:border-slate-200'
  }
} as const

const analysisProviderMeta: Record<string, { label: string; className: string }> = {
  deepseek: { label: 'LLM分析', className: 'bg-blue-50 text-blue-600 border border-blue-100' },
  fallback: { label: '关键词兜底', className: 'bg-amber-50 text-amber-700 border border-amber-100' },
  pending: { label: '待分析', className: 'bg-slate-50 text-slate-500 border border-slate-200' },
  fail: { label: '分析失败', className: 'bg-rose-50 text-rose-600 border border-rose-100' }
}

function renderInline(text: string): React.ReactNode {
  if (!text) return null
  const nodes: React.ReactNode[] = []
  let remaining = text
  const boldRe = /\*\*(.+?)\*\*/
  while (true) {
    const match = remaining.match(boldRe)
    if (!match) break
    const [full, inner] = match
    const idx = match.index ?? 0
    if (idx > 0) nodes.push(remaining.slice(0, idx))
    nodes.push(<strong key={`${nodes.length}-b`}>{inner}</strong>)
    remaining = remaining.slice(idx + full.length)
  }
  if (remaining) nodes.push(remaining)
  return nodes
}

function renderMarkdown(md: string) {
  if (!md) return null
  const lines = md.split(/\r?\n/)
  const blocks: React.ReactNode[] = []
  let list: string[] | null = null
  const flushList = () => {
    if (list && list.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="list-disc list-inside space-y-1 text-[13px] text-slate-800">
          {list.map((li, idx) => (
            <li key={idx}>{renderInline(li)}</li>
          ))}
        </ul>
      )
    }
    list = null
  }
  lines.forEach((line) => {
    const trimmed = line.trimEnd()
    if (!trimmed) {
      flushList()
      return
    }
    const heading = trimmed.match(/^(#{1,3})\s+(.*)$/)
    if (heading) {
      flushList()
      const level = heading[1].length
      const content = heading[2]
      const Tag = (`h${Math.min(level + 2, 6)}` as keyof JSX.IntrinsicElements) // use h3/h4/h5 for视觉
      blocks.push(
        <Tag key={`h-${blocks.length}`} className="font-semibold text-slate-900">
          {renderInline(content)}
        </Tag>
      )
      return
    }
    if (/^[-*+]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      list = list || []
      list.push(trimmed.replace(/^[-*+]\s+/, '').replace(/^\d+\.\s+/, ''))
      return
    }
    flushList()
    blocks.push(
      <p key={`p-${blocks.length}`} className="text-[13px] text-slate-800 leading-6">
        {renderInline(trimmed)}
      </p>
    )
  })
  flushList()
  return <div className="space-y-2">{blocks}</div>
}

// ===== Fundamental Center (独立页) =====
type FundamentalCenterProps = {
  navigateTo?: (url: string) => void
}

function FundamentalCenter({ navigateTo }: FundamentalCenterProps) {
  const [code, setCode] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('code') || ''
  })
  const [status, setStatus] = useState<'all' | 'pending' | 'fail' | 'done'>('all')
  const [startDate, setStartDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 3)
    return d.toISOString().slice(0, 10)
  })
  const [endDate, setEndDate] = useState(() => {
    return new Date().toISOString().slice(0, 10)
  })
  const [limit, setLimit] = useState(50)
  const [items, setItems] = useState<TimelineNewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reports, setReports] = useState<any[]>([])
  const [reportLoading, setReportLoading] = useState(false)
  const [reportGenerating, setReportGenerating] = useState<null | 'daily' | 'weekly'>(null)
  const [selectedReport, setSelectedReport] = useState<any | null>(null)
  const [watchlist, setWatchlist] = useState<Array<{ code: string; nickname?: string | null }>>([])
  const [newWatchCode, setNewWatchCode] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchStep, setSearchStep] = useState<'idle' | 'searching' | 'analyzing' | 'storing' | 'done'>('idle')
  const [batchAnalyzing, setBatchAnalyzing] = useState(false)
  const analyzedReports = useMemo(() => {
    return [...items]
      .filter((item) => {
        const provider = (item.analysis?.analysis_provider || '').toString().toLowerCase()
        const hasSentiment = !!item.analysis?.sentiment
        return provider && provider !== 'pending' && provider !== 'fail' && hasSentiment
      })
      .sort((a, b) => (parseNewsDate(b.publish_time || b.published_at) || 0) - (parseNewsDate(a.publish_time || a.published_at) || 0))
      .slice(0, 8)
  }, [items])

  const fetchList = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload: any = { code: code || undefined, limit }
      if (status !== 'all') payload.status = status
      if (startDate) payload.start_date = startDate
      if (endDate) payload.end_date = endDate
      const res = await fetch('/api/fundamental/news/list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!res.ok) throw new Error('加载失败')
      const json = (await res.json()) as ApiResponse<{ items: any[] }>
      if (json.ret_code !== 0) throw new Error(json.ret_msg || '加载失败')
      const list = json.data?.items || []
      const normalized: TimelineNewsItem[] = list.map((item: any) => {
        const sentiment = normalizeSentiment(item.analysis?.sentiment || item.sentiment || 'neutral')
        return {
          ...item,
          sentiment,
          timestamp: parseNewsDate(item.publish_time || item.published_at || item.last_seen)
        }
      })
      setItems(normalized)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const loadWatchlist = async () => {
      try {
        const res = await fetch('/api/dashboard/sessions')
        if (!res.ok) return
        const json = await res.json()
        const items = (json.sessions || []).map((s: any) => ({ code: s.code, nickname: s.nickname }))
        setWatchlist(items)
        if (!code && items.length) {
          setCode(items[0].code)
        }
      } catch (err) {
        console.warn('load watchlist failed', err)
      }
    }
    loadWatchlist()
  }, [])

  const handleAnalyzeNow = async (item: TimelineNewsItem) => {
    try {
      const res = await fetch('/api/fundamental/analyze_now', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: item.code || code,
          title: item.title,
          url: item.url,
          source: item.source,
          snippet: item.snippet,
          publish_time: item.publish_time || item.published_at
        })
      })
      const json = (await res.json()) as ApiResponse<{ analysis?: any }>
      if (!res.ok || json.ret_code !== 0) throw new Error(json.ret_msg || '触发分析失败')
      await fetchList()
      await fetchReports()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  const handleBatchAnalyze = async () => {
    if (batchAnalyzing) return
    const pendingItems = items.filter((item) => {
      const providerKey = (item.analysis?.analysis_provider || '').toString().toLowerCase()
      return providerKey === 'pending' || !item.analysis?.sentiment
    })
    if (!pendingItems.length) {
      alert('没有待分析的资讯')
      return
    }
    setBatchAnalyzing(true)
    try {
      for (const item of pendingItems) {
        await handleAnalyzeNow(item)
      }
    } finally {
      setBatchAnalyzing(false)
    }
  }

  const fetchReports = async () => {
    if (!code) return
    setReportLoading(true)
    try {
      const res = await fetch('/api/fundamental/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, limit: 20, offset: 0 })
      })
      const json = (await res.json()) as ApiResponse<{ items: any[] }>
      if (res.ok && json.ret_code === 0) {
        setReports(json.data?.items || [])
      }
    } catch (err) {
      console.warn('load reports failed', err)
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    fetchReports()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  const handleGenerateReport = async (period: 'daily' | 'weekly') => {
    if (!code) {
      alert('请先填写股票代码')
      return
    }
    try {
      setReportGenerating(period)
      const res = await fetch('/api/fundamental/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          stock_name: code,
          period,
          days: period === 'weekly' ? 7 : 3,
          limit: 30,
          source: 'manual'
        })
      })
      const json = (await res.json()) as ApiResponse<{ report?: string }>
      if (!res.ok || json.ret_code !== 0) throw new Error(json.ret_msg || '生成报告失败')
      await fetchReports()
      alert('报告已生成，可在列表查看')
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setReportGenerating(null)
    }
  }

  const handleAddWatch = () => {
    const c = newWatchCode.trim().toUpperCase()
    if (!c) return
    if (!watchlist.find((w) => w.code.toUpperCase() === c)) {
      setWatchlist((prev) => [...prev, { code: c }])
    }
    setCode(c)
    setNewWatchCode('')
  }

  const handleSearchCustom = async () => {
    const q = searchQuery.trim()
    if (!q) {
      alert('请输入搜索关键词')
      return
    }
    setSearchStep('searching')
    setSearchLoading(true)
    try {
      const res = await fetch('/api/fundamental/news/search_custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q, size: 20 })
      })
      const json = await res.json()
      if (!res.ok || json.ret_code !== 0) throw new Error(json.ret_msg || '搜索失败')
      const items = json.data?.results || json.data?.items || json.data?.data?.results || []
      setSearchResults(items)
      setSearchStep('analyzing')
      // 这里可以接后端分析/入库接口；暂用本地刷新兜底
      await fetchList()
      setSearchStep('storing')
      setSearchStep('done')
    } catch (err) {
      alert((err as Error).message)
      setSearchStep('idle')
    } finally {
      setSearchLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-4">
          <h1 className="text-2xl font-semibold text-slate-900">基础面中心</h1>
          <a href="/" className="text-blue-600 text-sm hover:underline">
            返回看板
          </a>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-6 space-y-4">
        <div className="rounded-2xl bg-white border border-slate-200 p-4 flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-slate-500">股票代码（关注/持仓）</label>
            <select
              className="mt-1 w-36 rounded border border-slate-200 px-2 py-1 text-sm"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            >
              <option value="">请选择</option>
              {watchlist.map((w) => (
                <option key={w.code} value={w.code}>
                  {w.code} {w.nickname ? `(${w.nickname})` : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500">状态</label>
            <select
              className="mt-1 rounded border border-slate-200 px-2 py-1 text-sm"
              value={status}
              onChange={(e) => setStatus(e.target.value as any)}
            >
              <option value="all">全部</option>
              <option value="pending">待分析</option>
              <option value="fail">分析失败</option>
              <option value="done">已分析</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500">起始日期</label>
            <input
              type="date"
              className="mt-1 rounded border border-slate-200 px-2 py-1 text-sm"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-slate-500">结束日期</label>
            <input
              type="date"
              className="mt-1 rounded border border-slate-200 px-2 py-1 text-sm"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-slate-500">数量</label>
            <input
              type="number"
              className="mt-1 w-20 rounded border border-slate-200 px-2 py-1 text-sm"
              value={limit}
              min={1}
              max={200}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
          </div>
          <button
            className="px-3 py-2 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50 text-sm"
            onClick={fetchList}
            disabled={loading}
          >
            {loading ? '加载中...' : '查询'}
          </button>
          <button
            className="px-3 py-2 rounded-full border border-amber-200 text-amber-700 hover:bg-amber-50 text-sm"
            onClick={handleBatchAnalyze}
            disabled={batchAnalyzing || items.length === 0}
            title="对当前列表中未分析/待分析的资讯批量触发LLM分析"
          >
            {batchAnalyzing ? '批量分析中...' : '批量触发分析'}
          </button>
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-slate-500">自定义新闻搜索</label>
            <div className="mt-1 flex gap-2">
              <input
                className="flex-1 rounded border border-slate-200 px-2 py-1 text-sm"
                placeholder="输入关键词，如 小米 汽车 基本面"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearchCustom()}
              />
              <button
                className="px-3 py-2 rounded-full border border-emerald-200 text-emerald-600 hover:bg-emerald-50 text-sm"
                onClick={handleSearchCustom}
                disabled={searchLoading}
              >
                {searchLoading ? '搜索中...' : '搜索'}
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(260px,0.8fr)] items-start">
          <div className="rounded-2xl bg-white border border-slate-200 p-4">
            {error && <div className="text-sm text-rose-500 mb-3">{error}</div>}
            {/* 自定义搜索进度 + 结果 */}
            <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div className="text-sm font-semibold text-slate-900">自定义搜索/入库流程</div>
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  {['searching', 'analyzing', 'storing', 'done'].map((s) => (
                    <span
                      key={s}
                      className={`px-2 py-0.5 rounded-full border ${
                        searchStep === s ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-400'
                      }`}
                    >
                      {s === 'searching' && '搜索中'}
                      {s === 'analyzing' && 'LLM分析'}
                      {s === 'storing' && '写入入库'}
                      {s === 'done' && '已完成'}
                    </span>
                  ))}
                  {searchStep === 'idle' && <span className="px-2 py-0.5 text-slate-400">等待搜索</span>}
                </div>
              </div>
              {searchResults.length > 0 ? (
                <div className="space-y-2">
                  {searchResults.map((r, idx) => (
                    <div key={idx} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="flex items-start gap-2">
                        <span className="text-[11px] text-slate-500 mt-0.5">{idx + 1}</span>
                        <div className="space-y-1 min-w-0">
                          <a
                            className="text-sm font-semibold text-slate-900 hover:text-blue-600 line-clamp-2"
                            href={r.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {r.title || '未命名'}
                          </a>
                          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                            {r.publish_time && <span>{formatDateTime(r.publish_time)}</span>}
                            {r.source && <span>{r.source}</span>}
                          </div>
                          {r.summary && <p className="text-xs text-slate-600 line-clamp-3">{r.summary}</p>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-400">未开始或暂无搜索结果。输入关键词后点击右侧“搜索”。</div>
              )}
            </div>

            {loading ? (
              <div className="text-sm text-slate-500">加载中...</div>
            ) : items.length === 0 ? (
              <div className="text-sm text-slate-400">暂无数据</div>
            ) : (
              <div className="space-y-3">
                {items.map((item, idx) => {
                  const sentiment = item.sentiment || 'neutral'
                  const sentimentKey = sentiment === 'bullish' || sentiment === 'bearish' ? sentiment : 'neutral'
                  const style = sentimentStyles[sentimentKey] || sentimentStyles.neutral
                  const providerKey = (item.analysis?.analysis_provider || '').toString().toLowerCase()
                  const providerMeta = analysisProviderMeta[providerKey]
                  const isPending = providerKey === 'pending' || (!item.analysis?.sentiment && !providerKey)
                  const isFail = providerKey === 'fail'
                  return (
                    <div key={`${item.url}-${idx}`} className={`rounded-xl border p-3 ${style.border}`}>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${style.badge}`}>
                          {sentimentKey === 'bullish' ? '利好' : sentimentKey === 'bearish' ? '利空' : '中性'}
                        </span>
                        <span>{formatDateTime(item.publish_time || item.published_at)}</span>
                        {item.source && <span>{item.source}</span>}
                        {providerMeta && <span className={`text-[11px] px-2 py-0.5 rounded-full ${providerMeta.className}`}>{providerMeta.label}</span>}
                      </div>
                      <div className="flex items-start gap-2">
                        <a
                          className="mt-2 block text-sm font-semibold text-slate-900 hover:text-blue-600"
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {item.title || '未命名资讯'}
                        </a>
                        {isPending && (
                          <button
                            className="ml-auto mt-2 text-[11px] px-2 py-1 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50"
                            onClick={() => handleAnalyzeNow(item)}
                          >
                            触发分析
                          </button>
                        )}
                        {isFail && (
                          <button
                            className="ml-auto mt-2 text-[11px] px-2 py-1 rounded-full border border-amber-200 text-amber-600 hover:bg-amber-50"
                            onClick={() => handleAnalyzeNow(item)}
                          >
                            重试分析
                          </button>
                        )}
                      </div>
                      {item.analysis?.summary && <p className="text-xs text-slate-600 mt-1">{item.analysis.summary}</p>}
                    </div>
                  )
                })}
              </div>
            )}
          </div>


          <aside className="rounded-2xl bg-white border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h4 className="text-sm font-semibold text-slate-900">基础面报告</h4>
                <p className="text-[11px] text-slate-500 mt-0.5">当前股票：{code || '未选择，请先输入并查询'}</p>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <button
                  className="px-2 py-1 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50"
                  onClick={() => handleGenerateReport('daily')}
                  disabled={!code || reportGenerating === 'daily'}
                >
                  {reportGenerating === 'daily' ? '生成中...' : '生成日报'}
                </button>
                <button
                  className="px-2 py-1 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50"
                  onClick={() => handleGenerateReport('weekly')}
                  disabled={!code || reportGenerating === 'weekly'}
                >
                  {reportGenerating === 'weekly' ? '生成中...' : '生成周报'}
                </button>
              </div>
            </div>
            {reportLoading ? <div className="text-xs text-slate-500">加载报告中...</div> : null}
            {reports.length === 0 ? (
              <div className="text-xs text-slate-400">{code ? '暂无报告，先点击生成日报/周报' : '请先输入股票代码并查询后再生成报告'}</div>
            ) : (
              <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                {reports.map((item) => (
                  <a
                    key={item.id}
                    className="w-full block text-left rounded-xl border border-slate-200 p-3 hover:border-blue-200"
                    href={`/fundamental-report?id=${item.id}`}
                    onClick={(e) => {
                      if (navigateTo) {
                        e.preventDefault()
                        navigateTo(`/fundamental-report?id=${item.id}`)
                      }
                    }}
                  >
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <div className="font-semibold text-slate-900 truncate mr-2">{item.title || `${item.code} ${item.date}`}</div>
                      <span>{item.date}</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1 line-clamp-3">{item.report}</p>
                  </a>
                ))}
              </div>
            )}
            <div className="pt-3 border-t border-slate-100 space-y-2">
              <div className="flex items-center justify-between">
                <h5 className="text-xs font-semibold text-slate-800">关注/持仓列表</h5>
                <span className="text-[11px] text-slate-400">点击切换</span>
              </div>
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded border border-slate-200 px-2 py-1 text-xs"
                  placeholder="输入代码关注，如 HK.01810"
                  value={newWatchCode}
                  onChange={(e) => setNewWatchCode(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddWatch()}
                />
                <button
                  className="px-2 py-1 rounded border border-blue-200 text-blue-600 text-xs hover:bg-blue-50"
                  onClick={handleAddWatch}
                >
                  关注
                </button>
              </div>
              <div className="space-y-1 max-h-[180px] overflow-y-auto">
                {watchlist.length === 0 ? (
                  <div className="text-[11px] text-slate-400">暂无关注/持仓，右侧输入添加</div>
                ) : (
                  watchlist.map((w) => (
                    <button
                      key={w.code}
                      className={`w-full flex items-center justify-between rounded-lg border px-2 py-1 text-xs ${
                        code === w.code ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-slate-200 hover:border-slate-300'
                      }`}
                      onClick={() => setCode(w.code)}
                    >
                      <span className="font-semibold truncate">{w.code}</span>
                      {w.nickname && <span className="text-[11px] text-slate-500 ml-2 truncate">{w.nickname}</span>}
                    </button>
                  ))
                )}
              </div>
            </div>
          </aside>
        </div>
      </main>
      {selectedReport && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">{selectedReport.title || `${selectedReport.code} ${selectedReport.date}`}</div>
                <div className="text-[11px] text-slate-500">
                  {selectedReport.date} · {selectedReport.period || 'daily'} · {selectedReport.items_used ? `引用 ${selectedReport.items_used} 条` : ''}
                </div>
              </div>
              <button
                className="text-slate-500 hover:text-slate-800 text-sm px-2 py-1"
                onClick={() => setSelectedReport(null)}
              >
                关闭
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[70vh]">
              <p className="text-sm leading-6 whitespace-pre-wrap text-slate-800">{selectedReport.report}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ===== 基础面报告详情页 =====
type ChatMessage = { role: 'user' | 'assistant'; content: string; kind?: 'report' }

function FundamentalReportPage() {
  const params = new URLSearchParams(window.location.search)
  const reportId = Number(params.get('id') || 0)
  const [report, setReport] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chatLog, setChatLog] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [chatting, setChatting] = useState(false)
  const [copyTip, setCopyTip] = useState<string | null>(null)
  const [selectedRefIds, setSelectedRefIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    const fetchReport = async () => {
      if (!reportId) {
        setError('缺少报告ID')
        return
      }
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/fundamental/report/${reportId}`)
        const json = (await res.json()) as ApiResponse<{ report: any }>
        if (!res.ok || json.ret_code !== 0) throw new Error(json.ret_msg || '加载失败')
        setReport(json.data?.report || null)
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setLoading(false)
      }
    }
    fetchReport()
  }, [reportId])

  const handleAsk = async () => {
    if (!question.trim() || !reportId) return
    const q = question.trim()
    setChatLog((prev) => [...prev, { role: 'user', content: q }])
    setQuestion('')
    setChatting(true)
    const refIds = Array.from(selectedRefIds).filter(Boolean)
    try {
      const res = await fetch('/api/fundamental/report/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_id: reportId, question: q, ref_ids: refIds })
      })
      const json = (await res.json()) as ApiResponse<{ answer: string }>
      if (!res.ok || json.ret_code !== 0) throw new Error(json.ret_msg || '提问失败')
      setChatLog((prev) => [...prev, { role: 'assistant', content: json.data?.answer || '' }])
    } catch (err) {
      setChatLog((prev) => [...prev, { role: 'assistant', content: `提问失败: ${(err as Error).message}` }])
    } finally {
      setChatting(false)
    }
  }

  const backUrl = '/fundamental'

  const combinedMessages = useMemo(() => {
    const arr: ChatMessage[] = []
    if (report) {
      arr.push({ role: 'assistant', content: report.report || '暂无报告内容', kind: 'report' })
    }
    return [...arr, ...chatLog]
  }, [report, chatLog])

  const references = useMemo(() => {
    return ((report?.meta?.references || []) as any[]).filter(Boolean)
  }, [report])

  useEffect(() => {
    if (!references.length) {
      setSelectedRefIds(new Set())
      return
    }
    const defaults = references.slice(0, 3).map((r) => String(r.ref_id || r.unique_key || r.id || ''))
    setSelectedRefIds(new Set(defaults))
  }, [references])

  const copyReport = async () => {
    if (!report?.report) return
    try {
      await navigator.clipboard.writeText(report.report)
      setCopyTip('已复制')
      setTimeout(() => setCopyTip(null), 1800)
    } catch (err) {
      setCopyTip('复制失败')
      setTimeout(() => setCopyTip(null), 1800)
    }
  }

  if (!reportId) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-500">
        缺少报告ID，<a className="text-blue-600 ml-2" href={backUrl}>返回基础面中心</a>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <a href={backUrl} className="text-blue-600 text-sm hover:underline">
              返回基础面中心
            </a>
            <h1 className="text-xl sm:text-2xl font-semibold text-slate-900">基础面报告</h1>
          </div>
          {report && (
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">{report.code}</span>
              {report.stock_name && <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">{report.stock_name}</span>}
              <span className="px-2 py-0.5 rounded-full border border-blue-100 bg-blue-50 text-blue-700">{report.period || 'daily'}</span>
              <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">{report.date}</span>
            </div>
          )}
        </div>
      </header>
      <main className="flex-1">
        {loading ? (
          <div className="max-w-3xl mx-auto px-4 py-8 text-slate-500 text-sm">加载中...</div>
        ) : error ? (
          <div className="max-w-3xl mx-auto px-4 py-8 text-rose-500 text-sm">{error}</div>
        ) : !report ? (
          <div className="max-w-3xl mx-auto px-4 py-8 text-slate-500 text-sm">未找到报告</div>
        ) : (
          <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
                <div className="space-y-1">
                  <div className="text-lg font-semibold text-slate-900">{report.title || `${report.code} ${report.date}`}</div>
                  <div className="text-xs text-slate-500 flex flex-wrap items-center gap-2">
                    <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">{report.code}</span>
                    {report.stock_name && <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">{report.stock_name}</span>}
                    <span className="px-2 py-0.5 rounded-full border border-blue-100 bg-blue-50 text-blue-700">{report.period || 'daily'}</span>
                    <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">{report.date}</span>
                    <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">引用 {report.items_used ?? '--'} 条</span>
                    {report.days ? <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">拉取 {report.days} 天</span> : null}
                    {report.size_limit ? <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">上限 {report.size_limit} 条</span> : null}
                    {report.source ? <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">来源 {report.source}</span> : null}
                    {report.created_at ? <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-50">{report.created_at.slice(0, 19).replace('T', ' ')}</span> : null}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <button
                    className="px-3 py-1.5 rounded-full border border-slate-200 hover:bg-slate-50"
                    onClick={copyReport}
                  >
                    复制全文
                  </button>
                  <a
                    className="px-3 py-1.5 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50"
                    href={backUrl}
                  >
                    返回
                  </a>
                </div>
              </div>

              {copyTip && <div className="text-xs text-blue-600 mt-2">{copyTip}</div>}

              <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-slate-900">引用点（可加入对话上下文）</div>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500">
                    <span>{selectedRefIds.size}/{references.length} 已选</span>
                    <button
                      className="px-2 py-1 rounded-full border border-slate-200 hover:bg-slate-100"
                      onClick={() => {
                        if (!references.length) return
                        if (selectedRefIds.size === references.length) {
                          setSelectedRefIds(new Set())
                        } else {
                          setSelectedRefIds(new Set(references.map((r) => String(r.ref_id || r.unique_key || r.id || ''))))
                        }
                      }}
                    >
                      {references.length && selectedRefIds.size === references.length ? '清空' : '全选'}
                    </button>
                  </div>
                </div>
                {references.length === 0 ? (
                  <div className="text-[12px] text-slate-500">报告未记录引用点，或生成时未保存引用。</div>
                ) : (
                  <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
                    {references.map((ref, idx) => {
                      const refId = String(ref.ref_id || ref.unique_key || ref.id || idx)
                      const checked = selectedRefIds.has(refId)
                      return (
                        <label
                          key={refId}
                          className={`block rounded-xl border px-3 py-2 text-xs space-y-1 cursor-pointer ${
                            checked ? 'border-blue-200 bg-white' : 'border-slate-200 bg-white'
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <input
                              type="checkbox"
                              className="mt-0.5"
                              checked={checked}
                              onChange={(e) => {
                                setSelectedRefIds((prev) => {
                                  const next = new Set(prev)
                                  if (e.target.checked) next.add(refId)
                                  else next.delete(refId)
                                  return next
                                })
                              }}
                            />
                            <div className="min-w-0">
                              <div className="font-semibold text-slate-900 truncate">{ref.title || '未命名资讯'}</div>
                              <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                                {ref.publish_time && <span>{formatDateTime(ref.publish_time)}</span>}
                                {ref.source && <span>{ref.source}</span>}
                                {ref.sentiment && <span className="px-2 py-0.5 rounded-full border border-slate-200">{ref.sentiment}</span>}
                              </div>
                              {ref.summary && <p className="text-[12px] text-slate-600 line-clamp-2">{ref.summary}</p>}
                            </div>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="mt-4 space-y-4">
                {combinedMessages.map((msg, idx) => {
                  const isUser = msg.role === 'user'
                  const isReport = msg.kind === 'report'
                  return (
                    <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                      <div
                    className={`max-w-[90%] sm:max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-6 border ${
                      isUser
                        ? 'bg-blue-50 text-slate-800 border-blue-100'
                        : isReport
                        ? 'bg-slate-50 text-slate-800 border-slate-200'
                        : 'bg-white text-slate-800 border-slate-200'
                    }`}
                  >
                    <div className="text-[11px] text-slate-500 mb-1">{isUser ? '你' : isReport ? '报告' : 'LLM'}</div>
                    <div className="space-y-1">{renderMarkdown(msg.content)}</div>
                    {isReport && (
                      <div className="mt-2 text-[11px] text-slate-500">
                        以上为报告全文，可直接追问：风险？催化剂？整体情绪？
                      </div>
                    )}
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="mt-6 space-y-2">
                <textarea
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                  rows={3}
                  placeholder="就这份报告追问：风险？催化剂？整体情绪？"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                />
                <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
                  <button
                    type="button"
                    className="px-2 py-1 rounded-full border border-slate-200 hover:bg-slate-50"
                    onClick={() => setQuestion('这份报告的核心风险和催化剂是什么？')}
                  >
                    风险/催化剂
                  </button>
                  <button
                    type="button"
                    className="px-2 py-1 rounded-full border border-slate-200 hover:bg-slate-50"
                    onClick={() => setQuestion('整体情绪和关键逻辑是什么？')}
                  >
                    情绪/逻辑
                  </button>
                  <button
                    type="button"
                    className="px-2 py-1 rounded-full border border-slate-200 hover:bg-slate-50"
                    onClick={() => setQuestion('未来一周的潜在催化剂和关注点有哪些？')}
                  >
                    未来催化剂
                  </button>
                </div>
                <button
                  className="w-full px-3 py-2 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50 text-sm disabled:opacity-60"
                  onClick={handleAsk}
                  disabled={chatting || !question.trim()}
                >
                  {chatting ? '提问中...' : '发送'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
export default function App() {
  const [appPath, setAppPath] = useState(() =>
    typeof window !== 'undefined' ? window.location.pathname : '/'
  )
  const [appSearch, setAppSearch] = useState(() =>
    typeof window !== 'undefined' ? window.location.search : ''
  )
  useEffect(() => {
    if (typeof window === 'undefined') return
    const handler = () => {
      setAppPath(window.location.pathname)
      setAppSearch(window.location.search)
    }
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [])
  const navigateTo = (url: string) => {
    if (typeof window === 'undefined') return
    window.history.pushState({}, '', url)
    setAppPath(window.location.pathname)
    setAppSearch(window.location.search)
  }

  if (typeof window !== 'undefined' && appPath.startsWith('/fundamental-report')) {
    return <FundamentalReportPage />
  }
  if (typeof window !== 'undefined' && appPath.includes('/fundamental')) {
    return <FundamentalCenter navigateTo={navigateTo} />
  }
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [quota, setQuota] = useState<QuotaInfo | null>(null)
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [selectedSession, setSelectedSession] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('session')
  })
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [data, setData] = useState<DashboardData | null>(null)
  const [moduleStatus, setModuleStatus] = useState<ModuleStatusMap>(() => createModuleStatusMap())
  const [streamQuote, setStreamQuote] = useState<QuoteDetail | null>(null)
  const [streamKlines, setStreamKlines] = useState<KLinePoint[]>([])
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('idle')
  const [streamError, setStreamError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [serverHeartbeat, setServerHeartbeat] = useState<string | null>(null)
  const streamRef = useRef<EventSource | null>(null)
  const reconnectTimer = useRef<number | null>(null)
  const detailLoadRef = useRef(0)

  const usagePercent = useMemo(() => {
    if (!quota) return 0
    const used = quota.total_used ?? 0
    const remain = quota.remain ?? 0
    const total = used + remain
    return total ? Math.min(100, Math.round((used / total) * 100)) : 0
  }, [quota])

  useEffect(() => {
    fetchSessions()
  }, [])

  useEffect(() => {
    if (!selectedSession) return
    loadDetail(selectedSession)
  }, [selectedSession])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (selectedSession) {
      params.set('session', selectedSession)
    } else {
      params.delete('session')
    }
    const query = params.toString()
    const newUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname
    window.history.replaceState({}, '', newUrl)
  }, [selectedSession])

  useEffect(() => {
    if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
      return
    }
    setStreamQuote(null)
    setStreamKlines([])
    setStreamError(null)
    streamRef.current?.close()
    streamRef.current = null
    if (reconnectTimer.current) {
      window.clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
    if (!selectedSession) {
      setStreamStatus('idle')
      return
    }
    let cancelled = false

    const scheduleReconnect = () => {
      if (cancelled) return
      if (reconnectTimer.current) {
        window.clearTimeout(reconnectTimer.current)
      }
      reconnectTimer.current = window.setTimeout(() => {
        reconnectTimer.current = null
        connect()
      }, 2000)
    }

    const handleMessage = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as StreamPayload
        if (payload.timestamp) {
          setServerHeartbeat(typeof payload.timestamp === 'string' ? payload.timestamp : new Date(payload.timestamp).toISOString())
        }
        const quotePayload = payload.quote as QuoteDetail | undefined
        if (quotePayload) {
          setStreamQuote((prev) => (prev ? { ...prev, ...quotePayload } : quotePayload))
          setData((prev) => {
            if (!prev || payload.code !== prev.code) {
              return prev
            }
            return {
              ...prev,
              quote: { ...(prev.quote || {}), ...quotePayload }
            }
          })
          setSessions((prev) =>
            prev.map((item) => {
              if (item.session_id !== selectedSession) {
                return item
              }
              return {
                ...item,
                quote: { ...(item.quote || {}), ...quotePayload }
              }
            })
          )
        }
        const klineRecords = normalizeKLineRecords(payload.kline)
        if (klineRecords.length) {
          setStreamKlines((prev) => mergeKlineSeries(prev, klineRecords))
          setData((prev) => {
            if (!prev || payload.code !== prev.code) {
              return prev
            }
            const existing = Array.isArray(prev.history_kline) ? prev.history_kline : []
            return {
              ...prev,
              history_kline: mergeKlineSeries(existing, klineRecords)
            }
          })
        }
      } catch (err) {
        console.warn('解析SSE数据失败', err)
      }
    }

    const connect = () => {
      if (cancelled || !selectedSession) return
      setStreamStatus('connecting')
      const source = new EventSource(`/web/api/stream/${selectedSession}`)
      streamRef.current = source
      source.onopen = () => {
        if (cancelled) return
        setStreamStatus('connected')
        setStreamError(null)
      }
      source.onmessage = handleMessage
      source.onerror = () => {
        if (cancelled) return
        setStreamStatus('disconnected')
        setStreamError('实时通道异常，将尝试重连')
        source.close()
        scheduleReconnect()
      }
    }

    connect()

    return () => {
      cancelled = true
      setStreamStatus('idle')
      streamRef.current?.close()
      streamRef.current = null
      if (reconnectTimer.current) {
        window.clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
    }
  }, [selectedSession])

  async function fetchSessions() {
    setListLoading(true)
    setListError(null)
    try {
      const res = await fetch('/api/dashboard/sessions')
      if (!res.ok) throw new Error('无法获取订阅列表')
      const json = await res.json()
      setSessions(json.sessions || [])
      setQuota(json.quota || null)
      setSelectedSession((prev) => {
        if (prev) {
          const stillExists = json.sessions?.some((item: SessionItem) => item.session_id === prev)
          if (stillExists) {
            return prev
          }
        }
        const params = new URLSearchParams(window.location.search)
        const urlSession = params.get('session')
        if (urlSession && json.sessions?.some((item: SessionItem) => item.session_id === urlSession)) {
          return urlSession
        }
        return null
      })
    } catch (err) {
      setListError((err as Error).message)
    } finally {
      setListLoading(false)
    }
  }

  function applyModulePayload(module: DashboardModule, payload: Partial<DashboardData>) {
    setData((prev) => {
      if (!prev) {
        if (module === 'core') {
          return payload as DashboardData
        }
        return prev
      }
      return { ...prev, ...payload } as DashboardData
    })
  }

  async function fetchDashboardModules(sessionId: string, modules: DashboardModule[]): Promise<Partial<DashboardData>> {
    const params = new URLSearchParams({ session: sessionId })
    if (modules.length) {
      params.set('modules', modules.join(','))
    }
    const res = await fetch(`/api/dashboard/bootstrap?${params.toString()}`)
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || '模块加载失败')
    }
    return (await res.json()) as Partial<DashboardData>
  }

  async function runModuleFetch(sessionId: string, module: DashboardModule, loadId: number) {
    try {
      const payload = await fetchDashboardModules(sessionId, [module])
      if (detailLoadRef.current !== loadId) {
        return
      }
      applyModulePayload(module, payload)
      setModuleStatus((prev) => ({
        ...prev,
        [module]: { loading: false, error: null }
      }))
    } catch (err) {
      if (detailLoadRef.current !== loadId) {
        return
      }
      const message = (err as Error).message || '模块加载失败'
      setModuleStatus((prev) => ({
        ...prev,
        [module]: { loading: false, error: message }
      }))
      if (module === 'core') {
        throw err
      }
    }
  }

  async function loadDetail(sessionId: string, opts?: { preserve?: boolean }) {
    const loadId = ++detailLoadRef.current
    const shouldBlock = !opts?.preserve || !data
    if (shouldBlock) {
      setDetailLoading(true)
    }
    setDetailError(null)
    if (!opts?.preserve) {
      setData(null)
    }
    setModuleStatus(() => {
      const base = createModuleStatusMap()
      DASHBOARD_MODULES.forEach((module) => {
        base[module] = { loading: true, error: null }
      })
      return base
    })
    try {
      await runModuleFetch(sessionId, 'core', loadId)
      if (detailLoadRef.current !== loadId) {
        return
      }
      setDetailLoading(false)
    } catch (err) {
      if (detailLoadRef.current !== loadId) {
        return
      }
      setDetailError((err as Error).message || '无法加载面板数据')
      setDetailLoading(false)
      return
    }
    DASHBOARD_MODULES.filter((module) => module !== 'core').forEach((module) => {
      runModuleFetch(sessionId, module, loadId)
    })
  }

  const handleReloadModule = (module: DashboardModule) => {
    if (!selectedSession) return
    setModuleStatus((prev) => ({
      ...prev,
      [module]: { loading: true, error: null }
    }))
    runModuleFetch(selectedSession, module, detailLoadRef.current).catch((err) => {
      if (module === 'core') {
        setDetailError((err as Error).message || '无法加载面板数据')
      }
    })
  }

  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const codeInput = form.elements.namedItem('code') as HTMLInputElement
    const code = codeInput.value.trim()
    if (!code) return
    try {
      const res = await fetch('/api/dashboard/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      })
      if (!res.ok) throw new Error('创建订阅失败')
      const json = await res.json()
      codeInput.value = ''
      await fetchSessions()
      setSelectedSession(json.session_id)
    } catch (err) {
      alert((err as Error).message)
    }
  }

  async function handleDelete(sessionId: string) {
    const target = sessions.find((item) => item.session_id === sessionId)
    const label = target?.nickname || target?.code || sessionId
    if (!window.confirm(`确定删除订阅「${label}」?`)) {
      return
    }
    setDeletingId(sessionId)
    try {
      const res = await fetch(`/api/dashboard/session/${sessionId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('删除失败')
      await fetchSessions()
      if (selectedSession === sessionId) {
        setSelectedSession(null)
      }
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setDeletingId(null)
    }
  }

  const quotaText = quota
    ? `已用 ${quota.total_used ?? '-'} / ${(quota.total_used ?? 0) + (quota.remain ?? 0) || '-'}`
    : '配额未知'

  const historyKline = data?.history_kline
  const normalizedHistory = useMemo(() => normalizeKLineRecords(historyKline), [historyKline])
  const mergedKlinePoints = useMemo(
    () => mergeKlineSeries(normalizedHistory, streamKlines),
    [normalizedHistory, streamKlines]
  )
  const triggerAnalyzeNow = async (item: TimelineNewsItem) => {
    try {
      const res = await fetch('/api/fundamental/analyze_now', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: data?.code,
          title: item.title,
          url: item.url,
          source: item.source,
          snippet: item.snippet,
          publish_time: item.publish_time || item.published_at
        })
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '触发分析失败')
      }
      const json = (await res.json()) as ApiResponse<{ analysis?: any }>
      if (json.ret_code !== 0) {
        throw new Error(json.ret_msg || '触发分析失败')
      }
      // 触发成功后，重载 signals 模块以获取最新
      if (selectedSession) {
        handleReloadModule('signals')
      }
    } catch (err) {
      alert((err as Error).message)
    }
  }
  const sessionKlinePoints = useMemo(() => {
    if (!mergedKlinePoints.length) return []
    const last = mergedKlinePoints[mergedKlinePoints.length - 1]
    const lastDate = typeof last.time_key === 'string' ? last.time_key.slice(0, 10) : null
    if (!lastDate) return mergedKlinePoints
    const sameDay = mergedKlinePoints.filter((point) => {
      const timeKey = typeof point.time_key === 'string' ? point.time_key : null
      return timeKey ? timeKey.startsWith(lastDate) : false
    })
    if (sameDay.length >= 20) {
      return sameDay
    }
    return mergedKlinePoints.slice(-240)
  }, [mergedKlinePoints])
  const candleData = useMemo(() => buildCandlesFromPoints(sessionKlinePoints), [sessionKlinePoints])
  const volumeData = useMemo(() => buildVolumeSeries(sessionKlinePoints, candleData), [sessionKlinePoints, candleData])

  const detailSection = data ? (
    <DetailContent
      data={data}
      moduleStatus={moduleStatus}
      serverHeartbeat={serverHeartbeat}
      liveQuote={streamQuote}
      candles={candleData}
      volumes={volumeData}
      klineCount={mergedKlinePoints.length}
      streamStatus={streamStatus}
      streamError={streamError}
      onBack={() => setSelectedSession(null)}
      onRefresh={() => selectedSession && loadDetail(selectedSession, { preserve: true })}
      onReloadModule={handleReloadModule}
      onAnalyzeNow={(item) => triggerAnalyzeNow(item)}
      onUpdateSignals={(signals) =>
        setData((prev) =>
          prev
            ? {
                ...prev,
                signals
              }
            : prev
        )
      }
    />
  ) : (
    <div className="p-10 text-center text-slate-400">请选择左侧的股票以加载实时看板</div>
  )

  if (listLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-600">
        <p className="text-lg">加载订阅列表...</p>
      </div>
    )
  }

  if (listError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-red-500">
        <p>{listError}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="w-[90%] max-w-7xl mx-auto px-6 py-4 flex flex-col gap-3">
          <div className="text-sm text-slate-500">实时观察室（React 版）</div>
          <div className="flex flex-wrap items-center gap-4">
            <h1 className="text-3xl font-semibold text-slate-900">订阅总面板</h1>
            <span className="text-slate-500">
              {quotaText} · {usagePercent}%
            </span>
            <div className="ml-auto flex gap-3">
              <a
                href="/fundamental"
                className="px-4 py-2 rounded-full bg-blue-600 text-white hover:bg-blue-500"
              >
                基础面中心
              </a>
              <button className="px-4 py-2 rounded-full border border-slate-200 text-slate-600 bg-white hover:bg-slate-100">关注</button>
              <button className="px-4 py-2 rounded-full border border-slate-200 text-slate-600 bg-white hover:bg-slate-100">分享</button>
            </div>
          </div>
        </div>
      </header>

      <main className="w-[90%] max-w-7xl mx-auto px-4 py-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(300px,0.28fr)_minmax(0,0.72fr)]">
          <aside className="space-y-5 lg:sticky lg:top-6 self-start">
            <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 space-y-4">
              <div>
                <div className="text-sm text-slate-500">新增订阅</div>
                <form onSubmit={handleCreate} className="mt-2 flex gap-3">
                  <input
                    type="text"
                    name="code"
                    placeholder="例如 HK.00700"
                    className="flex-1 rounded-xl border border-slate-200 px-4 py-2 text-slate-700 focus:border-blue-500 focus:outline-none"
                  />
                  <button type="submit" className="px-4 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-500">
                    添加
                  </button>
                </form>
              </div>
              <div>
                <div className="text-sm text-slate-500 mb-2">订阅配额</div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${usagePercent > 80 ? 'bg-rose-500' : 'bg-blue-500'}`}
                    style={{ width: `${usagePercent}%` }}
                  ></div>
                </div>
              </div>
            </section>
            <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 space-y-3">
              <button
                type="button"
                onClick={() => setSelectedSession(null)}
                className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                  selectedSession === null ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">持仓首页</div>
                    <div className="text-xs text-slate-500">综合概览</div>
                  </div>
                  <div className="text-xs text-slate-400">默认视图</div>
                </div>
              </button>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs text-slate-400">订阅列表</div>
                  <div className="text-lg font-semibold text-slate-900">共 {sessions.length} 条</div>
                </div>
              </div>
              <div className="space-y-3 max-h-[65vh] overflow-y-auto pr-1">
                {sessions.length === 0 ? (
                  <p className="text-xs text-slate-500">暂无订阅，添加股票即可生成看板。</p>
                ) : (
                  sessions.map((item) => {
                    const displayName = getSessionDisplayName(item) || '--'
                    const secondaryName =
                      item.quote?.name && item.quote?.name !== displayName ? item.quote?.name : null
                    const alias =
                      item.nickname && item.nickname !== displayName ? item.nickname : null
                    return (
                      <div
                        key={item.session_id}
                        onClick={() => setSelectedSession(item.session_id)}
                        role="button"
                        tabIndex={0}
                        className={`rounded-2xl border px-3 py-3 transition cursor-pointer ${
                          selectedSession === item.session_id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'
                        }`}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setSelectedSession(item.session_id)
                          }
                        }}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-slate-900">{displayName}</div>
                            <div className="text-xs text-slate-400">{item.code}</div>
                            {secondaryName && (
                              <div className="text-xs text-slate-500">名称：{secondaryName}</div>
                            )}
                            {alias && <div className="text-xs text-slate-500">别名：{alias}</div>}
                          </div>
                          <div className="text-right">
                            <div className={`text-sm font-semibold ${getChangeColor(item.quote?.change_rate)}`}>
                              {formatPercent(item.quote?.change_rate)}
                            </div>
                            <div className="text-xs text-slate-400">{formatDateTime(item.created_at)}</div>
                          </div>
                        </div>
                        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                          <span>策略：{formatStrategyLabel(item.strategy)}</span>
                          <span>{item.last_signal_time ? formatDateTime(item.last_signal_time) : '未更新'}</span>
                        </div>
                        <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                          <span>最新价 {formatPrice(item.quote?.price)}</span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDelete(item.session_id)
                            }}
                            disabled={deletingId === item.session_id}
                            className="text-[11px] px-2 py-0.5 rounded-full border border-slate-200 text-slate-500 hover:bg-slate-100 disabled:opacity-50"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </section>
          </aside>

          <section className="space-y-5">
            {selectedSession ? (
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
                {detailLoading ? (
                  <div className="p-10 text-center text-slate-500">加载面板数据...</div>
                ) : detailError ? (
                  <div className="p-10 text-center text-red-500">
                    {detailError}
                    <div>
                      <button onClick={() => loadDetail(selectedSession, { preserve: true })} className="mt-3 px-3 py-1.5 border rounded-full">
                        重试
                      </button>
                    </div>
                  </div>
                ) : (
                  detailSection
                )}
              </div>
            ) : (
              <HoldingsHomePanel sessions={sessions} onSelect={setSelectedSession} />
            )}
          </section>
        </div>
      </main>
    </div>
  )
}

type DetailContentProps = {
  data: DashboardData
  moduleStatus: ModuleStatusMap
  serverHeartbeat: string | null
  liveQuote?: QuoteDetail | null
  candles: CandlestickData[]
  volumes: HistogramData[]
  klineCount: number
  streamStatus: StreamStatus
  streamError?: string | null
  onBack: () => void
  onRefresh: () => void
  onUpdateSignals?: (signals: SignalMap) => void
  onReloadModule?: (module: DashboardModule) => void
  onAnalyzeNow?: (item: TimelineNewsItem) => void
  onNavigate?: (url: string) => void
}

function DetailContent({
  data,
  moduleStatus,
  serverHeartbeat,
  liveQuote,
  candles,
  volumes,
  klineCount,
  streamStatus,
  streamError,
  onBack,
  onRefresh,
  onUpdateSignals,
  onReloadModule,
  onAnalyzeNow,
  onNavigate
}: DetailContentProps) {
const quote = liveQuote ?? data.quote
  const sessionMeta = data.session
  const sessionWindow = data.session_window
  const signalModuleState = moduleStatus.signals
  const recommendationModuleState = moduleStatus.recommendations
  const capitalModuleState = moduleStatus.capital
  const klineModuleState = moduleStatus.kline
  const [heartbeatNow, setHeartbeatNow] = useState(() => Date.now())
  const [analysisModels, setAnalysisModels] = useState<string[]>(['deepseek', 'kimi'])
  const [analysisJudge, setAnalysisJudge] = useState<string>('gemini')
  const [analysisQuestion, setAnalysisQuestion] = useState('')
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<MultiModelAnalysisResponse | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [savingStrategy, setSavingStrategy] = useState(false)
  const [analysisModelStates, setAnalysisModelStates] = useState<
    Record<
      string,
      {
        status: string
        result?: MultiModelAction | Record<string, unknown>
        error?: string
        rawText?: string
      }
    >
  >({})
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>(data.recommendations ?? [])
  const [analysisWindow, setAnalysisWindow] = useState<{ start?: string; end?: string } | null>(null)
  const [analysisContextSnapshot, setAnalysisContextSnapshot] = useState<Record<string, any> | null>(null)
  const [newsSize, setNewsSize] = useState(10)
  const [newsDays, setNewsDays] = useState(3)
  const [newsRefreshing, setNewsRefreshing] = useState(false)
  const [reportGenerating, setReportGenerating] = useState<null | 'daily' | 'weekly'>(null)
  const [strategyPageId, setStrategyPageId] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('strategy')
  })
  const [prefetchedStrategy, setPrefetchedStrategy] = useState<RecommendationItem | null>(null)
  const [lastPrice, setLastPrice] = useState<number | null>(null)
  const [priceTrend, setPriceTrend] = useState<'up' | 'down' | 'flat'>('flat')
  const [priceDelta, setPriceDelta] = useState<number | null>(null)
  const [pricePulseToken, setPricePulseToken] = useState(0)
  const [pricePulse, setPricePulse] = useState(false)
  const [latestReports, setLatestReports] = useState<any[]>([])
  const [reportListLoading, setReportListLoading] = useState(false)
  useEffect(() => {
    setAnalysisResult(null)
    setAnalysisQuestion('')
    setAnalysisError(null)
    setAnalysisModelStates({})
    setAnalysisWindow(null)
    setRecommendations(data.recommendations ?? [])
    setAnalysisContextSnapshot(null)
    setPrefetchedStrategy(null)
    setLatestReports([])
  }, [data.code])
  useEffect(() => {
    setRecommendations(data.recommendations ?? [])
  }, [data.recommendations])
  useEffect(() => {
    const handler = () => {
      const params = new URLSearchParams(window.location.search)
      const next = params.get('strategy')
      setStrategyPageId(next)
      setPrefetchedStrategy(null)
    }
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [])
  useEffect(() => {
    if (typeof window === 'undefined') return
    const timer = window.setInterval(() => setHeartbeatNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const rawPrice = quote?.price
    const numericPrice =
      typeof rawPrice === 'number'
        ? rawPrice
        : rawPrice !== undefined && rawPrice !== null
        ? Number(rawPrice)
        : null
    if (numericPrice === null || Number.isNaN(numericPrice)) {
      return
    }
    setLastPrice((prev) => {
      if (prev === null) {
        return numericPrice
      }
      if (numericPrice !== prev) {
        setPriceTrend(numericPrice > prev ? 'up' : 'down')
        setPriceDelta(numericPrice - prev)
        setPricePulseToken((token) => token + 1)
      } else {
        setPriceTrend('flat')
        setPriceDelta(null)
      }
      return numericPrice
    })
  }, [quote?.price])

  useEffect(() => {
    if (!pricePulseToken || typeof window === 'undefined') return
    setPricePulse(true)
    const timer = window.setTimeout(() => setPricePulse(false), 700)
    return () => window.clearTimeout(timer)
  }, [pricePulseToken])

  useEffect(() => {
    const fetchReports = async () => {
      if (!data.code) return
      setReportListLoading(true)
      try {
        const res = await fetch('/api/fundamental/reports', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: data.code, limit: 5, offset: 0 })
        })
        const json = await res.json()
        if (res.ok && json.ret_code === 0) {
          setLatestReports(json.data?.items || [])
        }
      } catch (err) {
        console.warn('load latest reports failed', err)
      } finally {
        setReportListLoading(false)
      }
    }
    fetchReports()
  }, [data.code])

  if (strategyPageId) {
    return (
      <StrategyDetailPage
        strategyId={strategyPageId}
        initialStrategy={prefetchedStrategy}
        onBack={handleCloseStrategyPage}
        onStrategyUpdated={handleStrategyUpdated}
      />
    )
  }
  const accent: 'emerald' | 'rose' | 'slate' = quote?.change_rate === undefined || quote.change_rate === null
    ? 'slate'
    : quote.change_rate >= 0
    ? 'emerald'
    : 'rose'
  const statusMeta = {
    idle: { text: '等待实时数据', dot: 'bg-slate-300' },
    connecting: { text: '正在连接实时通道', dot: 'bg-amber-400 animate-pulse' },
    connected: { text: '实时更新中', dot: 'bg-emerald-400' },
    disconnected: { text: '已断开，尝试重连', dot: 'bg-rose-400 animate-pulse' }
  }[streamStatus] ?? { text: '实时状态未知', dot: 'bg-slate-300' }
  const heartbeatLagMs = useMemo(() => {
    if (!serverHeartbeat) return null
    const parsed = Date.parse(serverHeartbeat)
    if (Number.isNaN(parsed)) return null
    return Math.max(0, heartbeatNow - parsed)
  }, [serverHeartbeat, heartbeatNow])
  const heartbeatHealthy = heartbeatLagMs !== null && heartbeatLagMs < 15000
  const heartbeatText = heartbeatLagMs !== null ? `${Math.floor(heartbeatLagMs / 1000)}s` : '--'

  const realtimePoints = data.history?.length ?? 0
  const metrics = [
    { label: '今开', value: formatPrice(quote?.open) },
    { label: '最高', value: formatPrice(quote?.high) },
    { label: '最低', value: formatPrice(quote?.low) },
    { label: '昨收', value: formatPrice(quote?.prev_close) },
    { label: '成交量', value: formatAmount(quote?.volume) },
    { label: '成交额', value: formatAmount(quote?.turnover) },
    { label: '实时记录点', value: `${realtimePoints} 条`, hint: '来自 SSE 实时推送' },
    { label: 'K线采样', value: `${klineCount} 条`, hint: '近 1 分钟采样' }
  ]

  const holdingEntries = useMemo<[string, string][]>(() => {
    const raw = data.holding || {}
    return Object.entries(raw)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => {
        if (typeof value === 'number') {
          const numericValue: number = value
          if (key.includes('比例')) {
            return [key, formatPercent(numericValue)]
          }
          if (key.includes('盈亏')) {
            return [key, formatAmount(numericValue)]
          }
          if (key.includes('持仓')) {
            return [key, numericValue.toLocaleString()]
          }
          return [key, formatPrice(numericValue)]
        }
        return [key, value]
      })
  }, [data.holding])
  const flowSummary = data.capital_flow?.summary
  const distributionSummary = data.capital_distribution?.summary
  const breakdown = distributionSummary?.breakdown || {}
  const breakdownItems = [
    { label: '特大单', value: breakdown.super_net },
    { label: '大单', value: breakdown.big_net },
    { label: '中单', value: breakdown.mid_net },
    { label: '小单', value: breakdown.small_net }
  ]
  const breakdownMax = Math.max(...breakdownItems.map((item) => Math.abs(item.value ?? 0)), 0)

  const bullishNews = data.signals?.bullish ?? []
  const bearishNews = data.signals?.bearish ?? []
  const neutralNews = data.signals?.neutral ?? []
  const [sentimentFilter, setSentimentFilter] = useState<SentimentFilter>('all')
  const timelineNews = useMemo<TimelineNewsItem[]>(
    () =>
      [...bullishNews, ...bearishNews, ...neutralNews]
        .map((item) => {
          const published = item.published_at || item.publish_time
          const ts = parseNewsDate(published)
          const sentiment = normalizeSentiment(item.analysis?.sentiment || item.sentiment)
          return {
            ...item,
            sentiment,
            timestamp: ts
          }
        })
        .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)),
    [bullishNews, bearishNews, neutralNews]
  )
  const signalsSummary = useMemo(() => (data.signals as any)?.summary, [data.signals])
  const signalsMeta = useMemo(() => (data.signals as any)?.meta, [data.signals])
  const computedDailyMetrics = useMemo(() => {
    const computed = computeDailyMetricsFromNews(timelineNews)
    if (computed.length) {
      return computed
    }
    return (data.signals?.daily_metrics as DailyMetric[]) || []
  }, [timelineNews, data.signals?.daily_metrics])
  const dailyMetricMap = useMemo(() => {
    const map: Record<string, DailyMetric> = {}
    computedDailyMetrics.forEach((metric) => {
      if (metric?.date) {
        map[metric.date] = metric
      }
    })
    return map
  }, [computedDailyMetrics])
const timelineGroups = useMemo<TimelineGroup[]>(() => {
    if (!timelineNews.length) return []
    const grouped: Record<string, TimelineGroup & { latestTs: number }> = {}
    timelineNews.forEach((item) => {
      const dateKey = item.timestamp ? new Date(item.timestamp).toISOString().slice(0, 10) : 'unknown'
      if (!grouped[dateKey]) {
        const { label, weekday } = formatDateLabel(dateKey)
        grouped[dateKey] = {
          key: dateKey,
          displayDate: label,
          weekday,
          metric: dailyMetricMap[dateKey],
          items: [],
          latestTs: item.timestamp || 0
        }
      }
      grouped[dateKey].items.push(item)
      if ((item.timestamp || 0) > grouped[dateKey].latestTs) {
        grouped[dateKey].latestTs = item.timestamp || 0
      }
    })
    const groups = Object.values(grouped).map((group) => ({
      ...group,
      items: [...group.items].sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
    }))
    return groups
      .sort((a, b) => {
        const diff = (b.latestTs || 0) - (a.latestTs || 0)
        if (diff !== 0) return diff
        if (a.key === 'unknown') return 1
        if (b.key === 'unknown') return -1
        return b.key.localeCompare(a.key)
      })
      .map(({ latestTs, ...group }) => group)
}, [timelineNews, dailyMetricMap])

  const filteredTimelineGroups = useMemo(() => {
    if (sentimentFilter === 'all') {
      return timelineGroups
    }
    return timelineGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => item.sentiment === sentimentFilter)
      }))
      .filter((group) => group.items.length > 0)
  }, [timelineGroups, sentimentFilter])
  const displayedTimelineCount = filteredTimelineGroups.reduce((total, group) => total + group.items.length, 0)
  const sentimentOptions: Array<{ key: SentimentFilter; label: string; count: number; activeClass: string; baseClass: string }> = [
    {
      key: 'all',
      label: '全部',
      count: timelineNews.length,
      activeClass: 'bg-slate-900 text-white border-slate-900',
      baseClass: 'border-slate-200 text-slate-500 bg-white'
    },
    {
      key: 'bullish',
      label: '利好',
      count: bullishNews.length,
      activeClass: 'bg-emerald-500 text-white border-emerald-500',
      baseClass: 'border-emerald-200 text-emerald-600 bg-emerald-50'
    },
    {
      key: 'neutral',
      label: '中性',
      count: neutralNews.length,
      activeClass: 'bg-slate-700 text-white border-slate-700',
      baseClass: 'border-slate-200 text-slate-500 bg-slate-50'
    },
    {
      key: 'bearish',
      label: '利空',
      count: bearishNews.length,
      activeClass: 'bg-rose-500 text-white border-rose-500',
      baseClass: 'border-rose-200 text-rose-500 bg-rose-50'
    }
  ]
  const newsSizeOptions = useMemo(() => Array.from({ length: 10 }, (_, idx) => (idx + 1) * 10), [])
  const newsDaysOptions = useMemo(() => [1, 2, 3, 7, 14, 30], [])
  const pendingCount = useMemo(
    () =>
      timelineNews.filter(
        (item) => !item.analysis?.sentiment || (item.analysis?.analysis_provider || '').toString().toLowerCase() === 'pending'
      ).length,
    [timelineNews]
  )
  const llmModelOptions = [
    { key: 'deepseek', label: 'DeepSeek' },
    { key: 'kimi', label: 'Kimi' },
    { key: 'gemini', label: 'Gemini' }
  ]
  const shouldShowAnalysisPanel =
    analysisLoading || !!analysisResult || Object.keys(analysisModelStates).length > 0
  const analysisStartTime = analysisResult?.started_at || analysisWindow?.start
  const analysisEndTime = analysisResult?.finished_at || analysisWindow?.end
  const baseJudgeResult = analysisResult?.judge?.result
  const parsedJudgeRaw = useMemo(() => parseLooseJsonText(analysisResult?.judge?.raw_text), [analysisResult?.judge?.raw_text])
  const judgeResult = useMemo(() => {
    if (!baseJudgeResult && parsedJudgeRaw) {
      return parsedJudgeRaw as MultiModelJudgeResult['result']
    }
    if (!parsedJudgeRaw) {
      return baseJudgeResult
    }
    if (!baseJudgeResult) {
      return parsedJudgeRaw as MultiModelJudgeResult['result']
    }
    return {
      ...parsedJudgeRaw,
      ...baseJudgeResult,
      summary: baseJudgeResult.summary || parsedJudgeRaw?.summary,
      recommended: baseJudgeResult.recommended || parsedJudgeRaw?.recommended,
      deciding_factors: baseJudgeResult.deciding_factors || parsedJudgeRaw?.deciding_factors,
      opportunity_notes: baseJudgeResult.opportunity_notes || parsedJudgeRaw?.opportunity_notes,
      risk_notes: baseJudgeResult.risk_notes || parsedJudgeRaw?.risk_notes,
      warnings: baseJudgeResult.warnings || parsedJudgeRaw?.warnings,
      referenced_models: baseJudgeResult.referenced_models || parsedJudgeRaw?.referenced_models,
      status: baseJudgeResult.status || (parsedJudgeRaw?.status as string | undefined)
    } as MultiModelJudgeResult['result']
  }, [baseJudgeResult, parsedJudgeRaw])
  const judgeRecommended = judgeResult?.recommended
  const judgeConditions = toStringArray(judgeRecommended?.conditions)
  const judgeMissingConditions = toStringArray(judgeRecommended?.missing_conditions)
  const judgeBasis = toStringArray(judgeRecommended?.basis)
  const judgeTags = toStringArray(judgeRecommended?.tags)
  const judgeDecidingFactors = toStringArray(judgeResult?.deciding_factors)
  const judgeOpportunities = toStringArray(judgeResult?.opportunity_notes)
  const judgeRisks = toStringArray(judgeResult?.risk_notes)
  const judgeWarnings = toStringArray(judgeResult?.warnings)
  const judgeSummaryText = judgeResult?.summary || formatPlainText(analysisResult?.judge?.raw_text)

  const toggleModel = (model: string) => {
    setAnalysisModels((prev) =>
      prev.includes(model) ? prev.filter((key) => key !== model) : [...prev, model]
    )
  }

  const handleRunAnalysis = async () => {
    if (!analysisModels.length) {
      setAnalysisError('请至少选择一个模型')
      return
    }
    setAnalysisContextSnapshot(null)
    const startedAt = new Date().toISOString()
    const initStates: Record<string, { status: string }> = {}
    analysisModels.forEach((model) => {
      initStates[model] = { status: 'loading' }
    })
    setAnalysisModelStates(initStates)
    setAnalysisLoading(true)
    setAnalysisError(null)
    setAnalysisResult(null)
    setAnalysisWindow({ start: startedAt })
    let contextSnapshotRef: Record<string, any> | null = null
    try {
      const modelResults = await Promise.all(
        analysisModels.map(async (model) => {
          try {
            const res = await fetch('/api/analysis/multi_model/model', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                code: data.code,
                model,
                question: analysisQuestion || undefined
              })
            })
            if (!res.ok) {
              const text = await res.text()
              throw new Error(text || '模型分析失败')
            }
            const json = (await res.json()) as MultiModelModelResult
            if (!contextSnapshotRef && json.context_snapshot) {
              contextSnapshotRef = json.context_snapshot
              setAnalysisContextSnapshot(json.context_snapshot)
            }
            setAnalysisModelStates((prev) => ({
              ...prev,
              [model]: {
                status: json.status,
                result: json.result as MultiModelAction | Record<string, unknown> | undefined,
                error: json.error,
                rawText: json.raw_text
              }
            }))
            return json
          } catch (err) {
            const message = (err as Error).message || '模型分析失败'
            setAnalysisModelStates((prev) => ({
              ...prev,
              [model]: { status: 'error', error: message }
            }))
            return { model, status: 'error', error: message } as MultiModelModelResult
          }
        })
      )
      const successful = modelResults.filter((item) => item.status === 'success')
      let judgeResult: MultiModelJudgeResult | undefined
      if (successful.length) {
        try {
          const res = await fetch('/api/analysis/multi_model/judge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              code: data.code,
              judge_model: analysisJudge,
              base_results: successful,
              question: analysisQuestion || undefined
            })
          })
          if (!res.ok) {
            const text = await res.text()
            throw new Error(text || '评审失败')
          }
          judgeResult = (await res.json()) as MultiModelJudgeResult
          if (!contextSnapshotRef && judgeResult?.context_snapshot) {
            contextSnapshotRef = judgeResult.context_snapshot
            setAnalysisContextSnapshot(judgeResult.context_snapshot)
          }
        } catch (err) {
          judgeResult = {
            model: analysisJudge,
            status: 'error',
            error: (err as Error).message || '评审失败'
          }
        }
      } else {
        judgeResult = {
          model: analysisJudge,
          status: 'error',
          error: '全部模型均失败，无法进行评审'
        }
      }
      const finishedAt = new Date().toISOString()
      setAnalysisWindow({ start: startedAt, end: finishedAt })
      setAnalysisResult({
        code: data.code,
        models: modelResults,
        judge: judgeResult,
        started_at: startedAt,
        finished_at: finishedAt,
        context_snapshot: contextSnapshotRef || analysisContextSnapshot || undefined
      })
    } catch (err) {
      setAnalysisError((err as Error).message)
      setAnalysisWindow((prev) => (prev ? { ...prev, end: new Date().toISOString() } : prev))
    } finally {
      setAnalysisLoading(false)
    }
  }

  const handleRefreshNews = async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false
    if (!silent) {
      setNewsRefreshing(true)
    }
    try {
      const res = await fetch('/api/fundamental/news/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: data.code,
          size: newsSize,
          days: newsDays,
          stock_name: data.quote?.name || data.session?.nickname
        })
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '刷新失败')
      }
      const json = (await res.json()) as ApiResponse<{ signals: SignalMap }>
      if (json.ret_code !== 0 || !json.data?.signals) {
        throw new Error(json.ret_msg || '刷新失败')
      }
      onUpdateSignals?.(json.data.signals)
    } catch (err) {
      if (silent) {
        console.warn('[fundamental.refresh] failed', err)
      } else {
        alert((err as Error).message)
      }
    } finally {
      if (!silent) {
        setNewsRefreshing(false)
      }
    }
  }

  const handleGenerateReport = async (period: 'daily' | 'weekly') => {
    setReportGenerating(period)
    try {
      const res = await fetch('/api/fundamental/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: data.code,
          stock_name: data.quote?.name || data.session?.nickname,
          period,
          days: period === 'weekly' ? 7 : newsDays || 3,
          limit: newsSize || 20,
          source: 'dashboard'
        })
      })
      const json = (await res.json()) as ApiResponse<{ report?: string }>
      if (!res.ok || json.ret_code !== 0) throw new Error(json.ret_msg || '生成报告失败')
      alert('报告已生成，可在基础面中心查看')
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setReportGenerating(null)
    }
  }


  const handleSaveJudgeRecommendation = async () => {
    const recommended = analysisResult?.judge?.result?.recommended as MultiModelAction | undefined
    if (!recommended) {
      alert('暂无可保存的综合建议')
      return
    }
    setSavingStrategy(true)
    try {
      const payload: Record<string, any> = {
        code: data.code,
        action: recommended.action || 'WATCH',
        rationale: recommended.rationale || analysisResult?.judge?.result?.summary || 'AI策略建议',
        confidence: recommended.confidence ?? 0.5,
        timeframe: recommended.timeframe || 'short_term',
        source: 'multi-model',
        tags: recommended.tags || [],
        entry_price: recommended.entry_price,
        target_price: recommended.target_price,
        stop_loss: recommended.stop_loss,
        analysis_context: analysisResult?.context_snapshot,
        model_results: analysisResult?.models,
        judge_result: analysisResult?.judge
      }
      const res = await fetch('/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '保存失败')
      }
      const resp = (await res.json()) as { ret_code: number; ret_msg?: string; data?: { id?: number; created_at?: string } }
      if (resp.ret_code !== 0) {
        throw new Error(resp.ret_msg || '保存失败')
      }
      const newRecord: RecommendationItem = {
        id: resp.data?.id,
        action: payload.action,
        rationale: payload.rationale,
        confidence: payload.confidence,
        timeframe: payload.timeframe,
        created_at: resp.data?.created_at ?? new Date().toISOString(),
        adopted: false,
        source: payload.source || 'multi-model',
        tags: payload.tags,
        entry_price: payload.entry_price,
        target_price: payload.target_price,
        stop_loss: payload.stop_loss,
        eval_status: undefined,
        eval_summary: undefined,
        analysis_context: payload.analysis_context || undefined,
        model_results: payload.model_results as MultiModelModelResult[] | undefined,
        judge_result: payload.judge_result as MultiModelJudgeResult | undefined
      }
      setRecommendations((prev) => [newRecord, ...prev])
      alert('已保存策略建议')
    } catch (err) {
      alert(`保存失败: ${(err as Error).message}`)
    } finally {
      setSavingStrategy(false)
    }
  }

  const handleOpenStrategyDetail = (item: RecommendationItem) => {
    if (!item.id) {
      alert('该策略缺少ID，无法查看详情')
      return
    }
    setPrefetchedStrategy(item)
    const params = new URLSearchParams(window.location.search)
    params.set('strategy', String(item.id))
    window.history.pushState({ strategy: String(item.id) }, '', `${window.location.pathname}?${params.toString()}`)
    setStrategyPageId(String(item.id))
  }

  function handleCloseStrategyPage() {
    const params = new URLSearchParams(window.location.search)
    params.delete('strategy')
    const nextQuery = params.toString()
    const nextPath = nextQuery ? `${window.location.pathname}?${nextQuery}` : window.location.pathname
    window.history.pushState({}, '', nextPath)
    setStrategyPageId(null)
    setPrefetchedStrategy(null)
  }

  function handleStrategyUpdated(updated: RecommendationItem) {
    setRecommendations((prev) =>
      prev.map((rec) => (rec.id === updated.id ? { ...rec, ...updated } : rec))
    )
    setPrefetchedStrategy(updated)
  }

  const breakOverlay = useMemo(() => {
    if (!sessionWindow?.break_start || !sessionWindow?.break_end || !sessionWindow.open_time || !sessionWindow.close_time) {
      return null
    }
    const open = parseIsoToSeconds(sessionWindow.open_time)
    const close = parseIsoToSeconds(sessionWindow.close_time)
    const start = parseIsoToSeconds(sessionWindow.break_start)
    const end = parseIsoToSeconds(sessionWindow.break_end)
    if (open === null || close === null || start === null || end === null || close <= open) {
      return null
    }
    const left = ((start - open) / (close - open)) * 100
    const width = ((end - start) / (close - open)) * 100
    if (!Number.isFinite(left) || !Number.isFinite(width)) return null
    return { left: Math.max(0, left), width: Math.max(0, width) }
  }, [sessionWindow])

  const priceDeltaText = priceDelta !== null ? formatPriceDelta(priceDelta) : null
  const priceBoxClass = `
    relative px-4 py-3 rounded-2xl transition-all duration-500 text-right
    ${
      priceTrend === 'up'
        ? 'bg-emerald-50 text-emerald-600'
        : priceTrend === 'down'
        ? 'bg-rose-50 text-rose-600'
        : 'bg-slate-50 text-slate-600'
    }
    ${
      pricePulse
        ? priceTrend === 'up'
          ? 'ring-2 ring-emerald-200'
          : priceTrend === 'down'
          ? 'ring-2 ring-rose-200'
          : 'ring-2 ring-slate-200'
        : 'ring-0'
    }
  `.replace(/\s+/g, ' ')

  return (
    <div className="px-6 py-6 space-y-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex-1 min-w-[220px]">
          <p className="text-xs text-slate-500">会话 {sessionMeta?.session_id}</p>
          <h2 className="text-2xl font-semibold text-slate-900 mt-1">
            {sessionMeta?.nickname || quote?.name || data.code}
            <span className="text-base font-normal text-slate-500 ml-2">{data.code}</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">最近更新 {formatDateTime(quote?.update_time)}</p>
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            <span className={`h-2.5 w-2.5 rounded-full ${statusMeta.dot}`} />
            <span>{statusMeta.text}</span>
          </div>
          {streamError && (
            <div className="text-[11px] text-amber-600 mt-1">{streamError}</div>
          )}
          {serverHeartbeat && (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
              <span className={`h-2 w-2 rounded-full ${heartbeatHealthy ? 'bg-emerald-400' : 'bg-rose-500 animate-pulse'}`}></span>
              <span>后台时间 {formatDateTime(serverHeartbeat)}</span>
              <span>延迟 {heartbeatText}</span>
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className={priceBoxClass}>
            <div className="text-4xl font-bold leading-none">{formatPrice(quote?.price)}</div>
            <div className="flex items-center justify-end gap-2 text-xs mt-2 text-current">
              <span className="font-semibold">{formatChangeText(quote?.change_rate, quote?.change_value)}</span>
              {priceDeltaText && (
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    priceTrend === 'up'
                      ? 'bg-white/80 text-emerald-600'
                      : priceTrend === 'down'
                      ? 'bg-white/80 text-rose-600'
                      : 'bg-white/80 text-slate-600'
                  }`}
                >
                  {priceTrend === 'up' ? '▲' : priceTrend === 'down' ? '▼' : ''}
                  {priceDeltaText}
                </span>
              )}
            </div>
          </div>
          <div className="mt-3 flex gap-2 justify-end">
            <button onClick={onRefresh} className="px-3 py-1.5 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs">
              刷新数据
            </button>
            <button onClick={onBack} className="px-3 py-1.5 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs">
              返回列表
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-100 bg-gradient-to-b from-slate-50 to-white p-4 relative overflow-hidden">
        <KLineChart candles={candles} volumes={volumes} accent={accent} sessionWindow={sessionWindow} />
        {klineModuleState.loading && !candles.length && (
          <ModuleOverlayStatus message="正在加载分钟级 K 线..." />
        )}
        {klineModuleState.error && !candles.length && (
          <ModuleOverlayStatus
            variant="error"
            message={klineModuleState.error || 'K 线加载失败'}
            onRetry={() => onReloadModule?.('kline')}
          />
        )}
        {breakOverlay && (
          <div
            className="absolute inset-y-4 rounded-xl bg-slate-100/50 pointer-events-none"
            style={{ left: `${breakOverlay.left}%`, width: `${breakOverlay.width}%` }}
          >
            <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-xs text-slate-400">午休</div>
          </div>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-2xl border border-slate-100 bg-white/80 p-4">
            <div className="text-xs text-slate-500 uppercase tracking-wide">{metric.label}</div>
            <div className="text-xl font-semibold text-slate-900 mt-1">{metric.value}</div>
            {metric.hint && <div className="text-[11px] text-slate-400 mt-1">{metric.hint}</div>}
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)] items-start">
        <section className="rounded-3xl border border-slate-100 bg-white p-6 flex flex-col h-full min-w-0 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-slate-900">基础面模块</div>
              <p className="text-xs text-slate-400">本地缓存 + 拉新，一站式查看与汇总</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <button
                type="button"
                onClick={() => onReloadModule?.('signals')}
                disabled={signalModuleState.loading}
                className="px-3 py-1.5 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                title="仅重载本地缓存，不访问外部搜索"
              >
                重载缓存
              </button>
              <button
                type="button"
                onClick={() => handleRefreshNews()}
                disabled={newsRefreshing}
                className="px-3 py-1.5 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50 disabled:opacity-50"
              >
                {newsRefreshing ? '刷新中...' : '刷新基本面'}
              </button>
              <button
                type="button"
                onClick={() => handleGenerateReport('daily')}
                disabled={!!reportGenerating}
                className="px-3 py-1.5 rounded-full border border-emerald-200 text-emerald-600 hover:bg-emerald-50 disabled:opacity-50"
              >
                {reportGenerating === 'daily' ? '生成中...' : '生成日报'}
              </button>
              <button
                type="button"
                onClick={() => handleGenerateReport('weekly')}
                disabled={!!reportGenerating}
                className="px-3 py-1.5 rounded-full border border-emerald-200 text-emerald-600 hover:bg-emerald-50 disabled:opacity-50"
              >
                {reportGenerating === 'weekly' ? '生成中...' : '生成周报'}
              </button>
              <a
                className="px-3 py-1.5 rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50"
                href={`/fundamental?code=${data.code}`}
              >
                基础面中心
              </a>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-3">
              <div className="text-[11px] text-slate-500">基础面汇总</div>
              {signalsSummary?.headlines?.length ? (
                <>
                  <div className="mt-1 text-sm font-semibold text-slate-900 flex items-center gap-3">
                    <span>利好 {signalsSummary.counts?.bullish ?? 0}</span>
                    <span>利空 {signalsSummary.counts?.bearish ?? 0}</span>
                    <span>中性 {signalsSummary.counts?.neutral ?? 0}</span>
                  </div>
                  <div className="mt-2 space-y-1 text-[11px] text-slate-600">
                    {signalsSummary.headlines.slice(0, 3).map((h: any, idx: number) => (
                      <div key={idx} className="truncate">
                        <span className="font-semibold mr-1">
                          {h.sentiment === 'bullish' ? '利好' : h.sentiment === 'bearish' ? '利空' : '中性'}
                        </span>
                        <a className="hover:text-blue-600" href={h.url} target="_blank" rel="noreferrer">
                          {h.title}
                        </a>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="mt-2 text-[11px] text-slate-400">暂无汇总，点击刷新获取</div>
              )}
            </div>
            <div className="rounded-2xl border border-slate-100 bg-white px-3 py-3">
              <div className="text-[11px] text-slate-500">情绪分布</div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-600">
                <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-2 py-1">
                  <div className="text-[11px] text-emerald-600">利好</div>
                  <div className="text-sm font-semibold text-emerald-700">{bullishNews.length}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-1">
                  <div className="text-[11px] text-slate-600">中性</div>
                  <div className="text-sm font-semibold text-slate-700">{neutralNews.length}</div>
                </div>
                <div className="rounded-xl border border-rose-100 bg-rose-50 px-2 py-1">
                  <div className="text-[11px] text-rose-600">利空</div>
                  <div className="text-sm font-semibold text-rose-700">{bearishNews.length}</div>
                </div>
              </div>
              <div className="mt-2 text-[11px] text-slate-500">共 {displayedTimelineCount} 条，按时间排序</div>
            </div>
            <div className="rounded-2xl border border-slate-100 bg-white px-3 py-3">
              <div className="text-[11px] text-slate-500">过滤与数据质量</div>
              <div className="mt-2 text-xs text-slate-600 space-y-1">
                <div>过滤跳过：{signalsMeta?.skipped_irrelevant ?? 0}</div>
                <div>回填记录：{signalsMeta?.added_from_skipped ?? 0}</div>
                <div>使用宽松过滤：{signalsMeta?.used_loose_filter ? '是' : '否'}</div>
              </div>
              <div className="mt-2 text-[11px] text-slate-500">
                拉新参数：最近 {newsDays} 天 · 每次 {newsSize} 条
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {sentimentOptions.map((option) => {
              const isActive = sentimentFilter === option.key
              return (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setSentimentFilter(option.key)}
                  className={`px-3 py-1.5 text-xs rounded-full border transition ${isActive ? option.activeClass : option.baseClass}`}
                >
                  {option.label}
                  <span className="ml-1 text-[11px] opacity-70">{option.count}</span>
                </button>
              )
            })}
            <span className="text-xs text-slate-400">共 {displayedTimelineCount} 条</span>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 ml-auto">
              <label htmlFor="news-days" className="text-slate-500">
                刷新时间范围：
              </label>
              <select
                id="news-days"
                className="rounded-full border border-slate-200 px-2 py-1 text-slate-700"
                value={newsDays}
                onChange={(e) => setNewsDays(Number(e.target.value))}
              >
                {newsDaysOptions.map((d) => (
                  <option key={d} value={d}>
                    最近 {d} 天
                  </option>
                ))}
              </select>
              <label htmlFor="news-size" className="text-slate-500">
                每次拉取：
              </label>
              <select
                id="news-size"
                className="rounded-full border border-slate-200 px-2 py-1 text-slate-700"
                value={newsSize}
                onChange={(e) => setNewsSize(Number(e.target.value))}
              >
                {newsSizeOptions.map((size) => (
                  <option key={size} value={size}>
                    {size} 条
                  </option>
                ))}
              </select>
              {signalModuleState.loading && timelineNews.length > 0 && <span className="text-amber-600">更新中...</span>}
              {signalModuleState.error && timelineNews.length > 0 && (
                <button type="button" onClick={() => onReloadModule?.('signals')} className="text-rose-500 hover:underline">
                  重新加载
                </button>
              )}
              <span className="text-[11px] text-slate-500">待分析 {pendingCount} 条</span>
            </div>
          </div>

          <div className="timeline-scroll mt-2 flex-1 pr-3 max-h-[520px] lg:max-h-[640px] overflow-y-auto min-w-0">
            {signalModuleState.loading && !timelineNews.length ? (
              <ModuleInlineStatus message="正在拉取基本面资讯..." />
            ) : signalModuleState.error && !timelineNews.length ? (
              <ModuleInlineStatus
                variant="error"
                message={signalModuleState.error || '获取资讯失败'}
                onRetry={() => onReloadModule?.('signals')}
              />
            ) : filteredTimelineGroups.length ? (
              filteredTimelineGroups.map((group) => {
                const metric = group.metric
                const weighted = metric ? (metric.weighted_score ?? metric.score) : null
                const sentimentSummaryColor =
                  weighted !== null ? (weighted >= 0 ? 'text-emerald-600' : 'text-rose-500') : 'text-slate-500'
                const weightedLabel = weighted !== null ? `${weighted >= 0 ? '+' : ''}${(weighted * 100).toFixed(0)}%` : '--'
                return (
                  <div key={group.key} className="mb-10 last:mb-0">
                    <div className="sticky top-0 z-10 pb-2">
                      <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{group.displayDate}</p>
                          <p className="text-xs text-slate-400">{group.weekday || '未知日期'}</p>
                        </div>
                        {metric && (
                          <div className="flex items-center gap-3 text-[11px] text-slate-500">
                            <span>利好 {metric.bullish}</span>
                            <span>利空 {metric.bearish}</span>
                            <span>中性 {metric.neutral}</span>
                            <span className={`font-semibold ${sentimentSummaryColor}`}>情绪 {weightedLabel}</span>
                          </div>
                        )}
                      </div>
                    </div>
                    <ol className="relative mt-4 border-l border-slate-100 pl-4 space-y-4">
                      {group.items.map((item, index) => {
                        const analysis = item.analysis || {}
                        const sentiment = (item.sentiment || 'neutral') as string
                        const sentimentKey: 'bullish' | 'bearish' | 'neutral' =
                          sentiment === 'bullish' || sentiment === 'bearish'
                            ? sentiment
                            : sentiment === 'neutral'
                            ? 'neutral'
                            : 'neutral'
                        const style = sentimentStyles[sentimentKey] || sentimentStyles.neutral
                        const summary = analysis.summary || item.snippet
                        const rawHint = analysis.action_hint
                        const hint = rawHint && summary && rawHint.trim() === summary.trim() ? null : rawHint
                        const confidence =
                          analysis.confidence !== undefined ? `${Math.round((analysis.confidence || 0) * 100)}%` : null
                        const horizon = analysis.impact_horizon
                        const eventType = analysis.event_type
                        const effectiveness = analysis.effectiveness
                        const impactScore = analysis.impact_score
                        const sensitivity = analysis.market_sensitivity
                        const durationDays = analysis.duration_days
                        const tags = analysis.themes || []
                        const providerKey = (analysis.analysis_provider || '').toString().toLowerCase()
                        const providerMeta = analysisProviderMeta[providerKey]
                        const isPending = providerKey === 'pending' || (!analysis.sentiment && !analysis.analysis_provider)
                        const cardClasses = isPending ? 'opacity-80' : ''
                        const key = `${item.url}-${index}`
                        return (
                          <li key={key} className="relative pl-6">
                            <span className={`absolute -left-[7px] top-6 h-3 w-3 rounded-full border-2 border-white shadow ${style.dot}`} />
                            <div className={`rounded-2xl border border-slate-100 bg-white/90 p-4 transition ${style.border} ${cardClasses}`}>
                              <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${style.badge}`}>
                                    {sentiment === 'bullish' ? '利好' : sentiment === 'bearish' ? '利空' : '中性'}
                                  </span>
                                  <span>{formatDateTime(item.publish_time || item.published_at)}</span>
                                  {eventType && <span>{eventType}</span>}
                                  {effectiveness && (
                                    <span>{effectiveness === 'fresh' ? '新信息' : effectiveness === 'diminished' ? '影响减弱' : '已消化'}</span>
                                  )}
                                  {confidence && <span>置信 {confidence}</span>}
                                  {horizon && <span>{horizon}</span>}
                                  {sensitivity && <span>敏感度 {sensitivity}</span>}
                                  {impactScore !== undefined && <span>影响 {impactScore}</span>}
                                  {durationDays && <span>持续 {durationDays}天</span>}
                                </div>
                                {item.source && <span className="text-[11px] text-slate-400">{item.source}</span>}
                                {providerMeta && (
                                  <span className={`text-[11px] px-2 py-0.5 rounded-full ${providerMeta.className}`}>
                                    {providerMeta.label}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-start gap-2">
                                <a
                                  href={item.url}
                                  className="mt-2 block text-sm font-semibold text-slate-900 hover:text-blue-600"
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {item.title || '未命名资讯'}
                                </a>
                                {isPending && (
                                  <button
                                    type="button"
                                    className="ml-auto mt-1 text-[11px] px-2 py-1 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50"
                                    onClick={() => onAnalyzeNow?.(item)}
                                    title="立即触发分析"
                                  >
                                    触发分析
                                  </button>
                                )}
                              </div>
                              {summary && <p className="text-xs text-slate-500 mt-1 leading-relaxed">{summary}</p>}
                              {hint && <p className="text-xs text-slate-400 mt-1">建议：{hint}</p>}
                              {tags.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                  {tags.slice(0, 5).map((tag) => (
                                    <span key={tag} className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                                      {tag}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </li>
                        )
                      })}
                    </ol>
                  </div>
                )
              })
            ) : (
              <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-dashed border-slate-200 text-sm text-slate-400">
                {timelineNews.length ? '当前筛选暂无资讯' : '暂无资讯'}
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-4 self-stretch min-w-[280px]">
          {capitalModuleState.error && !flowSummary && !distributionSummary && (
            <ModuleInlineStatus
              variant="error"
              message={capitalModuleState.error || '资金模块加载失败'}
              onRetry={() => onReloadModule?.('capital')}
            />
          )}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-slate-900">持仓速览</h4>
              <span className="text-xs text-slate-400">同步富途账户</span>
            </div>
            {holdingEntries.length ? (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                {holdingEntries.map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-slate-500 text-xs">{key}</dt>
                    <dd className="text-base font-semibold text-slate-900">{value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-sm text-slate-500">暂无持仓记录</p>
            )}
          </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-slate-900">基础面报告（最新）</h4>
              <a
                className="text-xs text-blue-600 hover:underline"
                href={`/fundamental?code=${data.code}`}
                onClick={(e) => {
                  if (onNavigate) {
                    e.preventDefault()
                    onNavigate(`/fundamental?code=${data.code}`)
                  }
                }}
              >
                更多
              </a>
            </div>
            {reportListLoading ? (
              <div className="text-xs text-slate-500">加载中...</div>
            ) : latestReports.length === 0 ? (
              <div className="text-xs text-slate-400">暂无报告，点击生成日报/周报</div>
            ) : (
              <div className="space-y-2">
                {latestReports.map((item) => (
                  <a
                    key={item.id}
                    className="block rounded-xl border border-slate-200 p-3 hover:border-blue-200"
                    href={`/fundamental-report?id=${item.id}`}
                    onClick={(e) => {
                      if (onNavigate) {
                        e.preventDefault()
                        onNavigate(`/fundamental-report?id=${item.id}`)
                      }
                    }}
                  >
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <div className="font-semibold text-slate-900 truncate mr-2">{item.title || `${item.code} ${item.date}`}</div>
                      <span>{item.date}</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1 line-clamp-3">{item.report}</p>
                  </a>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-slate-900">资金流向</h4>
              <span className="text-xs text-slate-400">{flowSummary?.latest_time ? formatDateTime(flowSummary.latest_time) : '--'}</span>
            </div>
            {capitalModuleState.loading && !flowSummary ? (
              <ModuleInlineStatus message="正在获取资金流向..." compact />
            ) : flowSummary ? (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-slate-500 text-xs">总体</dt>
                  <dd className="text-base font-semibold text-slate-900">{flowSummary.overall_trend ?? '--'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 text-xs">主力</dt>
                  <dd className="text-base font-semibold text-slate-900">{flowSummary.main_trend ?? '--'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 text-xs">净流入</dt>
                  <dd className="text-base font-semibold text-emerald-600">{formatAmount(flowSummary.latest_net_inflow)}</dd>
                </div>
                <div>
                  <dt className="text-slate-500 text-xs">主力净流入</dt>
                  <dd className="text-base font-semibold text-emerald-600">{formatAmount(flowSummary.latest_main_inflow)}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-slate-500">暂无资金流向数据</p>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-slate-900">资金分布</h4>
              <span className="text-xs text-slate-400">{distributionSummary?.update_time ? formatDateTime(distributionSummary.update_time) : '--'}</span>
            </div>
            {capitalModuleState.loading && !distributionSummary ? (
              <ModuleInlineStatus message="正在汇总资金分布..." compact />
            ) : distributionSummary ? (
              <div className="space-y-3 text-sm">
                <div className="text-base font-semibold text-slate-900">{distributionSummary.overall_trend ?? '--'}</div>
                <div className="text-xs text-slate-500">
                  主导资金：{distributionSummary.dominant_fund_type ?? '--'} · {formatAmount(distributionSummary.dominant_fund_amount)}
                </div>
                <div className="space-y-2">
                  {breakdownItems.map((item) => (
                    <div key={item.label}>
                      <div className="flex items-center justify-between text-xs text-slate-500">
                        <span>{item.label}</span>
                        <span className="text-slate-900 font-medium">{formatAmount(item.value)}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-100">
                        <div
                          className={`${(item.value ?? 0) >= 0 ? 'bg-emerald-400' : 'bg-rose-400'} h-full rounded-full`}
                          style={{
                            width: breakdownMax ? `${Math.min(100, (Math.abs(item.value ?? 0) / breakdownMax) * 100)}%` : '0%'
                          }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">暂无资金分布数据</p>
            )}
          </div>
        </aside>
      </div>

      <section className="rounded-3xl border border-slate-100 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">多模型策略分析</h3>
            <p className="text-xs text-slate-400">并行调用 DeepSeek / Kimi / Gemini，生成综合建议</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <label className="text-slate-500">评审模型：</label>
            <select
              className="rounded-full border border-slate-200 px-2 py-1 text-slate-700"
              value={analysisJudge}
              onChange={(e) => setAnalysisJudge(e.target.value)}
            >
              <option value="gemini">Gemini</option>
              <option value="deepseek">DeepSeek</option>
              <option value="kimi">Kimi</option>
            </select>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          {llmModelOptions.map((option) => {
            const active = analysisModels.includes(option.key)
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => toggleModel(option.key)}
                className={`px-3 py-1.5 rounded-full text-xs border transition ${
                  active ? 'bg-slate-900 text-white border-slate-900' : 'border-slate-200 text-slate-500 bg-white'
                }`}
              >
                {option.label}
              </button>
            )
          })}
        </div>
        <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center">
          <input
            type="text"
            value={analysisQuestion}
            onChange={(e) => setAnalysisQuestion(e.target.value)}
            placeholder="补充问题，例如：侧重短线操作或风险控制"
            className="flex-1 rounded-2xl border border-slate-200 px-4 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={handleRunAnalysis}
            disabled={analysisLoading}
            className="px-4 py-2 rounded-2xl bg-blue-600 text-white text-sm hover:bg-blue-500 disabled:opacity-50"
          >
            {analysisLoading ? '分析中...' : '开始分析'}
          </button>
        </div>
        {analysisError && <div className="text-xs text-rose-500 mt-2">{analysisError}</div>}
        {shouldShowAnalysisPanel && (
          <div className="mt-5 space-y-4">
            <div className="text-xs text-slate-400">
              分析时间 {analysisStartTime ? formatDateTime(analysisStartTime) : '--'} -{' '}
              {analysisEndTime ? formatDateTime(analysisEndTime) : analysisLoading ? '分析中...' : '--'}
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {analysisModels.map((model) => {
                const state = analysisModelStates[model] || { status: 'idle' }
                const resultPayload = state.result as MultiModelAction | undefined
                const rawResultText =
                  state.rawText || ((state.result as Record<string, any>)?.raw as string | undefined)
                const hasStructured = !!(
                  resultPayload &&
                  (resultPayload.action ||
                    resultPayload.rationale ||
                    resultPayload.entry_price !== undefined ||
                    resultPayload.target_price !== undefined ||
                    resultPayload.stop_loss !== undefined)
                )
                const statusLabel =
                  state.status === 'success'
                    ? '完成'
                    : state.status === 'disabled'
                    ? '未启用'
                    : state.status === 'error'
                    ? '失败'
                    : '执行中'
                const statusColor =
                  state.status === 'success'
                    ? 'text-emerald-600'
                    : state.status === 'error'
                    ? 'text-rose-500'
                    : state.status === 'disabled'
                    ? 'text-slate-400'
                    : 'text-blue-500'
                return (
                  <div key={model} className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4 min-h-[160px] flex flex-col">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-slate-900">
                        {model === 'deepseek'
                          ? 'DeepSeek'
                          : model === 'kimi'
                          ? 'Kimi'
                          : model === 'gemini'
                          ? 'Gemini'
                          : model}
                      </span>
                      <span className={`text-xs ${statusColor} flex items-center gap-1`}>
                        {state.status === 'loading' && <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse" />}
                        {statusLabel}
                      </span>
                    </div>
                    {state.status === 'success' && hasStructured && resultPayload && (
                      <div className="mt-2 space-y-1 text-sm text-slate-600 flex-1">
                        <div>操作：{resultPayload.action || '--'}</div>
                        <div>信心：{resultPayload.confidence !== undefined ? `${Math.round(resultPayload.confidence * 100)}%` : '--'}</div>
                        <div>理由：{resultPayload.rationale || '--'}</div>
                      </div>
                    )}
                    {state.status === 'success' && !hasStructured && rawResultText && (
                      <pre className="mt-2 text-[11px] whitespace-pre-wrap break-words rounded-xl bg-white/80 p-2 text-slate-600 border border-slate-100 flex-1">
                        {formatPlainText(rawResultText)}
                      </pre>
                    )}
                    {state.status === 'loading' && (
                      <div className="mt-4 text-xs text-slate-500">正在分析...</div>
                    )}
                    {state.error && <div className="text-xs text-rose-500 mt-2">{state.error}</div>}
                    {state.status === 'success' && !hasStructured && !rawResultText && (
                      <div className="text-xs text-slate-500 mt-2">模型未返回结构化结果</div>
                    )}
                  </div>
                )
              })}
            </div>
            {analysisResult?.judge && (
              <div className="rounded-3xl border border-blue-200 bg-blue-50/70 p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900">
                      {analysisResult.judge.model === 'gemini' ? 'Gemini 评审结果' : '策略评审结果'}
                    </h4>
                    <p className="text-xs text-slate-500">聚合多模型观点，仅输出一个可执行方案</p>
                  </div>
                  {analysisResult.judge.status === 'success' && judgeRecommended && (
                    <button
                      type="button"
                      onClick={handleSaveJudgeRecommendation}
                      disabled={savingStrategy}
                      className="px-3 py-1.5 rounded-full bg-blue-600 text-white text-xs hover:bg-blue-500 disabled:opacity-50"
                    >
                      {savingStrategy ? '保存中...' : '保存为策略'}
                    </button>
                  )}
                </div>
                {analysisResult.judge.status === 'success' && (judgeResult || analysisResult.judge.raw_text) ? (
                  <>
                    {judgeSummaryText && (
                      <p className="rounded-2xl bg-white/70 px-4 py-3 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                        {judgeSummaryText}
                      </p>
                    )}
                    {judgeRecommended ? (
                      <div className="rounded-2xl border border-white bg-white/90 p-4 space-y-3 text-sm text-slate-700">
                        <div className="flex flex-wrap items-center gap-4 text-xs">
                          <span className="text-slate-900">操作：{judgeRecommended.action || '--'}</span>
                          <span>周期：{judgeRecommended.timeframe || '--'}</span>
                          {judgeRecommended.confidence !== undefined && (
                            <span>
                              信心：{Math.round((judgeRecommended.confidence ?? 0) * 100)}%
                            </span>
                          )}
                          {judgeResult?.status === 'insufficient_data' && (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-700">信息不足</span>
                          )}
                        </div>
                        {judgeRecommended.rationale && (
                          <p className="text-sm text-slate-600">{judgeRecommended.rationale}</p>
                        )}
                        <div className="grid gap-3 text-xs sm:grid-cols-3">
                          <div>
                            <div className="text-slate-400">入场</div>
                            <div className="text-base font-semibold text-slate-900">
                              {judgeRecommended.entry_price !== undefined ? formatPrice(judgeRecommended.entry_price) : '--'}
                            </div>
                          </div>
                          <div>
                            <div className="text-slate-400">目标</div>
                            <div className="text-base font-semibold text-slate-900">
                              {judgeRecommended.target_price !== undefined ? formatPrice(judgeRecommended.target_price) : '--'}
                            </div>
                          </div>
                          <div>
                            <div className="text-slate-400">止损</div>
                            <div className="text-base font-semibold text-slate-900">
                              {judgeRecommended.stop_loss !== undefined ? formatPrice(judgeRecommended.stop_loss) : '--'}
                            </div>
                          </div>
                        </div>
                        <PriceRangeBar
                          entry={judgeRecommended.entry_price}
                          target={judgeRecommended.target_price}
                          stop={judgeRecommended.stop_loss}
                          current={quote?.price}
                        />
                        {judgeRecommended.position_sizing && (
                          <div className="text-xs text-slate-500">仓位建议：{judgeRecommended.position_sizing}</div>
                        )}
                        {judgeTags.length > 0 && (
                          <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">
                            {judgeTags.map((tag) => (
                              <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5">
                                #{tag}
                              </span>
                            ))}
                          </div>
                        )}
                        {judgeConditions.length > 0 && (
                          <div className="text-xs">
                            <div className="text-slate-400 mb-1">执行条件</div>
                            <ul className="space-y-1 list-disc pl-4">
                              {judgeConditions.map((cond, idx) => (
                                <li key={`${cond}-${idx}`}>{cond}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {judgeMissingConditions.length > 0 && (
                          <div className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
                            缺失信息：{judgeMissingConditions.join('；')}
                          </div>
                        )}
                        {judgeBasis.length > 0 && (
                          <div className="text-xs">
                            <div className="text-slate-400 mb-1">策略依据</div>
                            <ul className="space-y-1 list-disc pl-4">
                              {judgeBasis.map((text, idx) => (
                                <li key={`${text}-${idx}`}>{text}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="rounded-2xl border border-dashed border-slate-300 bg-white/50 p-4 text-xs text-slate-500 whitespace-pre-wrap">
                        未返回结构化建议，原始内容：{formatPlainText(analysisResult.judge.raw_text) || '—'}
                      </div>
                    )}
                    <div className="grid gap-3 text-xs md:grid-cols-3">
                      <div className="rounded-2xl border border-blue-100 bg-blue-50/80 p-3 space-y-1">
                        <div className="text-sm font-semibold text-blue-700">关键因子</div>
                        {judgeDecidingFactors.length ? (
                          <ul className="space-y-1 list-disc pl-4 text-blue-700">
                            {judgeDecidingFactors.map((factor, idx) => (
                              <li key={`${factor}-${idx}`}>{factor}</li>
                            ))}
                          </ul>
                        ) : (
                          <div className="text-blue-500">暂无</div>
                        )}
                      </div>
                      <div className="rounded-2xl border border-emerald-100 bg-emerald-50/80 p-3 space-y-1">
                        <div className="text-sm font-semibold text-emerald-700">机会</div>
                        {judgeOpportunities.length ? (
                          <ul className="space-y-1 list-disc pl-4 text-emerald-700">
                            {judgeOpportunities.map((note, idx) => (
                              <li key={`${note}-${idx}`}>{note}</li>
                            ))}
                          </ul>
                        ) : (
                          <div className="text-emerald-500">暂无</div>
                        )}
                      </div>
                      <div className="rounded-2xl border border-rose-100 bg-rose-50/80 p-3 space-y-1">
                        <div className="text-sm font-semibold text-rose-700">风险</div>
                        {judgeRisks.length ? (
                          <ul className="space-y-1 list-disc pl-4 text-rose-700">
                            {judgeRisks.map((risk, idx) => (
                              <li key={`${risk}-${idx}`}>{risk}</li>
                            ))}
                          </ul>
                        ) : (
                          <div className="text-rose-500">暂无</div>
                        )}
                      </div>
                    </div>
                    {judgeWarnings.length > 0 && (
                      <div className="rounded-2xl border border-amber-100 bg-amber-50/80 p-3 text-xs text-amber-700 space-y-1">
                        <div className="text-sm font-semibold text-amber-700">注意事项</div>
                        <ul className="list-disc pl-4 space-y-1">
                          {judgeWarnings.map((warn, idx) => (
                            <li key={`${warn}-${idx}`}>{warn}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {judgeResult?.referenced_models && judgeResult.referenced_models.length > 0 && (
                      <div className="text-xs text-slate-500">
                        <div className="text-slate-400 mb-1">参考模型</div>
                        <div className="flex flex-wrap gap-2">
                          {judgeResult.referenced_models.map((ref) => (
                            <span key={ref.model} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600">
                              {ref.model}
                              {ref.weight && <span className="ml-1 text-slate-400">· {ref.weight}</span>}
                              {ref.confidence !== undefined && <span className="ml-1 text-slate-400">{Math.round((ref.confidence ?? 0) * 100)}%</span>}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="rounded-2xl border border-dashed border-blue-200 bg-white/70 p-4 text-sm text-rose-500 space-y-3">
                    <div>{analysisResult.judge.error || '评审失败'}</div>
                    <button
                      type="button"
                      onClick={handleRunAnalysis}
                      disabled={analysisLoading}
                      className="px-3 py-1.5 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50 disabled:opacity-50"
                    >
                      {analysisLoading ? '评审中...' : '重新评审'}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-slate-100 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">策略建议时间轴</h3>
            <p className="text-xs text-slate-400">来自 MCP 策略记录</p>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>{recommendations.length} 条记录</span>
            {recommendationModuleState.loading && recommendations.length > 0 && <span className="text-amber-600">更新中...</span>}
            {recommendationModuleState.error && recommendations.length > 0 && (
              <button
                type="button"
                onClick={() => onReloadModule?.('recommendations')}
                className="text-rose-500 hover:underline"
              >
                重新加载
              </button>
            )}
          </div>
        </div>
        <div className="mt-6 space-y-4 pr-2">
          {recommendationModuleState.loading && !recommendations.length ? (
            <ModuleInlineStatus message="正在同步策略建议..." />
          ) : recommendationModuleState.error && !recommendations.length ? (
            <ModuleInlineStatus
              variant="error"
              message={recommendationModuleState.error || '策略模块加载失败'}
              onRetry={() => onReloadModule?.('recommendations')}
            />
          ) : (
            <RecommendationTimeline items={recommendations} onSelect={handleOpenStrategyDetail} />
          )}
        </div>
      </section>

    </div>
  )
}

type RecommendationTimelineProps = {
  items: RecommendationItem[]
  onSelect?: (item: RecommendationItem) => void
}

function RecommendationTimeline({ items, onSelect }: RecommendationTimelineProps) {
  if (!items.length) {
    return <p className="text-sm text-slate-400">暂无策略建议</p>
  }
  const parseTs = (value?: string) => {
    if (!value) return 0
    const ts = Date.parse(value)
    return Number.isNaN(ts) ? 0 : ts
  }
  const sortedItems = [...items].sort((a, b) => parseTs(b.created_at) - parseTs(a.created_at))
  const actionMap: Record<string, { label: string; color: string }> = {
    BUY: { label: '买入', color: 'bg-emerald-500/15 text-emerald-600' },
    SELL: { label: '卖出', color: 'bg-rose-500/15 text-rose-600' },
    HOLD: { label: '持有', color: 'bg-slate-500/15 text-slate-600' },
    WATCH: { label: '观察', color: 'bg-amber-500/15 text-amber-600' },
    EXIT: { label: '清仓', color: 'bg-rose-500/15 text-rose-600' },
    ADD: { label: '加仓', color: 'bg-emerald-500/15 text-emerald-600' },
    REDUCE: { label: '减仓', color: 'bg-orange-500/15 text-orange-600' }
  }
  const timeframeMap: Record<string, string> = {
    intraday: '日内',
    short_term: '短线',
    mid_term: '中线',
    long_term: '长线'
  }
  return (
    <ol className="relative pl-6 before:absolute before:left-3 before:top-0 before:bottom-0 before:w-px before:bg-slate-200">
      {sortedItems.map((item, index) => {
        const key = item.id ?? item.created_at ?? index
        const action = (item.action || 'WATCH').toUpperCase()
        const actionStyle = actionMap[action] ?? { label: action, color: 'bg-blue-500/15 text-blue-600' }
        const bulletColor =
          action === 'SELL' || action === 'EXIT' || action.includes('空')
            ? 'bg-rose-500'
            : action === 'BUY' || action === 'ADD'
            ? 'bg-emerald-500'
            : 'bg-amber-500'
        const tags = Array.isArray(item.tags) ? item.tags.filter(Boolean) : []
        const hasExecutionParams = item.entry_price || item.target_price || item.stop_loss || item.valid_until
        const evaluationStatus = (item.eval_status || '').toLowerCase()
        const evalColor =
          evaluationStatus === 'completed'
            ? 'text-emerald-600'
            : evaluationStatus === 'invalid'
            ? 'text-rose-500'
            : 'text-slate-500'
        const evalLabel =
          evaluationStatus === 'completed'
            ? '已评估'
            : evaluationStatus === 'invalid'
            ? '失效'
            : '待评估'
        const pnlValue =
          item.eval_pnl_pct !== undefined && item.eval_pnl_pct !== null && !Number.isNaN(item.eval_pnl_pct)
            ? item.eval_pnl_pct
            : null
        const pnlText = pnlValue !== null ? `${pnlValue >= 0 ? '+' : ''}${(pnlValue * 100).toFixed(2)}%` : null
        const createdLabel = formatDateTime(item.created_at)
        const timeframeLabel = item.timeframe ? timeframeMap[item.timeframe] ?? item.timeframe : null
        return (
          <li key={key} className="relative pl-8 pb-8 last:pb-0">
            <span className={`absolute left-1.5 top-6 h-3 w-3 rounded-full border-[3px] border-white ${bulletColor}`} aria-hidden />
            <div className="rounded-3xl border border-slate-100 bg-white shadow-[0_10px_30px_-25px_rgba(15,23,42,0.6)] p-5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-3 py-1 rounded-full font-semibold text-sm ${actionStyle.color}`}>{actionStyle.label}</span>
                  {timeframeLabel && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5">周期 {timeframeLabel}</span>
                  )}
                  {item.status && (
                    <span className="rounded-full bg-slate-900/5 px-2 py-0.5 text-slate-600 uppercase tracking-wide">
                      {item.status}
                    </span>
                  )}
                  {tags.slice(0, 2).map((tag) => (
                    <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">
                      #{tag}
                    </span>
                  ))}
                </div>
                <div className="text-right">
                  <div className="text-slate-900 font-semibold text-sm">{createdLabel}</div>
                  <div className={item.adopted ? 'text-emerald-600 font-medium' : 'text-amber-600'}>
                    {item.adopted ? '已采纳' : '待采纳'}
                  </div>
                </div>
              </div>
              {item.rationale && <p className="text-sm leading-relaxed text-slate-700">{item.rationale}</p>}
              <div className="flex justify-between text-xs text-slate-500">
                <button
                  type="button"
                  onClick={() => onSelect?.(item)}
                  className="text-blue-600 hover:underline"
                >
                  查看详情
                </button>
                <div>
                  {item.entry_price && <span className="mr-3">入场 {formatPrice(item.entry_price)}</span>}
                  {item.target_price && <span className="mr-3">目标 {formatPrice(item.target_price)}</span>}
                  {item.stop_loss && <span>止损 {formatPrice(item.stop_loss)}</span>}
                </div>
              </div>
              {(evaluationStatus || item.eval_summary || pnlText) && (
                <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
                    <div className={`font-semibold ${evalColor}`}>策略评估 · {evalLabel}</div>
                    {pnlText && (
                      <div className={`font-semibold ${pnlValue! >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>盈亏 {pnlText}</div>
                    )}
                    {item.eval_generated_at && <div>{formatDateTime(item.eval_generated_at)}</div>}
                  </div>
                  {item.eval_summary && <p className="mt-2 text-sm text-slate-700 leading-relaxed">{item.eval_summary}</p>}
                </div>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

type ModuleInlineStatusProps = {
  message: string
  variant?: 'loading' | 'error'
  onRetry?: () => void
  compact?: boolean
}

function ModuleInlineStatus({ message, variant = 'loading', onRetry, compact }: ModuleInlineStatusProps) {
  const isLoading = variant === 'loading'
  const baseClass = isLoading
    ? 'border-slate-200 bg-slate-50 text-slate-500'
    : 'border-rose-200 bg-rose-50/80 text-rose-600'
  return (
    <div
      className={`rounded-2xl border border-dashed ${baseClass} ${compact ? 'p-3 text-xs' : 'p-4 text-sm'} flex items-center justify-between gap-3`}
    >
      <span className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${isLoading ? 'bg-slate-300 animate-pulse' : 'bg-rose-400'}`}></span>
        {message}
      </span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="text-xs px-2 py-1 rounded-full border border-slate-200 text-slate-600 hover:bg-white"
        >
          重试
        </button>
      )}
    </div>
  )
}

type ModuleOverlayStatusProps = {
  message: string
  variant?: 'loading' | 'error'
  onRetry?: () => void
}

function ModuleOverlayStatus({ message, variant = 'loading', onRetry }: ModuleOverlayStatusProps) {
  const isLoading = variant === 'loading'
  const textClass = isLoading ? 'text-slate-600' : 'text-rose-600'
  const borderClass = isLoading ? 'border-transparent' : 'border border-rose-200'
  return (
    <div className={`absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-white/85 ${borderClass} ${textClass}`}>
      <span className="text-sm">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-1.5 rounded-full border border-slate-300 text-xs text-slate-600 hover:bg-white"
        >
          重试
        </button>
      )}
    </div>
  )
}

type HoldingsHomePanelProps = {
  sessions: SessionItem[]
  onSelect: (sessionId: string) => void
}

function HoldingsHomePanel({ sessions, onSelect }: HoldingsHomePanelProps) {
  if (!sessions.length) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center text-slate-500">
        暂无持仓订阅，左侧添加股票后即可在此查看综合概况。
      </div>
    )
  }
  const total = sessions.length
  const gainers = sessions.filter((item) => (item.quote?.change_rate ?? 0) > 0)
  const losers = sessions.filter((item) => (item.quote?.change_rate ?? 0) < 0)
  const flat = total - gainers.length - losers.length
  const avgChange =
    sessions.reduce((sum, item) => sum + (item.quote?.change_rate ?? 0), 0) / total
  const topWinners = [...sessions]
    .sort((a, b) => (b.quote?.change_rate ?? 0) - (a.quote?.change_rate ?? 0))
    .slice(0, 4)
  const topLosers = [...sessions]
    .sort((a, b) => (a.quote?.change_rate ?? 0) - (b.quote?.change_rate ?? 0))
    .slice(0, 4)
  const recentSignals = [...sessions]
    .sort(
      (a, b) =>
        Date.parse(b.last_signal_time || b.created_at) -
        Date.parse(a.last_signal_time || a.created_at)
    )
    .slice(0, 6)
  const strategyCounts = sessions.reduce<Record<string, number>>((acc, item) => {
    const key = (item.strategy || '未设置').toUpperCase()
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})
  const strategyEntries = Object.entries(strategyCounts).sort((a, b) => b[1] - a[1])
  const criticalList = sessions
    .map((item) => ({
      session_id: item.session_id,
      code: item.code,
      name: getSessionDisplayName(item),
      rawStrategy: (item.strategy || '').toUpperCase(),
      strategyLabel: formatStrategyLabel(item.strategy),
      change: item.quote?.change_rate ?? 0
    }))
    .filter((item) => item.change <= -2 || item.rawStrategy === 'WATCH')
    .sort((a, b) => a.change - b.change)
    .slice(0, 4)
  const opportunityList = topWinners.filter((item) => (item.quote?.change_rate ?? 0) > 0)
  const lastSignalTimestamp = recentSignals[0]?.last_signal_time
  const lastSignalLabel = lastSignalTimestamp
    ? formatDateTime(lastSignalTimestamp)
    : '暂无信号'
  const strategyProgressList = [...sessions]
    .sort(
      (a, b) =>
        Date.parse(b.last_signal_time || b.created_at) -
        Date.parse(a.last_signal_time || a.created_at)
    )
    .slice(0, 5)

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-400">当前视图</p>
            <h2 className="text-2xl font-semibold text-slate-900">持仓首页</h2>
          </div>
          <div className="text-sm text-slate-500">共 {total} 个关注标的</div>
        </div>
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
            <div className="text-xs text-slate-400">平均涨跌幅</div>
            <div className={`text-2xl font-semibold ${getChangeColor(avgChange)}`}>
              {formatPercent(avgChange)}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              乘数：{gainers.length} 涨 · {losers.length} 跌
            </div>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
            <div className="text-xs text-slate-400">上涨 / 下跌</div>
            <div className="text-2xl font-semibold text-slate-900">
              {gainers.length} / {losers.length}
            </div>
            <div className="text-xs text-slate-400 mt-1">平盘 {flat}</div>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
            <div className="text-xs text-slate-400">最新信号时间</div>
            <div className="text-base font-semibold text-slate-900">{lastSignalLabel}</div>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
            <div className="text-xs text-slate-400">策略覆盖</div>
            <div className="text-2xl font-semibold text-slate-900">{strategyEntries.length}</div>
            <div className="text-xs text-slate-400 mt-1">
              最多：{strategyEntries[0] ? formatStrategyLabel(strategyEntries[0][0]) : '未设置'}（
              {strategyEntries[0]?.[1] || 0} 个）
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">今日领跑</h3>
            <span className="text-xs text-slate-400">涨幅优先</span>
          </div>
          {opportunityList.map((item) => (
            <button
              key={`top-${item.session_id}`}
              type="button"
              onClick={() => onSelect(item.session_id)}
              className="flex w-full items-center justify-between rounded-xl border border-slate-100 px-3 py-2 text-left hover:border-blue-300"
            >
              <div>
                <div className="font-semibold text-slate-900">{getSessionDisplayName(item)}</div>
                <div className="text-xs text-slate-400">{item.code}</div>
              </div>
              <div className={`text-sm font-semibold ${getChangeColor(item.quote?.change_rate)}`}>
                {formatPercent(item.quote?.change_rate)}
              </div>
            </button>
          ))}
          {!opportunityList.length && (
            <p className="text-xs text-slate-400">暂无明显领跑者。</p>
          )}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">压力标的</h3>
            <span className="text-xs text-slate-400">跌幅/WATCH 策略</span>
          </div>
          {criticalList.map((item) => (
            <button
              key={`risk-${item.session_id}`}
              type="button"
              onClick={() => onSelect(item.session_id)}
              className="flex w-full items-center justify-between rounded-xl border border-slate-100 px-3 py-2 text-left hover:border-rose-300"
            >
              <div>
                <div className="font-semibold text-slate-900">{item.name}</div>
                <div className="text-xs text-slate-400">
                  {item.code} · {item.strategyLabel}
                </div>
              </div>
              <div className={`text-sm font-semibold ${getChangeColor(item.change)}`}>
                {formatPercent(item.change)}
              </div>
            </button>
          ))}
        {!criticalList.length && <p className="text-xs text-slate-400">暂无需要关注的标的。</p>}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">策略执行状态</h3>
          <span className="text-xs text-slate-400">采纳 / 执行 / 结束</span>
        </div>
        {strategyProgressList.map((item) => {
          const { state, badge } = classifyStrategyState(item.strategy)
          return (
            <div
              key={`state-${item.session_id}`}
              className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2 hover:border-blue-300 cursor-pointer"
              onClick={() => onSelect(item.session_id)}
            >
              <div>
                <div className="font-semibold text-slate-900">{getSessionDisplayName(item)}</div>
                <div className="text-xs text-slate-400">
                  {item.code} · {formatStrategyLabel(item.strategy)}
                </div>
              </div>
              <span className={`text-[11px] px-2 py-0.5 rounded-full ${badge}`}>{state}</span>
            </div>
          )
        })}
        {!strategyProgressList.length && <p className="text-xs text-slate-400">暂无策略记录。</p>}
      </div>
    </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">最近信号</h3>
            <span className="text-xs text-slate-400">点击即可进入详情</span>
          </div>
          {recentSignals.map((item) => (
            <div
              key={`signal-${item.session_id}`}
              className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2 text-sm hover:border-blue-300 cursor-pointer"
              onClick={() => onSelect(item.session_id)}
            >
              <div>
                <div className="font-semibold text-slate-900">{getSessionDisplayName(item)}</div>
                <div className="text-xs text-slate-400">
                  {item.last_signal_time ? formatDateTime(item.last_signal_time) : '尚无记录'}
                </div>
              </div>
              <div className="text-xs text-slate-500">策略：{formatStrategyLabel(item.strategy)}</div>
            </div>
          ))}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">全部持仓</h3>
            <span className="text-xs text-slate-400">长按/点击可进入详情</span>
          </div>
          <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
            {sessions.map((item) => (
              <button
                key={`list-${item.session_id}`}
                type="button"
                onClick={() => onSelect(item.session_id)}
                className="flex w-full items-center justify-between rounded-xl border border-slate-100 px-3 py-2 text-left hover:border-blue-300"
              >
                <div>
                  <div className="font-semibold text-slate-900">{getSessionDisplayName(item)}</div>
                  <div className="text-xs text-slate-400">{item.code}</div>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-semibold ${getChangeColor(item.quote?.change_rate)}`}>
                    {formatPercent(item.quote?.change_rate)}
                  </div>
                  <div className="text-xs text-slate-400">{formatStrategyLabel(item.strategy)}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

type PriceRangeBarProps = {
  entry?: number | string | null
  target?: number | string | null
  stop?: number | string | null
  current?: number | string | null
}

function PriceRangeBar({ entry, target, stop, current }: PriceRangeBarProps) {
  const entryValue = toNumeric(entry)
  const targetValue = toNumeric(target)
  const stopValue = toNumeric(stop)
  const currentValue = toNumeric(current)

  const markers = [
    { key: 'stop', label: '止损', value: stopValue, dot: 'bg-rose-500', text: 'text-rose-600' },
    { key: 'entry', label: '入场', value: entryValue, dot: 'bg-slate-900', text: 'text-slate-900' },
    { key: 'current', label: '现价', value: currentValue, dot: 'bg-blue-500', text: 'text-blue-600' },
    { key: 'target', label: '目标', value: targetValue, dot: 'bg-emerald-500', text: 'text-emerald-600' }
  ].filter((marker) => marker.value !== null) as Array<{
    key: string
    label: string
    value: number
    dot: string
    text: string
  }>

  if (markers.length < 2) {
    return null
  }

  const values = markers.map((marker) => marker.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || Math.max(Math.abs(max), 1) * 0.01 || 1

  const getOffset = (value: number) => ((value - min) / span) * 100

  return (
    <div className="mt-2 space-y-2 text-xs">
      <div className="flex justify-between text-[11px] text-slate-400">
        <span>{formatPrice(min)}</span>
        <span>{formatPrice(max)}</span>
      </div>
      <div className="relative h-2 rounded-full bg-gradient-to-r from-rose-50 via-slate-50 to-emerald-50">
        <div className="absolute inset-0 rounded-full border border-slate-200" />
        {markers.map((marker) => (
          <div
            key={marker.key}
            className="absolute -top-4 flex flex-col items-center text-[10px]"
            style={{ left: `${getOffset(marker.value)}%`, transform: 'translateX(-50%)' }}
          >
            <span className={`rounded-full border border-white px-1.5 py-0.5 font-medium leading-tight shadow ${marker.text}`}>
              {marker.label}
            </span>
            <span className={`mt-1 h-3 w-3 rounded-full border-2 border-white shadow ${marker.dot}`} />
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
        {markers.map((marker) => (
          <span key={`${marker.key}-legend`} className="flex items-center gap-1">
            <span className={`h-2 w-2 rounded-full ${marker.dot}`} />
            <span>
              {marker.label} {formatPrice(marker.value)}
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

type StrategyDetailPageProps = {
  strategyId: string
  initialStrategy?: RecommendationItem | null
  onBack: () => void
  onStrategyUpdated: (item: RecommendationItem) => void
}

function StrategyDetailPage({ strategyId, initialStrategy, onBack, onStrategyUpdated }: StrategyDetailPageProps) {
  const [strategy, setStrategy] = useState<RecommendationItem | null>(initialStrategy ?? null)
  const [loading, setLoading] = useState(!initialStrategy)
  const [error, setError] = useState<string | null>(null)
  const [evaluations, setEvaluations] = useState<StrategyEvaluationRecord[]>([])
  const [evalLoading, setEvalLoading] = useState(true)
  const [alerts, setAlerts] = useState<StrategyAlertRecord[]>([])
  const [alertsLoading, setAlertsLoading] = useState(true)
  useEffect(() => {
    if (initialStrategy) {
      setStrategy(initialStrategy)
      setLoading(false)
    }
  }, [initialStrategy])
  useEffect(() => {
    let aborted = false
    async function fetchDetail() {
      if (initialStrategy && initialStrategy.id?.toString() === strategyId) {
        return
      }
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/recommendations/${strategyId}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || '加载失败')
        }
        const json = (await res.json()) as ApiResponse<RecommendationItem>
        if (json.ret_code !== 0 || !json.data) {
          throw new Error(json.ret_msg || '加载失败')
        }
        if (!aborted) {
          setStrategy(json.data)
        }
      } catch (err) {
        if (!aborted) {
          setError((err as Error).message)
        }
      } finally {
        if (!aborted) {
          setLoading(false)
        }
      }
    }
    fetchDetail()
    return () => {
      aborted = true
    }
  }, [strategyId, initialStrategy])

  const refreshEvaluations = async () => {
    setEvalLoading(true)
    setError((prev) => prev)
    try {
      const res = await fetch(`/api/recommendations/${strategyId}/evaluations`)
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '加载评估历史失败')
      }
      const json = (await res.json()) as ApiResponse<{ items: StrategyEvaluationRecord[] }>
      if (json.ret_code !== 0 || !json.data) {
        throw new Error(json.ret_msg || '加载评估历史失败')
      }
      setEvaluations(json.data.items || [])
    } catch (err) {
      console.warn(err)
    } finally {
      setEvalLoading(false)
    }
  }

  useEffect(() => {
    refreshEvaluations()
    refreshAlerts()
  }, [strategyId])

  const refreshAlerts = async () => {
    setAlertsLoading(true)
    try {
      const res = await fetch(`/api/recommendations/${strategyId}/alerts`)
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '加载盯盘事件失败')
      }
      const json = (await res.json()) as ApiResponse<{ items: StrategyAlertRecord[] }>
      if (json.ret_code !== 0 || !json.data) {
        throw new Error(json.ret_msg || '加载盯盘事件失败')
      }
      setAlerts(json.data.items || [])
    } catch (err) {
      console.warn(err)
    } finally {
      setAlertsLoading(false)
    }
  }
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">策略详情</h1>
          <p className="text-xs text-slate-500">编号 #{strategyId}</p>
        </div>
        <button onClick={onBack} className="rounded-full border border-slate-200 px-4 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
          返回看板
        </button>
      </header>
      <main className="mx-auto max-w-5xl p-6">
        {loading && <p className="text-sm text-slate-500">加载中...</p>}
        {error && <p className="text-sm text-rose-500">{error}</p>}
        {!loading && strategy && (
          <StrategyDetailView
            strategy={strategy}
            evaluations={evaluations}
            evalLoading={evalLoading}
            alerts={alerts}
            alertsLoading={alertsLoading}
            onStrategyUpdated={(updated) => {
              setStrategy(updated)
              onStrategyUpdated(updated)
              refreshEvaluations()
              refreshAlerts()
            }}
            onRefreshEvaluations={refreshEvaluations}
            onRefreshAlerts={refreshAlerts}
          />
        )}
      </main>
    </div>
  )
}

type StrategyDetailViewProps = {
  strategy: RecommendationItem
  evaluations: StrategyEvaluationRecord[]
  evalLoading: boolean
  alerts: StrategyAlertRecord[]
  alertsLoading: boolean
  onStrategyUpdated: (item: RecommendationItem) => void
  onRefreshEvaluations: () => Promise<void> | void
  onRefreshAlerts: () => Promise<void> | void
}

function StrategyDetailView({ strategy, evaluations, evalLoading, alerts, alertsLoading, onStrategyUpdated, onRefreshEvaluations, onRefreshAlerts }: StrategyDetailViewProps) {
  const actionLabel = strategy.action || '—'
  const timeframe = strategy.timeframe || '—'
  const confidence = strategy.confidence !== undefined ? `${Math.round(strategy.confidence * 100)}%` : '--'
  const reevalAnalysis = (strategy.eval_detail && typeof strategy.eval_detail === 'object'
    ? (strategy.eval_detail.analysis || strategy.eval_detail)
    : null) as MultiModelAnalysisResponse | null
  const contextSnapshot =
    reevalAnalysis?.context_snapshot || strategy.analysis_context || strategy.judge_result?.context_snapshot
  const contextText = contextSnapshot?.context_text
  const models = (reevalAnalysis?.models as MultiModelModelResult[]) ?? strategy.model_results ?? []
  const judge = (reevalAnalysis?.judge as MultiModelJudgeResult) ?? strategy.judge_result
  const recommended = judge?.result?.recommended
  const snapshotQuote =
    (contextSnapshot?.quote as QuoteDetail | undefined) ??
    (strategy.analysis_context?.quote as QuoteDetail | undefined)
  const detailEntryPrice = strategy.entry_price ?? recommended?.entry_price
  const detailTargetPrice = strategy.target_price ?? recommended?.target_price
  const detailStopPrice = strategy.stop_loss ?? recommended?.stop_loss
  const detailCurrentPrice = snapshotQuote?.price
  const showPriceSummary =
    detailEntryPrice !== undefined ||
    detailTargetPrice !== undefined ||
    detailStopPrice !== undefined ||
    detailCurrentPrice !== undefined
  const [updating, setUpdating] = useState(false)
  const [reevaluating, setReevaluating] = useState(false)
  const [statusUpdating, setStatusUpdating] = useState(false)

  const handleToggleAdopted = async () => {
    if (!strategy.id) return
    setUpdating(true)
    try {
      const res = await fetch(`/api/recommendations/${strategy.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          adopted: !strategy.adopted,
          adopted_at: new Date().toISOString()
        })
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '更新失败')
      }
      const json = (await res.json()) as ApiResponse<RecommendationItem>
      if (json.ret_code !== 0 || !json.data) {
        throw new Error(json.ret_msg || '更新失败')
      }
      onStrategyUpdated(json.data)
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setUpdating(false)
    }
  }

  const handleReevaluate = async () => {
    if (!strategy.id) return
    setReevaluating(true)
    try {
      const res = await fetch(`/api/recommendations/${strategy.id}/reevaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '重新评估失败')
      }
      const json = (await res.json()) as ApiResponse<{ analysis: any; updated?: RecommendationItem }>
      if (json.ret_code !== 0) {
        throw new Error(json.ret_msg || '重新评估失败')
      }
      if (json.data?.updated) {
        onStrategyUpdated(json.data.updated)
      }
      await onRefreshEvaluations()
      await onRefreshAlerts()
      alert('重新评估完成')
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setReevaluating(false)
    }
  }


  const formattedPnl =
    strategy.eval_pnl_pct !== undefined && strategy.eval_pnl_pct !== null
      ? `${((strategy.eval_pnl_pct ?? 0) * 100).toFixed(2)}%`
      : '--'

  const handleStatusChange = async (nextStatus: string) => {
    if (!strategy.id) return
    setStatusUpdating(true)
    try {
      const res = await fetch(`/api/recommendations/${strategy.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus })
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '更新状态失败')
      }
      const json = (await res.json()) as ApiResponse<RecommendationItem>
      if (json.ret_code !== 0 || !json.data) {
        throw new Error(json.ret_msg || '更新状态失败')
      }
      onStrategyUpdated(json.data)
    } catch (err) {
      alert((err as Error).message)
    } finally {
      setStatusUpdating(false)
    }
  }
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-100 bg-slate-50/80 p-5">
        <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600">
          <span className="text-xl font-semibold text-slate-900">{actionLabel}</span>
          <span>周期：{timeframe}</span>
          <span>信心：{confidence}</span>
          <span>来源：{strategy.source || 'multi-model'}</span>
          <span>状态：{strategy.status || 'draft'}</span>
          <button
            className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 disabled:opacity-50"
            onClick={handleToggleAdopted}
            disabled={updating}
          >
            {strategy.adopted ? '取消采纳' : '标记采纳'}
          </button>
          <button
            className="rounded-full border border-emerald-300 px-3 py-1 text-xs text-emerald-600 hover:bg-emerald-50 disabled:opacity-50"
            onClick={() => handleStatusChange('running')}
            disabled={statusUpdating || strategy.status === 'running'}
          >
            开始执行
          </button>
          <button
            className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 disabled:opacity-50"
            onClick={() => handleStatusChange('completed')}
            disabled={statusUpdating || strategy.status === 'completed'}
          >
            结束策略
          </button>
          <button
            className="rounded-full border border-blue-200 px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 disabled:opacity-50"
            onClick={handleReevaluate}
            disabled={reevaluating}
          >
            {reevaluating ? '评估中...' : '重新评估'}
          </button>
        </div>
        <div className="mt-2 text-xs text-slate-500">生成时间：{formatDateTime(strategy.created_at)}</div>
        {strategy.rationale && <p className="mt-3 text-sm leading-relaxed text-slate-700">{strategy.rationale}</p>}
        {showPriceSummary && (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white/80 p-4 space-y-3">
            <div className="grid gap-3 text-xs text-slate-600 sm:grid-cols-4">
              <div>
                <div className="text-slate-400">入场</div>
                <div className="text-base font-semibold text-slate-900">{formatPrice(detailEntryPrice)}</div>
              </div>
              <div>
                <div className="text-slate-400">目标</div>
                <div className="text-base font-semibold text-slate-900">{formatPrice(detailTargetPrice)}</div>
              </div>
              <div>
                <div className="text-slate-400">止损</div>
                <div className="text-base font-semibold text-slate-900">{formatPrice(detailStopPrice)}</div>
              </div>
              <div>
                <div className="text-slate-400">现价</div>
                <div className="text-base font-semibold text-slate-900">{formatPrice(detailCurrentPrice)}</div>
              </div>
            </div>
            <PriceRangeBar
              entry={detailEntryPrice}
              target={detailTargetPrice}
              stop={detailStopPrice}
              current={detailCurrentPrice}
            />
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-100 bg-white p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-slate-900">策略评估</h4>
          <span className="text-xs text-slate-500">
            最近评估时间：{strategy.eval_generated_at ? formatDateTime(strategy.eval_generated_at) : '未评估'}
          </span>
        </div>
        {strategy.eval_status ? (
          <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600 space-y-2">
            <div className="flex flex-wrap gap-4 text-xs">
              <span>状态：{strategy.eval_status}</span>
              <span>盈亏：{formattedPnl}</span>
            </div>
            {strategy.eval_summary && <p className="text-sm text-slate-700">{strategy.eval_summary}</p>}
          </div>
        ) : (
          <p className="text-sm text-slate-500">尚未进行评估。</p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-100 bg-white p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-slate-900">策略上下文</h4>
          {contextSnapshot?.code && <span className="text-xs text-slate-500">{contextSnapshot.code}</span>}
          {reevalAnalysis && <span className="text-xs text-blue-500">来源：最新评估</span>}
        </div>
        {contextText ? (
          <pre className="max-h-48 overflow-y-auto rounded-xl bg-slate-50 p-3 text-xs text-slate-600 whitespace-pre-wrap">{contextText}</pre>
        ) : (
          <p className="text-sm text-slate-500">无上下文记录，建议重新分析。</p>
        )}
        {!reevalAnalysis && strategy.analysis_context?.context_text && (
          <details className="text-xs text-slate-500">
            <summary className="cursor-pointer text-blue-500">查看初次分析上下文</summary>
            <pre className="mt-2 max-h-40 overflow-y-auto rounded-xl bg-slate-50 p-3 whitespace-pre-wrap">
              {strategy.analysis_context.context_text}
            </pre>
          </details>
        )}
      </section>

      <section className="rounded-2xl border border-slate-100 bg-white p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-slate-900">盯盘事件</h4>
          <button
            className="text-xs text-blue-600 hover:underline"
            onClick={async () => {
              await onRefreshAlerts()
              alert('已刷新盯盘事件')
            }}
          >
            刷新
          </button>
        </div>
        {alertsLoading ? (
          <p className="text-sm text-slate-500">加载盯盘事件...</p>
        ) : alerts.length ? (
          <ol className="space-y-2">
            {alerts.map((alert) => (
              <li key={alert.id} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-600">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-slate-900">{formatDateTime(alert.created_at)}</span>
                  <span className="text-[10px] uppercase tracking-widest text-slate-400">{alert.level || 'info'}</span>
                </div>
                <div className="mt-1 text-sm text-slate-700">{alert.message}</div>
                <div className="text-[11px] text-slate-500">类型：{alert.alert_type}</div>
                {alert.payload && (
                  <details className="mt-1 text-slate-500">
                    <summary className="cursor-pointer text-blue-500">查看详情</summary>
                    <pre className="mt-1 max-h-32 overflow-y-auto rounded bg-white p-2 text-[11px] whitespace-pre-wrap">
                      {JSON.stringify(alert.payload, null, 2)}
                    </pre>
                  </details>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-slate-500">暂无盯盘事件。</p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-100 bg-white p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-slate-900">评估历史</h4>
          <button
            className="text-xs text-blue-600 hover:underline"
            onClick={async () => {
              await onRefreshEvaluations()
              alert('已刷新评估历史')
            }}
          >
            刷新
          </button>
        </div>
        {evalLoading ? (
          <p className="text-sm text-slate-500">加载评估记录...</p>
        ) : evaluations.length ? (
          <ol className="space-y-3">
            {evaluations.map((record) => {
              const pnlText =
                record.pnl !== undefined && record.pnl !== null
                  ? `${(record.pnl * 100).toFixed(2)}%`
                  : '--'
              return (
                <li key={record.id} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-600">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="font-semibold text-slate-900">{formatDateTime(record.created_at)}</span>
                    <span>盈亏：{pnlText}</span>
                    {record.judge_model && <span>评审：{record.judge_model}</span>}
                  </div>
                  {record.summary && <p className="mt-2 text-sm text-slate-700">{record.summary}</p>}
                  {record.detail && (
                    <details className="mt-2 text-slate-500">
                      <summary className="cursor-pointer text-blue-500">查看分析详情</summary>
                      <pre className="mt-1 max-h-40 overflow-y-auto rounded-lg bg-white p-2 text-[11px] whitespace-pre-wrap">
                        {JSON.stringify(record.detail, null, 2)}
                      </pre>
                    </details>
                  )}
                </li>
              )
            })}
          </ol>
        ) : (
          <p className="text-sm text-slate-500">暂无评估记录。</p>
        )}
      </section>

      {models.length > 0 && (
        <section className="rounded-2xl border border-slate-100 bg-white p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900">模型建议</h4>
            {reevalAnalysis && <span className="text-xs text-blue-500">来自重新评估</span>}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {models.map((model) => {
              const resultPayload = model.result as MultiModelAction | undefined
              return (
                <div key={`${model.model}-${model.status}-${model.duration}`} className="rounded-xl border border-slate-100 bg-slate-50/70 p-4 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-900">{model.model}</span>
                    <span className="text-xs text-slate-500">{model.status}</span>
                  </div>
                  {resultPayload ? (
                    <div className="text-xs text-slate-600 space-y-1">
                      <div>操作：{resultPayload.action || '--'} · 周期：{resultPayload.timeframe || '--'}</div>
                      <div>信心：{resultPayload.confidence !== undefined ? `${Math.round((resultPayload.confidence ?? 0) * 100)}%` : '--'}</div>
                      {resultPayload.rationale && <div>理由：{resultPayload.rationale}</div>}
                      {resultPayload.conditions && resultPayload.conditions.length > 0 && (
                        <div>条件：{resultPayload.conditions.join('；')}</div>
                      )}
                      {resultPayload.missing_conditions && resultPayload.missing_conditions.length > 0 && (
                        <div className="text-amber-600">缺失：{resultPayload.missing_conditions.join('；')}</div>
                      )}
                      {resultPayload.risk_items && resultPayload.risk_items.length > 0 && (
                        <div>风险：{resultPayload.risk_items.join('；')}</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 whitespace-pre-wrap">
                      {model.raw_text || '未返回结构化结果'}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {judge && (
        <section className="rounded-2xl border border-blue-100 bg-blue-50/70 p-5 space-y-2">
          <h4 className="text-sm font-semibold text-slate-900">评审总结 ({judge.model})</h4>
          {judge.result?.summary && <p className="text-sm text-slate-700 leading-relaxed">{judge.result.summary}</p>}
          {recommended && (
            <div className="text-xs text-slate-600 space-y-1 rounded-xl bg-white/80 p-3">
              <div>最终操作：{recommended.action || '--'} · 周期：{recommended.timeframe || '--'}</div>
              <div>信心：{recommended.confidence !== undefined ? `${Math.round((recommended.confidence ?? 0) * 100)}%` : '--'}</div>
              {recommended.conditions && recommended.conditions.length > 0 && (
                <div>执行条件：{recommended.conditions.join('；')}</div>
              )}
            </div>
          )}
          {judge.result?.risk_notes && judge.result.risk_notes.length > 0 && (
            <div className="text-xs text-rose-500">风险提示：{judge.result.risk_notes.join('；')}</div>
          )}
          {judge.result?.warnings && judge.result.warnings.length > 0 && (
            <div className="text-xs text-amber-600">注意：{judge.result.warnings.join('；')}</div>
          )}
          {judge.result?.referenced_models && (
            <div className="text-xs text-slate-500">
              参考模型：{judge.result.referenced_models.map((ref) => `${ref.model}(${ref.weight || ref.confidence || ''})`).join('、')}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
const parseNewsDate = (value?: string | null) => {
  if (!value) return 0

  const tryParse = (input: string) => {
    const ts = Date.parse(input)
    return Number.isNaN(ts) ? 0 : ts
  }

  const direct = tryParse(value)
  if (direct) return direct

  let normalized = value
    .replace(/[年月]/g, '-')
    .replace(/日/g, '')
    .replace(/[\/]/g, '-')
  normalized = normalized.replace(/[\u3000]+/g, ' ')

  let cleaned = normalized.replace(/[^\d:\-T\s]/g, '').trim()
  if (!cleaned) return 0

  const hasTime = cleaned.includes(':')
  if (cleaned.includes(' ') && !cleaned.includes('T')) {
    cleaned = cleaned.replace(' ', 'T')
  }
  if (!hasTime && /\d{4}-\d{2}-\d{2}/.test(cleaned)) {
    cleaned = `${cleaned}T00:00:00`
  }
  if (!cleaned.endsWith('Z') && cleaned.includes('T')) {
    cleaned = `${cleaned}Z`
  }

  const normalizedTs = tryParse(cleaned)
  if (normalizedTs) return normalizedTs

  const digits = value.match(/\d+/g)
  if (digits && digits.length >= 3) {
    const [year, month, day, hour = '0', minute = '0', second = '0'] = digits
    const utcTs = Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second)
    )
    if (!Number.isNaN(utcTs)) return utcTs
  }

  return 0
}
const computeDailyMetricsFromNews = (news: TimelineNewsItem[]): DailyMetric[] => {
  const buckets = new Map<
    string,
    {
      counts: { bullish: number; bearish: number; neutral: number }
      weights: { bullish: number; bearish: number; neutral: number }
    }
  >()

  news.forEach((item) => {
    const ts = item.timestamp
    if (!ts) return
    const dateKey = new Date(ts).toISOString().slice(0, 10)
    if (!buckets.has(dateKey)) {
      buckets.set(dateKey, {
        counts: { bullish: 0, bearish: 0, neutral: 0 },
        weights: { bullish: 0, bearish: 0, neutral: 0 }
      })
    }
    const bucket = buckets.get(dateKey)!
    const sentiment = normalizeSentiment(item.sentiment)
    bucket.counts[sentiment] += 1
    const analysis = item.analysis || {}
    const impact = Number(analysis.impact_score ?? 50)
    const novelty = Number(analysis.novelty_score ?? analysis.magnitude_score ?? 50)
    let weight = Math.max(0.1, Math.min((impact * 0.7 + novelty * 0.3) / 100, 2))
    const effectiveness = analysis.effectiveness
    if (effectiveness === 'stale') weight *= 0.3
    else if (effectiveness === 'diminished') weight *= 0.6
    bucket.weights[sentiment] += weight
  })

  return Array.from(buckets.entries())
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, { counts, weights }]) => {
      const total = counts.bullish + counts.bearish + counts.neutral
      const totalWeight = weights.bullish + weights.bearish + weights.neutral
      const score = total ? (counts.bullish - counts.bearish) / total : 0
      const weighted = totalWeight ? (weights.bullish - weights.bearish) / totalWeight : 0
      return {
        date,
        bullish: counts.bullish,
        bearish: counts.bearish,
        neutral: counts.neutral,
        score: Math.round(score * 100) / 100,
        weighted_score: Math.round(weighted * 100) / 100
      }
    })
}
