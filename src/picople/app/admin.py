from __future__ import annotations
import argparse
from getpass import getpass
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
    # asegura/migra esquema de personas/caras
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
    # Borrar recortes antiguos (si existieran)
    faces_dir = app_data_dir() / "faces"
    avatars_dir = app_data_dir() / "avatars"

    if faces_dir.exists():
        rmtree(faces_dir, ignore_errors=True)
        log("Faces cache borrada:", faces_dir)
    else:
        log("Faces cache no existe:", faces_dir)

    if avatars_dir.exists():
        rmtree(avatars_dir, ignore_errors=True)
        log("Avatars cache borrada:", avatars_dir)
    else:
        log("Avatars cache no existe:", avatars_dir)

    return 0


def cmd_wipe_all(args) -> int:
    rc1 = cmd_wipe_people(argparse.Namespace(
        vacuum=getattr(args, "vacuum", False)))
    rc2 = cmd_wipe_faces_cache(args)
    return rc1 or rc2


def cmd_reset_covers(args) -> int:
    """Limpia cover_path de todas las personas (para forzar re‐generación)."""
    pw = _prompt_key()
    db = _open_db_and_migrate(pw)
    try:
        db.conn.execute("UPDATE persons SET cover_path=NULL;")
        db.conn.commit()
        print("[covers] cover_path limpiado en todas las personas")
        return 0
    finally:
        try:
            db.conn.close()
        except Exception:
            pass


def cmd_regen_avatars(args) -> int:
    """
    Regenera portadas de personas desde sugerencias/caras.
    - --force       : primero limpia cover_path (como reset-covers)
    - --wipe-cache  : borra carpeta de avatars antes de regenerar
    """
    pw = _prompt_key()
    if getattr(args, "wipe_cache", False):
        avatars_dir = app_data_dir() / "avatars"
        if avatars_dir.exists():
            rmtree(avatars_dir, ignore_errors=True)
            log("Avatars cache borrada:", avatars_dir)

    db = _open_db_and_migrate(pw)
    try:
        if getattr(args, "force", False):
            db.conn.execute("UPDATE persons SET cover_path=NULL;")
            db.conn.commit()
            print("[covers] cover_path limpiado (--force)")

        store = PeopleStore(db)
        cur = db.conn.cursor()
        cur.execute("SELECT id FROM persons;")
        for (pid,) in cur.fetchall():
            # intenta con sugerencias; si no hay, usa una cara confirmada
            path = store.ensure_cover_if_missing(
                pid) or store.generate_cover_for_person(pid)
            if path:
                print(f"[avatars] person {pid} -> {path}")
        return 0
    finally:
        try:
            db.conn.close()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="picople-admin", description="Utilidades de mantenimiento Picople")
    sub = p.add_subparsers(dest="cmd", required=True)

    wpp = sub.add_parser("wipe-people",
                         help="Borra personas/caras/sugerencias y estado de escaneo")
    wpp.add_argument("--vacuum", action="store_true",
                     help="Compactar la base tras borrar")
    wpp.set_defaults(func=cmd_wipe_people)

    wfc = sub.add_parser("wipe-faces-cache",
                         help="Borra cachés de recortes de rostro/avatars")
    wfc.set_defaults(func=cmd_wipe_faces_cache)

    wall = sub.add_parser("wipe-all",
                          help="Wipe people + cachés de rostros")
    wall.add_argument("--vacuum", action="store_true",
                      help="Compactar la base tras borrar")
    wall.set_defaults(func=cmd_wipe_all)

    rc = sub.add_parser("reset-covers",
                        help="Pone cover_path = NULL en todas las personas")
    rc.set_defaults(func=cmd_reset_covers)

    sp = sub.add_parser("regen-avatars",
                        help="Regenera portadas de personas desde caras/sugerencias")
    sp.add_argument("--force", action="store_true",
                    help="Limpiar cover_path antes de regenerar")
    sp.add_argument("--wipe-cache", action="store_true",
                    help="Borrar carpeta de avatars antes de regenerar")
    sp.set_defaults(func=cmd_regen_avatars)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
