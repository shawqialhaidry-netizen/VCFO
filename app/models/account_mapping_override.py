import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class AccountMappingOverride(Base):
    __tablename__ = "account_mapping_overrides"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "account_code",
            name="uq_account_mapping_overrides_company_account_code",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_code = Column(String(255), nullable=False)
    account_name_hint = Column(String(255), nullable=True)
    mapped_type = Column(String(50), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="account_mapping_overrides")

    def __repr__(self):
        return (
            f"<AccountMappingOverride company={self.company_id} "
            f"account_code={self.account_code} mapped_type={self.mapped_type}>"
        )
