from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(80))
    season: Mapped[int] = mapped_column(Integer)
    logo_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # League averages (recalculated after each ingestion)
    home_goals_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_goals_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_xg_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_xg_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_matches: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    teams: Mapped[list["Team"]] = relationship("Team", back_populates="league")
    matches: Mapped[list["Match"]] = relationship("Match", back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_id: Mapped[int] = mapped_column(Integer, index=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"))
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Home stats (last N games at home)
    home_played: Mapped[int] = mapped_column(Integer, default=0)
    home_goals_scored: Mapped[float] = mapped_column(Float, default=0.0)
    home_goals_conceded: Mapped[float] = mapped_column(Float, default=0.0)
    home_xg_scored: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_xg_conceded: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Away stats
    away_played: Mapped[int] = mapped_column(Integer, default=0)
    away_goals_scored: Mapped[float] = mapped_column(Float, default=0.0)
    away_goals_conceded: Mapped[float] = mapped_column(Float, default=0.0)
    away_xg_scored: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_xg_conceded: Mapped[float | None] = mapped_column(Float, nullable=True)

    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    league: Mapped["League"] = relationship("League", back_populates="teams")
    players: Mapped[list["Player"]] = relationship("Player", back_populates="team")
    home_matches: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.home_team_id", back_populates="home_team"
    )
    away_matches: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.away_team_id", back_populates="away_team"
    )


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Advanced metrics (manually updated or via API)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    goal_contribution_pct: Mapped[float] = mapped_column(Float, default=0.0)
    sca: Mapped[float | None] = mapped_column(Float, nullable=True)
    xg_assisted: Mapped[float | None] = mapped_column(Float, nullable=True)
    minutes_played: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    team: Mapped["Team"] = relationship("Team", back_populates="players")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"))
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"))

    match_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_xg: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    league: Mapped["League"] = relationship("League", back_populates="matches")
    home_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[home_team_id], back_populates="home_matches"
    )
    away_team: Mapped["Team"] = relationship(
        "Team", foreign_keys=[away_team_id], back_populates="away_matches"
    )
