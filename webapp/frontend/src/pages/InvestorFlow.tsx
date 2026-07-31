import { useEffect, useState } from 'react'
import {
  api, daysLeft, money, pct, type Deal, type Pricing, type ReturnsShape,
} from '../api'
import { BookScan, DistributionChart, FeeDrag } from '../components/domain'
import {
  Card, Head, Note, Pill, Progress, Returns, Score, Slider, Spinner, Stat, Tag,
} from '../components/ui'

type Position = {
  id: string
  business_name: string
  rail_score: string
  amount_c: number
  mean_return: number
  p5_return: number
}

type InvestorMe = {
  positions: Position[]
  committed_c: number
}

export default function InvestorFlow() {
  const [deals, setDeals] = useState<Deal[] | null>(null)
  const [me, setMe] = useState<InvestorMe | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [err, setErr] = useState('')

  const load = async () => {
    try {
      const [d, m] = await Promise.all([api.deals(), api.investorMe()])
      setDeals(d.deals)
      setMe(m as InvestorMe)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    load()
  }, [open])

  if (open) {
    return <DealDetail id={open} onBack={() => setOpen(null)} />
  }

  if (!deals) {
    return (
      <div className="mx-auto flex max-w-[1200px] justify-center px-6 py-20">
        <Spinner />
      </div>
    )
  }

  const committed = me?.committed_c ?? 0

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16 lg:py-20">
      <Note>{err}</Note>

      <Head
        eyebrow="Open rounds"
        aside={
          <p className="max-w-xs text-[15px] leading-[1.5] opacity-80">
            Returns are shown as a distribution, because a mid-teens mean is
            not a floor.
          </p>
        }
      >
        Every business here was underwritten from its <em>actual</em> payment
        history.
      </Head>

      {deals.length === 0 ? (
        <Card className="mt-10 p-8">
          <p className="text-[16px] text-slate">
            No open rounds. Open the business side in another tab, connect a
            Pinch account and open a round — it&apos;ll appear here.
          </p>
        </Card>
      ) : (
        <div className="mt-10 space-y-4">
          {deals.map((d) => (
            <button
              key={d.id}
              onClick={() => setOpen(d.id)}
              className="block w-full rounded-[24px] bg-mist p-8 text-left transition-colors hover:bg-fog lg:p-10"
            >
              <div className="grid gap-8 lg:grid-cols-[1.1fr_1.4fr] lg:items-center">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-[26px] leading-[1.18] font-semibold tracking-[-0.009em]">
                      {d.business_name}
                    </h2>
                    <Score grade={d.rail_score} />
                  </div>
                  <p className="mt-2 text-[14px] text-ash">{d.sector}</p>
                  <p className="mt-6 text-[15px] text-slate tabular-nums">
                    {d.asset_class === 'contract' ? 'Contract revenue' : 'Invoices'} ·{' '}
                    {d.term_weeks}w · fee drag {pct(d.fee_drag)} · {daysLeft(d.deadline_at)}
                  </p>
                  <div className="mt-4 max-w-sm">
                    <Progress raised={d.raised_c} target={d.target_c} />
                  </div>
                </div>

                <div>
                  <Returns returns={d.returns} compact />
                  <span className="mt-6 inline-block text-[16px] text-ink">
                    View deal · min {money(d.min_ticket_c)} →
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {me && me.positions.length > 0 && (
        <section className="mt-20">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <h2 className="display text-[26px] leading-[1.18]">Your positions</h2>
            <span className="text-[15px] text-slate tabular-nums">
              {money(committed)} committed
            </span>
          </div>
          <table className="mt-6 w-full text-[16px]">
            <thead>
              <tr className="border-b border-hair text-left text-[14px] text-ash">
                <th className="py-3 font-normal">Business</th>
                <th className="py-3 font-normal">Score</th>
                <th className="py-3 text-right font-normal">Amount</th>
                <th className="py-3 text-right font-normal">Mean / 5th pct</th>
              </tr>
            </thead>
            <tbody>
              {me.positions.map((p) => (
                <tr key={p.id} className="border-b border-hair">
                  <td className="py-4">{p.business_name}</td>
                  <td className="py-4 text-[14px] text-slate">{p.rail_score}</td>
                  <td className="py-4 text-right tabular-nums">{money(p.amount_c)}</td>
                  <td className="py-4 text-right tabular-nums">
                    <span className="text-emerald">{pct(p.mean_return)}</span>
                    <span className="text-slate"> / </span>
                    <span className={p.p5_return < 0 ? 'text-flag' : ''}>
                      {pct(p.p5_return)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

/* ------------------------------------------------------------- deal detail */

function DealDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const [data, setData] = useState<{
    deal: Deal
    pricing: Pricing | null
    investments: { investor_name: string; amount_c: number }[]
  } | null>(null)
  const [committed, setCommitted] = useState<{
    accepted_c: number
    payment_link?: { url: string; id: string }
    warning?: string
    clamped?: boolean
  } | null>(null)
  const [err, setErr] = useState('')

  const load = async () => {
    try {
      setData(await api.deal(id))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    load()
  }, [id])

  if (!data) {
    return (
      <div className="mx-auto flex max-w-[1200px] justify-center px-6 py-20">
        {err ? <Note>{err}</Note> : <Spinner />}
      </div>
    )
  }

  const { deal, pricing } = data

  if (committed) {
    return (
      <Committed
        deal={deal}
        result={committed}
        onBack={() => setCommitted(null)}
      />
    )
  }

  const remaining = deal.remaining_c

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16 lg:py-20">
      <button onClick={onBack} className="text-[16px] text-slate hover:text-ink">
        ← All deals
      </button>

      <Note>{err}</Note>

      <div className="mt-6 flex flex-wrap items-start justify-between gap-6">
        <div>
          <h1 className="display text-[clamp(2rem,4.4vw,44px)] leading-[1.3] tracking-[-0.015em]">
            {deal.business_name}
          </h1>
          <p className="mt-2 text-[17px] text-slate">{deal.sector}</p>
        </div>
        <div className="flex items-center gap-3">
          <Score grade={deal.rail_score} />
          <Tag>{daysLeft(deal.deadline_at)}</Tag>
        </div>
      </div>

      <div className="mt-10 max-w-xl">
        <Progress raised={deal.raised_c} target={deal.target_c} />
      </div>

      <div className="mt-12 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Average month life"
          value={deal.wal_months.toFixed(1)}
          size="lg"
          sub="weighted by value"
        />
        <Stat label="Term" value={`${deal.term_weeks} weeks`} sub="contract length" />
        <Stat label="Still open" value={money(remaining)} sub="left to fill" />
        <Stat label="Minimum" value={money(deal.min_ticket_c)} sub="per investor" />
      </div>

      <section className="mt-20">
        <h2 className="display text-[26px] leading-[1.18]">
          What you&apos;d earn, and what you&apos;d risk
        </h2>
        <div className="mt-8">
          <Returns returns={deal.returns} />
        </div>
      </section>

      <div className="mt-20 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        {pricing?.curve && <DistributionChart curve={pricing.curve} />}
        {pricing && <FeeDrag pricing={pricing} />}
      </div>

      {pricing?.scan && (
        <div className="mt-6">
          <BookScan scan={pricing.scan} historySource={pricing.history_source} />
        </div>
      )}

      <section className="mt-20 max-w-[820px]">
        <h2 className="display text-[26px] leading-[1.18]">
          How much in {deal.business_name.split(' ')[0]}?
        </h2>
        {deal.status !== 'open' ? (
          <p className="mt-4 text-[17px] text-slate">
            This round is {deal.status}.
          </p>
        ) : (
          <StakePicker
            deal={deal}
            remaining={remaining}
            onResult={(r) => {
              setCommitted(r)
              load()
            }}
            onError={setErr}
          />
        )}
      </section>

      {data.investments.length > 0 && (
        <Card className="mt-10 overflow-hidden p-0">
          <table className="w-full text-[16px]">
            <thead>
              <tr className="border-b border-hair text-left text-[14px] text-ash">
                <th className="px-8 py-4 font-normal">Investor</th>
                <th className="px-8 py-4 text-right font-normal">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.investments.map((i, k) => (
                <tr key={k} className="border-b border-hair last:border-0">
                  <td className="px-8 py-4">{i.investor_name}</td>
                  <td className="px-8 py-4 text-right tabular-nums">
                    {money(i.amount_c)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}

/* --------------------------------------------------------------- the stake */

function outcome(stakeDollars: number, r: ReturnsShape, walMonths: number) {
  const years = walMonths / 12
  return {
    profit: stakeDollars * r.mean * years,
    p5: stakeDollars * r.p5 * years,
    p1: stakeDollars * r.p1 * years,
    naive: stakeDollars * r.mean,
    probLoss: r.prob_loss,
  }
}

function formatAud(n: number, cents = false) {
  return n.toLocaleString('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })
}

function StakePicker({
  deal,
  remaining,
  onResult,
  onError,
}: {
  deal: Deal
  remaining: number
  onResult: (r: {
    accepted_c: number
    payment_link?: { url: string; id: string }
    warning?: string
    clamped?: boolean
  }) => void
  onError: (msg: string) => void
}) {
  const minDollars = Math.max(1, Math.round(deal.min_ticket_c / 100))
  const maxDollars = Math.max(minDollars, Math.floor(remaining / 100))
  const [stake, setStake] = useState(Math.min(1000, maxDollars))
  const [busy, setBusy] = useState(false)
  const o = outcome(stake, deal.returns, deal.wal_months)

  const presets = [500, 1000, 5000, 25000].filter(
    (p) => p >= minDollars && p <= maxDollars,
  )

  const invest = async () => {
    setBusy(true)
    onError('')
    try {
      const r = await api.invest(deal.id, stake)
      onResult(r)
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const rows = [
    {
      label: 'Expected profit',
      value: `+${formatAud(o.profit, true)}`,
      tone: 'pos' as const,
    },
    {
      label: 'If it goes badly (5th pct)',
      value: `${o.p5 < 0 ? '−' : '+'}${formatAud(Math.abs(o.p5), true)}`,
      tone: o.p5 < 0 ? ('neg' as const) : ('pos' as const),
    },
    {
      label: 'If it goes very badly (1st pct)',
      value: `−${formatAud(Math.abs(o.p1), true)}`,
      tone: 'neg' as const,
    },
    { label: 'Chance of losing money', value: pct(o.probLoss, 2) },
    {
      label: 'Capital returned by',
      value: `week ${deal.term_weeks} · weekly`,
    },
  ]

  return (
    <Card className="mt-8 p-8 lg:p-10">
      <p className="mb-6 text-[15px] text-slate">
        You&apos;ll be sent to a Pinch hosted checkout. In test mode no real
        money moves.
      </p>

      <div className="flex flex-wrap gap-3">
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setStake(p)}
            className={`rounded-full px-5 py-2.5 text-[15px] leading-none tabular-nums transition-colors ${
              stake === p
                ? 'bg-emerald text-paper'
                : 'border border-hair text-slate hover:border-ink hover:text-ink'
            }`}
          >
            {formatAud(p)}
          </button>
        ))}
      </div>

      <div className="mt-8">
        <Slider
          label="Your stake"
          value={stake}
          min={minDollars}
          max={maxDollars}
          step={50}
          onChange={setStake}
        />
      </div>

      <p className="display mt-6 text-[clamp(2.5rem,6vw,64px)] leading-none tabular-nums">
        {formatAud(stake)}
      </p>
      <p className="mt-2 text-[15px] text-slate">
        your stake · minimum {formatAud(minDollars)}, {formatAud(maxDollars)} still open
      </p>

      <dl className="mt-10">
        {rows.map((r) => (
          <div
            key={r.label}
            className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-1 border-b border-hair py-4"
          >
            <dt className="text-[16px] text-slate">{r.label}</dt>
            <dd
              className={`text-[16px] tabular-nums ${
                r.tone === 'pos' ? 'text-emerald' : r.tone === 'neg' ? 'text-flag' : ''
              }`}
            >
              {r.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="mt-8 rounded-[16px] border border-flag/30 bg-flag/5 p-6 text-[15px] leading-[1.5] text-flag">
        <span className="font-semibold">Why the dollar figure looks small.</span>{' '}
        {pct(deal.returns.mean)} is a rate on capital outstanding, and this book
        pays you back weekly rather than at the end. Average life is{' '}
        {deal.wal_months.toFixed(2)} months, so {formatAud(stake)} earns about{' '}
        {formatAud(o.profit, true)} over the full {deal.term_weeks} weeks, not{' '}
        {formatAud(o.naive, true)}. Reinvesting is what keeps the capital working.
      </div>

      <Pill variant="accent" className="mt-8" disabled={busy} onClick={invest}>
        {busy ? 'Creating…' : `Invest ${formatAud(stake)}`}
      </Pill>
    </Card>
  )
}

/* ------------------------------------------------------- payment and return */

function Committed({
  deal,
  result,
  onBack,
}: {
  deal: Deal
  result: {
    accepted_c: number
    payment_link?: { url: string; id: string }
    warning?: string
    clamped?: boolean
  }
  onBack: () => void
}) {
  const stakeDollars = result.accepted_c / 100
  const o = outcome(stakeDollars, deal.returns, deal.wal_months)
  const perWeek = (stakeDollars + o.profit) / deal.term_weeks

  return (
    <div className="mx-auto max-w-[720px] px-6 py-16 lg:py-20">
      <button onClick={onBack} className="text-[16px] text-slate hover:text-ink">
        ← Change amount
      </button>

      <div className="mt-8 text-center">
        <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-wash text-[26px] text-emerald">
          ✓
        </span>
        <h1 className="display mt-8 text-[clamp(2rem,4.4vw,44px)] leading-[1.15]">
          You&apos;re in.
        </h1>
        <p className="display mt-6 text-[clamp(3rem,7vw,80px)] leading-none tabular-nums text-emerald">
          {money(result.accepted_c)}
        </p>
        <p className="mt-3 text-[16px] text-slate">
          paid to {deal.business_name} through Pinch
          {result.payment_link && (
            <>
              {' · '}
              <a
                href={result.payment_link.url}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-emerald underline"
              >
                {result.payment_link.id}
              </a>
            </>
          )}
        </p>
        {result.clamped && (
          <p className="mt-3 text-[15px] text-slate">
            Clamped to {money(result.accepted_c)} — that&apos;s all the room the
            round had left.
          </p>
        )}
        {result.warning && (
          <p className="mt-3 text-[15px] text-flag">{result.warning}</p>
        )}
      </div>

      <Card tone="paper" className="mt-12 p-8 lg:p-10">
        <h2 className="text-[22px] font-semibold">What comes back</h2>
        <dl className="mt-6">
          {[
            { label: 'Your stake', value: money(result.accepted_c) },
            {
              label: 'Expected profit',
              value: `+${formatAud(o.profit, true)}`,
              pos: true,
            },
            {
              label: 'Expected total returned',
              value: formatAud(stakeDollars + o.profit),
            },
            {
              label: 'Roughly per week',
              value: `${formatAud(perWeek, true)} × ${deal.term_weeks}`,
            },
            { label: 'First repayment', value: 'week 1' },
            { label: 'Chance of losing money', value: pct(o.probLoss, 2) },
          ].map((r) => (
            <div
              key={r.label}
              className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-1 border-b border-hair py-4 last:border-0 last:pb-0"
            >
              <dt className="text-[16px] text-slate">{r.label}</dt>
              <dd className={`text-[16px] tabular-nums ${r.pos ? 'text-emerald' : ''}`}>
                {r.value}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <div className="mt-6 rounded-[24px] bg-mint p-8 text-emerald-deep">
        <p className="text-[16px] leading-[1.5]">
          Repayments arrive weekly from week one, not in a lump at week{' '}
          {deal.term_weeks}. If the book runs short, the business&apos;s recourse
          mandate is debited before your position takes a loss.
        </p>
      </div>

      <p className="mt-8 text-[15px] leading-[1.5] text-slate">
        Expected is not guaranteed. One run in twenty returns{' '}
        {o.p5 < 0 ? `−${formatAud(Math.abs(o.p5), true)}` : `+${formatAud(o.p5, true)}`},
        and one in a hundred returns −{formatAud(Math.abs(o.p1), true)}.
      </p>
    </div>
  )
}
