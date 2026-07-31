// API client. `credentials: 'include'` on every call — the session is an
// httpOnly cookie, and omitting it silently signs the user out.

async function call(path, { method = 'GET', body } = {}) {
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
  return data
}

export const api = {
  health: () => call('/health'),

  businessStart: (name, email) =>
    call('/business/start', { method: 'POST', body: { name, email } }),
  businessMe: () => call('/business/me'),
  businessOnboard: (payload) =>
    call('/business/onboard', { method: 'POST', body: payload }),
  openRound: (deadline_days, min_ticket_dollars) =>
    call('/business/open-round', {
      method: 'POST',
      body: { deadline_days, min_ticket_dollars },
    }),

  investorStart: (name, email) =>
    call('/investor/start', { method: 'POST', body: { name, email } }),
  investorMe: () => call('/investor/me'),

  deals: () => call('/deals'),
  deal: (id) => call(`/deals/${id}`),
  invest: (deal_id, amount_dollars) =>
    call('/invest', { method: 'POST', body: { deal_id, amount_dollars } }),
}

// ---------- formatting ----------
// Money crosses the wire as integer cents and is only ever turned into
// dollars for display.

export const money = (cents, opts = {}) =>
  (cents / 100).toLocaleString('en-AU', {
    style: 'currency',
    currency: 'AUD',
    maximumFractionDigits: opts.cents ? 2 : 0,
    minimumFractionDigits: opts.cents ? 2 : 0,
  })

export const pct = (x, dp = 2) => `${(x * 100).toFixed(dp)}%`

export const scoreClass = (grade) =>
  grade === 'A' || grade === 'A-' ? '' : grade === 'C' ? 'c' : 'b'

export function daysLeft(iso) {
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'closed'
  const hours = ms / 3600000
  // Round up: a 7-day round should read "7d left" the moment it opens, not
  // "6d" because a few seconds have elapsed.
  if (hours >= 24) return `${Math.ceil(hours / 24)}d left`
  return `${Math.max(1, Math.ceil(hours))}h left`
}
