import { money, pct, scoreClass } from './api'
import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
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

/** Outcome distribution. The shape matters more than the mean. */
export function DistributionChart({ histogram }) {
  if (!histogram || !histogram.length) return null
  const data = histogram.map((h) => ({
    mid: ((h.lo + h.hi) / 2) * 100,
    count: h.count,
    loss: h.hi <= 0,
  }))
  return (
    <div className="card">
      <h3>Outcome distribution</h3>
      <p className="small muted" style={{ margin: '8px 0 16px' }}>
        {data.length} buckets over simulated outcomes. Red is money lost.
      </p>
      <div style={{ width: '100%', height: 210 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -18 }}>
            <XAxis dataKey="mid" tickFormatter={(v) => `${v.toFixed(0)}%`}
                   tick={{ fontSize: 11, fill: '#5b6b78' }} stroke="#e7ecee" />
            <YAxis tick={{ fontSize: 11, fill: '#5b6b78' }} stroke="#e7ecee" />
            <Tooltip
              formatter={(v) => [`${v} runs`, 'count']}
              labelFormatter={(v) => `${Number(v).toFixed(1)}% p.a.`}
              contentStyle={{
                borderRadius: 10, border: '1px solid #e7ecee',
                fontSize: 12, fontFamily: 'var(--ui)',
              }}
            />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.loss ? '#ff5263' : '#0e8c6a'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
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
