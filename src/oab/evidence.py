"""Deterministic synthetic evidence packs for workflow task authors.

The toolkit generates one coherent company history from a single seed:
master data, balanced ledger activity over at least three periods,
reconciling subledgers, machine-readable source documents, and optional
registered anomalies.  Clean facts reconcile exactly.  Dirty facts are
allowed only when an anomaly names the evidence, the authoritative
resolution path, the intended disposition, and the plausible wrong path.
That invariant is what lets a later workflow family turn an evidence
pack into a unique oracle instead of a pile of contradictory files.

Everything is original synthetic data.  Names are assembled from generic
word lists and identifiers carry a ``syn-`` prefix; no real company,
filing, examination, or third-party record is used as a template.
"""

from __future__ import annotations

import calendar
import copy
import csv
import io
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from oab.families import (
    ACC_DEP,
    AP,
    AR,
    BANK,
    CENT,
    CONTRACT_LIABILITY,
    COST_OF_SALES,
    DEPRECIATION,
    INVENTORY,
    PRODUCT_REVENUE,
    WAGES,
    _chart_md,
    _ledger_header,
    _txn,
    money,
)

ZERO = Decimal("0.00")
PREPAID = "Assets:PrepaidInsurance"
EQUIPMENT = "Assets:Equipment"
ACCUMULATED_DEPRECIATION = ACC_DEP
ACCRUED_WAGES = "Liabilities:AccruedWages"
NOTES_PAYABLE = "Liabilities:NotesPayable"
SERVICE_REVENUE = "Income:ServiceRevenue"
OPENING_EQUITY = "Equity:Opening-Balances"
INSURANCE = "Expenses:Insurance"
REPAIRS = "Expenses:Repairs"
BANK_FEES = "Expenses:BankFees"

EXTRA_ACCOUNTS = [
    (AR, "Customer receivables"),
    (INVENTORY, "Merchandise inventory"),
    (ACCUMULATED_DEPRECIATION, "Accumulated depreciation (contra asset)"),
    (AP, "Supplier payables"),
    (CONTRACT_LIABILITY, "Customer amounts received before performance"),
    (PRODUCT_REVENUE, "Product revenue"),
    (SERVICE_REVENUE, "Service revenue"),
    (COST_OF_SALES, "Cost of products sold"),
]

ANOMALY_KINDS = (
    "revised_document",
    "duplicate_document",
    "stale_policy",
    "amount_mismatch",
    "contradictory_log",
    "late_corroboration",
    "goods_in_transit",
    "unrecorded_invoice",
    "post_period_receipt",
    "post_period_payment",
    "missing_source_copy",
    "false_alarm",
)

CONFLICTING_DOCUMENT_STATUSES = {
    "superseded",
    "duplicate",
    "conflicting",
    "unrecorded",
    "missing-copy",
    "false-alarm",
    "stale",
}

MAX_EVIDENCE_FILES = 40
MAX_EVIDENCE_TOTAL_BYTES = 250_000
MAX_EVIDENCE_FILE_BYTES = 50_000
MAX_EVIDENCE_TOTAL_LINES = 5_000

_DOCUMENT_PREFIXES = {
    "sales_invoice": "invoice",
    "customer_receipt": "receipt",
    "supplier_bill": "bill",
    "bank_statement": "bankstmt",
    "shipping_log": "shipment",
    "contract": "contractdoc",
    "payroll_register": "payroll",
    "inventory_count": "count",
}

