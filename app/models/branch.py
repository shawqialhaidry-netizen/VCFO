"""
models/branch.py — Phase 7.6
Branch model for multi-branch company structure.
Uses classic Column() style for Python 3.14 compatibility.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text

from app.core.database import Base


class Branch(Base):
    __tablename__ = "branches"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), nullable=False, index=True)
    code       = Column(String(50),  nullable=True)
    name       = Column(String(255), nullable=False)
    name_ar    = Column(String(255), nullable=True)
    manager_name = Column(String(255), nullable=True)
    city       = Column(String(100), nullable=True)
    country    = Column(String(100), nullable=True)
    currency   = Column(String(10),  default="USD", nullable=False)
    is_active  = Column(Boolean,     default=True,  nullable=False)
    created_at = Column(DateTime,    default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Branch id={self.id} name={self.name} company={self.company_id}>"


class BranchFinancial(Base):
    """
    Pre-aggregated monthly financial summary per branch.
    Populated when a branch-level TB upload is processed.
    """
    __tablename__ = "branch_financials"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    branch_id  = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), nullable=False, index=True)
    period     = Column(String(10), nullable=False)  # YYYY-MM

    revenue    = Column(Float, nullable=True)
    cogs       = Column(Float, nullable=True)
    gross_profit = Column(Float, nullable=True)
    expenses   = Column(Float, nullable=True)
    net_profit = Column(Float, nullable=True)
    total_assets = Column(Float, nullable=True)

    upload_id  = Column(String(36), nullable=True)   # FK → tb_uploads.id
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<BranchFinancial branch={self.branch_id} period={self.period}>"
