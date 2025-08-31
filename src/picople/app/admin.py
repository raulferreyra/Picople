# src/picople/app/admin.py
from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
from typing import Iterable

from picople.core.paths import app_data_dir
from picople.core.log import log
from picople.infrastructure.db import Database


def default_db_path() -> Path:
    return app_data_dir() / "db" / "picople.db"


def open_db(db_path: Path, key: str) -> Database:
    db = Database(db_path)
    db.open(key)
    return db


def _ask_key(passed: str | None) -> str:
    return passed if passed else getpass("Clave de la base: ")


def cmd_info(args) -> int:
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    db = open_db(db_path, key)
    cur = db.conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tabs = [r[0] for r in cur.fetchall()]
    print(f"DB: {db_path}")
    for t in sorted(tabs):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t};")
            n = cur.fetchone()[0]
        except Exception as e:
            n = f"error: {e}"
        print(f"  • {t:24} {n}")
    return 0


def cmd_wipe_people(args) -> int:
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    db = open_db(db_path, key)
    log("Vaciando tablas de People…")
    db.conn.executescript("""
        DELETE FROM person_face;
        DELETE FROM face_suggestions;
        DELETE FROM faces;
        DELETE FROM person_alias;
        DELETE FROM persons;
        DELETE FROM face_scan_state;
    """)
    db.conn.commit()
    if args.vacuum:
        db.conn.execute("VACUUM;")
        db.conn.commit()
        log("VACUUM listo.")
    log("Wipe People listo.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m picople.app.admin", description="Herramientas de mantenimiento Picople")
    p.add_argument(
        "--db", help="Ruta de la base (por defecto, la del perfil).")
    p.add_argument("--key", help="Clave de la base.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Listar tablas y conteos").set_defaults(
        func=cmd_info)

    wp = sub.add_parser(
        "wipe-people", help="Vaciar datos de Personas/Caras/Sugerencias")
    wp.add_argument("--vacuum", action="store_true",
                    help="Ejecutar VACUUM al terminar")
    wp.set_defaults(func=cmd_wipe_people)
    return p


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
