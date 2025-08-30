# src/picople/app/admin.py
from __future__ import annotations

import argparse
import re
import sys
from getpass import getpass
from pathlib import Path
from typing import Iterable

from picople.core.paths import app_data_dir
from picople.core.log import log
from picople.infrastructure.db import Database

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

SAFE_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_db_path() -> Path:
    return app_data_dir() / "db" / "picople.db"


def open_db(db_path: Path, key: str) -> Database:
    db = Database(db_path)
    db.open(key)
    return db


def _ask_key(args_key: str | None, prompt: str = "Clave de la base: ") -> str:
    if args_key:
        return args_key
    return getpass(prompt)


def _confirm(token: str, msg: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    print(msg)
    typed = input(f'Escribe exactamente "{token}" para continuar: ').strip()
    return typed == token


def _tables(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'android_%';"
    )
    return [r[0] for r in cur.fetchall()]


def _executescript(conn, sql: str) -> None:
    cur = conn.cursor()
    cur.executescript(sql)
    conn.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Comandos
# ──────────────────────────────────────────────────────────────────────────────

def cmd_info(args) -> int:
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    db = open_db(db_path, key)
    tabs = _tables(db.conn)
    print(f"\nDB: {db_path}")
    print(f"Tablas ({len(tabs)}):")
    cur = db.conn.cursor()
    for t in sorted(tabs):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t};")
            n = cur.fetchone()[0]
        except Exception as e:
            n = f"error: {e}"
        print(f"  • {t:24} {n}")
    return 0


def cmd_vacuum(args) -> int:
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    db = open_db(db_path, key)
    log("VACUUM…")
    db.conn.execute("VACUUM;")
    db.conn.commit()
    log("VACUUM listo.")
    return 0


def cmd_purge(args) -> int:
    """Elimina el archivo de la base y crea una nueva vacía (con la misma clave u otra)."""
    db_path = Path(args.db or default_db_path())

    if not _confirm("PURGE", f"⚠️  Esto BORRARÁ el archivo: {db_path}", args.yes):
        log("Purge cancelado.")
        return 2

    if db_path.exists():
        db_path.unlink()
        log("Archivo DB eliminado:", db_path)

    # Crear base vacía otra vez
    key = _ask_key(args.key, "Clave para la nueva base: ")
    db = Database(db_path)
    db.open(key)
    log("Base recreada vacía:", db_path)
    return 0


def cmd_wipe_people(args) -> int:
    """
    Limpia TODO lo relacionado a Personas/Caras/Sugerencias/Estado de escaneo.
    Si usas --drop, DROP TABLE y se recreará en el próximo arranque.
    """
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    db = open_db(db_path, key)

    if not _confirm("WIPE", "⚠️  Esto vaciará los datos de PERSONAS/CARAS.", args.yes):
        log("Wipe cancelado.")
        return 2

    if args.drop:
        sql = """
        DROP TABLE IF EXISTS person_face;
        DROP TABLE IF EXISTS face_suggestions;
        DROP TABLE IF EXISTS faces;
        DROP TABLE IF EXISTS person_alias;
        DROP TABLE IF EXISTS persons;
        DROP TABLE IF EXISTS face_scan_state;
        """
        log("Eliminando tablas de People (DROP)…")
        _executescript(db.conn, sql)
    else:
        sql = """
        DELETE FROM person_face;
        DELETE FROM face_suggestions;
        DELETE FROM faces;
        DELETE FROM person_alias;
        DELETE FROM persons;
        DELETE FROM face_scan_state;
        """
        log("Vaciando tablas de People (DELETE)…")
        _executescript(db.conn, sql)

    if args.vacuum:
        db.conn.execute("VACUUM;")
        db.conn.commit()
        log("VACUUM listo.")

    log("Wipe People listo.")
    return 0


def cmd_wipe_table(args) -> int:
    """
    Vacía una tabla concreta (DELETE) o la elimina (DROP con --drop).
    """
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    table = args.table.strip()

    if not SAFE_TABLE_RE.match(table):
        print("Nombre de tabla inválido.")
        return 3

    db = open_db(db_path, key)

    tabs = set(_tables(db.conn))
    if table not in tabs:
        print(f"La tabla '{table}' no existe en esta base.")
        return 4

    if not _confirm("YES", f"⚠️  Esto afectará a la tabla: {table}", args.yes):
        log("Operación cancelada.")
        return 2

    cur = db.conn.cursor()
    if args.drop:
        log(f"Dropping tabla {table}…")
        cur.execute(f"DROP TABLE IF EXISTS {table};")
    else:
        log(f"Deleting filas de {table}…")
        cur.execute(f"DELETE FROM {table};")
    db.conn.commit()

    if args.vacuum:
        db.conn.execute("VACUUM;")
        db.conn.commit()
        log("VACUUM listo.")

    log("Operación sobre tabla completada.")
    return 0


