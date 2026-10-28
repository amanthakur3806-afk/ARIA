"""Declarative base and shared column helpers for the `aria` schema."""
import os
import uuid

from sqlalchemy import DateTime, ForeignKey, MetaData, String, func, text
from sqlalchemy.orm import DeclarativeBase, mapped_column

SCHEMA = os.getenv("DB_SCHEMA", "aria")


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


def uuid_pk():
    """VARCHAR(36) primary key. Python generates a UUID string; the DB default
    (gen_random_uuid()::text) covers inserts made outside the ORM."""
    return mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=text("gen_random_uuid()::text"),
    )


def created_at_col():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def fk(table: str, *, nullable: bool = False, ondelete: str = "CASCADE"):
    """Foreign key to <schema>.<table>.id"""
    return mapped_column(
        String(36),
        ForeignKey(f"{SCHEMA}.{table}.id", ondelete=ondelete),
        nullable=nullable,
    )
