# app/picople/src/picople/infrastructure/people_store.py
from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any

import sqlite3
import time

from pathlib import Path

from picople.infrastructure.db import Database
from picople.core.paths import app_data_dir
from .people_avatars import PeopleAvatarService


class PeopleStore:
    """
    Capa de acceso para Personas/Mascotas y Caras.
    No modifica Database; usa la misma conexión y crea su propio esquema si no existe.
    """

    def __init__(self, db: Database) -> None:
        if not db or not db.is_open:
            raise RuntimeError("PeopleStore requiere una Database abierta.")
        self._db = db
        self._conn: sqlite3.Connection = db.conn  # type: ignore
        self._ensure_schema()

    def set_is_pet(self, person_id: int, is_pet: bool) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE persons SET is_pet=?, updated_at=? WHERE id=?;",
            (1 if is_pet else 0, self._now(), person_id)
        )
        self._conn.commit()

    def _get_best_face_for_person(self, person_id: int) -> Optional[Tuple[int, str, str, float, float, float, float]]:
        """
        Devuelve (face_id, media_path, thumb_path, x, y, w, h) de la mejor cara:
        mayor calidad y, si empata, más reciente.
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, m.path, m.thumb_path, f.x, f.y, f.w, f.h
            FROM person_face pf
            JOIN faces f ON f.id = pf.face_id
            JOIN media m ON m.id = f.media_id
            WHERE pf.person_id = ?
            ORDER BY COALESCE(f.quality, 0) DESC, f.ts DESC
            LIMIT 1;
        """, (person_id,))
        row = cur.fetchone()
        if not row:
            return None
        return int(row[0]), row[1], (row[2] or row[1]), float(row[3]), float(row[4]), float(row[5]), float(row[6])

    def _get_face_info(self, face_id: int) -> Optional[Tuple[str, str, float, float, float, float]]:
        """
        Devuelve (media_path, thumb_path, x, y, w, h) para una cara.
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT m.path, m.thumb_path, f.x, f.y, f.w, f.h
            FROM faces f
            JOIN media m ON m.id = f.media_id
            WHERE f.id = ?;
        """, (face_id,))
        r = cur.fetchone()
        if not r:
            return None
        return r[0], (r[1] or r[0]), float(r[2]), float(r[3]), float(r[4]), float(r[5])

    def _avatar_output_path(self, person_id: int) -> str:
        base = app_data_dir() / "people" / "avatars"
        return str(base / f"person_{person_id}.jpg")

    def generate_cover_for_person(self, person_id: int, *, prefer_thumb: bool = True) -> Optional[str]:
        """
        Elige la mejor cara confirmada de la persona, genera avatar y actualiza persons.cover_path.
        """
        best = self._get_best_face_for_person(person_id)
        if not best:
            return None
        face_id, media_path, thumb_path, x, y, w, h = best
        src = thumb_path if prefer_thumb else media_path
        out = self._avatar_output_path(person_id)
        ok = PeopleAvatarService.crop_face_square(
            src, (x, y, w, h), out_path=out)
        if not ok:
            return None
        self.set_person_cover(person_id, out)
        return out

    def set_person_cover_from_face(self, person_id: int, face_id: int, *, prefer_thumb: bool = True) -> Optional[str]:
        """
        Genera la portada a partir de una cara específica (útil desde 'Sugerencias' → ⭐).
        """
        info = self._get_face_info(face_id)
        if not info:
            return None
        media_path, thumb_path, x, y, w, h = info
        src = thumb_path if prefer_thumb else media_path
        out = self._avatar_output_path(person_id)
        ok = PeopleAvatarService.crop_face_square(
            src, (x, y, w, h), out_path=out)
        if not ok:
            return None
        self.set_person_cover(person_id, out)
        return out

    def generate_covers_for_all(self, *, missing_only: bool = True) -> int:
        """
        Recorre todas las personas y genera portada:
        - Si missing_only=True, solo para quienes no tienen cover_path.
        Devuelve el número de portadas generadas.
        """
        cur = self._conn.cursor()
        if missing_only:
            cur.execute(
                "SELECT id FROM persons WHERE cover_path IS NULL OR cover_path='';")
        else:
            cur.execute("SELECT id FROM persons;")
        ids = [int(r[0]) for r in cur.fetchall()]
        n = 0
        for pid in ids:
            if self.generate_cover_for_person(pid):
                n += 1
        return n

    # --------------------------------------------------------------------- #
    # Esquema
    # --------------------------------------------------------------------- #

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()

        # Personas (clusters)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT,
                is_pet       INTEGER NOT NULL DEFAULT 0,
                cover_path   TEXT,
                created_at   INTEGER NOT NULL,
                updated_at   INTEGER NOT NULL
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_is_pet ON persons(is_pet);")

        # Alias por persona
        cur.execute("""
            CREATE TABLE IF NOT EXISTS person_alias (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                alias     TEXT NOT NULL,
                UNIQUE(person_id, alias),
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE
            );
        """)

        # Caras detectadas (por media)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id  INTEGER NOT NULL,
                x         REAL NOT NULL,
                y         REAL NOT NULL,
                w         REAL NOT NULL,
                h         REAL NOT NULL,
                embedding BLOB,         -- puede ser NULL si aún no se computa
                quality   REAL,         -- score de calidad/confianza
                ts        INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_media ON faces(media_id);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_quality ON faces(quality);")

        # Asignación CONFIRMADA de cara -> persona (cada cara a lo sumo 1 persona)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS person_face (
                person_id INTEGER NOT NULL,
                face_id   INTEGER NOT NULL UNIQUE,
                PRIMARY KEY(person_id, face_id),
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE,
                FOREIGN KEY(face_id)   REFERENCES faces(id)   ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_person_face_person ON person_face(person_id);")

        # Sugerencias cara <-> persona (posibles matches)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS face_suggestions (
                face_id   INTEGER NOT NULL,
                person_id INTEGER NOT NULL,
                score     REAL,
                state     TEXT NOT NULL DEFAULT 'pending', -- pending|accepted|rejected
                PRIMARY KEY(face_id, person_id),
                FOREIGN KEY(face_id)   REFERENCES faces(id)   ON DELETE CASCADE,
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_sug_person ON face_suggestions(person_id);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_sug_state  ON face_suggestions(state);")

        self._conn.commit()

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    def _now(self) -> int:
        return int(time.time())

    def _get_media_id_by_path(self, path: str) -> Optional[int]:
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM media WHERE path=?;", (path,))
        row = cur.fetchone()
        return int(row[0]) if row else None

    # --------------------------------------------------------------------- #
    # Personas (clusters)
    # --------------------------------------------------------------------- #
    def create_person(self, display_name: Optional[str] = None, *, is_pet: bool = False,
                      cover_path: Optional[str] = None) -> int:
        cur = self._conn.cursor()
        ts = self._now()
        cur.execute("""
            INSERT INTO persons(display_name, is_pet, cover_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?);
        """, (display_name, 1 if is_pet else 0, cover_path, ts, ts))
        self._conn.commit()
        return int(cur.lastrowid)

    def set_person_name(self, person_id: int, name: Optional[str]) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE persons SET display_name=?, updated_at=? WHERE id=?;",
                    (name, self._now(), person_id))
        self._conn.commit()

    def set_person_cover(self, person_id: int, cover_path: Optional[str]) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE persons SET cover_path=?, updated_at=? WHERE id=?;",
                    (cover_path, self._now(), person_id))
        self._conn.commit()

    def delete_person(self, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM persons WHERE id=?;", (person_id,))
        self._conn.commit()

    def add_alias(self, person_id: int, alias: str) -> None:
        cur = self._conn.cursor()
        cur.execute("INSERT OR IGNORE INTO person_alias(person_id, alias) VALUES(?,?);",
                    (person_id, alias))
        self._conn.commit()

    def list_persons_with_suggestion_counts(self, *, include_pets: bool = True) -> List[Dict[str, Any]]:
        where = "" if include_pets else "WHERE p.is_pet=0"
        cur = self._conn.cursor()
        cur.execute(f"""
            SELECT
                p.id,
                COALESCE(p.display_name, '(Sin nombre)') AS title,
                p.is_pet,
                p.cover_path,
                COALESCE( SUM(CASE WHEN fs.state='pending' THEN 1 ELSE 0 END), 0 ) AS sug_count
            FROM persons p
            LEFT JOIN face_suggestions fs ON fs.person_id = p.id
            {where}
            GROUP BY p.id
            ORDER BY title COLLATE NOCASE;
        """)
        rows = cur.fetchall()
        return [{
            "id": int(r[0]),
            "title": r[1],
            "is_pet": bool(r[2]),
            "cover": r[3],
            "suggestions_count": int(r[4] or 0)
        } for r in rows]

    # --------------------------------------------------------------------- #
    # Caras
    # --------------------------------------------------------------------- #
    def add_face(self, media_path: str, bbox_xywh: Tuple[float, float, float, float],
                 *, embedding: Optional[bytes] = None, quality: Optional[float] = None) -> Optional[int]:
        """
        Inserta una cara detectada perteneciente a una media (por path).
        Devuelve face_id o None si el media no está indexado.
        """
        mid = self._get_media_id_by_path(media_path)
        if mid is None:
            return None
        x, y, w, h = bbox_xywh
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO faces(media_id, x, y, w, h, embedding, quality, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (mid, x, y, w, h, embedding, quality, self._now()))
        self._conn.commit()
        return int(cur.lastrowid)

    def delete_face(self, face_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM faces WHERE id=?;", (face_id,))
        self._conn.commit()

    # --------------------------------------------------------------------- #
    # Sugerencias y asignación
    # --------------------------------------------------------------------- #
    def add_suggestion(self, face_id: int, person_id: int, *, score: Optional[float] = None) -> None:
        cur = self._conn.cursor()
        # UPSERT simple: si existe, solo actualiza score y resetea a 'pending' si estaba rechazado
        cur.execute("""
            INSERT INTO face_suggestions(face_id, person_id, score, state)
            VALUES (?, ?, ?, 'pending')
            ON CONFLICT(face_id, person_id) DO UPDATE SET
                score=COALESCE(excluded.score, face_suggestions.score),
                state=CASE WHEN face_suggestions.state='rejected' THEN 'pending' ELSE face_suggestions.state END;
        """, (face_id, person_id, score))
        self._conn.commit()

    def accept_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        # 1) Confirmar asignación (una cara → una persona)
        cur.execute("""
            INSERT INTO person_face(person_id, face_id)
            VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        # 2) Marcar aceptada esta sugerencia y rechazadas las demás de la misma cara
        cur.execute("""
            UPDATE face_suggestions
               SET state = CASE
                               WHEN person_id=? THEN 'accepted'
                               ELSE 'rejected'
                           END
             WHERE face_id=?;
        """, (person_id, face_id))
        self._conn.commit()

    def reject_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            UPDATE face_suggestions SET state='rejected'
            WHERE face_id=? AND person_id=?;
        """, (face_id, person_id))
        self._conn.commit()

    # --------------------------------------------------------------------- #
    # Listados para UI
    # --------------------------------------------------------------------- #
    def list_person_media(self, person_id: int, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Devuelve medias CONFIRMADAS para la persona (para la pestaña “Todos”).
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT m.path, m.kind, m.mtime, m.size, m.thumb_path, m.favorite
            FROM person_face pf
            JOIN faces f  ON f.id = pf.face_id
            JOIN media m  ON m.id = f.media_id
            WHERE pf.person_id = ?
            ORDER BY m.mtime DESC
            LIMIT ? OFFSET ?;
        """, (person_id, limit, offset))
        rows = cur.fetchall()
        return [{
            "path": r[0], "kind": r[1], "mtime": int(r[2]), "size": int(r[3]),
            "thumb_path": r[4], "favorite": bool(r[5])
        } for r in rows]

    def list_person_suggestions(self, person_id: int, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Devuelve caras sugeridas PENDIENTES para la persona (para la pestaña “Sugerencias”).
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, m.thumb_path, m.path, COALESCE(fs.score, 0.0)
            FROM face_suggestions fs
            JOIN faces f ON f.id = fs.face_id
            JOIN media m ON m.id = f.media_id
            WHERE fs.person_id = ? AND fs.state='pending'
            ORDER BY fs.score DESC, f.ts DESC
            LIMIT ? OFFSET ?;
        """, (person_id, limit, offset))
        rows = cur.fetchall()
        return [{
            "face_id": int(r[0]),
            "thumb": r[1] or r[2],
            "media_path": r[2],
            "score": float(r[3]),
        } for r in rows]
