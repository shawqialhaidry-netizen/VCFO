import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    currency = Column(String(10), default="USD", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Subscription / trial
    # plan: 'trial' | 'active' | 'enterprise'
    # trial_ends_at: date trial expires; None = unlimited trial
    # IMPORTANT: all members of the same company inherit this subscription state.
    plan           = Column(String(20), nullable=False, default="trial")
    trial_ends_at  = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    memberships = relationship("Membership", back_populates="company", lazy="dynamic")

    def __repr__(self):
        return f"<Company id={self.id} name={self.name}>"
