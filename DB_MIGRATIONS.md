# VCFO — Database Migration & Production Setup Guide

## Quick Start (Development)

```bash
# 1. Copy .env.example → .env and fill in values
cp .env.example .env

# 2. Start the server (creates tables automatically)
uvicorn app.main:app --reload --port 8000

# 3. Apply schema migrations
python scripts/db_migrate.py up

# 4. Verify
python scripts/db_migrate.py status
```

---

## Migration Commands

```bash
python scripts/db_migrate.py status      # show applied / pending migrations
python scripts/db_migrate.py up          # apply all pending
python scripts/db_migrate.py up --dry-run  # preview without applying
python scripts/db_migrate.py history     # full history log
python scripts/db_migrate.py --db PATH status  # explicit DB file path
```

---

## Applied Migrations

| Version  | Description                           | Status   |
|----------|---------------------------------------|----------|
| 2026_001 | Add tb_type to tb_uploads             | Required |

### Adding a New Migration

1. Open `scripts/db_migrate.py`
2. Add a new entry at the **bottom** of `MIGRATIONS` list
3. Never edit or remove existing entries
4. Run `python scripts/db_migrate.py up`

```python
{
    "version":     "2026_002",
    "description": "Short description here",
    "sql": [
        "ALTER TABLE some_table ADD COLUMN new_col VARCHAR(50)",
    ],
},
```

---

## SQLite → PostgreSQL Migration

### Step 1 — Install PostgreSQL driver

```bash
pip install psycopg2-binary
```

### Step 2 — Update .env

```
DATABASE_URL=postgresql://vcfo_user:strongpassword@localhost:5432/vcfo_db
```

### Step 3 — Create PostgreSQL database

```sql
CREATE DATABASE vcfo_db;
CREATE USER vcfo_user WITH ENCRYPTED PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE vcfo_db TO vcfo_user;
```

### Step 4 — Run the app once to create tables

```bash
uvicorn app.main:app --port 8000
# startup will call init_db() → Base.metadata.create_all()
# All tables created including tb_type column (it's in the ORM model now)
```

### Step 5 — Apply migrations (no-op if column already in schema)

```bash
DATABASE_URL=postgresql://vcfo_user:strongpassword@localhost:5432/vcfo_db \
  python scripts/db_migrate.py up
```

> **Note:** `db_migrate.py` auto-detects PostgreSQL via `DATABASE_URL` env var.
> It uses `psycopg2` and `information_schema` for PostgreSQL compatibility.

### Step 6 — Migrate data (if you have existing SQLite data)

```bash
# Export from SQLite
sqlite3 data/vcfo.db .dump > backup.sql

# For production migration, use pgloader or a custom script.
# Contact your DBA for data migration assistance.
```

---

## Production Environment Variables

Create `C:\VCFO1\CFO\vcfo\.env` (Windows) or `/opt/vcfo/.env` (Linux):

```env
# ── Required ──────────────────────────────────────────────────────────────────
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=<strong-random-secret-here>

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@host:5432/vcfo_db
# OR for SQLite dev:
# DATABASE_URL=sqlite:///./data/vcfo.db

# ── Access control ────────────────────────────────────────────────────────────
ENFORCE_MEMBERSHIP=true

# ── CORS ──────────────────────────────────────────────────────────────────────
# CORS_ORIGINS=["https://app.yourdomain.com"]

# ── Production guard ──────────────────────────────────────────────────────────
# Prevents startup with insecure defaults:
PRODUCTION_MODE=true

# ── Optional ──────────────────────────────────────────────────────────────────
DEBUG=false
```

---

## Fresh Deployment Checklist

- [ ] `.env` file created with all required variables
- [ ] `JWT_SECRET_KEY` set to a strong random value
- [ ] `DATABASE_URL` points to production database
- [ ] `PRODUCTION_MODE=true` set in .env
- [ ] Server starts without `[SECURITY]` or `[SCHEMA]` warnings
- [ ] `python scripts/db_migrate.py status` shows all migrations applied
- [ ] `python scripts/bootstrap_admin.py` run to create first user
- [ ] Login works and returns a valid token
- [ ] Upload a trial balance file and confirm `status=ok`

---

## PostgreSQL Readiness Status

| Item | Status |
|------|--------|
| `connect_args` conditional (SQLite-only) | ✅ Done |
| `pool_pre_ping` for PG connection health | ✅ Done |
| `pool_size` / `max_overflow` for PG | ✅ Done |
| ORM models use standard SQL types | ✅ Done |
| `db_migrate.py` supports PostgreSQL | ✅ Done |
| Startup validates DB connectivity | ✅ Done |
| `PRODUCTION_MODE` guard | ✅ Done |
| Full Alembic auto-migration | ⚠️ Planned |
