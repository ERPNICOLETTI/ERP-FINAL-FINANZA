// APP PAGOS - Frontend Inteligente v5.2.0 💳🧠

const pagosApp = {
    state: {
        anio: '2026',
        mes: new Date().getMonth() + 1, // Mes actual
        estado: '',
        search: ''
    },

    init() {
        const today = new Date();
        // Formatear mes a 2 dígitos
        this.state.mes = this.state.mes.toString().padStart(2, '0');
        
        document.getElementById('filter-anio').value = this.state.anio;
        document.getElementById('filter-mes').value = this.state.mes;

        this.bindEvents();
        this.fetchPagos();
    },

    bindEvents() {
        document.getElementById('filter-anio').addEventListener('change', (e) => {
            this.state.anio = e.target.value;
            this.fetchPagos();
        });

        document.getElementById('filter-mes').addEventListener('change', (e) => {
            this.state.mes = e.target.value;
            this.fetchPagos();
        });

        document.getElementById('filter-estado').addEventListener('change', (e) => {
            this.setEstado(e.target.value);
        });

        document.getElementById('pro-search').addEventListener('input', (e) => {
            this.state.search = e.target.value.toLowerCase();
            this.renderTable(); // Búsqueda rápida offline
        });
    },

    setEstado(estado) {
        this.state.estado = estado;
        document.getElementById('filter-estado').value = estado;
        
        // Actualizar visual de pills
        document.querySelectorAll('.status-pills .pill').forEach(p => p.classList.remove('active'));
        if(estado === '') document.querySelector('.status-pills .pill').classList.add('active');
        if(estado === 'PENDIENTE') document.querySelector('.status-pills .pending').classList.add('active');
        if(estado === 'PAGADO') document.querySelector('.status-pills .completed').classList.add('active');
        
        this.fetchPagos();
    },

    async fetchPagos() {
        let url = `/api/pagos?periodo_anio=${this.state.anio}`;
        if(this.state.mes) url += `&periodo_mes=${this.state.mes}`;
        if(this.state.estado) url += `&estado=${this.state.estado}`;

        try {
            const res = await fetch(url);
            this.pagosData = await res.json();
            this.renderTable();
        } catch (e) {
            console.error("Error cargando pagos:", e);
        }
    },

    renderTable() {
        const tbody = document.getElementById('tbody-pagos');
        tbody.innerHTML = '';

        if(!this.pagosData) return;

        let filtered = this.pagosData;
        if(this.state.search) {
            filtered = filtered.filter(p => 
                (p.concepto && p.concepto.toLowerCase().includes(this.state.search)) ||
                (p.categoria && p.categoria.toLowerCase().includes(this.state.search))
            );
        }

        const hoy = new Date().toISOString().split('T')[0];

        filtered.forEach(p => {
            // Lógica de Estado Dinámico 💀🔴🟢
            let statusIcon = "🔴 PENDIENTE";
            let statusClass = "status-warn";
            
            if(p.estado === 'PAGADO') {
                statusIcon = "🟢 PAGADO";
                statusClass = "status-ok";
            } else if (p.estado === 'PENDIENTE' && p.fecha_vencimiento && p.fecha_vencimiento < hoy) {
                statusIcon = "💀 VENCIDO";
                statusClass = "status-error";
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="${statusClass}">${statusIcon}</span></td>
                <td>${p.fecha_vencimiento || '---'}</td>
                <td><span class="badge badge-cat">${p.categoria}</span></td>
                <td><strong>${p.concepto}</strong></td>
                <td>$ ${parseFloat(p.monto).toLocaleString('es-AR', {minimumFractionDigits:2})}</td>
                <td>
                    <div style="display:flex; gap:10px;">
                        ${p.path_boleta ? `<button class="btn-primary-main btn-sm" onclick="pagosApp.openFile('${p.path_boleta}')">📄 Boleta</button>` : ''}
                        ${p.path_comprobante ? `<button class="btn-ok btn-sm" onclick="pagosApp.openFile('${p.path_comprobante}')">💵 Recibo</button>` : ''}
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    openFile(rawPath) {
        // Link de Acero: Normalización e indexación en frontend (Regla de Independencia v5)
        let safePath = rawPath.replace(/\\/g, '/');
        
        // Recortar la raiz absoluta de la bóveda para hacerla URL universal
        const targetToken = "modulo_pagos/archivos_pagos/";
        if(safePath.includes(targetToken)){
            safePath = safePath.split(targetToken)[1];
        }

        // Construir la URL hacia el mount estático de FastAPI
        const serveUrl = `/archivos/pagos/${safePath}`;
        window.open(serveUrl, '_blank');
    }
};

// Iniciar aplicación al cargar HTML
document.addEventListener('DOMContentLoaded', () => pagosApp.init());