def cmd_wipe_all(args) -> int:
    """
    Limpia TODAS las tablas (excepto internas). Útil si quieres preservar el archivo/clave.
    """
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    db = open_db(db_path, key)

    if not _confirm("WIPE-ALL", "⚠️  Esto vaciará TODAS las tablas de usuario.", args.yes):
        log("Wipe-all cancelado.")
        return 2

    tabs = [t for t in _tables(db.conn)]
    if args.drop:
        log("DROP de todas las tablas de usuario…")
        for t in tabs:
            db.conn.execute(f"DROP TABLE IF EXISTS {t};")
    else:
        log("DELETE de todas las tablas de usuario…")
        for t in tabs:
            try:
                db.conn.execute(f"DELETE FROM {t};")
            except Exception as e:
                log(f"Saltando {t}: {e}")
    db.conn.commit()

    if args.vacuum:
        db.conn.execute("VACUUM;")
        db.conn.commit()
        log("VACUUM listo.")

    log("Wipe-all listo.")
    return 0


def cmd_migrate(args) -> int:
    """
    Fuerza migraciones mínimas (creación de tablas/columnas) para el módulo People.
    Útil tras un DROP, sin necesidad de abrir la app.
    """
    db_path = Path(args.db or default_db_path())
    key = _ask_key(args.key)
    db = open_db(db_path, key)

    try:
        from picople.infrastructure.people_store import PeopleStore
        PeopleStore(db)  # __init__ ya asegura el esquema
        log("Migraciones People aplicadas/aseguradas.")
    except Exception as e:
        log("Error ejecutando migraciones People:", e)
        return 1
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m picople.app.admin",
        description="Utilidades de mantenimiento para la base de Picople."
    )
    p.add_argument(
        "--db", help="Ruta de la base (por defecto, la del perfil actual).")
    p.add_argument(
        "--key", help="Clave de la base (si se omite, se solicitará).")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Muestra tablas y conteos.").set_defaults(
        func=cmd_info)
    sub.add_parser("vacuum", help="Ejecuta VACUUM.").set_defaults(
        func=cmd_vacuum)

    pg = sub.add_parser(
        "purge", help="Borra el archivo de DB y crea uno vacío.")
    pg.add_argument("--yes", action="store_true",
                    help="No preguntar confirmación.")
    pg.set_defaults(func=cmd_purge)

    wp = sub.add_parser(
        "wipe-people", help="Vacía (o elimina) tablas relacionadas a Personas/Caras.")
    wp.add_argument("--drop", action="store_true",
                    help="DROP TABLE en lugar de DELETE.")
    wp.add_argument("--vacuum", action="store_true",
                    help="Ejecutar VACUUM al terminar.")
    wp.add_argument("--yes", action="store_true",
                    help="No preguntar confirmación.")
    wp.set_defaults(func=cmd_wipe_people)

    wt = sub.add_parser(
        "wipe-table", help="Vacía o elimina una tabla concreta.")
    wt.add_argument("table", help="Nombre de la tabla.")
    wt.add_argument("--drop", action="store_true",
                    help="DROP TABLE en lugar de DELETE.")
    wt.add_argument("--vacuum", action="store_true",
                    help="Ejecutar VACUUM al terminar.")
    wt.add_argument("--yes", action="store_true",
                    help="No preguntar confirmación.")
    wt.set_defaults(func=cmd_wipe_table)

    wa = sub.add_parser(
        "wipe-all", help="Vacía/elimina todas las tablas de usuario.")
    wa.add_argument("--drop", action="store_true",
                    help="DROP TABLE en lugar de DELETE.")
    wa.add_argument("--vacuum", action="store_true",
                    help="Ejecutar VACUUM al terminar.")
    wa.add_argument("--yes", action="store_true",
                    help="No preguntar confirmación.")
    wa.set_defaults(func=cmd_wipe_all)

    mg = sub.add_parser(
        "migrate", help="Fuerza/asegura migraciones mínimas (People).")
    mg.set_defaults(func=cmd_migrate)

    return p


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
