#!/usr/bin/env python3
"""
Dashboard Web de Eli - Backend Flask
Sistema J.A.R.V.I.S. - Control y Monitoreo
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import psutil
import time
from datetime import datetime
from threading import Thread
import sys
import os

# Agregar el directorio padre al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comandos import ejecutar_comando, DISPATCH

# Configuración Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'eli-jarvis-2026'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Estado global del sistema
sistema_estado = {
    'uptime_inicio': time.time(),
    'comandos_ejecutados': 0,
    'ultimo_comando': None,
    'estado_actual': 'Inactivo',
    'eli_corriendo': False
}

historial_comandos = []
metricas_historicas = {
    'timestamps': [],
    'cpu': [],
    'ram': [],
    'latencia': []
}

# ============================================================================
# RUTAS WEB
# ============================================================================

@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Estado actual del sistema"""
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'sistema': get_system_metrics(),
        'eli': sistema_estado,
        'comandos_disponibles': len(DISPATCH)
    })

@app.route('/api/comandos')
def api_comandos():
    """Lista de comandos disponibles"""
    comandos_info = {}
    for nombre in sorted(DISPATCH.keys()):
        # Categorizar comandos por prefijo
        if nombre.startswith('abrir_'):
            categoria = 'Apps'
        elif nombre.startswith('spotify_'):
            categoria = 'Spotify'
        elif nombre.startswith('gmail_'):
            categoria = 'Gmail'
        elif nombre.startswith('calendario_'):
            categoria = 'Calendar'
        elif nombre in ['subir_volumen', 'bajar_volumen', 'silenciar', 'volumen_especifico']:
            categoria = 'Audio'
        elif nombre in ['minimizar_ventana', 'maximizar_ventana', 'cerrar_ventana']:
            categoria = 'Ventanas'
        elif nombre.startswith('buscar_'):
            categoria = 'Web'
        else:
            categoria = 'Sistema'
        
        if categoria not in comandos_info:
            comandos_info[categoria] = []
        comandos_info[categoria].append(nombre)
    
    return jsonify(comandos_info)

@app.route('/api/historial')
def api_historial():
    """Historial de comandos ejecutados"""
    return jsonify({
        'total': len(historial_comandos),
        'comandos': historial_comandos[-50:]
    })

@app.route('/api/metricas')
def api_metricas():
    """Métricas históricas del sistema"""
    return jsonify(metricas_historicas)

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Cliente conectado"""
    print(f"🌐 Cliente conectado: {request.sid}")
    emit('connected', {
        'mensaje': 'Conectado al sistema Eli',
        'timestamp': datetime.now().isoformat()
    })
    emit('estado_actualizado', sistema_estado)

@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectado"""
    print(f"🌐 Cliente desconectado: {request.sid}")

@socketio.on('ejecutar_comando')
def handle_ejecutar_comando(data):
    """Ejecutar comando desde el dashboard"""
    comando = data.get('comando')
    parametros = data.get('parametros', {})
    
    print(f"🎯 Comando recibido: {comando}")
    
    try:
        sistema_estado['estado_actual'] = 'Ejecutando'
        socketio.emit('estado_actualizado', sistema_estado)
        
        inicio = time.time()
        resultado = ejecutar_comando(comando, parametros)
        latencia = time.time() - inicio
        
        registro = {
            'timestamp': datetime.now().isoformat(),
            'comando': comando,
            'parametros': parametros,
            'resultado': resultado,
            'latencia': round(latencia, 2),
            'exito': True
        }
        historial_comandos.append(registro)
        sistema_estado['comandos_ejecutados'] += 1
        sistema_estado['ultimo_comando'] = comando
        sistema_estado['estado_actual'] = 'Listo'
        
        socketio.emit('comando_ejecutado', registro)
        socketio.emit('estado_actualizado', sistema_estado)
        
        return {'exito': True, 'resultado': resultado, 'latencia': latencia}
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
        
        registro = {
            'timestamp': datetime.now().isoformat(),
            'comando': comando,
            'error': error_msg,
            'exito': False
        }
        historial_comandos.append(registro)
        sistema_estado['estado_actual'] = 'Error'
        
        socketio.emit('comando_error', registro)
        socketio.emit('estado_actualizado', sistema_estado)
        
        return {'exito': False, 'error': error_msg}

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_system_metrics():
    """Obtener métricas del sistema"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memoria = psutil.virtual_memory()
        disco = psutil.disk_usage('/')
        
        temp = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temp = entries[0].current
                        break
        except:
            pass
        
        return {
            'cpu': {
                'porcentaje': round(cpu_percent, 1),
                'cores': psutil.cpu_count()
            },
            'ram': {
                'total_gb': round(memoria.total / (1024**3), 1),
                'usado_gb': round(memoria.used / (1024**3), 1),
                'porcentaje': round(memoria.percent, 1)
            },
            'disco': {
                'total_gb': round(disco.total / (1024**3), 1),
                'usado_gb': round(disco.used / (1024**3), 1),
                'porcentaje': round(disco.percent, 1)
            },
            'temperatura': temp,
            'uptime_segundos': round(time.time() - sistema_estado['uptime_inicio'])
        }
    except Exception as e:
        print(f"⚠️ Error métricas: {e}")
        return {}

def background_metrics_updater():
    """Actualizar métricas periódicamente"""
    while True:
        try:
            metricas = get_system_metrics()
            socketio.emit('metricas_actualizadas', metricas)
        except Exception as e:
            print(f"⚠️ Error updater: {e}")
        socketio.sleep(2)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 ELI DASHBOARD - Sistema J.A.R.V.I.S.")
    print("=" * 60)
    print(f"📊 Comandos: {len(DISPATCH)}")
    print(f"📱 Local: http://localhost:5000")
    print("=" * 60)
    
    metrics_thread = Thread(target=background_metrics_updater, daemon=True)
    metrics_thread.start()
    
    sistema_estado['eli_corriendo'] = True
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
