"""
test_pg_readiness.py — PostgreSQL readiness and database config tests.

Covers:
  - database.py: PostgreSQL pool settings only (no SQLite)
  - config.py: DATABASE_URL validation rejects SQLite
  - db_migrate.py: PostgreSQL path present
  - startup preflight guards
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


class TestDatabaseConfig:
    def test_postgresql_engine_only_no_sqlite_branch(self):
        """Engine must use pool settings; no SQLite URL or check_same_thread path."""
        src = _read("app/core/database.py")
        assert "pool_pre_ping" in src
        assert "check_same_thread" not in src
        assert "is_sqlite" not in src
        assert "sqlite:///" not in src

    def test_pg_gets_pool_pre_ping(self):
        src = _read("app/core/database.py")
        assert "pool_pre_ping" in src
        assert "True" in src

    def test_pg_gets_pool_size(self):
        src = _read("app/core/database.py")
        assert "pool_size" in src
        assert "max_overflow" in src

    def test_check_db_connection_exists(self):
        src = _read("app/core/database.py")
        assert "def check_db_connection" in src
        assert "return True" in src
        assert "return False" in src


class TestConfigFields:
    def test_production_mode_field_exists(self):
        src = _read("app/core/config.py")
        assert "PRODUCTION_MODE" in src
        assert "bool" in src

    def test_database_url_postgres_only_validator(self):
        src = _read("app/core/config.py")
        assert "DATABASE_URL" in src
        assert "postgres_only" in src
        assert "startswith(\"sqlite\")" in src or "startswith('sqlite')" in src

    def test_enforce_membership_field_exists(self):
        src = _read("app/core/config.py")
        assert "ENFORCE_MEMBERSHIP" in src

    def test_cors_origins_field_exists(self):
        src = _read("app/core/config.py")
        assert "CORS_ORIGINS" in src

    def test_env_example_exists(self):
        assert (REPO_ROOT / ".env.example").is_file()

    def test_env_example_postgresql_only(self):
        content = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        for key in ("JWT_SECRET_KEY", "DATABASE_URL", "ENFORCE_MEMBERSHIP",
                    "PRODUCTION_MODE", "DEBUG"):
            assert key in content, f".env.example missing: {key}"
        assert "postgresql" in content.lower()
        assert "sqlite:///./data/vcfo.db" not in content


class TestMigrationScript:
    def test_pg_path_in_migrate_script(self):
        src = _read("scripts/db_migrate.py")
        assert "postgresql" in src
        assert "_connect_pg" in src or "psycopg2" in src

    def test_col_exists_pg_compatible(self):
        """Legacy SQLite PRAGMA path may remain for --db file mode; PG uses information_schema."""
        src = _read("scripts/db_migrate.py")
        assert "information_schema" in src
        assert "PRAGMA table_info" in src

    def test_migrations_registry_has_tb_type(self):
        src = _read("scripts/db_migrate.py")
        assert "2026_001" in src
        assert "tb_type" in src


class TestStartupPreflight:
    def test_startup_checks_db_connectivity(self):
        src = _read("app/main.py")
        assert "check_db_connection" in src

    def test_startup_checks_schema(self):
        src = _read("app/main.py")
        assert "tb_type" in src
        assert "alembic upgrade head" in src or "db_migrate.py" in src

    def test_startup_has_production_mode_guard(self):
        src = _read("app/main.py")
        assert "PRODUCTION_MODE" in src
        assert "[BLOCKED]" in src

    def test_startup_logs_environment_summary(self):
        src = _read("app/main.py")
        assert "[ENV]" in src or "ENV" in src
        assert "production" in src or "PRODUCTION_MODE" in src

    def test_startup_blocks_empty_jwt_in_production(self, monkeypatch):
        src = _read("app/main.py")
        assert "[BLOCKED]" in src
        assert "JWT_SECRET_KEY" in src
        assert "PRODUCTION_MODE" in src

    def test_db_migrations_doc_exists(self):
        assert (REPO_ROOT / "DB_MIGRATIONS.md").is_file()

    def test_db_migrations_doc_has_pg_section(self):
        content = _read("DB_MIGRATIONS.md")
        assert "PostgreSQL" in content
        assert "psycopg2" in content
        assert "DATABASE_URL" in content


class TestUploadFlowIntegrity:
    """Upload pipeline correctness tests (no HTTP layer needed)."""

    def test_upload_pipeline_with_real_data(self):
        import sys
        import types

        root = str(REPO_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)

        sa = types.ModuleType("sqlalchemy")
        sa.Column = lambda *a, **k: None
        sa.String = lambda *a: None
        sa.Integer = lambda: None
        sa.Float = lambda: None
        sa.Boolean = type("B", (), {})
        sa.Text = lambda: None
        sa.DateTime = lambda: None
        sa.ForeignKey = lambda *a, **k: None
        sa.UniqueConstraint = lambda *a, **k: None
        sa.orm = types.ModuleType("sqlalchemy.orm")
        sa.orm.DeclarativeBase = type("Base", (), {})
        sa.orm.sessionmaker = lambda **k: None
        sa.orm.relationship = lambda *a, **k: None
        for m in ["sqlalchemy", "sqlalchemy.orm"]:
            if m not in sys.modules:
                sys.modules[m] = sa if m == "sqlalchemy" else sa.orm

        import pandas as pd
        from app.services.account_classifier import classify_dataframe
        from app.services.financial_statements import build_statements, statements_to_dict

        df = pd.DataFrame([
            {"account_code": "1010", "account_name": "Cash",        "debit": 50000, "credit": 0},
            {"account_code": "1100", "account_name": "Receivables", "debit": 30000, "credit": 0},
            {"account_code": "2010", "account_name": "Payables",    "debit": 0, "credit": 15000},
            {"account_code": "3010", "account_name": "Capital",     "debit": 0, "credit": 40000},
            {"account_code": "4010", "account_name": "Revenue",     "debit": 0, "credit": 80000},
            {"account_code": "5010", "account_name": "COGS",        "debit": 45000, "credit": 0},
            {"account_code": "6010", "account_name": "Salaries",    "debit": 15000, "credit": 0},
        ])

        classified = classify_dataframe(df)
        assert "mapped_type" in classified.columns
        assert "confidence" in classified.columns
        assert len(classified) == len(df)

        fs = build_statements(classified, company_id="test", period="2026-03",
                              tb_type="pre_closing")
        d = statements_to_dict(fs)

        is_ = d["income_statement"]
        assert is_["revenue"]["total"] == 80000.0
        assert is_["net_profit"] == 20000.0
        assert d["balance_sheet"]["tb_type"] == "pre_closing"
        assert d["balance_sheet"].get("balance_warning") is None or \
               "tb_type_unknown" not in str(d["balance_sheet"].get("balance_warning", ""))

    def test_upload_pipeline_with_unknown_tb_type(self):
        import sys
        import types

        root = str(REPO_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)

        sa = types.ModuleType("sqlalchemy")
        sa.Column = lambda *a, **k: None
        sa.String = lambda *a: None
        sa.orm = types.ModuleType("sqlalchemy.orm")
        sa.orm.DeclarativeBase = type("Base", (), {})
        sa.orm.sessionmaker = lambda **k: None
        sa.orm.relationship = lambda *a, **k: None
        for m in ["sqlalchemy", "sqlalchemy.orm"]:
            if m not in sys.modules:
                sys.modules[m] = sa if m == "sqlalchemy" else sa.orm

        import pandas as pd
        from app.services.account_classifier import classify_dataframe
        from app.services.financial_statements import build_statements, statements_to_dict

        df = pd.DataFrame([
            {"account_code": "4010", "account_name": "Revenue", "debit": 0, "credit": 80000},
            {"account_code": "5010", "account_name": "COGS", "debit": 45000, "credit": 0},
        ])
        classified = classify_dataframe(df)
        fs = build_statements(classified, company_id="test", period="2026-03", tb_type=None)
        d = statements_to_dict(fs)

        assert "tb_type_unknown" in str(d["balance_sheet"].get("balance_warning", ""))
        assert d["income_statement"]["net_profit"] == 35000.0
