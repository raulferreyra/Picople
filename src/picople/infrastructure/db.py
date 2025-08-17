# src/picople/infrastructure/db.py
from __future__ import annotations
from pathlib import Path
from typing import Optional

# Intentamos varios módulos compatibles con SQLCipher
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


def _sql_quote(s: str) -> str:
    """Escapa comillas simples para usarlas dentro de literales SQL ('...')."""
    return s.replace("'", "''")


class Database:
    """
    Gestor de DB cifrada con SQLCipher.
    - Requiere 'sqlcipher3-wheels' (Windows) o 'pysqlcipher3'.
    - Activa WAL.
    - Esquema mínimo para metadatos de medios.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = None

    @property
    def is_open(self) -> bool:
        return self.conn is not None

    def open(self, passphrase: str) -> None:
        if _sqlcipher_mod is None:
            raise DBError(
                "No se encontró SQLCipher. Instala 'sqlcipher3-wheels' (Windows) o 'pysqlcipher3'."
            )

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = _sqlcipher_mod.connect(str(self.db_path))
        cur = self.conn.cursor()

        # PRAGMA key: NO acepta placeholders → embebemos la clave escapada
        cur.execute(f"PRAGMA key = '{_sql_quote(passphrase)}';")

        # (Opcional) parámetros de endurecimiento: pueden no existir según build
        try:
            cur.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
            cur.execute("PRAGMA kdf_iter = 256000;")
            cur.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA256;")
            cur.execute("PRAGMA cipher_page_size = 4096;")
            # Si abres DBs antiguas:
            # cur.execute("PRAGMA cipher_compatibility = 4;")
        except Exception:
            pass

        # Verificar que la clave es válida (si no, falla aquí)
        try:
            cur.execute("SELECT count(*) FROM sqlite_master;")
            cur.fetchone()
        except Exception as e:
            self.conn.close()
            self.conn = None
            raise DBError(f"Clave inválida o base de datos corrupta: {e}")

        # WAL y performance segura
        try:
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA temp_store=MEMORY;")
            cur.execute("PRAGMA mmap_size=268435456;")  # 256MB
        except Exception:
            pass

        self._ensure_schema()
        self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    # ---------------- Schema ---------------- #
    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,            -- 'image' | 'video'
                mtime INTEGER NOT NULL,
                size  INTEGER NOT NULL,
                thumb_path TEXT
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_mtime ON media(mtime);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_kind  ON media(kind);")

    # ---------------- Upsert ---------------- #
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

    # ---------------- Backup cifrado ---------------- #
    def backup_to(self, dest_path: Path, passphrase: str) -> None:
        """
        Copia cifrada de la DB usando export propio de SQLCipher.
        ATTACH ... KEY tampoco acepta placeholders.
        """
        cur = self.conn.cursor()
        d = _sql_quote(str(dest_path))
        k = _sql_quote(passphrase)
        cur.execute(f"ATTACH DATABASE '{d}' AS backup KEY '{k}';")
        cur.execute("SELECT sqlcipher_export('backup');")
        cur.execute("DETACH DATABASE backup;")
        self.conn.commit()

        # ---------------- Consultas de lectura ---------------- #
    def _build_where(self, kind: str | None, search: str | None) -> tuple[str, list]:
        clauses = []
        args: list = []
        if kind in ("image", "video"):
            clauses.append("kind = ?")
            args.append(kind)
        if search:
            clauses.append("(path LIKE ?)")
            args.append(f"%{search}%")
        if clauses:
            return "WHERE " + " AND ".join(clauses), args
        return "", args

    def count_media(self, kind: str | None = None, search: str | None = None) -> int:
        cur = self.conn.cursor()
        where, args = self._build_where(kind, search)
        cur.execute(f"SELECT COUNT(*) FROM media {where};", args)
        row = cur.fetchone()
        return int(row[0] if row and row[0] is not None else 0)

    def fetch_media_page(
        self,
        offset: int,
        limit: int,
        kind: str | None = None,      # 'image' | 'video' | None (todos)
        search: str | None = None,    # filtro por substring en path
        order_by: str = "mtime DESC",
    ) -> list[dict]:
        cur = self.conn.cursor()
        where, args = self._build_where(kind, search)
        cur.execute(
            f"""SELECT path, kind, mtime, size, thumb_path
                FROM media
                {where}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?;""",
            [*args, int(limit), int(offset)],
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "path": r[0],
                "kind": r[1],
                "mtime": int(r[2]),
                "size": int(r[3]),
                "thumb_path": r[4],
            })
        return out
