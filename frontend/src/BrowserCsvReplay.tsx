import { useEffect, useMemo, useState } from 'react'
import { FileUp, Pause, Play, RotateCcw, ShieldCheck } from 'lucide-react'
import { CandleChart } from './HistoricalResearch'
import type { Candle } from './HistoricalResearch'

const MAX_BYTES = 12 * 1024 * 1024
const MAX_BARS = 80000
const ISO_UTC = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)$/

export function parseLocalHistoricalCsv(raw: string, loadedAtMs: number): {
  bars: Candle[]; gaps: number
} {
  const source = raw.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').trimEnd()
  const lines = source.split('\n')
  const header = lines.shift()?.trim()
  if (header !== 'timestamp_open,open,high,low,close' &&
      header !== 'timestamp_open,open,high,low,close,volume')
    throw new Error('CSV needs timestamp_open,open,high,low,close[,volume] in exactly that order.')
  const columns = header.split(',').length
  if (lines.length === 0 || lines.length > MAX_BARS)
    throw new Error('CSV must contain between 1 and 80,000 completed M15 candles.')
  const bars: Candle[] = []
  let gaps = 0
  let previous = -1
  for (let i = 0; i < lines.length; i++) {
    const row = lines[i].trim().split(',')
    if (row.length !== columns) throw new Error('CSV row ' + (i + 2) + ' has the wrong number of columns.')
    const [ts, o, h, l, c, vol] = row.map(value => value.trim())
    if (!ISO_UTC.test(ts)) throw new Error('CSV row ' + (i + 2) + ' needs an explicit UTC ISO timestamp.')
    const time = Date.parse(ts)
    if (!Number.isFinite(time) || time % (15 * 60 * 1000) !== 0)
      throw new Error('CSV row ' + (i + 2) + ' must align to a 15-minute UTC candle.')
    if (time <= previous || time + 15 * 60 * 1000 > loadedAtMs)
      throw new Error('CSV row ' + (i + 2) + ' is out of order, duplicate or not yet closed.')
    const parts = [o, h, l, c].map(Number)
    if (parts.some(v => !Number.isFinite(v) || v <= 0))
      throw new Error('CSV row ' + (i + 2) + ' contains an invalid price.')
    if (parts[1] < Math.max(parts[0], parts[2], parts[3]) ||
        parts[2] > Math.min(parts[0], parts[1], parts[3]))
      throw new Error('CSV row ' + (i + 2) + ' has impossible OHLC bounds.')
    if (vol && (!Number.isFinite(Number(vol)) || Number(vol) < 0))
      throw new Error('CSV row ' + (i + 2) + ' has invalid volume.')
    if (previous !== -1 && time - previous !== 15 * 60 * 1000) gaps++
    bars.push({ open_time: new Date(time).toISOString(),
      available_at: new Date(time + 15 * 60 * 1000).toISOString(),
      open: o, high: h, low: l, close: c, volume: vol || null })
    previous = time
  }
  return { bars, gaps }
}

const number = (n: string | undefined) => {
  const value = Number(n)
  return Number.isFinite(value) ? value.toFixed(2) : '—'
}

