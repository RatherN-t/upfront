import { money, pct, scoreClass } from './api'
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

export function Stat({ label, value, sub, tone, small }) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <span className={`value ${small ? 'sm' : ''} ${tone || ''}`}>{value}</span>
      {sub && <span className="sub">{sub}</span>}
    </div>
  )
}

export function Score({ grade }) {
  return <span className={`score ${scoreClass(grade)}`}>{grade}</span>
}

/**
 * Mean, 5th percentile and probability of loss, rendered as one unit.
 *
 * This mirrors the `claims` guard that the markdown docs are held to: a yield
 * never appears without its downside beside it. Do not split this component up
 * to show the mean somewhere on its own — a mid-teens return looks safe and is
 * not, and that gap is this product's whole credibility problem.
 */
export function Returns({ returns, compact }) {
  if (!returns) return null
  const { mean, p5, p1, prob_loss } = returns
  return (
    <div>
      <div className={`grid ${compact ? 'three' : 'four'}`}>
        <Stat label="Mean return" value={pct(mean)} tone="pos" small={compact}
              sub="expected, p.a." />
        <Stat label="5th percentile" value={pct(p5)}
              tone={p5 < 0 ? 'neg' : ''} small={compact}
              sub="1 run in 20 is worse" />
        {!compact && (
          <Stat label="1st percentile" value={pct(p1)} tone="neg"
                sub="1 run in 100 is worse" />
        )}
        <Stat label="Chance of loss" value={pct(prob_loss, 1)}
              tone={prob_loss > 0.02 ? 'neg' : ''} small={compact}
              sub="probability of < 0%" />
      </div>
      {!compact && (
        <p className="small muted" style={{ marginTop: 12 }}>
          The mean is not a floor. A single deal is one business — if it fails
          early the loss is large, which is what the 1st percentile shows.
          Spreading across books cuts the tail, but correlation puts a floor on
          how much: you cannot diversify away the economy.
        </p>
      )}
    </div>
  )
}

/** Where the money goes between contracted face and cash today. */
export function FeeDrag({ pricing }) {
  const b = pricing.fee_breakdown || {}
  const rows = [
    ['Transaction fees', b.txn_fees_c],
    ['Decline fees', b.decline_fees_c],
    ['Transfer fees', b.transfer_fees_c],
  ].filter(([, v]) => typeof v === 'number')

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3>Pinch fee drag</h3>
        <span className="chip gold">{pct(pricing.fee_drag)} of collections</span>
      </div>
      <p className="small muted" style={{ margin: '8px 0 14px' }}>
        An underwriting input, not overhead. Cadence and ticket size move this
        several-fold on identical revenue, so it is priced in and it moves the
        Rail Score.
      </p>
      <table>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td className="num">{money(v)}</td>
            </tr>
          ))}
          <tr>
            <td><strong>Net settled</strong></td>
            <td className="num"><strong>{money(pricing.net_settled_c)}</strong></td>
          </tr>
        </tbody>
      </table>
      <p className="small muted" style={{ marginTop: 12 }}>
        Net settled is what the advance is priced against — not gross
        collections. Advancing against gross would push this cost onto
        investors without telling them.
      </p>
    </div>
  )
}

/** Bad-debt scanner output: what the payment rail actually shows. */
export function BookScan({ scan }) {
  return (
    <div className="card">
      <h3>What the rail shows</h3>
      <p className="small muted" style={{ margin: '8px 0 16px' }}>
        Underwritten from {scan.attempts.toLocaleString()} real payment
        attempts across {scan.distinct_payers} customers — not a P&amp;L
        someone typed in.
      </p>
      <div className="grid four">
        <Stat label="Gross dishonour" value={pct(scan.gross_dishonour_rate)}
              small sub="of attempted value" />
        <Stat label="Cure rate" value={pct(scan.cure_rate, 1)} small tone="pos"
              sub="recovered on retry" />
        <Stat label="Net bad debt" value={pct(scan.net_loss_rate)} small
              sub="what actually never lands" />
        <Stat label="Top payer" value={pct(scan.top_payer_concentration, 1)}
              small sub="concentration" />
      </div>
    </div>
  )
}

