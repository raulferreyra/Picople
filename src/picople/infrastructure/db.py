from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List

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
      - albums(id, title UNIQUE, cover_path, folder_key UNIQUE-ish)
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
        esc = passphrase.replace("'", "''")
        cur.execute(f"PRAGMA key = '{esc}';")
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
                    cover_path TEXT,
                    folder_key TEXT
                );
            """)
        self._add_column_if_missing("albums", "folder_key", "TEXT")
        # Índice único robusto: intenta con WHERE ... NOT NULL (si versión soporta) y fallback sin WHERE
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_folder_key ON albums(folder_key) WHERE folder_key IS NOT NULL;"
            )
        except Exception:
            try:
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_folder_key ON albums(folder_key);"
                )
            except Exception:
                pass

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

    def _normalize_rel(self, rel: str) -> str:
        # normaliza separadores, caso y quita slashes inicial/final
        return rel.replace("\\", "/").strip("/").lower()

    def _roots_normalized(self, roots: list[str]) -> list[str]:
        n = []
        for r in roots:
            rp = Path(r)
            n.append(str(rp.resolve()).replace(
                "\\", "/").lower().rstrip("/") + "/")
        return n

    def _folder_key_from_path(self, abs_path: str, nroots: List[str]) -> Optional[str]:
        """
        Devuelve la ruta relativa del directorio contenedor (carpeta del álbum)
        tomando la RAÍZ MÁS LARGA que haga match (para raíces superpuestas).
        Normaliza a minúsculas y '/'.
        """
        pnorm = str(Path(abs_path).resolve()).replace("\\", "/").lower()
        base_match = None
        best_len = -1
        for base in nroots:
            if pnorm.startswith(base) and len(base) > best_len:
                base_match = base
                best_len = len(base)
        if base_match is None:
            return None
        rel = pnorm[len(base_match):]
        parent_dir = os.path.dirname(rel)  # ej: amigos/cumpleaños/carlos 2025
        if not parent_dir:
            return None
        return self._normalize_rel(parent_dir)

    def _default_title_from_folder_key(self, folder_key: str) -> str:
        # "amigos/cumpleaños/carlos 2025" -> "Amigos - Cumpleaños - Carlos 2025"
        parts = [p for p in folder_key.split("/") if p]
        titled = [p[:1].upper() + p[1:] if p else p for p in parts]
        return " - ".join(titled) if titled else "(Sin título)"

    def _get_or_create_album_by_key(self, folder_key: str, default_title: str) -> int:
        cur = self.conn.cursor()
        # 1) ¿ya existe por folder_key?
        cur.execute("SELECT id FROM albums WHERE folder_key=?;", (folder_key,))
        row = cur.fetchone()
        if row:
            return int(row[0])

        # 2) Compatibilidad: ¿álbum antiguo con título autogenerado?
        cur.execute(
            "SELECT id, folder_key FROM albums WHERE title=?;", (default_title,))
        row = cur.fetchone()
        if row:
            aid = int(row[0])
            if row[1] is None:
                cur.execute(
                    "UPDATE albums SET folder_key=? WHERE id=?;", (folder_key, aid))
                self.conn.commit()
            return aid

        # 3) Crear uno nuevo
        cur.execute("INSERT INTO albums(title, folder_key) VALUES(?, ?);",
                    (default_title, folder_key))
        self.conn.commit()
        return int(cur.lastrowid)

    def rename_album(self, album_id: int, new_title: str) -> None:
        cur = self.conn.cursor()
        cur.execute("UPDATE albums SET title=? WHERE id=?;",
                    (new_title, album_id))
        self.conn.commit()

    def dedupe_albums_by_folder_key(self) -> None:
        """
        Une álbumes duplicados con el mismo folder_key.
        Conserva el de menor id; migra medias y portada; borra duplicados.
        (Usado como pasada extra de seguridad.)
        """
        cur = self.conn.cursor()
        cur.execute("""
                SELECT folder_key, GROUP_CONCAT(id)
                FROM albums
                WHERE folder_key IS NOT NULL
                GROUP BY folder_key
                HAVING COUNT(*) > 1;
            """)
        groups = cur.fetchall()
        for folder_key, idlist in groups:
            ids = [int(x) for x in str(idlist).split(",") if x]
            if len(ids) < 2:
                continue
            ids.sort()
            keep = ids[0]
            for dup in ids[1:]:
                # move media links
                cur.execute("""
                        INSERT OR IGNORE INTO album_media(album_id, media_id, position)
                        SELECT ?, media_id, position FROM album_media WHERE album_id=?;
                    """, (keep, dup))
                # adopt cover if keep has none
                cur.execute(
                    "SELECT cover_path FROM albums WHERE id=?;", (keep,))
                kcover = cur.fetchone()
                cur.execute(
                    "SELECT cover_path FROM albums WHERE id=?;", (dup,))
                dcover = cur.fetchone()
                if kcover and dcover and (kcover[0] is None) and (dcover[0] is not None):
                    cur.execute(
                        "UPDATE albums SET cover_path=? WHERE id=?;", (dcover[0], keep))
                # delete dup
                cur.execute(
                    "DELETE FROM album_media WHERE album_id=?;", (dup,))
                cur.execute("DELETE FROM albums WHERE id=?;", (dup,))
        self.conn.commit()

    # -------------------- Reconstrucción por carpetas -------------------- #
    def rebuild_albums_from_media(self, roots: List[str]) -> None:
        """
        Autogenera álbumes a partir de la **carpeta** del media (llave estable folder_key),
        sin alterar títulos existentes. Completa folder_key cuando falte.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT id, path, thumb_path FROM media;")
        rows = cur.fetchall()

        nroots = self._roots_normalized(roots)

        for mid, mpath, mthumb in rows:
            folder_key = self._folder_key_from_path(mpath, nroots)
            if not folder_key:
                continue

            default_title = self._default_title_from_folder_key(folder_key)

            # Si la media ya está en algún álbum, reutiliza ese álbum y completa folder_key si falta
            cur.execute(
                "SELECT album_id FROM album_media WHERE media_id=? LIMIT 1;", (mid,))
            link = cur.fetchone()
            if link:
                album_id = int(link[0])
                cur.execute(
                    "SELECT folder_key FROM albums WHERE id=?;", (album_id,))
                fkey = cur.fetchone()
                if fkey and fkey[0] is None:
                    cur.execute(
                        "UPDATE albums SET folder_key=? WHERE id=?;", (folder_key, album_id))
                    self.conn.commit()
            else:
                album_id = self._get_or_create_album_by_key(
                    folder_key, default_title)

            # vincula media -> álbum
            cur.execute("""
                    INSERT OR IGNORE INTO album_media(album_id, media_id, position)
                    VALUES (?, ?, 0);
                """, (album_id, mid))

            # portada por defecto si no tiene
            cur.execute(
                "SELECT cover_path FROM albums WHERE id=?;", (album_id,))
            cover = cur.fetchone()
            if cover and (cover[0] is None) and mthumb:
                cur.execute(
                    "UPDATE albums SET cover_path=? WHERE id=?;", (mthumb, album_id))

        self.conn.commit()

        # Pasada extra para unir duplicados residuales
        self.dedupe_albums_by_folder_key()

    # -------------------- Reparación “a posteriori” -------------------- #
    def _infer_folder_key_for_album(self, album_id: int, nroots: list[str]) -> Optional[str]:
        """
        Folder_key canónico deducido de las medias del álbum (usa raíz más larga).
        """
        cur = self.conn.cursor()
        cur.execute("""
                SELECT m.path
                FROM album_media am
                JOIN media m ON m.id = am.media_id
                WHERE am.album_id = ?;
            """, (album_id,))
        rows = cur.fetchall()
        if not rows:
            return None
        counts: dict[str, int] = {}
        for (path,) in rows:
            fk = self._folder_key_from_path(path, nroots)
            if fk:
                counts[fk] = counts.get(fk, 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def repair_albums(self, roots: list[str]) -> None:
        """
        Repara álbumes existentes:
          1) Calcula un folder_key CANÓNICO por álbum (inferido de sus medias) usando la raíz más larga.
          2) Agrupa por ese folder_key y fusiona duplicados:
             - Conserva el de título PERSONALIZADO (distinto del título por defecto).
             - Si ninguno es personalizado, conserva el de id menor.
             - Migra medias y portada, borra duplicados.
          3) Establece el folder_key canónico en el álbum que se conserva.
          4) Elimina álbumes VACÍOS (sin medias).
          5) Reintenta crear el índice único de folder_key.
        """
        cur = self.conn.cursor()
        nroots = self._roots_normalized(roots)

        # Cargar álbumes
        cur.execute("SELECT id, title, folder_key, cover_path FROM albums;")
        albums = {int(r[0]): {"title": r[1], "folder_key": r[2],
                              "cover": r[3]} for r in cur.fetchall()}

        # 1) Calcular folder_key CANÓNICO por álbum (no confiamos en el guardado)
        canon_fk: dict[int, Optional[str]] = {}
        for aid in list(albums.keys()):
            fk_inf = self._infer_folder_key_for_album(aid, nroots)
            canon_fk[aid] = fk_inf

        # 2) Agrupar por folder_key canónico
        groups: dict[str, list[int]] = {}
        for aid, fk in canon_fk.items():
            if not fk:
                continue
            groups.setdefault(fk, []).append(aid)

        # Fusión por grupo
        for fk, ids in groups.items():
            if len(ids) < 2:
                # Si el álbum único no tiene folder_key guardado, fija el canónico
                aid = ids[0]
                if albums[aid]["folder_key"] != fk:
                    try:
                        cur.execute(
                            "UPDATE albums SET folder_key=? WHERE id=?;", (fk, aid))
                        albums[aid]["folder_key"] = fk
                    except Exception:
                        pass
                continue

            # Regla de conservación
            default_title = self._default_title_from_folder_key(fk)
            custom = [aid for aid in ids if albums[aid]
                      ["title"] != default_title]
            keep = min(custom) if custom else min(ids)

            # Fusionar el resto
            for dup in ids:
                if dup == keep:
                    continue
                # mover vínculos (evita duplicar por PK)
                cur.execute("""
                        INSERT OR IGNORE INTO album_media(album_id, media_id, position)
                        SELECT ?, media_id, position FROM album_media WHERE album_id=?;
                    """, (keep, dup))
                # portada: adopta si keep no tiene y dup sí
                if albums[keep]["cover"] is None and albums[dup]["cover"] is not None:
                    cur.execute(
                        "UPDATE albums SET cover_path=? WHERE id=?;", (albums[dup]["cover"], keep))
                    albums[keep]["cover"] = albums[dup]["cover"]
                # borrar vínculos y el duplicado
                cur.execute(
                    "DELETE FROM album_media WHERE album_id=?;", (dup,))
                cur.execute("DELETE FROM albums WHERE id=?;", (dup,))
                albums.pop(dup, None)

            # asegurar folder_key guardado = canónico
            if albums[keep]["folder_key"] != fk:
                try:
                    cur.execute(
                        "UPDATE albums SET folder_key=? WHERE id=?;", (fk, keep))
                    albums[keep]["folder_key"] = fk
                except Exception:
                    pass

        # 4) Eliminar álbumes VACÍOS
        cur.execute("""
                DELETE FROM albums
                WHERE id IN (
                    SELECT a.id
                    FROM albums a
                    LEFT JOIN album_media am ON am.album_id = a.id
                    WHERE am.album_id IS NULL
                );
            """)

        # 5) Reintentar índice único
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_folder_key ON albums(folder_key) WHERE folder_key IS NOT NULL;"
            )
        except Exception:
            try:
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_folder_key ON albums(folder_key);"
                )
            except Exception:
                pass

        self.conn.commit()

    # -------------------- Debug opcional -------------------- #
    def debug_albums_snapshot(self) -> list[tuple]:
        cur = self.conn.cursor()
        cur.execute("""
                SELECT a.id, a.title, a.folder_key,
                       (SELECT COUNT(*) FROM album_media am WHERE am.album_id = a.id) AS items
                FROM albums a
                ORDER BY COALESCE(a.folder_key, ''), a.id;
            """)
        return cur.fetchall()
