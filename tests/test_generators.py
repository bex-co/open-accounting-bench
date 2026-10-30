"""Generators are seed-deterministic and seed-sensitive."""

from pathlib import Path

from oab.families import FAMILIES
from oab.generate import task_digest, write_task


def test_same_seed_same_instance():
    for fn in FAMILIES.values():
        first, second = fn(42), fn(42)
        assert first.app_files == second.app_files
        assert first.expected == second.expected
        assert first.solution_ledger == second.solution_ledger


def test_different_seeds_differ():
    for fn in FAMILIES.values():
        assert fn(1).expected != fn(2).expected


def test_written_task_is_reproducible(tmp_path: Path):
    instance = FAMILIES["bank-recon-missing-fee"](102)
    first = write_task(instance, tmp_path / "a")
    digest_a = task_digest(first)
    second = write_task(instance, tmp_path / "b")
    assert task_digest(second) == digest_a


def test_ppe_disposal_proceeds_are_positive():
    """Regression: a large loss offset on a small carrying amount gave negative
    sale proceeds (e.g. seed 6589)."""
    from decimal import Decimal

    for seed in [6589, *range(1, 3000)]:
        deltas = FAMILIES["ppe-disposal"](seed).expected["expected_deltas"]
        assert Decimal(deltas["Assets:Bank:Checking"]) > 0, seed


def test_suspense_memo_states_balance_side_without_sign():
    for seed in range(1, 200):
        memo = FAMILIES["suspense-clearance"](seed).app_files["documents/controller_memo.md"]
        assert "USD -" not in memo, seed
        assert "credit balance" in memo or "debit balance" in memo, seed


def test_level_scores_match_labels_and_generators():
    """docs/task-families.md scores, its labels, and generator levels agree.

    The rubric derives the level from the seven dimension scores
    (>=2 at U or higher -> university; professional needs >=2 P
    including I/E/J). 59 rows drifted once because nothing enforced
    this; the table, the label, and TaskInstance.level must now
    stay in lockstep for every family.
    """
    import re

    text = (Path(__file__).parent.parent / "docs" / "task-families.md").read_text()
    rows = {}
    for line in text.splitlines():
        m = re.match(
            r"\| `([a-z0-9-]+)` \| ([VUP]) \| ([VUP]) \| ([VUP]) \| ([VUP]) "
            r"\| ([VUP]) \| ([VUP]) \| ([VUP]) \| ([^|]+) \|",
            line,
        )
        if m:
            rows[m.group(1)] = (m.groups()[1:8], m.group(9).strip())

    assert set(rows) == set(FAMILIES), sorted(set(FAMILIES) ^ set(rows))
    for task_id, (scores, label) in rows.items():
        ups = sum(1 for s in scores if s in "UP")
        professional = scores.count("P") >= 2 and any(scores[i] == "P" for i in (2, 3, 4))
        derived = "professional" if professional else ("university" if ups >= 2 else "vocational")
        expected_label = (
            "university (borderline)" if derived == "university" and ups == 2 else derived
        )
        assert label == expected_label, (task_id, scores, label)
        assert FAMILIES[task_id](1).level == derived, task_id


def test_scenario_sanity_sweeps():
    """Seeds 0-999: generated scenarios stay economically sensible."""
    import re
    from decimal import Decimal

    for seed in range(1000):
        equity = FAMILIES["accounting-equation-missing-equity"](seed).expected
        assert Decimal(equity["gold"]) > 0 and Decimal(equity["trap_value"]) > 0, seed
        gp = FAMILIES["gross-profit-from-trial-balance"](seed).expected
        assert Decimal(gp["gold"]) > 0, seed
        basket = FAMILIES["basket-purchase-allocation"](seed).expected["expected_deltas"]
        assert basket["Assets:Land"] != basket["Assets:Building"], seed
        slb = FAMILIES["sale-and-leaseback-entry"](seed).expected["expected_deltas"]
        assert (
            Decimal(slb["Assets:RightOfUseAsset"]) < Decimal(slb["Assets:Bank:Checking"]) * 9 / 10
        ), seed
        doc = FAMILIES["expected-profit-choice"](seed).app_files["documents/forecasts.md"]
        rows = re.findall(r"\| (Strong|Weak) demand \| \d+% \| ([\d,]+\.\d\d) \|", doc)
        for i in range(0, len(rows) - 1, 2):
            strong = Decimal(rows[i][1].replace(",", ""))
            weak = Decimal(rows[i + 1][1].replace(",", ""))
            assert rows[i][0] == "Strong" and strong >= weak, (seed, rows)