export function BrowserCsvReplay() {
  const [bars, setBars] = useState<Candle[]>([])
  const [fileName, setFileName] = useState('')
  const [gaps, setGaps] = useState(0)
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(5)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const load = async (file?: File) => {
    setPlaying(false); setError(''); setBusy(true)
    try {
      if (!file) throw new Error('Choose a CSV from your iPhone Files app.')
      if (file.size > MAX_BYTES) throw new Error('File exceeds the 12 MiB safety limit.')
      const parsed = parseLocalHistoricalCsv(await file.text(), Date.now())
      setBars(parsed.bars)
      setFileName(file.name)
      setGaps(parsed.gaps)
      setCursor(Math.min(39, parsed.bars.length - 1))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'CSV cannot be read')
    } finally {
      setBusy(false)
    }
  }
  useEffect(() => {
    if (!playing || !bars.length) return
    const timer = window.setInterval(() => setCursor(value => Math.min(value + speed, bars.length - 1)), 120)
    return () => window.clearInterval(timer)
  }, [playing, bars.length, speed])
  useEffect(() => {
    if (bars.length && cursor >= bars.length - 1 && playing) setPlaying(false)
  }, [bars.length, cursor, playing])
  const visible = useMemo(() => bars.slice(Math.max(0, cursor - 61), cursor + 1), [bars, cursor])
  const current = bars[cursor]
  return <section className="surface panel historical-replay" aria-label="On-device historical CSV candle replay">
    <div className="panel-heading"><div>
      <p className="eyebrow">HISTORICAL DATA · ON-DEVICE</p>
      <h3>Replay an M15 CSV from your iPhone</h3>
    </div><span className="pill pill-blue"><ShieldCheck size={13}/> LOCAL ONLY</span></div>
    <div className="historical-body">
      <p className="skills-disclaimer">Choose a historical XAUUSD M15 CSV from Files. Candle playback works <strong>without a database connection</strong>. The file stays in this browser session; it is <strong>not uploaded, verified, stored or used to train a student</strong>. Closing or reloading the page clears it.</p>
      <div className="historical-toolbar">
        <label className="browser-file-label">CSV · timestamp_open,open,high,low,close[,volume]
          <input type="file" accept=".csv,text/csv" disabled={busy}
            onChange={e => { void load(e.target.files?.[0]); e.target.value = '' }}/>
        </label>
      </div>
      {error && <p className="message-error" role="alert">{error}</p>}
      {busy && <p className="muted">Checking candles on your device…</p>}
      {!bars.length && !busy && <div className="dataset-empty"><FileUp size={18}/>
        Select an M15 CSV to inspect candle-by-candle price movement. Real-money or paper trading is not enabled.
      </div>}
      {!!bars.length && <>
        <div className="historical-meta">
          <span><strong>{fileName}</strong> · {bars.length.toLocaleString('en-GB')} candles</span>
          <span>Detected gaps: {gaps}</span>
          <span>LOCAL · UNVERIFIED</span>
        </div>
        <CandleChart candles={visible}/>
        <div className="historical-figures">
          <div><span>Position</span><strong>{cursor + 1} / {bars.length}</strong></div>
          <div><span>Open</span><strong>{number(current?.open)}</strong></div>
          <div><span>High</span><strong>{number(current?.high)}</strong></div>
          <div><span>Low</span><strong>{number(current?.low)}</strong></div>
          <div><span>Close</span><strong>{number(current?.close)}</strong></div>
        </div>
        <div className="historical-scrubber">
          <label htmlFor="on-device-historical-range">Completed candle at {current ? new Date(current.available_at).toLocaleString('en-GB', { timeZone: 'UTC' }) + ' UTC' : '—'}</label>
          <input type="range" id="on-device-historical-range" min={0} max={bars.length - 1} value={cursor}
            onChange={e => { setPlaying(false); setCursor(Number(e.target.value)) }}/>
        </div>
        <div className="historical-actions">
          <button type="button" className="btn btn-primary" onClick={() => {
            if (cursor >= bars.length - 1) setCursor(0)
            setPlaying(x => !x)
          }}>{playing ? <Pause size={15}/> : <Play size={15}/>} {playing ? 'Pause' : 'Play CSV'}</button>
          <button type="button" className="btn btn-secondary" onClick={() => { setPlaying(false); setCursor(0) }}><RotateCcw size={15}/> Rewind</button>
          <label className="demo-speed">Speed
            <select value={speed} onChange={e => setSpeed(Number(e.target.value))}>
              <option value={1}>1×</option><option value={5}>5×</option><option value={20}>20×</option><option value={100}>100×</option>
            </select>
          </label>
        </div>
        <p className="historical-warning">Local M15 OHLC candles alone cannot justify bid/ask trade fills, net P&amp;L or model skill qualification. For saved imports and provenance reports, connect your Render PostgreSQL database.</p>
      </>}
    </div>
  </section>
}
