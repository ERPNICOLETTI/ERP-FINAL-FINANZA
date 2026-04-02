import hashlib
import sqlite3
import os

# SERVICIO DE AUDITORÍA Y CHECKUM (ANTI-DUPLICADOS) 🦾🛡️🧠

DB_PATH = 'erp_nicoletti.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def calculate_file_hash(file_path):
    """Calcula el SHA-256 de un archivo físico."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Leer en bloques para archivos grandes
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def calculate_text_hash(text):
    """Calcula el SHA-256 de un bloque de texto (Copia y Pega)."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def is_already_ingested(hash_val):
    """Verifica si este hash ya existe en la base de datos."""
    conn = get_db_connection()
    cursor = conn.execute('SELECT id FROM core_registro_ingestas WHERE hash_sha256 = ?', (hash_val,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def register_ingesta(modulo, tipo, nombre_fuente, hash_val):
    """Registra una operación exitosa en el libro de auditoría."""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO core_registro_ingestas (modulo, tipo, nombre_fuente, hash_sha256)
            VALUES (?, ?, ?, ?)
        ''', (modulo, tipo, nombre_fuente, hash_val))
        conn.commit()
    finally:
        conn.close()

def validar_y_registrar(modulo, tipo, nombre_fuente, content_or_path):
    """
    Función de Conveniencia: Valida duplicados y registra en un solo paso.
    Retorna (es_nuevo, hash_val)
    """
    if tipo == 'FILE':
        hash_val = calculate_file_hash(content_or_path)
    else:
        hash_val = calculate_text_hash(content_or_path)
        
    if is_already_ingested(hash_val):
        return False, hash_val
    
    register_ingesta(modulo, tipo, nombre_fuente, hash_val)
    return True, hash_val
