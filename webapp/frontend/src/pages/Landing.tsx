import Calculation from '../components/Calculation'
import { Card, Pill, Progress, Score, Tag } from '../components/ui'
import { aud, CASH_TODAY, DEALS, ELIGIBLE, WAL_MONTHS } from '../lib/data'

export default function Landing({ onPick }: { onPick: (r: 'business' | 'investor') => void }) {
  return (
    <>
      <Hero onPick={onPick} />

      <section id="how" className="border-t border-hair bg-fog">
        <div className="mx-auto max-w-[1200px] px-6 py-20 lg:py-28">
          <Calculation />
        </div>
      </section>

      <Handoff onPick={onPick} />
      <Foot />
    </>
  )
}

function Hero({ onPick }: { onPick: (r: 'business' | 'investor') => void }) {
  const deal = DEALS[0]

  return (
    <section className="mx-auto max-w-[1200px] px-6 pt-20 pb-24 lg:pt-28">
      <div className="grid gap-16 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
        <div>
          <Tag>Contract revenue · Australia</Tag>
          <h1 className="display mt-4 text-[clamp(2.75rem,7vw,90px)] leading-[1.08] tracking-[-0.025em]">
            Revenue you have already won, <em>paid today.</em>
          </h1>
          <p className="mt-7 max-w-lg text-[17px] leading-[1.35] text-slate">
            Connect your Pinch account. We read the contracts on your rail,
            strike out the ones nobody can fund, and price the rest, one step
            at a time, in front of you.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Pill onClick={() => onPick('business')}>Get paid now</Pill>
            <Pill variant="ghost" onClick={() => onPick('investor')}>
              Fund a book
            </Pill>
          </div>
          <a
            href="#how"
            className="mt-6 inline-block text-[16px] text-ink hover:underline"
          >
            See how the number is built →
          </a>
        </div>

        {/* Product artifacts, not photography: the only elevated surfaces.
          * They sit apart rather than overlapping, so no label is ever covered. */}
        <div className="space-y-5">
          <Card tone="float" className="p-6 lg:ml-10">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[20px] font-semibold">{deal.business}</p>
                <p className="mt-1 text-[14px] text-ash">{deal.sector}</p>
              </div>
              <Score grade={deal.score} />
            </div>
            <p className="display mt-8 text-[44px] leading-none tracking-[-0.015em] tabular-nums">
              {aud(CASH_TODAY)}
            </p>
            <p className="mt-2 text-[14px] text-slate">
              advanced against {ELIGIBLE} eligible contracts
            </p>
            <div className="mt-6">
              <Progress raised={deal.raised} target={deal.target} />
            </div>
          </Card>

          <Card
            tone="float"
            className="mr-auto w-[80%] p-5 lg:ml-0"
          >
            <p className="text-[14px] text-ash">Average month life</p>
            <p className="mt-1 text-[20px] font-semibold tabular-nums">
              {WAL_MONTHS.toFixed(1)} months
            </p>
            <p className="mt-1 text-[14px] text-emerald">
              ↑ capital returns weekly, from week one
            </p>
          </Card>
        </div>
      </div>
    </section>
  )
}

function Handoff({ onPick }: { onPick: (r: 'business' | 'investor') => void }) {
  return (
    <section className="mx-auto max-w-[1200px] px-6 py-20 lg:py-28">
      <h2 className="display max-w-2xl text-[clamp(2rem,4.4vw,44px)] leading-[1.3] tracking-[-0.015em]">
        Two ways in. The <em>same</em> numbers on both sides.
      </h2>

      <div className="mt-12 grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col p-8 lg:p-10">
          <Tag>For businesses</Tag>
          <h3 className="mt-3 text-[26px] leading-[1.18] font-semibold tracking-[-0.009em]">
            Get paid now
          </h3>
          <p className="mt-4 max-w-sm flex-1 text-[16px] leading-[1.5] text-slate">
            Connect Pinch. We read real payment attempts, not a P&amp;L you
            typed, then make an offer against what actually settles.
          </p>
          <div className="mt-8">
            <Pill onClick={() => onPick('business')}>I&apos;m a business</Pill>
          </div>
        </Card>

        <Card tone="mint" className="flex flex-col p-8 lg:p-10">
          <span className="text-[14px] opacity-70">For investors</span>
          <h3 className="mt-3 text-[26px] leading-[1.18] font-semibold tracking-[-0.009em]">
            Fund a book
          </h3>
          <p className="mt-4 max-w-sm flex-1 text-[16px] leading-[1.5] opacity-85">
            Back Australian businesses against revenue we can see. Every deal
            shows its mean, its 5th percentile and its chance of loss together.
          </p>
          <div className="mt-8">
            <Pill variant="accent" onClick={() => onPick('investor')}>
              I&apos;m an investor
            </Pill>
          </div>
        </Card>
      </div>
    </section>
  )
}

function Foot() {
  return (
    <footer className="border-t border-hair">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-8 gap-y-2 px-6 py-8 text-[14px] text-slate">
        <span className="text-ink">Upfront</span>
        <span className="flex-1" />
        <span>Figures shown are one worked example</span>
        <span>Pinch rail · test mode</span>
      </div>
    </footer>
  )
}