def test_review_regressions_seed_sweeps():
    """Seeds 0-999: reviewed generators keep their facts internally coherent."""
    import re
    from decimal import ROUND_HALF_UP, Decimal

    def amounts(instance):
        doc = next(v for k, v in instance.app_files.items() if k.startswith("documents/"))
        return [Decimal(x) for x in re.findall(r"\| ([\d]+\.[\d]{2}) \|", doc)]

    for seed in range(1000):
        warranty = FAMILIES["warranty-provision-and-claims"](seed).expected["expected_deltas"]
        assert Decimal(warranty["Liabilities:WarrantyPayable"]) != 0, seed

        cost, accdep, _price = amounts(FAMILIES["depreciation-recapture-ordinary"](seed))
        assert cost - accdep >= 0, seed

        price, inside, appreciation, *_fair_values = amounts(
            FAMILIES["basis-adjustment-754-allocation"](seed)
        )
        assert price - inside <= appreciation, seed

        below_doc = FAMILIES["below-market-imputed-interest"](seed).app_files[
            "documents/loan_data.md"
        ]
        assert "| Loan principal (outstanding all year) | 100000.00 |" not in below_doc, seed

        total, lease_sa, service_sa = amounts(FAMILIES["lease-component-allocation"](seed))
        assert Decimal("0.75") <= total / (lease_sa + service_sa) <= Decimal("1.05"), seed

        disposal = amounts(FAMILIES["disposal-of-subsidiary-gain"](seed))
        retained_ratio = (disposal[1] / 20) / (disposal[0] / 60)
        assert Decimal("0.5") <= retained_ratio <= Decimal("1.05"), seed

        control = FAMILIES["control-deviation-rate"](seed)
        control_doc = control.app_files["documents/control_test.md"]
        sample, deviations = map(
            int, re.search(r"Sample of (\d+).*?In (\d+) items", control_doc, re.S).groups()
        )
        exact = Decimal(deviations * 100) / sample
        half_up = exact.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        assert abs(half_up - Decimal(control.expected["gold"])) <= Decimal(
            control.expected["abs_tolerance"]
        ), seed


def test_second_review_regressions_seed_sweeps():
    """Seeds 0-999: second-review ranges and current-law thresholds hold."""
    import re
    from decimal import Decimal

    def doc(instance):
        return next(v for k, v in instance.app_files.items() if k.startswith("documents/"))

    def amounts(text):
        return [Decimal(x) for x in re.findall(r"\| ([+-]?[\d]+\.[\d]{2}) \|", text)]

    niit_branches = set()
    for seed in range(1000):
        ownership = doc(FAMILIES["constructive-ownership-percent"](seed))
        holdings = [int(x) for x in re.findall(r"owns (\d+)%", ownership[:170])]
        assert sum(holdings[:3]) <= 100, seed

        _assets, liabilities, _d_assets, d_liabilities = amounts(
            doc(FAMILIES["accounting-equation-missing-equity"](seed))
        )
        assert liabilities + d_liabilities >= 0, seed

        capital = FAMILIES["capital-loss-carryforward"](seed)
        assert Decimal(capital.expected["gold"]) > 0, seed
        assert "USD 0.00" not in doc(capital), seed

        fsa_doc = doc(FAMILIES["fsa-tax-saving"](seed))
        election, expenses = amounts(fsa_doc)
        fsa_rate = Decimal(re.search(r"rate \| (\d+)%", fsa_doc)[1]) / 100
        fsa = FAMILIES["fsa-tax-saving"](seed).expected
        assert Decimal(fsa["gold"]) == election * fsa_rate - (election - expenses), seed
        assert Decimal(fsa["trap_value"]) == election * fsa_rate, seed
        assert Decimal(fsa["gold"]) > 0, seed

        single_doc = doc(FAMILIES["single-audit-type-a-count"](seed))
        expended = [
            Decimal(value)
            for value in re.findall(r"\| [\d]+\.[\d]{2} \| ([\d]+\.[\d]{2}) \|", single_doc)
        ]
        single = FAMILIES["single-audit-type-a-count"](seed).expected
        assert sum(expended) <= Decimal("34000000.00"), seed
        assert all(v != Decimal("1000000.00") for v in expended), seed
        assert Decimal(single["gold"]) == sum(v > 1000000 for v in expended), seed
        assert Decimal(single["trap_value"]) == sum(v > 750000 for v in expended), seed
        assert Decimal(single["trap_value"]) > Decimal(single["gold"]), seed

        cash_amounts = amounts(doc(FAMILIES["cash-to-accrual-profit"](seed)))
        revenue = cash_amounts[0] + cash_amounts[2]
        cash_gold = Decimal(FAMILIES["cash-to-accrual-profit"](seed).expected["gold"])
        assert cash_gold / revenue <= Decimal("0.6"), seed

        net, _interest, tax, _dna, _oneoff = amounts(
            doc(FAMILIES["adjusted-ebitda-computation"](seed))
        )
        assert net >= 0 and tax / (net + tax) <= Decimal("0.5"), seed

        niit_amounts = amounts(doc(FAMILIES["individual-tax-with-niit"](seed)))
        niit_branches.add("excess" if niit_amounts[2] < niit_amounts[1] else "nii")

        pension = FAMILIES["pension-expense-and-contribution"](seed).expected
        amortization = -Decimal(
            pension["expected_deltas"]["Equity:AccumulatedOtherComprehensiveIncome"]
        )
        final_aoci = Decimal(
            pension["required_final_balances"]["Equity:AccumulatedOtherComprehensiveIncome"]
        )
        opening_aoci = final_aoci + amortization
        assert opening_aoci / amortization >= 60, seed

        fx_doc = doc(FAMILIES["fx-payable-remeasurement"](seed))
        spots = [Decimal(x) for x in re.findall(r"USD ([0-9.]+) per EUR", fx_doc)]
        assert abs((spots[1] - spots[0]) / spots[0]) <= Decimal("0.05"), seed

        educator = amounts(doc(FAMILIES["tax-return-crossfoot-difference"](seed)))[-1]
        assert educator <= Decimal("300.00"), seed

        days = FAMILIES["inventory-days-on-hand"](seed).expected
        assert Decimal(days["abs_tolerance"]) >= Decimal("0.5"), seed

        error = FAMILIES["inventory-error-correction"](seed)
        retained = Decimal(
            re.search(
                r"Opening retained earnings.*?Equity:Opening-Balances\s+([\d.]+) USD",
                error.initial_ledger,
                re.S,
            )[1]
        )
        error_amount = Decimal(error.expected["expected_deltas"]["Assets:Inventory"])
        assert error_amount / retained >= Decimal("0.01"), seed

    assert niit_branches == {"excess", "nii"}


