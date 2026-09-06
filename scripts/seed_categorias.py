import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'erp_nicoletti.db')

CATEGORIAS = [
    # EGRESOS
    ('Pago Tarjeta', 'EGRESO', '💳', 'rgba(225, 29, 72, 0.2); color: #e11d48', 'pago tj,pago tarjeta,pago de t.credito,tarjeta visa,tarjeta master'),
    ('Comida', 'EGRESO', '🍔', 'rgba(239, 68, 68, 0.2); color: #ef4444', 'coto,carrefour,jumbo,dia ,almacen,supermercado,fiambreria,pedidosya,rappi,mcdonalds,burger,restaurante,kiosco,panaderia'),
    ('Transporte', 'EGRESO', '🚗', 'rgba(249, 115, 22, 0.2); color: #f97316', 'uber,cabify,didi,taxi,nafta,ypf,shell,axion,sube,peaje'),
    ('Vivienda', 'EGRESO', '🏠', 'rgba(245, 158, 11, 0.2); color: #f59e0b', 'alquiler,expensas'),
    ('Servicios', 'EGRESO', '💡', 'rgba(234, 179, 8, 0.2); color: #eab308', 'edesur,edenor,ayesa,metrogas,telecom,personal,movistar,claro,internet,wifi,cablevision,telecentro'),
    ('Impuestos', 'EGRESO', '🧾', 'rgba(132, 204, 22, 0.2); color: #84cc16', 'i.v.a,iva,sircreb,comision,mantenimiento,impuesto,perc.,percepcion,iibb,ley 25413,afip,arba'),
    ('Salud', 'EGRESO', '🏥', 'rgba(236, 72, 153, 0.2); color: #ec4899', 'psicologo,cosmetologa,farmacia,farmacity,osde,galeno,swiss medical,salud,medico,odontologo'),
    ('Educación', 'EGRESO', '🎓', 'rgba(168, 85, 247, 0.2); color: #a855f7', 'colegio,universidad,facultad,curso,capacitacion,escuela'),
    ('Ocio', 'EGRESO', '🎮', 'rgba(139, 92, 246, 0.2); color: #8b5cf6', 'netflix,spotify,steam,cine,teatro,juegos,playstation'),
    ('Compras', 'EGRESO', '🛒', 'rgba(244, 63, 94, 0.2); color: #f43f5e', 'mercadolibre,amazon,compra debito'),
    ('Ropa', 'EGRESO', '👕', 'rgba(217, 70, 239, 0.2); color: #d946ef', 'zara,nike,adidas,indumentaria,ropa,zapatillas'),
    ('Tecnología', 'EGRESO', '💻', 'rgba(56, 189, 248, 0.2); color: #38bdf8', 'garbarino,fravega,musimundo,apple,tecnologia,computacion'),
    ('Deportes', 'EGRESO', '🏋️', 'rgba(251, 146, 60, 0.2); color: #fb923c', 'gimnasio,megatlon,sportclub,futbol,padel,tenis'),
    ('Estética', 'EGRESO', '💅', 'rgba(244, 114, 182, 0.2); color: #f472b6', 'peluqueria,barberia,estetica,spa,uñas'),
    ('Mascotas', 'EGRESO', '🐶', 'rgba(250, 204, 21, 0.2); color: #facc15', 'veterinaria,petshop,royal canin,mascotas,perro,gato'),
    ('Otros', 'EGRESO', '📦', 'rgba(156, 163, 175, 0.2); color: #9ca3af', ''),
    
    # INGRESOS
    ('Sueldo', 'INGRESO', '💼', 'rgba(16, 185, 129, 0.2); color: #10b981', 'haberes,sueldo,honorarios'),
    ('Ventas', 'INGRESO', '🧾', 'rgba(5, 150, 105, 0.2); color: #059669', 'recaudacion,liquid,payway,naranja,mercado pago,cobro'),
    ('Transferencia recibida', 'INGRESO', '💸', 'rgba(52, 211, 153, 0.2); color: #34d399', 'transferencia de terceros,credito transferencia coelsa,recibiste una transferencia,recibiste transf cash out,credito cash out'),
    ('Intereses', 'INGRESO', '🏦', 'rgba(20, 184, 166, 0.2); color: #14b8a6', 'interes,plazo fijo,rendimiento'),
    ('Inversiones', 'INGRESO', '📈', 'rgba(16, 185, 129, 0.2); color: #10b981', 'cedear,bono,accion,fondo comun'),
    ('Reembolsos', 'INGRESO', '📦', 'rgba(94, 234, 212, 0.2); color: #5eead4', 'dev.compra,devolucion,reverso'),
    ('Regalos', 'INGRESO', '🎁', 'rgba(14, 165, 233, 0.2); color: #0ea5e9', 'regalo'),
    ('Otros Ingresos', 'INGRESO', '🧮', 'rgba(156, 163, 175, 0.2); color: #9ca3af', ''),
    
    # OTROS
    ('Movimiento Interno', 'OTRO', '🔄', 'rgba(99, 102, 241, 0.2); color: #6366f1', 'ctas propias,cuenta propia,movimiento entre tus cuentas,transferencia de cuenta tuya,extraccion,cajero automatico'),
    ('Sin Categorizar', 'OTRO', '❓', 'rgba(107, 114, 128, 0.2); color: #9ca3af', '')
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for nombre, tipo, emoji, color_css, palabras in CATEGORIAS:
        cursor.execute('''
            INSERT OR REPLACE INTO categorias_maestras (nombre, tipo, emoji, color_css, palabras_clave)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, tipo, emoji, color_css, palabras))
    conn.commit()
    conn.close()
    print("Categorías maestras inyectadas con éxito.")

if __name__ == "__main__":
    seed()
