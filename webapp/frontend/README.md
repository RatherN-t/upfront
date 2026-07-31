# Upfront frontend

React 19 + Vite 8 + Tailwind CSS v4. Speaks to the FastAPI app under
`webapp/api/` via the Vite `/api` proxy (same-origin session cookie).

```
src/
  App.tsx                 shell, mode banner, role gate
  api.ts                  fetch client + money/pct helpers
  pages/
    Landing.tsx           thesis + calculation reveal
    SignIn.tsx            name + email → session
    BusinessFlow.tsx      path → connect/onboard → offer → round → collections
    InvestorFlow.tsx      marketplace → deal → stake → committed
    Collections.tsx       post-funding collections story
  components/
    ui.tsx                design primitives
    Calculation.tsx       animated eligibility → cash today
    domain.tsx            BookScan, FeeDrag, DistributionChart
  lib/data.ts             landing / collections worked example
```

```bash
npm install
npm run dev      # http://localhost:5173  (API on :8017)
npm run build
```
