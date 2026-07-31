import { useLayoutEffect, useRef, useState } from 'react'
import {
  ADVANCE_RATE, aud, BANDS, CASH_TODAY, DEDUCTIONS, ELIGIBLE, FACE,
  TOTAL_CONTRACTS, WAL_MONTHS,
} from '../lib/data'
import { Tag, useCountUp, useInView, useSequence } from './ui'

/* The layer-by-layer reveal, shared by the landing page and the live offer.
 *
 * 0 idle · 1 total · 2-4 deductions · 5 eligible lands centre-screen
 * 6 it docks into place · 7-9 term bands · 10 contracted face · 11 outcome
 */
const DELAYS = [700, 900, 750, 750, 900, 1500, 700, 620, 620, 900, 1000]

export default function Calculation({ autoplay = true }: { autoplay?: boolean }) {
  const [ref, seen] = useInView<HTMLDivElement>('-25%')
  const { step, replay } = useSequence(autoplay ? seen : true, DELAYS)

  return (
    <div ref={ref} className="space-y-24">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="max-w-xl">
          <Tag>How the number is built</Tag>
          <h2 className="display mt-3 text-[clamp(2rem,4.4vw,44px)] leading-[1.3] tracking-[-0.015em]">
            Two moves, and <em>nothing</em> hidden between them.
          </h2>
        </div>
        <button
          onClick={replay}
          className="rounded-full border border-ink px-5 py-2.5 text-[15px] transition-colors hover:bg-mist"
        >
          Replay
        </button>
      </div>

      <Ledger step={step} />
      <Bands step={step} />
      <Outcome step={step} />
    </div>
  )
}

