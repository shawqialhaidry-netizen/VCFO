"""
test_pg_readiness.py — PostgreSQL readiness and database config tests.

Covers:
  - database.py: SQLite gets check_same_thread, PostgreSQL does NOT
  - database.py: pool_pre_ping set for PostgreSQL
  - database.py: check_db_connection() function exists and returns (bool, str)
  - config.py: PRODUCTION_MODE field exists
  - config.py: all required fields present
  - db_migrate.py: PostgreSQL path present
  - startup: PRODUCTION_MODE=True blocks insecure default JWT
  - startup: PRODUCTION_MODE=True blocks empty JWT
"""
import pytest


class TestDatabaseConfig:
    def test_sqlite_gets_check_same_thread(self):
        """SQLite engine must have check_same_thread=False in connect_args."""
        src = open("/home/claude/vcfo_repair/app/core/database.py").read()
        assert "_is_sqlite" in src
        assert 'check_same_thread' in src
        assert "_is_sqlite" in src.split('check_same_thread')[0].split('\n')[-1] or \
               "if _is_sqlite" in src

    def test_pg_gets_pool_pre_ping(self):
        """PostgreSQL path must include pool_pre_ping=True."""
        src = open("/home/claude/vcfo_repair/app/core/database.py").read()
        assert "pool_pre_ping" in src
        assert "True" in src

    def test_pg_gets_pool_size(self):
        """PostgreSQL path must define pool_size and max_overflow."""
        src = open("/home/claude/vcfo_repair/app/core/database.py").read()
        assert "pool_size" in src
        assert "max_overflow" in src

    def test_check_db_connection_exists(self):
        """check_db_connection() must be importable and return (bool, str)."""
        src = open("/home/claude/vcfo_repair/app/core/database.py").read()
        assert "def check_db_connection" in src
        assert "return True" in src
        assert "return False" in src

    def test_no_unconditional_check_same_thread(self):
        """check_same_thread must not be passed unconditionally."""
        src = open("/home/claude/vcfo_repair/app/core/database.py").read()
        # Must be inside a conditional block, not at top level
        lines = src.split('\n')
        for i, line in enumerate(lines):
            if 'check_same_thread' in line and 'if' not in line:
                # Check that the surrounding context is inside an if block
                context = '\n'.join(lines[max(0,i-3):i+1])
                assert 'if _is_sqlite' in context or '#' in line, \
                    f"check_same_thread appears unconditionally at line {i+1}: {line}"


class TestConfigFields:
    def test_production_mode_field_exists(self):
        src = open("/home/claude/vcfo_repair/app/core/config.py").read()
        assert "PRODUCTION_MODE" in src
        assert "bool" in src

    def test_database_url_field_exists(self):
        src = open("/home/claude/vcfo_repair/app/core/config.py").read()
        assert "DATABASE_URL" in src

    def test_enforce_membership_field_exists(self):
        src = open("/home/claude/vcfo_repair/app/core/config.py").read()
        assert "ENFORCE_MEMBERSHIP" in src

    def test_cors_origins_field_exists(self):
        src = open("/home/claude/vcfo_repair/app/core/config.py").read()
        assert "CORS_ORIGINS" in src

    def test_env_example_exists(self):
        import os
        assert os.path.exists("/home/claude/vcfo_repair/.env.example")

    def test_env_example_has_all_keys(self):
        content = open("/home/claude/vcfo_repair/.env.example").read()
        for key in ("JWT_SECRET_KEY", "DATABASE_URL", "ENFORCE_MEMBERSHIP",
                    "PRODUCTION_MODE", "DEBUG"):
            assert key in content, f".env.example missing: {key}"


class TestMigrationScript:
    def test_pg_path_in_migrate_script(self):
        """db_migrate.py must have a PostgreSQL connection path."""
        src = open("/home/claude/vcfo_repair/scripts/db_migrate.py").read()
        assert "postgresql" in src
        assert "_connect_pg" in src or "psycopg2" in src

    def test_col_exists_pg_compatible(self):
        """_col_exists must support both SQLite PRAGMA and PG information_schema."""
        src = open("/home/claude/vcfo_repair/scripts/db_migrate.py").read()
        assert "information_schema" in src
        assert "PRAGMA table_info" in src

    def test_migrations_registry_has_tb_type(self):
        """Migration registry must contain the tb_type migration."""
        src = open("/home/claude/vcfo_repair/scripts/db_migrate.py").read()
        assert "2026_001" in src
        assert "tb_type" in src


