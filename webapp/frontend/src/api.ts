// API client. `credentials: 'include'` on every call — the session is an
// httpOnly cookie, and omitting it silently signs the user out.

async function call<T = unknown>(
  path: string,
  { method = 'GET', body }: { method?: string; body?: unknown } = {},
): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data as T
}

export type ReturnsShape = {
  mean: number
  p5: number
  p1: number
  prob_loss: number
}

export type Scan = {
  attempts: number
  distinct_payers: number
  gross_dishonour_rate: number
  cure_rate: number
  net_loss_rate: number
  credibility?: number
}

export type Pricing = {
  rail_score: string
  asset_class: 'contract' | 'invoice'
  term_weeks: number
  wal_months: number
  cash_today_c: number
  reserve_c: number
  gross_face_c: number
  eligible_face_c: number
  net_settled_c: number
  business_irr: number
  fee_drag: number
  fee_breakdown?: {
    txn_fees_c?: number
    decline_fees_c?: number
    transfer_fees_c?: number
  }
  scan?: Scan
  history_source?: string
  curve?: { p: number; value: number }[]
  fundable?: boolean
}

export type Deal = {
  id: string
  business_name: string
  sector: string
  rail_score: string
  asset_class: 'contract' | 'invoice'
  term_weeks: number
  wal_months: number
  fee_drag: number
  raised_c: number
  target_c: number
  remaining_c: number
  min_ticket_c: number
  cash_today_c: number
  deadline_at: string
  status: string
  returns: ReturnsShape
}

export const api = {
  health: () => call<{ pinch_mode: string; pinch_mode_note?: string }>('/health'),

  businessStart: (name: string, email: string) =>
    call('/business/start', { method: 'POST', body: { name, email } }),
  businessMe: () => call<Record<string, unknown>>('/business/me'),
  businessOnboard: (payload: Record<string, unknown>) =>
    call('/business/onboard', { method: 'POST', body: payload }),
  connectAccount: (payload: Record<string, unknown>) =>
    call('/business/connect', { method: 'POST', body: payload }),
  openRound: (deadline_days: number, min_ticket_dollars: number) =>
    call('/business/open-round', {
      method: 'POST',
      body: { deadline_days, min_ticket_dollars },
    }),

  investorStart: (name: string, email: string) =>
    call('/investor/start', { method: 'POST', body: { name, email } }),
  investorMe: () => call<Record<string, unknown>>('/investor/me'),

  deals: () => call<{ deals: Deal[] }>('/deals'),
  deal: (id: string) =>
    call<{ deal: Deal; pricing: Pricing | null; investments: { investor_name: string; amount_c: number }[] }>(
      `/deals/${id}`,
    ),
  invest: (deal_id: string, amount_dollars: number) =>
    call<{
      accepted_c: number
      clamped?: boolean
      payment_link?: { url: string; id: string }
      warning?: string
    }>('/invest', { method: 'POST', body: { deal_id, amount_dollars } }),
}

// ---------- formatting ----------
// Money crosses the wire as integer cents and is only ever turned into
// dollars for display.

export const money = (cents: number, opts: { cents?: boolean } = {}) =>
  (cents / 100).toLocaleString('en-AU', {
    style: 'currency',
    currency: 'AUD',
    maximumFractionDigits: opts.cents ? 2 : 0,
    minimumFractionDigits: opts.cents ? 2 : 0,
  })

export const pct = (x: number, dp = 2) => `${(x * 100).toFixed(dp)}%`

/** 1 -> "1st", 2 -> "2nd", 3 -> "3rd", 11 -> "11th". */
export function ordinal(n: number) {
  const rem100 = n % 100
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`
  return `${n}${['th', 'st', 'nd', 'rd'][n % 10] || 'th'}`
}

export function daysLeft(iso: string) {
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'closed'
  const hours = ms / 3600000
  if (hours >= 24) return `${Math.ceil(hours / 24)}d left`
  return `${Math.max(1, Math.ceil(hours))}h left`
}
