import { useEffect, useRef, useState } from 'react'
import { api, daysLeft, money, pct, type Deal, type Pricing } from '../api'
import Calculation from '../components/Calculation'
import { BookScan, FeeDrag } from '../components/domain'
import {
  Card, Field, Head, Input, Note, Pill, PinchMark, Progress, Returns, Score,
  Select, Spinner, Stat, Tag,
} from '../components/ui'
import Collections from './Collections'

const STAGES = [
  ['creating_merchant', 'Creating your managed merchant on Pinch'],
  ['seeding', 'Recording your payment history on the rail'],
  ['underwriting', 'Reading your book and pricing the risk'],
] as const

const CONNECT_STAGES = [
  ['underwriting', 'Reading your book and pricing the risk'],
] as const

type Me = {
  status: string
  status_detail?: string
  connection_type?: string
  mch_id?: string
  pinch_mode?: string
  pricing?: Pricing
  deals?: Deal[]
}

export default function BusinessFlow() {
  const [me, setMe] = useState<Me | null>(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [path, setPath] = useState<'connect' | 'new' | null>(null)
  const [showCollections, setShowCollections] = useState(false)
  const poll = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = async () => {
    try {
      setMe((await api.businessMe()) as Me)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    const inFlight = me && STAGES.some(([s]) => s === me.status)
    if (!inFlight) {
      if (poll.current) clearInterval(poll.current)
      return
    }
    poll.current = setInterval(load, 700)
    return () => {
      if (poll.current) clearInterval(poll.current)
    }
  }, [me?.status])

  if (showCollections) {
    return <Collections onBack={() => setShowCollections(false)} />
  }

  if (!me) {
    return (
      <div className="mx-auto flex max-w-[1200px] justify-center px-6 py-20">
        <Spinner />
      </div>
    )
  }

  const onboard = async (form: Record<string, unknown>) => {
    setBusy(true)
    setErr('')
    try {
      await api.businessOnboard(form)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const connect = async (form: Record<string, unknown>) => {
    setBusy(true)
    setErr('')
    try {
      await api.connectAccount(form)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const openRound = async (days: number, min: number) => {
    setBusy(true)
    setErr('')
    try {
      await api.openRound(days, min)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const openDeal = me.deals?.[0]
  const onboarding = STAGES.some(([s]) => s === me.status)
  const connected = me.connection_type === 'connected'

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16 lg:py-20">
      <Note>{err}</Note>

      {me.mch_id && (
        <p className="mb-6 font-mono text-[13px] text-ash">
          managed merchant {me.mch_id} · {me.pinch_mode}
        </p>
      )}

      {me.status === 'failed' && (
        <Card className="mb-6 p-8">
          <h2 className="text-[26px] font-semibold">Onboarding failed</h2>
          <p className="mt-3 text-[16px] leading-[1.5] text-slate">
            {me.status_detail || 'Something went wrong.'} Your merchant record,
            if one was created, is kept so nothing is orphaned.
          </p>
          <Pill
            variant="ghost"
            className="mt-6"
            onClick={() => setMe({ ...me, status: 'new' })}
          >
            Try again
          </Pill>
        </Card>
      )}

      {me.status === 'not_fundable' && (
        <Card className="mb-6 p-8">
          <h2 className="text-[26px] font-semibold">Not fundable yet</h2>
          <p className="mt-3 text-[16px] leading-[1.5] text-slate">
            {me.status_detail || 'No eligible receivables.'} We only advance
            against committed revenue with an active mandate behind it.
          </p>
        </Card>
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

      {me.status === 'ready' && !openDeal && me.pricing && (
        <Offer me={me} onOpen={openRound} busy={busy} />
      )}

      {openDeal && (
        <DealStatus
          deal={openDeal}
          pricing={me.pricing}
          onCollections={() => setShowCollections(true)}
        />
      )}
    </div>
  )
}

/* ------------------------------------------------------------- path choice */

function PathChoice({ onPick }: { onPick: (p: 'connect' | 'new') => void }) {
  const options = [
    {
      key: 'connect' as const,
      tag: 'Real book',
      title: 'I already use Pinch',
      body: 'We read your own customers, mandates and settled payments, and price off evidence you have already built.',
      cta: 'Connect my account',
    },
    {
      key: 'new' as const,
      tag: 'New account',
      title: "I'm new to Pinch",
      body: 'We create a managed merchant for you and price the book from the schedule you describe until real history accrues.',
      cta: 'Set me up',
    },
  ]

  return (
    <>
      <Head
        eyebrow="Step one"
        aside={
          <p className="max-w-xs text-[15px] leading-[1.5] opacity-80">
            The two paths price off different evidence, so we ask before we
            read anything.
          </p>
        }
      >
        Where does your payment history <em>live</em>?
      </Head>

      <div className="mt-10 grid gap-6 lg:grid-cols-2">
        {options.map((o) => (
          <Card key={o.key} className="flex flex-col p-8 lg:p-10">
            <div className="flex items-center justify-between gap-4">
              <Tag>{o.tag}</Tag>
              {o.key === 'connect' && <PinchMark className="h-8 w-8" />}
            </div>
            <h2 className="mt-3 text-[26px] leading-[1.18] font-semibold tracking-[-0.009em]">
              {o.title}
            </h2>
            <p className="mt-4 max-w-sm flex-1 text-[16px] leading-[1.5] text-slate">
              {o.body}
            </p>
            <div className="mt-8">
              <Pill onClick={() => onPick(o.key)}>{o.cta}</Pill>
            </div>
          </Card>
        ))}
      </div>
    </>
  )
}

/* --------------------------------------------------------------- the forms */

function ConnectForm({
  onSubmit,
  onBack,
  busy,
}: {
  onSubmit: (f: Record<string, unknown>) => void
  onBack: () => void
  busy: boolean
}) {
  const [f, setF] = useState({
    app_id: '',
    secret: '',
    sector: 'E-bike subscription rentals',
    asset_class: 'contract',
  })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }))

  return (
    <div className="max-w-[720px]">
      <button onClick={onBack} className="text-[16px] text-slate hover:text-ink">
        ← I&apos;m new to Pinch
      </button>

      <div className="mt-6 flex items-center gap-3">
        <PinchMark className="h-9 w-9" />
        <span className="text-[15px] text-slate">Pinch Payments</span>
      </div>

      <h1 className="display mt-6 text-[44px] leading-[1.3] tracking-[-0.015em]">
        Connect your Pinch account
      </h1>
      <p className="mt-4 text-[17px] leading-[1.35] text-slate">
        Upfront only <strong>reads</strong> this account — payers, plans,
        subscriptions, payments and transfers. It never writes to a connected
        account.
      </p>

      <form
        className="mt-10 space-y-6"
        onSubmit={(e) => {
          e.preventDefault()
          const payload = { ...f }
          setF((p) => ({ ...p, secret: '' }))
          onSubmit(payload)
        }}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="Application ID">
            <Input
              value={f.app_id}
              onChange={set('app_id')}
              placeholder="app_test_…"
              autoComplete="off"
              required
            />
          </Field>
          <Field
            label="Secret key"
            hint="Development keys only (app_test_… / sk_test_…). Live keys are refused."
          >
            <Input
              type="password"
              value={f.secret}
              onChange={set('secret')}
              placeholder="sk_test_…"
              autoComplete="off"
              required
            />
          </Field>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="What does your business do?">
            <Input value={f.sector} onChange={set('sector')} required />
          </Field>
          <Field label="What are you selling us?">
            <Select value={f.asset_class} onChange={set('asset_class')}>
              <option value="contract">Contract revenue — committed subscriptions</option>
              <option value="invoice">Invoices — work already delivered</option>
            </Select>
          </Field>
        </div>

        <Card className="p-6 text-[15px] leading-[1.5] text-slate">
          {f.asset_class === 'contract'
            ? 'Contract revenue is service not yet delivered. If the business stops, the stream stops — which is why it prices wider than an invoice.'
            : 'An invoice is for work already done, so the debtor still owes it even if your business fails. That is why it prices tighter.'}
        </Card>

        <Pill className="w-full" disabled={busy}>
          {busy ? 'Connecting…' : 'Connect Pinch account'}
        </Pill>
      </form>
    </div>
  )
}

function OnboardForm({
  onSubmit,
  onBack,
  busy,
}: {
  onSubmit: (f: Record<string, unknown>) => void
  onBack: () => void
  busy: boolean
}) {
  const [f, setF] = useState({
    sector: 'E-bike subscription rentals',
    asset_class: 'contract',
    ticket_dollars: 34.78,
    cadence: 'weekly',
    customers: 120,
    term_weeks: 26,
  })
  const set =
    (k: keyof typeof f) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const v = e.target.type === 'number' ? Number(e.target.value) : e.target.value
      setF((p) => ({ ...p, [k]: v }))
    }

  return (
    <div className="max-w-[720px]">
      <button onClick={onBack} className="text-[16px] text-slate hover:text-ink">
        ← I already use Pinch
      </button>

      <h1 className="display mt-6 text-[44px] leading-[1.3] tracking-[-0.015em]">
        Tell us what you sell
      </h1>
      <p className="mt-4 text-[17px] leading-[1.35] text-slate">
        We don&apos;t ask for a P&amp;L or a forecast. We read the payment
        attempts on your account and price what we can see.
      </p>

      <form
        className="mt-10 space-y-6"
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit(f)
        }}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="What does your business do?">
            <Input value={f.sector} onChange={set('sector')} required />
          </Field>
          <Field label="What are you selling us?">
            <Select value={f.asset_class} onChange={set('asset_class')}>
              <option value="contract">Contract revenue (committed subscriptions)</option>
              <option value="invoice">Invoices (work already delivered)</option>
            </Select>
          </Field>
        </div>
        <div className="grid gap-6 sm:grid-cols-3">
          <Field label="Typical payment (A$)">
            <Input
              type="number"
              step="0.01"
              min={1}
              value={f.ticket_dollars}
              onChange={set('ticket_dollars')}
              required
            />
          </Field>
          <Field label="How often do you bill?">
            <Select value={f.cadence} onChange={set('cadence')}>
              <option value="weekly">Weekly</option>
              <option value="fortnightly">Fortnightly</option>
              <option value="monthly">Monthly</option>
            </Select>
          </Field>
          <Field label="Paying customers">
            <Input
              type="number"
              min={1}
              max={400}
              value={f.customers}
              onChange={set('customers')}
              required
            />
          </Field>
        </div>
        <Card className="p-6 text-[15px] leading-[1.5] text-slate">
          {f.asset_class === 'contract'
            ? 'Contract revenue is service not yet delivered. If the business stops, the stream stops, which is why it prices wider than an invoice.'
            : 'An invoice is for work already done, so the debtor still owes it even if your business fails. That is why it prices tighter.'}
        </Card>

        <Pill className="w-full" disabled={busy}>
          {busy ? 'Connecting…' : 'Create my managed merchant'}
        </Pill>
      </form>
    </div>
  )
}

/* -------------------------------------------------------------- onboarding */

function Onboarding({ status, connected }: { status: string; connected: boolean }) {
  const stages = connected ? CONNECT_STAGES : STAGES
  const idx = stages.findIndex(([s]) => s === status)

  return (
    <div className="max-w-[620px]">
      <div className="flex items-center gap-4">
        <PinchMark className="h-11 w-11 animate-pulse" />
        <h1 className="display text-[44px] leading-[1.3] tracking-[-0.015em]">
          {connected ? 'Reading your Pinch account' : 'Connecting to Pinch'}
        </h1>
      </div>
      <p className="mt-4 text-[17px] leading-[1.35] text-slate">
        {connected
          ? "This is a real read, not a loading screen: we're pulling your customers, mandates and settled payment history straight off your own account and pricing from what comes back."
          : 'This is a real onboarding, not a loading screen: a managed merchant is created, a payment history is written, and the book is priced from what comes back.'}
      </p>

      <ol className="mt-10 space-y-1">
        {stages.map(([s, label], k) => {
          const done = k < idx
          const active = k === idx
          return (
            <li
              key={s}
              className={`flex items-center gap-4 border-b border-hair py-5 transition-opacity duration-500 ${
                done || active ? 'opacity-100' : 'opacity-35'
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] tabular-nums ${
                  done
                    ? 'bg-emerald text-paper'
                    : active
                      ? 'bg-ink text-paper'
                      : 'bg-mist text-ash'
                }`}
              >
                {done ? '✓' : k + 1}
              </span>
              <span className="text-[17px]">{label}</span>
              {active && <span className="ml-auto"><Spinner /></span>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

/* ------------------------------------------------------------------- offer */

function Offer({
  me,
  onOpen,
  busy,
}: {
  me: Me
  onOpen: (deadline: number, min: number) => void
  busy: boolean
}) {
  const p = me.pricing!
  const [deadline, setDeadline] = useState(7)
  const [min, setMin] = useState(50)

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <Score grade={p.rail_score} />
          <h1 className="display mt-4 max-w-2xl text-[clamp(2rem,4.4vw,44px)] leading-[1.3] tracking-[-0.015em]">
            Here is your offer, <em>built in front of you.</em>
          </h1>
          <p className="mt-3 text-[16px] text-slate">
            {p.asset_class === 'contract' ? 'Contract revenue' : 'Invoices'}
            {' · '}{p.term_weeks} weeks · WAL {p.wal_months.toFixed(2)} months
          </p>
        </div>
      </div>

      <div className="mt-16">
        <Calculation autoplay={false} />
      </div>

      <div className="mt-24 grid gap-6 lg:grid-cols-2">
        {p.scan && (
          <BookScan scan={p.scan} historySource={p.history_source} />
        )}
        <FeeDrag pricing={p} />
      </div>

      <Card className="mt-6 p-8 lg:p-12">
        <div className="grid gap-8 sm:grid-cols-3">
          <Stat
            label="Cash today"
            value={money(p.cash_today_c)}
            tone="pos"
            size="lg"
            sub={`then ${money(p.reserve_c)} reserve on completion`}
          />
          <Stat label="Net settled" value={money(p.net_settled_c)} sub="after Pinch fees" />
          <Stat label="Your cost" value={pct(p.business_irr)} sub="p.a. equivalent" />
        </div>
        <div className="mt-10 grid gap-8 sm:grid-cols-3 border-t border-hair pt-10">
          <Stat label="Contracted face" value={money(p.gross_face_c)} />
          <Stat label="Eligible face" value={money(p.eligible_face_c)} sub="after screen + cap" />
          <Stat label="Fee drag" value={pct(p.fee_drag)} sub="of collections" />
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="rounded-[24px] bg-mint p-8 text-emerald-deep lg:p-10">
          <h2 className="text-[26px] leading-[1.18] font-semibold tracking-[-0.009em]">
            Open the round
          </h2>
          <p className="mt-4 text-[16px] leading-[1.5] opacity-85">
            Investors fund {money(p.cash_today_c)}. If the round doesn&apos;t
            fill by the deadline it closes unfunded, so you are not committed
            to a partial raise.
          </p>
        </div>

        <Card className="p-8 lg:p-10">
          <div className="grid gap-6 sm:grid-cols-2">
            <Field label="How long can you wait?">
              <Select
                value={deadline}
                onChange={(e) => setDeadline(Number(e.target.value))}
              >
                <option value={1}>24 hours</option>
                <option value={3}>3 days</option>
                <option value={7}>7 days</option>
                <option value={14}>14 days</option>
              </Select>
            </Field>
            <Field label="Minimum investment (A$)">
              <Input
                type="number"
                min={1}
                value={min}
                onChange={(e) => setMin(Number(e.target.value))}
              />
            </Field>
          </div>
          <Pill className="mt-8 w-full" disabled={busy} onClick={() => onOpen(deadline, min)}>
            {busy ? 'Opening…' : `Open round for ${money(p.cash_today_c)}`}
          </Pill>
        </Card>
      </div>
    </>
  )
}

/* -------------------------------------------------------------- deal status */

function DealStatus({
  deal,
  pricing,
  onCollections,
}: {
  deal: Deal
  pricing?: Pricing
  onCollections: () => void
}) {
  const funded = deal.status === 'funded'
  const expired = deal.status === 'expired'

  return (
    <div className="max-w-[820px]">
      <Tag>Your round</Tag>
      <h1 className="display mt-3 text-[clamp(2rem,4.4vw,44px)] leading-[1.3] tracking-[-0.015em]">
        {funded ? 'Fully funded.' : expired ? 'Closed unfunded.' : `Open — ${daysLeft(deal.deadline_at)}.`}
      </h1>

      <p className="display mt-10 text-[64px] leading-none tracking-[-0.015em] tabular-nums text-emerald">
        {money(deal.raised_c)}
      </p>
      <p className="mt-2 text-[17px] text-slate tabular-nums">
        raised of {money(deal.target_c)} · minimum cheque {money(deal.min_ticket_c)}
      </p>

      <div className="mt-8">
        <Progress raised={deal.raised_c} target={deal.target_c} />
      </div>

      <div className="mt-10 rounded-[24px] bg-mint p-8 text-emerald-deep">
        {funded ? (
          <p className="text-[17px] leading-[1.35]">
            {money(deal.cash_today_c)} is scheduled to land, and collections
            route back automatically on the Pinch rail.
          </p>
        ) : expired ? (
          <p className="text-[17px] leading-[1.35]">
            The deadline passed without a full raise. You are not committed to
            a partial amount.
          </p>
        ) : (
          <p className="text-[17px] leading-[1.35]">
            If the round doesn&apos;t fill by the deadline it closes unfunded,
            so you are not committed to a partial raise.
          </p>
        )}
      </div>

      {deal.returns && (
        <Card className="mt-6 p-8">
          <h3 className="text-[22px] font-semibold">What investors see</h3>
          <p className="mt-2 mb-6 text-[15px] text-slate">
            The same downside we show you.
          </p>
          <Returns returns={deal.returns} compact />
        </Card>
      )}

      {funded && (
        <Pill className="mt-8" onClick={onCollections}>
          Go to collections
        </Pill>
      )}

      {pricing?.scan && funded && (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <BookScan scan={pricing.scan} historySource={pricing.history_source} />
          <FeeDrag pricing={pricing} />
        </div>
      )}
    </div>
  )
}
