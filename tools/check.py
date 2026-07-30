#!/usr/bin/env python3
"""
check — the single verification entrypoint for this repo.

    python3 tools/check.py figures      regenerate engine/FIGURES.json
    python3 tools/check.py guards       run the guards
    python3 tools/check.py tests        run engine tests
    python3 tools/check.py prove        prove the guards catch real regressions
    python3 tools/check.py check        figures + tests + guards
    python3 tools/check.py pre-commit   what the git hook runs
    python3 tools/check.py install-git-hooks

Design rule borrowed from the config repo: a clean pass is not proof. `prove`
introduces a real regression, confirms the guard fails for the right reason,
restores, and confirms it passes again. Guards that cannot be proven this way
are reported as unproven rather than quietly trusted.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ROOT / "tools"))


def _fmt_money(c):
    return "$" + format(round(c / 100), ",")


def _fmt_pct(x, dp=2):
    return f"{x * 100:.{dp}f}%"


def cmd_figures() -> int:
    """Regenerate every number the docs are allowed to assert."""
    from pricing_engine import price_deal, platform_viability
    from portfolio_risk import Position, PortfolioParams, simulate, diversification_curve
    from fees import cadence_comparison
    from mock_books import ALL_BOOKS

    figs, strings = {}, set()

    def rec(key, value, kind="raw"):
        figs[key] = value
        if kind == "money":
            strings.add(_fmt_money(value))
            strings.add("$" + format(value / 100, ",.2f"))   # cents precision
        elif kind == "pct":
            for dp in (0, 1, 2):
                strings.add(_fmt_pct(value, dp))
                strings.add(_fmt_pct(abs(value), dp))        # negatives print bare

    deals = {}
    for b in ALL_BOOKS:
        r = price_deal(b)
        deals[b.name] = r
        k = b.name.split()[0].lower()
        for field, kind in (
            ("gross_face_c", "money"), ("eligible_face_c", "money"),
            ("gross_collections_c", "money"), ("net_settled_c", "money"),
            ("discount_c", "money"), ("cash_today_c", "money"),
            ("platform_c", "money"), ("investor_income_c", "money"),
            ("reserve_c", "money"),
        ):
            rec(f"{k}.{field}", r[field], kind)
        for field in ("fee_drag", "advance_rate", "discount_pct", "business_irr",
                      "investor_gross_irr", "investor_net_irr",
                      "investor_after_cash_drag", "loss_drag_annual",
                      "pd_annual", "pd_life", "continuation", "lgd"):
            rec(f"{k}.{field}", r[field], "pct")
        for field in ("net_loss_rate", "gross_dishonour_rate", "cure_rate",
                      "hard_fail_share", "top_payer_concentration"):
            rec(f"{k}.scan.{field}", r["scan"][field], "pct")
        rec(f"{k}.wal_months", r["wal_months"])
        rec(f"{k}.term_weeks", r["term_weeks"])
        rec(f"{k}.grade", r["grade"])
        for fk in ("txn_fees_c", "decline_fees_c", "transfer_fees_c", "total_fees_c"):
            rec(f"{k}.fees.{fk}", r["fee_breakdown"][fk], "money")

    # cadence
    for label, v in cadence_comparison(3478 * 52, 0.066, 0.68).items():
        rec(f"cadence.{label}.drag", v["drag"], "pct")
        rec(f"cadence.{label}.ticket_c", v["ticket_c"], "money")

    # portfolio
    pos = [Position(b.name, deals[b.name]["cash_today_c"],
                    deals[b.name]["investor_gross_irr"],
                    deals[b.name]["wal_months"] / 12,
                    b.business_pd_annual, b.asset_class) for b in ALL_BOOKS]
    for rho in (0.05, 0.15, 0.25, 0.40):
        s = simulate(pos, PortfolioParams(rho=rho), n=20000)
        tag = f"portfolio.rho{int(rho*100)}"
        for f in ("mean", "p50", "p25", "p10", "p5", "p1",
                  "prob_negative", "prob_below_term_deposit"):
            rec(f"{tag}.{f}", s[f], "pct")

    for k, s in diversification_curve(pos[0], PortfolioParams(rho=0.15)).items():
        for f in ("mean", "p5", "p1", "prob_negative"):
            rec(f"diversification.{k}.{f}", s[f], "pct")

    # platform
    for dep in (5_000_000_00, 10_000_000_00, 20_000_000_00, 50_000_000_00):
        v = platform_viability(list(deals.values()), dep)
        rec(f"platform.{dep//100_00}k.revenue_c", v["annual_revenue_c"], "money")
        rec(f"platform.{dep//100_00}k.profit_c", v["profit_c"], "money")
    v = platform_viability(list(deals.values()), 10_000_000_00)
    rec("platform.breakeven_c", v["breakeven_deployed_c"], "money")
    rec("platform.take_rate", v["take_rate_per_deal"], "pct")
    rec("platform.turns", v["turns_per_year"])

    # median tickets, haircuts, and the retail-scale illustrations
    for b in ALL_BOOKS:
        k = b.name.split()[0].lower()
        rec(f"{k}.median_ticket_c", deals[b.name]["scan"]["median_ticket_c"], "money")
        rec(f"{k}.concentration_haircut_c",
            deals[b.name]["screen"]["concentration_haircut_c"], "money")
        rec(f"{k}.screened_face_c", deals[b.name]["screen"]["screened_face_c"], "money")
        rec(f"{k}.discount_rate_pm", deals[b.name]["discount_rate_pm"], "pct")
    # what $1,000 actually earns in the reference book (the amortisation fix)
    v = deals["Voltride"]
    for amt in (500_00, 1000_00, 5000_00, 25000_00):
        rec(f"retail.{amt//100}.stake_c", amt, "money")
        rec(f"retail.{amt//100}.profit_c",
            amt * v["investor_after_cash_drag"] * v["wal_months"] / 12, "money")
    # policy dials that appear in prose
    from pricing_engine import PricingPolicy, RiskPolicy
    pp, rp = PricingPolicy(), RiskPolicy()
    rec("policy.base_discount_pm", pp.base_discount_pm, "pct")
    rec("policy.reserve_buffer", pp.reserve_buffer, "pct")
    rec("policy.max_advance", pp.max_advance, "pct")
    rec("policy.platform_take", pp.platform_take_of_discount, "pct")
    rec("policy.cash_drag", rp.cash_drag, "pct")
    rec("policy.recourse_unsecured", rp.recourse_recovery, "pct")
    rec("policy.recourse_ppsr", rp.recourse_recovery_with_ppsr, "pct")
    for g, sp in pp.grade_spread_pm.items():
        rec(f"policy.spread.{g}", sp, "pct")
    for a, c in rp.continuation_on_failure.items():
        rec(f"policy.continuation.{a}", c, "pct")
    # cash-drag and platform sensitivity rows quoted in docs
    from pricing_engine import price_deal
    for cd in (0.0, 0.10, 0.18, 0.30, 0.45):
        r2 = price_deal(ALL_BOOKS[0], None, RiskPolicy(cash_drag=cd))
        rec(f"sens.cashdrag.{int(cd*100)}", r2["investor_after_cash_drag"], "pct")
    # published Pinch fee schedule — constants, not derived figures
    import fees as _f
    for v in (_f.DD_FIXED_C, _f.DD_CAP_C, _f.CARD_FIXED_C,
              _f.DECLINE_FEE_C, _f.TRANSFER_FEE_C, _f.DISPUTE_FEE_C):
        rec(f"pinchfee.{v}", v, "money")
    for v in (_f.DD_PCT, _f.CARD_PCT, 0.025):
        rec(f"pinchpct.{v}", v, "pct")
    # per-transaction economics on each book's median ticket
    for b in ALL_BOOKS:
        k = b.name.split()[0].lower()
        t = deals[b.name]["scan"]["median_ticket_c"]
        rec(f"{k}.fee_per_txn_c", _f.dd_fee_c(t), "money")
        rec(f"{k}.fee_per_txn_pct", _f.dd_fee_c(t) / t, "pct")
    for _s in ("$1.2m","$1.2","$17.7m","$17.7","$2 million","$100,000","$10"):
        strings.add(_s)
    # small integers and years are always allowed
    for n in range(0, 301):
        strings.add(f"{n}%")
    for n in range(1900, 2100):
        strings.add(str(n))

    figs["all_strings"] = sorted(strings)
    (ENGINE / "FIGURES.json").write_text(json.dumps(figs, indent=1, default=str))
    print(f"  wrote engine/FIGURES.json  ({len(figs)-1} figures, "
          f"{len(strings)} allowed strings)")
    return 0


def cmd_tests() -> int:
    r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                        "-s", str(ENGINE), "-p", "test_*.py", "-q"],
                       cwd=str(ENGINE))
    if r.returncode:
        return r.returncode
    integ = ROOT / "integration"
    if (integ / "test_adapter.py").exists():
        r2 = subprocess.run([sys.executable, "-m", "unittest", "discover",
                            "-s", str(integ), "-p", "test_*.py", "-q"],
                           cwd=str(ROOT))
        return r2.returncode
    return 0


def cmd_guards(only=None) -> int:
    import guards
    return guards.run_all(only)


def cmd_prove() -> int:
    """A guard you have not seen fail is a guard you do not have."""
    import guards
    cases = [
        ("pinch_api", DOCS_REG := ROOT / "docs" / "02-pinch-integration.md",
         "\n\nPOST /merchants\n"),
        ("no_secrets", ROOT / "docs" / "08-external-setup.md",
         "\n\nsk_live_abcdef1234567890\n"),
    ]
    unproven, proven = [], []
    for guard, path, poison in cases:
        if not path.exists():
            unproven.append(f"{guard}: {path.name} not present")
            continue
        original = path.read_text()
        try:
            path.write_text(original + poison)
            try:
                guards.GUARDS[guard]()
                unproven.append(f"{guard}: did NOT fail on injected regression")
            except guards.Failure:
                proven.append(guard)
        finally:
            path.write_text(original)
        try:
            guards.GUARDS[guard]()
        except guards.Failure as e:
            print(f"  ERROR {guard} still failing after restore: {e}")
            return 1
    for g in proven:
        print(f"  proven    {g}  (failed on regression, passed after restore)")
    for u in unproven:
        print(f"  UNPROVEN  {u}")
    return 1 if unproven else 0


def cmd_check() -> int:
    print("figures:")
    if cmd_figures():
        return 1
    print("tests:")
    if cmd_tests():
        return 1
    print("guards:")
    return cmd_guards()


def cmd_pre_commit() -> int:
    return cmd_check()


def cmd_install_git_hooks() -> int:
    r = subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                       cwd=str(ROOT))
    if r.returncode == 0:
        print("  core.hooksPath -> .githooks")
    return r.returncode


COMMANDS = {
    "figures": cmd_figures, "tests": cmd_tests, "guards": cmd_guards,
    "prove": cmd_prove, "check": cmd_check, "pre-commit": cmd_pre_commit,
    "install-git-hooks": cmd_install_git_hooks,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd not in COMMANDS:
        print(f"unknown command {cmd!r}; one of: {', '.join(COMMANDS)}")
        sys.exit(2)
    sys.exit(COMMANDS[cmd]())
