document.addEventListener('DOMContentLoaded', () => {
    const dropzones = document.querySelectorAll('.dropzone-card');
    const processBtn = document.getElementById('btn-process');
    const statusMsg = document.getElementById('status-message');

    let isProcessing = false;

    dropzones.forEach(card => {
        const dropArea = card.querySelector('.drop-area');
        const modulo = card.getAttribute('data-modulo');
        const counterEl = dropArea.querySelector('.file-counter');
        
        let pendingCount = 0;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => dropArea.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, () => dropArea.classList.remove('dragover'), false);
        });

        dropArea.addEventListener('drop', handleDrop, false);

        async function handleDrop(e) {
            if(isProcessing) return;
            const dt = e.dataTransfer;
            const files = [...dt.files];

            if(files.length === 0) return;

            // Update UI optimistically
            pendingCount += files.length;
            updateCounter();

            for (const file of files) {
                await uploadFile(file, modulo);
            }
        }

        function updateCounter() {
            if (pendingCount > 0) {
                counterEl.textContent = `${pendingCount} listos`;
                counterEl.classList.add('has-files');
            } else {
                counterEl.textContent = `0 pendientes`;
                counterEl.classList.remove('has-files');
            }
        }

        async function uploadFile(file, modulo) {
            statusMsg.style.color = 'var(--text-muted)';
            statusMsg.textContent = `[Upload] Despachando ${file.name}...`;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch(`/api/upload/${modulo}`, {
                    method: 'POST',
                    body: formData
                });
                const res = await response.json();
                
                if(res.status === 'success') {
                    statusMsg.textContent = `¡${file.name} soltado en bandeja de ${modulo}!`;
                } else {
                    statusMsg.style.color = 'red';
                    statusMsg.textContent = `Error: ${res.message}`;
                    pendingCount--; 
                    updateCounter();
                }
            } catch (error) {
                pendingCount--;
                updateCounter();
                statusMsg.style.color = 'red';
                statusMsg.textContent = `Error red: ${error}`;
            }
        }
        
        card.addEventListener('resetCounter', () => {
            pendingCount = 0;
            updateCounter();
        });
    });

    processBtn.addEventListener('click', async () => {
        if(isProcessing) return;
        
        isProcessing = true;
        processBtn.classList.add('loading');
        processBtn.textContent = '⚡ Procesando Inboxes... ⚡';
        statusMsg.style.color = 'var(--text-main)';
        statusMsg.textContent = 'Analizando, extrayendo y archivando legalmente...';

        try {
            const response = await fetch('/api/process', { method: 'POST' });
            const result = await response.json();

            if (result.status === 'success') {
                statusMsg.style.color = 'var(--success)';
                statusMsg.textContent = '¡Ecosistema Sincronizado Exitosamente!';
                
                // Limpiar la UI
                dropzones.forEach(card => card.dispatchEvent(new Event('resetCounter')));
            } else {
                statusMsg.style.color = 'red';
                statusMsg.textContent = `Error del Orquestador: ${result.message}`;
            }
        } catch (error) {
            statusMsg.style.color = 'red';
            statusMsg.textContent = `Error de conexión: ${error}`;
        } finally {
            isProcessing = false;
            processBtn.classList.remove('loading');
            processBtn.textContent = '⚡ Sincronizar Ecosistema ⚡';
            
            // Limpiar mensaje
            setTimeout(() => { if(statusMsg.style.color === 'var(--success)') statusMsg.textContent = ''; }, 5000);
        }
    });

    // SPOTLIGHT SEARCH (FTS5)
    const searchInput = document.getElementById('spotlight-search');
    const searchResults = document.getElementById('search-results');
    let searchTimeout;

    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        
        if (query.length < 3) {
            searchResults.classList.add('hidden');
            searchResults.innerHTML = '';
            return;
        }

        searchTimeout = setTimeout(async () => {
            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                
                if (data.results && data.results.length > 0) {
                    searchResults.innerHTML = data.results.map(r => `
                        <div class="search-result-item">
                            <div class="meta">${r.source} | ID: ${r.record_id} <span class="amount">$ ${Number(r.monto).toLocaleString()}</span></div>
                            <div class="title">${r.nombre} (Fecha: ${r.fecha})</div>
                        </div>
                    `).join('');
                    searchResults.classList.remove('hidden');
                } else {
                    searchResults.innerHTML = '<div class="search-result-item"><div class="title">Ninguna entidad o comprobante encontrado.</div></div>';
                    searchResults.classList.remove('hidden');
                }
            } catch (err) {
                console.error("Fallo de red en Search 360", err);
            }
        }, 300); // 300ms preventivos
    });
    
    // Hide panel
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.add('hidden');
        }
    });
});
