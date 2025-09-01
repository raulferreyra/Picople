# src/picople/infrastructure/people_store.py
from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import sqlite3
import time

from picople.infrastructure.db import Database
from picople.infrastructure.people_avatars import PeopleAvatarService
from picople.core.paths import app_data_dir

from picople.core.log import log


def _ham_hex(a: str, b: str) -> int:
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 256  # lejos


class PeopleStore:
    def __init__(self, db: Database) -> None:
        if not db or not db.is_open:
            raise RuntimeError("PeopleStore requiere una Database abierta.")
        self._db = db
        self._conn: sqlite3.Connection = db.conn  # type: ignore
        self._ensure_schema()

    def _ensure_face_thumb_best(self, face_id: int, src1: str | None, src2: str | None,
                                bbox_xywh: Tuple[float, float, float, float]) -> Optional[str]:
        outp = self._face_thumb_path(face_id)
        if outp.exists():
            return str(outp)
        for src in (src1, src2):
            if not src:
                continue
            p = PeopleAvatarService.crop_face_square(src_path=src, bbox_xywh=bbox_xywh,
                                                     out_path=str(outp), out_size=256, pad_ratio=0.35)
            if p:
                return p
            else:
                log("PeopleStore: crop fallo para src:", src, "face_id=", face_id)
        return None

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        # Base existente…
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
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
        """)
        self._add_column_if_missing(
            "faces", "is_hidden", "INTEGER NOT NULL DEFAULT 0")
        # firma perceptual opcional
        self._add_column_if_missing("faces", "sig", "TEXT")

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_media   ON faces(media_id);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_quality ON faces(quality);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_hidden  ON faces(is_hidden);")

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

        # firma representativa por persona (para agrupar simple)
        self._add_column_if_missing("persons", "rep_sig", "TEXT")

        self._conn.commit()

    def _add_column_if_missing(self, table: str, column: str, decl: str) -> None:
        cur = self._conn.cursor()
        cur.execute(f"PRAGMA table_info({table});")
        cols = {r[1] for r in cur.fetchall()}
        if column not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl};")
            self._conn.commit()
            log(f"PeopleStore: columna añadida {table}.{column}")

    def _now(self) -> int:
        return int(time.time())

    def _get_media_id_by_path(self, path: str) -> Optional[int]:
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM media WHERE path=?;", (path,))
        row = cur.fetchone()
        return int(row[0]) if row else None

    # ---------- Personas ----------
    def create_person(self, display_name: Optional[str] = None, *, is_pet: bool = False,
                      cover_path: Optional[str] = None, rep_sig: Optional[str] = None) -> int:
        cur = self._conn.cursor()
        ts = self._now()
        cur.execute("""
            INSERT INTO persons(display_name, is_pet, cover_path, created_at, updated_at, rep_sig)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (display_name, 1 if is_pet else 0, cover_path, ts, ts, rep_sig))
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

    def set_person_rep_sig(self, person_id: int, sig: Optional[str]) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE persons SET rep_sig=?, updated_at=? WHERE id=?;",
                    (sig, self._now(), person_id))
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

    # ---------- Caras ----------
    def add_face(self, media_path: str, bbox_xywh: Tuple[float, float, float, float],
                 *, embedding: Optional[bytes] = None, quality: Optional[float] = None,
                 sig: Optional[str] = None) -> Optional[int]:
        mid = self._get_media_id_by_path(media_path)
        if mid is None:
            return None
        return self.add_face_by_media_id(mid, bbox_xywh, embedding=embedding, quality=quality, sig=sig)

    def add_face_by_media_id(self, media_id: int, bbox_xywh: Tuple[float, float, float, float],
                             *, embedding: Optional[bytes] = None, quality: Optional[float] = None,
                             sig: Optional[str] = None) -> int:
        x, y, w, h = bbox_xywh
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO faces(media_id, x, y, w, h, embedding, quality, ts, is_hidden, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?);
        """, (media_id, x, y, w, h, embedding, quality, self._now(), sig))
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

    # ---------- Sugerencias y asignación ----------
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
        # confirmar asignación
        cur.execute("""
            INSERT INTO person_face(person_id, face_id)
            VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        # actualizar estados
        cur.execute("""
            UPDATE face_suggestions
               SET state = CASE WHEN person_id=? THEN 'accepted' ELSE 'rejected' END
             WHERE face_id=?;
        """, (person_id, face_id))
        # refrescar rep_sig con la sig de la cara (si existe)
        cur.execute("SELECT sig FROM faces WHERE id=?;", (face_id,))
        row = cur.fetchone()
        if row and row[0]:
            self.set_person_rep_sig(person_id, row[0])
        self._conn.commit()

    def reject_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE face_suggestions SET state='rejected' WHERE face_id=? AND person_id=?;", (face_id, person_id))
        self._conn.commit()

    # ---------- Listados para UI ----------
    def list_person_media_faces(self, person_id: int, *, limit: int = 400, offset: int = 0) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, f.x, f.y, f.w, f.h, m.path, m.thumb_path
            FROM person_face pf
            JOIN faces f  ON f.id = pf.face_id
            JOIN media m  ON m.id = f.media_id
            WHERE pf.person_id = ?
            ORDER BY f.ts DESC
            LIMIT ? OFFSET ?;
        """, (person_id, limit, offset))
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            fid = int(r[0])
            bbox = (float(r[1]), float(r[2]), float(r[3]), float(r[4]))
            media_path, thumb_src = r[5], (r[6] or None)
            face_thumb = self._ensure_face_thumb_best(
                fid, thumb_src, media_path, bbox)
            out.append({"face_id": fid, "face_thumb": face_thumb or (
                thumb_src or media_path), "media_path": media_path})
        return out

    def list_person_suggestions(self, person_id: int, *, limit: int = 400, offset: int = 0) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id, f.x, f.y, f.w, f.h, m.thumb_path, m.path
            FROM face_suggestions fs
            JOIN faces f ON f.id = fs.face_id
            JOIN media m ON m.id = f.media_id
            WHERE fs.person_id = ? AND fs.state='pending' AND f.is_hidden=0
            ORDER BY COALESCE(fs.score,0) DESC, f.ts DESC
            LIMIT ? OFFSET ?;
        """, (person_id, limit, offset))
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            fid = int(r[0])
            bbox = (float(r[1]), float(r[2]), float(r[3]), float(r[4]))
            thumb_src, media_path = (r[5] or None), r[6]
            face_thumb = self._ensure_face_thumb_best(
                fid, thumb_src, media_path, bbox)
            out.append(
                {"face_id": fid, "thumb": face_thumb or (thumb_src or media_path)})
        return out

    # ---------- Portadas ----------
    def set_person_cover_from_face(self, person_id: int, face_id: int) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT m.thumb_path, m.path
            FROM faces f
            JOIN media m ON m.id = f.media_id
            WHERE f.id = ?;
        """, (face_id,))
        row = cur.fetchone()
        if not row:
            return None
        cover = row[0] or row[1]
        self.set_person_cover(person_id, cover)
        return cover

    def generate_cover_for_person(self, person_id: int) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT m.thumb_path, m.path
            FROM person_face pf
            JOIN faces f ON f.id = pf.face_id
            JOIN media m ON m.id = f.media_id
            WHERE pf.person_id = ?
            ORDER BY COALESCE(f.quality, 0.0) DESC, f.ts DESC
            LIMIT 1;
        """, (person_id,))
        row = cur.fetchone()
        if not row:
            return None
        cover = row[0] or row[1]
        self.set_person_cover(person_id, cover)
        return cover

    # ---------- Escaneo incremental ----------
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
        self._conn.commit()
        log("PeopleStore.mark_media_scanned: media_id =",
            media_id, "mtime =", mtime)

    # ---------- Agrupación simple por firma ----------
    def nearest_person_by_sig(self, sig: str, *, max_dist: int = 10) -> Optional[int]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, rep_sig FROM persons WHERE rep_sig IS NOT NULL;")
        best = None
        best_d = 999
        for pid, psig in cur.fetchall():
            if not psig:
                continue
            d = _ham_hex(sig, psig)
            if d < best_d:
                best_d = d
                best = int(pid)
        return best if best is not None and best_d <= max_dist else None

    # ---------- Thumbs por cara ----------
    def _faces_cache_dir(self) -> Path:
        d = app_data_dir() / "faces"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _face_thumb_path(self, face_id: int) -> Path:
        return self._faces_cache_dir() / f"face_{face_id}.jpg"

    def _ensure_face_thumb(self, face_id: int, src_img: str, bbox_xywh: Tuple[float, float, float, float]) -> Optional[str]:
        outp = self._face_thumb_path(face_id)
        if outp.exists():
            return str(outp)
        path = PeopleAvatarService.crop_face_square(
            src_path=src_img,
            bbox_xywh=bbox_xywh,
            out_path=str(outp),
            out_size=256,
            pad_ratio=0.35,
        )
        return path
