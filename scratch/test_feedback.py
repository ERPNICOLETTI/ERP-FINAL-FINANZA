import sqlite3
import os
import sys

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project path to python paths
sys.path.append(r"c:\Users\essao\Desktop\ERP FINAL")

from modulo_bancos import storage_bancos
from erp_api import aprender_categoria_maestra, extraer_palabra_clave

def run_tests():
    print("🚀 [TEST] Iniciando verificación del Feedback Loop y Auto-clasificación Bancaria...")
    
    # 1. Probar extracción inteligente de palabra clave
    tests_extract = {
        "DEBITO CAMUZZI GAS": "CAMUZZI",
        "PAGO DE NETFLIX": "NETFLIX",
        "K CRUNCHY JOR": "CRUNCHY",
        "DEBITO AUTOMATICO SANCRIS": "SANCRIS",
        "TRANSFERENCIA RECIBIDA COELSA": "COELSA"
    }
    
    for desc, expected in tests_extract.items():
        kw = extraer_palabra_clave(desc)
        print(f"   - Extracción de '{desc}' -> '{kw}' (Esperado: '{expected}')")
        assert kw == expected, f"❌ Falló extracción para {desc}: obtuvo {kw}"
    print("✅ [OK] Extracción de palabras clave correcta y libre de palabras genéricas.")

    # Conectar a base de datos
    conn = storage_bancos.get_db_connection()
    try:
        # Asegurar semilla de categorías para el test
        from scripts import seed_categorias
        seed_categorias.seed()
        
        # 2. Verificar auto-categorización en ingesta con palabra clave semilla
        print("\n📥 [TEST] Simulando ingesta de movimiento con palabra clave semilla 'COTO'...")
        movs = [{
            "banco": "TEST_BANCO",
            "cuenta": "CA_TEST",
            "fecha": "2026-06-08",
            "descripcion": "DEBITO SUPERMERCADO COTO SUC 12",
            "importe": -15000.0,
            "saldo": 85000.0
        }]
        
        # Borrar registros previos del test
        conn.execute("DELETE FROM bancos_movimientos WHERE banco = 'TEST_BANCO'")
        conn.commit()
        
        agregados, last_id = storage_bancos.save_movimiento_banco(movs, "test_hash_123")
        print(f"   - Agregados: {agregados}, Last ID: {last_id}")
        
        # Consultar cómo quedó guardado
        row = conn.execute("SELECT categoria FROM bancos_movimientos WHERE id = ?", (last_id,)).fetchone()
        print(f"   - Categoría asignada automáticamente: '{row['categoria']}' (Esperado: 'Comida')")
        assert row['categoria'] == 'Comida', f"❌ Falló auto-categorización: obtuvo {row['categoria']}"
        print("✅ [OK] Auto-categorización por semilla exitosa.")

        # 3. Probar aprendizaje manual y re-ingesta
        print("\n🧠 [TEST] Educando al sistema sobre 'CABIFY' para la categoría 'Transporte'...")
        # Limpiar palabras clave previas de Transporte
        conn.execute("UPDATE categorias_maestras SET palabras_clave = 'uber,cabify,didi,taxi,nafta,ypf,shell,axion,sube,peaje' WHERE nombre = 'Transporte'")
        conn.commit()
        
        # Eliminar 'cabify' para simular que no lo conoce
        conn.execute("UPDATE categorias_maestras SET palabras_clave = 'uber,didi,taxi,nafta' WHERE nombre = 'Transporte'")
        conn.commit()
        
        # Verificar que sin la regla entra como SIN_CATEGORIZAR
        movs_unknown = [{
            "banco": "TEST_BANCO",
            "cuenta": "CA_TEST",
            "fecha": "2026-06-08",
            "descripcion": "DEBITO CABIFY TRANSPORTE",
            "importe": -4500.0,
            "saldo": 80500.0
        }]
        conn.execute("DELETE FROM bancos_movimientos WHERE descripcion = 'DEBITO CABIFY TRANSPORTE'")
        conn.commit()
        
        _, unk_id = storage_bancos.save_movimiento_banco(movs_unknown, "test_hash_unk")
        row_unk = conn.execute("SELECT categoria FROM bancos_movimientos WHERE id = ?", (unk_id,)).fetchone()
        print(f"   - Categoría sin regla: '{row_unk['categoria']}' (Esperado: 'SIN_CATEGORIZAR')")
        assert row_unk['categoria'] == 'SIN_CATEGORIZAR'
        
        # Ahora el usuario corrige el movimiento a 'Transporte' (Simula trigger htmx /api/bancos/movimientos/{id}/categoria)
        print("   - Corrigiendo categoría a 'Transporte' en caliente...")
        aprender_categoria_maestra("Transporte", "DEBITO CABIFY TRANSPORTE")
        
        # Verificar que se agregó la palabra clave 'CABIFY'
        row_kw = conn.execute("SELECT palabras_clave FROM categorias_maestras WHERE nombre = 'Transporte'").fetchone()
        print(f"   - Nuevas palabras clave de 'Transporte': '{row_kw['palabras_clave']}'")
        assert "CABIFY" in row_kw['palabras_clave'], "❌ No se guardó la palabra clave 'CABIFY' en Transporte"
        
        # Probar ingesta de un NUEVO movimiento de Cabify
        print("   - Ingestando un nuevo movimiento con 'CABIFY'...")
        movs_new = [{
            "banco": "TEST_BANCO",
            "cuenta": "CA_TEST",
            "fecha": "2026-06-09",
            "descripcion": "CABIFY VIAJE DE TRABAJO",
            "importe": -3200.0,
            "saldo": 77300.0
        }]
        _, new_id = storage_bancos.save_movimiento_banco(movs_new, "test_hash_new")
        row_new = conn.execute("SELECT categoria FROM bancos_movimientos WHERE id = ?", (new_id,)).fetchone()
        print(f"   - Nueva categoría asignada automáticamente: '{row_new['categoria']}' (Esperado: 'Transporte')")
        assert row_new['categoria'] == 'Transporte', f"❌ Ingesta futura no aprendió: obtuvo {row_new['categoria']}"
        print("✅ [OK] Aprendizaje en caliente y auto-clasificación futura exitoso.")
        
        # Limpiar datos de prueba
        conn.execute("DELETE FROM bancos_movimientos WHERE banco = 'TEST_BANCO'")
        conn.commit()
        print("\n✨ [ÉXITO] ¡Todas las pruebas del Feedback Loop Bancario pasaron perfectamente!")
        
    finally:
        conn.close()

if __name__ == "__main__":
    run_tests()
