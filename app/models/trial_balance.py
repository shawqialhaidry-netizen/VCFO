import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.core.database import Base


class TrialBalanceUpload(Base):
    __tablename__ = "tb_uploads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    raw_path = Column(String(512), nullable=False)       # path to saved raw file
    normalized_path = Column(String(512), nullable=True) # path to normalized CSV
    period = Column(String(10), nullable=True)           # e.g. "2026-01"
    format_detected = Column(String(20), nullable=True)  # "wide" | "long" | "standard"
    record_count = Column(Integer, nullable=True)
    total_debit = Column(Float, nullable=True)
    total_credit = Column(Float, nullable=True)
    is_balanced = Column(String(5), nullable=True)       # "true" | "false" | "warn"
    status = Column(String(20), default="pending")       # pending | ok | error
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # FIX-S0: tb_type added to ORM (was only in raw SQL migration).
    # NULL = unknown (conservative — equity injection disabled).
    # "pre_closing"  = NP injected into equity.
    # "post_closing" = NP already in equity, no injection.
    tb_type = Column(String(20), nullable=True)
    # branch_id: NULL = company-level upload, value = branch-level upload
    branch_id = Column(String(36), nullable=True, index=True)

    def __repr__(self):
        return f"<TBUpload id={self.id} company={self.company_id} period={self.period}>"
