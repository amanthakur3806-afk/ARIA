"""Generic CRUD repository. Entity repositories subclass this."""
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def create(self, **data: Any) -> ModelT:
        obj = self.model(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def create_many(self, rows: list[dict[str, Any]]) -> list[ModelT]:
        objs = [self.model(**row) for row in rows]
        self.db.add_all(objs)
        self.db.commit()
        for obj in objs:
            self.db.refresh(obj)
        return objs

    def get(self, id: str) -> ModelT | None:
        return self.db.get(self.model, id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def update(self, id: str, **changes: Any) -> ModelT | None:
        obj = self.get(id)
        if obj is None:
            return None
        for key, value in changes.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id: str) -> bool:
        obj = self.get(id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
