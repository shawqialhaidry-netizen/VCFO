"""
account_rules.py — Phase 3 (Fixed)
Pure data layer: classification rules.

FIX: Code ranges 8xxx and 9xxx are now mapped to TAX and OTHER respectively,
     but the classifier gives NAME keywords priority over these "weak" code
     prefixes when the name strongly indicates a different type.
"""

# ── Type constants ─────────────────────────────────────────────────────────────
REVENUE     = "revenue"
COGS        = "cogs"
EXPENSES    = "expenses"
ASSETS      = "assets"
LIABILITIES = "liabilities"
EQUITY      = "equity"
TAX         = "tax"
OTHER       = "other"

ALL_TYPES = {REVENUE, COGS, EXPENSES, ASSETS, LIABILITIES, EQUITY, TAX, OTHER}

# ── Confidence levels ──────────────────────────────────────────────────────────
CONF_CODE_AND_NAME = 0.95   # code prefix AND name keyword agree
CONF_CODE_ONLY     = 0.75   # code prefix only (no name hint)
CONF_NAME_STRONG   = 0.65   # strong name keyword, no code match
CONF_NAME_WEAK     = 0.40   # weak name keyword
CONF_UNKNOWN       = 0.0    # nothing matched

# ── "Weak" code prefixes ───────────────────────────────────────────────────────
# When a code prefix maps to one of these types, the name keyword is allowed
# to OVERRIDE it (rather than causing a conflict that the code always wins).
# This handles 8xxx accounts (tax, intercompany, etc.) where the code scheme
# varies by company but the account name is authoritative.
WEAK_CODE_TYPES = {OTHER}

# ── Code-prefix rules ──────────────────────────────────────────────────────────
# More specific prefixes (longer) must come first — sort is done after.
CODE_PREFIX_RULES: list[tuple[str, str]] = [
    # Assets (1xxx)
    ("10", ASSETS), ("11", ASSETS), ("12", ASSETS),
    ("13", ASSETS), ("14", ASSETS), ("15", ASSETS),
    ("16", ASSETS), ("17", ASSETS), ("18", ASSETS),
    ("19", ASSETS),
    ("1",  ASSETS),

    # Liabilities (2xxx)
    ("20", LIABILITIES), ("21", LIABILITIES), ("22", LIABILITIES),
    ("23", LIABILITIES), ("24", LIABILITIES), ("25", LIABILITIES),
    ("26", LIABILITIES), ("27", LIABILITIES), ("28", LIABILITIES),
    ("29", LIABILITIES),
    ("2",  LIABILITIES),

    # Equity (3xxx)
    ("30", EQUITY), ("31", EQUITY), ("32", EQUITY),
    ("33", EQUITY), ("34", EQUITY), ("35", EQUITY),
    ("3",  EQUITY),

    # Revenue (4xxx)
    ("40", REVENUE), ("41", REVENUE), ("42", REVENUE),
    ("43", REVENUE), ("44", REVENUE),
    ("4",  REVENUE),

    # COGS (5xxx)
    ("50", COGS), ("51", COGS), ("52", COGS),
    ("53", COGS), ("54", COGS),
    ("5",  COGS),

    # Expenses (6xxx)
    ("60", EXPENSES), ("61", EXPENSES), ("62", EXPENSES),
    ("63", EXPENSES), ("64", EXPENSES), ("65", EXPENSES),
    ("66", EXPENSES), ("67", EXPENSES), ("68", EXPENSES),
    ("69", EXPENSES),
    ("6",  EXPENSES),

    # Tax (7xxx)
    ("70", TAX), ("71", TAX), ("72", TAX),
    ("7",  TAX),

    # 8xxx → treated as OTHER (weak) — name keywords can override
    # Common uses: income tax (8010), intercompany, suspense accounts
    ("8",  OTHER),

    # 9xxx → OTHER (weak)
    ("9",  OTHER),
]

# Sort longest prefix first so "11" beats "1"
CODE_PREFIX_RULES.sort(key=lambda x: len(x[0]), reverse=True)