_COMPANY_WORDS = ("North", "Pine", "Harbor", "Summit", "Meadow", "Cedar", "Blue", "Stone")
_COMPANY_SUFFIXES = ("Components", "Systems", "Supply", "Works", "Labs", "Goods")
_PERSON_FIRST = ("Alex", "Blair", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper")
_PERSON_LAST = ("North", "Vale", "Rowan", "Sterling", "Marsh", "Quinn", "Briar", "Slate")
_ITEM_WORDS = ("Bracket", "Module", "Sensor", "Panel", "Valve", "Kit", "Frame", "Unit")


@dataclass
class Party:
    id: str
    kind: str
    name: str
    monthly_pay: Decimal | None = None


@dataclass
class Item:
    id: str
    sku: str
    name: str
    unit_cost: Decimal
    unit_price: Decimal


@dataclass
class Asset:
    id: str
    name: str
    cost: Decimal
    accumulated_depreciation: Decimal
    monthly_depreciation: Decimal
    in_service_date: str


@dataclass
class Contract:
    id: str
    customer_id: str
    title: str
    total: Decimal
    deferred_amount: Decimal
    start: str
    end: str


@dataclass
class BankAccount:
    id: str
    account: str
    label: str
    balance: Decimal


@dataclass
class Period:
    id: str
    label: str
    start: str
    end: str
    closed: bool


@dataclass
class CompanyMasterData:
    company_id: str
    company_name: str
    currency: str
    periods: list[Period]
    accounts: list[tuple[str, str]]
    customers: list[Party]
    suppliers: list[Party]
    employees: list[Party]
    items: list[Item]
    assets: list[Asset]
    contracts: list[Contract]
    bank_accounts: list[BankAccount]


@dataclass
class LedgerTransaction:
    id: str
    date: str
    period: str
    payee: str
    narration: str
    postings: list[tuple[str, Decimal]]
    source_ref: str | None = None


@dataclass
class SubledgerRecord:
    id: str
    kind: str
    control_account: str
    amount: Decimal
    party_id: str | None = None
    item_id: str | None = None
    asset_id: str | None = None
    contract_id: str | None = None
    quantity: Decimal | None = None
    unit_cost: Decimal | None = None
    accumulated_depreciation: Decimal | None = None
    due_date: str | None = None
    status: str = "open"
    source_ref: str | None = None


@dataclass
class DocumentLine:
    description: str
    quantity: Decimal
    unit_amount: Decimal
    amount: Decimal


@dataclass
class Document:
    id: str
    kind: str
    date: str
    period: str
    party_id: str | None
    lines: list[DocumentLine]
    total: Decimal
    currency: str = "USD"
    status: str = "current"
    supersedes: str | None = None
    duplicate_of: str | None = None
    source_refs: list[str] = field(default_factory=list)


@dataclass
class RegisteredAnomaly:
    id: str
    kind: str
    determination: str
    disposition: str
    authoritative_ref: str
    evidence_refs: list[str]
    precedence: str
    wrong_disposition: str


@dataclass
class EvidencePack:
    master: CompanyMasterData
    opening_balances: dict[str, Decimal]
    transactions: list[LedgerTransaction]
    trial_balances: dict[str, dict[str, Decimal]]
    subledgers: dict[str, list[SubledgerRecord]]
    documents: list[Document]
    anomalies: list[RegisteredAnomaly]
    files: dict[str, str]

    @property
    def periods(self) -> list[Period]:
        return self.master.periods


def _shift_month(year: int, month: int, offset: int = 1) -> tuple[int, int]:
    total = (year * 12 + month - 1) + offset
    return total // 12, total % 12 + 1


def _snapshot_dict(balances: dict[str, Decimal]) -> dict[str, Decimal]:
    return {account: amount for account, amount in sorted(balances.items()) if amount != ZERO}


def _periods(start_period: str, count: int) -> list[Period]:
    year_text, month_text = start_period.split("-", 1)
    year, month = int(year_text), int(month_text)
    periods: list[Period] = []
    for index in range(count):
        label = f"{year:04d}-{month:02d}"
        day = calendar.monthrange(year, month)[1]
        periods.append(
            Period(
                id=label,
                label=label,
                start=f"{label}-01",
                end=f"{label}-{day:02d}",
                closed=index < count - 1,
            )
        )
        year, month = _shift_month(year, month)
    return periods


def _date(period: Period, day: int) -> str:
    return f"{period.label}-{day:02d}"


def _next_period_date(period: Period, day: int) -> str:
    year, month = (int(part) for part in period.label.split("-", 1))
    year, month = _shift_month(year, month)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _master_data(rng: random.Random, start_period: str, period_count: int) -> CompanyMasterData:
    periods = _periods(start_period, period_count)
    company_name = (
        f"{rng.choice(_COMPANY_WORDS)} {rng.choice(_COMPANY_WORDS)} {rng.choice(_COMPANY_SUFFIXES)}"
    )
    customers = [
        Party(
            id=f"syn-customer-{index:03d}",
            kind="customer",
            name=f"{rng.choice(_COMPANY_WORDS)} {rng.choice(_COMPANY_SUFFIXES)} {index}",
        )
        for index in range(1, 5)
    ]
    suppliers = [
        Party(
            id=f"syn-supplier-{index:03d}",
            kind="supplier",
            name=f"{rng.choice(_COMPANY_WORDS)} {rng.choice(_COMPANY_SUFFIXES)} {index}",
        )
        for index in range(1, 5)
    ]
    employees = [
        Party(
            id=f"syn-employee-{index:03d}",
            kind="employee",
            name=f"{rng.choice(_PERSON_FIRST)} {rng.choice(_PERSON_LAST)}",
            monthly_pay=Decimal(rng.randrange(2800, 5201, 100)),
        )
        for index in range(1, 6)
    ]
    items: list[Item] = []
    for index in range(1, 5):
        cost = Decimal(rng.randrange(18, 76, 2))
        items.append(
            Item(
                id=f"syn-item-{index:03d}",
                sku=f"SYN-{1000 + index}",
                name=f"{rng.choice(_ITEM_WORDS)} {index}",
                unit_cost=cost,
                unit_price=(cost * Decimal("1.60")).quantize(CENT),
            )
        )
    assets: list[Asset] = []
    for index in range(1, 4):
        cost = Decimal(rng.randrange(6000, 18001, 500))
        life_months = rng.choice([36, 48, 60])
        monthly = (cost / Decimal(life_months)).quantize(CENT)
        accumulated = monthly * rng.randrange(4, 13)
        assets.append(
            Asset(
                id=f"syn-asset-{index:03d}",
                name=f"Production asset {index}",
                cost=cost,
                accumulated_depreciation=accumulated,
                monthly_depreciation=monthly,
                in_service_date=periods[0].start,
            )
        )
    contracts = [
        Contract(
            id=f"syn-contract-{index:03d}",
            customer_id=customers[index - 1].id,
            title=f"Synthetic service agreement {index}",
            total=Decimal(rng.randrange(6000, 12001, 500)),
            deferred_amount=ZERO,
            start=periods[0].start,
            end=periods[-1].end,
        )
        for index in range(1, 3)
    ]
    return CompanyMasterData(
        company_id="syn-company-001",
        company_name=company_name,
        currency="USD",
        periods=periods,
        accounts=EXTRA_ACCOUNTS,
        customers=customers,
        suppliers=suppliers,
        employees=employees,
        items=items,
        assets=assets,
        contracts=contracts,
        bank_accounts=[BankAccount("syn-bank-001", BANK, "Operating checking", ZERO)],
    )


class _PackBuilder:
    def __init__(self, master: CompanyMasterData, rng: random.Random):
        self.master = master
        self.rng = rng
        self.balances: dict[str, Decimal] = {}
        self.transactions: list[LedgerTransaction] = []
        self.documents: list[Document] = []
        self.trial_balances: dict[str, dict[str, Decimal]] = {}
        self.subledgers: dict[str, list[SubledgerRecord]] = {
            "accounts_receivable": [],
            "accounts_payable": [],
            "inventory": [],
            "fixed_assets": [],
            "payroll": [],
            "bank": [],
            "contracts": [],
        }
        self.bank_lines: dict[str, list[DocumentLine]] = {}
        self.counters: dict[str, int] = {}

    def _next_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"syn-{prefix}-{self.counters[prefix]:04d}"

    def document(
        self,
        kind: str,
        date: str,
        period: str,
        party_id: str | None,
        lines: list[DocumentLine],
        *,
        status: str = "current",
        supersedes: str | None = None,
        duplicate_of: str | None = None,
        source_refs: Iterable[str] = (),
    ) -> Document:
        document = Document(
            id=self._next_id(_DOCUMENT_PREFIXES.get(kind, "doc")),
            kind=kind,
            date=date,
            period=period,
            party_id=party_id,
            lines=lines,
            total=sum((line.amount for line in lines), ZERO),
            status=status,
            supersedes=supersedes,
            duplicate_of=duplicate_of,
            source_refs=list(source_refs),
        )
        self.documents.append(document)
        return document

    def txn(
        self,
        date: str,
        period: str,
        payee: str,
        narration: str,
        postings: list[tuple[str, Decimal]],
        *,
        source_ref: str | None = None,
    ) -> LedgerTransaction:
        transaction = LedgerTransaction(
            id=self._next_id("txn"),
            date=date,
            period=period,
            payee=payee,
            narration=narration,
            postings=postings,
            source_ref=source_ref,
        )
        for account, amount in postings:
            self.balances[account] = self.balances.get(account, ZERO) + amount
            if account == BANK:
                self.bank_lines.setdefault(period, []).append(
                    DocumentLine(narration, Decimal("1"), amount, amount)
                )
        self.transactions.append(transaction)
        return transaction

    def _sync_bank(self) -> None:
        balance = self.balances.get(BANK, ZERO)
        self.master.bank_accounts[0].balance = balance
        if self.subledgers["bank"]:
            self.subledgers["bank"][0].amount = balance

    def _sync_fixed_assets(self) -> None:
        self.subledgers["fixed_assets"] = [
            SubledgerRecord(
                id=f"syn-fixed-{index:03d}",
                kind="fixed_asset",
                control_account=EQUIPMENT,
                amount=asset.cost,
                asset_id=asset.id,
                accumulated_depreciation=asset.accumulated_depreciation,
                status="in-service",
            )
            for index, asset in enumerate(self.master.assets, 1)
        ]

    def _snapshot(self, label: str) -> None:
        self._sync_bank()
        self.trial_balances[label] = _snapshot_dict(self.balances)

    def _first_open_record(self, key: str) -> SubledgerRecord | None:
        return next(
            (record for record in self.subledgers[key] if record.amount != ZERO),
            None,
        )

    def setup_opening(self) -> dict[str, Decimal]:
        rng = self.rng
        period = self.master.periods[0]
        for customer in self.master.customers:
            amount = Decimal(rng.randrange(400, 1501, 25))
            document = self.document(
                "sales_invoice",
                period.start,
                period.label,
                customer.id,
                [DocumentLine("Opening customer balance", Decimal("1"), amount, amount)],
            )
            self.subledgers["accounts_receivable"].append(
                SubledgerRecord(
                    id=self._next_id("ar"),
                    kind="accounts_receivable",
                    control_account=AR,
                    amount=amount,
                    party_id=customer.id,
                    due_date=_date(period, 15),
                    source_ref=document.id,
                )
            )
        for supplier in self.master.suppliers:
            amount = Decimal(rng.randrange(300, 1201, 25))
            document = self.document(
                "supplier_bill",
                period.start,
                period.label,
                supplier.id,
                [DocumentLine("Opening supplier balance", Decimal("1"), amount, amount)],
            )
            self.subledgers["accounts_payable"].append(
                SubledgerRecord(
                    id=self._next_id("ap"),
                    kind="accounts_payable",
                    control_account=AP,
                    amount=-amount,
                    party_id=supplier.id,
                    due_date=_date(period, 18),
                    source_ref=document.id,
                )
            )
        for item in self.master.items:
            quantity = Decimal(rng.randrange(25, 86, 5))
            self.subledgers["inventory"].append(
                SubledgerRecord(
                    id=self._next_id("inv"),
                    kind="inventory",
                    control_account=INVENTORY,
                    amount=quantity * item.unit_cost,
                    item_id=item.id,
                    quantity=quantity,
                    unit_cost=item.unit_cost,
                )
            )
        for employee in self.master.employees:
            amount = Decimal(rng.randrange(300, 901, 25))
            self.subledgers["payroll"].append(
                SubledgerRecord(
                    id=self._next_id("payaccrual"),
                    kind="payroll",
                    control_account=ACCRUED_WAGES,
                    amount=-amount,
                    party_id=employee.id,
                    due_date=_date(period, 10),
                )
            )
        for contract in self.master.contracts:
            deferred = Decimal(rng.randrange(1200, 4201, 100))
            contract.deferred_amount = deferred
            document = self.document(
                "contract",
                contract.start,
                period.label,
                contract.customer_id,
                [DocumentLine(contract.title, Decimal("1"), contract.total, contract.total)],
                source_refs=[contract.id],
            )
            self.subledgers["contracts"].append(
                SubledgerRecord(
                    id=self._next_id("deferred"),
                    kind="contract",
                    control_account=CONTRACT_LIABILITY,
                    amount=-deferred,
                    party_id=contract.customer_id,
                    contract_id=contract.id,
                    source_ref=document.id,
                )
            )

        bank_balance = Decimal(rng.randrange(15000, 30001, 250))
        self.subledgers["bank"].append(
            SubledgerRecord(
                id=self._next_id("bankacct"),
                kind="bank",
                control_account=BANK,
                amount=bank_balance,
                status="current",
            )
        )
        self._sync_fixed_assets()

        def total(key: str) -> Decimal:
            return sum((record.amount for record in self.subledgers[key]), ZERO)

        balances = {
            BANK: bank_balance,
            AR: total("accounts_receivable"),
            INVENTORY: total("inventory"),
            PREPAID: Decimal(rng.choice([1200, 1800, 2400])),
            EQUIPMENT: sum((asset.cost for asset in self.master.assets), ZERO),
            ACCUMULATED_DEPRECIATION: -sum(
                (asset.accumulated_depreciation for asset in self.master.assets), ZERO
            ),
            AP: total("accounts_payable"),
            ACCRUED_WAGES: total("payroll"),
            CONTRACT_LIABILITY: total("contracts"),
            NOTES_PAYABLE: Decimal(-rng.randrange(4000, 9001, 500)),
        }
        balances[OPENING_EQUITY] = -sum(balances.values(), ZERO)
        self.balances = dict(balances)
        self._sync_bank()
        self._snapshot("opening")
        return dict(balances)

    def _inventory_record(self, item_id: str) -> SubledgerRecord:
        return next(record for record in self.subledgers["inventory"] if record.item_id == item_id)

    def _sale(self, period: Period, day: int) -> None:
        rng = self.rng
        customer = rng.choice(self.master.customers)
        item = rng.choice(self.master.items)
        record = self._inventory_record(item.id)
        available = int(record.quantity or ZERO)
        quantity = (
            Decimal(rng.randrange(3, min(16, available) + 1)) if available >= 3 else Decimal(0)
        )
        if quantity == ZERO:
            return
        revenue = quantity * item.unit_price
        cost = quantity * item.unit_cost
        invoice = self.document(
            "sales_invoice",
            _date(period, day),
            period.label,
            customer.id,
            [DocumentLine(item.name, quantity, item.unit_price, revenue)],
        )
        self.document(
            "shipping_log",
            _date(period, day),
            period.label,
            customer.id,
            [DocumentLine(item.name, quantity, ZERO, ZERO)],
            source_refs=[invoice.id],
        )
        self.subledgers["accounts_receivable"].append(
            SubledgerRecord(
                id=self._next_id("ar"),
                kind="accounts_receivable",
                control_account=AR,
                amount=revenue,
                party_id=customer.id,
                item_id=item.id,
                due_date=_date(period, min(day + 14, 28)),
                source_ref=invoice.id,
            )
        )
        record.quantity = (record.quantity or ZERO) - quantity
        record.amount = (record.quantity or ZERO) * item.unit_cost
        self.txn(
            _date(period, day),
            period.label,
            customer.name,
            "Product sale",
            [(AR, revenue), (PRODUCT_REVENUE, -revenue)],
            source_ref=invoice.id,
        )
        self.txn(
            _date(period, day),
            period.label,
            "Warehouse",
            "Cost of product sale",
            [(COST_OF_SALES, cost), (INVENTORY, -cost)],
            source_ref=invoice.id,
        )

    def _settle_oldest(
        self,
        *,
        key: str,
        period: Period,
        day: int,
        document_kind: str,
        narration: str,
        parties: list[Party],
        maximum: int,
    ) -> None:
        record = self._first_open_record(key)
        if record is None:
            return
        amount = min(abs(record.amount), Decimal(self.rng.randrange(200, maximum, 25)))
        party = next(candidate for candidate in parties if candidate.id == record.party_id)
        document = self.document(
            document_kind,
            _date(period, day),
            period.label,
            party.id,
            [DocumentLine(f"{party.kind.title()} payment", Decimal("1"), amount, amount)],
            source_refs=[record.source_ref] if record.source_ref else [],
        )
        if record.amount > ZERO:
            record.amount -= amount
            postings = [(BANK, amount), (record.control_account, -amount)]
        else:
            record.amount += amount
            postings = [(record.control_account, amount), (BANK, -amount)]
        record.status = "closed" if record.amount == ZERO else "open"
        self.txn(
            _date(period, day),
            period.label,
            party.name,
            narration,
            postings,
            source_ref=document.id,
        )

    def _customer_receipt(self, period: Period, day: int) -> None:
        self._settle_oldest(
            key="accounts_receivable",
            period=period,
            day=day,
            document_kind="customer_receipt",
            narration="Customer receipt",
            parties=self.master.customers,
            maximum=901,
        )

    def _supplier_purchase(self, period: Period, day: int) -> None:
        rng = self.rng
        supplier = rng.choice(self.master.suppliers)
        item = rng.choice(self.master.items)
        quantity = Decimal(rng.randrange(10, 36, 5))
        amount = quantity * item.unit_cost
        document = self.document(
            "supplier_bill",
            _date(period, day),
            period.label,
            supplier.id,
            [DocumentLine(item.name, quantity, item.unit_cost, amount)],
        )
        record = self._inventory_record(item.id)
        record.quantity = (record.quantity or ZERO) + quantity
        record.amount = (record.quantity or ZERO) * item.unit_cost
        self.subledgers["accounts_payable"].append(
            SubledgerRecord(
                id=self._next_id("ap"),
                kind="accounts_payable",
                control_account=AP,
                amount=-amount,
                party_id=supplier.id,
                item_id=item.id,
                due_date=_date(period, min(day + 14, 28)),
                source_ref=document.id,
            )
        )
        self.txn(
            _date(period, day),
            period.label,
            supplier.name,
            "Inventory purchase",
            [(INVENTORY, amount), (AP, -amount)],
            source_ref=document.id,
        )

    def _supplier_payment(self, period: Period, day: int) -> None:
        self._settle_oldest(
            key="accounts_payable",
            period=period,
            day=day,
            document_kind="supplier_payment",
            narration="Supplier payment",
            parties=self.master.suppliers,
            maximum=1001,
        )

    def generate_periods(self) -> None:
        for period in self.master.periods:
            self._supplier_purchase(period, 3)
            self._sale(period, 5)
            self._sale(period, 9)
            self._customer_receipt(period, 12)
            self._supplier_payment(period, 15)

            supplier = self.rng.choice(self.master.suppliers)
            repairs = Decimal(self.rng.randrange(150, 501, 25))
            bill = self.document(
                "supplier_bill",
                _date(period, 18),
                period.label,
                supplier.id,
                [DocumentLine("Repairs service", Decimal("1"), repairs, repairs)],
            )
            self.subledgers["accounts_payable"].append(
                SubledgerRecord(
                    id=self._next_id("ap"),
                    kind="accounts_payable",
                    control_account=AP,
                    amount=-repairs,
                    party_id=supplier.id,
                    due_date=_date(period, 28),
                    source_ref=bill.id,
                )
            )
            self.txn(
                _date(period, 18),
                period.label,
                supplier.name,
                "Repairs service",
                [(REPAIRS, repairs), (AP, -repairs)],
                source_ref=bill.id,
            )

            contract_record = next(
                (record for record in self.subledgers["contracts"] if record.amount != ZERO),
                None,
            )
            if contract_record is not None:
                earned = min(-contract_record.amount, Decimal("250.00"))
                contract = next(
                    item for item in self.master.contracts if item.id == contract_record.contract_id
                )
                contract_record.amount += earned
                contract_record.status = "closed" if contract_record.amount == ZERO else "open"
                contract.deferred_amount = -contract_record.amount
                self.txn(
                    _date(period, 20),
                    period.label,
                    "Customer",
                    "Service revenue earned",
                    [(CONTRACT_LIABILITY, earned), (SERVICE_REVENUE, -earned)],
                    source_ref=contract_record.source_ref,
                )

            record = self._first_open_record("payroll")
            if record is not None:
                amount = -record.amount
                record.amount = ZERO
                record.status = "closed"
                self.txn(
                    _date(period, 25),
                    period.label,
                    "Payroll",
                    "Pay accrued wages",
                    [(ACCRUED_WAGES, amount), (BANK, -amount)],
                )
            payroll_lines = []
            wages_total = ZERO
            for employee in self.master.employees:
                pay = employee.monthly_pay or ZERO
                wages_total += pay
                payroll_lines.append(DocumentLine(employee.name, Decimal("1"), pay, pay))
                self.subledgers["payroll"].append(
                    SubledgerRecord(
                        id=self._next_id("payaccrual"),
                        kind="payroll",
                        control_account=ACCRUED_WAGES,
                        amount=-pay,
                        party_id=employee.id,
                        due_date=period.end,
                    )
                )
            register = self.document(
                "payroll_register", _date(period, 28), period.label, None, payroll_lines
            )
            self.txn(
                _date(period, 28),
                period.label,
                "Payroll",
                "Monthly wages",
                [(WAGES, wages_total), (ACCRUED_WAGES, -wages_total)],
                source_ref=register.id,
            )

            if self.balances.get(PREPAID, ZERO) >= Decimal("100.00"):
                self.txn(
                    _date(period, 28),
                    period.label,
                    "Insurer",
                    "Insurance expired",
                    [(INSURANCE, Decimal("100.00")), (PREPAID, Decimal("-100.00"))],
                )
            depreciation = sum((asset.monthly_depreciation for asset in self.master.assets), ZERO)
            for asset in self.master.assets:
                asset.accumulated_depreciation += asset.monthly_depreciation
            self._sync_fixed_assets()
            self.txn(
                _date(period, 28),
                period.label,
                "Fixed assets",
                "Monthly depreciation",
                [(DEPRECIATION, depreciation), (ACCUMULATED_DEPRECIATION, -depreciation)],
            )
            fee = Decimal("25.00")
            self.txn(
                _date(period, 28),
                period.label,
                "Bank",
                "Monthly bank fee",
                [(BANK_FEES, fee), (BANK, -fee)],
            )
            self.document(
                "bank_statement",
                period.end,
                period.label,
                None,
                list(self.bank_lines.get(period.label, [])),
            )
            self._snapshot(period.label)

        current = self.master.periods[-1]
        count_lines = []
        items_by_id = {item.id: item for item in self.master.items}
        for record in self.subledgers["inventory"]:
            item = items_by_id[record.item_id]
            count_lines.append(
                DocumentLine(
                    item.name,
                    record.quantity or ZERO,
                    record.unit_cost or item.unit_cost,
                    record.amount,
                )
            )
        self.document("inventory_count", current.end, current.label, None, count_lines)

    def _first_document(self, kind: str) -> Document:
        return next(document for document in self.documents if document.kind == kind)

    def _register(
        self,
        anomalies: list[RegisteredAnomaly],
        kind: str,
        disposition: str,
        authoritative: Document,
        evidence: list[Document],
        precedence: str,
        wrong_disposition: str,
    ) -> None:
        anomalies.append(
            RegisteredAnomaly(
                id=f"syn-anomaly-{len(anomalies) + 1:03d}",
                kind=kind,
                determination=f"resolve-{kind.replace('_', '-')}",
                disposition=disposition,
                authoritative_ref=authoritative.id,
                evidence_refs=[document.id for document in evidence],
                precedence=precedence,
                wrong_disposition=wrong_disposition,
            )
        )

    def apply_anomalies(self, kinds: Iterable[str]) -> list[RegisteredAnomaly]:
        anomalies: list[RegisteredAnomaly] = []
        current = self.master.periods[-1]
        for kind in kinds:
            if kind not in ANOMALY_KINDS:
                raise ValueError(f"unknown evidence anomaly kind {kind!r}")
            if kind == "revised_document":
                original = self._first_document("bank_statement")
                revised_lines = copy.deepcopy(original.lines)
                revised_lines.append(
                    DocumentLine(
                        "Corrected bank charge", Decimal("1"), Decimal("-5.00"), Decimal("-5.00")
                    )
                )
                original.status = "superseded"
                revised = self.document(
                    "bank_statement",
                    current.end,
                    current.label,
                    None,
                    revised_lines,
                    supersedes=original.id,
                    source_refs=[original.id],
                )
                self._register(
                    anomalies,
                    kind,
                    "use-revised-document",
                    revised,
                    [original, revised],
                    "The later revised bank statement supersedes the earlier statement.",
                    "use-superseded-document",
                )
            elif kind == "duplicate_document":
                original = self._first_document("supplier_bill")
                duplicate = self.document(
                    "supplier_bill",
                    current.end,
                    current.label,
                    original.party_id,
                    copy.deepcopy(original.lines),
                    status="duplicate",
                    duplicate_of=original.id,
                    source_refs=[original.id],
                )
                self._register(
                    anomalies,
                    kind,
                    "ignore-duplicate",
                    original,
                    [original, duplicate],
                    "A duplicate copy does not create a second obligation.",
                    "record-duplicate",
                )
            elif kind == "stale_policy":
                old = self.document(
                    "policy",
                    current.start,
                    current.label,
                    None,
                    [DocumentLine("Superseded capitalization threshold", Decimal("1"), ZERO, ZERO)],
                    status="stale",
                )
                current_policy = self.document(
                    "policy",
                    current.end,
                    current.label,
                    None,
                    [DocumentLine("Current capitalization threshold", Decimal("1"), ZERO, ZERO)],
                    supersedes=old.id,
                    source_refs=[old.id],
                )
                self._register(
                    anomalies,
                    kind,
                    "use-current-policy",
                    current_policy,
                    [old, current_policy],
                    "The current policy supersedes the stale policy for this period.",
                    "use-stale-policy",
                )
            elif kind == "amount_mismatch":
                supplier = self.master.suppliers[0]
                owed = -sum(
                    (
                        record.amount
                        for record in self.subledgers["accounts_payable"]
                        if record.party_id == supplier.id
                    ),
                    ZERO,
                )
                statement = self.document(
                    "supplier_statement",
                    current.end,
                    current.label,
                    supplier.id,
                    [
                        DocumentLine(
                            "Supplier statement balance",
                            Decimal("1"),
                            owed + Decimal("125.00"),
                            owed + Decimal("125.00"),
                        )
                    ],
                    status="conflicting",
                )
                reconciliation = self.document(
                    "supplier_reconciliation",
                    current.end,
                    current.label,
                    supplier.id,
                    [DocumentLine("Reconciled supplier balance", Decimal("1"), owed, owed)],
                    source_refs=[statement.id],
                )
                self._register(
                    anomalies,
                    kind,
                    "use-reconciled-balance",
                    reconciliation,
                    [statement, reconciliation],
                    "The itemized reconciliation prevails over an unexplained statement total.",
                    "use-statement-total",
                )
            elif kind == "contradictory_log":
                original = self._first_document("shipping_log")
                lines = copy.deepcopy(original.lines)
                if lines:
                    lines[0].quantity += Decimal("1")
                conflicting = self.document(
                    "shipping_log",
                    current.end,
                    current.label,
                    original.party_id,
                    lines,
                    status="conflicting",
                    source_refs=[original.id],
                )
                self._register(
                    anomalies,
                    kind,
                    "use-signed-shipping-log",
                    original,
                    [original, conflicting],
                    "The signed shipping log prevails over the unsigned warehouse copy.",
                    "use-unsigned-log",
                )
            elif kind == "late_corroboration":
                shipment = self._first_document("shipping_log")
                late = self.document(
                    "delivery_confirmation",
                    _next_period_date(current, 3),
                    "subsequent",
                    shipment.party_id,
                    copy.deepcopy(shipment.lines),
                    status="corroborating",
                    source_refs=[shipment.id],
                )
                self._register(
                    anomalies,
                    kind,
                    "treat-as-current-period-corroboration",
                    shipment,
                    [shipment, late],
                    "Later delivery confirmation corroborates the current-period shipment date.",
                    "defer-to-subsequent-period",
                )
            elif kind == "goods_in_transit":
                item = self.master.items[0]
                supplier = self.master.suppliers[0]
                quantity = Decimal("10")
                shipped = self.document(
                    "shipping_log",
                    current.end,
                    current.label,
                    supplier.id,
                    [DocumentLine(item.name, quantity, item.unit_cost, quantity * item.unit_cost)],
                    status="in-transit",
                )
                received = self.document(
                    "receiving_log",
                    _next_period_date(current, 2),
                    "subsequent",
                    supplier.id,
                    copy.deepcopy(shipped.lines),
                    status="corroborating",
                    source_refs=[shipped.id],
                )
                self._register(
                    anomalies,
                    kind,
                    "apply-stated-title-transfer",
                    shipped,
                    [shipped, received],
                    "Shipping title terms determine the period; receipt date alone does not.",
                    "use-receipt-date-only",
                )
            elif kind == "unrecorded_invoice":
                supplier = self.master.suppliers[1]
                amount = Decimal("425.00")
                bill = self.document(
                    "supplier_bill",
                    current.end,
                    current.label,
                    supplier.id,
                    [
                        DocumentLine(
                            "Unrecorded current-period service", Decimal("1"), amount, amount
                        )
                    ],
                    status="unrecorded",
                )
                self._register(
                    anomalies,
                    kind,
                    "record-current-period",
                    bill,
                    [bill],
                    "A valid current-period bill is recorded even if missing from the subledger.",
                    "omit-unrecorded-invoice",
                )
            elif kind == "post_period_receipt":
                record = self._first_open_record("accounts_receivable")
                assert record is not None
                receipt = self.document(
                    "customer_receipt",
                    _next_period_date(current, 4),
                    "subsequent",
                    record.party_id,
                    [
                        DocumentLine(
                            "Subsequent customer payment",
                            Decimal("1"),
                            record.amount,
                            record.amount,
                        )
                    ],
                    status="subsequent",
                    source_refs=[record.source_ref] if record.source_ref else [],
                )
                self._register(
                    anomalies,
                    kind,
                    "use-as-subsequent-evidence",
                    receipt,
                    [receipt],
                    "Subsequent receipt evidences the receivable; it is not current-period cash.",
                    "record-as-current-cash",
                )
            elif kind == "post_period_payment":
                record = self._first_open_record("accounts_payable")
                assert record is not None
                amount = -record.amount
                payment = self.document(
                    "supplier_payment",
                    _next_period_date(current, 5),
                    "subsequent",
                    record.party_id,
                    [DocumentLine("Subsequent supplier payment", Decimal("1"), amount, amount)],
                    status="subsequent",
                    source_refs=[record.source_ref] if record.source_ref else [],
                )
                self._register(
                    anomalies,
                    kind,
                    "use-as-subsequent-evidence",
                    payment,
                    [payment],
                    "Subsequent payment evidences the payable; it is not current-period cash.",
                    "record-as-current-cash",
                )
            elif kind == "missing_source_copy":
                shipment = next(
                    document
                    for document in self.documents
                    if document.kind == "shipping_log" and document.source_refs
                )
                invoice = next(
                    document
                    for document in self.documents
                    if document.id == shipment.source_refs[0]
                )
                invoice.status = "missing-copy"
                self._register(
                    anomalies,
                    kind,
                    "rely-on-corroborating-shipment",
                    shipment,
                    [invoice, shipment],
                    "The signed shipping log corroborates a sale with a missing invoice copy.",
                    "omit-sale-without-invoice-copy",
                )
            elif kind == "false_alarm":
                inquiry = self.document(
                    "bank_inquiry",
                    current.end,
                    current.label,
                    None,
                    [DocumentLine("Bank inquiry with no charge", Decimal("1"), ZERO, ZERO)],
                    status="false-alarm",
                )
                self._register(
                    anomalies,
                    kind,
                    "no-entry",
                    inquiry,
                    [inquiry],
                    "An inquiry with no amount or obligation requires no journal entry.",
                    "record-false-alarm",
                )
        return anomalies


def _csv(rows: Iterable[Iterable[object]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    return output.getvalue()


def _document_rows(documents: Iterable[Document]) -> list[list[object]]:
    rows: list[list[object]] = [
        [
            "document_id",
            "kind",
            "date",
            "period",
            "party_id",
            "status",
            "description",
            "quantity",
            "unit_amount",
            "line_amount",
            "document_total",
            "source_refs",
        ]
    ]
    for document in documents:
        for line in document.lines:
            rows.append(
                [
                    document.id,
                    document.kind,
                    document.date,
                    document.period,
                    document.party_id or "",
                    document.status,
                    line.description,
                    money(line.quantity),
                    money(line.unit_amount),
                    money(line.amount),
                    money(document.total),
                    ";".join(document.source_refs),
                ]
            )
    return rows


def _render_files(builder: _PackBuilder, opening_balances: dict[str, Decimal]) -> dict[str, str]:
    master = builder.master
    ledger = _ledger_header(ZERO, EXTRA_ACCOUNTS)
    ledger += _txn(
        master.periods[0].start,
        master.company_name,
        "Opening balances",
        [
            (account, amount)
            for account, amount in sorted(opening_balances.items())
            if amount != ZERO
        ],
    )
    for transaction in builder.transactions:
        ledger += _txn(
            transaction.date,
            transaction.payee,
            transaction.narration,
            transaction.postings,
        )

    trial_rows: list[list[object]] = [["period", "account", "balance"]]
    for label, balances in builder.trial_balances.items():
        for account, amount in balances.items():
            trial_rows.append([label, account, money(amount)])

    history_rows: list[list[object]] = [
        ["transaction_id", "date", "period", "account", "amount", "source_ref"]
    ]
    for transaction in builder.transactions:
        for account, amount in transaction.postings:
            history_rows.append(
                [
                    transaction.id,
                    transaction.date,
                    transaction.period,
                    account,
                    money(amount),
                    transaction.source_ref or "",
                ]
            )

    def subledger_csv(key: str) -> str:
        rows: list[list[object]] = [
            [
                "record_id",
                "kind",
                "control_account",
                "amount",
                "party_id",
                "item_id",
                "asset_id",
                "contract_id",
                "quantity",
                "unit_cost",
                "accumulated_depreciation",
                "due_date",
                "status",
                "source_ref",
            ]
        ]
        for record in builder.subledgers[key]:
            rows.append(
                [
                    record.id,
                    record.kind,
                    record.control_account,
                    money(record.amount),
                    record.party_id or "",
                    record.item_id or "",
                    record.asset_id or "",
                    record.contract_id or "",
                    money(record.quantity) if record.quantity is not None else "",
                    money(record.unit_cost) if record.unit_cost is not None else "",
                    money(record.accumulated_depreciation)
                    if record.accumulated_depreciation is not None
                    else "",
                    record.due_date or "",
                    record.status,
                    record.source_ref or "",
                ]
            )
        return _csv(rows)

    documents = builder.documents
    files = {
        "ledger.beancount": ledger,
        "chart_of_accounts.md": _chart_md(EXTRA_ACCOUNTS),
        "master_data.json": json.dumps(
            {
                "company_id": master.company_id,
                "company_name": master.company_name,
                "currency": master.currency,
                "periods": [period.__dict__ for period in master.periods],
                "customers": [party.__dict__ for party in master.customers],
                "suppliers": [party.__dict__ for party in master.suppliers],
                "employees": [party.__dict__ for party in master.employees],
                "items": [item.__dict__ for item in master.items],
                "assets": [asset.__dict__ for asset in master.assets],
                "contracts": [contract.__dict__ for contract in master.contracts],
                "bank_accounts": [account.__dict__ for account in master.bank_accounts],
            },
            indent=2,
            default=str,
        )
        + "\n",
        "trial_balances.csv": _csv(trial_rows),
        "account_history.csv": _csv(history_rows),
        "documents/contracts.json": json.dumps(
            [contract.__dict__ for contract in master.contracts], indent=2, default=str
        )
        + "\n",
        "documents/evidence_index.json": json.dumps(
            [
                {
                    "id": document.id,
                    "kind": document.kind,
                    "date": document.date,
                    "period": document.period,
                    "party_id": document.party_id,
                    "status": document.status,
                    "supersedes": document.supersedes,
                    "duplicate_of": document.duplicate_of,
                    "source_refs": document.source_refs,
                    "total": money(document.total),
                }
                for document in documents
            ],
            indent=2,
        )
        + "\n",
    }
    for key in builder.subledgers:
        files[f"subledgers/{key}.csv"] = subledger_csv(key)

    document_groups: dict[str, set[str]] = {
        "documents/sales_invoices.csv": {"sales_invoice"},
        "documents/customer_receipts.csv": {"customer_receipt"},
        "documents/bank_statements.csv": {"bank_statement"},
        "documents/shipping_log.csv": {
            "shipping_log",
            "receiving_log",
            "delivery_confirmation",
        },
        "documents/inventory_counts.csv": {"inventory_count"},
        "documents/payroll_register.csv": {"payroll_register"},
    }
    grouped_kinds = set().union(*document_groups.values())
    for path, kinds in document_groups.items():
        files[path] = _csv(_document_rows(doc for doc in documents if doc.kind in kinds))
    files["documents/supplier_documents.csv"] = _csv(
        _document_rows(doc for doc in documents if doc.kind.startswith("supplier_"))
    )
    files["documents/other_documents.csv"] = _csv(
        _document_rows(
            doc
            for doc in documents
            if doc.kind not in grouped_kinds
            and doc.kind != "contract"
            and not doc.kind.startswith("supplier_")
        )
    )
    return dict(sorted(files.items()))


def _selected_anomalies(seed: int) -> list[str]:
    rng = random.Random(seed ^ 0x5EED5)
    return rng.sample(ANOMALY_KINDS, k=6)


def generate_company_history(
    seed: int,
    *,
    start_period: str = "2025-11",
    period_count: int = 3,
    anomalies: Iterable[str] | None = None,
) -> EvidencePack:
    """Generate and validate one deterministic synthetic evidence pack."""

    if period_count < 3:
        raise ValueError("an evidence pack needs at least three periods")
    rng = random.Random(seed)
    master = _master_data(rng, start_period, period_count)
    builder = _PackBuilder(master, rng)
    opening = builder.setup_opening()
    builder.generate_periods()
    selected = _selected_anomalies(seed) if anomalies is None else list(anomalies)
    registered = builder.apply_anomalies(selected)
    pack = EvidencePack(
        master=master,
        opening_balances=opening,
        transactions=builder.transactions,
        trial_balances=builder.trial_balances,
        subledgers=builder.subledgers,
        documents=builder.documents,
        anomalies=registered,
        files={},
    )
    pack.files = _render_files(builder, opening)
    failures = validate_evidence_pack(pack) + validate_evidence_budgets(pack)
    if failures:
        raise ValueError("generated evidence pack failed validation: " + "; ".join(failures))
    return pack


def clean_example_pack(seed: int) -> EvidencePack:
    return generate_company_history(seed, anomalies=())


def dirty_example_pack(seed: int) -> EvidencePack:
    return generate_company_history(seed, anomalies=None)


def validate_evidence_budgets(pack: EvidencePack) -> list[str]:
    failures: list[str] = []
    if len(pack.files) > MAX_EVIDENCE_FILES:
        failures.append(
            f"evidence pack file count {len(pack.files)} exceeds file budget {MAX_EVIDENCE_FILES}"
        )
    total_bytes = 0
    total_lines = 0
    for path, content in pack.files.items():
        size = len(content.encode("utf-8"))
        total_bytes += size
        total_lines += content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        if size > MAX_EVIDENCE_FILE_BYTES:
            failures.append(
                f"{path}: size {size} exceeds per-file byte budget {MAX_EVIDENCE_FILE_BYTES}"
            )
    if total_bytes > MAX_EVIDENCE_TOTAL_BYTES:
        failures.append(
            f"evidence pack size {total_bytes} exceeds total byte budget {MAX_EVIDENCE_TOTAL_BYTES}"
        )
    if total_lines > MAX_EVIDENCE_TOTAL_LINES:
        failures.append(
            f"evidence pack lines {total_lines} exceeds line budget {MAX_EVIDENCE_TOTAL_LINES}"
        )
    return failures


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def validate_evidence_pack(pack: EvidencePack) -> list[str]:
    """Return referential-integrity failures for an evidence pack."""

    failures: list[str] = []
    master = pack.master
    parties = {
        party.id: party for party in [*master.customers, *master.suppliers, *master.employees]
    }
    items = {item.id: item for item in master.items}
    assets = {asset.id: asset for asset in master.assets}
    contracts = {contract.id: contract for contract in master.contracts}
    periods = {period.label: period for period in master.periods}

    for label, values in [
        ("party", parties),
        ("item", items),
        ("asset", assets),
        ("contract", contracts),
    ]:
        for value in values:
            if not value.startswith("syn-"):
                failures.append(f"{label} id {value!r} is not a synthetic syn- identifier")

    if sum(pack.opening_balances.values(), ZERO) != ZERO:
        failures.append("opening balances do not balance")

    balances = dict(pack.opening_balances)
    opening_snapshot = pack.trial_balances.get("opening", {})
    if opening_snapshot != _snapshot_dict(balances):
        failures.append("opening trial balance does not match opening balances")

    transaction_ids = [transaction.id for transaction in pack.transactions]
    for duplicate in sorted(_duplicates(transaction_ids)):
        failures.append(f"duplicate transaction id {duplicate}")
    document_ids = {document.id for document in pack.documents}
    known_refs = set(document_ids) | set(parties) | set(items) | set(assets) | set(contracts)
    for transaction in pack.transactions:
        if transaction.period not in periods:
            failures.append(f"{transaction.id}: unknown period {transaction.period!r}")
        total = sum((amount for _account, amount in transaction.postings), ZERO)
        if total != ZERO:
            failures.append(f"{transaction.id}: postings do not balance")
        if transaction.source_ref is not None and transaction.source_ref not in known_refs:
            failures.append(
                f"{transaction.id}: unknown source reference {transaction.source_ref!r}"
            )

    transactions_by_period: dict[str, list[LedgerTransaction]] = {}
    for transaction in pack.transactions:
        transactions_by_period.setdefault(transaction.period, []).append(transaction)
    for period in master.periods:
        for transaction in transactions_by_period.get(period.label, []):
            for account, amount in transaction.postings:
                balances[account] = balances.get(account, ZERO) + amount
        expected = _snapshot_dict(balances)
        if pack.trial_balances.get(period.label) != expected:
            failures.append(f"trial balance for {period.label} does not roll forward")

    current = pack.trial_balances.get(master.periods[-1].label, {})

    def balance(account: str) -> Decimal:
        return current.get(account, ZERO)

    record_ids: list[str] = []
    for key, records in pack.subledgers.items():
        for record in records:
            record_ids.append(record.id)
            if record.party_id is not None and record.party_id not in parties:
                failures.append(f"{record.id}: unknown party {record.party_id!r}")
            if record.item_id is not None and record.item_id not in items:
                failures.append(f"{record.id}: unknown item {record.item_id!r}")
            if record.asset_id is not None and record.asset_id not in assets:
                failures.append(f"{record.id}: unknown asset {record.asset_id!r}")
            if record.contract_id is not None and record.contract_id not in contracts:
                failures.append(f"{record.id}: unknown contract {record.contract_id!r}")
            if record.source_ref is not None and record.source_ref not in known_refs:
                failures.append(f"{record.id}: unknown source reference {record.source_ref!r}")
            if key == "inventory":
                quantity = record.quantity or ZERO
                unit_cost = record.unit_cost or ZERO
                if record.amount != quantity * unit_cost:
                    failures.append(
                        f"{record.id}: inventory amount does not equal quantity x unit cost"
                    )
    for duplicate in sorted(_duplicates(record_ids)):
        failures.append(f"duplicate subledger record id {duplicate}")

    def subtotal(key: str) -> Decimal:
        return sum((record.amount for record in pack.subledgers.get(key, [])), ZERO)

    reconciliations = [
        ("accounts receivable", subtotal("accounts_receivable"), balance(AR)),
        ("accounts payable", subtotal("accounts_payable"), balance(AP)),
        ("inventory", subtotal("inventory"), balance(INVENTORY)),
        ("payroll", subtotal("payroll"), balance(ACCRUED_WAGES)),
        ("bank", subtotal("bank"), balance(BANK)),
        ("contracts", subtotal("contracts"), balance(CONTRACT_LIABILITY)),
        ("fixed asset cost", subtotal("fixed_assets"), balance(EQUIPMENT)),
    ]
    for label, actual, expected in reconciliations:
        if actual != expected:
            failures.append(
                f"{label} subledger does not reconcile: subledger {actual} != control {expected}"
            )
    accumulated = sum(
        (
            record.accumulated_depreciation or ZERO
            for record in pack.subledgers.get("fixed_assets", [])
        ),
        ZERO,
    )
    if -accumulated != balance(ACCUMULATED_DEPRECIATION):
        failures.append("accumulated depreciation subledger does not reconcile")

    for duplicate in sorted(_duplicates(document.id for document in pack.documents)):
        failures.append(f"duplicate document id {duplicate}")
    for document in pack.documents:
        if not document.id.startswith("syn-"):
            failures.append(f"document id {document.id!r} is not a synthetic syn- identifier")
        if document.party_id is not None and document.party_id not in parties:
            failures.append(f"{document.id}: unknown party {document.party_id!r}")
        if document.total != sum((line.amount for line in document.lines), ZERO):
            failures.append(f"{document.id}: document total does not cross-foot")
        for reference in document.source_refs:
            if reference not in known_refs:
                failures.append(f"{document.id}: unknown source reference {reference!r}")
        if document.supersedes is not None and document.supersedes not in document_ids:
            failures.append(f"{document.id}: supersedes unknown document {document.supersedes!r}")
        if document.duplicate_of is not None and document.duplicate_of not in document_ids:
            failures.append(
                f"{document.id}: duplicate_of unknown document {document.duplicate_of!r}"
            )

    anomaly_ids = [anomaly.id for anomaly in pack.anomalies]
    for duplicate in sorted(_duplicates(anomaly_ids)):
        failures.append(f"duplicate anomaly id {duplicate}")
    referenced_by_anomaly: set[str] = set()
    for anomaly in pack.anomalies:
        referenced_by_anomaly.update(anomaly.evidence_refs)
        if anomaly.kind not in ANOMALY_KINDS:
            failures.append(f"{anomaly.id}: unknown anomaly kind {anomaly.kind!r}")
        if not anomaly.determination:
            failures.append(f"{anomaly.id}: determination is required")
        if not anomaly.disposition:
            failures.append(f"{anomaly.id}: disposition is required")
        if not anomaly.precedence:
            failures.append(f"{anomaly.id}: precedence is required")
        if not anomaly.wrong_disposition:
            failures.append(f"{anomaly.id}: wrong disposition is required")
        if anomaly.authoritative_ref not in document_ids:
            failures.append(
                f"{anomaly.id}: unknown authoritative document {anomaly.authoritative_ref!r}"
            )
        if anomaly.authoritative_ref not in anomaly.evidence_refs:
            failures.append(f"{anomaly.id}: authoritative document is not in evidence refs")
        for reference in anomaly.evidence_refs:
            if reference not in document_ids:
                failures.append(f"{anomaly.id}: unknown evidence document {reference!r}")

    for document in pack.documents:
        if (
            document.status in CONFLICTING_DOCUMENT_STATUSES
            and document.id not in referenced_by_anomaly
        ):
            failures.append(
                f"{document.id}: conflicting status {document.status!r} has no registered anomaly"
            )
    return failures
