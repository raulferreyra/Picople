from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any

import sqlite3
import time

from picople.infrastructure.db import Database
from picople.core.paths import app_data_dir
from picople.infrastructure.people_avatars import PeopleAvatarService


class PeopleStore:
    """
    Acceso y utilidades para Personas/Mascotas, Caras y Sugerencias.
    Incluye:
    - Agrupado por firma (aHash) de rostro (faces.sig / persons.rep_sig)
    - Portadas recortadas al rostro
    """

    def __init__(self, db: Database) -> None:
        if not db or not db.is_open:
            raise RuntimeError("PeopleStore requiere una Database abierta.")
        self._db = db
        self._conn: sqlite3.Connection = db.conn  # type: ignore
        self._ensure_schema()

    # ------------------------------------------------------------------ #
    # Esquema y migraciones
    # ------------------------------------------------------------------ #
    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()

        # Personas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT,
                is_pet       INTEGER NOT NULL DEFAULT 0,
                cover_path   TEXT,
                rep_sig      TEXT,                     -- firma de representativo
                created_at   INTEGER NOT NULL,
                updated_at   INTEGER NOT NULL
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_is_pet ON persons(is_pet);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_sig ON persons(rep_sig);")

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

        # Caras
        cur.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id  INTEGER NOT NULL,
                x         REAL NOT NULL,
                y         REAL NOT NULL,
                w         REAL NOT NULL,
                h         REAL NOT NULL,
                embedding BLOB,
                quality   REAL,
                sig       TEXT,                        -- aHash del rostro
                ts        INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                is_hidden INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_media   ON faces(media_id);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_quality ON faces(quality);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_hidden  ON faces(is_hidden);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_sig     ON faces(sig);")

        # Asignación confirmada
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

        # Sugerencias (opcional)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS face_suggestions (
                face_id   INTEGER NOT NULL,
                person_id INTEGER NOT NULL,
                score     REAL,
                state     TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY(face_id, person_id),
                FOREIGN KEY(face_id)   REFERENCES faces(id)   ON DELETE CASCADE,
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_sug_person ON face_suggestions(person_id);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_sug_state  ON face_suggestions(state);")

        # Estado de escaneo incremental
        cur.execute("""
            CREATE TABLE IF NOT EXISTS face_scan_state (
                media_id   INTEGER PRIMARY KEY,
                last_mtime INTEGER NOT NULL,
                last_ts    INTEGER NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_scan_ts ON face_scan_state(last_ts);")

        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _now(self) -> int:
        return int(time.time())

    def _get_media_id_by_path(self, path: str) -> Optional[int]:
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM media WHERE path=?;", (path,))
        row = cur.fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _hamming_hex(a_hex: str, b_hex: str) -> int:
        try:
            return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")
        except Exception:
            return 64

    # ------------------------------------------------------------------ #
    # Personas (clusters)
    # ------------------------------------------------------------------ #
    def create_person(self, display_name: Optional[str] = None, *,
                      is_pet: bool = False, cover_path: Optional[str] = None,
                      rep_sig: Optional[str] = None) -> int:
        cur = self._conn.cursor()
        ts = self._now()
        cur.execute("""
            INSERT INTO persons(display_name, is_pet, cover_path, rep_sig, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (display_name, 1 if is_pet else 0, cover_path, rep_sig, ts, ts))
        self._conn.commit()
        return int(cur.lastrowid)

    def set_person_name(self, person_id: int, name: Optional[str]) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE persons SET display_name=?, updated_at=? WHERE id=?;",
                    (name, self._now(), person_id))
        self._conn.commit()

    def set_is_pet(self, person_id: int, is_pet: bool) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE persons SET is_pet=?, updated_at=? WHERE id=?;",
                    (1 if is_pet else 0, self._now(), person_id))
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
        cur.execute(
            "INSERT OR IGNORE INTO person_alias(person_id, alias) VALUES(?,?);",
            (person_id, alias)
        )
        self._conn.commit()

    # Agrupado por firma -------------------------------------------------- #
    def set_face_sig(self, face_id: int, sig: str) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE faces SET sig=? WHERE id=?;", (sig, face_id))
        self._conn.commit()

    def find_person_by_sig(self, sig: Optional[str], max_dist: int = 7) -> Optional[int]:
        if not sig:
            return None
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, rep_sig FROM persons WHERE rep_sig IS NOT NULL;")
        best_id = None
        best_d = 999
        for pid, rep in cur.fetchall():
            d = self._hamming_hex(sig, rep)
            if d < best_d:
                best_id, best_d = int(pid), d
        return best_id if best_d <= max_dist else None

    def upsert_person_for_sig(self, sig: Optional[str], *, cover_hint: Optional[str] = None) -> int:
        pid = self.find_person_by_sig(sig)
        if pid is not None:
            return pid
        return self.create_person(display_name=None, is_pet=False,
                                  cover_path=cover_hint, rep_sig=sig)

    def link_face_to_person(self, person_id: int, face_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO person_face(person_id, face_id) VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        # y marca sugerencias como aceptadas/rechazadas si existían
        cur.execute("""
            UPDATE face_suggestions
               SET state = CASE
                               WHEN person_id=? THEN 'accepted'
                               ELSE 'rejected'
                           END
             WHERE face_id=?;
        """, (person_id, face_id))
        self._conn.commit()

    # Portadas desde rostro ---------------------------------------------- #
    def make_avatar_from_face(self, person_id: int, face_id: int) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT m.thumb_path, m.path, f.x, f.y, f.w, f.h
            FROM faces f
            JOIN media m ON m.id = f.media_id
            WHERE f.id = ?;
        """, (face_id,))
        row = cur.fetchone()
        if not row:
            return None
        src = row[0] or row[1]
        x, y, w, h = float(row[2]), float(row[3]), float(row[4]), float(row[5])
        out = app_data_dir() / "avatars" / f"person_{person_id}.jpg"
        path = PeopleAvatarService.crop_face_square(
            src, (x, y, w, h), out_path=str(out), out_size=256, pad_ratio=0.35
        )
        if path:
            self.set_person_cover(person_id, path)
        return path

    def set_person_cover_from_face(self, person_id: int, face_id: int) -> Optional[str]:
        # compat: usa la misma ruta final de avatar
        return self.make_avatar_from_face(person_id, face_id)

    def generate_cover_for_person(self, person_id: int) -> Optional[str]:
        """
        Si no hay portada, usa la cara confirmada con mejor calidad para crearla.
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id
            FROM person_face pf
            JOIN faces f ON f.id = pf.face_id
            WHERE pf.person_id = ?
            ORDER BY COALESCE(f.quality, 0.0) DESC, f.ts DESC
            LIMIT 1;
        """, (person_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self.make_avatar_from_face(person_id, int(row[0]))

    # ------------------------------------------------------------------ #
    # Caras
    # ------------------------------------------------------------------ #
    def add_face(self, media_path: str, bbox_xywh: Tuple[float, float, float, float],
                 *, embedding: Optional[bytes] = None, quality: Optional[float] = None) -> Optional[int]:
        mid = self._get_media_id_by_path(media_path)
        if mid is None:
            return None
        return self.add_face_by_media_id(mid, bbox_xywh, embedding=embedding, quality=quality)

    def add_face_by_media_id(self, media_id: int, bbox_xywh: Tuple[float, float, float, float],
                             *, embedding: Optional[bytes] = None, quality: Optional[float] = None) -> int:
        x, y, w, h = bbox_xywh
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO faces(media_id, x, y, w, h, embedding, quality, ts, is_hidden)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0);
        """, (media_id, x, y, w, h, embedding, quality, self._now()))
        self._conn.commit()
        return int(cur.lastrowid)

    def delete_face(self, face_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM faces WHERE id=?;", (face_id,))
        self._conn.commit()

    def hide_face(self, face_id: int, hidden: bool = True) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE faces SET is_hidden=? WHERE id=?;",
                    (1 if hidden else 0, face_id))
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Sugerencias (se mantienen por compatibilidad con la UI)
    # ------------------------------------------------------------------ #
    def add_suggestion(self, face_id: int, person_id: int, *, score: Optional[float] = None) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO face_suggestions(face_id, person_id, score, state)
            VALUES (?, ?, ?, 'pending')
            ON CONFLICT(face_id, person_id) DO UPDATE SET
                score=COALESCE(excluded.score, face_suggestions.score),
                state=CASE WHEN face_suggestions.state='rejected' THEN 'pending' ELSE face_suggestions.state END;
        """, (face_id, person_id, score))
        self._conn.commit()

    def accept_suggestion(self, face_id: int, person_id: int) -> None:
        self.link_face_to_person(person_id, face_id)

    def reject_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            UPDATE face_suggestions SET state='rejected'
            WHERE face_id=? AND person_id=?;
        """, (face_id, person_id))
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Listados para UI
    # ------------------------------------------------------------------ #
    def list_person_media(self, person_id: int, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
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
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, m.thumb_path, m.path, COALESCE(fs.score, 0.0)
            FROM face_suggestions fs
            JOIN faces f ON f.id = fs.face_id
            JOIN media m ON m.id = f.media_id
            WHERE fs.person_id = ? AND fs.state='pending' AND f.is_hidden=0
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

    def list_persons_overview(self, *, include_zero: bool = False) -> List[Dict[str, Any]]:
        """
        Resumen para la grilla: id, title, is_pet, cover, photos_count, suggestions_count.
        Por defecto oculta personas sin fotos (0).
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT
                p.id,
                COALESCE(p.display_name, '') AS title,
                p.is_pet,
                p.cover_path,
                COUNT(pf.face_id) AS photos,
                COALESCE(SUM(CASE WHEN fs.state='pending' THEN 1 ELSE 0 END), 0) AS sug_count
            FROM persons p
            LEFT JOIN person_face pf ON pf.person_id = p.id
            LEFT JOIN face_suggestions fs ON fs.person_id = p.id
            GROUP BY p.id
            ORDER BY photos DESC, title COLLATE NOCASE;
        """)
        rows = cur.fetchall()
        out = []
        for r in rows:
            photos = int(r[4] or 0)
            if not include_zero and photos == 0:
                continue
            out.append({
                "id": int(r[0]),
                "title": r[1],
                "is_pet": bool(r[2]),
                "cover": r[3],
                "photos": photos,
                "suggestions_count": int(r[5] or 0)
            })
        return out

    # ------------------------------------------------------------------ #
    # Escaneo incremental
    # ------------------------------------------------------------------ #
    def get_unscanned_media(self, *, batch: int = 48) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT m.id AS media_id, m.path, m.mtime, m.thumb_path
            FROM media m
            LEFT JOIN face_scan_state s ON s.media_id = m.id
            WHERE s.media_id IS NULL OR s.last_mtime < m.mtime
            ORDER BY COALESCE(s.last_ts, 0) ASC, m.mtime DESC
            LIMIT ?;
        """, (int(batch),))
        rows = cur.fetchall()
        return [{
            "media_id": int(r[0]),
            "path": r[1],
            "mtime": int(r[2]),
            "thumb_path": r[3],
        } for r in rows]

    def mark_media_scanned(self, media_id: int, mtime: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO face_scan_state(media_id, last_mtime, last_ts)
            VALUES(?, ?, ?)
            ON CONFLICT(media_id) DO UPDATE SET
                last_mtime=excluded.last_mtime,
                last_ts=excluded.last_ts;
        """, (media_id, int(mtime), self._now()))
        self._conn.commit()