def test_exact_factor_answers_fit_tolerances():
    """Exact recomputation and stated-factor answers both fit the tolerance."""
    from decimal import Decimal

    # The discrete rate/year grids are small; maximize the monetary amounts.
    for years in [3, 5, 8, 10]:
        for rate in [Decimal("0.06"), Decimal("0.08"), Decimal("0.10")]:
            exact = Decimal(120000) / (1 + rate) ** years
            stated = Decimal(120000) * (Decimal(1) / (1 + rate) ** years).quantize(
                Decimal("0.0000000001")
            )
            assert abs(exact - stated) <= Decimal("0.01")
    for instance_id in ["present-value-lump-sum", "bond-issue-price"]:
        for seed in [1, 7, 42]:
            policy = FAMILIES[instance_id](seed).app_files["policy.md"]
            assert "do not recompute" not in policy


def test_stated_rates_fit_generated_prices():
    """Seeds 0-99: bond/ARO prices are consistent with their stated rates."""
    import re
    from decimal import Decimal

    for seed in range(100):
        terms = FAMILIES["bond-discount-amortization"](seed).app_files["documents/bond_terms.md"]
        face = Decimal(re.search(r"face value USD ([\d]+\.[\d]{2})", terms)[1])
        price = Decimal(re.search(r"Issue price USD ([\d]+\.[\d]{2})", terms)[1])
        monthly = Decimal("0.006")
        semi = (1 + monthly) ** 6 - 1
        pv = (
            face * Decimal("0.03") * sum(1 / (1 + semi) ** k for k in range(1, 11))
            + face / (1 + monthly) ** 60
        )
        assert abs(price - pv) < Decimal("5"), (seed, price, pv)

        doc = FAMILIES["bond-issued-at-premium"](seed).app_files["documents/bond_issuance.md"]
        face = Decimal(re.search(r"Face value USD ([\d]+\.[\d]{2})", doc)[1])
        coupon = Decimal(re.search(r", (\d+)% coupon", doc)[1]) / 100
        market = Decimal(re.search(r"market rate (\d+)%", doc)[1]) / 100
        proceeds = Decimal(re.search(r"sold for USD ([\d]+\.[\d]{2})", doc)[1])
        semi_m = market / 2
        pv = (
            face * coupon / 2 * sum(1 / (1 + semi_m) ** k for k in range(1, 11))
            + face / (1 + semi_m) ** 10
        )
        assert abs(proceeds - pv) < Decimal("5"), (seed, proceeds, pv)

        aro = FAMILIES["aro-accretion"](seed).app_files["documents/aro_data.md"]
        carrying = Decimal(
            re.search(r"Carrying amount at 2026-01-01: USD ([\d]+\.[\d]{2})", aro)[1]
        )
        settlement = Decimal(
            re.search(r"settlement cost in 10 years: USD ([\d]+\.[\d]{2})", aro)[1]
        )
        rate = Decimal(re.search(r"rate: ([\d.]+)% per month", aro)[1]) / 100
        assert abs(settlement - carrying * (1 + rate) ** 120) < Decimal("5"), seed
