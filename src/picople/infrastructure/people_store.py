from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any

import sqlite3
import time
from pathlib import Path

from picople.infrastructure.db import Database
from picople.core.paths import app_data_dir
from picople.infrastructure.people_avatars import PeopleAvatarService


class PeopleStore:
    """
    Personas/Mascotas, Caras y Sugerencias:
      • Agrupado por firma (aHash) de rostro (faces.sig / persons.rep_sig)
      • Portadas recortadas al rostro
    """

    def __init__(self, db: Database) -> None:
        if not db or not db.is_open:
            raise RuntimeError("PeopleStore requiere una Database abierta.")
        self._db = db
        self._conn: sqlite3.Connection = db.conn  # type: ignore
        self._ensure_schema()

    # ───────────────────────── Esquema ─────────────────────────
    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS persons(
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT,
                is_pet       INTEGER NOT NULL DEFAULT 0,
                cover_path   TEXT,
                rep_sig      TEXT,
                created_at   INTEGER NOT NULL,
                updated_at   INTEGER NOT NULL
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_is_pet ON persons(is_pet);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_persons_sig   ON persons(rep_sig);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS person_alias(
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                alias     TEXT NOT NULL,
                UNIQUE(person_id, alias),
                FOREIGN KEY(person_id) REFERENCES persons(id) ON DELETE CASCADE
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS faces(
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id  INTEGER NOT NULL,
                x         REAL NOT NULL,
                y         REAL NOT NULL,
                w         REAL NOT NULL,
                h         REAL NOT NULL,
                embedding BLOB,
                quality   REAL,
                sig       TEXT,
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS person_face(
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
            CREATE TABLE IF NOT EXISTS face_suggestions(
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
            CREATE TABLE IF NOT EXISTS face_scan_state(
                media_id   INTEGER PRIMARY KEY,
                last_mtime INTEGER NOT NULL,
                last_ts    INTEGER NOT NULL,
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_scan_ts ON face_scan_state(last_ts);")

        self._conn.commit()

    # ───────────────────────── Helpers ─────────────────────────
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

    def _is_legacy_cover(self, cover_path: Optional[str]) -> bool:
        """
        Devuelve True si la portada parece 'legada': inexistente, no-cuadrada,
        o fuera de la carpeta de avatars del app.
        """
        if not cover_path:
            return True
        try:
            p = Path(cover_path)
            # si no está en …/avatars/ lo consideramos legado
            if p.parent.name.lower() != "avatars":
                return True
            with Image.open(cover_path) as im:
                w, h = im.size
                if w != h or w == 0:
                    return True
        except Exception:
            return True
        return False

    def _best_suggestion_face_id(self, person_id: int) -> Optional[int]:
        cur = self._conn.cursor()
        cur.execute("""
            SELECT f.id
            FROM face_suggestions fs
            JOIN faces f ON f.id = fs.face_id
            WHERE fs.person_id=? AND fs.state='pending' AND f.is_hidden=0
            ORDER BY COALESCE(fs.score,0) DESC, f.ts DESC
            LIMIT 1;
        """, (person_id,))
        row = cur.fetchone()
        return int(row[0]) if row else None

    def refresh_avatar_if_legacy(self, person_id: int, *, force: bool = False) -> Optional[str]:
        """
        Si la portada está ausente o parece 'legada', crea una portada nueva
        recortando la mejor cara disponible (sugerencia o confirmada).
        Si 'force' es True, siempre regenera.
        Devuelve la ruta final usada, o None si no hubo cambios.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT cover_path FROM persons WHERE id=?", (person_id,))
        row = cur.fetchone()
        current = row[0] if row else None

        if force:
            cur.execute(
                "UPDATE persons SET cover_path=NULL WHERE id=?", (person_id,))
            self._conn.commit()
            current = None

        if not force and not self._is_legacy_cover(current):
            return current  # ya está bien

        # 1) preferimos mejor sugerencia
        face_id = self._best_suggestion_face_id(person_id)
        if face_id is not None:
            path = self.make_avatar_from_face(
                person_id, face_id, out_size=256, pad_ratio=0.25)
            if path:
                return path

        # 2) si no hay sugerencias, usar cara confirmada de mejor calidad
        path = self.generate_cover_for_person(person_id)
        return path

    # ─────────────── Avatares (recorte de rostro) ───────────────
    def _avatar_out_path(self, person_id: int) -> str:
        out = app_data_dir() / "avatars" / f"person_{person_id}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        return str(out)

    def make_avatar_from_face(self, person_id: int, face_id: int,
                              *, out_size: int = 256, pad_ratio: float = 0.25) -> Optional[str]:
        """
        Recorta la cara indicada y guarda como portada de la persona.
        Devuelve la ruta generada o None.
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT m.thumb_path, m.path, f.x, f.y, f.w, f.h
            FROM faces f
            JOIN media m ON m.id = f.media_id
            WHERE f.id = ? AND f.is_hidden = 0;
        """, (face_id,))
        row = cur.fetchone()
        if not row:
            return None

        # Usamos la misma imagen con la que se detectó (coordenadas consistentes)
        src_path = row[0] or row[1]
        bbox = (float(row[2]), float(row[3]), float(row[4]), float(row[5]))
        out_path = self._avatar_out_path(person_id)

        path = PeopleAvatarService.crop_face_square(
            src_path, bbox, out_path=out_path, out_size=out_size, pad_ratio=pad_ratio
        )
        if path:
            self.set_person_cover(person_id, path)
            return path
        return None

    def ensure_cover_if_missing(self, person_id: int) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT cover_path FROM persons WHERE id=?", (person_id,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0]

        # 1) mejor sugerencia
        cur.execute("""
            SELECT face_id
            FROM face_suggestions
            WHERE person_id=? AND state='pending'
            ORDER BY COALESCE(score,0) DESC
            LIMIT 1;
        """, (person_id,))
        r = cur.fetchone()
        if r:
            path = self.make_avatar_from_face(person_id, int(r[0]))
            if path:
                return path

        # 2) una cara confirmada
        cur.execute("""
            SELECT face_id
            FROM person_face
            WHERE person_id=?
            ORDER BY rowid DESC
            LIMIT 1;
        """, (person_id,))
        r = cur.fetchone()
        if r:
            path = self.make_avatar_from_face(person_id, int(r[0]))
            if path:
                return path

        return None

    # ───────────────────────── Personas ─────────────────────────
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
        cur = self._conn.cursor
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

    # ───────────── Agrupado por firma (aHash) ─────────────
    def set_face_sig(self, face_id: int, sig: str) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE faces SET sig=? WHERE id=?;", (sig, face_id))
        self._conn.commit()

    def find_person_by_sig(self, sig: Optional[str], max_dist: int = 12) -> Optional[int]:
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
        return self.create_person(display_name=None, is_pet=False, cover_path=cover_hint, rep_sig=sig)

    def link_face_to_person(self, person_id: int, face_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO person_face(person_id, face_id) VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        cur.execute("""
            UPDATE face_suggestions
               SET state = CASE
                               WHEN person_id=? THEN 'accepted'
                               ELSE 'rejected'
                           END
             WHERE face_id=?;
        """, (person_id, face_id))
        self._conn.commit()

    def set_person_cover_from_face(self, person_id: int, face_id: int) -> Optional[str]:
        return self.make_avatar_from_face(person_id, face_id)

    # ───────────── Listados para UI ─────────────
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

    def list_persons_with_suggestion_counts(self, *, include_pets: bool = True) -> List[Dict[str, Any]]:
        where = "" if include_pets else "WHERE p.is_pet=0"
        cur = self._conn.cursor()
        cur.execute(f"""
            SELECT
                p.id,
                COALESCE(p.display_name, '(Sin nombre)') AS title,
                p.is_pet,
                p.cover_path,
                COALESCE(SUM(CASE WHEN fs.state='pending' THEN 1 ELSE 0 END), 0) AS sug_count
            FROM persons p
            LEFT JOIN face_suggestions fs ON fs.person_id = p.id
            {where}
            GROUP BY p.id
            ORDER BY title COLLATE NOCASE;
        """)
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            pid = int(r[0])
            cover = r[3] or ""
            if not cover:
                try:
                    cover = self.ensure_cover_if_missing(pid) or ""
                except Exception:
                    pass
            out.append({
                "id": pid,
                "title": r[1],
                "is_pet": bool(r[2]),
                "cover": cover,
                "suggestions_count": int(r[4] or 0)
            })
        return out

    def list_persons_overview(self, *, include_zero: bool = False) -> List[Dict[str, Any]]:
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
        out: List[Dict[str, Any]] = []
        for r in rows:
            pid = int(r[0])
            photos = int(r[4] or 0)
            if not include_zero and photos == 0:
                # igual queremos avatar si hay sugerencias
                pass

            cover = r[3] or ""
            try:
                cover = self.ensure_cover_if_missing(pid) or cover
            except Exception:
                pass

            out.append({
                "id": pid,
                "title": r[1],
                "is_pet": bool(r[2]),
                "cover": cover,
                "photos": photos,
                "suggestions_count": int(r[5] or 0)
            })
        return out

    # ───────────────────────── Escaneo ─────────────────────────
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

    def accept_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO person_face(person_id, face_id)
            VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        cur.execute("""
            UPDATE face_suggestions
               SET state = CASE
                               WHEN person_id=? THEN 'accepted'
                               ELSE 'rejected'
                           END
             WHERE face_id=?;
        """, (person_id, face_id))
        self._conn.commit()

        self.ensure_cover_if_missing(person_id)
        self.link_face_to_person(person_id, face_id)

    def reject_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            UPDATE face_suggestions SET state='rejected'
            WHERE face_id=? AND person_id=?;
        """, (face_id, person_id))
        self._conn.commit()

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

    # ───────────────────────── Suggestions ─────────────────────────
    def add_suggestion(self, face_id: int, person_id: int, *, score: Optional[float] = None) -> None:
        """
        Crea/actualiza una sugerencia (estado = pending).
        Si ya existía y estaba 'rejected', la vuelve a poner 'pending'.
        """
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO face_suggestions(face_id, person_id, score, state)
            VALUES (?, ?, ?, 'pending')
            ON CONFLICT(face_id, person_id) DO UPDATE SET
                score=COALESCE(excluded.score, face_suggestions.score),
                state=CASE
                        WHEN face_suggestions.state='rejected' THEN 'pending'
                        ELSE face_suggestions.state
                    END;
        """, (face_id, person_id, score))
        self._conn.commit()

    def accept_suggestion(self, face_id: int, person_id: int) -> None:
        """
        Acepta una sugerencia: vincula la cara a la persona y limpia estados.
        """
        cur = self._conn.cursor()
        cur.execute("""
            INSERT INTO person_face(person_id, face_id)
            VALUES (?, ?)
            ON CONFLICT(face_id) DO UPDATE SET person_id=excluded.person_id;
        """, (person_id, face_id))
        cur.execute("""
            UPDATE face_suggestions
            SET state = CASE
                            WHEN person_id=? THEN 'accepted'
                            ELSE 'rejected'
                        END
            WHERE face_id=?;
        """, (person_id, face_id))
        self._conn.commit()
        # asegurar portada si faltaba
        try:
            self.ensure_cover_if_missing(person_id)
        except Exception:
            pass

    def reject_suggestion(self, face_id: int, person_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            UPDATE face_suggestions SET state='rejected'
            WHERE face_id=? AND person_id=?;
        """, (face_id, person_id))
        self._conn.commit()
