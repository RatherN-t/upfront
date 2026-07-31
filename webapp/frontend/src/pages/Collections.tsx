import { useEffect, useState } from 'react'
import { Card, Head, Stat, Tag } from '../components/ui'
import {
  aud, EVENTS, RECOURSE, TERM_WEEKS, TIMELINE, WEEKLY_COLLECTION, WEEKS_ELAPSED,
  type EventKind,
} from '../lib/data'

/* The collections engine: what the rail is doing with the book after funding,
 * and what happens on the weeks it fails. */

const KIND: Record<EventKind, { label: string; chip: string }> = {
  settled: { label: 'SETTLED', chip: 'bg-wash text-emerald-deep' },
  recovered: { label: 'RECOVERED', chip: 'bg-wash text-emerald-deep' },
  retrying: { label: 'RETRYING', chip: 'bg-mist text-slate' },
  dishonoured: { label: 'DISHONOURED', chip: 'bg-flag/10 text-flag' },
  recourse: { label: 'RECOURSE', chip: 'bg-flag/10 text-flag' },
}

export default function Collections({ onBack }: { onBack: () => void }) {
  const collected = EVENTS.filter((e) => e.kind === 'settled').reduce(
    (s, e) => s + (e.amount ?? 0),
    0,
  )

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16 lg:py-20">
      <button onClick={onBack} className="text-[16px] text-slate hover:text-ink">
        ← Back
      </button>

      <div className="mt-6">
        <Head
          eyebrow="Collections engine"
          aside={
            <p className="max-w-xs text-[15px] leading-[1.5] opacity-80">
              Repayment is plumbing. Every week the rail attempts the debit and
              tells you what came back.
            </p>
          }
        >
          Week {WEEKS_ELAPSED} of {TERM_WEEKS}, <em>running itself</em>.
        </Head>
      </div>

      <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Collected so far"
          value={aud(collected)}
          size="lg"
          sub={`${aud(WEEKLY_COLLECTION)} scheduled each week`}
        />
        <Stat label="Weeks settled" value={`${WEEKS_ELAPSED - 1} of ${WEEKS_ELAPSED}`} tone="pos" sub="attempts that landed" />
        <Stat label="Recovered on retry" value="1" sub="soft failure, cured T+3" />
        <Stat label="Pulled to recourse" value={aud(RECOURSE.amount, true)} tone="neg" sub="hard failure, week 5" />
      </div>

      <div className="mt-14">
        <Timeline />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.25fr_1fr]">
        <Events />
        <Recourse />
      </div>
    </div>
  )
}

/** One square per week, filling in as the term runs. */
function Timeline() {
  const [shown, setShown] = useState(0)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    setShown(0)
    let i = 0
    const id = window.setInterval(() => {
      i += 1
      setShown(i)
      if (i >= WEEKS_ELAPSED) window.clearInterval(id)
    }, 130)
    return () => window.clearInterval(id)
  }, [nonce])

  const fill = {
    settled: 'bg-emerald',
    dishonoured: 'bg-flag',
    scheduled: 'bg-mist',
  }

  return (
    <Card tone="paper" className="p-8 lg:p-10">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h2 className="text-[22px] font-semibold">Collection timeline</h2>
        <button
          onClick={() => setNonce((n) => n + 1)}
          className="text-[15px] text-emerald hover:underline"
        >
          Replay
        </button>
      </div>

      <div className="mt-6 flex flex-wrap gap-1.5">
        {TIMELINE.map((w) => {
          const revealed = w.week <= shown
          return (
            <span
              key={w.week}
              title={`Week ${w.week} · ${w.state}`}
              className={`h-9 w-9 rounded-[8px] transition-colors duration-300 ${
                revealed ? fill[w.state] : 'bg-mist'
              }`}
            />
          )
        })}
      </div>

      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-[14px] text-slate">
        <Key className="bg-mist" label="Scheduled" />
        <Key className="bg-emerald" label="Settled" />
        <Key className="bg-flag" label="Dishonoured" />
      </div>
    </Card>
  )
}

function Key({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-2">
      <span className={`h-3 w-3 rounded-[4px] ${className}`} />
      {label}
    </span>
  )
}

function Events() {
  return (
    <Card tone="paper" className="p-8 lg:p-10">
      <h2 className="text-[22px] font-semibold">Payment events</h2>
      <ul className="mt-6">
        {EVENTS.map((e, i) => (
          <li
            key={`${e.week}-${e.kind}-${i}`}
            className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-hair py-4 last:border-0"
          >
            <span
              className={`shrink-0 rounded-full px-3 py-1 text-[12px] tracking-[0.04em] ${KIND[e.kind].chip}`}
            >
              {KIND[e.kind].label}
            </span>
            <span className="text-[16px]">
              Week {e.week} · {e.amount ? `${aud(e.amount)} ${e.detail}` : e.detail}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function Recourse() {
  return (
    <Card tone="paper" className="p-8 lg:p-10">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[22px] font-semibold">Recourse</h2>
        <Tag>week {RECOURSE.week}</Tag>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-hair pb-5">
        <span className="shrink-0 rounded-full bg-flag/10 px-3 py-1 text-[12px] tracking-[0.04em] text-flag">
          RECOURSE
        </span>
        <span className="text-[16px] tabular-nums">
          {aud(RECOURSE.amount, true)} debited from you
        </span>
      </div>

      <p className="mt-5 font-mono text-[14px] break-words text-slate">
        {RECOURSE.call} · {RECOURSE.reference} · nonce set
      </p>

      <p className="mt-6 text-[15px] leading-[1.5] text-slate">
        Recourse is a direct-debit mandate from you to Upfront, signed at
        funding. A shortfall is a payment against your own payer record, not a
        clause in a contract someone has to chase.
      </p>

      <p className="mt-4 text-[15px] leading-[1.5] text-slate">
        Soft failures retry themselves and usually cure. Only a hard failure,
        like a blocked mandate, reaches this panel.
      </p>
    </Card>
  )
}
