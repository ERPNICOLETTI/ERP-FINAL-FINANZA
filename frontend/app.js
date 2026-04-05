/**
 * ERP Central Intelligence - Ecosistema Compras v4.7.0 🧾🧠
 * Gestión Unificada: Ingesta + Bóveda + Filtros Cronológicos
 */

const app = {
    allFacturas: [],
    backupFacturas: [], // Para búsqueda local pro
    selectedFactura: null,
    sidebarFile: null,

    // Filtros de estado
    currentAnio: "2026",
    currentMes: "",
    currentFilter: "all",

    init() {
        this.bindEvents();
        this.fetchFacturas(); // Carga inicial directa
    },

    bindEvents() {
        // --- FILTROS CRONOLÓGICOS (Modo ML) ---
        const filterAnio = document.getElementById('filter-anio');
        const filterMes = document.getElementById('filter-mes');

        if (filterAnio) filterAnio.onchange = () => { this.currentAnio = filterAnio.value; this.fetchFacturas(); };
        if (filterMes) filterMes.onchange = () => { this.currentMes = filterMes.value; this.fetchFacturas(); };

        // --- BÚSQUEDA REACTIVA DE MATCH ATÓMICO (v4.8) ---
        const numInput = document.getElementById('edit-full-number');
        if (numInput) {
            let debounceTimer;
            numInput.oninput = (e) => {
                const q = e.target.value;
                clearTimeout(debounceTimer);
                if (q.length >= 3) {
                    debounceTimer = setTimeout(() => this.performSmartMatch(q), 400);
                } else {
                    this.clearMatch();
                }
            };
        }

        // --- BÚSQUEDA LOCAL PRO EN BÓVEDA ---
        const proSearch = document.getElementById('pro-search');
        if (proSearch) {
            proSearch.oninput = (e) => {
                const q = e.target.value.toLowerCase();
                this.allFacturas = this.backupFacturas.filter(f => 
                    f.proveedor.toLowerCase().includes(q) || 
                    f.cuit_proveedor?.includes(q) || 
                    f.numero_comprobante?.includes(q)
                );
                this.renderFacturas();
            };
        }

        // --- FILTROS DE ESTADO (PILLS) ---
        document.querySelectorAll('.pill').forEach(pill => {
            pill.onclick = () => {
                document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                this.currentFilter = pill.dataset.filter;
                this.renderFacturas();
            };
        });

        // --- INGESTA & DRAG & DROP ---
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');

        if (dropZone && fileInput) {
            dropZone.onclick = (e) => {
                // Si ya hay un archivo, no abrimos el selector al hacer click para permitir paneo
                if (!this.sidebarFile && e.target.tagName !== 'INPUT') {
                    fileInput.click();
                }
            };
            dropZone.ondragover = (e) => { e.preventDefault(); dropZone.style.borderColor = 'var(--accent-color)'; };
            dropZone.ondragleave = () => dropZone.style.borderColor = 'rgba(255,255,255,0.1)';
            dropZone.ondrop = (e) => {
                e.preventDefault();
                dropZone.style.borderColor = 'rgba(255,255,255,0.1)';
                if (e.dataTransfer.files.length) this.handleFilePreview(e.dataTransfer.files[0]);
            };
            fileInput.onchange = (e) => {
                if (e.target.files.length) this.handleFilePreview(e.target.files[0]);
            };
        }

        // --- SINCRONIZACIÓN ---
        const btnSync = document.getElementById('btn-process');
        if (btnSync) btnSync.onclick = () => this.sincronizarEcosistema();
    },

    async performSmartMatch(q) {
        try {
            const res = await fetch(`/api/compras/search?q=${q}`);
            const data = await res.json();
            
            if (data.results && data.results.length > 0) {
                const match = data.results[0]; // Tomamos el más cercano
                this.applyMatch(match);
            } else {
                this.clearMatch();
            }
        } catch (e) {
            console.error("Error en Smart Match", e);
        }
    },

    applyMatch(f) {
        this.selectedFactura = f;
        
        const card = document.getElementById('match-card');
        const badge = document.getElementById('match-origen');
        const fecha = document.getElementById('match-fecha');
        const details = document.getElementById('match-details');
        
        card.classList.remove('hidden');
        badge.textContent = f.origen.toUpperCase();
        badge.className = `badge ${f.origen.toLowerCase() === 'calim' ? 'calim' : ''}`;
        fecha.textContent = f.fecha;
        details.innerHTML = `<strong>${f.proveedor}</strong> - $${Number(f.total).toLocaleString()}<br>Monto Total A Conciliar.`;
    },

    clearMatch() {
        this.selectedFactura = null;
        document.getElementById('match-card').classList.add('hidden');
    },

    async confirmarVinculacion() {
        if (!this.selectedFactura || !this.sidebarFile) {
            alert("Sube la foto primero y asegúrate de que el sistema encuentre el número de factura.");
            return;
        }

        const statusLabel = document.getElementById('sidebar-status');
        statusLabel.style.color = 'var(--accent-color)';
        statusLabel.textContent = '💾 Archivado nominal y limpieza de origen...';
        
        const formData = new FormData();
        formData.append('file', this.sidebarFile);
        
        try {
            const res = await fetch(`/api/compras/vincular?id_factura=${this.selectedFactura.id}`, {
                method: 'POST',
                body: formData
            });
            
            const result = await res.json();
            if (result.status === 'success') {
                statusLabel.style.color = 'var(--success)';
                statusLabel.textContent = '✅ Archivado y eliminado de origen.';
                
                // --- LIMPIEZA TOTAL TRAS ÉXITO ---
                this.sidebarFile = null;
                document.getElementById('edit-full-number').value = '';
                document.getElementById('sidebar-preview').innerHTML = '<p class="preview-placeholder">Previsualización HD de Factura</p>';
                this.clearMatch();
                this.fetchFacturas(); // Refrescar lista principal
            } else {
                statusLabel.style.color = 'var(--danger)';
                statusLabel.textContent = '❌ Error: ' + result.message;
            }
        } catch (e) {
            statusLabel.textContent = '❌ Error de conexión';
        }
    },

    async fetchFacturas() {
        try {
            const url = `/api/facturas?anio=${this.currentAnio}&mes=${this.currentMes}`;
            const res = await fetch(url);
            const data = await res.json();
            
            this.allFacturas = data;
            this.backupFacturas = [...data];
            this.updateStats();
            this.renderFacturas();
        } catch (e) {
            console.error("Error cargando Bóveda", e);
        }
    },

    updateStats() {
        const total = this.backupFacturas.length;
        const pending = this.backupFacturas.filter(f => !f.tiene_foto).length;
        const completed = total - pending;

        document.getElementById('count-all').textContent = total;
        document.getElementById('count-pending').textContent = pending;
        document.getElementById('count-completed').textContent = completed;
    },

    renderFacturas() {
        const tbody = document.getElementById('tbody-compras');
        let filtered = this.allFacturas;

        if (this.currentFilter === 'pending') filtered = filtered.filter(f => !f.tiene_foto);
        if (this.currentFilter === 'completed') filtered = filtered.filter(f => f.tiene_foto);

        tbody.innerHTML = filtered.map(f => {
            const statusClass = f.tiene_foto ? 'green' : 'red';
            const pv = String(f.punto_venta || '').padStart(5, '0');
            const num = String(f.numero_comprobante || '').padStart(8, '0');

            return `
                <tr onclick="app.loadToIngesta(${f.id})">
                    <td><span class="status-dot ${statusClass}"></span></td>
                    <td>${f.fecha}</td>
                    <td>${f.proveedor}</td>
                    <td>${pv}-${num}</td>
                    <td>$ ${Number(f.total).toLocaleString()}</td>
                    <td>
                        ${f.path_archivo ? `
                            <button class="btn-sync" style="padding: 5px 10px; font-size: 0.7rem;" 
                                    onclick="event.stopPropagation(); app.viewFile('${f.path_archivo}', ${f.tiene_foto})">👁️ VER</button>
                        ` : '--'}
                    </td>
                </tr>
            `;
        }).join('');
    },

    handleFilePreview(file) {
        this.sidebarFile = file;
        const dropZone = document.getElementById('drop-zone');
        const previewContainer = document.getElementById('sidebar-preview');
        previewContainer.innerHTML = ''; 

        const fileUrl = URL.createObjectURL(file);
        
        if (file.type === 'application/pdf') {
            const embed = document.createElement('embed');
            embed.src = fileUrl;
            embed.type = 'application/pdf';
            previewContainer.appendChild(embed);
        } else if (file.type.startsWith('image/')) {
            const img = document.createElement('img');
            img.src = fileUrl;
            img.id = 'zoomable-img';
            img.style.width = '100%';
            previewContainer.appendChild(img);
            
            // Lógica de Zoom con Rueda
            let zoomPct = 100;
            dropZone.onwheel = (e) => {
                e.preventDefault();
                if (e.deltaY < 0) zoomPct += 15; // Zoom In
                else zoomPct -= 15; // Zoom Out
                
                zoomPct = Math.max(20, Math.min(zoomPct, 500)); // Limites
                img.style.width = `${zoomPct}%`;
                img.style.maxWidth = 'none';
                img.style.maxHeight = 'none';
                
                // Si hace zoom, alineamos al inicio para que el scroll empiece desde top-left
                if (zoomPct > 100) {
                    previewContainer.style.alignItems = 'flex-start';
                    previewContainer.style.justifyContent = 'flex-start';
                } else {
                    previewContainer.style.alignItems = 'center';
                    previewContainer.style.justifyContent = 'center';
                }
            };
            
            // Lógica de Paneo (Drag to Scroll)
            let isDown = false;
            let startX, startY, scrollLeft, scrollTop;
            
            dropZone.onmousedown = (e) => {
                isDown = true;
                dropZone.classList.add('active-pan');
                startX = e.pageX - dropZone.offsetLeft;
                startY = e.pageY - dropZone.offsetTop;
                scrollLeft = dropZone.scrollLeft;
                scrollTop = dropZone.scrollTop;
            };
            dropZone.onmouseleave = () => {
                isDown = false;
                dropZone.classList.remove('active-pan');
            };
            dropZone.onmouseup = () => {
                isDown = false;
                dropZone.classList.remove('active-pan');
            };
            dropZone.onmousemove = (e) => {
                if (!isDown) return;
                e.preventDefault();
                const x = e.pageX - dropZone.offsetLeft;
                const y = e.pageY - dropZone.offsetTop;
                const walkX = (x - startX) * 1.5; // Velocidad
                const walkY = (y - startY) * 1.5;
                dropZone.scrollLeft = scrollLeft - walkX;
                dropZone.scrollTop = scrollTop - walkY;
            };
        }
        
        document.getElementById('sidebar-status').textContent = `📄 ${file.name} listo.`;
    },

    loadToIngesta(id) {
        const f = this.backupFacturas.find(x => x.id === id);
        if (!f) return;

        this.selectedFactura = f;
        document.getElementById('edit-proveedor').value = f.proveedor;
        document.getElementById('edit-pv').value = f.punto_venta || '';
        document.getElementById('edit-numero').value = f.numero_comprobante || '';
        document.getElementById('edit-total').value = f.total;
        
        // Match Feedback Visual
        const feedback = document.getElementById('match-feedback');
        feedback.classList.remove('hidden');
        feedback.className = 'match-feedback success';
        feedback.innerHTML = `<strong>Factura Seleccionada</strong><br>Listo para vincular evidencia física.`;
    },

    async confirmarVinculacion() {
        if (!this.selectedFactura || !this.sidebarFile) {
            alert("Selecciona una factura de la tabla y carga un archivo.");
            return;
        }

        const statusLabel = document.getElementById('sidebar-status');
        statusLabel.textContent = '🚀 Archivando en Bóveda...';
        
        const formData = new FormData();
        formData.append('file', this.sidebarFile);
        
        try {
            const res = await fetch(`/api/compras/vincular?id_factura=${this.selectedFactura.id}`, {
                method: 'POST',
                body: formData
            });
            
            const result = await res.json();
            if (result.status === 'success') {
                statusLabel.style.color = 'var(--success)';
                statusLabel.textContent = '✅ Archivado por CUIT con éxito.';
                this.fetchFacturas(); // Recargar tabla
            } else {
                statusLabel.style.color = 'var(--danger)';
                statusLabel.textContent = '❌ Error: ' + result.message;
            }
        } catch (e) {
            statusLabel.textContent = '❌ Error de conexión';
        }
    },

    viewFile(path, tieneFoto) {
        // tieneFoto ? Bóveda (archivos) : Histórico (crudos)
        const prefix = tieneFoto ? '/archivos/compras/' : '/historico/compras/';
        window.open(`${prefix}${path}`, '_blank');
    },

    async sincronizarEcosistema() {
        const btn = document.getElementById('btn-process');
        const status = document.getElementById('status-message');
        
        btn.textContent = '⏳ Sincronizando...';
        btn.disabled = true;

        try {
            const response = await fetch('/api/process', { method: 'POST' });
            if (response.ok) {
                status.textContent = '✅ Ecosistema al día';
                this.fetchFacturas();
            }
        } catch (e) {
            status.textContent = '❌ Error';
        } finally {
            btn.textContent = '⚡ Sincronizar Ecosistema ⚡';
            btn.disabled = false;
        }
    }
};

window.app = app;
document.addEventListener('DOMContentLoaded', () => app.init());
