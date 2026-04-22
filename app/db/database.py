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
        if "mi_id_proveedor_1" not in existing_subasta_cols:
            self.execute("ALTER TABLE subasta ADD COLUMN mi_id_proveedor_1 TEXT")
        if "mi_id_proveedor_2" not in existing_subasta_cols:
            self.execute("ALTER TABLE subasta ADD COLUMN mi_id_proveedor_2 TEXT")

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
        """Compatibilidad: devuelve el primer ID propio disponible de la subasta."""
        ids = self.get_mis_ids_proveedor(subasta_id=subasta_id)
        return ids[0] if ids else None

    def set_mi_id_proveedor(self, *, subasta_id: int, mi_id_proveedor: str | None) -> None:
        """Compatibilidad: guarda solo el ID propio 1 y limpia el ID propio 2."""
        self.set_mis_ids_proveedor(
            subasta_id=subasta_id,
            mi_id_proveedor_1=mi_id_proveedor,
            mi_id_proveedor_2=None,
        )

    def get_mis_ids_proveedor(self, *, subasta_id: int) -> tuple[str, ...]:
        """Devuelve IDs propios configurados para la subasta, sin duplicados y preservando orden."""
        row = self.fetchone(
            """
            SELECT mi_id_proveedor, mi_id_proveedor_1, mi_id_proveedor_2
            FROM subasta
            WHERE id = ?
            """,
            (subasta_id,),
        )
        if not row:
            return ()

        values = [
            row["mi_id_proveedor_1"],
            row["mi_id_proveedor_2"],
            row["mi_id_proveedor"],
        ]
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values:
            raw = str(value or "").strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            normalized.append(raw)
        return tuple(normalized)

    def set_mis_ids_proveedor(
        self,
        *,
        subasta_id: int,
        mi_id_proveedor_1: str | None,
        mi_id_proveedor_2: str | None,
    ) -> None:
        """Guarda los dos IDs propios de la subasta y mantiene compatibilidad legacy."""
        value_1 = str(mi_id_proveedor_1 or "").strip() or None
        value_2 = str(mi_id_proveedor_2 or "").strip() or None
        if value_1 and value_2 and value_1 == value_2:
            value_2 = None
        self.execute(
            """
            UPDATE subasta
            SET mi_id_proveedor = ?,
                mi_id_proveedor_1 = ?,
                mi_id_proveedor_2 = ?
            WHERE id = ?
            """,
            (value_1, value_1, value_2, subasta_id),
        )

    def get_mi_id_proveedor_by_id_cot(self, *, id_cot: str) -> str | None:
        """Compatibilidad: devuelve el primer ID propio disponible buscando por id_cot."""
        ids = self.get_mis_ids_proveedor_by_id_cot(id_cot=id_cot)
        return ids[0] if ids else None

    def get_mis_ids_proveedor_by_id_cot(self, *, id_cot: str) -> tuple[str, ...]:
        """Devuelve IDs propios configurados buscando por id_cot."""
        row = self.fetchone("SELECT id FROM subasta WHERE id_cot = ?", (id_cot,))
        if not row:
            return ()
        return self.get_mis_ids_proveedor(subasta_id=int(row["id"]))

    def upsert_provider_alias(
        self,
        *,
        id_proveedor: str,
        alias: str,
        notas: str | None = None,
        activo: bool = True,
    ) -> None:
        provider_id = str(id_proveedor or "").strip()
        provider_alias = str(alias or "").strip()
        if not provider_id or not provider_alias:
            raise ValueError("id_proveedor y alias son requeridos")

        row = self.fetchone(
            "SELECT id_proveedor FROM proveedor_alias WHERE id_proveedor = ?",
            (provider_id,),
        )
        payload = (
            provider_alias,
            notas,
            1 if activo else 0,
            provider_id,
        )
        if row:
            self.execute(
                """
                UPDATE proveedor_alias
                SET alias = ?,
                    notas = ?,
                    activo = ?,
                    updated_at = datetime('now')
                WHERE id_proveedor = ?
                """,
                payload,
            )
        else:
            self.execute(
                """
                INSERT INTO proveedor_alias (alias, notas, activo, id_proveedor)
                VALUES (?, ?, ?, ?)
                """,
                payload,
            )

    def get_provider_alias(self, *, id_proveedor: str) -> str | None:
        provider_id = str(id_proveedor or "").strip()
        if not provider_id:
            return None
        row = self.fetchone(
            """
            SELECT alias
            FROM proveedor_alias
            WHERE id_proveedor = ? AND activo = 1
            """,
            (provider_id,),
        )
        return str(row["alias"]).strip() if row and row["alias"] else None

    def list_provider_aliases(self) -> list[dict]:
        rows = self.fetchall(
            """
            SELECT id_proveedor, alias, notas, activo, updated_at
            FROM proveedor_alias
            ORDER BY activo DESC, alias COLLATE NOCASE, id_proveedor
            """
        )
        return [
            {
                "id_proveedor": str(row["id_proveedor"]),
                "alias": str(row["alias"] or "").strip(),
                "notas": str(row["notas"] or "").strip(),
                "activo": bool(row["activo"]),
                "updated_at": str(row["updated_at"] or ""),
            }
            for row in rows
        ]

    def delete_provider_alias(self, *, id_proveedor: str) -> None:
        provider_id = str(id_proveedor or "").strip()
        if not provider_id:
            return
        self.execute("DELETE FROM proveedor_alias WHERE id_proveedor = ?", (provider_id,))

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
        self.execute("DELETE FROM evento_auditoria")

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
        self.execute("DELETE FROM evento_auditoria")# hijo de subasta/renglon
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

    def insert_evento_auditoria(
        self,
        *,
        subasta_id: int | None,
        renglon_id: int | None,
        id_cot: str | None,
        id_renglon: str,
        descripcion: str | None,
        detected_at: str,
        portal_time_prev: str | None,
        portal_time_new: str | None,
        provider_prev_id: str | None,
        provider_prev_txt: str | None,
        provider_new_id: str | None,
        provider_new_txt: str | None,
        best_offer_prev_txt: str | None,
        best_offer_prev_val: float | None,
        best_offer_new_txt: str | None,
        best_offer_new_val: float | None,
        offer_min_txt: str | None,
        offer_min_val: float | None,
        outbid: bool,
        my_provider_outbid_id: str | None,
    ) -> int:
        return self.execute_returning_id(
            """
            INSERT INTO evento_auditoria (
                subasta_id, renglon_id, id_cot, id_renglon, descripcion, detected_at,
                portal_time_prev, portal_time_new,
                provider_prev_id, provider_prev_txt, provider_new_id, provider_new_txt,
                best_offer_prev_txt, best_offer_prev_val, best_offer_new_txt, best_offer_new_val,
                offer_min_txt, offer_min_val, outbid, my_provider_outbid_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subasta_id,
                renglon_id,
                id_cot,
                id_renglon,
                descripcion,
                detected_at,
                portal_time_prev,
                portal_time_new,
                provider_prev_id,
                provider_prev_txt,
                provider_new_id,
                provider_new_txt,
                best_offer_prev_txt,
                best_offer_prev_val,
                best_offer_new_txt,
                best_offer_new_val,
                offer_min_txt,
                offer_min_val,
                1 if outbid else 0,
                my_provider_outbid_id,
            ),
        )

    def fetch_audit_export_rows(self, *, subasta_id: int) -> list[dict]:
        rows = self.fetchall(
            """
            SELECT
                a.detected_at,
                s.id_cot,
                a.id_renglon,
                a.descripcion,
                a.portal_time_prev,
                a.portal_time_new,
                a.provider_prev_id,
                pa_prev.alias AS provider_prev_alias,
                a.provider_prev_txt,
                a.provider_new_id,
                pa_new.alias AS provider_new_alias,
                a.provider_new_txt,
                a.best_offer_prev_txt,
                a.best_offer_prev_val,
                a.best_offer_new_txt,
                a.best_offer_new_val,
                a.offer_min_txt,
                a.offer_min_val,
                a.outbid,
                a.my_provider_outbid_id
            FROM evento_auditoria a
            LEFT JOIN subasta s ON s.id = a.subasta_id
            LEFT JOIN proveedor_alias pa_prev ON pa_prev.id_proveedor = a.provider_prev_id AND pa_prev.activo = 1
            LEFT JOIN proveedor_alias pa_new ON pa_new.id_proveedor = a.provider_new_id AND pa_new.activo = 1
            WHERE a.subasta_id = ?
            ORDER BY a.detected_at, a.id
            """,
            (subasta_id,),
        )
        return [
            {
                "FECHA DETECCION": row["detected_at"],
                "ID SUBASTA": row["id_cot"],
                "ITEM": row["id_renglon"],
                "DESCRIPCION": row["descripcion"],
                "HORA PORTAL ANTERIOR": row["portal_time_prev"],
                "HORA PORTAL NUEVA": row["portal_time_new"],
                "PROVEEDOR ANTERIOR ID": row["provider_prev_id"],
                "PROVEEDOR ANTERIOR ALIAS": row["provider_prev_alias"],
                "PROVEEDOR ANTERIOR PORTAL": row["provider_prev_txt"],
                "PROVEEDOR NUEVO ID": row["provider_new_id"],
                "PROVEEDOR NUEVO ALIAS": row["provider_new_alias"],
                "PROVEEDOR NUEVO PORTAL": row["provider_new_txt"],
                "OFERTA ANTERIOR TXT": row["best_offer_prev_txt"],
                "OFERTA ANTERIOR VALOR": row["best_offer_prev_val"],
                "OFERTA NUEVA TXT": row["best_offer_new_txt"],
                "OFERTA NUEVA VALOR": row["best_offer_new_val"],
                "MINIMO ACTUAL TXT": row["offer_min_txt"],
                "MINIMO ACTUAL VALOR": row["offer_min_val"],
                "FUE OUTBID": "SI" if row["outbid"] else "NO",
                "MI ID SUPERADO": row["my_provider_outbid_id"],
            }
            for row in rows
        ]
