"""
Tests for app.services.scope_resolver (Phase 2 financial scope).
"""
import uuid

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.branch import Branch
from app.models.company import Company
from app.models.group import Group, GroupMembership
from app.models.membership import Membership
from app.models.user import User
from app.services.scope_resolver import ResolvedScope, resolve_financial_scope


def _uid() -> str:
    return str(uuid.uuid4())


def _user(db) -> User:
    u = User(
        id=_uid(),
        email=f"u{_uid()}@test.local",
        password_hash=hash_password("x"),
        is_active=True,
        is_superuser=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _group(db, *, active: bool = True) -> Group:
    g = Group(
        id=_uid(),
        name="G",
        is_active=active,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def _group_member(db, user: User, group: Group, *, active: bool = True) -> None:
    db.add(
        GroupMembership(
            id=_uid(),
            user_id=user.id,
            group_id=group.id,
            role="owner",
            is_active=active,
        )
    )
    db.commit()


def _company(db, *, group_id=None, active: bool = True) -> Company:
    c = Company(
        id=_uid(),
        group_id=group_id,
        name="Co",
        currency="USD",
        is_active=active,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _membership(db, user: User, company: Company) -> None:
    db.add(
        Membership(
            id=_uid(),
            user_id=user.id,
            company_id=company.id,
            role="owner",
            is_active=True,
        )
    )
    db.commit()


def _branch(db, company: Company) -> Branch:
    b = Branch(
        id=_uid(),
        company_id=company.id,
        name="Br",
        is_active=True,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


class TestResolveGroup:
    def test_empty_group_returns_empty_company_ids(self, db_session):
        user = _user(db_session)
        g = _group(db_session)
        _group_member(db_session, user, g)
        rs = resolve_financial_scope(db_session, user, "group", g.id)
        assert rs == ResolvedScope(
            scope_type="group",
            scope_id=g.id,
            group_id=g.id,
            company_ids=(),
            branch_id=None,
        )

    def test_excludes_inactive_companies(self, db_session):
        user = _user(db_session)
        g = _group(db_session)
        _group_member(db_session, user, g)
        ca = _company(db_session, group_id=g.id, active=True)
        _company(db_session, group_id=g.id, active=False)
        rs = resolve_financial_scope(db_session, user, "group", g.id)
        assert rs.company_ids == (ca.id,)

    def test_company_ids_sorted(self, db_session):
        user = _user(db_session)
        g = _group(db_session)
        _group_member(db_session, user, g)
        # Create with ids that sort non-insertion order
        low, high = sorted([_uid(), _uid()])
        c_hi = Company(
            id=high,
            group_id=g.id,
            name="Hi",
            currency="USD",
            is_active=True,
        )
        c_lo = Company(
            id=low,
            group_id=g.id,
            name="Lo",
            currency="USD",
            is_active=True,
        )
        db_session.add_all([c_hi, c_lo])
        db_session.commit()
        rs = resolve_financial_scope(db_session, user, "group", g.id)
        assert rs.company_ids == (low, high)

    def test_missing_group_404(self, db_session):
        user = _user(db_session)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "group", _uid())
        assert ei.value.status_code == 404
        assert ei.value.detail == "Group not found"

    def test_inactive_group_404(self, db_session):
        user = _user(db_session)
        g = _group(db_session, active=False)
        _group_member(db_session, user, g)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "group", g.id)
        assert ei.value.status_code == 404

    def test_no_group_membership_403(self, db_session):
        user = _user(db_session)
        g = _group(db_session)
        _company(db_session, group_id=g.id)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "group", g.id)
        assert ei.value.status_code == 403

    def test_company_member_without_group_membership_not_implicit(self, db_session):
        """Direct group_memberships only — company membership does not grant group scope."""
        user = _user(db_session)
        g = _group(db_session)
        c = _company(db_session, group_id=g.id)
        _membership(db_session, user, c)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "group", g.id)
        assert ei.value.status_code == 403


class TestResolveCompany:
    def test_ok(self, db_session):
        user = _user(db_session)
        c = _company(db_session, group_id=None)
        _membership(db_session, user, c)
        rs = resolve_financial_scope(db_session, user, "company", c.id)
        assert rs.scope_type == "company"
        assert rs.company_ids == (c.id,)
        assert rs.branch_id is None
        assert rs.group_id is None

    def test_group_id_preserved_when_company_in_group(self, db_session):
        user = _user(db_session)
        g = _group(db_session)
        c = _company(db_session, group_id=g.id)
        _membership(db_session, user, c)
        rs = resolve_financial_scope(db_session, user, "company", c.id)
        assert rs.group_id == g.id

    def test_inactive_company_404(self, db_session):
        user = _user(db_session)
        c = _company(db_session, active=False)
        _membership(db_session, user, c)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "company", c.id)
        assert ei.value.status_code == 404

    def test_no_membership_403(self, db_session):
        user = _user(db_session)
        c = _company(db_session)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "company", c.id)
        assert ei.value.status_code == 403


class TestResolveBranch:
    def test_ok(self, db_session):
        user = _user(db_session)
        c = _company(db_session)
        _membership(db_session, user, c)
        b = _branch(db_session, c)
        rs = resolve_financial_scope(db_session, user, "branch", b.id)
        assert rs.scope_type == "branch"
        assert rs.branch_id == b.id
        assert rs.company_ids == (c.id,)

    def test_missing_branch_404(self, db_session):
        user = _user(db_session)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "branch", _uid())
        assert ei.value.status_code == 404

    def test_inactive_parent_company_404(self, db_session):
        user = _user(db_session)
        c = _company(db_session, active=False)
        _membership(db_session, user, c)
        b = _branch(db_session, c)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "branch", b.id)
        assert ei.value.status_code == 404


class TestValidation:
    def test_invalid_scope_type_422(self, db_session):
        user = _user(db_session)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "portfolio", _uid())
        assert ei.value.status_code == 422

    def test_empty_scope_id_422(self, db_session):
        user = _user(db_session)
        with pytest.raises(HTTPException) as ei:
            resolve_financial_scope(db_session, user, "company", "  ")
        assert ei.value.status_code == 422
