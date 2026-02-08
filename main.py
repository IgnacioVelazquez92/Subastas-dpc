# main.py
from __future__ import annotations

import argparse
from pathlib import Path

from app.db.database import Database
from app.core.app_runtime import AppRuntime
from app.ui.app import App


def bootstrap_db() -> Database:
    project_root = Path(__file__).resolve().parent
    db_path = project_root / "data" / "monitor.db"
    schema_path = project_root / "app" / "db" / "schema.sql"

    db = Database(db_path)
    db.init_schema(schema_path)
    return db


def main():
    parser = argparse.ArgumentParser(
        description="Monitor de Subastas - Con escenarios JSON (sin datos hardcodeados)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["MOCK", "PLAYWRIGHT"],
        default="MOCK",
        help="Modo: MOCK (simulación con JSON) o PLAYWRIGHT (navegador real)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        required=False,
        help="(Solo MOCK) Path a JSON de escenario - ej: data/test_scenarios/scenario_controlled_real.json",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecutar Playwright en modo headless (solo para modo PLAYWRIGHT)",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=1.0,
        help="Intervalo entre polling en segundos (default: 1.0)",
    )
    args = parser.parse_args()

    # Validar escenario solo en modo MOCK
    scenario_path = None
    if args.mode == "MOCK":
        if not args.scenario:
            parser.error("❌ --scenario es requerido en modo MOCK")
        scenario_path = Path(args.scenario)
        if not scenario_path.exists():
            parser.error(f"❌ Escenario no encontrado: {scenario_path}")

    db = bootstrap_db()

    runtime = AppRuntime(
        db=db,
        mode=args.mode,
        headless=args.headless,
        poll_seconds=args.poll_seconds,
        autostart_collector=False if args.mode == "PLAYWRIGHT" else True,
        scenario_path=str(scenario_path) if scenario_path else None,
    )
    handles = runtime.start()

    app = App(handles=handles)

    def _on_close():
        try:
            runtime.stop()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", _on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
