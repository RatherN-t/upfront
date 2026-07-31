import { useEffect, useState } from 'react'
import { api } from './api'
import BusinessFlow from './BusinessFlow'
import InvestorFlow from './InvestorFlow'
import { ErrorNote, ModeBanner } from './components'

function Landing({ onPick }) {
  return (
    <>
      <div style={{ textAlign: 'center', padding: '40px 0 34px' }}>
        <h1 style={{ fontSize: '2.6rem', marginBottom: 12 }}>
          Revenue you've already won, paid today.
        </h1>
        <p className="muted" style={{ maxWidth: 560, margin: '0 auto' }}>
          Businesses sell committed contract revenue at a discount. Investors
          fund the advance. Collections route back automatically on the Pinch
          rail — repayment isn't a promise, it's the plumbing.
        </p>
      </div>

      <div className="grid two">
        <div className="card">
          <span className="chip cash">For businesses</span>
          <h2 style={{ margin: '14px 0 10px' }}>Get paid now</h2>
          <p className="small muted" style={{ marginBottom: 18 }}>
            Connect your Pinch account. We read your real payment attempts —
            not a P&amp;L you typed — and make an offer against what actually
            settles.
          </p>
          <button className="cash wide" onClick={() => onPick('business')}>
            I'm a business
          </button>
        </div>

        <div className="card">
          <span className="chip">For investors</span>
          <h2 style={{ margin: '14px 0 10px' }}>Fund a book</h2>
          <p className="small muted" style={{ marginBottom: 18 }}>
            Back real Australian businesses against revenue we can see. Every
            deal shows its mean, its 5th percentile and its chance of loss
            together.
          </p>
          <button className="wide" onClick={() => onPick('investor')}>
            I'm an investor
          </button>
        </div>
      </div>
    </>
  )
}

function SignIn({ role, onDone, onBack }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const business = role === 'business'

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      if (business) await api.businessStart(name, email)
      else await api.investorStart(name, email)
      onDone()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div style={{ maxWidth: 420, margin: '0 auto' }}>
      <button className="ghost" onClick={onBack} style={{ marginBottom: 16 }}>
        ← Back
      </button>
      <div className="card">
        <h2>{business ? 'Your business' : 'Your details'}</h2>
        <p className="small muted" style={{ margin: '8px 0 18px' }}>
          No password — this is a test-mode prototype.
          {business && (
            <> Using an email that's already onboarded resumes that business
            exactly where it left off. <strong>Use a new email</strong> to see
            the choice between connecting a Pinch account and starting
            fresh.</>
          )}
        </p>
        <ErrorNote>{err}</ErrorNote>
        <form onSubmit={submit}>
          <div className="field">
            <label>{business ? 'Company name' : 'Your name'}</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
                   required placeholder={business ? 'Your Company Pty Ltd' : 'Ari'} />
          </div>
          <div className="field">
            <label>Email</label>
            <input type="email" value={email} required
                   onChange={(e) => setEmail(e.target.value)}
                   placeholder={business ? 'you@yourcompany.example' : 'ari@example.com'} />
          </div>
          <button className="cash wide" disabled={busy}>
            {busy ? 'Starting…' : 'Continue'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [role, setRole] = useState(null)      // 'business' | 'investor'
  const [signedIn, setSignedIn] = useState(false)

  useEffect(() => { api.health().then(setHealth).catch(() => {}) }, [])

  // Resume an existing session on reload so a refresh mid-demo isn't fatal.
  useEffect(() => {
    (async () => {
      try { await api.businessMe(); setRole('business'); setSignedIn(true); return }
      catch { /* not a business */ }
      try { await api.investorMe(); setRole('investor'); setSignedIn(true) }
      catch { /* not signed in */ }
    })()
  }, [])

  const signOut = async () => {
    await fetch('/api/sign-out', { method: 'POST', credentials: 'include' })
    setRole(null); setSignedIn(false)
  }

  return (
    <>
      <div className="topbar">
        <span className="brand"><span className="dot" />Upfront</span>
        <span className="spacer" />
        {signedIn && (
          <>
            <span className="chip">{role}</span>
            <button className="ghost" onClick={signOut}>Sign out</button>
          </>
        )}
      </div>

      <div className="shell">
        {health && (
          <ModeBanner mode={health.pinch_mode} note={health.pinch_mode_note} />
        )}

        {!role && <Landing onPick={setRole} />}
        {role && !signedIn && (
          <SignIn role={role} onDone={() => setSignedIn(true)}
                  onBack={() => setRole(null)} />
        )}
        {signedIn && role === 'business' && <BusinessFlow />}
        {signedIn && role === 'investor' && <InvestorFlow />}
      </div>
    </>
  )
}
