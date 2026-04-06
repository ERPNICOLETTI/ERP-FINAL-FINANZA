/**
 * ERP Central Intelligence - Ecosistema Compras v4.7.0 🧾🧠
 * Gestión Unificada: Ingesta + Bóveda + Filtros Cronológicos
 */

const app = {
    allFacturas: [],
    backupFacturas: [],
    currentFilter: 'all',
    selectedFactura: null,
    sidebarFile: null,
    
    currentAnio: new Date().getFullYear().toString(),
    currentMes: String(new Date().getMonth() + 1).padStart(2, '0'),
    
    // --- LÓGICA DE BUZÓN (MAZO DE CARTAS v4.9) ---
    inboxFiles: [],
    inboxIndex: 0,

    init() {
        this.fillDateFilters();
        this.bindEvents();
        this.fetchFacturas();
        this.fetchInbox();
    },

    fillDateFilters() {
        const anioSelect = document.getElementById('filter-anio');
        const mesSelect = document.getElementById('filter-mes');
        if (anioSelect) anioSelect.value = this.currentAnio;
        if (mesSelect) mesSelect.value = this.currentMes;
    },

    async fetchInbox(resetIndex = true) {
        try {
            const res = await fetch('/api/compras/inbox/list');
            const data = await res.json();
            this.inboxFiles = data.files || [];
            if (resetIndex) this.inboxIndex = 0;
            else if (this.inboxIndex >= this.inboxFiles.length) this.inboxIndex = Math.max(0, this.inboxFiles.length - 1);
            
            this.renderInboxController();
            if (this.inboxFiles.length > 0) {
                this.loadInboxFile();
            } else {
                document.getElementById('sidebar-preview').innerHTML = '<p class="preview-placeholder">📁 Buzón vacío. Arrastre aquí.</p>';
            }
        } catch (e) { console.error("Error cargando inbox", e); }
    },

    renderInboxController() {
        const ctrl = document.getElementById('inbox-controller');
        if (!ctrl) return;
        if (this.inboxFiles.length === 0) {
            ctrl.classList.add('hidden');
        } else {
            ctrl.classList.remove('hidden');
            document.getElementById('inbox-status').textContent = `Buzón: ${this.inboxIndex + 1} de ${this.inboxFiles.length}`;
        }
    },

    prevInbox() {
        if (this.inboxIndex > 0) {
            this.inboxIndex--;
            this.loadInboxFile();
            this.renderInboxController();
        }
    },

    nextInbox() {
        if (this.inboxIndex < this.inboxFiles.length - 1) {
            this.inboxIndex++;
            this.loadInboxFile();
            this.renderInboxController();
        }
    },

    loadInboxFile() {
        if (this.inboxFiles.length === 0) return;
        const filename = this.inboxFiles[this.inboxIndex];
        const url = `/inbox/${filename}`;
        
        this.sidebarFile = null; // Anulamos bypass manual
        
        // Limpiar el form
        const numInput = document.getElementById('edit-full-number');
        if (numInput) numInput.value = '';
        this.clearMatch();
        
        this.renderVisual(url, filename);
        document.getElementById('sidebar-status').textContent = `📄 Inbox: ${filename}`;
    },
    
    renderVisual(url, filename) {
        const dropZone = document.getElementById('drop-zone');
        const previewContainer = document.getElementById('sidebar-preview');
        previewContainer.innerHTML = ''; 
        
        const ext = filename.toLowerCase().split('.').pop();
        
        if (ext === 'pdf') {
            const embed = document.createElement('embed');
            embed.src = `${url}#toolbar=0&navpanes=0&scrollbar=0`;
            embed.type = 'application/pdf';
            embed.style.width = '100%';
            embed.style.height = '100%';
            previewContainer.appendChild(embed);
        } else if (['png', 'jpg', 'jpeg'].includes(ext)) {
            const img = document.createElement('img');
            img.src = url;
            img.id = 'zoomable-img';
            img.style.maxWidth = '100%';
            img.style.maxHeight = '100%';
            img.style.objectFit = 'contain';
            img.draggable = false;
            
            img.style.transformOrigin = 'center center';
            img.style.transition = 'transform 0.1s ease-out';
            
            previewContainer.appendChild(img);
            
            let scale = 1;
            let translateX = 0;
            let translateY = 0;
            
            dropZone.onwheel = (e) => {
                e.preventDefault();
                if (e.deltaY < 0) scale += 0.2;
                else scale -= 0.2;
                
                scale = Math.max(0.2, Math.min(scale, 10)); // Hasta 10x zoom
                img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
            };
            
            let isDown = false;
            let startX, startY;
            let initialTx = 0, initialTy = 0;
            
            dropZone.onmousedown = (e) => {
                isDown = true;
                dropZone.classList.add('active-pan');
                startX = e.pageX;
                startY = e.pageY;
                initialTx = translateX;
                initialTy = translateY;
                img.style.transition = 'none'; // Movimiento fluido
            };
            const deactivateDrag = () => { 
                isDown = false; 
                dropZone.classList.remove('active-pan'); 
                img.style.transition = 'transform 0.1s ease-out';
            };
            
            dropZone.onmouseleave = deactivateDrag;
            dropZone.onmouseup = deactivateDrag;
            
            dropZone.onmousemove = (e) => {
                if (!isDown) return;
                e.preventDefault();
                const x = e.pageX;
                const y = e.pageY;
                translateX = initialTx + (x - startX);
                translateY = initialTy + (y - startY);
                img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
            };
        }
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
        const calimCard = document.getElementById('calim-card');
        
        card.classList.remove('hidden');
        calimCard.classList.add('hidden'); // Ocultar válvula CALIM si hay match
        
        badge.textContent = f.origen.toUpperCase();
        badge.className = `badge ${f.origen.toLowerCase() === 'calim' ? 'calim' : ''}`;
        fecha.textContent = f.fecha;
        details.innerHTML = `<strong>${f.proveedor}</strong> - $${Number(f.total).toLocaleString()}<br>Monto Total A Conciliar.`;
    },

    clearMatch() {
        this.selectedFactura = null;
        document.getElementById('match-card').classList.add('hidden');
        
        // Válvula CALIM: Mostrar si no hay match pero y hay un número
        const numInput = document.getElementById('edit-full-number');
        if (numInput && numInput.value.trim().length >= 3) {
            document.getElementById('calim-card').classList.remove('hidden');
        } else {
            document.getElementById('calim-card').classList.add('hidden');
        }
    },

    async confirmarVinculacion() {
        if (!this.selectedFactura) {
            alert("Sube la foto primero y asegúrate de que el sistema encuentre el número de factura.");
            return;
        }
        
        const isInboxMode = (this.inboxFiles.length > 0 && !this.sidebarFile);
        if (!isInboxMode && !this.sidebarFile) {
            alert("No hay ningún comprobante para vincular.");
            return;
        }

        const statusLabel = document.getElementById('sidebar-status');
        statusLabel.style.color = 'var(--accent-color)';
        statusLabel.textContent = '💾 Archivado nominal y limpieza de origen...';
        
        const formData = new FormData();
        if (this.sidebarFile) formData.append('file', this.sidebarFile);
        else formData.append('inbox_filename', this.inboxFiles[this.inboxIndex]);
        
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
                this.clearMatch();
                this.fetchFacturas(); // Refrescar lista principal
                
                if (isInboxMode) {
                    this.fetchInbox(false); // Refresca mantenido el index para cargar la siguiente
                } else {
                    document.getElementById('sidebar-preview').innerHTML = '<p class="preview-placeholder">📁 Arrastrar PDF o Foto aquí</p>';
                }
            } else {
                statusLabel.style.color = 'var(--danger)';
                statusLabel.textContent = '❌ Error: ' + result.message;
            }
        } catch (e) {
            statusLabel.textContent = '❌ Error de conexión';
        }
    },

    async archivarPendiente() {
        const proveedor = document.getElementById('pending-proveedor').value.trim();
        const num = document.getElementById('edit-full-number').value.trim();
        const isInboxMode = (this.inboxFiles.length > 0 && !this.sidebarFile);
        
        if (!isInboxMode && !this.sidebarFile) { alert("Carga un archivo primero."); return; }
        if (!proveedor || !num) { alert("Completa el Nombre del Proveedor y el Número."); return; }
        
        const statusLabel = document.getElementById('sidebar-status');
        statusLabel.style.color = 'var(--warning)';
        statusLabel.textContent = '⏳ Pasando a Sala de Espera CALIM...';
        
        const formData = new FormData();
        if (this.sidebarFile) formData.append('file', this.sidebarFile);
        else formData.append('inbox_filename', this.inboxFiles[this.inboxIndex]);
        
        formData.append('is_pending_calim', 'true');
        formData.append('proveedor_nombre', proveedor);
        formData.append('numero_factura', num);
        
        try {
            const res = await fetch(`/api/compras/vincular`, { method: 'POST', body: formData });
            const result = await res.json();
            if (result.status === 'success') {
                statusLabel.style.color = 'var(--success)';
                statusLabel.textContent = '✅ Archivado como pendiente.';
                
                this.sidebarFile = null;
                document.getElementById('edit-full-number').value = '';
                document.getElementById('pending-proveedor').value = '';
                this.clearMatch();
                
                if (isInboxMode) this.fetchInbox(false);
                else document.getElementById('sidebar-preview').innerHTML = '<p class="preview-placeholder">📁 Arrastrar PDF o Foto aquí</p>';
            } else {
                statusLabel.textContent = '❌ Error: ' + result.message;
            }
        } catch(e) { statusLabel.textContent = '❌ Error'; }
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
        this.sidebarFile = file; // Anula el flujo de Inbox y activa el modo Bypass (Manual)
        const fileUrl = URL.createObjectURL(file);
        this.renderVisual(fileUrl, file.name);
        document.getElementById('sidebar-status').textContent = `📄 Manual: ${file.name}`;
        
        // Limpiamos match para que obligue a buscar o mandar a espera
        const numInput = document.getElementById('edit-full-number');
        if (numInput) numInput.value = '';
        this.clearMatch();
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
