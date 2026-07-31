import { useState } from 'react'
import { api } from '../api'
import { Field, Input, Note, Pill, Tag } from '../components/ui'

export default function SignIn({
  role,
  onDone,
  onBack,
}: {
  role: 'business' | 'investor'
  onDone: () => void
  onBack: () => void
}) {
  const business = role === 'business'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setErr('')
    try {
      if (business) await api.businessStart(name, email)
      else await api.investorStart(name, email)
      onDone()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-[560px] px-6 py-20 lg:py-28">
      <button onClick={onBack} className="text-[16px] text-slate hover:text-ink">
        ← Back
      </button>

      <div className="mt-6">
        <Tag>{business ? 'For businesses' : 'For investors'}</Tag>
      </div>
      <h1 className="display mt-3 text-[44px] leading-[1.3] tracking-[-0.015em]">
        {business ? 'Your business' : 'Your details'}
      </h1>
      <p className="mt-4 text-[17px] leading-[1.35] text-slate">
        No password — this is a test-mode prototype.
        {business && (
          <>
            {' '}
            Using an email that&apos;s already onboarded resumes that business
            exactly where it left off. <strong>Use a new email</strong> to see
            the choice between connecting a Pinch account and starting fresh.
          </>
        )}
      </p>

      <Note>{err}</Note>

      <form className="mt-10 space-y-6" onSubmit={submit}>
        <Field label={business ? 'Company name' : 'Your name'}>
          <Input
            value={name}
            required
            onChange={(e) => setName(e.target.value)}
            placeholder={business ? 'Voltride Pty Ltd' : 'Ari Whitfield'}
          />
        </Field>
        <Field label="Email">
          <Input
            type="email"
            value={email}
            required
            onChange={(e) => setEmail(e.target.value)}
            placeholder={business ? 'ops@voltride.example' : 'ari@example.com'}
          />
        </Field>
        <Pill className="w-full" disabled={busy}>
          {busy ? 'Starting…' : 'Continue'}
        </Pill>
      </form>
    </div>
  )
}
