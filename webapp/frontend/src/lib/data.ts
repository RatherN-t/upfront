/* The prototype's whole dataset. One worked example carried end to end, so
 * every figure on every screen resolves from the same arithmetic. */

export const TOTAL_CONTRACTS = 148

export const DEDUCTIONS = [
  { n: 16, label: 'Cancel-anytime', why: 'The customer can walk this week.' },
  { n: 21, label: 'No fixed term', why: 'Nothing committed to advance against.' },
  { n: 7, label: 'Mandate inactive', why: 'No live direct debit on the rail.' },
]

export const BANDS = [
  { term: 26, contracts: 58, weekly: 34.78 },
  { term: 39, contracts: 31, weekly: 29.5 },
  { term: 52, contracts: 15, weekly: 24.9 },
]

export const ELIGIBLE = TOTAL_CONTRACTS - DEDUCTIONS.reduce((s, d) => s + d.n, 0)
export const FACE = BANDS.reduce((s, b) => s + b.contracts * b.weekly * b.term, 0)

export const FEES = [
  { label: 'Transaction fees', value: FACE * 0.0212 },
  { label: 'Decline fees', value: FACE * 0.0061 },
  { label: 'Transfer fees', value: FACE * 0.0009 },
]
export const FEE_DRAG = FEES.reduce((s, f) => s + f.value, 0) / FACE
export const NET_SETTLED = FACE - FEES.reduce((s, f) => s + f.value, 0)

export const ADVANCE_RATE = 0.79
export const CASH_TODAY = FACE * ADVANCE_RATE
export const BUSINESS_IRR = 0.174
export const RAIL_SCORE = 'B+'

/** Value-weighted average life of a dollar in this book, in months. */
export const WAL_MONTHS =
  BANDS.reduce((s, b) => s + b.contracts * b.weekly * b.term * (b.term / 2), 0) /
  FACE /
  4.345

/* What the advance costs, and what is held back until the book completes.
 *
 * The rate is charged on cash actually outstanding for the time it is actually
 * outstanding, so the discount is small next to the headline percentage. The
 * remainder is a holdback, not a fee: it is released at the end of term. */
export const DISCOUNT = CASH_TODAY * BUSINESS_IRR * (WAL_MONTHS / 12)
export const RESERVE = NET_SETTLED - CASH_TODAY - DISCOUNT

export const SCAN = {
  attempts: 4182,
  distinctPayers: 131,
  grossDishonour: 0.041,
  cureRate: 0.68,
  netLoss: 0.013,
  credibility: 1,
  historySource: 'measured' as 'measured' | 'synthesised',
}

export const RETURNS = { mean: 0.152, p5: -0.031, p1: -0.286, probLoss: 0.037 }

/** Return by percentile: flat on the right, a cliff in the left tail. */
export const CURVE = [
  1, 2, 3, 5, 8, 12, 17, 23, 30, 40, 50, 60, 70, 80, 90, 95, 99,
].map((p) => ({
  p,
  value:
    p <= 5
      ? -0.286 + (p - 1) * 0.0637
      : p <= 17
        ? -0.031 + (p - 5) * 0.0142
        : 0.14 + (p - 17) * 0.00022,
}))

/* ------------------------------------------------- collections engine data */

export const TERM_WEEKS = 26
export const WEEKLY_COLLECTION = FACE / TERM_WEEKS

/** Where the book is up to. Weeks past this are still scheduled. */
export const WEEKS_ELAPSED = 8

export type EventKind = 'settled' | 'retrying' | 'recovered' | 'dishonoured' | 'recourse'

export type CollectionEvent = {
  week: number
  kind: EventKind
  detail: string
  amount?: number
}

/* Read newest first. The week 3 soft failure cures on retry; the week 5 hard
 * failure never does, which is what pulls the recourse mandate. */