# ── Name keyword rules ─────────────────────────────────────────────────────────
# (keyword_lowercase, mapped_type, is_strong: bool)
NAME_KEYWORD_RULES: list[tuple[str, str, bool]] = [

    # ── Tax-specific terms FIRST to avoid "income" matching revenue ───────────
    ("income tax",    TAX, True),
    ("corporate tax", TAX, True),
    ("deferred tax",  TAX, True),
    ("ضريبة الدخل",   TAX, True),
    ("ضريبة دخل",     TAX, True),

    # ── Revenue ──────────────────────────────────────────────────────────────
    ("revenue",    REVENUE, True),
    ("sales",      REVENUE, True),
    ("income",     REVENUE, True),
    ("turnover",   REVENUE, True),
    ("proceeds",   REVENUE, True),
    ("ايراد",      REVENUE, True),
    ("إيراد",      REVENUE, True),
    ("مبيعات",     REVENUE, True),
    ("دخل",        REVENUE, True),
    ("hasılat",    REVENUE, True),
    ("gelir",      REVENUE, True),
    ("satış",      REVENUE, True),

    # ── COGS ─────────────────────────────────────────────────────────────────
    ("cost of goods", COGS, True),
    ("cost of sales", COGS, True),
    ("cogs",          COGS, True),
    ("direct cost",   COGS, True),
    ("تكلفة البضاعة", COGS, True),
    ("تكلفة المبيعات",COGS, True),
    ("تكلفة",         COGS, True),
    ("بضاعة",         COGS, False),
    ("satılan",       COGS, True),
    ("smmm",          COGS, True),

    # ── Expenses ─────────────────────────────────────────────────────────────
    ("expense",      EXPENSES, True),
    ("expenses",     EXPENSES, True),
    ("depreciation", EXPENSES, True),
    ("amortization", EXPENSES, True),
    ("salary",       EXPENSES, True),
    ("salaries",     EXPENSES, True),
    ("wages",        EXPENSES, True),
    ("rent",         EXPENSES, True),
    ("utilities",    EXPENSES, True),
    ("insurance",    EXPENSES, True),
    ("marketing",    EXPENSES, False),
    ("مصروف",        EXPENSES, True),
    ("مصاريف",       EXPENSES, True),
    ("رواتب",        EXPENSES, True),
    ("أجور",         EXPENSES, True),
    ("إيجار",        EXPENSES, True),
    ("استهلاك",      EXPENSES, True),
    ("gider",        EXPENSES, True),
    ("masraf",       EXPENSES, True),
    ("maaş",         EXPENSES, True),
    ("kira",         EXPENSES, True),

    # ── Assets ───────────────────────────────────────────────────────────────
    ("cash",       ASSETS, True),
    ("bank",       ASSETS, True),
    ("receivable", ASSETS, True),
    ("inventory",  ASSETS, True),
    ("prepaid",    ASSETS, True),
    ("fixed asset",ASSETS, True),
    ("equipment",  ASSETS, True),
    ("property",   ASSETS, False),
    ("investment", ASSETS, False),
    ("صندوق",      ASSETS, True),
    ("بنك",        ASSETS, True),
    ("نقدية",      ASSETS, True),
    ("مدينون",     ASSETS, True),
    ("مخزون",      ASSETS, True),
    ("أصول",       ASSETS, True),
    ("عقارات",     ASSETS, False),
    ("kasa",       ASSETS, True),
    ("nakit",      ASSETS, True),
    ("banka",      ASSETS, True),
    ("alacak",     ASSETS, True),
    ("stok",       ASSETS, True),

    # ── Liabilities ──────────────────────────────────────────────────────────
    ("payable",    LIABILITIES, True),
    ("loan",       LIABILITIES, True),
    ("debt",       LIABILITIES, True),
    ("borrowing",  LIABILITIES, True),
    ("accrued",    LIABILITIES, False),
    ("overdraft",  LIABILITIES, True),
    ("mortgage",   LIABILITIES, True),
    ("التزامات",   LIABILITIES, True),
    ("دائنون",     LIABILITIES, True),
    ("قرض",        LIABILITIES, True),
    ("ديون",       LIABILITIES, True),
    ("borç",       LIABILITIES, True),
    ("kredi",      LIABILITIES, False),

    # ── Equity ───────────────────────────────────────────────────────────────
    ("equity",         EQUITY, True),
    ("capital",        EQUITY, True),
    ("retained",       EQUITY, True),
    ("reserve",        EQUITY, False),
    ("dividend",       EQUITY, False),
    ("حقوق الملكية",  EQUITY, True),
    ("رأس المال",      EQUITY, True),
    ("أرباح محتجزة",  EQUITY, True),
    ("احتياطي",        EQUITY, False),
    ("özkaynak",       EQUITY, True),
    ("sermaye",        EQUITY, True),

    # ── Tax ──────────────────────────────────────────────────────────────────
    ("tax",       TAX, True),
    ("vat",       TAX, True),
    ("zakat",     TAX, True),
    ("withholding",TAX, False),
    ("ضريبة",     TAX, True),
    ("زكاة",      TAX, True),
    ("kdv",       TAX, True),
    ("vergi",     TAX, True),
]
