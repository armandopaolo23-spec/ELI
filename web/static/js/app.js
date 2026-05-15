const socket = io();
let comandosDisponibles = {};
let chart = null;

document.addEventListener('DOMContentLoaded', () => {
    console.log('🤖 Dashboard iniciando...');
    setupSocketEvents();
    setupUIEvents();
    cargarComandos();
    cargarHistorial();
    setInterval(updateClock, 1000);
    updateClock();
    initChart();
});

function setupSocketEvents() {
    socket.on('connect', () => {
        console.log('✅ Conectado');
        updateConnectionStatus(true);
    });
    
    socket.on('disconnect', () => {
        console.log('❌ Desconectado');
        updateConnectionStatus(false);
    });
    
    socket.on('estado_actualizado', (data) => {
        updateEstadoEli(data);
    });
    
    socket.on('metricas_actualizadas', (data) => {
        updateMetricas(data);
    });
    
    socket.on('comando_ejecutado', (data) => {
        mostrarResultado(data);
        agregarAlHistorial(data);
    });
    
    socket.on('comando_error', (data) => {
        mostrarError(data);
        agregarAlHistorial(data);
    });
}

function setupUIEvents() {
    document.getElementById('ejecutar-btn').addEventListener('click', ejecutarComando);
    document.getElementById('comando-select').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') ejecutarComando();
    });
    document.getElementById('limpiar-historial').addEventListener('click', limpiarHistorial);
}

function updateConnectionStatus(connected) {
    const statusDiv = document.getElementById('connection-status');
    if (connected) {
        statusDiv.innerHTML = `
            <div class="w-3 h-3 bg-green-500 rounded-full"></div>
            <span class="text-sm text-green-400">Conectado</span>
        `;
    } else {
        statusDiv.innerHTML = `
            <div class="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
            <span class="text-sm text-red-400">Desconectado</span>
        `;
    }
}

function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('es-PE', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('current-time').textContent = timeStr;
}

function updateEstadoEli(data) {
    const estadoSpan = document.getElementById('eli-estado');
    estadoSpan.textContent = data.estado_actual;
    estadoSpan.className = 'px-3 py-1 rounded-full text-sm ';
    
    switch(data.estado_actual) {
        case 'Listo':
        case 'Inactivo':
            estadoSpan.className += 'bg-green-900 text-green-300';
            break;
        case 'Ejecutando':
            estadoSpan.className += 'bg-yellow-900 text-yellow-300 animate-pulse';
            break;
        case 'Error':
            estadoSpan.className += 'bg-red-900 text-red-300';
            break;
        default:
            estadoSpan.className += 'bg-gray-700 text-gray-300';
    }
    
    document.getElementById('eli-comandos').textContent = data.comandos_ejecutados;
    
    if (data.ultimo_comando) {
        document.getElementById('eli-ultimo').textContent = data.ultimo_comando;
        document.getElementById('eli-ultimo').className = 'font-mono text-sm text-blue-400';
    }
    
    if (data.uptime_inicio) {
        const uptime = Date.now()/1000 - data.uptime_inicio;
        const hours = Math.floor(uptime / 3600);
        const minutes = Math.floor((uptime % 3600) / 60);
        document.getElementById('eli-uptime').textContent = `${hours}h ${minutes}m`;
    }
}

function updateMetricas(data) {
    if (!data.cpu) return;
    
    document.getElementById('cpu-percent').textContent = `${data.cpu.porcentaje}%`;
    document.getElementById('cpu-bar').style.width = `${data.cpu.porcentaje}%`;
    
    document.getElementById('ram-percent').textContent = `${data.ram.porcentaje}%`;
    document.getElementById('ram-bar').style.width = `${data.ram.porcentaje}%`;
    document.getElementById('ram-usado').textContent = data.ram.usado_gb;
    document.getElementById('ram-total').textContent = data.ram.total_gb;
    
    document.getElementById('disco-percent').textContent = `${data.disco.porcentaje}%`;
    document.getElementById('disco-bar').style.width = `${data.disco.porcentaje}%`;
    
    if (data.temperatura) {
        document.getElementById('temp').textContent = `${Math.round(data.temperatura)}°C`;
    }
    
    updateChart(data.cpu.porcentaje, data.ram.porcentaje);
}

function mostrarResultado(data) {
    const container = document.getElementById('resultado-container');
    container.className = 'mt-4';
    container.innerHTML = `
        <div class="bg-gray-800 border border-green-700 rounded-lg p-4">
            <div class="flex items-start space-x-3">
                <div class="text-2xl">✅</div>
                <div class="flex-1">
                    <div class="font-semibold mb-1">Ejecutado</div>
                    <div class="text-sm text-gray-400">${data.resultado || 'Completado'}</div>
                    <div class="text-xs text-gray-500 mt-2">Latencia: ${data.latencia}s</div>
                </div>
            </div>
        </div>
    `;
    
    setTimeout(() => {
        container.classList.add('hidden');
    }, 5000);
}

