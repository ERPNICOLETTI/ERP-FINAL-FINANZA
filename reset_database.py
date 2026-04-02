import os
from core_sistema import db_ingesta

# RESET DATABASE - REINICIO TOTAL DEL ECOSISTEMA ERP 🏗️🧱🧠
# CUIDADO: Este script es destructivo y regenera la estructura desde cero.

def reset_db():
    db_file = 'erp_nicoletti.db'
    if os.path.exists(db_file):
        print(f"🗑️ Eliminando base de datos actual: {db_file}")
        os.remove(db_file)
    else:
        print(f"ℹ️ No se encontró base de datos previa.")
    
    # Orquestación Core
    db_ingesta.initialize_all()
    print("✅ Sistema Reiniciado con Éxito (Modo Modular DDD).")

if __name__ == "__main__":
    confirm = input("⚠️ ¿ESTÁ SEGURO DE QUE QUIERE RESETEAR EL ERP? (SI/NO): ")
    if confirm.upper() == "SI":
        reset_db()
    else:
        print("❌ Operación cancelada.")
