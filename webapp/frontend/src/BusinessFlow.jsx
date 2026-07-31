import { useEffect, useRef, useState } from 'react'
import { api, daysLeft, money, pct } from './api'
import {
  BookScan, ErrorNote, FeeDrag, Progress, Returns, Score, Stat,
} from './components'

const STAGES = [
  ['creating_merchant', 'Creating your managed merchant on Pinch'],
  ['seeding', 'Recording your payment history on the rail'],
  ['underwriting', 'Reading your book and pricing the risk'],
]

/** Staged progress — a bare spinner tells the user nothing about what is
 *  slow, and on the live path each of these is genuinely many API calls. */
function Onboarding({ status }) {
  const idx = STAGES.findIndex(([s]) => s === status)
  return (
    <div className="card">
      <h2>Connecting to Pinch</h2>
      <p className="small muted" style={{ margin: '8px 0 18px' }}>
        This is a real onboarding, not a loading screen: a managed merchant is
        created, a payment history is written, and the book is priced from
        what comes back.
      </p>
      <div className="steps">
        {STAGES.map(([s, label], i) => (
          <div key={s} className={`step ${i < idx ? 'done' : i === idx ? 'active' : 'pending'}`}>
            <span className="mark">{i < idx ? '✓' : i + 1}</span>
            <span>{label}</span>
            {i === idx && <span className="spin" />}
          </div>
        ))}
      </div>
    </div>
  )
}

function OnboardForm({ onSubmit, busy }) {
  const [f, setF] = useState({
    sector: 'E-bike subscription rentals',
    asset_class: 'contract',
    ticket_dollars: 34.78,
    cadence: 'weekly',
    customers: 120,
    term_weeks: 26,
  })
  const set = (k) => (e) => {
    const v = e.target.type === 'number' ? Number(e.target.value) : e.target.value
    setF((p) => ({ ...p, [k]: v }))
  }

  return (
    <div className="card">
      <h2>Get paid now for revenue you've already won</h2>
      <p className="small muted" style={{ margin: '8px 0 20px' }}>
        We don't ask for a P&amp;L or a forecast. We read the payment attempts
        on your Pinch account and price what we can see.
      </p>

      <form onSubmit={(e) => { e.preventDefault(); onSubmit(f) }}>
        <div className="grid two">
          <div className="field">
            <label>What does your business do?</label>
            <input value={f.sector} onChange={set('sector')} required />
          </div>
          <div className="field">
            <label>What are you selling us?</label>
            <select value={f.asset_class} onChange={set('asset_class')}>
              <option value="contract">
                Contract revenue — committed subscriptions
              </option>
              <option value="invoice">
                Invoices — work already delivered
              </option>
            </select>
          </div>
        </div>

        <div className="grid three">
          <div className="field">
            <label>Typical payment size (A$)</label>
            <input type="number" step="0.01" min="1" value={f.ticket_dollars}
                   onChange={set('ticket_dollars')} required />
          </div>
          <div className="field">
            <label>How often do you bill?</label>
            <select value={f.cadence} onChange={set('cadence')}>
              <option value="weekly">Weekly</option>
              <option value="fortnightly">Fortnightly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div className="field">
            <label>Paying customers</label>
            <input type="number" min="1" max="400" value={f.customers}
                   onChange={set('customers')} required />
          </div>
        </div>

        <p className="small muted" style={{ marginBottom: 16 }}>
          {f.asset_class === 'contract'
            ? 'Contract revenue is service not yet delivered. If the business stops, the stream stops — which is why it prices wider than an invoice.'
            : 'An invoice is for work already done, so the debtor still owes it even if your business fails. That is why it prices tighter.'}
        </p>

        <button className="cash wide" disabled={busy}>
          {busy ? 'Connecting…' : 'Connect Pinch account'}
        </button>
      </form>
    </div>
  )
}