export const EVENTS: CollectionEvent[] = [
  { week: 8, kind: 'settled', detail: 'collected', amount: WEEKLY_COLLECTION },
  { week: 7, kind: 'settled', detail: 'collected', amount: WEEKLY_COLLECTION },
  { week: 5, kind: 'recourse', detail: "Charged back to the business's own mandate", amount: 34.78 },
  { week: 6, kind: 'settled', detail: 'collected', amount: WEEKLY_COLLECTION },
  { week: 5, kind: 'dishonoured', detail: 'blocked-by-bank, hard, no retry' },
  { week: 3, kind: 'recovered', detail: 'retry settled' },
  { week: 4, kind: 'settled', detail: 'collected', amount: WEEKLY_COLLECTION },
  { week: 3, kind: 'retrying', detail: 'insufficient-funds, soft, auto-retry T+3' },
  { week: 2, kind: 'settled', detail: 'collected', amount: WEEKLY_COLLECTION },
  { week: 1, kind: 'settled', detail: 'collected', amount: WEEKLY_COLLECTION },
]

/** One square per week of the term, coloured by what happened. */
export const TIMELINE = Array.from({ length: TERM_WEEKS }, (_, i) => {
  const week = i + 1
  if (week > WEEKS_ELAPSED) return { week, state: 'scheduled' as const }
  if (week === 5) return { week, state: 'dishonoured' as const }
  return { week, state: 'settled' as const }
})

export const RECOURSE = {
  week: 5,
  amount: 34.78,
  reference: 'pmt_9Hs02Kd71Lq',
  call: 'POST /payments',
}

/* ------------------------------------------------------- investor outcomes */

/**
 * What a stake actually earns.
 *
 * The headline rate is a rate on capital *outstanding*, and this book repays
 * weekly, so a dollar is only working for the average life of the book. Any
 * screen showing a dollar figure has to say that, or the number reads as a
 * disappointment instead of an amortising return.
 */
export function outcome(stake: number, r: typeof RETURNS, walMonths: number) {
  const years = walMonths / 12
  return {
    profit: stake * r.mean * years,
    p5: stake * r.p5 * years,
    p1: stake * r.p1 * years,
    naive: stake * r.mean,
    probLoss: r.probLoss,
  }
}

export type Deal = {
  id: string
  business: string
  sector: string
  suburb: string
  score: string
  assetClass: 'contract' | 'invoice'
  termWeeks: number
  walMonths: number
  feeDrag: number
  target: number
  raised: number
  minTicket: number
  daysLeft: number
  returns: typeof RETURNS
}

export const DEALS: Deal[] = [
  {
    id: 'dl_voltride',
    business: 'Voltride Pty Ltd',
    sector: 'E-bike subscription rentals',
    suburb: 'Brunswick VIC',
    score: RAIL_SCORE,
    assetClass: 'contract',
    termWeeks: 26,
    walMonths: WAL_MONTHS,
    feeDrag: FEE_DRAG,
    target: CASH_TODAY,
    raised: CASH_TODAY * 0.62,
    minTicket: 50,
    daysLeft: 5,
    returns: RETURNS,
  },
  {
    id: 'dl_kindling',
    business: 'Kindling Coffee Co.',
    sector: 'Wholesale roasting · café accounts',
    suburb: 'Marrickville NSW',
    score: 'A−',
    assetClass: 'invoice',
    termWeeks: 12,
    walMonths: 1.4,
    feeDrag: 0.019,
    target: 48200,
    raised: 48200,
    minTicket: 100,
    daysLeft: 0,
    returns: { mean: 0.113, p5: 0.021, p1: -0.094, probLoss: 0.011 },
  },
  {
    id: 'dl_northline',
    business: 'Northline Physio',
    sector: 'Clinical care plans · 6 month blocks',
    suburb: 'Fortitude Valley QLD',
    score: 'B',
    assetClass: 'contract',
    termWeeks: 26,
    walMonths: 3.1,
    feeDrag: 0.036,
    target: 71400,
    raised: 71400 * 0.18,
    minTicket: 50,
    daysLeft: 11,
    returns: { mean: 0.168, p5: -0.062, p1: -0.341, probLoss: 0.058 },
  },
]

export const POSITIONS = [
  { id: 'p1', business: 'Kindling Coffee Co.', score: 'A−', amount: 2500, mean: 0.113, p5: 0.021 },
  { id: 'p2', business: 'Northline Physio', score: 'B', amount: 1000, mean: 0.168, p5: -0.062 },
]

/* ------------------------------------------------------------- formatting */

export const aud = (n: number, cents = false) =>
  n.toLocaleString('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })

export const pct = (n: number, dp = 1) => `${(n * 100).toFixed(dp)}%`

export const ordinal = (n: number) => {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}