/** Move one: every contract on the rail, less the ones nobody can fund. */
function Ledger({ step }: { step: number }) {
  const total = useCountUp(TOTAL_CONTRACTS, step >= 1, 700)
  const slot = useRef<HTMLDivElement>(null)
  const [flight, setFlight] = useState('')

  // The eligible card lives in its final slot from the moment it exists, but
  // is first transformed out to the centre of the viewport and scaled up,
  // then released, so it flies in and settles at its real size.
  useLayoutEffect(() => {
    if (step !== 5) return setFlight('')
    const el = slot.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const dx = window.innerWidth / 2 - (r.left + r.width / 2)
    const dy = window.innerHeight / 2 - (r.top + r.height / 2)
    setFlight(`translate(${dx}px, ${dy}px) scale(1.5)`)
  }, [step])

  return (
    <section className="grid gap-10 lg:grid-cols-[0.75fr_1.25fr] lg:gap-20">
      <div>
        <Tag>Move one</Tag>
        <h3 className="display mt-3 text-[26px] leading-[1.18] tracking-[-0.009em]">
          Which contracts can be funded at all
        </h3>
        <p className="mt-4 max-w-sm text-[17px] leading-[1.35] text-slate">
          We never advance against revenue a customer can walk away from next
          week.
        </p>
      </div>

      <div>
        <div
          className={`flex items-baseline justify-between border-b border-hair pb-6 transition-all duration-700 ${
            step >= 1 ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'
          }`}
        >
          <span className="text-[17px] text-slate">Contracts on the rail</span>
          <span className="display text-[64px] leading-none tabular-nums">
            {Math.round(total)}
          </span>
        </div>

        {DEDUCTIONS.map((d, i) => {
          const on = step >= i + 2
          return (
            <div
              key={d.label}
              className={`flex items-center justify-between gap-6 border-b border-hair py-5 transition-all duration-500 ${
                on ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
              }`}
            >
              <div>
                <p className="text-[17px]">{d.label}</p>
                <p className="mt-1 text-[14px] text-slate">{d.why}</p>
              </div>
              <span className="text-[26px] text-flag tabular-nums">−{d.n}</span>
            </div>
          )
        })}

        <div
          ref={slot}
          style={{ transform: flight || undefined }}
          className={`mt-8 origin-center rounded-[24px] bg-wash px-8 py-7 text-emerald-deep transition-all duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)] ${
            step >= 5 ? 'opacity-100' : 'scale-90 opacity-0'
          } ${step === 5 ? 'z-40 shadow-[var(--shadow-overlay)]' : ''}`}
        >
          <p className="text-[14px] opacity-70">Eligible contracts</p>
          <div className="mt-2 flex items-end justify-between gap-8">
            <span className="display text-[90px] leading-none tracking-[-0.025em] tabular-nums">
              {ELIGIBLE}
            </span>
            <p className="pb-4 text-right text-[15px] leading-[1.5] opacity-80">
              committed · fixed term
              <br />
              live mandate
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

/** Move two: eligible contracts × weekly price × weeks, band by band. */
function Bands({ step }: { step: number }) {
  return (
    <section
      className={`grid gap-10 transition-opacity duration-700 lg:grid-cols-[0.75fr_1.25fr] lg:gap-20 ${
        step >= 6 ? 'opacity-100' : 'opacity-0'
      }`}
    >
      <div>
        <Tag>Move two</Tag>
        <h3 className="display mt-3 text-[26px] leading-[1.18] tracking-[-0.009em]">
          What those contracts are worth
        </h3>
        <p className="mt-4 max-w-sm text-[17px] leading-[1.35] text-slate">
          Each eligible contract sits in a term band with its own weekly price.
          Nothing forecast, nothing typed in by hand.
        </p>
      </div>

      <div>
        <div className="flex justify-between border-b border-hair pb-3 text-[14px] text-ash">
          <span>Term band</span>
          <span>Contract value</span>
        </div>

        {BANDS.map((b, i) => (
          <div
            key={b.term}
            className={`flex items-center justify-between gap-6 border-b border-hair py-5 transition-all duration-500 ${
              step >= 7 + i ? 'translate-x-0 opacity-100' : '-translate-x-6 opacity-0'
            }`}
          >
            <div>
              <p className="text-[20px]">{b.term} weeks</p>
              <p className="mt-1 text-[14px] text-slate tabular-nums">
                {b.contracts} contracts × {aud(b.weekly, true)}/wk × {b.term}
              </p>
            </div>
            <span className="text-[22px] font-semibold tabular-nums">
              {aud(b.contracts * b.weekly * b.term)}
            </span>
          </div>
        ))}

        <div
          className={`mt-7 flex items-end justify-between gap-6 transition-all duration-700 ${
            step >= 10 ? 'translate-y-0 opacity-100' : 'translate-y-5 opacity-0'
          }`}
        >
          <div>
            <p className="text-[14px] text-ash">Contracted face</p>
            <p className="mt-1 text-[15px] text-slate">
              {ELIGIBLE} contracts, all bands
            </p>
          </div>
          <span className="display text-[64px] leading-none tracking-[-0.015em] tabular-nums">
            {aud(FACE)}
          </span>
        </div>
      </div>
    </section>
  )
}

/** The two figures that actually decide anything. */
function Outcome({ step }: { step: number }) {
  const on = step >= 11
  const cash = useCountUp(CASH_TODAY, on, 1100)

  return (
    <section
      className={`grid gap-6 transition-all duration-700 lg:grid-cols-[1.3fr_1fr] ${
        on ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
      }`}
    >
      <div className="rounded-[24px] bg-mist px-8 py-12 lg:px-12">
        <p className="text-[14px] text-ash">Cash today</p>
        <p className="display mt-3 text-[clamp(3rem,7vw,90px)] leading-none tracking-[-0.025em] tabular-nums text-emerald">
          {aud(cash)}
        </p>
        <p className="mt-6 max-w-md text-[17px] leading-[1.35] text-slate">
          {Math.round(ADVANCE_RATE * 100)}% of contracted face, paid on
          settlement. Collections route back automatically on the Pinch rail, so
          repayment is plumbing, not a promise.
        </p>
      </div>

      <div className="rounded-[24px] bg-mist px-8 py-12 lg:px-12">
        <p className="text-[14px] text-ash">
          Average month life of one investment
        </p>
        <p className="display mt-3 text-[64px] leading-none tracking-[-0.015em] tabular-nums">
          {WAL_MONTHS.toFixed(1)}
          <span className="ml-2 font-sans text-[20px] text-slate">months</span>
        </p>
        <p className="mt-6 text-[17px] leading-[1.35] text-slate">
          Weighted by value across every band. Capital comes back steadily from
          week one, not in a balloon at the end.
        </p>
      </div>
    </section>
  )
}
