# app/excel/excel_io.py
"""
Excel import/export helpers.
"""

from __future__ import annotations

import unicodedata
from typing import Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

COLUMNS = [
    "ID SUBASTA",
    "ITEM",
    "DESCRIPCION",
    "UNIDAD DE MEDIDA",
    "CANTIDAD",
    "MARCA",
    "Observaciones",
    "CONVERSIÓN USD",
    "COSTO USD",
    "COSTO FINAL PESOS",
    "SUBTOTAL COSTO PESOS",
    "RENTA",
    "P.UNIT MINIMO",
    "SUBTOTAL",
    "Precio referencia",
    "RENTA/ REF",
    "P. UNIT MEJORA",
    "SUBTOTAL PARA MEJORAR",
    "dif unit",
    "Renta DPC",
]

USER_FIELDS = {
    "UNIDAD DE MEDIDA",
    "MARCA",
    "Observaciones",
    "CONVERSIÓN USD",
    "COSTO FINAL PESOS",
    "RENTA",
}

CALC_FIELDS = {
    "COSTO USD",
    "SUBTOTAL COSTO PESOS",
    "P.UNIT MINIMO",
    "SUBTOTAL",
    "RENTA/ REF",
    "P. UNIT MEJORA",
    "dif unit",
    "Renta DPC",
}

OBS_FIELDS = {
    "ID SUBASTA",
    "ITEM",
    "DESCRIPCION",
    "SUBTOTAL PARA MEJORAR",
    "Precio referencia",
}

TABLE_NAME = "T_Subastas"
SHEET_NAME = "Subastas"

MONEY_COLS = {
    "COSTO USD",
    "COSTO FINAL PESOS",
    "SUBTOTAL COSTO PESOS",
    "P.UNIT MINIMO",
    "SUBTOTAL",
    "Precio referencia",
    "P. UNIT MEJORA",
    "SUBTOTAL PARA MEJORAR",
    "dif unit",
}

PERCENT_COLS = {
    "RENTA/ REF",
    "Renta DPC",
}

# Se mantiene por referencia conceptual, no se usa para escribir fórmulas
FORMULAS = {
    "COSTO USD": "=[@[COSTO FINAL PESOS]]/[@[CONVERSIÓN USD]]",
    "SUBTOTAL COSTO PESOS": "=[@CANTIDAD]*[@[COSTO FINAL PESOS]]",
    "P.UNIT MINIMO": "=[@RENTA]*[@[COSTO FINAL PESOS]]",
    "SUBTOTAL": "=[@CANTIDAD]*[@[P.UNIT MINIMO]]",
    "RENTA/ REF": "=[@[Precio referencia]]/[@[COSTO FINAL PESOS]]-1",
    "P. UNIT MEJORA": "=[@[SUBTOTAL PARA MEJORAR]]/[@[CANTIDAD]]",
    "dif unit": "=[@[P. UNIT MEJORA]]-[@[COSTO FINAL PESOS]]",
    "Renta DPC": "=[@[P. UNIT MEJORA]]/[@[COSTO FINAL PESOS]]-1",
}


def _normalize_header(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("\u00a0", " ")
    text = " ".join(text.split())
    return text.upper()


def export_subasta_to_excel(*, rows: Iterable[dict], out_path: str) -> None:
    """
    Exporta filas a Excel creando una tabla con formato y fórmulas.
    El archivo queda completamente editable (sin protección).
    """
    rows = list(rows)

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    # Header
    ws.append(COLUMNS)

    # Data
    if rows:
        for row in rows:
            ws.append([row.get(col) for col in COLUMNS])
    else:
        # Fila vacía para que existan tabla y fórmulas
        ws.append([None for _ in COLUMNS])

    max_row = ws.max_row
    max_col = ws.max_column

    # Tabla
    ref = f"{ws.cell(row=1, column=1).coordinate}:{ws.cell(row=max_row, column=max_col).coordinate}"
    table = Table(displayName=TABLE_NAME, ref=ref)
    style = TableStyleInfo(
        name="TableStyleMedium9",
        showRowStripes=True,
        showColumnStripes=False,
    )
    table.tableStyleInfo = style
    ws.add_table(table)

    # Índices y letras
    header_index = {name: i + 1 for i, name in enumerate(COLUMNS)}
    header_letter = {name: get_column_letter(i) for name, i in header_index.items()}

    def col(name: str) -> str:
        return header_letter[name]

    # Fórmulas A1 (robustas)
    rules = {
        "COSTO USD": lambda r: f"={col('COSTO FINAL PESOS')}{r}/{col('CONVERSIÓN USD')}{r}",
        "SUBTOTAL COSTO PESOS": lambda r: f"={col('CANTIDAD')}{r}*{col('COSTO FINAL PESOS')}{r}",
        "P.UNIT MINIMO": lambda r: f"={col('RENTA')}{r}*{col('COSTO FINAL PESOS')}{r}",
        "SUBTOTAL": lambda r: f"={col('CANTIDAD')}{r}*{col('P.UNIT MINIMO')}{r}",
        "RENTA/ REF": lambda r: f"={col('Precio referencia')}{r}/{col('COSTO FINAL PESOS')}{r}-1",
        "P. UNIT MEJORA": lambda r: f"={col('SUBTOTAL PARA MEJORAR')}{r}/{col('CANTIDAD')}{r}",
        "dif unit": lambda r: f"={col('P. UNIT MEJORA')}{r}-{col('COSTO FINAL PESOS')}{r}",
        "Renta DPC": lambda r: f"={col('P. UNIT MEJORA')}{r}/{col('COSTO FINAL PESOS')}{r}-1",
    }

    for col_name, builder in rules.items():
        col_idx = header_index[col_name]
        for r in range(2, max_row + 1):
            ws.cell(row=r, column=col_idx).value = builder(r)

    # Formatos
    for col_name, col_idx in header_index.items():
        if col_name in MONEY_COLS:
            for r in range(2, max_row + 1):
                ws.cell(row=r, column=col_idx).number_format = "$ #.##0,00"
        if col_name in PERCENT_COLS:
            for r in range(2, max_row + 1):
                ws.cell(row=r, column=col_idx).number_format = "0,00%"

    wb.save(out_path)


def import_excel_to_rows(*, file_path: str) -> list[dict]:
    wb = load_workbook(file_path, data_only=False)
    ws = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else wb.active

    headers = [c.value for c in ws[1]]
    header_map = {_normalize_header(h): h for h in headers if h}
    required = {
        "ID SUBASTA",
        "ITEM",
        "UNIDAD DE MEDIDA",
        "MARCA",
        "OBSERVACIONES",
        "CONVERSION USD",
        "COSTO FINAL PESOS",
        "RENTA",
    }
    if not required.issubset(set(header_map.keys())):
        missing = sorted(required - set(header_map.keys()))
        raise ValueError(f"Faltan columnas requeridas: {missing}")

    header_index = {
        _normalize_header(name): i for i, name in enumerate(headers) if name
    }
    reverse_headers = {
        _normalize_header(name): name for name in COLUMNS
    }

    rows: list[dict] = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in r):
            continue
        row = {
            reverse_headers.get(norm, norm): r[idx] if idx < len(r) else None
            for norm, idx in header_index.items()
        }
        rows.append(row)

    return rows
