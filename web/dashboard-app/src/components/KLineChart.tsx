import { useEffect, useMemo, useRef, useState } from 'react'
import type { CandlestickData, HistogramData } from 'lightweight-charts'

interface ChartSessionWindow {
  open_time?: string
  close_time?: string
  previous_close?: number
}

export interface KLineChartProps {
  candles: CandlestickData[]
  volumes: HistogramData[]
  accent?: 'emerald' | 'rose' | 'slate'
  sessionWindow?: ChartSessionWindow
}

const ACCENT_MAP: Record<string, { up: string; down: string }> = {
  emerald: { up: '#16a34a', down: '#dc2626' },
  rose: { up: '#16a34a', down: '#dc2626' },
  slate: { up: '#0ea5e9', down: '#dc2626' }
}

export function KLineChart({ candles, volumes, accent = 'emerald', sessionWindow }: KLineChartProps) {
  const priceContainerRef = useRef<HTMLDivElement | null>(null)
  const volumeContainerRef = useRef<HTMLDivElement | null>(null)
  const priceChartRef = useRef<any>(null)
  const volumeChartRef = useRef<any>(null)
  const seriesRef = useRef<any>(null)
  const priceLineRef = useRef<any>(null)
  const volumeSeriesRef = useRef<any>(null)
  const prevCloseLineRef = useRef<any>(null)
  const volumeMapRef = useRef<Map<number, number>>(new Map())
  const [hoverInfo, setHoverInfo] = useState<{ price: number; time: number; volume?: number } | null>(null)

  const parseIsoSeconds = (value?: string): number | null => {
    if (!value) return null
    const ms = Date.parse(value)
    if (Number.isNaN(ms)) return null
    return Math.floor(ms / 1000)
  }

  const formatVolumeValue = (value: number): string => {
    const abs = Math.abs(value)
    if (abs >= 1e8) {
      return `${(value / 1e8).toFixed(2)} 亿`
    }
    if (abs >= 1e4) {
      return `${(value / 1e4).toFixed(2)} 万`
    }
    return value.toFixed(0)
  }

  const formatHoverTime = (unixSeconds?: number): string => {
    if (!unixSeconds) return '--'
    const date = new Date(unixSeconds * 1000)
    if (Number.isNaN(date.getTime())) return '--'
    return date.toLocaleString('zh-CN', { hour12: false })
  }

  useEffect(() => {
    const map = new Map<number, number>()
    volumes.forEach((hist) => {
      if (typeof hist.time === 'number') {
        map.set(hist.time, hist.value)
      }
    })
    volumeMapRef.current = map
  }, [volumes])

  useEffect(() => {
    let dispose = false
    let priceObserver: ResizeObserver | null = null
    let volumeObserver: ResizeObserver | null = null
    async function init() {
      const module = await import('lightweight-charts')
      if (!priceContainerRef.current || !volumeContainerRef.current || dispose) return
      const { createChart, ColorType, CandlestickSeries, HistogramSeries } = module as typeof import('lightweight-charts')

      const priceChart = createChart(priceContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: '#f8fafc' },
          textColor: '#0f172a',
          fontFamily: 'Inter, "PingFang SC", system-ui'
        },
        rightPriceScale: {
          borderVisible: false
        },
        timeScale: {
          borderVisible: false,
          timeVisible: true,
          secondsVisible: false,
          fixLeftEdge: true,
          fixRightEdge: true,
          rightOffset: 0
        },
        grid: {
          vertLines: { color: '#e2e8f0', style: 1 },
          horzLines: { color: '#e2e8f0', style: 1 }
        },
        crosshair: {
          mode: 1
        },
        localization: {
          priceFormatter: (price: number) => price.toFixed(2)
        }
      }) as any
      priceChartRef.current = priceChart
      const palette = ACCENT_MAP[accent] || ACCENT_MAP.emerald
      const series = priceChart.addSeries(CandlestickSeries, {
        upColor: palette.up,
        downColor: palette.down,
        borderDownColor: palette.down,
        borderUpColor: palette.up,
        wickDownColor: palette.down,
        wickUpColor: palette.up,
        priceScaleId: 'right'
      })
      seriesRef.current = series
      if (candles.length) {
        series.setData(candles)
      }

      const volumeChart = createChart(volumeContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: '#ffffff' },
          textColor: '#475569',
          fontFamily: 'Inter, "PingFang SC", system-ui'
        },
        rightPriceScale: { borderVisible: false },
        timeScale: {
          borderVisible: false,
          timeVisible: true,
          secondsVisible: false,
          fixLeftEdge: true,
          fixRightEdge: true,
          rightOffset: 0,
          visible: true
        },
        grid: {
          vertLines: { color: '#e2e8f0', style: 1 },
          horzLines: { color: '#f1f5f9', style: 1 }
        },
        crosshair: {
          mode: 0
        },
        localization: {
          priceFormatter: (price: number) => formatVolumeValue(price)
        }
      }) as any
      volumeChartRef.current = volumeChart
      const volumeSeries = volumeChart.addSeries(HistogramSeries, {
        priceScaleId: 'right',
        priceFormat: {
          type: 'custom',
          minMove: 1,
          formatter: (value: number) => formatVolumeValue(value)
        },
        lastValueVisible: false,
        priceLineVisible: false
      })
      volumeSeriesRef.current = volumeSeries
      if (volumes.length) {
        volumeSeries.setData(volumes)
      }
      volumeChart.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0 } })

      priceObserver = new ResizeObserver(() => {
        if (!priceContainerRef.current) return
        const { clientWidth, clientHeight } = priceContainerRef.current
        priceChart.applyOptions({ width: clientWidth, height: clientHeight })
      })
      priceObserver.observe(priceContainerRef.current)
      volumeObserver = new ResizeObserver(() => {
        if (!volumeContainerRef.current) return
        const { clientWidth, clientHeight } = volumeContainerRef.current
        volumeChart.applyOptions({ width: clientWidth, height: clientHeight })
      })
      volumeObserver.observe(volumeContainerRef.current)
    }
    init()
    return () => {
      dispose = true
      priceObserver?.disconnect()
      volumeObserver?.disconnect()
      priceChartRef.current?.remove()
      volumeChartRef.current?.remove()
      priceChartRef.current = null
      volumeChartRef.current = null
      seriesRef.current = null
      priceLineRef.current = null
      prevCloseLineRef.current = null
      volumeSeriesRef.current = null
    }
  }, [accent, candles.length, volumes.length])

  useEffect(() => {
    if (!seriesRef.current || !candles.length) return
    seriesRef.current.setData(candles)
    if (priceLineRef.current) {
      seriesRef.current.removePriceLine(priceLineRef.current)
    }
    const last = candles[candles.length - 1]
    priceLineRef.current = seriesRef.current.createPriceLine({
      price: last.close,
      color: '#94a3b8',
      lineWidth: 2,
      lineStyle: 2,
      axisLabelVisible: true,
      title: '最新价'
    })
    if (prevCloseLineRef.current) {
      seriesRef.current.removePriceLine(prevCloseLineRef.current)
    }
    if (sessionWindow?.previous_close) {
      prevCloseLineRef.current = seriesRef.current.createPriceLine({
        price: sessionWindow.previous_close,
        color: '#e2e8f0',
        lineStyle: 1,
        lineWidth: 1,
        axisLabelVisible: true,
        title: '昨收'
      })
    }
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.setData(volumes)
    }
    priceChartRef.current?.timeScale().scrollToRealTime()
    volumeChartRef.current?.timeScale().scrollToRealTime()
  }, [candles, volumes, sessionWindow])

  useEffect(() => {
    if (!priceChartRef.current || !sessionWindow?.open_time || !sessionWindow?.close_time) return
    const from = parseIsoSeconds(sessionWindow.open_time)
    const to = parseIsoSeconds(sessionWindow.close_time)
    if (from && to) {
      priceChartRef.current.timeScale().setVisibleRange({ from, to })
      volumeChartRef.current?.timeScale().setVisibleRange({ from, to })
    }
  }, [sessionWindow])

  useEffect(() => {
    if (!priceChartRef.current || !seriesRef.current) return
    const handler = (param: any) => {
      if (!param || param.time === undefined) {
        setHoverInfo(null)
        return
      }
      const time = typeof param.time === 'number' ? param.time : Number(param.time)
      const seriesData = param.seriesData.get(seriesRef.current)
      const price = seriesData?.close ?? seriesData?.value
      if (price === undefined) {
        setHoverInfo(null)
        return
      }
      const volume = volumeMapRef.current.get(time)
      setHoverInfo({ price, time, volume })
    }
    priceChartRef.current.subscribeCrosshairMove(handler)
    return () => {
      priceChartRef.current?.unsubscribeCrosshairMove(handler)
    }
  }, [candles, volumes])

  const latestClose = candles.length ? candles[candles.length - 1].close : null
  const latestVolume = volumes.length ? volumes[volumes.length - 1].value : null
  const tooltipInfo = hoverInfo ?? (latestClose ? { price: latestClose, time: candles[candles.length - 1].time as number, volume: latestVolume ?? undefined } : null)

  if (!candles.length) {
    return (
      <div className="space-y-2">
        <div className="h-56 rounded-3xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-400">暂无K线数据</div>
        <div className="h-20 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-300 text-sm">暂无成交量</div>
        <div className="text-right text-xs text-slate-400 pr-1">成交量单位：股（格式化显示）</div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="relative h-56 rounded-3xl bg-white border border-slate-100">
        <div ref={priceContainerRef} className="absolute inset-0" />
        {tooltipInfo && (
          <div className="absolute top-3 right-3 text-right text-[11px] leading-tight text-slate-600 bg-white/80 px-3 py-2 rounded-2xl shadow">
            <div className="font-semibold">HKD ${tooltipInfo.price?.toFixed(2)}</div>
            <div className="text-slate-400">{formatHoverTime(tooltipInfo.time)}</div>
            <div className="text-slate-500">成交量：{tooltipInfo.volume != null ? formatVolumeValue(tooltipInfo.volume) : '--'}</div>
          </div>
        )}
      </div>
      <div className="relative h-20 rounded-2xl bg-white border border-slate-100">
        <div ref={volumeContainerRef} className="absolute inset-0" />
      </div>
      <div className="text-right text-xs text-slate-400 pr-1">成交量单位：股（自动折算显示万/亿）</div>
    </div>
  )
}

export default KLineChart