/**
 * Return at each percentile.
 *
 * Not a histogram, deliberately. A single deal's outcome is close to a point
 * mass — if the business survives, the return is nearly fixed — so a
 * histogram is one spike beside an empty axis, and the information that
 * matters is in the thin left tail. This curve shows the ordinary case (the
 * flat right) and the risk (the cliff on the left) without distorting
 * either, and p5/p1 in the summary above are literally points on this line.
 */
export function DistributionChart({ curve }) {
  if (!curve || !curve.length) return null
  const data = curve.map((d) => ({ p: d.p, value: d.value * 100 }))
  const worst = data[0]
  const crossing = data.find((d) => d.value >= 0)

  return (
    <div className="card">
      <h3>Return by percentile</h3>
      <p className="small muted" style={{ margin: '8px 0 16px' }}>
        Read it as "this outcome or worse, this often". The flat stretch on
        the right is the ordinary result. The cliff on the left is the deal
        failing — it is narrow, and it is deep.
      </p>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 6, right: 10, bottom: 4, left: -12 }}>
            <defs>
              <linearGradient id="curveFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0e8c6a" stopOpacity="0.28" />
                <stop offset="100%" stopColor="#0e8c6a" stopOpacity="0.02" />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#e7ecee" vertical={false} />
            <XAxis dataKey="p" tickFormatter={(v) => `${v}th`}
                   ticks={[1, 5, 10, 25, 50, 75, 99]}
                   tick={{ fontSize: 11, fill: '#5b6b78' }} stroke="#e7ecee" />
            <YAxis tickFormatter={(v) => `${v.toFixed(0)}%`}
                   tick={{ fontSize: 11, fill: '#5b6b78' }} stroke="#e7ecee" />
            <Tooltip
              formatter={(v) => [`${Number(v).toFixed(2)}% p.a.`, 'return']}
              labelFormatter={(v) => `${v}th percentile — ${v}% of runs are worse`}
              contentStyle={{
                borderRadius: 10, border: '1px solid #e7ecee',
                fontSize: 12, fontFamily: 'var(--ui)',
              }}
            />
            <ReferenceLine y={0} stroke="#ff5263" strokeDasharray="4 3" />
            <Area type="monotone" dataKey="value" stroke="#0e8c6a"
                  strokeWidth={2} fill="url(#curveFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="small muted" style={{ marginTop: 10 }}>
        Worst simulated run <span className="mono">{worst.value.toFixed(1)}%</span>.
        {crossing
          ? ` Breaks even around the ${crossing.p}th percentile — below that, you lose money.`
          : ' Every simulated run lost money.'}
      </p>
    </div>
  )
}

/** Never hidden: whether Pinch is live or simulated. */
export function ModeBanner({ mode, note }) {
  if (!mode) return null
  const live = mode === 'live'
  return (
    <div className={`mode ${live ? 'live' : 'simulated'}`}>
      <strong style={{ whiteSpace: 'nowrap' }}>
        {live ? 'Pinch: LIVE (test mode)' : 'Pinch: SIMULATED'}
      </strong>
      <span>
        {note ||
          (live
            ? 'Real API calls against api.getpinch.com.au/test.'
            : 'No credentials found — running the in-process simulator.')}
      </span>
    </div>
  )
}

export function Progress({ raised_c, target_c }) {
  const p = target_c ? Math.min(1, raised_c / target_c) : 0
  return (
    <div>
      <div className="bar"><i style={{ width: `${p * 100}%` }} /></div>
      <div className="row small muted" style={{ justifyContent: 'space-between', marginTop: 6 }}>
        <span className="mono">{money(raised_c)} raised</span>
        <span className="mono">{money(target_c)} target</span>
      </div>
    </div>
  )
}

export function ErrorNote({ children }) {
  if (!children) return null
  return <div className="error" style={{ marginBottom: 16 }}>{children}</div>
}
