#!/usr/bin/env python3
"""
Script de migración: Formato VIEJO (multiplicadores) → NUEVO (fracciones)

Convierte:
- 1.1 → 0.10 (10%)
- 1.3 → 0.30 (30%)
- 2.0 → 1.0 (100%)
- 11.0 → 10.0 (1000%)

⚠️  HACER BACKUP ANTES DE EJECUTAR
"""

import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB_PATH = "data/subastas.db"

def backup_database():
    """Hacer backup de la base de datos"""
    if not Path(DB_PATH).exists():
        print(f"❌ No se encontró la base de datos: {DB_PATH}")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"data/subastas_backup_{timestamp}.db"
    
    try:
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Backup creado: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Error creando backup: {e}")
        return False

def analyze_data(conn):
    """Analizar datos actuales"""
    print("\n" + "="*60)
    print("ANÁLISIS DE DATOS ACTUALES")
    print("="*60)
    
    cursor = conn.cursor()
    
    # Contar registros con renta_minima
    cursor.execute("SELECT COUNT(*) FROM renglon_excel WHERE renta_minima IS NOT NULL")
    total = cursor.fetchone()[0]
    print(f"Total de renglones con renta_minima: {total}")
    
    if total == 0:
        print("ℹ️  No hay datos para migrar")
        return False
    
    # Estadísticas de rangos
    cursor.execute("""
        SELECT 
            MIN(renta_minima) as min_val,
            MAX(renta_minima) as max_val,
            AVG(renta_minima) as avg_val,
            COUNT(CASE WHEN renta_minima >= 1.0 THEN 1 END) as multiplicadores,
            COUNT(CASE WHEN renta_minima < 1.0 THEN 1 END) as fracciones
        FROM renglon_excel 
        WHERE renta_minima IS NOT NULL
    """)
    
    stats = cursor.fetchone()
    print(f"\nEstadísticas:")
    print(f"  Min: {stats[0]:.2f}")
    print(f"  Max: {stats[1]:.2f}")
    print(f"  Promedio: {stats[2]:.2f}")
    print(f"  Formato multiplicador (>= 1.0): {stats[3]}")
    print(f"  Formato fracción (< 1.0): {stats[4]}")
    
    # Mostrar ejemplos
    cursor.execute("""
        SELECT id, renta_minima 
        FROM renglon_excel 
        WHERE renta_minima IS NOT NULL 
        LIMIT 10
    """)
    
    print(f"\nEjemplos de valores actuales:")
    for row in cursor.fetchall():
        print(f"  ID {row[0]}: {row[1]:.4f}")
    
    if stats[3] == 0:
        print("\n✅ Todos los valores ya están en formato fracción")
        return False
    
    return True

def migrate_data(conn):
    """Migrar datos de multiplicadores a fracciones"""
    print("\n" + "="*60)
    print("MIGRANDO DATOS")
    print("="*60)
    
    cursor = conn.cursor()
    
    # Obtener registros a migrar
    cursor.execute("""
        SELECT id, renta_minima 
        FROM renglon_excel 
        WHERE renta_minima >= 1.0
    """)
    
    records = cursor.fetchall()
    total = len(records)
    
    if total == 0:
        print("ℹ️  No hay registros para migrar")
        return
    
    print(f"Migrando {total} registros...")
    
    migrated = 0
    errors = 0
    
    for record_id, old_value in records:
        try:
            # Convertir: 1.3 → 0.3, 2.0 → 1.0, 11.0 → 10.0
            new_value = old_value - 1.0
            
            cursor.execute("""
                UPDATE renglon_excel 
                SET renta_minima = ? 
                WHERE id = ?
            """, (new_value, record_id))
            
            migrated += 1
            
            if migrated <= 5:  # Mostrar primeros 5
                print(f"  ✅ ID {record_id}: {old_value:.4f} → {new_value:.4f}")
            
        except Exception as e:
            errors += 1
            print(f"  ❌ Error en ID {record_id}: {e}")
    
    conn.commit()
    
    print(f"\n📊 Resultado:")
    print(f"  Migrados: {migrated}")
    print(f"  Errores: {errors}")

def verify_migration(conn):
    """Verificar que la migración fue exitosa"""
    print("\n" + "="*60)
    print("VERIFICACIÓN POST-MIGRACIÓN")
    print("="*60)
    
    cursor = conn.cursor()
    
    # Verificar que no quedan multiplicadores
    cursor.execute("""
        SELECT COUNT(*) 
        FROM renglon_excel 
        WHERE renta_minima >= 1.0
    """)
    
    remaining = cursor.fetchone()[0]
    
    if remaining > 0:
        print(f"⚠️  Advertencia: {remaining} registros todavía con valor >= 1.0")
        print("   Estos pueden ser márgenes muy altos (>= 100%)")
    else:
        print("✅ Todos los valores están en rango correcto (< 1.0)")
    
    # Mostrar nuevos valores
    cursor.execute("""
        SELECT id, renta_minima 
        FROM renglon_excel 
        WHERE renta_minima IS NOT NULL 
        ORDER BY renta_minima DESC
        LIMIT 10
    """)
    
    print(f"\nEjemplos de valores migrados:")
    for row in cursor.fetchall():
        porcentaje = row[1] * 100
        print(f"  ID {row[0]}: {row[1]:.4f} ({porcentaje:.1f}%)")

def main():
    """Proceso principal de migración"""
    print("="*60)
    print("MIGRACIÓN DE FORMATO: Multiplicadores → Fracciones")
    print("="*60)
    
    # 1. Verificar que existe la BD
    if not Path(DB_PATH).exists():
        print(f"❌ No se encontró la base de datos: {DB_PATH}")
        sys.exit(1)
    
    # 2. Hacer backup
    if not backup_database():
        sys.exit(1)
    
    # 3. Conectar a BD
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        print(f"❌ Error conectando a BD: {e}")
        sys.exit(1)
    
    try:
        # 4. Analizar datos
        needs_migration = analyze_data(conn)
        
        if not needs_migration:
            print("\n✅ No es necesario migrar datos")
            return
        
        # 5. Confirmar con usuario
        print("\n⚠️  ADVERTENCIA: Esta operación modificará la base de datos")
        print("   Se creó un backup, pero asegúrate de tener una copia adicional")
        response = input("\n¿Continuar con la migración? (sí/no): ")
        
        if response.lower() not in ['sí', 'si', 's', 'yes', 'y']:
            print("❌ Migración cancelada")
            return
        
        # 6. Migrar
        migrate_data(conn)
        
        # 7. Verificar
        verify_migration(conn)
        
        print("\n" + "="*60)
        print("✅ MIGRACIÓN COMPLETADA")
        print("="*60)
        print("\nPróximos pasos:")
        print("1. Ejecuta: python test_renta_format_v2.py")
        print("2. Prueba exportar/importar Excel")
        print("3. Verifica cálculos en la UI")
        
    except Exception as e:
        print(f"\n❌ Error durante migración: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()
