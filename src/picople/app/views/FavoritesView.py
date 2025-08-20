# src/picople/app/views/FavoritesView.py
from __future__ import annotations
from typing import Optional
from picople.infrastructure.db import Database
from .CollectionView import CollectionView


class FavoritesView(CollectionView):
    def __init__(self, db: Optional[Database] = None):
        super().__init__(
            db,
            title="Favoritos",
            subtitle="Tus fotos y videos marcados con ♥.",
            favorites_only=True
        )
