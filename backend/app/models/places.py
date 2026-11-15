"""Where people say a word: settlements (GeoNames) and members' "they say it here" marks.

A member adding a word says where it is said: a settlement, or only an oblast or country.
Only the settlement is kept, never the member's own coordinates ("my location" is matched
to the nearest settlement and forgotten).
"""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.lexicon import Region


class Settlement(Base):
    """A city, town or village from GeoNames."""

    __tablename__ = "settlement"
    __table_args__ = (
        # Settlement search: substring (LIKE) matches on all its names, folded like word search
        Index(
            "ix_settlement_search_key_trgm",
            text("search_key(keys)"),
            postgresql_using="gin",
            postgresql_ops={"search_key(keys)": "gin_trgm_ops"},
        ),
    )

    # The GeoNames id
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    # GeoNames' main name (local, in Latin script for Ukraine: "Staryi Kosiv")
    name: Mapped[str] = mapped_column(String(200))
    # Names in the interface languages and the local one: {"uk": "Старий Косів", ...}
    names: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, server_default="{}")
    # All its names joined with " | ", what the search matches
    keys: Mapped[str] = mapped_column(Text)
    # ISO 3166-1 alpha-2
    country: Mapped[str] = mapped_column(String(2))
    population: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    geom = mapped_column(Geometry("POINT", srid=4326, spatial_index=True))
    # The smallest of our regions it lies in: the oblast, else the country
    region_id: Mapped[int | None] = mapped_column(ForeignKey("region.id"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id"))

    region: Mapped[Region | None] = relationship()


class FormPlace(Base):
    """A member says the word is said here (when adding it, or adding it again)."""

    __tablename__ = "form_place"
    __table_args__ = (UniqueConstraint("form_id", "user_id", "settlement_id", "region_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlement.id", ondelete="SET NULL"), index=True
    )
    # The settlement's oblast or country, or the region chosen without a settlement
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    settlement: Mapped[Settlement | None] = relationship()
    region: Mapped[Region] = relationship()
