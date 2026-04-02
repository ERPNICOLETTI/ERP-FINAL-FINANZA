import sys
import os
import requests
import importlib

# CEREBRO ERP - Consola de Control Central (Orquestador DDD) 🦾🧠⚖️
# Este archivo es el "Hub" que conecta con las Neuronas de cada módulo.

API_URL = "http://127.0.0.1:5005"

def query_api(endpoint, params=None, method="GET", data=None):
    try:
        url = f"{API_URL}/{endpoint}"
        if method.upper() == "POST":
            response = requests.post(url, json=data, params=params)
        else:
            response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión con API: {e}")
        return None

def mostrar_ayuda():
    print("\n🧠 CEREBRO ERP - CONSOLA CENTRAL")
    print("-" * 50)
    print("ÁREAS DISPONIBLES:")
    print("   -> tarjetas     | Gestión de recaudación y POS.")
    print("   -> facturas     | Gestión de ARCA (AFIP) y CALIM.")
    print("   -> bancos       | Tesorería y conciliación.")
    print("-" * 50)
    print("Para ver comandos de una neurona: python cerebro.py <AREA>")
    print("-" * 50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        mostrar_ayuda()
        sys.exit(0)
    
    area = sys.argv[1].lower()
    command = sys.argv[2].lower() if len(sys.argv) > 2 else None
    args = sys.argv[3:] if len(sys.argv) > 3 else []
    
    # Mapeo de áreas a sus respectivas neuronas
    mapping = {
        "tarjetas": "modulo_tarjetas.neuron_tarjetas",
        "facturas": "modulo_compras.neuron_compras",
        "bancos": "modulo_bancos.neuron_bancos"
    }
    
    if area in mapping:
        try:
            # Importación dinámica de la neurona especialista
            neuron = importlib.import_module(mapping[area])
            if command:
                neuron.handle_command(command, args, query_api)
            else:
                print(f"\n🧬 NEURONA {area.upper()} - Comandos disponibles:")
                # Si la neurona no recibe comando, mostramos su ayuda básica (implementada dentro de handle_command o similar)
                neuron.handle_command("help", [], query_api)
        except ImportError as e:
            print(f"Error al cargar la neurona {area}: {e}")
        except AttributeError as e:
            print(f"La neurona {area} no tiene un manejador válido: {e}")
    else:
        mostrar_ayuda()
