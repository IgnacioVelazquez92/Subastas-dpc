# app/db/database.py
"""
Capa de acceso a SQLite (sin ORM).
Objetivos:
- Una única conexión central (thread-safe mediante Lock).
- Activar PRAGMAs recomendados (foreign_keys, WAL, busy_timeout).
- Inicializar el esquema desde app/db/schema.sql.
- Proveer métodos explícitos y simples (insert/update/get) para el dominio.

Nota importante sobre threading:
- SQLite soporta múltiples hilos si check_same_thread=False, pero se recomienda
  SERIALIZAR el acceso a la conexión con un Lock (lo hacemos acá).
- En el diseño final, idealmente el "core" es el único que escribe en DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Optional


class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Reentrant lock: permite que métodos internos se llamen entre sí sin deadlock.
        self._lock = RLock()

        # check_same_thread=False: permitimos usar la conexión desde distintos hilos,
        # pero SIEMPRE protegida por self._lock.
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )

        # Queremos filas como dict-like: row["col"]
        self._conn.row_factory = sqlite3.Row

        # PRAGMAs recomendados (aplican por conexión)
        self._apply_pragmas()

    # -------------------------
    # Setup
    # -------------------------
    def _apply_pragmas(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            # Integridad referencial real
            cur.execute("PRAGMA foreign_keys = ON;")
            # Modo WAL: mejor para lectura concurrente + writes cortos
            cur.execute("PRAGMA journal_mode = WAL;")
            # Espera si el archivo está bloqueado (ms)
            cur.execute("PRAGMA busy_timeout = 5000;")
            # Sincronización: NORMAL es buena relación performance/seguridad
            cur.execute("PRAGMA synchronous = NORMAL;")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _ensure_columns(self) -> None:
        """
        Asegura compatibilidad hacia atrás cuando el schema evoluciona.
        - Agrega columnas faltantes con ALTER TABLE.
        """
        cols = self.fetchall("PRAGMA table_info(renglon_excel)")
        existing_cols = {c[1] for c in cols}  # c[1] = name
        if "precio_referencia_subasta" not in existing_cols:
            self.execute("ALTER TABLE renglon_excel ADD COLUMN precio_referencia_subasta REAL")

    def init_schema(self, schema_path: str | Path) -> None:
        """
        Ejecuta el schema.sql (idempotente gracias a IF NOT EXISTS).
        """
        schema_path = Path(schema_path)
        sql = schema_path.read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(sql)
            self._conn.commit()
        try:
            self._ensure_columns()
        except Exception:
            # No bloqueamos el arranque si hay un edge-case de migración
            pass

    # -------------------------
    # Helpers SQL genéricos
    # -------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            self._conn.execute(sql, tuple(params))
            self._conn.commit()

    def executemany(self, sql: str, seq_of_params: Iterable[Iterable[Any]]) -> None:
        with self._lock:
            self._conn.executemany(sql, [tuple(p) for p in seq_of_params])
            self._conn.commit()

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.fetchall()

    def execute_returning_id(self, sql: str, params: Iterable[Any] = ()) -> int:
        """
        Ejecuta un INSERT y devuelve lastrowid.
        """
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return int(cur.lastrowid)

    # -------------------------
    # Operaciones de dominio (MVP)
    # -------------------------
    def upsert_subasta(self, *, id_cot: str, url: str) -> int:
        """
        Crea (si no existe) una subasta por id_cot. Devuelve subasta.id (PK).
        """
        row = self.fetchone("SELECT id FROM subasta WHERE id_cot = ?", (id_cot,))
        if row:
            # actualizar url por si cambió
            self.execute("UPDATE subasta SET url = ? WHERE id = ?", (url, row["id"]))
            return int(row["id"])

        return self.execute_returning_id(
            "INSERT INTO subasta (id_cot, url) VALUES (?, ?)",
            (id_cot, url),
        )

    def set_subasta_estado(
        self,
        *,
        subasta_id: int,
        estado: str,
        last_ok_at: str | None = None,
        last_http_code: int | None = None,
        err_streak: int | None = None,
        ended_at: str | None = None,
    ) -> None:
        """
        Actualiza campos operativos de la subasta.
        """
        fields = ["estado = ?"]
        params: list[Any] = [estado]

        if last_ok_at is not None:
            fields.append("last_ok_at = ?")
            params.append(last_ok_at)

        if last_http_code is not None:
            fields.append("last_http_code = ?")
            params.append(int(last_http_code))

        if err_streak is not None:
            fields.append("err_streak = ?")
            params.append(int(err_streak))

        if ended_at is not None:
            fields.append("ended_at = ?")
            params.append(ended_at)

        params.append(subasta_id)

        sql = f"UPDATE subasta SET {', '.join(fields)} WHERE id = ?"
        self.execute(sql, params)

    def get_subasta_id_by_id_cot(self, *, id_cot: str) -> int | None:
        row = self.fetchone("SELECT id FROM subasta WHERE id_cot = ?", (id_cot,))
        return int(row["id"]) if row else None

    def upsert_renglon(
        self,
        *,
        subasta_id: int,
        id_renglon: str,
        descripcion: str,
        margen_minimo: str | None = None,
    ) -> int:
        """
        Inserta un renglón si no existe. Devuelve renglon.id (PK).
        """
        row = self.fetchone(
            "SELECT id FROM renglon WHERE subasta_id = ? AND id_renglon = ?",
            (subasta_id, id_renglon),
        )
        if row:
            # actualizamos descripción por si cambió (ocasionalmente cambia el texto)
            self.execute(
                "UPDATE renglon SET descripcion = ?, margen_minimo = ? WHERE id = ?",
                (descripcion, margen_minimo, row["id"]),
            )
            return int(row["id"])

        return self.execute_returning_id(
            "INSERT INTO renglon (subasta_id, id_renglon, descripcion, margen_minimo) VALUES (?, ?, ?, ?)",
            (subasta_id, id_renglon, descripcion, margen_minimo),
        )

    def get_running_subasta_id(self) -> int | None:
        row = self.fetchone("SELECT id FROM subasta WHERE estado = 'RUNNING' ORDER BY id DESC LIMIT 1")
        return int(row["id"]) if row else None

    def get_latest_subasta_id(self) -> int | None:
        row = self.fetchone("SELECT id FROM subasta ORDER BY id DESC LIMIT 1")
        return int(row["id"]) if row else None

    def get_renglon_id_by_keys(
        self,
        *,
        subasta_id: int,
        id_renglon: str,
    ) -> int | None:
        row = self.fetchone(
            "SELECT id FROM renglon WHERE subasta_id = ? AND id_renglon = ?",
            (subasta_id, id_renglon),
        )
        return int(row["id"]) if row else None

    def get_renglon_config(self, *, renglon_id: int) -> dict | None:
        row = self.fetchone(
            "SELECT costo_subtotal, oferta_mia, seguir, utilidad_min_pct, ocultar_bajo_umbral "
            "FROM renglon_config WHERE renglon_id = ?",
            (renglon_id,),
        )
        if not row:
            return None

        return {
            "costo_subtotal": row["costo_subtotal"],
            "oferta_mia": bool(row["oferta_mia"]),
            "seguir": bool(row["seguir"]),
            "utilidad_min_pct": float(row["utilidad_min_pct"]),
            "ocultar_bajo_umbral": bool(row["ocultar_bajo_umbral"]),
        }

    def fetch_export_rows(self, *, subasta_id: int) -> list[dict]:
        rows = self.fetchall(
            """
            SELECT
                s.id_cot AS id_subasta,
                r.id_renglon AS item,
                r.descripcion AS descripcion,
                e.unidad_medida AS unidad_medida,
                e.cantidad AS cantidad,
                e.marca AS marca,
                e.observaciones AS observaciones,
                e.conversion_usd AS conversion_usd,
                e.costo_usd AS costo_usd,
                e.costo_final_pesos AS costo_final_pesos,
                e.renta AS renta,
                e.precio_referencia_subasta AS precio_referencia_subasta,
                st.oferta_min AS subtotal_para_mejorar
            FROM renglon r
            JOIN subasta s ON s.id = r.subasta_id
            LEFT JOIN renglon_excel e ON e.renglon_id = r.id
            LEFT JOIN renglon_estado st ON st.renglon_id = r.id
            WHERE r.subasta_id = ?
            ORDER BY r.id_renglon
            """,
            (subasta_id,),
        )
        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "ID SUBASTA": row["id_subasta"],
                    "ITEM": row["item"],
                    "DESCRIPCION": row["descripcion"],
                    "UNIDAD DE MEDIDA": row["unidad_medida"],
                    "CANTIDAD": row["cantidad"],
                    "MARCA": row["marca"],
                    "Observaciones": row["observaciones"],
                    "CONVERSIÓN USD": row["conversion_usd"],
                    "COSTO USD": row["costo_usd"],
                    "COSTO FINAL PESOS": row["costo_final_pesos"],
                    "RENTA": row["renta"],
                    "Precio referencia": row["precio_referencia_subasta"],
                    "SUBTOTAL PARA MEJORAR": row["subtotal_para_mejorar"],
                }
            )
        return out

    def upsert_renglon_estado(
        self,
        *,
        renglon_id: int,
        mejor_txt: str | None,
        oferta_min_txt: str | None,
        presupuesto_txt: str | None,
        mejor: float | None,
        oferta_min: float | None,
        presupuesto: float | None,
        mensaje: str | None,
        updated_at: str,
    ) -> None:
        """
        Guarda el estado "actual" (1 por renglón). Si no existe, lo crea.
        """
        row = self.fetchone(
            "SELECT id FROM renglon_estado WHERE renglon_id = ?",
            (renglon_id,),
        )

        if row:
            self.execute(
                """
                UPDATE renglon_estado
                SET mejor_oferta_txt = ?,
                    oferta_min_txt   = ?,
                    presupuesto_txt  = ?,
                    mejor_oferta     = ?,
                    oferta_min       = ?,
                    presupuesto      = ?,
                    mensaje          = ?,
                    updated_at       = ?
                WHERE renglon_id = ?
                """,
                (
                    mejor_txt,
                    oferta_min_txt,
                    presupuesto_txt,
                    mejor,
                    oferta_min,
                    presupuesto,
                    mensaje,
                    updated_at,
                    renglon_id,
                ),
            )
        else:
            self.execute(
                """
                INSERT INTO renglon_estado (
                    renglon_id,
                    mejor_oferta_txt, oferta_min_txt, presupuesto_txt,
                    mejor_oferta, oferta_min, presupuesto,
                    mensaje, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    renglon_id,
                    mejor_txt,
                    oferta_min_txt,
                    presupuesto_txt,
                    mejor,
                    oferta_min,
                    presupuesto,
                    mensaje,
                    updated_at,
                ),
            )

    def get_renglon_excel(self, *, renglon_id: int) -> dict | None:
        row = self.fetchone(
            """
            SELECT
                unidad_medida, cantidad, marca, observaciones,
                conversion_usd, costo_usd, costo_final_pesos,
                renta, precio_referencia, precio_referencia_subasta
            FROM renglon_excel
            WHERE renglon_id = ?
            """,
            (renglon_id,),
        )
        if not row:
            return None

        return {
            "unidad_medida": row["unidad_medida"],
            "cantidad": row["cantidad"],
            "marca": row["marca"],
            "observaciones": row["observaciones"],
            "conversion_usd": row["conversion_usd"],
            "costo_usd": row["costo_usd"],
            "costo_final_pesos": row["costo_final_pesos"],
            "renta": row["renta"],
            "precio_referencia": row["precio_referencia"],
            "precio_referencia_subasta": row["precio_referencia_subasta"],
        }

    def upsert_renglon_excel(
        self,
        *,
        renglon_id: int,
        unidad_medida: str | None,
        cantidad: float | None,
        marca: str | None,
        observaciones: str | None,
        conversion_usd: float | None,
        costo_usd: float | None,
        costo_final_pesos: float | None,
        renta: float | None,
        precio_referencia: float | None,
        precio_referencia_subasta: float | None,
        updated_at: str,
    ) -> None:
        row = self.fetchone("SELECT id FROM renglon_excel WHERE renglon_id = ?", (renglon_id,))
        payload = (
            unidad_medida,
            cantidad,
            marca,
            observaciones,
            conversion_usd,
            costo_usd,
            costo_final_pesos,
            renta,
            precio_referencia,
            precio_referencia_subasta,
            updated_at,
            renglon_id,
        )

        if row:
            self.execute(
                """
                UPDATE renglon_excel
                SET unidad_medida = ?,
                    cantidad = ?,
                    marca = ?,
                    observaciones = ?,
                    conversion_usd = ?,
                    costo_usd = ?,
                    costo_final_pesos = ?,
                    renta = ?,
                    precio_referencia = ?,
                    precio_referencia_subasta = ?,
                    updated_at = ?
                WHERE renglon_id = ?
                """,
                payload,
            )
        else:
            self.execute(
                """
                INSERT INTO renglon_excel (
                    unidad_medida, cantidad, marca, observaciones,
                    conversion_usd, costo_usd, costo_final_pesos,
                    renta, precio_referencia, precio_referencia_subasta, updated_at, renglon_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )

    def upsert_renglon_config(
        self,
        *,
        renglon_id: int,
        costo_subtotal: float | None,
        oferta_mia: bool,
        seguir: bool,
        utilidad_min_pct: float,
        ocultar_bajo_umbral: bool,
        updated_at: str,
    ) -> None:
        """
        Guarda la configuración del usuario (1 por renglón).
        """
        row = self.fetchone("SELECT id FROM renglon_config WHERE renglon_id = ?", (renglon_id,))
        payload = (
            costo_subtotal,
            1 if oferta_mia else 0,
            1 if seguir else 0,
            float(utilidad_min_pct),
            1 if ocultar_bajo_umbral else 0,
            updated_at,
            renglon_id,
        )

        if row:
            self.execute(
                """
                UPDATE renglon_config
                SET costo_subtotal = ?,
                    oferta_mia = ?,
                    seguir = ?,
                    utilidad_min_pct = ?,
                    ocultar_bajo_umbral = ?,
                    updated_at = ?
                WHERE renglon_id = ?
                """,
                payload,
            )
        else:
            self.execute(
                """
                INSERT INTO renglon_config (
                    costo_subtotal, oferta_mia, seguir,
                    utilidad_min_pct, ocultar_bajo_umbral, updated_at,
                    renglon_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )

    def get_ui_config(self, *, key: str) -> str | None:
        row = self.fetchone("SELECT value FROM ui_config WHERE key = ?", (key,))
        return str(row["value"]) if row else None

    def set_ui_config(self, *, key: str, value: str) -> None:
        row = self.fetchone("SELECT key FROM ui_config WHERE key = ?", (key,))
        if row:
            self.execute("UPDATE ui_config SET value = ?, updated_at = datetime('now') WHERE key = ?", (value, key))
        else:
            self.execute("INSERT INTO ui_config (key, value) VALUES (?, ?)", (key, value))

    def cleanup_logs(self) -> None:
        self.execute("DELETE FROM evento")

    def cleanup_states(self) -> None:
        """Borra todos los datos de estados y renglones.
        Orden correcto para respetar foreign keys: primero hijos, luego padres.
        """
        # Desactivar temporalmente foreign keys para evitar errores
        self.execute("PRAGMA foreign_keys = OFF")
        
        # Orden correcto: primero las tablas hijas, luego las padres
        self.execute("DELETE FROM renglon_estado")  # hijo de renglon
        self.execute("DELETE FROM renglon_config")  # hijo de renglon
        self.execute("DELETE FROM renglon_excel")   # hijo de renglon
        self.execute("DELETE FROM evento")          # hijo de subasta/renglon
        self.execute("DELETE FROM renglon")         # hijo de subasta
        self.execute("DELETE FROM subasta")         # padre
        
        # Reactivar foreign keys
        self.execute("PRAGMA foreign_keys = ON")

    def cleanup_all(self) -> None:
        """Borra todos los datos incluyendo configuración de UI."""
        self.cleanup_states()
        self.execute("DELETE FROM ui_config")

    def insert_evento(
        self,
        *,
        nivel: str,
        tipo: str,
        mensaje: str,
        subasta_id: int | None = None,
        renglon_id: int | None = None,
    ) -> int:
        """
        Inserta un evento persistente (observabilidad).
        """
        return self.execute_returning_id(
            """
            INSERT INTO evento (subasta_id, renglon_id, nivel, tipo, mensaje)
            VALUES (?, ?, ?, ?, ?)
            """,
            (subasta_id, renglon_id, nivel, tipo, mensaje),
        )
