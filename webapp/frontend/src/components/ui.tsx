import { useEffect, useRef, useState, type ReactNode } from 'react'
import pinchLogo from '../assets/pinch-logo.png'
import { pct, type ReturnsShape } from '../api'

/** The Pinch mark, shown wherever we are asking to touch their rail. */
export function PinchMark({ className = 'h-8 w-8' }: { className?: string }) {
  return (
    <img src={pinchLogo} alt="Pinch Payments" className={`${className} object-contain`} />
  )
}

export function Pill({
  children,
  variant = 'filled',
  className = '',
  ...rest
}: {
  children: ReactNode
  variant?: 'filled' | 'ghost' | 'accent'
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const styles = {
    filled: 'bg-ink text-paper hover:bg-ink/90',
    ghost: 'border border-ink text-ink hover:bg-mist',
    accent: 'bg-emerald text-paper hover:bg-emerald-deep',
  }[variant]

  return (
    <button
      {...rest}
      className={`rounded-full px-5 py-3 text-[16px] leading-none transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
    >
      {children}
    </button>
  )
}

export function Card({
  children,
  tone = 'mist',
  className = '',
}: {
  children: ReactNode
  tone?: 'mist' | 'paper' | 'wash' | 'mint' | 'float'
  className?: string
}) {
  const tones = {
    mist: 'bg-mist',
    paper: 'bg-paper border border-hair',
    wash: 'bg-wash text-emerald-deep',
    mint: 'bg-mint text-emerald-deep',
    float: 'bg-paper shadow-[var(--shadow-artifact)]',
  }[tone]
  return (
    <div className={`rounded-[24px] ${tones} ${className}`}>{children}</div>
  )
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="text-[14px] text-ash">{children}</span>
}

export function Head({
  eyebrow,
  children,
  aside,
}: {
  eyebrow: string
  children: ReactNode
  aside?: ReactNode
}) {
  return (
    <div className="rounded-[24px] bg-mint px-8 py-10 text-emerald-deep lg:px-12 lg:py-12">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <span className="text-[14px] opacity-70">{eyebrow}</span>
          <h1 className="display mt-3 max-w-2xl text-[clamp(2rem,4.4vw,44px)] leading-[1.15]">
            {children}
          </h1>
        </div>
        {aside}
      </div>
    </div>
  )
}

export function Stat({
  label,
  value,
  sub,
  tone,
  size = 'md',
}: {
  label: string
  value: ReactNode
  sub?: string
  tone?: 'pos' | 'neg'
  size?: 'md' | 'lg'
}) {
  const color = tone === 'pos' ? 'text-emerald' : tone === 'neg' ? 'text-flag' : 'text-ink'
  return (
    <div>
      <p className="text-[14px] text-ash">{label}</p>
      <p
        className={`mt-2 tabular-nums ${color} ${
          size === 'lg' ? 'display text-[44px] leading-none' : 'text-[22px] font-semibold'
        }`}
      >
        {value}
      </p>
      {sub && <p className="mt-1.5 text-[14px] text-slate">{sub}</p>}
    </div>
  )
}

export function Score({ grade }: { grade: string }) {
  return (
    <span className="rounded-full bg-mint px-3 py-1.5 text-[14px] font-medium text-emerald-deep tabular-nums">
      Rail score {grade}
    </span>
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="text-[14px] text-slate">{label}</span>
      <div className="mt-2">{children}</div>
      {hint && <span className="mt-2 block text-[13px] text-smoke">{hint}</span>}
    </label>
  )
}

const inputBase =
  'w-full rounded-[16px] border border-hair bg-paper px-4 py-3 text-[16px] text-ink outline-none transition-colors placeholder:text-smoke focus:border-emerald'

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${inputBase} ${props.className || ''}`} />
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${inputBase} appearance-none ${props.className || ''}`} />
}

export function Progress({ raised, target }: { raised: number; target: number }) {
  const p = target ? Math.min(1, raised / target) : 0
  return (
    <div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-mint-soft">
        <div
          className="h-full rounded-full bg-emerald transition-[width] duration-700"
          style={{ width: `${p * 100}%` }}
        />
      </div>
      <p className="mt-2 text-[14px] text-slate tabular-nums">
        {pct(p, 0)} filled
      </p>
    </div>
  )
}

export function Slider({
  value,
  min,
  max,
  step = 50,
  onChange,
  label,
}: {
  value: number
  min: number
  max: number
  step?: number
  onChange: (n: number) => void
  label: string
}) {
  const p = max === min ? 0 : ((value - min) / (max - min)) * 100
  return (
    <input
      type="range"
      aria-label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="upfront-slider w-full"
      style={{ '--fill': `${p}%` } as React.CSSProperties}
    />
  )
}

/**
 * Mean, 5th percentile and chance of loss, rendered as one unit.
 * Never split this apart to show the mean on its own.
 */
export function Returns({
  returns,
  compact,
}: {
  returns: ReturnsShape
  compact?: boolean
}) {
  if (!returns) return null
  return (
    <div>
      <div className={`grid gap-6 ${compact ? 'grid-cols-3' : 'sm:grid-cols-4'}`}>
        <Stat label="Mean return" value={pct(returns.mean)} tone="pos" sub="expected, p.a." />
        <Stat
          label="5th percentile"
          value={pct(returns.p5)}
          tone={returns.p5 < 0 ? 'neg' : undefined}
          sub="1 run in 20 is worse"
        />
        {!compact && (
          <Stat label="1st percentile" value={pct(returns.p1)} tone="neg" sub="1 run in 100 is worse" />
        )}
        <Stat
          label="Chance of loss"
          value={pct(returns.prob_loss, 1)}
          tone={returns.prob_loss > 0.02 ? 'neg' : undefined}
          sub="probability of < 0%"
        />
      </div>
      {!compact && (
        <p className="mt-6 max-w-2xl text-[15px] leading-[1.5] text-slate">
          The mean is not a floor. A single deal is one business, and if it
          fails early the loss is large, which is what the 1st percentile shows.
        </p>
      )}
    </div>
  )
}

export function Note({ children }: { children?: ReactNode }) {
  if (!children) return null
  return (
    <div className="mb-6 rounded-[16px] border border-flag/30 bg-flag/5 px-4 py-3 text-[15px] text-flag">
      {children}
    </div>
  )
}

/** Whether Pinch is live or simulated is never hidden. */
export function ModeBanner({
  mode,
  note,
}: {
  mode?: string | null
  note?: string
}) {
  if (!mode) return null
  const live = mode === 'live'
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 bg-mint px-6 py-2.5 text-[13px] text-emerald-deep">
      <span className="font-semibold">
        {live ? 'Pinch: LIVE (test mode)' : 'Pinch: SIMULATED'}
      </span>
      <span className="opacity-80">
        {note ||
          (live
            ? 'Real API calls against api.getpinch.com.au/test.'
            : 'No credentials found — running the in-process simulator.')}
      </span>
    </div>
  )
}

export function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-hair border-t-ink" />
  )
}

/* ------------------------------------------------------------ motion utils */

export function useInView<T extends HTMLElement>(margin = '-20%') {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setSeen(true), {
      rootMargin: `0px 0px ${margin} 0px`,
    })
    io.observe(el)
    return () => io.disconnect()
  }, [seen, margin])

  return [ref, seen] as const
}

export function useCountUp(target: number, run: boolean, ms = 900) {
  const [v, setV] = useState(0)

  useEffect(() => {
    if (!run) {
      setV(0)
      return
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setV(target)
      return
    }
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms)
      setV(target * (1 - Math.pow(1 - p, 3)))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, run, ms])

  return v
}

/** Staged reveal driver: one step per entry in `delays`. */
export function useSequence(run: boolean, delays: number[]) {
  const [step, setStep] = useState(0)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!run) return
    setStep(0)
    let cancelled = false
    let i = 0
    const advance = () => {
      if (cancelled) return
      i += 1
      setStep(i)
      if (i <= delays.length) window.setTimeout(advance, delays[i - 1] ?? 800)
    }
    const id = window.setTimeout(advance, 250)
    return () => {
      cancelled = true
      window.clearTimeout(id)
    }
  }, [run, nonce, delays])

  return { step, replay: () => setNonce((n) => n + 1) }
}
