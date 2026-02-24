-- app/db/schema.sql
-- Esquema SQLite para Monitor de Subastas.
-- Buenas prácticas incluidas:
-- - Foreign keys
-- - Índices útiles
-- - Campos de auditoría (created_at / updated_at)
-- - Modelo preparado para multi-subasta

PRAGMA foreign_keys = ON;

-- =========================================================
-- Tabla: subastas
-- Representa una subasta monitoreada (id_cotizacion del portal)
-- =========================================================
CREATE TABLE IF NOT EXISTS subasta (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cot          TEXT NOT NULL UNIQUE,       -- id_Cotizacion del portal
    url             TEXT NOT NULL,
    estado          TEXT NOT NULL DEFAULT 'RUNNING', -- RUNNING | PAUSED | ENDED | ERROR
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at        TEXT,                       -- se setea cuando finaliza
    last_ok_at      TEXT,                       -- último update válido
    last_http_code  INTEGER,                    -- último HTTP status observado
    err_streak      INTEGER NOT NULL DEFAULT 0, -- errores consecutivos (seguridad)
    mi_id_proveedor TEXT                        -- ID de proveedor propio en esta subasta (anónimo/variable)
);

CREATE INDEX IF NOT EXISTS idx_subasta_estado ON subasta(estado);
CREATE INDEX IF NOT EXISTS idx_subasta_last_ok ON subasta(last_ok_at);

-- =========================================================
-- Tabla: renglon
-- Catálogo de renglones de una subasta (ddlItemRenglon option)
-- =========================================================
CREATE TABLE IF NOT EXISTS renglon (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subasta_id      INTEGER NOT NULL,
    id_renglon      TEXT NOT NULL,              -- id_Item_Renglon del portal
    descripcion     TEXT NOT NULL,
    margen_minimo   TEXT,                       -- margen tal cual viene (ej "0,0050")
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY(subasta_id) REFERENCES subasta(id) ON DELETE CASCADE,
    UNIQUE(subasta_id, id_renglon)
);

CREATE INDEX IF NOT EXISTS idx_renglon_subasta ON renglon(subasta_id);
CREATE INDEX IF NOT EXISTS idx_renglon_idr ON renglon(id_renglon);

-- =========================================================
-- Tabla: renglon_estado
-- Estado "actual" de cada renglón (última lectura)
-- NOTA: Guardamos números como REAL (float) para cálculos.
--       Guardamos también el string original por si el formato cambia.
-- =========================================================
CREATE TABLE IF NOT EXISTS renglon_estado (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    renglon_id          INTEGER NOT NULL UNIQUE,   -- 1 estado actual por renglón

    mejor_oferta_txt    TEXT,                      -- "$ 20.115.680,0000"
    oferta_min_txt      TEXT,                      -- "$ 20.015.101,6000"
    presupuesto_txt     TEXT,                      -- "$ 21.696.480,0000"

    mejor_oferta        REAL,                      -- 20115680.0
    oferta_min          REAL,                      -- 20015101.6
    presupuesto         REAL,                      -- 21696480.0

    mensaje             TEXT,                      -- estado del portal
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY(renglon_id) REFERENCES renglon(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_estado_updated ON renglon_estado(updated_at);

-- =========================================================
-- Tabla: renglon_config
-- Configuración del usuario por renglón (persistente)
-- - costo_subtotal: costo propio para calcular utilidad
-- - oferta_mia: marca si la mejor oferta es "mía"
-- - seguir: si el renglón está en seguimiento (alertas)
-- - utilidad_min_pct: filtro / umbral para alertas
-- - ocultar_bajo_umbral: UX (filtrar en UI)
-- =========================================================
CREATE TABLE IF NOT EXISTS renglon_config (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    renglon_id              INTEGER NOT NULL UNIQUE,

    costo_subtotal           REAL,                   -- NULL si no configurado
    oferta_mia               INTEGER NOT NULL DEFAULT 0, -- 0/1
    seguir                   INTEGER NOT NULL DEFAULT 0, -- 0/1

    utilidad_min_pct         REAL NOT NULL DEFAULT 10.0, -- umbral
    ocultar_bajo_umbral      INTEGER NOT NULL DEFAULT 0, -- 0/1

    updated_at               TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY(renglon_id) REFERENCES renglon(id) ON DELETE CASCADE
);

-- =========================================================
-- Tabla: evento
-- Log persistente (auditoría). Útil para horas de monitoreo.
-- =========================================================
CREATE TABLE IF NOT EXISTS evento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subasta_id      INTEGER,                    -- puede ser NULL si es global
    renglon_id      INTEGER,                    -- puede ser NULL si aplica a la subasta
    nivel           TEXT NOT NULL,              -- DEBUG | INFO | WARN | ERROR
    tipo            TEXT NOT NULL,              -- HEARTBEAT | UPDATE | ALERT | SECURITY | HTTP_ERROR | etc.
    mensaje         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY(subasta_id) REFERENCES subasta(id) ON DELETE SET NULL,
    FOREIGN KEY(renglon_id) REFERENCES renglon(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evento_created ON evento(created_at);
CREATE INDEX IF NOT EXISTS idx_evento_nivel ON evento(nivel);
CREATE INDEX IF NOT EXISTS idx_evento_tipo ON evento(tipo);
CREATE INDEX IF NOT EXISTS idx_evento_subasta ON evento(subasta_id);

-- =========================================================
-- Tabla: renglon_excel
-- Datos de Excel / usuario por renglon
-- REFACTORING: Nuevos nombres de columnas para mayor claridad
-- - observaciones → obs_usuario
-- - costo_usd → costo_unit_usd (y new: costo_total_usd)
-- - costo_final_pesos → costo_unit_ars (y new: costo_total_ars)
-- - renta → renta_minima
-- NOTA: Mantenemos columnas viejas para backward compatibility durante migración
-- =========================================================
CREATE TABLE IF NOT EXISTS renglon_excel (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    renglon_id              INTEGER NOT NULL UNIQUE,

    unidad_medida           TEXT,
    cantidad                REAL,
    marca                   TEXT,

    -- REFACTORED COLUMNS (nuevas)
    obs_usuario             TEXT,
    conv_usd                REAL,
    costo_unit_usd          REAL,
    costo_total_usd         REAL,
    costo_unit_ars          REAL,
    costo_total_ars         REAL,
    renta_minima            REAL,
    precio_referencia       REAL,
    precio_ref_unitario     REAL,
    renta_referencia        REAL,
    precio_unit_aceptable   REAL,
    precio_total_aceptable  REAL,
    precio_unit_mejora      REAL,
    renta_para_mejorar      REAL,
    oferta_para_mejorar     REAL,
    mejor_oferta_txt        TEXT,
    obs_cambio              TEXT,

    -- LEGACY COLUMNS (old, kept for backward compatibility)
    observaciones           TEXT,
    conversion_usd          REAL,
    costo_usd               REAL,
    costo_final_pesos       REAL,
    renta                   REAL,
    precio_referencia_subasta REAL,

    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY(renglon_id) REFERENCES renglon(id) ON DELETE CASCADE
);

-- =========================================================
-- Tabla: ui_config
-- Configuracion persistente de UI (por clave)
-- =========================================================
CREATE TABLE IF NOT EXISTS ui_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

