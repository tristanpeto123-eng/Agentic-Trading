import { useState } from 'react'
import { FileCheck2, ShieldCheck } from 'lucide-react'

const MAX_BYTES = 12 * 1024 * 1024
const MAX_BARS = 80000
const MINUTE_MS = 60000
const UTC_ISO = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)$/

type Quote = { open: number; close: number }
type QuoteTape = { rows: Map<number, Quote>; gaps: number; missingMinutes: number }
export type M1PairReport = {
  bidRows: number; askRows: number; aligned: number
  bidOnly: number; askOnly: number
  bidGaps: number; askGaps: number
  missingBidMinutes: number; missingAskMinutes: number
  medianOpeningSpread: number; minOpeningSpread: number
  maxOpeningSpread: number; medianClosingSpread: number
  overlapFirstUtc: string; overlapLastUtc: string
}

export function parseLocalM1Quotes(raw: string, now: number): QuoteTape {
  const source = raw.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').trimEnd()
  const lines = source.split('\n')
  const header = lines.shift()?.trim()
  const upper = header === 'Etc/UTC,Open,High,Low,Close,Volume'
  const lower = header === 'time,open,high,low,close,volume'
  if (!upper && !lower)
    throw new Error('Expected Etc/UTC,Open,High,Low,Close,Volume or time,open,high,low,close,volume.')
  if (!lines.length || lines.length > MAX_BARS)
    throw new Error('M1 export must contain 1–80,000 completed minute candles (split longer exports by month).')
  const rows = new Map<number, Quote>()
  let previous = -1
  let gaps = 0
  let missingMinutes = 0
  for (let i = 0; i < lines.length; i++) {
    const fields = lines[i].split(',').map(x => x.trim())
    if (fields.length !== 6 || fields.some(x => x === ''))
      throw new Error('Invalid M1 CSV row ' + (i + 2) + '.')
    const [stamp, opText, hiText, loText, clText, volText] = fields
    if (!UTC_ISO.test(stamp))
      throw new Error('Row ' + (i + 2) + ' needs an explicit ISO UTC timestamp.')
    const time = Date.parse(stamp)
    if (!Number.isFinite(time) || new Date(time).toISOString().slice(0, 19) !== stamp.slice(0, 19) ||
        time % MINUTE_MS !== 0 || time + MINUTE_MS > now)
      throw new Error('Row ' + (i + 2) + ' has an invalid, unclosed or misaligned UTC minute.')
    if (time <= previous)
      throw new Error('M1 timestamps must be strictly increasing and unique.')
    const [op, hi, lo, cl, vol] = [opText, hiText, loText, clText, volText].map(Number)
    if (![op, hi, lo, cl, vol].every(Number.isFinite) || Math.min(op, hi, lo, cl) <= 0 ||
        vol < 0 || hi < Math.max(op, cl, lo) || lo > Math.min(op, cl, hi))
      throw new Error('Row ' + (i + 2) + ' contains invalid OHLC/volume values.')
    if (previous >= 0 && time - previous !== MINUTE_MS) {
      gaps++
      missingMinutes += (time - previous) / MINUTE_MS - 1
    }
    rows.set(time, { open: op, close: cl })
    previous = time
  }
  return { rows, gaps, missingMinutes }
}

function median(numbers: number[]): number {
  const ordered = [...numbers].sort((a, b) => a - b)
  const middle = Math.floor(ordered.length / 2)
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2
}

export function inspectLocalM1Pair(bid: QuoteTape, ask: QuoteTape): M1PairReport {
  const opens: number[] = []
  const closes: number[] = []
  let first = -1
  let last = -1
  for (const [time, quote] of bid.rows) {
    const opposite = ask.rows.get(time)
    if (!opposite) continue
    const openSpread = opposite.open - quote.open
    const closeSpread = opposite.close - quote.close
    if (!(openSpread > 0) || !(closeSpread > 0))
      throw new Error('Crossed or non-positive opening/closing BID/ASK spread at ' + new Date(time).toISOString())
    opens.push(openSpread)
    closes.push(closeSpread)
    if (first === -1) first = time
    last = time
  }
  if (!opens.length)
    throw new Error('BID and ASK files do not contain any matching minute timestamps.')
  const ordered = opens.slice().sort((a, b) => a - b)
  return {
    bidRows: bid.rows.size, askRows: ask.rows.size, aligned: opens.length,
    bidOnly: bid.rows.size - opens.length, askOnly: ask.rows.size - opens.length,
    bidGaps: bid.gaps, askGaps: ask.gaps,
    missingBidMinutes: bid.missingMinutes, missingAskMinutes: ask.missingMinutes,
    minOpeningSpread: ordered[0], medianOpeningSpread: median(opens),
    maxOpeningSpread: ordered[ordered.length - 1],
    medianClosingSpread: median(closes),
    overlapFirstUtc: new Date(first).toISOString(),
    overlapLastUtc: new Date(last).toISOString(),
  }
}

