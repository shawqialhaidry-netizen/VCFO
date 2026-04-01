"""
Group and GroupMembership — Phase 1 (organizational hierarchy).

Hierarchy: Group → Company → Branch

================================================================================
MEMBERSHIP RULE (single source of truth for group-level access)
================================================================================
**Company access** — unchanged: `memberships` table (user_id + company_id + role).
  A user sees a company only with an active row there.

**Group access** — **direct only** via `group_memberships` (user_id + group_id + role).
  - There is **no** automatic inheritance from company membership in Phase 1.
  - Future group APIs MUST require an active `GroupMembership` for the target group.
  - A user may hold company memberships without any group membership (typical today).

**Rationale:** Explicit grants are auditable and revocable; avoiding implicit
"see every group that contains my company" until product rules are defined.

Optional future extension (not implemented here): derived read access based on
company membership could be a **separate** policy layer on top of this model.
================================================================================
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base

# Same role vocabulary as company Membership (owner / analyst / viewer)
GROUP_ROLES = ("owner", "analyst", "viewer")


class Group(Base):
    __tablename__ = "groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    companies   = relationship("Company", back_populates="group")
    memberships = relationship("GroupMembership", back_populates="group", lazy="dynamic")

    def __repr__(self):
        return f"<Group id={self.id} name={self.name}>"


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_group_membership_user_group"),
    )

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id   = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    role       = Column(String(20), nullable=False, default="owner")
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user  = relationship("User", back_populates="group_memberships")
    group = relationship("Group", back_populates="memberships")

    def __repr__(self):
        return f"<GroupMembership user={self.user_id} group={self.group_id} role={self.role}>"
