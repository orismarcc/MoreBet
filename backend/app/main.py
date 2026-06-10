from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import create_tables, SessionLocal
from app.api.routes import leagues, teams, matches, players
from app.services.scheduler import setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
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

app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(players.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