function Offer({ me, onOpen, busy }) {
  const p = me.pricing
  const [deadline, setDeadline] = useState(7)
  const [minTicket, setMinTicket] = useState(50)

  return (
    <>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <span className="chip">Rail Score</span>
            <div className="row" style={{ marginTop: 8 }}>
              <Score grade={p.rail_score} />
              <span className="muted small">
                {p.asset_class === 'contract' ? 'Contract revenue' : 'Invoices'}
                {' · '}{p.term_weeks} weeks · WAL {p.wal_months.toFixed(2)} months
              </span>
            </div>
          </div>
          <Stat label="Cash today" value={money(p.cash_today_c)} tone="pos"
                sub={`then ${money(p.reserve_c)} reserve on completion`} />
        </div>

        <div className="divider" />

        <div className="grid four">
          <Stat label="Contracted face" value={money(p.gross_face_c)} small />
          <Stat label="Eligible face" value={money(p.eligible_face_c)} small
                sub="after screen + cap" />
          <Stat label="Net settled" value={money(p.net_settled_c)} small
                sub="after Pinch fees" />
          <Stat label="Your cost" value={pct(p.business_irr)} small
                sub="p.a. equivalent" />
        </div>
      </div>

      <div className="grid two" style={{ marginBottom: 16 }}>
        <BookScan scan={p.scan} />
        <FeeDrag pricing={p} />
      </div>

      <div className="card">
        <h2>Open the round</h2>
        <p className="small muted" style={{ margin: '8px 0 18px' }}>
          Investors fund {money(p.cash_today_c)}. You choose how long you can
          wait for it to fill, and the smallest cheque you'll accept.
        </p>
        <div className="grid two">
          <div className="field">
            <label>How long can you wait?</label>
            <select value={deadline} onChange={(e) => setDeadline(Number(e.target.value))}>
              <option value={1}>24 hours</option>
              <option value={3}>3 days</option>
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
            </select>
          </div>
          <div className="field">
            <label>Minimum investment (A$)</label>
            <input type="number" min="1" value={minTicket}
                   onChange={(e) => setMinTicket(Number(e.target.value))} />
          </div>
        </div>
        <p className="small muted" style={{ marginBottom: 16 }}>
          If the round doesn't fill by the deadline it closes unfunded — you
          are not committed to a partial raise.
        </p>
        <button className="cash wide" disabled={busy}
                onClick={() => onOpen(deadline, minTicket)}>
          {busy ? 'Opening…' : `Open round for ${money(p.cash_today_c)}`}
        </button>
      </div>
    </>
  )
}

function DealStatus({ deal }) {
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2>Your round</h2>
        <span className={`chip ${deal.status === 'funded' ? 'cash' : deal.status === 'expired' ? 'rail' : ''}`}>
          {deal.status === 'funded' ? 'Fully funded' :
           deal.status === 'expired' ? 'Closed unfunded' : daysLeft(deal.deadline_at)}
        </span>
      </div>
      <div style={{ margin: '18px 0' }}>
        <Progress raised_c={deal.raised_c} target_c={deal.target_c} />
      </div>
      {deal.status === 'funded' && (
        <p className="small" style={{ color: 'var(--cash)' }}>
          Funded. {money(deal.cash_today_c)} is scheduled to land, and
          collections route back automatically on the Pinch rail.
        </p>
      )}
    </div>
  )
}

export default function BusinessFlow() {
  const [me, setMe] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const poll = useRef(null)

  const load = async () => {
    try { setMe(await api.businessMe()) } catch (e) { setErr(e.message) }
  }

  useEffect(() => { load() }, [])

  // Poll only while onboarding is actually in flight.
  useEffect(() => {
    const inFlight = me && STAGES.some(([s]) => s === me.status)
    if (!inFlight) { clearInterval(poll.current); return }
    poll.current = setInterval(load, 700)
    return () => clearInterval(poll.current)
  }, [me && me.status])

  if (!me) return <div className="card"><span className="spin" /></div>

  const onboard = async (form) => {
    setBusy(true); setErr('')
    try { await api.businessOnboard(form); await load() }
    catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  const openRound = async (days, min) => {
    setBusy(true); setErr('')
    try { await api.openRound(days, min); await load() }
    catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  const openDeal = me.deals && me.deals[0]
  const onboarding = STAGES.some(([s]) => s === me.status)

  return (
    <>
      <ErrorNote>{err}</ErrorNote>

      {me.mch_id && (
        <p className="small muted mono" style={{ marginBottom: 16 }}>
          managed merchant {me.mch_id} · {me.pinch_mode}
        </p>
      )}

      {me.status === 'failed' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Onboarding failed</h2>
          <p className="small muted" style={{ marginTop: 8 }}>
            {me.status_detail || 'Something went wrong.'} Your merchant record,
            if one was created, is kept so nothing is orphaned.
          </p>
          <button className="ghost" style={{ marginTop: 14 }}
                  onClick={() => setMe({ ...me, status: 'new' })}>
            Try again
          </button>
        </div>
      )}

      {me.status === 'not_fundable' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Not fundable yet</h2>
          <p className="small muted" style={{ marginTop: 8 }}>
            {me.status_detail || 'No eligible receivables.'} We only advance
            against committed revenue with an active mandate behind it.
          </p>
        </div>
      )}

      {onboarding && <Onboarding status={me.status} />}

      {(me.status === 'new' || me.status === 'failed') && !onboarding && (
        <OnboardForm onSubmit={onboard} busy={busy} />
      )}

      {me.status === 'ready' && !openDeal && (
        <Offer me={me} onOpen={openRound} busy={busy} />
      )}

      {openDeal && (
        <>
          <DealStatus deal={openDeal} />
          <div style={{ height: 16 }} />
          <div className="card">
            <h3>What investors see</h3>
            <p className="small muted" style={{ margin: '8px 0 16px' }}>
              The same downside we show you.
            </p>
            <Returns returns={openDeal.returns} compact />
          </div>
        </>
      )}
    </>
  )
}
