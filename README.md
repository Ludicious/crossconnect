# CrossConnect

Infrastructure cross-connect management — replaces architect→tech Excel-by-email workflows.

## Stack

Python 3.11+, FastAPI, Jinja2, HTMX, Alpine.js, Bootstrap 5,
SQLAlchemy 2 + Alembic, SQLite (dev) / Postgres (prod), openpyxl.

## Quick start (WSL Debian / Linux)

```bash
# 1. Clone and enter the project
cd crossconnect

# 2. Create venv and install
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 3. Create .env (optional for dev — defaults work)
cp .env.example .env
# Edit SECRET_KEY if you care about session security in dev

# 4. Apply migrations
.venv/bin/alembic upgrade head

# 5. Seed admin user + default settings
#    SAVE THE PASSWORD — printed once, not recoverable without DB access
.venv/bin/python -m seed_data.seed

# 6. Start dev server
.venv/bin/uvicorn app.main:app --reload

# Open http://localhost:8000 — login with admin / <printed password>
# You will be prompted to set a new password on first login.
```

## Reset admin password (if lost)

```bash
.venv/bin/python - << 'EOF'
from app.db import SessionLocal
from app.services.auth import hash_password, generate_temp_password
from app.models.user import User
db = SessionLocal()
user = db.query(User).filter(User.username == "admin").first()
pw = generate_temp_password()
user.password_hash = hash_password(pw)
user.force_password_change = True
db.commit()
print(f"New temp password: {pw}")
EOF
```

## Useful URLs (dev)

| URL | Description |
|-----|-------------|
| `http://localhost:8000/` | Dashboard |
| `http://localhost:8000/login` | Login |
| `http://localhost:8000/healthz` | Health check (JSON) |
| `http://localhost:8000/api/docs` | FastAPI auto-docs |

## Roles

| Role | Can do |
|------|--------|
| `admin` | Everything + user management, settings, recycle bin |
| `architect` | Inventory CRUD, work order create/issue, Excel import/export |
| `dc_tech` | View issued/in-progress work orders, update install status |
| `viewer` | Read-only across all work orders and reports |

## Build phases

- [x] Phase 1 — Foundation: models, migrations, auth, base layout
- [x] Phase 2 — Inventory CRUD with autocomplete (datacenter, rack, system, device, switch, device type)
- [x] Phase 3 — Work order CRUD + connection editor grid (inline editing, bulk save, duplicate detection)
- [x] Phase 4 — Cable length service (seg1/2/3 auto-calculation, standard length rounding, slack)
- [x] Phase 5 — Report view with color coding, inline install-status editing across all work orders
- [x] Phase 6 — DC tech install-status tracking, audit log with filters and pagination
- [x] Phase 7 — Excel import (configurable column map, canonical template download, NetBox aliases)
- [ ] Phase 8 — Excel export matching template
- [ ] Phase 9 — Port utilization analytics
- [ ] Phase 10 — Recycle bin + admin tools + settings
- [ ] Phase 11 — Tests, systemd unit, deployment guide

## Database

Dev uses SQLite (`crossconnect.db` in project root).
Switch to Postgres by setting `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql+psycopg2://user:pass@localhost/crossconnect
```

Then install: `.venv/bin/pip install psycopg2-binary`

## Design notes

- All deletes are soft (`deleted_at` field); hard purge only via admin recycle bin.
- Switch port uniqueness `(switch_id, switch_slot, switch_port)` enforced at the
  service layer (SQLite has no partial unique constraints); also enforced in Postgres
  via a partial index added in a future migration.
- `bcrypt==4.0.1` is pinned — newer versions break passlib 1.7.x.
- `render_as_batch=True` in Alembic env lets SQLite handle ALTER TABLE operations.