function mostrarError(data) {
    const container = document.getElementById('resultado-container');
    container.className = 'mt-4';
    container.innerHTML = `
        <div class="bg-gray-800 border border-red-700 rounded-lg p-4">
            <div class="flex items-start space-x-3">
                <div class="text-2xl">❌</div>
                <div class="flex-1">
                    <div class="font-semibold mb-1">Error</div>
                    <div class="text-sm text-red-400">${data.error}</div>
                </div>
            </div>
        </div>
    `;
    
    setTimeout(() => {
        container.classList.add('hidden');
    }, 5000);
}

async function cargarComandos() {
    try {
        const response = await fetch('/api/comandos');
        comandosDisponibles = await response.json();
        
        const select = document.getElementById('comando-select');
        select.innerHTML = '<option value="">Selecciona un comando...</option>';
        
        for (const [categoria, comandos] of Object.entries(comandosDisponibles)) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = categoria;
            
            comandos.forEach(cmd => {
                const option = document.createElement('option');
                option.value = cmd;
                option.textContent = cmd.replace(/_/g, ' ');
                optgroup.appendChild(option);
            });
            
            select.appendChild(optgroup);
        }
        
        mostrarListaComandos();
        
    } catch (error) {
        console.error('Error:', error);
    }
}

function mostrarListaComandos() {
    const container = document.getElementById('comandos-lista');
    container.innerHTML = '';
    
    for (const [categoria, comandos] of Object.entries(comandosDisponibles)) {
        const div = document.createElement('div');
        div.className = 'bg-gray-800 rounded-lg p-4';
        
        const titulo = document.createElement('h3');
        titulo.className = 'font-bold mb-2 text-blue-400';
        titulo.textContent = categoria;
        div.appendChild(titulo);
        
        const lista = document.createElement('div');
        lista.className = 'space-y-1';
        
        comandos.forEach(cmd => {
            const item = document.createElement('div');
            item.className = 'text-sm text-gray-400 hover:text-white cursor-pointer';
            item.textContent = '• ' + cmd.replace(/_/g, ' ');
            item.onclick = () => {
                document.getElementById('comando-select').value = cmd;
            };
            lista.appendChild(item);
        });
        
        div.appendChild(lista);
        container.appendChild(div);
    }
}

function ejecutarComando() {
    const select = document.getElementById('comando-select');
    const comando = select.value;
    
    if (!comando) {
        alert('Selecciona un comando');
        return;
    }
    
    console.log('▶️ Ejecutando:', comando);
    
    socket.emit('ejecutar_comando', {
        comando: comando,
        parametros: {}
    });
}

async function cargarHistorial() {
    try {
        const response = await fetch('/api/historial');
        const data = await response.json();
        data.comandos.forEach(cmd => agregarAlHistorial(cmd));
    } catch (error) {
        console.error('Error:', error);
    }
}

function agregarAlHistorial(data) {
    const container = document.getElementById('historial-container');
    
    if (container.children[0]?.textContent.includes('Sin comandos')) {
        container.innerHTML = '';
    }
    
    const item = document.createElement('div');
    item.className = `bg-gray-800 rounded-lg p-3 ${data.exito ? 'border-l-4 border-green-500' : 'border-l-4 border-red-500'}`;
    
    const time = new Date(data.timestamp).toLocaleTimeString('es-PE');
    
    item.innerHTML = `
        <div class="flex items-start justify-between">
            <div class="flex-1">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-sm font-mono text-blue-400">${data.comando}</span>
                    ${data.latencia ? `<span class="text-xs text-gray-500">${data.latencia}s</span>` : ''}
                </div>
                ${data.resultado ? `<div class="text-sm text-gray-400">${data.resultado}</div>` : ''}
                ${data.error ? `<div class="text-sm text-red-400">${data.error}</div>` : ''}
            </div>
            <div class="text-xs text-gray-500">${time}</div>
        </div>
    `;
    
    container.insertBefore(item, container.firstChild);
    
    while (container.children.length > 50) {
        container.removeChild(container.lastChild);
    }
}

function limpiarHistorial() {
    const container = document.getElementById('historial-container');
    container.innerHTML = `<div class="text-center text-gray-500 py-8">Historial limpiado</div>`;
}

function initChart() {
    const ctx = document.getElementById('metricsChart').getContext('2d');
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'CPU %',
                    data: [],
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'RAM %',
                    data: [],
                    borderColor: 'rgb(34, 197, 94)',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#9ca3af' }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: '#9ca3af' },
                    grid: { color: '#374151' }
                },
                x: {
                    ticks: { color: '#9ca3af' },
                    grid: { color: '#374151' }
                }
            }
        }
    });
}

function updateChart(cpu, ram) {
    if (!chart) return;
    
    const now = new Date().toLocaleTimeString('es-PE', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
    });
    
    chart.data.labels.push(now);
    chart.data.datasets[0].data.push(cpu);
    chart.data.datasets[1].data.push(ram);
    
    if (chart.data.labels.length > 20) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
    }
    
    chart.update('none');
}

console.log('🤖 Dashboard listo');
