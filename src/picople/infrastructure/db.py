# src/picople/infrastructure/db.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple

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


class Database:
    """
    Gestor de DB cifrada con SQLCipher.
    - Requiere `sqlcipher3-binary` o `pysqlcipher3`.
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
                "No se encontró SQLCipher. Instala 'sqlcipher3-binary' (recomendado) o 'pysqlcipher3'."
            )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = _sqlcipher_mod.connect(str(self.db_path))
        cur = self.conn.cursor()

        # Clave y configuración segura (algunas PRAGMAs pueden no existir según build; se ignoran).
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
        # Rutas de raíz (además de QSettings podremos persistir aquí si lo deseas luego)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE
            );
        """)
        # Medios indexados
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
        # Índices
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_mtime ON media(mtime);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_kind  ON media(kind);")

    # ---------------- Upsert ---------------- #
    def upsert_media(self, path: str, kind: str, mtime: int, size: int, thumb_path: Optional[str]) -> None:
        cur = self.conn.cursor()
        try:
            # UPSERT (si la versión lo soporta)
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
            # Fallback: update/insert en dos pasos
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
        """
        cur = self.conn.cursor()
        # Export SQLCipher: attach destino con clave y export
        cur.execute(f"ATTACH DATABASE ? AS backup KEY ?;",
                    (str(dest_path), passphrase))
        cur.execute("SELECT sqlcipher_export('backup');")
        cur.execute("DETACH DATABASE backup;")
        self.conn.commit()
