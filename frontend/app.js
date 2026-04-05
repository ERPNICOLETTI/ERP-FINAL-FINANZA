/**
 * ERP Central Intelligence - Frontend Logic v4.6
 * Bóveda de Gestión de Compras & Ingesta Híbrida 🧾🧠
 */

const app = {
    allFacturas: [],
    currentFilter: 'all',
    selectedFactura: null,
    isProcessing: false,

    init() {
        this.bindEvents();
        this.initDropzones();
        this.initSpotlight();
    },

    bindEvents() {
        const processBtn = document.getElementById('btn-process');
        if (processBtn) processBtn.addEventListener('click', () => this.processInboxes());

        // Filtros de la tabla
        document.querySelectorAll('.pill').forEach(pill => {
            pill.addEventListener('click', (e) => {
                document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                this.currentFilter = pill.dataset.filter;
                this.renderFacturas();
            });
        });

        // Dropzone del Sidebar
        const sidebarDrop = document.getElementById('dropzone-sidebar');
        if (sidebarDrop) {
            sidebarDrop.addEventListener('dragover', (e) => { e.preventDefault(); sidebarDrop.classList.add('dragover'); });
            sidebarDrop.addEventListener('dragleave', () => sidebarDrop.classList.remove('dragover'));
            sidebarDrop.addEventListener('drop', (e) => this.handleSidebarDrop(e));
            sidebarDrop.addEventListener('click', () => document.getElementById('file-vincular').click());
        }

        const fileInput = document.getElementById('file-vincular');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) this.vincularFactura(this.selectedFactura.id, e.target.files[0]);
            });
        }

        // Boton de guardado de correcciones
        const btnSave = document.getElementById('btn-save-fields');
        if (btnSave) {
            btnSave.addEventListener('click', () => this.saveCorrections());
        }
    },

    // --- NAVEGACIÓN ---
    showModule(modulo) {
        if (modulo === 'compras') {
            document.querySelector('.modules-grid').classList.add('hidden');
            document.querySelector('.trigger-container').classList.add('hidden');
            document.getElementById('view-compras').classList.remove('hidden');
            this.fetchFacturas();
        }
    },

    showDashboard() {
        document.getElementById('view-compras').classList.add('hidden');
        document.querySelector('.modules-grid').classList.remove('hidden');
        document.querySelector('.trigger-container').classList.remove('hidden');
        this.closeSidebar();
    },

    // --- LÓGICA DE COMPRAS ---
    async fetchFacturas() {
        const statusMsg = document.getElementById('status-message');
        try {
            const response = await fetch('/api/facturas');
            this.allFacturas = await response.json();
            this.updateStats();
            this.renderFacturas();
        } catch (err) {
            console.error("Error cargando facturas", err);
        }
    },

    updateStats() {
        const total = this.allFacturas.length;
        const pending = this.allFacturas.filter(f => !f.tiene_foto).length;
        const completed = total - pending;

        document.getElementById('count-all').textContent = total;
        document.getElementById('count-pending').textContent = pending;
        document.getElementById('count-completed').textContent = completed;
    },

    renderFacturas() {
        const tbody = document.getElementById('tbody-compras');
        const filter = this.currentFilter;
        
        let filtered = this.allFacturas;
        if (filter === 'pending') filtered = this.allFacturas.filter(f => !f.tiene_foto);
        if (filter === 'completed') filtered = this.allFacturas.filter(f => f.tiene_foto);

        tbody.innerHTML = filtered.map(f => {
            const statusClass = f.tiene_foto ? 'green' : 'red';
            // Padding visual 5-8
            const pv = String(f.punto_venta || '').padStart(5, '0');
            const num = String(f.numero_comprobante || '').padStart(8, '0');
            
            return `
                <tr onclick="app.openSidebar(${f.id})">
                    <td><span class="status-dot ${statusClass}"></span></td>
                    <td>${f.fecha}</td>
                    <td>${f.proveedor}</td>
                    <td>${pv}-${num}</td>
                    <td>$ ${Number(f.total).toLocaleString()}</td>
                    <td>
                        ${f.path_archivo ? `
                            <button class="btn-eye" onclick="event.stopPropagation(); app.viewFile('${f.path_archivo}', ${f.tiene_foto})">👁️</button>
                        ` : '<span style="opacity:0.3">No disp.</span>'}
                    </td>
                </tr>
            `;
        }).join('');
    },

    // --- SIDEBAR & VINCULACIÓN ---
    openSidebar(id) {
        const f = this.allFacturas.find(i => i.id === id);
        if (!f) return;
        this.selectedFactura = f;

        const sidebar = document.getElementById('sidebar-vincular');
        const details = document.getElementById('sidebar-details');
        
        // Formatear metadatos JSON para visualización
        let metaHtml = "";
        try {
            const meta = JSON.parse(f.meta_json || '{}');
            metaHtml = Object.entries(meta).map(([k, v]) => {
                if(typeof v === 'object') return ""; 
                return `<p><strong>${k}:</strong> ${v}</p>`;
            }).join('');
        } catch(e) { metaHtml = "<p>Error cargando metadata</p>"; }

        details.innerHTML = `
            <p><strong>ID Interno:</strong> ${f.id}</p>
            <p><strong>Proveedor:</strong> ${f.proveedor}</p>
            <p><strong>Origen:</strong> ${f.origen}</p>
            <div class="meta-box">${metaHtml}</div>
        `;

        // Llenar campos de edición
        document.getElementById('edit-pv').value = f.punto_venta || '';
        document.getElementById('edit-num').value = f.numero_comprobante || '';
        
        document.getElementById('sidebar-status').textContent = '';
        sidebar.classList.remove('hidden');
    },

    closeSidebar() {
        document.getElementById('sidebar-vincular').classList.add('hidden');
        this.selectedFactura = null;
    },

    async saveCorrections() {
        if (!this.selectedFactura) return;
        const fid = this.selectedFactura.id;
        const pv = document.getElementById('edit-pv').value;
        const num = document.getElementById('edit-num').value;

        try {
            const res = await fetch(`/api/facturas/update/${fid}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ punto_venta: pv, numero_comprobante: num })
            });
            if (res.ok) {
                document.getElementById('sidebar-status').textContent = '✅ Cambios guardados';
                this.fetchFacturas(); // Recargar
            }
        } catch (err) {
            console.error("Error guardando correcciones", err);
        }
    },

    handleSidebarDrop(e) {
        e.preventDefault();
        document.getElementById('dropzone-sidebar').classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0 && this.selectedFactura) {
            this.vincularFactura(this.selectedFactura.id, files[0]);
        }
    },

    async vincularFactura(id, file) {
        const status = document.getElementById('sidebar-status');
        status.textContent = `⏳ Vinculando ${file.name}...`;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`/api/compras/vincular?id_factura=${id}`, {
                method: 'POST',
                body: formData
            });
            const res = await response.json();
            if (res.status === 'success') {
                status.textContent = '✅ Vinculación Exitosa';
                status.style.color = 'var(--success)';
                this.fetchFacturas(); // Actualizar tabla
                setTimeout(() => this.closeSidebar(), 1500);
            } else {
                status.textContent = `❌ Error: ${res.message}`;
                status.style.color = '#ef4444';
            }
        } catch (err) {
            status.textContent = `❌ Error de red: ${err}`;
        }
    },

    viewFile(path, tieneFoto) {
        // tieneFoto ? Bóveda (archivos) : Histórico (crudos)
        const prefix = tieneFoto ? '/archivos/compras/' : '/historico/compras/';
        window.open(`${prefix}${path}`, '_blank');
    },

    // --- DASHBOARD: INGESTA ---
    initDropzones() {
        const dropzones = document.querySelectorAll('.dropzone-card');
        dropzones.forEach(card => {
            const dropArea = card.querySelector('.drop-area');
            const modulo = card.getAttribute('data-modulo');
            const counterEl = dropArea.querySelector('.file-counter');
            let pendingCount = 0;

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
                dropArea.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
            });

            dropArea.addEventListener('dragenter', () => dropArea.classList.add('dragover'));
            dropArea.addEventListener('dragover', () => dropArea.classList.add('dragover'));
            dropArea.addEventListener('dragleave', () => dropArea.classList.remove('dragover'));
            dropArea.addEventListener('drop', async (e) => {
                dropArea.classList.remove('dragover');
                const files = [...e.dataTransfer.files];
                pendingCount += files.length;
                counterEl.textContent = `${pendingCount} listos`;
                counterEl.classList.add('has-files');

                for (const file of files) {
                    await this.uploadToInbox(file, modulo);
                }
            });

            card.addEventListener('resetCounter', () => {
                pendingCount = 0;
                counterEl.textContent = `0 pendientes`;
                counterEl.classList.remove('has-files');
            });
        });
    },

    async uploadToInbox(file, modulo) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            await fetch(`/api/upload/${modulo}`, { method: 'POST', body: formData });
        } catch (err) { console.error("Upload failed", err); }
    },

    async processInboxes() {
        if(this.isProcessing) return;
        const btn = document.getElementById('btn-process');
        const status = document.getElementById('status-message');

        this.isProcessing = true;
        btn.classList.add('loading');
        btn.textContent = '⚡ Sincronizando... ⚡';

        try {
            const response = await fetch('/api/process', { method: 'POST' });
            const res = await response.json();
            if (res.status === 'success') {
                status.textContent = '¡Ecosistema Sincronizado!';
                status.style.color = 'var(--success)';
                document.querySelectorAll('.dropzone-card').forEach(c => c.dispatchEvent(new Event('resetCounter')));
            }
        } catch (err) {
            status.textContent = 'Error en sincronización';
            status.style.color = 'red';
        } finally {
            this.isProcessing = false;
            btn.classList.remove('loading');
            btn.textContent = '⚡ Sincronizar Ecosistema ⚡';
        }
    },

    initSpotlight() {
        const searchInput = document.getElementById('spotlight-search');
        const searchResults = document.getElementById('search-results');
        let timeout;

        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            const q = e.target.value.trim();
            if (q.length < 3) { searchResults.classList.add('hidden'); return; }

            timeout = setTimeout(async () => {
                const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                if (data.results && data.results.length > 0) {
                    searchResults.innerHTML = data.results.map(r => `
                        <div class="search-result-item" onclick="app.handleSearchClick('${r.source}', ${r.record_id})">
                            <div class="meta">${r.source} | ID: ${r.record_id} <span class="amount">$ ${Number(r.monto).toLocaleString()}</span></div>
                            <div class="title">${r.nombre} (${r.fecha})</div>
                        </div>
                    `).join('');
                    searchResults.classList.remove('hidden');
                }
            }, 300);
        });

        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target)) searchResults.classList.add('hidden');
        });
    },

    handleSearchClick(source, id) {
        if (source === 'Factura') {
            this.showModule('compras');
            setTimeout(() => this.openSidebar(id), 500);
        }
    }
};

window.app = app;
document.addEventListener('DOMContentLoaded', () => app.init());
