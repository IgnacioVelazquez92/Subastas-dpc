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
        
        REFACTORING: Agregamos nuevas columnas con nombres mejorados
        si la tabla existe sin ellas (para DBs existentes).
        """
        cols = self.fetchall("PRAGMA table_info(renglon_excel)")
        existing_cols = {c[1] for c in cols}  # c[1] = name
        
        # Legacy: ensure old columns exist
        if "precio_referencia_subasta" not in existing_cols:
            self.execute("ALTER TABLE renglon_excel ADD COLUMN precio_referencia_subasta REAL")
        
        # REFACTORING: Add new columns if they don't exist
        new_columns = [
            "items_por_renglon", "obs_usuario", "conv_usd", "costo_unit_usd", "costo_total_usd",
            "costo_unit_ars", "costo_total_ars", "renta_minima",
            "precio_ref_unitario", "renta_referencia", "precio_unit_aceptable",
            "precio_total_aceptable", "precio_unit_mejora", "renta_para_mejorar",
            "oferta_para_mejorar", "mejor_oferta_txt", "obs_cambio"
        ]
        
        for col in new_columns:
            if col not in existing_cols:
                col_type = "TEXT" if col in ["obs_usuario", "mejor_oferta_txt", "obs_cambio"] else "REAL"
                self.execute(f"ALTER TABLE renglon_excel ADD COLUMN {col} {col_type}")

        # Migración tabla subasta: columna mi_id_proveedor
        subasta_cols = self.fetchall("PRAGMA table_info(subasta)")
        existing_subasta_cols = {c[1] for c in subasta_cols}
        if "mi_id_proveedor" not in existing_subasta_cols:
            self.execute("ALTER TABLE subasta ADD COLUMN mi_id_proveedor TEXT")

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

    def get_mi_id_proveedor(self, *, subasta_id: int) -> str | None:
        """Devuelve el mi_id_proveedor asignado a la subasta, o None."""
        row = self.fetchone("SELECT mi_id_proveedor FROM subasta WHERE id = ?", (subasta_id,))
        return str(row["mi_id_proveedor"]) if row and row["mi_id_proveedor"] else None

    def set_mi_id_proveedor(self, *, subasta_id: int, mi_id_proveedor: str | None) -> None:
        """Guarda (o borra) el mi_id_proveedor de la subasta."""
        self.execute(
            "UPDATE subasta SET mi_id_proveedor = ? WHERE id = ?",
            (mi_id_proveedor, subasta_id),
        )

    def get_mi_id_proveedor_by_id_cot(self, *, id_cot: str) -> str | None:
        """Devuelve mi_id_proveedor buscando por id_cot."""
        row = self.fetchone(
            "SELECT mi_id_proveedor FROM subasta WHERE id_cot = ?", (id_cot,)
        )
        return str(row["mi_id_proveedor"]) if row and row["mi_id_proveedor"] else None

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
        """Exporta renglones con todos los campos nuevos (refactorizado)."""
        rows = self.fetchall(
            """
            SELECT
                s.id_cot AS id_subasta,
                r.id_renglon AS item,
                r.descripcion AS descripcion,
                e.unidad_medida AS unidad_medida,
                e.cantidad AS cantidad,
                e.items_por_renglon AS items_por_renglon,
                e.marca AS marca,
                e.obs_usuario AS obs_usuario,
                e.conv_usd AS conv_usd,
                e.costo_unit_usd AS costo_unit_usd,
                e.costo_total_usd AS costo_total_usd,
                e.costo_unit_ars AS costo_unit_ars,
                e.costo_total_ars AS costo_total_ars,
                e.renta_minima AS renta_minima,
                e.precio_unit_aceptable AS precio_unit_aceptable,
                e.precio_total_aceptable AS precio_total_aceptable,
                e.precio_referencia AS precio_referencia,
                e.precio_ref_unitario AS precio_ref_unitario,
                e.renta_referencia AS renta_referencia,
                st.mejor_oferta_txt AS mejor_oferta_txt,
                e.oferta_para_mejorar AS oferta_para_mejorar,
                e.precio_unit_mejora AS precio_unit_mejora,
                e.renta_para_mejorar AS renta_para_mejorar,
                e.obs_cambio AS obs_cambio
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
                    "ITEMS POR RENGLON": row["items_por_renglon"],
                    "MARCA": row["marca"],
                    "OBS USUARIO": row["obs_usuario"],
                    "CONVERSIÓN USD": row["conv_usd"],
                    "COSTO UNIT USD": row["costo_unit_usd"],
                    "COSTO TOTAL USD": row["costo_total_usd"],
                    "COSTO UNIT ARS": row["costo_unit_ars"],
                    "COSTO TOTAL ARS": row["costo_total_ars"],
                    # Renta minima se exporta como fraccion (0-1) para evitar ambiguedad.
                    # Si detectamos formato legacy (multiplicador >= 1), normalizar.
                    "RENTA MINIMA %": (
                        (row["renta_minima"] - 1.0)
                        if row["renta_minima"] is not None and row["renta_minima"] > 1.0
                        else row["renta_minima"]
                    ),
                    "PRECIO UNIT ACEPTABLE": row["precio_unit_aceptable"],
                    "PRECIO TOTAL ACEPTABLE": row["precio_total_aceptable"],
                    "PRESUPUESTO OFICIAL": row["precio_referencia"],
                    "PRECIO DE REFERENCIA": row["precio_ref_unitario"],
                    "RENTA REFERENCIA %": row["renta_referencia"],
                    "MEJOR OFERTA ACTUAL": row["mejor_oferta_txt"],
                    "OFERTA PARA MEJORAR": row["oferta_para_mejorar"],
                    "PRECIO UNIT MEJORA": row["precio_unit_mejora"],
                    "RENTA PARA MEJORAR %": row["renta_para_mejorar"],
                    "OBS / CAMBIO": row["obs_cambio"],
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
                unidad_medida, cantidad, marca,
                items_por_renglon,
                obs_usuario, conv_usd, costo_unit_usd, costo_total_usd,
                costo_unit_ars, costo_total_ars, renta_minima,
                precio_referencia, precio_ref_unitario, renta_referencia,
                precio_unit_aceptable, precio_total_aceptable,
                precio_unit_mejora, renta_para_mejorar, oferta_para_mejorar,
                mejor_oferta_txt, obs_cambio,
                observaciones, conversion_usd, costo_usd, costo_final_pesos,
                renta, precio_referencia_subasta
            FROM renglon_excel
            WHERE renglon_id = ?
            """,
            (renglon_id,),
        )
        if not row:
            return None

        return {
            # REFACTORED columns (preferred)
            "unidad_medida": row["unidad_medida"],
            "cantidad": row["cantidad"],
            "items_por_renglon": row["items_por_renglon"],
            "marca": row["marca"],
            "obs_usuario": row["obs_usuario"],
            "conv_usd": row["conv_usd"],
            "costo_unit_usd": row["costo_unit_usd"],
            "costo_total_usd": row["costo_total_usd"],
            "costo_unit_ars": row["costo_unit_ars"],
            "costo_total_ars": row["costo_total_ars"],
            "renta_minima": row["renta_minima"],
            "precio_referencia": row["precio_referencia"],
            "precio_ref_unitario": row["precio_ref_unitario"],
            "renta_referencia": row["renta_referencia"],
            "precio_unit_aceptable": row["precio_unit_aceptable"],
            "precio_total_aceptable": row["precio_total_aceptable"],
            "precio_unit_mejora": row["precio_unit_mejora"],
            "renta_para_mejorar": row["renta_para_mejorar"],
            "oferta_para_mejorar": row["oferta_para_mejorar"],
            "mejor_oferta_txt": row["mejor_oferta_txt"],
            "obs_cambio": row["obs_cambio"],
            # LEGACY columns (for backward compatibility)
            "observaciones": row["observaciones"],
            "conversion_usd": row["conversion_usd"],
            "costo_usd": row["costo_usd"],
            "costo_final_pesos": row["costo_final_pesos"],
            "renta": row["renta"],
            "precio_referencia_subasta": row["precio_referencia_subasta"],
        }

    def upsert_renglon_excel(
        self,
        *,
        renglon_id: int,
        unidad_medida: str | None = None,
        cantidad: float | None = None,
        items_por_renglon: float | None = None,
        marca: str | None = None,
        # REFACTORED columns (preferred)
        obs_usuario: str | None = None,
        conv_usd: float | None = None,
        costo_unit_usd: float | None = None,
        costo_total_usd: float | None = None,
        costo_unit_ars: float | None = None,
        costo_total_ars: float | None = None,
        renta_minima: float | None = None,
        precio_referencia: float | None = None,
        precio_ref_unitario: float | None = None,
        renta_referencia: float | None = None,
        precio_unit_aceptable: float | None = None,
        precio_total_aceptable: float | None = None,
        precio_unit_mejora: float | None = None,
        renta_para_mejorar: float | None = None,
        oferta_para_mejorar: float | None = None,
        mejor_oferta_txt: str | None = None,
        obs_cambio: str | None = None,
        # LEGACY columns (for backward compatibility)
        observaciones: str | None = None,
        conversion_usd: float | None = None,
        costo_usd: float | None = None,
        costo_final_pesos: float | None = None,
        renta: float | None = None,
        precio_referencia_subasta: float | None = None,
        updated_at: str = None,
    ) -> None:
        # Use current timestamp if not provided
        if updated_at is None:
            from datetime import datetime
            updated_at = datetime.now().isoformat()
        
        row = self.fetchone("SELECT id FROM renglon_excel WHERE renglon_id = ?", (renglon_id,))
        
        # Update payload with all columns
        payload = (
            unidad_medida, cantidad, items_por_renglon, marca,
            obs_usuario, conv_usd, costo_unit_usd, costo_total_usd,
            costo_unit_ars, costo_total_ars, renta_minima,
            precio_referencia, precio_ref_unitario, renta_referencia,
            precio_unit_aceptable, precio_total_aceptable,
            precio_unit_mejora, renta_para_mejorar, oferta_para_mejorar,
            mejor_oferta_txt, obs_cambio,
            observaciones, conversion_usd, costo_usd, costo_final_pesos,
            renta, precio_referencia_subasta,
            updated_at, renglon_id
        )

        if row:
            self.execute(
                """
                UPDATE renglon_excel
                SET unidad_medida = ?, cantidad = ?, items_por_renglon = ?, marca = ?,
                    obs_usuario = ?, conv_usd = ?, costo_unit_usd = ?, costo_total_usd = ?,
                    costo_unit_ars = ?, costo_total_ars = ?, renta_minima = ?,
                    precio_referencia = ?, precio_ref_unitario = ?, renta_referencia = ?,
                    precio_unit_aceptable = ?, precio_total_aceptable = ?,
                    precio_unit_mejora = ?, renta_para_mejorar = ?, oferta_para_mejorar = ?,
                    mejor_oferta_txt = ?, obs_cambio = ?,
                    observaciones = ?, conversion_usd = ?, costo_usd = ?, costo_final_pesos = ?,
                    renta = ?, precio_referencia_subasta = ?,
                    updated_at = ?
                WHERE renglon_id = ?
                """,
                payload,
            )
        else:
            self.execute(
                """
                INSERT INTO renglon_excel (
                    unidad_medida, cantidad, items_por_renglon, marca,
                    obs_usuario, conv_usd, costo_unit_usd, costo_total_usd,
                    costo_unit_ars, costo_total_ars, renta_minima,
                    precio_referencia, precio_ref_unitario, renta_referencia,
                    precio_unit_aceptable, precio_total_aceptable,
                    precio_unit_mejora, renta_para_mejorar, oferta_para_mejorar,
                    mejor_oferta_txt, obs_cambio,
                    observaciones, conversion_usd, costo_usd, costo_final_pesos,
                    renta, precio_referencia_subasta,
                    updated_at, renglon_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
