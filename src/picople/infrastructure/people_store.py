from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any

import sqlite3
import time
from pathlib import Path

from picople.infrastructure.db import Database
from picople.core.paths import app_data_dir
from picople.core.log import log
from .people_avatars import PeopleAvatarService


class PeopleStore:
    """
    Capa de acceso para Personas/Mascotas y Caras.
    Reutiliza la conexión de Database y crea/migra su propio esquema si no existe.
    """

    def __init__(self, db: Database) -> None:
        if not db or not db.is_open:
            raise RuntimeError("PeopleStore requiere una Database abierta.")
        self._db = db
        self._conn: sqlite3.Connection = db.conn  # type: ignore
        self._ensure_schema()

    # --------------------------------------------------------------------- #
    # Esquema y migraciones ligeras
    # --------------------------------------------------------------------- #
    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()

        # 1) Tablas básicas (NO dependemos aún de columnas nuevas)
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS person_alias (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                alias     TEXT NOT NULL,
                UNIQUE(person_id, alias),
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE
            );
        """)
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
                ts        INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                is_hidden INTEGER NOT NULL DEFAULT 0
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS person_face (
                person_id INTEGER NOT NULL,
                face_id   INTEGER NOT NULL UNIQUE,
                PRIMARY KEY(person_id, face_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS face_suggestions (
                face_id   INTEGER NOT NULL,
                person_id INTEGER NOT NULL,
                score     REAL,
                state     TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY(face_id, person_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS face_scan_state (
                media_id   INTEGER PRIMARY KEY,
                last_mtime INTEGER NOT NULL,
                last_ts    INTEGER NOT NULL
            );
        """)

        # 2) Migraciones idempotentes (AÑADIR COLUMNAS SI FALTAN)
        self._add_column_if_missing("faces", "sig", "TEXT")
        self._add_column_if_missing(
            "faces", "is_hidden", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("persons", "rep_sig", "TEXT")

        # 3) Índices (tras garantizar columnas)
        def _try(sql: str):
            try:
                cur.execute(sql)
            except sqlite3.OperationalError as e:
                log("PeopleStore.ensure_schema idx skip:", e)

        _try("CREATE INDEX IF NOT EXISTS idx_persons_is_pet   ON persons(is_pet);")
        _try("CREATE INDEX IF NOT EXISTS idx_persons_rep_sig  ON persons(rep_sig);")
        _try("CREATE INDEX IF NOT EXISTS idx_faces_media      ON faces(media_id);")
        _try("CREATE INDEX IF NOT EXISTS idx_faces_quality    ON faces(quality);")
        _try("CREATE INDEX IF NOT EXISTS idx_faces_hidden     ON faces(is_hidden);")
        _try("CREATE INDEX IF NOT EXISTS idx_faces_sig        ON faces(sig);")
        _try("CREATE INDEX IF NOT EXISTS idx_person_face_person ON person_face(person_id);")
        _try("CREATE INDEX IF NOT EXISTS idx_face_sug_person  ON face_suggestions(person_id);")
        _try("CREATE INDEX IF NOT EXISTS idx_face_sug_state   ON face_suggestions(state);")
        _try("CREATE INDEX IF NOT EXISTS idx_face_scan_ts     ON face_scan_state(last_ts);")

        self._conn.commit()

    def _add_column_if_missing(self, table: str, column: str, decl: str) -> None:
        cur = self._conn.cursor()
        cur.execute(f"PRAGMA table_info({table});")
        cols = {r[1] for r in cur.fetchall()}
        if column not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl};")
            self._conn.commit()
            log(f"PeopleStore: columna añadida {table}.{column}")

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

    @staticmethod
    def _ham(a_hex: Optional[str], b_hex: Optional[str]) -> int:
        if not a_hex or not b_hex:
            return 999
        a = int(a_hex, 16)
        b = int(b_hex, 16)
        return (a ^ b).bit_count()

    # --------------------------------------------------------------------- #
    # Personas (clusters)
    # --------------------------------------------------------------------- #
    def create_person(self, display_name: Optional[str] = None, *, is_pet: bool = False,
                      cover_path: Optional[str] = None, rep_sig: Optional[str] = None) -> int:
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

    def set_person_rep_sig(self, person_id: int, rep_sig: Optional[str]) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE persons SET rep_sig=?, updated_at=? WHERE id=?;",
                    (rep_sig, self._now(), person_id))
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
                 *, embedding: Optional[bytes] = None, quality: Optional[float] = None, sig: Optional[str] = None) -> Optional[int]:
        mid = self._get_media_id_by_path(media_path)
        if mid is None:
            return None
        return self.add_face_by_media_id(mid, bbox_xywh, embedding=embedding, quality=quality, sig=sig)

    def add_face_by_media_id(self, media_id: int, bbox_xywh: Tuple[float, float, float, float],
                             *, embedding: Optional[bytes] = None, quality: Optional[float] = None, sig: Optional[str] = None) -> int:
        x, y, w, h = bbox_xywh
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO faces(media_id, x, y, w, h, embedding, quality, sig, ts, is_hidden)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
        """, (media_id, x, y, w, h, embedding, quality, sig, self._now()))
        self._conn.commit()
        return int(cur.lastrowid)

    def get_face_info(self, face_id: int) -> Optional[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, m.path, m.thumb_path, f.x, f.y, f.w, f.h, f.sig
            FROM faces f
            JOIN media m ON m.id = f.media_id
            WHERE f.id=?;
        """, (face_id,))
        r = cur.fetchone()
        if not r:
            return None
        return {
            "face_id": int(r[0]),
            "path": r[1],
            "thumb_path": r[2],
            "bbox": (float(r[3]), float(r[4]), float(r[5]), float(r[6])),
            "sig": r[7],
        }

    def ensure_face_signature(self, face_id: int) -> Optional[str]:
        info = self.get_face_info(face_id)
        if not info:
            return None
        if info.get("sig"):
            return info["sig"]
        sig = PeopleAvatarService.face_signature(info["path"], info["bbox"])
        if not sig and info.get("thumb_path"):
            sig = PeopleAvatarService.face_signature(
                info["thumb_path"], info["bbox"])
        if sig:
            cur = self._conn.cursor()
            cur.execute("UPDATE faces SET sig=? WHERE id=?", (sig, face_id))
            self._conn.commit()
        return sig

    def delete_face(self, face_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM faces WHERE id=?;", (face_id,))
        self._conn.commit()

    def hide_face(self, face_id: int, hidden: bool = True) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE faces SET is_hidden=? WHERE id=?;",
                    (1 if hidden else 0, face_id))
        self._conn.commit()

    # Limpieza de placeholders sin uso
    def purge_empty_persons(self) -> int:
        cur = self._conn.cursor()
        cur.execute("""
            DELETE FROM persons
             WHERE id NOT IN (SELECT DISTINCT person_id FROM person_face)
               AND id NOT IN (SELECT DISTINCT person_id FROM face_suggestions);
        """)
        n = cur.rowcount or 0
        self._conn.commit()
        if n:
            log("PeopleStore: purge_empty_persons ->", n)
        return n

    # --------------------------------------------------------------------- #
    # Agrupación por similitud de firma (rep_sig)
    # --------------------------------------------------------------------- #
    def find_person_by_signature(self, sig: str, *, threshold: int = 10) -> Optional[int]:
        """
        Busca la persona con rep_sig más parecida (distancia Hamming).
        Umbral 10 funciona bien para selfies/series similares.
        """
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, rep_sig FROM persons WHERE rep_sig IS NOT NULL;")
        best_id: Optional[int] = None
        best_d = 999
        for pid, rep in cur.fetchall():
            d = self._ham(sig, rep)
            if d < best_d:
                best_d = d
                best_id = int(pid)
        if best_d <= threshold:
            return best_id
        return None

    # --------------------------------------------------------------------- #
    # Sugerencias y asignación
    # --------------------------------------------------------------------- #
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
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO person_face(person_id, face_id)
            VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        cur.execute("""
            UPDATE face_suggestions
               SET state = CASE WHEN person_id=? THEN 'accepted' ELSE 'rejected' END
             WHERE face_id=?;
        """, (person_id, face_id))
        self._conn.commit()
        # Si la persona no tiene rep_sig, usa la de esta cara
        sig = self.ensure_face_signature(face_id)
        if sig:
            cur.execute(
                "UPDATE persons SET rep_sig=COALESCE(rep_sig, ?) WHERE id=?", (sig, person_id))
            self._conn.commit()

    def reject_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE face_suggestions SET state='rejected' WHERE face_id=? AND person_id=?;", (face_id, person_id))
        self._conn.commit()

    # --------------------------------------------------------------------- #
    # Listados para UI
    # --------------------------------------------------------------------- #
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

    def _face_thumb_path(self, face_id: int, size: int = 160) -> Path:
        base = app_data_dir() / "faces" / "thumbs"
        return base / f"{face_id}_{size}.jpg"

    def build_face_thumb(self, face_id: int, size: int = 160) -> Optional[str]:
        info = self.get_face_info(face_id)
        if not info:
            return None
        outp = self._face_thumb_path(face_id, size)
        if outp.exists():
            return str(outp)
        src = info["thumb_path"] or info["path"]
        ok = PeopleAvatarService.crop_face_square(
            src, info["bbox"], out_path=str(outp), out_size=size, pad_ratio=0.22)
        return ok

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
        out = []
        for r in rows:
            fid = int(r[0])
            thumb = self.build_face_thumb(fid, size=160) or (r[1] or r[2])
            out.append({
                "face_id": fid,
                "thumb": thumb,
                "media_path": r[2],
                "score": float(r[3]),
            })
        return out

    # --------------------------------------------------------------------- #
    # Escaneo incremental
    # --------------------------------------------------------------------- #
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
        log("PeopleStore.get_unscanned_media: filas =", len(rows))
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
        log("PeopleStore.mark_media_scanned: media_id =",
            media_id, "mtime =", mtime)
        self._conn.commit()
