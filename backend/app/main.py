from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import create_tables, SessionLocal
from app.api.routes import leagues, teams, matches, players, fixtures
from app.api.routes import auth as auth_router
from app.core.auth import get_current_user, hash_password
from app.services.scheduler import setup_scheduler


def _seed_admin(db) -> None:
    """Seed the admin user from ADMIN_EMAIL / ADMIN_PASSWORD env vars.
    Silently skipped if either is missing — no implicit/hardcoded fallback."""
    from app.models.user import User

    email = (settings.admin_email or "").strip().lower()
    password = settings.admin_password or ""
    if not email or not password:
        return

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return

    db.add(User(email=email, hashed_password=hash_password(password), is_active=True))
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    db = SessionLocal()
    try:
        _seed_admin(db)
    finally:
        db.close()
    setup_scheduler(SessionLocal)
    yield


app = FastAPI(
    title="MoreBet API",
    description="Advanced football odds calculator using Poisson distribution",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth (public)
app.include_router(auth_router.router)

# Protected routes — require valid JWT
protected = {"dependencies": [Depends(get_current_user)]}
app.include_router(leagues.router, **protected)
app.include_router(teams.router, **protected)
app.include_router(matches.router, **protected)
app.include_router(players.router, **protected)
app.include_router(fixtures.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
