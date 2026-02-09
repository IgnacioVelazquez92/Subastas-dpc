#!/usr/bin/env python3
"""Test script para verificar que los headers de la tabla se vean correctamente."""

import customtkinter as ctk
from tkinter import ttk
from app.ui.table_manager import TableManager

# Crear ventana de prueba
root = ctk.CTk()
root.title("Test Headers - Monitor de Subastas")
root.geometry("1400x600")

# Crear frame para la tabla
frame = ctk.CTkFrame(root)
frame.pack(fill="both", expand=True, padx=10, pady=10)

# Obtener configuración de tabla
table_config = TableManager.get_default_config()

# Configurar estilo de Treeview
style = ttk.Style()
style.configure('Treeview', font=("Segoe UI", 11), rowheight=20)
style.configure('Treeview.Heading', font=("Segoe UI", 11, "bold"))

# Crear tabla con todas las columnas
tree = ttk.Treeview(frame, columns=table_config.columns, show="headings", height=15)
tree.pack(side="top", fill="both", expand=True)

# Inicializar tabla (esto configura headers con nombres CORTOS + tooltips)
table_manager = TableManager(tree)
table_manager.initialize()

# Agregar algunas filas de ejemplo para probar
sample_data = [
    ("001", "Item 1", "Descripción de prueba 1", "100", "un", "Brand A", "Obs 1",
     "1.8", "1000", "1800", "1800", "3600", "1.3", "1300", "2600", "1500", "15",
     "1.2", "5000", "1000", "1100", "1.15", "Cambio 1"),
    ("002", "Item 2", "Descripción de prueba 2 más larga", "200", "un", "Brand B", "Obs 2",
     "1.9", "2000", "3800", "3800", "7600", "1.25", "2000", "4000", "2000", "20",
     "1.25", "5500", "2000", "2100", "1.20", "Cambio 2"),
]

for row_data in sample_data:
    tree.insert("", "end", values=row_data)

# Instrucción para usuario
label_info = ctk.CTkLabel(
    root,
    text="👁️ Verifica que TODOS los headers sean legibles\n💡 Pasa el mouse sobre los headers para ver el nombre completo",
    font=("Segoe UI", 10),
    text_color="gray"
)
label_info.pack(side="bottom", padx=10, pady=5)

root.mainloop()