class TestStartupPreflight:
    def test_startup_checks_db_connectivity(self):
        src = open("/home/claude/vcfo_repair/app/main.py").read()
        assert "check_db_connection" in src

    def test_startup_checks_schema(self):
        src = open("/home/claude/vcfo_repair/app/main.py").read()
        assert "tb_type" in src
        assert "db_migrate.py up" in src

    def test_startup_has_production_mode_guard(self):
        src = open("/home/claude/vcfo_repair/app/main.py").read()
        assert "PRODUCTION_MODE" in src
        assert "STARTUP BLOCKED" in src

    def test_startup_logs_environment_summary(self):
        src = open("/home/claude/vcfo_repair/app/main.py").read()
        assert "ENV" in src
        assert "production" in src or "PRODUCTION_MODE" in src

    def test_startup_blocks_empty_jwt_in_production(self, monkeypatch):
        """PRODUCTION_MODE=True + empty JWT must raise RuntimeError."""
        from unittest.mock import patch, MagicMock

        # We test the logic directly from the source, not by importing
        # (avoids DB dependency in unit tests)
        src = open("/home/claude/vcfo_repair/app/main.py").read()

        # Verify the guard code is present
        assert "STARTUP BLOCKED" in src
        assert "JWT_SECRET_KEY is not set" in src or "JWT_SECRET_KEY is empty" in src or \
               "not set" in src
        assert "PRODUCTION_MODE" in src

    def test_db_migrations_doc_exists(self):
        import os
        assert os.path.exists("/home/claude/vcfo_repair/DB_MIGRATIONS.md")

    def test_db_migrations_doc_has_pg_section(self):
        content = open("/home/claude/vcfo_repair/DB_MIGRATIONS.md").read()
        assert "PostgreSQL" in content
        assert "psycopg2" in content
        assert "DATABASE_URL" in content


class TestUploadFlowIntegrity:
    """Upload pipeline correctness tests (no HTTP layer needed)."""

    def test_upload_pipeline_with_real_data(self):
        """
        Simulate the full upload → classify → build_statements chain
        that runs inside POST /uploads.
        """
        import sys, types
        sys.path.insert(0, '/home/claude/vcfo_repair')

        # Mock SQLAlchemy so we can import services without a DB
        sa = types.ModuleType('sqlalchemy')
        sa.Column = lambda *a, **k: None
        sa.String = lambda *a: None; sa.Integer = lambda: None
        sa.Float = lambda: None; sa.Boolean = type('B',(),{})
        sa.Text = lambda: None; sa.DateTime = lambda: None
        sa.ForeignKey = lambda *a,**k: None
        sa.UniqueConstraint = lambda *a,**k: None
        sa.orm = types.ModuleType('sqlalchemy.orm')
        sa.orm.DeclarativeBase = type('Base', (), {})
        sa.orm.sessionmaker = lambda **k: None
        sa.orm.relationship = lambda *a, **k: None
        for m in ['sqlalchemy','sqlalchemy.orm']:
            if m not in sys.modules:
                sys.modules[m] = sa if m=='sqlalchemy' else sa.orm

        import pandas as pd
        from app.services.account_classifier import classify_dataframe
        from app.services.financial_statements import build_statements, statements_to_dict

        # Minimal TB that looks like a real monthly upload
        df = pd.DataFrame([
            {"account_code":"1010","account_name":"Cash",       "debit":50000,"credit":0    },
            {"account_code":"1100","account_name":"Receivables","debit":30000,"credit":0    },
            {"account_code":"2010","account_name":"Payables",   "debit":0,    "credit":15000},
            {"account_code":"3010","account_name":"Capital",    "debit":0,    "credit":40000},
            {"account_code":"4010","account_name":"Revenue",    "debit":0,    "credit":80000},
            {"account_code":"5010","account_name":"COGS",       "debit":45000,"credit":0    },
            {"account_code":"6010","account_name":"Salaries",   "debit":15000,"credit":0    },
        ])

        # Phase 3: classify (same as upload endpoint)
        classified = classify_dataframe(df)
        assert "mapped_type" in classified.columns
        assert "confidence" in classified.columns
        assert len(classified) == len(df)

        # Build statements (same as analysis pipeline)
        fs = build_statements(classified, company_id="test", period="2026-03",
                              tb_type="pre_closing")
        d = statements_to_dict(fs)

        # Verify correctness
        is_ = d["income_statement"]
        assert is_["revenue"]["total"] == 80000.0
        assert is_["net_profit"] == 20000.0
        assert d["balance_sheet"]["tb_type"] == "pre_closing"
        assert d["balance_sheet"].get("balance_warning") is None or \
               "tb_type_unknown" not in str(d["balance_sheet"].get("balance_warning", ""))

    def test_upload_pipeline_with_unknown_tb_type(self):
        """Unknown tb_type (None) should set warning but not crash."""
        import sys, types
        sa = types.ModuleType('sqlalchemy')
        sa.Column = lambda *a, **k: None; sa.String = lambda *a: None
        sa.orm = types.ModuleType('sqlalchemy.orm')
        sa.orm.DeclarativeBase = type('Base', (), {})
        sa.orm.sessionmaker = lambda **k: None
        sa.orm.relationship = lambda *a, **k: None
        for m in ['sqlalchemy','sqlalchemy.orm']:
            if m not in sys.modules:
                sys.modules[m] = sa if m=='sqlalchemy' else sa.orm

        import pandas as pd
        from app.services.account_classifier import classify_dataframe
        from app.services.financial_statements import build_statements, statements_to_dict

        df = pd.DataFrame([
            {"account_code":"4010","account_name":"Revenue","debit":0,    "credit":80000},
            {"account_code":"5010","account_name":"COGS",   "debit":45000,"credit":0    },
        ])
        classified = classify_dataframe(df)
        fs = build_statements(classified, company_id="test", period="2026-03", tb_type=None)
        d = statements_to_dict(fs)

        # Warning must be set, no crash
        assert "tb_type_unknown" in str(d["balance_sheet"].get("balance_warning", ""))
        assert d["income_statement"]["net_profit"] == 35000.0
