import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, ArrowDownRight, ArrowUpRight, LockKeyhole, RefreshCw, ShieldCheck, Wallet } from 'lucide-react'
import { api } from './api'
import type { PaperAccountSnapshot } from './api'
import './PaperAccountPanel.css'

function money(value: string | null | undefined, currency: string): string {
  if (value == null || value === '') return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  const label = currency === 'USD' ? '$' : currency + ' '
  return label + new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(number)
}

function PaperAccountPanel() {
  const [snapshot, setSnapshot] = useState<PaperAccountSnapshot | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const refresh = useCallback(async (signal?: { cancelled: boolean }) => {
    setBusy(true); setError('')
    try {
      const data = await api<PaperAccountSnapshot>('/v1/paper/account')
      if (!signal?.cancelled) setSnapshot(data)
    } catch {
      if (!signal?.cancelled) { setError('Account snapshot unavailable. Verify backend paper credentials and account selection.'); setSnapshot(null) }
    } finally {
      if (!signal?.cancelled) setBusy(false)
    }
  }, [])

  useEffect(() => {
    const signal = { cancelled: false }
    void refresh(signal)
    return () => { signal.cancelled = true }
  }, [refresh])

  const currency = snapshot?.currency || 'USD'
  return <section className="surface alpaca-paper-panel" aria-label="Alpaca paper account">
    <div className="alpaca-paper-heading">
      <div>
        <p className="eyebrow">SPRINT 12 / ALPACA PAPER</p>
        <h3><Wallet size={18}/> Simulated account overview</h3>
        <p className="muted">Read-only brokerage snapshot. Not a strategy performance report.</p>
      </div>
      <button className="btn btn-secondary" type="button" onClick={() => void refresh()} disabled={busy}>
        <RefreshCw size={15} className={busy ? 'alpaca-spinning' : ''}/> {busy ? 'Checking…' : 'Refresh'}
      </button>
    </div>

    {error && <div className="alpaca-paper-alert" role="alert"><AlertCircle size={17}/>{error}</div>}
    {!error && !snapshot && <p className="muted alpaca-paper-status">Fetching paper account status…</p>}
    {snapshot && !snapshot.configured && <div className="alpaca-paper-alert">
      <LockKeyhole size={18}/>
      <div><strong>Backend credentials not configured</strong>
        <p>The GitHub Actions test passed, but the running backend needs its own secure paper API key and secret. No keys belong in this browser.</p>
      </div>
    </div>}

    {snapshot?.paper_api_readable && <div className="alpaca-paper-content">
      <div className="alpaca-paper-state">
        <span><ShieldCheck size={15}/> Paper API responding · {snapshot.account_status ?? 'Unknown'}</span>
        <small>Account ••••{snapshot.account_suffix ?? '—'} · {snapshot.account_bound ? 'Account identity bound' : 'Observation only · identity not pinned'}</small>
      </div>
      <div className="alpaca-paper-metrics">
        <div><span>Virtual equity</span><strong>{money(snapshot.equity, currency)}</strong></div>
        <div><span>Virtual cash</span><strong>{money(snapshot.cash, currency)}</strong></div>
        <div><span>Buying power</span><strong>{money(snapshot.buying_power, currency)}</strong></div>
        <div><span>Open positions</span><strong>{snapshot.positions_count ?? '—'}</strong></div>
        <div><span>Open orders</span><strong>{snapshot.open_orders_count_capped ? '500+' : (snapshot.open_orders_count ?? '—')}</strong></div>
      </div>
      <div className="alpaca-paper-positions">
        <div className="alpaca-paper-subhead"><h4>Current simulated positions</h4><small>Live account state · no orders placed by this application</small></div>
        {!snapshot.positions?.length ? <p className="alpaca-paper-empty">No open positions in this paper account.</p> :
          <div className="alpaca-paper-table-scroll"><table>
            <thead><tr><th>Symbol</th><th>Side / qty</th><th>Market value</th><th>Unrealised P/L</th></tr></thead>
            <tbody>{snapshot.positions.map((position, i) => {
              const pnl = position.unrealized_pl ? Number(position.unrealized_pl) : 0
              return <tr key={position.symbol + i}>
                <td><strong>{position.symbol}</strong></td>
                <td>{position.side} · {position.qty ?? '—'}</td>
                <td>{money(position.market_value, currency)}</td>
                <td className={pnl > 0 ? 'alpaca-positive' : pnl < 0 ? 'alpaca-negative' : ''}>
                  {pnl > 0 ? <ArrowUpRight size={13}/> : pnl < 0 ? <ArrowDownRight size={13}/> : null}
                  {money(position.unrealized_pl, currency)}
                </td>
              </tr>
            })}</tbody>
          </table></div>}
        {snapshot.positions_truncated && <p className="muted">Showing the first 30 positions.</p>}
      </div>
      <div className="alpaca-paper-footer">
        <span>Snapshot: {snapshot.as_of_utc ? new Date(snapshot.as_of_utc).toLocaleString('en-GB') : '—'}</span>
        <strong><LockKeyhole size={13}/> Paper orders disabled · Live orders disabled</strong>
      </div>
    </div>}
  </section>
}

export default PaperAccountPanel
