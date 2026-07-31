import { useEffect, useState } from 'react'
import { api } from './api'
import { ModeBanner } from './components/ui'
import BusinessFlow from './pages/BusinessFlow'
import InvestorFlow from './pages/InvestorFlow'
import Landing from './pages/Landing'
import SignIn from './pages/SignIn'

type Role = 'business' | 'investor'

export default function App() {
  const [health, setHealth] = useState<{
    pinch_mode: string
    pinch_mode_note?: string
  } | null>(null)
  const [role, setRole] = useState<Role | null>(null)
  const [signedIn, setSignedIn] = useState(false)

  useEffect(() => {
    api.health().then(setHealth).catch(() => {})
  }, [])

  // Resume an existing session on reload so a refresh mid-demo isn't fatal.
  useEffect(() => {
    ;(async () => {
      try {
        await api.businessMe()
        setRole('business')
        setSignedIn(true)
        return
      } catch {
        /* not a business */
      }
      try {
        await api.investorMe()
        setRole('investor')
        setSignedIn(true)
      } catch {
        /* not signed in */
      }
    })()
  }, [])

  const signOut = async () => {
    await fetch('/api/sign-out', { method: 'POST', credentials: 'include' })
    setRole(null)
    setSignedIn(false)
  }

  return (
    <div className="min-h-screen bg-paper">
      <ModeBanner mode={health?.pinch_mode} note={health?.pinch_mode_note} />

      <header className="mx-auto flex max-w-[1200px] items-center gap-6 px-6 py-6">
        <button
          onClick={signOut}
          className="flex items-center gap-2 text-[16px] font-medium"
        >
          <span className="h-2.5 w-2.5 rounded-full bg-emerald" />
          Upfront
        </button>
        <span className="flex-1" />
        {signedIn ? (
          <>
            <span className="text-[14px] text-ash capitalize">{role}</span>
            <button onClick={signOut} className="text-[16px] text-ink hover:underline">
              Sign out
            </button>
          </>
        ) : (
          <>
            <a href="#how" className="hidden text-[16px] text-ink hover:underline sm:block">
              How it works
            </a>
            <button
              onClick={() => setRole('investor')}
              className="rounded-full bg-ink px-5 py-2.5 text-[16px] leading-none text-paper transition-colors hover:bg-ink/90"
            >
              Browse deals
            </button>
          </>
        )}
      </header>

      {!role && <Landing onPick={setRole} />}

      {role && !signedIn && (
        <SignIn
          role={role}
          onDone={() => setSignedIn(true)}
          onBack={() => setRole(null)}
        />
      )}

      {signedIn && role === 'business' && <BusinessFlow />}
      {signedIn && role === 'investor' && <InvestorFlow />}
    </div>
  )
}
