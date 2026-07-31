import { useMemo } from 'react'
import { money, ordinal, pct, type Pricing, type Scan } from '../api'
import { Card, Stat, Tag } from './ui'

/** Where the money goes between contracted face and cash today. */
export function FeeDrag({ pricing }: { pricing: Pricing }) {
  const b = pricing.fee_breakdown || {}
  const rows = [
    ['Transaction fees', b.txn_fees_c],
    ['Decline fees', b.decline_fees_c],
    ['Transfer fees', b.transfer_fees_c],
  ].filter(([, v]) => typeof v === 'number') as [string, number][]

  return (
    <Card className="p-8 lg:p-10">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-[22px] font-semibold">Pinch fee drag</h3>
        <span className="text-[14px] text-ash tabular-nums">
          {pct(pricing.fee_drag)} of collections
        </span>
      </div>
      <p className="mt-3 max-w-md text-[15px] leading-[1.5] text-slate">
        An underwriting input, not overhead. Cadence and ticket size move this
        several-fold on identical revenue, so it is priced in.
      </p>
      <dl className="mt-8">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between border-b border-hair py-3 text-[16px]">
            <dt className="text-slate">{label}</dt>
            <dd className="tabular-nums">{money(value)}</dd>
          </div>
        ))}
        <div className="flex justify-between py-4 text-[16px] font-medium">
          <dt>Net settled</dt>
          <dd className="tabular-nums">{money(pricing.net_settled_c)}</dd>
        </div>
      </dl>
      <p className="text-[14px] leading-[1.5] text-slate">
        Net settled is what the advance is priced against — not gross collections.
      </p>
    </Card>
  )
}

/**
 * Bad-debt scanner output: what the payment rail actually shows.
 */
export function BookScan({
  scan,
  historySource,
}: {
  scan: Scan
  historySource?: string
}) {
  const cred = scan.credibility === undefined ? 1 : scan.credibility
  const thin = cred < 0.99
  const standIn = historySource === 'synthesised'

  return (
    <Card className="p-8 lg:p-10">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-[22px] font-semibold">What the rail shows</h3>
        {standIn && <Tag>history stood in</Tag>}
      </div>
      {standIn && (
        <p className="mt-3 text-[15px] leading-[1.5] text-emerald">
          This account has no settled payments yet — Pinch&apos;s test-mode
          settlement runs on its own batch — so the attempt history below is
          generated, not measured.
        </p>
      )}
      {thin ? (
        <p className="mt-3 max-w-md text-[15px] leading-[1.5] text-slate">
          Only {scan.attempts.toLocaleString()} settled payment attempts on
          this account so far — not enough to measure a failure rate. The loss
          figure below is therefore mostly <strong>assumed</strong>.
        </p>
      ) : (
        <p className="mt-3 max-w-md text-[15px] leading-[1.5] text-slate">
          Underwritten from {scan.attempts.toLocaleString()} real payment
          attempts across {scan.distinct_payers} customers — not a P&amp;L
          someone typed in.
        </p>
      )}
      <div className="mt-8 grid grid-cols-2 gap-8">
        <Stat
          label="Gross dishonour"
          value={pct(scan.gross_dishonour_rate)}
          sub={thin ? 'too little data' : 'of attempted value'}
        />
        <Stat
          label="Cure rate"
          value={pct(scan.cure_rate, 1)}
          tone={thin ? undefined : 'pos'}
          sub={thin ? 'too little data' : 'recovered on retry'}
        />
        <Stat
          label={thin ? 'Assumed bad debt' : 'Net bad debt'}
          value={pct(scan.net_loss_rate)}
          tone={thin ? 'neg' : undefined}
          sub={thin ? 'not measured' : 'what never lands'}
        />
        <Stat
          label="Evidence"
          value={`${Math.round(cred * 100)}%`}
          tone={thin ? 'neg' : 'pos'}
          sub={thin ? 'thin history' : 'fully credible'}
        />
      </div>
    </Card>
  )
}

/**
 * Return at each percentile — SVG curve, not a histogram.
 */
export function DistributionChart({ curve }: { curve: { p: number; value: number }[] }) {
  const { path, area, zeroY, cross, worst } = useMemo(() => {
    if (!curve?.length) {
      return { path: '', area: '', zeroY: 0, cross: undefined, worst: undefined }
    }
    const w = 640
    const h = 220
    const vals = curve.map((d) => d.value)
    const lo = Math.min(...vals) * 1.08
    const hi = Math.max(...vals) * 1.15
    const x = (p: number) => ((p - 1) / 98) * w
    const y = (v: number) => h - ((v - lo) / (hi - lo)) * h
    const pts = curve.map((d) => `${x(d.p).toFixed(1)},${y(d.value).toFixed(1)}`)
    return {
      path: `M ${pts.join(' L ')}`,
      area: `M ${pts.join(' L ')} L ${w},${h} L 0,${h} Z`,
      zeroY: y(0),
      cross: curve.find((d) => d.value >= 0),
      worst: curve[0],
    }
  }, [curve])

  if (!curve?.length || !worst) return null

  return (
    <Card className="p-8 lg:p-10">
      <h3 className="text-[22px] font-semibold">Return by percentile</h3>
      <p className="mt-3 max-w-md text-[15px] leading-[1.5] text-slate">
        Read it as &ldquo;this outcome or worse, this often&rdquo;. The flat
        stretch on the right is the ordinary result. The cliff on the left is
        the deal failing: narrow, and deep.
      </p>

      <svg
        viewBox="0 0 640 220"
        className="mt-8 w-full"
        role="img"
        aria-label="Return by percentile"
      >
        <defs>
          <linearGradient id="curve" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0f7a4d" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#0f7a4d" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#curve)" />
        <line
          x1="0"
          x2="640"
          y1={zeroY}
          y2={zeroY}
          stroke="#b4432f"
          strokeDasharray="4 4"
          strokeWidth="1"
        />
        <path d={path} fill="none" stroke="#0f7a4d" strokeWidth="2" strokeLinejoin="round" />
      </svg>

      <div className="mt-3 flex justify-between text-[13px] text-smoke tabular-nums">
        {[1, 25, 50, 75, 99].map((p) => (
          <span key={p}>{ordinal(p)}</span>
        ))}
      </div>

      <p className="mt-6 text-[15px] leading-[1.5] text-slate tabular-nums">
        Worst simulated run {pct(worst.value)}.
        {cross
          ? ` Breaks even around the ${ordinal(cross.p)} percentile. Below that, you lose money.`
          : ' Every simulated run lost money.'}
      </p>
    </Card>
  )
}
