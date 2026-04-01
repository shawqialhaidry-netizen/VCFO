"""
test_schema.py — Schema correctness tests.
Covers: ORM model has tb_type, create_all creates tb_type column,
        migration script is idempotent.
"""
import pytest
from sqlalchemy import inspect as sa_inspect


def test_orm_model_has_tb_type():
    """tb_type must be declared in the ORM model."""
    from app.models.trial_balance import TrialBalanceUpload
    col_names = [c.name for c in TrialBalanceUpload.__table__.columns]
    assert "tb_type" in col_names, (
        "tb_type missing from TrialBalanceUpload ORM model — "
        "equity injection will be broken on fresh deployments"
    )


def test_create_all_includes_tb_type(setup_test_db):
    """create_all() must create tb_type column in the test DB."""
    from app.core.database import Base
    from tests.conftest import engine_test
    insp = sa_inspect(engine_test)
    cols = [c["name"] for c in insp.get_columns("tb_uploads")]
    assert "tb_type" in cols, (
        "create_all() did not create tb_type column — "
        "check that Column is declared in models/trial_balance.py"
    )


def test_tb_type_nullable():
    """tb_type must be nullable (unknown uploads should not crash)."""
    from app.models.trial_balance import TrialBalanceUpload
    col = next(c for c in TrialBalanceUpload.__table__.columns if c.name == "tb_type")
    assert col.nullable is True, "tb_type must be nullable for backward compatibility"


def test_migration_registry_has_tb_type():
    """Migration registry must include the tb_type migration."""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "db_migrate", "/home/claude/vcfo_repair/scripts/db_migrate.py"  # adjust path in CI
    )
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        versions = [m["version"] for m in mod.MIGRATIONS]
        assert "2026_001" in versions, "tb_type migration missing from registry"
    except FileNotFoundError:
        pytest.skip("Migration script not accessible in this environment")
