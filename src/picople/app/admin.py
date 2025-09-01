# src/picople/app/admin.py
from __future__ import annotations
import argparse
from getpass import getpass
from pathlib import Path
from shutil import rmtree

from picople.core.log import log
from picople.core.paths import app_data_dir
from picople.infrastructure.db import Database
from picople.infrastructure.people_store import PeopleStore


def _prompt_key() -> str:
    pw = getpass("Clave de la base: ")
    if not pw:
        raise SystemExit(2)
    return pw


def _table_exists(conn, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;", (name,)
    )
    return cur.fetchone() is not None


def _delete_all(conn, table: str) -> None:
    if _table_exists(conn, table):
        conn.execute(f"DELETE FROM {table};")
        log("admin:", f"TRUNCATE {table}")
    else:
        log("admin:", f"tabla no existe (skip) {table}")


def _open_db_and_migrate(pw: str) -> Database:
    db_path = app_data_dir() / "db" / "picople.db"
    db = Database(db_path)
    db.open(pw)
    # Inicializa/migra esquema de personas/caras si hiciera falta
    try:
        PeopleStore(db)  # dispara _ensure_schema()
    except Exception as e:
        log("admin: PeopleStore init (para migrar) lanzó:", e)
    return db


# ──────────────────────────────────────────────────────────────────────────────
# Comandos
# ──────────────────────────────────────────────────────────────────────────────

def cmd_wipe_people(args) -> int:
    pw = _prompt_key()
    db = _open_db_and_migrate(pw)
    conn = db.conn

    log("Vaciando datos de Personas/Caras/Sugerencias…")
    conn.execute("BEGIN;")
    # el orden importa por FKs
    for t in ("person_face", "face_suggestions", "faces",
              "person_alias", "persons", "face_scan_state"):
        _delete_all(conn, t)
    conn.execute("COMMIT;")

    if getattr(args, "vacuum", False):
        try:
            conn.execute("VACUUM;")
            log("VACUUM ok")
        except Exception as e:
            log("VACUUM error:", e)
    return 0


def cmd_wipe_faces_cache(args) -> int:
    faces_dir = app_data_dir() / "faces"
    if faces_dir.exists():
        rmtree(faces_dir, ignore_errors=True)
        log("Faces cache borrada:", faces_dir)
    else:
        log("Faces cache no existe:", faces_dir)
    return 0


def cmd_wipe_all(args) -> int:
    # Limpia tablas de personas/caras y cache asociada
    rc1 = cmd_wipe_people(argparse.Namespace(
        vacuum=getattr(args, "vacuum", False)))
    rc2 = cmd_wipe_faces_cache(args)
    return rc1 or rc2


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="picople-admin", description="Utilidades de mantenimiento Picople")
    sub = p.add_subparsers(dest="cmd", required=True)

    wpp = sub.add_parser(
        "wipe-people", help="Borra personas/caras/sugerencias y estado de escaneo")
    wpp.add_argument("--vacuum", action="store_true",
                     help="Compactar la base tras borrar")
    wpp.set_defaults(func=cmd_wipe_people)

    wfc = sub.add_parser("wipe-faces-cache",
                         help="Borra cache de recortes de rostro")
    wfc.set_defaults(func=cmd_wipe_faces_cache)

    wall = sub.add_parser("wipe-all", help="Wipe people + cache de rostros")
    wall.add_argument("--vacuum", action="store_true",
                      help="Compactar la base tras borrar")
    wall.set_defaults(func=cmd_wipe_all)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
