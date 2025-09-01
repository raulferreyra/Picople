from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any

import sqlite3
import time
from pathlib import Path
from PIL import Image

from picople.infrastructure.db import Database
from picople.infrastructure.people_avatars import PeopleAvatarService
from picople.core.paths import app_data_dir


class PeopleStore:
    """
    Acceso a Personas/Mascotas y Caras.
    """

    def __init__(self, db: Database) -> None:
        if not db or not db.is_open:
            raise RuntimeError("PeopleStore requiere una Database abierta.")
        self._db = db
        self._conn: sqlite3.Connection = db.conn  # type: ignore
        self._ensure_schema()

    # ───────────────────────── esquema ─────────────────────────
    def _ensure_schema(self) -> None:
        c = self._conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT,
                is_pet       INTEGER NOT NULL DEFAULT 0,
                cover_path   TEXT,
                rep_sig      BLOB,
                created_at   INTEGER NOT NULL,
                updated_at   INTEGER NOT NULL
            );
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_is_pet ON persons(is_pet);")

        c.execute("""
            CREATE TABLE IF NOT EXISTS person_alias (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                alias     TEXT NOT NULL,
                UNIQUE(person_id, alias),
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE
            );
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id  INTEGER NOT NULL,
                x         REAL NOT NULL,
                y         REAL NOT NULL,
                w         REAL NOT NULL,
                h         REAL NOT NULL,
                embedding BLOB,
                quality   REAL,
                sig       BLOB,
                ts        INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                is_hidden INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_media   ON faces(media_id);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_faces_quality ON faces(quality);")
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_faces_hidden  ON faces(is_hidden);")

        c.execute("""
            CREATE TABLE IF NOT EXISTS person_face (
                person_id INTEGER NOT NULL,
                face_id   INTEGER NOT NULL UNIQUE,
                PRIMARY KEY(person_id, face_id),
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE,
                FOREIGN KEY(face_id)   REFERENCES faces(id)   ON DELETE CASCADE
            );
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_person_face_person ON person_face(person_id);")

        c.execute("""
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
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_sug_person ON face_suggestions(person_id);")
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_sug_state  ON face_suggestions(state);")

        c.execute("""
            CREATE TABLE IF NOT EXISTS face_scan_state (
                media_id   INTEGER PRIMARY KEY,
                last_mtime INTEGER NOT NULL,
                last_ts    INTEGER NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_scan_ts ON face_scan_state(last_ts);")

        self._conn.commit()

    # ───────────────────────── helpers ────────────────────────
    def _now(self) -> int:
        return int(time.time())

    def _get_media_id_by_path(self, path: str) -> Optional[int]:
        c = self._conn.cursor()
        c.execute("SELECT id FROM media WHERE path=?;", (path,))
        row = c.fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _ahash_64(img: Image.Image) -> bytes:
        g = img.convert("L").resize((8, 8), Image.LANCZOS)
        px = list(g.getdata())
        avg = sum(px) / 64.0
        bits = 0
        for i, p in enumerate(px):
            if p > avg:
                bits |= (1 << (63 - i))
        return bits.to_bytes(8, "big")

    @staticmethod
    def _ham64(a: bytes, b: bytes) -> int:
        return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).bit_count()

    def compute_face_signature(self, *, src_path: str, bbox_xywh: Tuple[float, float, float, float]) -> Optional[bytes]:
        p = Path(src_path)
        if not p.exists():
            return None
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                W, H = im.size
                # usar el mismo rect que el avatar (con padding/campo cuadrado)
                pad = 0.35
                x, y, w, h = bbox_xywh
                cx, cy = x + w/2.0, y + h/2.0
                side = int(round(max(w, h) * (1.0 + pad * 2)))
                half = side // 2
                left = max(0, int(round(cx - half)))
                top = max(0, int(round(cy - half)))
                right = min(W, left + side)
                bottom = min(H, top + side)
                if right - left != side:
                    left = max(0, right - side)
                if bottom - top != side:
                    top = max(0, bottom - side)
                crop = im.crop((left, top, right, bottom))
                return self._ahash_64(crop)
        except Exception:
            return None

    # ───────────────────────── personas ────────────────────────
    def create_person(self, display_name: Optional[str] = None, *, is_pet: bool = False,
                      cover_path: Optional[str] = None, rep_sig: Optional[bytes] = None) -> int:
        c = self._conn.cursor()
        ts = self._now()
        c.execute("""
            INSERT INTO persons(display_name, is_pet, cover_path, rep_sig, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (display_name, 1 if is_pet else 0, cover_path, rep_sig, ts, ts))
        self._conn.commit()
        return int(c.lastrowid)

    def set_person_name(self, person_id: int, name: Optional[str]) -> None:
        c = self._conn.cursor()
        c.execute("UPDATE persons SET display_name=?, updated_at=? WHERE id=?;",
                  (name, self._now(), person_id))
        self._conn.commit()

    def set_is_pet(self, person_id: int, is_pet: bool) -> None:
        c = self._conn.cursor()
        c.execute("UPDATE persons SET is_pet=?, updated_at=? WHERE id=?;",
                  (1 if is_pet else 0, self._now(), person_id))
        self._conn.commit()

    def set_person_cover(self, person_id: int, cover_path: Optional[str]) -> None:
        c = self._conn.cursor()
        c.execute("UPDATE persons SET cover_path=?, updated_at=? WHERE id=?;",
                  (cover_path, self._now(), person_id))
        self._conn.commit()

    def delete_person(self, person_id: int) -> None:
        c = self._conn.cursor()
        c.execute("DELETE FROM persons WHERE id=?;", (person_id,))
        self._conn.commit()

    def list_persons_overview(self, *, include_pets: bool = True) -> List[Dict[str, Any]]:
        where = "" if include_pets else "WHERE p.is_pet=0"
        c = self._conn.cursor()
        c.execute(f"""
            SELECT
              p.id,
              COALESCE(p.display_name,'') as title,
              p.is_pet,
              p.cover_path,
              (SELECT COUNT(*) FROM person_face pf WHERE pf.person_id=p.id) AS photos_count,
              COALESCE(SUM(CASE WHEN fs.state='pending' THEN 1 ELSE 0 END),0) AS pending_count
            FROM persons p
            LEFT JOIN face_suggestions fs ON fs.person_id=p.id
            {where}
            GROUP BY p.id
            ORDER BY CASE WHEN title='' THEN 1 ELSE 0 END, title COLLATE NOCASE;
        """)
        rows = c.fetchall()
        return [{
            "id": int(r[0]),
            "title": r[1],  # cadena vacía => “Agregar nombre”
            "is_pet": bool(r[2]),
            "cover": r[3],
            "photos_count": int(r[4] or 0),
            "suggestions_count": int(r[5] or 0),
        } for r in rows]

    # ───────────────────────── caras ───────────────────────────
    def add_face(self, media_path: str, bbox_xywh: Tuple[float, float, float, float],
                 *, embedding: Optional[bytes] = None, quality: Optional[float] = None) -> Optional[int]:
        mid = self._get_media_id_by_path(media_path)
        if mid is None:
            return None
        return self.add_face_by_media_id(mid, bbox_xywh, embedding=embedding, quality=quality)

    def add_face_by_media_id(self, media_id: int, bbox_xywh: Tuple[float, float, float, float],
                             *, embedding: Optional[bytes] = None, quality: Optional[float] = None) -> int:
        x, y, w, h = bbox_xywh
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO faces(media_id, x, y, w, h, embedding, quality, ts, is_hidden, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL);
        """, (media_id, x, y, w, h, embedding, quality, self._now()))
        self._conn.commit()
        return int(c.lastrowid)

    def set_face_signature(self, face_id: int, sig: Optional[bytes]) -> None:
        c = self._conn.cursor()
        c.execute("UPDATE faces SET sig=? WHERE id=?;", (sig, face_id))
        self._conn.commit()

    def hide_face(self, face_id: int, hidden: bool = True) -> None:
        c = self._conn.cursor()
        c.execute("UPDATE faces SET is_hidden=? WHERE id=?;",
                  (1 if hidden else 0, face_id))
        self._conn.commit()

    # ─────────────────────── asignación/sugerencias ───────────────────────
    def add_suggestion(self, face_id: int, person_id: int, *, score: Optional[float] = None) -> None:
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO face_suggestions(face_id, person_id, score, state)
            VALUES (?, ?, ?, 'pending')
            ON CONFLICT(face_id, person_id) DO UPDATE SET
              score=COALESCE(excluded.score, face_suggestions.score),
              state=CASE WHEN face_suggestions.state='rejected' THEN 'pending' ELSE face_suggestions.state END;
        """, (face_id, person_id, score))
        self._conn.commit()

    def accept_suggestion(self, face_id: int, person_id: int) -> None:
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO person_face(person_id, face_id)
            VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        c.execute("""
            UPDATE face_suggestions
               SET state = CASE WHEN person_id=? THEN 'accepted' ELSE 'rejected' END
             WHERE face_id=?;
        """, (person_id, face_id))
        self._conn.commit()

    def add_face_direct(self, face_id: int, person_id: int, *, ensure_cover=True) -> None:
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO person_face(person_id, face_id)
            VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        self._conn.commit()
        if ensure_cover:
            self.set_person_cover_from_face(person_id, face_id)

    # ───────────────────── listados para UI ─────────────────────
    def list_person_media(self, person_id: int, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        c = self._conn.cursor()
        c.execute("""
            SELECT m.path, m.kind, m.mtime, m.size, m.thumb_path, m.favorite
            FROM person_face pf
            JOIN faces f  ON f.id = pf.face_id
            JOIN media m  ON m.id = f.media_id
            WHERE pf.person_id = ?
            ORDER BY m.mtime DESC
            LIMIT ? OFFSET ?;
        """, (person_id, limit, offset))
        rows = c.fetchall()
        return [{
            "path": r[0], "kind": r[1], "mtime": int(r[2]), "size": int(r[3]),
            "thumb_path": r[4], "favorite": bool(r[5])
        } for r in rows]

    def list_person_suggestions(self, person_id: int, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        c = self._conn.cursor()
        c.execute("""
            SELECT f.id, m.thumb_path, m.path, COALESCE(fs.score, 0.0)
            FROM face_suggestions fs
            JOIN faces f ON f.id = fs.face_id
            JOIN media m ON m.id = f.media_id
            WHERE fs.person_id = ? AND fs.state='pending' AND f.is_hidden=0
            ORDER BY fs.score DESC, f.ts DESC
            LIMIT ? OFFSET ?;
        """, (person_id, limit, offset))
        rows = c.fetchall()
        return [{
            "face_id": int(r[0]),
            "thumb": r[1] or r[2],
            "media_path": r[2],
            "score": float(r[3]),
        } for r in rows]

    # ─────────────────── portadas (recorte de rostro) ────────────────────
    def set_person_cover_from_face(self, person_id: int, face_id: int) -> Optional[str]:
        c = self._conn.cursor()
        c.execute("""
            SELECT f.x, f.y, f.w, f.h, m.thumb_path, m.path
            FROM faces f
            JOIN media m ON m.id = f.media_id
            WHERE f.id = ?;
        """, (face_id,))
        row = c.fetchone()
        if not row:
            return None

        x, y, w, h, thumb, path = row
        src = thumb or path
        out_dir = app_data_dir() / "people" / "covers"
        out_path = out_dir / f"person_{person_id}.jpg"

        result = PeopleAvatarService.crop_face_square(
            src_path=src, bbox_xywh=(x, y, w, h),
            out_path=str(out_path), out_size=256, pad_ratio=0.35
        )
        if result:
            self.set_person_cover(person_id, result)
            return result

        # Fallback
        self.set_person_cover(person_id, src)
        return src

    def generate_cover_for_person(self, person_id: int) -> Optional[str]:
        c = self._conn.cursor()
        c.execute("""
            SELECT f.id
            FROM person_face pf
            JOIN faces f ON f.id = pf.face_id
            WHERE pf.person_id = ?
            ORDER BY COALESCE(f.quality, 0.0) DESC, f.ts DESC
            LIMIT 1;
        """, (person_id,))
        row = c.fetchone()
        if not row:
            return None
        return self.set_person_cover_from_face(person_id, int(row[0]))

    # ─────────────────── escaneo incremental ───────────────────
    def get_unscanned_media(self, *, batch: int = 48) -> List[Dict[str, Any]]:
        c = self._conn.cursor()
        c.execute("""
            SELECT m.id AS media_id, m.path, m.mtime, m.thumb_path
            FROM media m
            LEFT JOIN face_scan_state s ON s.media_id = m.id
            WHERE s.media_id IS NULL OR s.last_mtime < m.mtime
            ORDER BY COALESCE(s.last_ts, 0) ASC, m.mtime DESC
            LIMIT ?;
        """, (int(batch),))
        rows = c.fetchall()
        return [{
            "media_id": int(r[0]),
            "path": r[1],
            "mtime": int(r[2]),
            "thumb_path": r[3],
        } for r in rows]

    def mark_media_scanned(self, media_id: int, mtime: int) -> None:
        c = self._conn.cursor()
        c.execute("""
            INSERT INTO face_scan_state(media_id, last_mtime, last_ts)
            VALUES(?, ?, ?)
            ON CONFLICT(media_id) DO UPDATE SET
                last_mtime=excluded.last_mtime,
                last_ts=excluded.last_ts;
        """, (media_id, int(mtime), self._now()))
        self._conn.commit()

    # ─────────────────── agrupación por firma ───────────────────
    def find_similar_person(self, sig: bytes, *, max_hamming: int = 10) -> Optional[int]:
        c = self._conn.cursor()
        c.execute("SELECT id, rep_sig FROM persons WHERE rep_sig IS NOT NULL;")
        best_id: Optional[int] = None
        best_d = max_hamming + 1
        for pid, psig in c.fetchall():
            if psig is None:
                continue
            d = self._ham64(sig, psig)
            if d < best_d:
                best_d = d
                best_id = int(pid)
        return best_id if best_d <= max_hamming else None

    def create_person_from_face(self, face_id: int, sig: Optional[bytes], *, display_name: Optional[str] = None) -> int:
        pid = self.create_person(display_name, rep_sig=sig)
        self.add_face_direct(face_id, pid, ensure_cover=True)
        return pid
