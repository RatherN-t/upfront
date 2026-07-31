import { useEffect, useState } from 'react'
import { api, daysLeft, money, pct } from './api'
import {
  BookScan, DistributionChart, ErrorNote, FeeDrag, Progress, Returns, Score,
  Stat,
} from './components'

function DealCard({ deal, onOpen }) {
  return (
    <div className="card deal">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div>
          <h3>{deal.business_name}</h3>
          <span className="small muted">{deal.sector}</span>
        </div>
        <Score grade={deal.rail_score} />
      </div>

      <div style={{ margin: '16px 0' }}>
        <Progress raised_c={deal.raised_c} target_c={deal.target_c} />
      </div>

      {/* Mean never appears without its downside. */}
      <Returns returns={deal.returns} compact />

      <div className="row small muted" style={{ marginTop: 14, justifyContent: 'space-between' }}>
        <span>
          {deal.asset_class === 'contract' ? 'Contract revenue' : 'Invoices'}
          {' · '}{deal.term_weeks}w · fee drag {pct(deal.fee_drag)}
        </span>
        <span>{daysLeft(deal.deadline_at)}</span>
      </div>

      <div className="cta">
        <button className="wide" onClick={() => onOpen(deal.id)}>
          View deal · min {money(deal.min_ticket_c)}
        </button>
      </div>
    </div>
  )
}

function DealDetail({ id, onBack }) {
  const [data, setData] = useState(null)
  const [amount, setAmount] = useState('')
  const [err, setErr] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try { setData(await api.deal(id)) } catch (e) { setErr(e.message) }
  }
  useEffect(() => { load() }, [id])

  if (!data) return <div className="card"><span className="spin" /></div>

  const { deal, pricing } = data
  const remaining = deal.remaining_c

  const invest = async () => {
    setBusy(true); setErr(''); setResult(null)
    try {
      const r = await api.invest(id, Number(amount))
      setResult(r)
      await load()
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <>
      <button className="ghost" onClick={onBack} style={{ marginBottom: 16 }}>
        ← All deals
      </button>

      <ErrorNote>{err}</ErrorNote>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>{deal.business_name}</h1>
            <span className="muted">{deal.sector}</span>
          </div>
          <div className="row">
            <Score grade={deal.rail_score} />
            <span className="chip">{daysLeft(deal.deadline_at)}</span>
          </div>
        </div>

        <div style={{ margin: '20px 0' }}>
          <Progress raised_c={deal.raised_c} target_c={deal.target_c} />
        </div>

        <div className="grid four">
          <Stat label="Term" value={`${deal.term_weeks}w`} small
                sub={`WAL ${deal.wal_months.toFixed(2)} months`} />
          <Stat label="Fee drag" value={pct(deal.fee_drag)} small
                sub="Pinch cost of collection" />
          <Stat label="Still open" value={money(remaining)} small
                sub="left to fill" />
          <Stat label="Minimum" value={money(deal.min_ticket_c)} small
                sub="per investor" />
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>What you'd earn, and what you'd risk</h2>
        <div style={{ marginTop: 16 }}>
          <Returns returns={deal.returns} />
        </div>
      </div>

      {pricing && pricing.curve && (
        <div style={{ marginBottom: 16 }}>
          <DistributionChart curve={pricing.curve} />
        </div>
      )}

      {pricing && pricing.scan && (
        <div className="grid two" style={{ marginBottom: 16 }}>
          <BookScan scan={pricing.scan}
                    historySource={pricing.history_source} />
          <FeeDrag pricing={pricing} />
        </div>
      )}

      <div className="card">
        <h2>Invest</h2>
        {deal.status !== 'open' ? (
          <p className="small muted" style={{ marginTop: 8 }}>
            This round is {deal.status}.
          </p>
        ) : (
          <>
            <p className="small muted" style={{ margin: '8px 0 16px' }}>
              You'll be sent to a Pinch hosted checkout. In test mode no real
              money moves.
            </p>
            <div className="row" style={{ alignItems: 'flex-end' }}>
              <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                <label>Amount (A$)</label>
                <input type="number" min="1" value={amount} placeholder={deal.min_ticket_c / 100}
                       onChange={(e) => setAmount(e.target.value)} />
              </div>
              <button className="cash" disabled={busy || !amount} onClick={invest}>
                {busy ? 'Creating…' : 'Invest'}
              </button>
            </div>

            {result && (
              <div style={{ marginTop: 18 }}>
                {result.clamped && (
                  <p className="small muted" style={{ marginBottom: 8 }}>
                    Clamped to {money(result.accepted_c)} — that's all the room
                    the round had left.
                  </p>
                )}
                {result.payment_link ? (
                  <a className="small" href={result.payment_link.url}
                     target="_blank" rel="noreferrer">
                    Pinch checkout for {money(result.accepted_c)} →
                    <span className="mono"> {result.payment_link.id}</span>
                  </a>
                ) : (
                  <p className="small error">{result.warning}</p>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {data.investments.length > 0 && (
        <div className="card flush" style={{ marginTop: 16 }}>
          <table>
            <thead>
              <tr><th>Investor</th><th className="num">Amount</th></tr>
            </thead>
            <tbody>
              {data.investments.map((i, k) => (
                <tr key={k}>
                  <td>{i.investor_name}</td>
                  <td className="num">{money(i.amount_c)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export default function InvestorFlow() {
  const [deals, setDeals] = useState(null)
  const [me, setMe] = useState(null)
  const [open, setOpen] = useState(null)
  const [err, setErr] = useState('')

  const load = async () => {
    try {
      const [d, m] = await Promise.all([api.deals(), api.investorMe()])
      setDeals(d.deals); setMe(m)
    } catch (e) { setErr(e.message) }
  }
  useEffect(() => { load() }, [open])

  if (open) return <DealDetail id={open} onBack={() => setOpen(null)} />
  if (!deals) return <div className="card"><span className="spin" /></div>

  return (
    <>
      <ErrorNote>{err}</ErrorNote>

      {me && me.positions.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3>Your positions</h3>
            <span className="mono">{money(me.committed_c)} committed</span>
          </div>
          <table style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Business</th><th>Score</th>
                <th className="num">Amount</th><th className="num">Mean / 5th pct</th>
              </tr>
            </thead>
            <tbody>
              {me.positions.map((p) => (
                <tr key={p.id}>
                  <td>{p.business_name}</td>
                  <td><Score grade={p.rail_score} /></td>
                  <td className="num">{money(p.amount_c)}</td>
                  <td className="num">
                    {pct(p.mean_return)} / {pct(p.p5_return)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h1 style={{ marginBottom: 6 }}>Open rounds</h1>
      <p className="muted small" style={{ marginBottom: 20 }}>
        Every business here was underwritten from its actual payment history.
        Returns are shown as a distribution because a mid-teens mean is not a
        floor.
      </p>

      {deals.length === 0 ? (
        <div className="card">
          <p className="muted">
            No open rounds. Open the business side in another tab, connect a
            Pinch account and open a round — it'll appear here.
          </p>
        </div>
      ) : (
        <div className="grid two">
          {deals.map((d) => (
            <DealCard key={d.id} deal={d} onOpen={setOpen} />
          ))}
        </div>
      )}
    </>
  )
}