export function M1BidAskInspector() {
  const [bid, setBid] = useState<File | null>(null)
  const [ask, setAsk] = useState<File | null>(null)
  const [report, setReport] = useState<M1PairReport | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function inspect() {
    setBusy(true); setReport(null); setError('')
    try {
      if (!bid || !ask) throw new Error('Select both matching BID and ASK M1 CSVs.')
      if (bid.size > MAX_BYTES || ask.size > MAX_BYTES)
        throw new Error('Each CSV must be under 12 MiB. Split longer history into months.')
      const now = Date.now()
      const [bidRaw, askRaw] = await Promise.all([bid.text(), ask.text()])
      const outcome = inspectLocalM1Pair(
        parseLocalM1Quotes(bidRaw, now),
        parseLocalM1Quotes(askRaw, now),
      )
      setReport(outcome)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not inspect local quote pair.')
    } finally {
      setBusy(false)
    }
  }

  const money = (value: number) => '$' + value.toFixed(3) + '/oz'
  return <section className="surface panel historical-replay" aria-label="Private on-device M1 BID ASK inspector">
    <div className="panel-heading"><div>
      <p className="eyebrow">HISTORICAL DATA · LOCAL BID / ASK</p>
      <h3>Inspect matching XAU/USD M1 quotes</h3>
    </div><span className="pill pill-blue"><ShieldCheck size={13}/> ON-DEVICE</span></div>
    <div className="historical-body">
      <p className="skills-disclaimer">Select the matching 1-minute BID and ASK exports from iPhone Files.
        Both files are read <strong>only in this browser session</strong>; they are not sent to the server,
        stored in your account or used to train a student. Reloading clears the results.</p>
      <div className="historical-toolbar">
        <label htmlFor="local-bid-m1">BID · M1 CSV
          <input id="local-bid-m1" type="file" accept=".csv,text/csv" disabled={busy}
            onChange={e => { setBid(e.currentTarget.files?.[0] ?? null); setReport(null); setError('') }}/>
        </label>
        <label htmlFor="local-ask-m1">ASK · M1 CSV
          <input id="local-ask-m1" type="file" accept=".csv,text/csv" disabled={busy}
            onChange={e => { setAsk(e.currentTarget.files?.[0] ?? null); setReport(null); setError('') }}/>
        </label>
        <button className="btn btn-primary" type="button" disabled={!bid || !ask || busy}
          onClick={() => { void inspect() }}><FileCheck2 size={15}/> {busy ? 'Inspecting…' : 'Inspect M1 pair locally'}</button>
      </div>
      {bid && ask && <p className="muted">{bid.name} / {ask.name}</p>}
      {error && <p className="message-error" role="alert">{error}</p>}
      {report && <>
        <div className="historical-meta">
          <span><strong>{report.aligned.toLocaleString('en-GB')}</strong> aligned M1 candles</span>
          <span>BID-only: {report.bidOnly} · ASK-only: {report.askOnly}</span>
          <span>LOCAL · UNVERIFIED</span>
        </div>
        <div className="historical-figures">
          <div><span>Median OPEN spread</span><strong>{money(report.medianOpeningSpread)}</strong></div>
          <div><span>Median CLOSE spread</span><strong>{money(report.medianClosingSpread)}</strong></div>
          <div><span>Minimum OPEN spread</span><strong>{money(report.minOpeningSpread)}</strong></div>
          <div><span>Maximum OPEN spread</span><strong>{money(report.maxOpeningSpread)}</strong></div>
          <div><span>BID missing minutes</span><strong>{report.missingBidMinutes}</strong></div>
          <div><span>ASK missing minutes</span><strong>{report.missingAskMinutes}</strong></div>
        </div>
        <p className="muted">Overlap: {report.overlapFirstUtc} – {report.overlapLastUtc}</p>
      </>}
      <p className="historical-warning">A matched minute-candle opening/closing spread is only a quote proxy.
        It is not an executable simultaneous tick, certified historical source, independent model result
        or permission to place paper/live orders. Source rights and session breaks still require review.</p>
    </div>
  </section>
}
