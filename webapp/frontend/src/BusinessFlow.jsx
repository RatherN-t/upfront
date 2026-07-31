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

// The connect path already has a merchant and a history — both belong to the
// business, not us — so it skips straight to underwriting. Showing the full
// STAGES list here would leave two steps permanently unreached, which reads
// as stuck rather than fast.
const CONNECT_STAGES = [
  ['underwriting', 'Reading your book and pricing the risk'],
]

/** Staged progress — a bare spinner tells the user nothing about what is
 *  slow, and on the live path each of these is genuinely many API calls. */
function Onboarding({ status, connected }) {
  const stages = connected ? CONNECT_STAGES : STAGES
  const idx = stages.findIndex(([s]) => s === status)
  return (
    <div className="card">
      <h2>{connected ? 'Reading your Pinch account' : 'Connecting to Pinch'}</h2>
      <p className="small muted" style={{ margin: '8px 0 18px' }}>
        {connected
          ? "This is a real read, not a loading screen: we're pulling your customers, mandates and settled payment history straight off your own account and pricing from what comes back."
          : 'This is a real onboarding, not a loading screen: a managed merchant is created, a payment history is written, and the book is priced from what comes back.'}
      </p>
      <div className="steps">
        {stages.map(([s, label], i) => (
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

/** Choice shown before either form: bring your own Pinch account, or start
 *  fresh. The two paths price off very different evidence, so the user
 *  should pick with eyes open rather than land in a form by default. */
function PathChoice({ onPick }) {
  return (
    <div className="grid two">
      <div className="card">
        <span className="chip cash">Real book</span>
        <h2 style={{ margin: '10px 0 8px' }}>I already use Pinch</h2>
        <p className="small muted" style={{ marginBottom: 20 }}>
          Connect your own account. We read your actual customers, mandates
          and settled payment history — not a seeded stand-in.
        </p>
        <button className="cash wide" onClick={() => onPick('connect')}>
          Connect my account
        </button>
      </div>
      <div className="card">
        <span className="chip">New account</span>
        <h2 style={{ margin: '10px 0 8px' }}>I'm new to Pinch</h2>
        <p className="small muted" style={{ marginBottom: 20 }}>
          Upfront creates a managed merchant for you and seeds a
          representative book, because a brand-new account has no history to
          underwrite.
        </p>
        <button className="ghost wide" onClick={() => onPick('new')}>
          Start fresh
        </button>
      </div>
    </div>
  )
}

function ConnectForm({ onSubmit, onBack, busy }) {
  const [f, setF] = useState({
    app_id: '', secret: '',
    sector: 'E-bike subscription rentals', asset_class: 'contract',
  })
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }))

  const submit = (e) => {
    e.preventDefault()
    const payload = { ...f }
    // Clear the secret from state the moment it's handed off — it must not
    // sit in the DOM, or be re-typeable back out of it, once submitted.
    setF((p) => ({ ...p, secret: '' }))
    onSubmit(payload)
  }

  return (
    <div className="card">
      <button type="button" className="ghost" style={{ marginBottom: 16 }}
              onClick={onBack}>
        ← I'm new to Pinch
      </button>
      <h2>Connect your Pinch account</h2>
      <p className="small muted" style={{ margin: '8px 0 20px' }}>
        Upfront only <strong>reads</strong> this account — payers, plans,
        subscriptions, payments and transfers. It never writes to a connected
        account.
      </p>

      <form onSubmit={submit}>
        <div className="grid two">
          <div className="field">
            <label>Application ID</label>
            <input value={f.app_id} onChange={set('app_id')}
                   placeholder="app_test_…" autoComplete="off" required />
          </div>
          <div className="field">
            <label>Secret key</label>
            <input type="password" value={f.secret} onChange={set('secret')}
                   placeholder="sk_test_…" autoComplete="off" required />
          </div>
        </div>

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

        <p className="small muted" style={{ marginBottom: 12 }}>
          {f.asset_class === 'contract'
            ? 'Contract revenue is service not yet delivered. If the business stops, the stream stops — which is why it prices wider than an invoice.'
            : 'An invoice is for work already done, so the debtor still owes it even if your business fails. That is why it prices tighter.'}
        </p>

        <p className="small muted" style={{ marginBottom: 16 }}>
          Get these from <span className="mono">web.getpinch.com.au/api-keys</span>.
          Use the <strong>Development</strong> keys
          (<span className="mono">app_test_…</span> / <span className="mono">sk_test_…</span>),
          not Live — this prototype is test mode only and the backend refuses
          live keys.
        </p>

        <button className="cash wide" disabled={busy}>
          {busy ? 'Connecting…' : 'Connect Pinch account'}
        </button>
      </form>
    </div>
  )
}

function OnboardForm({ onSubmit, onBack, busy }) {
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
      {onBack && (
        <button type="button" className="ghost" style={{ marginBottom: 16 }}
                onClick={onBack}>
          ← I already use Pinch
        </button>
      )}
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
        <BookScan scan={p.scan} historySource={p.history_source} />
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
  // null = show the choice, 'connect' | 'new' = show that form. Lets the
  // user switch paths before submitting, and keeps the same form in view if
  // a submission on it fails.
  const [path, setPath] = useState(null)
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

  const connect = async (form) => {
    setBusy(true); setErr('')
    try { await api.connectAccount(form); await load() }
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
  const connected = me.connection_type === 'connected'

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

      {onboarding && <Onboarding status={me.status} connected={connected} />}

      {(me.status === 'new' || me.status === 'failed') && !onboarding && (
        path === 'connect' ? (
          <ConnectForm onSubmit={connect} onBack={() => setPath(null)} busy={busy} />
        ) : path === 'new' ? (
          <OnboardForm onSubmit={onboard} onBack={() => setPath(null)} busy={busy} />
        ) : (
          <PathChoice onPick={setPath} />
        )
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
