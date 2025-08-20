# src/picople/infrastructure/db.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Tuple, List

_sqlcipher_mod = None
try:
    import sqlcipher3 as _sqlcipher_mod  # type: ignore
except Exception:
    try:
        import pysqlcipher3 as _sqlcipher_mod  # type: ignore
    except Exception:
        _sqlcipher_mod = None


class DBError(RuntimeError):
    pass


class Database:
    """
    Gestor de DB cifrada con SQLCipher.
    Tablas:
      - folders(path UNIQUE)
      - media(path UNIQUE, kind, mtime, size, thumb_path, favorite)
      - albums(id, title UNIQUE, cover_path)
      - album_media(album_id, media_id, position)
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = None

    @property
    def is_open(self) -> bool:
        return self.conn is not None

    # -------------------- Open / Close -------------------- #
    def open(self, passphrase: str) -> None:
        if _sqlcipher_mod is None:
            raise DBError(
                "No se encontró SQLCipher. Instala 'pysqlcipher3' (Windows) o enlaza sqlcipher."
            )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = _sqlcipher_mod.connect(str(self.db_path))
        cur = self.conn.cursor()

        # Clave y PRAGMAs seguros (algunas pueden no existir según build)
        cur.execute("PRAGMA key = ?;", (passphrase,))
        try:
            cur.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
            cur.execute("PRAGMA kdf_iter = 256000;")
            cur.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA256;")
            cur.execute("PRAGMA cipher_page_size = 4096;")
        except Exception:
            pass

        # Verificar clave
        try:
            cur.execute("SELECT count(*) FROM sqlite_master;")
            cur.fetchone()
        except Exception as e:
            self.conn.close()
            self.conn = None
            raise DBError(f"Clave inválida o base de datos corrupta: {e}")

        try:
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass

        self._ensure_schema()
        self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    # -------------------- Schema & migraciones -------------------- #
    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()

        # folders
        cur.execute("""
            CREATE TABLE IF NOT EXISTS folders(
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE
            );
        """)

        # media
        cur.execute("""
            CREATE TABLE IF NOT EXISTS media(
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                path       TEXT NOT NULL UNIQUE,
                kind       TEXT NOT NULL,     -- 'image' | 'video'
                mtime      INTEGER NOT NULL,
                size       INTEGER NOT NULL,
                thumb_path TEXT,
                favorite   INTEGER NOT NULL DEFAULT 0
            );
        """)
        # Migración: favorite si faltara
        self._add_column_if_missing(
            "media", "favorite", "INTEGER NOT NULL DEFAULT 0")

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_mtime ON media(mtime);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_kind  ON media(kind);")

        # albums
        cur.execute("""
            CREATE TABLE IF NOT EXISTS albums(
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL UNIQUE,
                cover_path TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS album_media(
                album_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(album_id, media_id),
                FOREIGN KEY(album_id) REFERENCES albums(id) ON DELETE CASCADE,
                FOREIGN KEY(media_id) REFERENCES media(id)  ON DELETE CASCADE
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_album_media_album ON album_media(album_id);")

    def _add_column_if_missing(self, table: str, column: str, decl: str) -> None:
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({table});")
        cols = [r[1] for r in cur.fetchall()]
        if column not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl};")

    # -------------------- Media UPSERT -------------------- #
    def upsert_media(self, path: str, kind: str, mtime: int, size: int, thumb_path: Optional[str]) -> None:
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO media(path, kind, mtime, size, thumb_path)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    kind=excluded.kind,
                    mtime=excluded.mtime,
                    size=excluded.size,
                    thumb_path=excluded.thumb_path;
            """, (path, kind, mtime, size, thumb_path))
        except Exception:
            cur.execute("UPDATE media SET kind=?, mtime=?, size=?, thumb_path=? WHERE path=?;",
                        (kind, mtime, size, thumb_path, path))
            if cur.rowcount == 0:
                cur.execute("INSERT INTO media(path, kind, mtime, size, thumb_path) VALUES (?, ?, ?, ?, ?);",
                            (path, kind, mtime, size, thumb_path))
        self.conn.commit()

    # -------------------- Favoritos -------------------- #
    def set_favorite(self, path: str, fav: bool) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE media SET favorite=? WHERE path=?;",
                    (1 if fav else 0, path))
        self.conn.commit()

    def is_favorite(self, path: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT favorite FROM media WHERE path=?;", (path,))
        row = cur.fetchone()
        return bool(row and row[0])

    # -------------------- Listados / Paginación -------------------- #
    def count_media(
        self,
        *,
        kind: Optional[str] = None,
        search: Optional[str] = None,
        favorites_only: bool = False,
        album_id: Optional[int] = None
    ) -> int:
        cur = self.conn.cursor()
        where = []
        params: list = []
        if kind:
            where.append("m.kind=?")
            params.append(kind)
        if search:
            where.append("(m.path LIKE ?)")
            params.append(f"%{search}%")
        if favorites_only:
            where.append("m.favorite=1")
        if album_id is not None:
            where.append("am.album_id=?")
            params.append(album_id)

        sql = "SELECT COUNT(*) FROM media m"
        if album_id is not None:
            sql += " JOIN album_media am ON am.media_id = m.id"
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur.execute(sql, params)
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def fetch_media_page(
        self,
        *,
        offset: int,
        limit: int,
        kind: Optional[str] = None,
        search: Optional[str] = None,
        order_by: str = "mtime DESC",
        favorites_only: bool = False,
        album_id: Optional[int] = None
    ) -> list[dict]:
        cur = self.conn.cursor()
        where = []
        params: list = []
        if kind:
            where.append("m.kind=?")
            params.append(kind)
        if search:
            where.append("(m.path LIKE ?)")
            params.append(f"%{search}%")
        if favorites_only:
            where.append("m.favorite=1")
        if album_id is not None:
            where.append("am.album_id=?")
            params.append(album_id)

        sql = "SELECT m.path, m.kind, m.mtime, m.size, m.thumb_path, m.favorite FROM media m"
        if album_id is not None:
            sql += " JOIN album_media am ON am.media_id = m.id"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY m.{order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cur.execute(sql, params)
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "path": r[0], "kind": r[1], "mtime": int(r[2]), "size": int(r[3]),
                "thumb_path": r[4], "favorite": bool(r[5])
            })
        return out

    # -------------------- Álbumes -------------------- #
    def list_albums(self) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT a.id, a.title, a.cover_path, COUNT(am.media_id)
            FROM albums a
            LEFT JOIN album_media am ON am.album_id=a.id
            GROUP BY a.id
            ORDER BY a.title COLLATE NOCASE;
        """)
        rows = cur.fetchall()
        return [{"id": r[0], "title": r[1], "cover_path": r[2], "count": r[3]} for r in rows]

    def fetch_album_media(self, album_id: int, offset: int, limit: int) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT m.path, m.kind, m.mtime, m.size, m.thumb_path, m.favorite
            FROM album_media am
            JOIN media m ON m.id = am.media_id
            WHERE am.album_id=?
            ORDER BY m.mtime DESC
            LIMIT ? OFFSET ?;
        """, (album_id, limit, offset))
        rows = cur.fetchall()
        return [{
            "path": r[0], "kind": r[1], "mtime": int(r[2]), "size": int(r[3]),
            "thumb_path": r[4], "favorite": bool(r[5])
        } for r in rows]

    def set_album_cover(self, album_id: int, cover_path: Optional[str]) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE albums SET cover_path=? WHERE id=?;",
                    (cover_path, album_id))
        self.conn.commit()

    def _get_media_id(self, path: str) -> Optional[int]:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM media WHERE path=?;", (path,))
        r = cur.fetchone()
        return int(r[0]) if r else None

    def _get_or_create_album(self, title: str) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM albums WHERE title=?;", (title,))
        row = cur.fetchone()
        if row:
            return int(row[0])
        cur.execute("INSERT INTO albums(title) VALUES(?);", (title,))
        self.conn.commit()
        return int(cur.lastrowid)

    def rebuild_albums_from_media(self, roots: List[str]) -> None:
        """
        Autogenera álbumes a partir de la ruta relativa a cada raíz.
        Ej.: .../Amigos/Cumpleaños/Carlos 2025/archivo.jpg -> "Amigos - Cumpleaños - Carlos 2025"
        """
        cur = self.conn.cursor()
        cur.execute("SELECT id, path, thumb_path FROM media;")
        rows = cur.fetchall()
        # normaliza raíces para matching robusto
        nroots = []
        for r in roots:
            rp = Path(r)
            nroots.append(str(rp.resolve()).replace("\\", "/").lower() + "/")

        for mid, mpath, mthumb in rows:
            pnorm = str(Path(mpath).resolve()).replace("\\", "/").lower()
            best_rel = None
            for base in nroots:
                if pnorm.startswith(base):
                    rel = pnorm[len(base):]
                    best_rel = rel
                    break
            if not best_rel:
                continue
            parent_dir = os.path.dirname(best_rel)
            if not parent_dir:
                continue
            parts = [x for x in Path(parent_dir).parts if x]
            if not parts:
                continue
            title = " - ".join(parts)  # puedes limitar niveles si deseas

            album_id = self._get_or_create_album(title)
            # vínculo (si no existe)
            cur.execute("""
                INSERT OR IGNORE INTO album_media(album_id, media_id, position)
                VALUES (?, ?, 0);
            """, (album_id, mid))

            # portada por defecto si no hay
            cur.execute(
                "SELECT cover_path FROM albums WHERE id=?;", (album_id,))
            cover = cur.fetchone()
            if cover and (cover[0] is None) and mthumb:
                cur.execute(
                    "UPDATE albums SET cover_path=? WHERE id=?;", (mthumb, album_id))

        self.conn.commit()
