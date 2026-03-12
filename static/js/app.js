/**
 * ERP Nicoletti - Lógica de Negocio y Persistencia
 * Archivo adaptado para FLASK (Backend en Python)
 */

// Ya no usamos ipcRenderer ni XLSX (ahora todo va al backend Python)
// Las dependencias de NodeJS se corren en backend ahora (o se manejan por HTML)

// --- ESTADO GLOBAL Y PERSISTENCIA ---
let transactions = [];

const CUENTAS_LIQUIDEZ = [
    'Banco Galicia', 'Banco Hipotecario', 'Efectivo / Caja',
    'Caja de Ahorro Galicia', 'Cuenta Corriente Galicia',
    'Caja de Ahorro Chubut', 'Cuenta Corriente Chubut', 'MercadoPago'
];
const CUENTAS_DEUDA = ['VISA Galicia', 'MASTER Galicia', 'Patagonia 365', 'Tarjeta Naranja', 'VISA Hipotecario', 'Préstamo Chubut', 'Préstamo Hipotecario', 'Cheques Emitidos'];

/**
 * Carga las transacciones desde Flask (API Rest)
 */
async function loadTransactions() {
    try {
        const response = await fetch('/api/transactions');
        return await response.json();
    } catch (err) {
        console.error('Error loading transactions', err);
        return [];
    }
}

// --- UTILIDADES ---
const formatMoney = (val) => new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
}).format(val);

/**
 * Parsea un valor a número de forma inteligente, 
 * detectando si el punto es decimal o separador de miles.
 */
function parseSmartNumber(val) {
    if (typeof val === 'number') return val;
    let str = String(val || '0').trim().replace('$', '').replace('ARS', '');
    if (!str) return 0;

    // Si tiene coma, es formato regional (ej: 1.234,56 o 1234,56)
    if (str.includes(',')) {
        // Quitamos los puntos de miles y cambiamos la coma por punto decimal
        return parseFloat(str.replace(/\./g, '').replace(',', '.'));
    }
    
    // Si no tiene coma, asumimos que el punto (si existe) ya es decimal (formato JS/estándar)
    return parseFloat(str);
}

function showLoader() {
    const loader = document.getElementById('loader-overlay');
    if (loader) {
        loader.style.display = 'flex';
        gsap.to(loader, { opacity: 1, duration: 0.3 });
    }
}

function hideLoader() {
    const loader = document.getElementById('loader-overlay');
    if (loader) {
        gsap.to(loader, {
            opacity: 0, duration: 0.3, onComplete: () => {
                loader.style.display = 'none';
            }
        });
    }
}

/**
 * Inicialización de la App
 */
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Cargar datos persistidos desde DB
    transactions = await loadTransactions();

    // 2. Inicializar componentes visuales
    initChart();
    renderTransactions();
    calculateBalances();
    renderSemaforo();
    setupModals();
    setupNavigation();
    renderAccounting();
    renderPayments();

    // GSAP Initial Stagger Animation
    gsap.from(".stat-card", {
        y: 40,
        opacity: 0,
        duration: 0.8,
        stagger: 0.15,
        ease: "back.out(1.7)"
    });

    gsap.from(".content-grid > div", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.4,
        stagger: 0.2,
        ease: "power3.out"
    });

    const dolarBlueInput = document.getElementById('dolar-blue');
    if (dolarBlueInput) {
        dolarBlueInput.addEventListener('input', () => {
            calculateBalances();
        });
    }

    const btnImport = document.getElementById('btn-import-csv');
    const csvUpload = document.getElementById('csv-upload');
    if (btnImport && csvUpload) {
        btnImport.addEventListener('click', () => csvUpload.click());
        csvUpload.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                parseCSV(e.target.files[0]);
                e.target.value = ''; // Reset to allow re-upload
            }
        });
    }

    // Initialize with today's date if possible
    const tDateInput = document.getElementById('t-date');
    if (tDateInput) tDateInput.value = new Date().toISOString().split('T')[0];
});

// --- LÓGICA DE NEGOCIO (FRONTERAS DE PATRIMONIO) ---

/**
 * Animar números con GSAP
 */
function animateValue(id, start, end) {
    const el = document.getElementById(id);
    if (!el) return;
    const obj = { val: start };
    gsap.to(obj, {
        val: end,
        duration: 1.5,
        ease: "power2.out",
        onUpdate: function () {
            // Se quita el Math.floor para que conserve y anime los centavos
            el.textContent = formatMoney(obj.val);
        }
    });
}

/**
 * Calcula y actualiza los saldos en las tarjetas de estadísticas
 * Aplica lógica de ingresos (+) y egresos (-) por entidad.
 */
function calculateBalances() {
    let liquidezTotal = 0;
    let deudaTotal = 0;
    let breakdownLiquidez = {};
    let breakdownDeuda = {};

    // Inicializar todas a 0 para que siempre figuren en cartelera, aunque no tengan movimientos aún
    CUENTAS_LIQUIDEZ.forEach(acc => breakdownLiquidez[acc] = 0);
    CUENTAS_DEUDA.forEach(acc => breakdownDeuda[acc] = 0);

    const dolarBlueInput = document.getElementById('dolar-blue');
    const dolarRate = dolarBlueInput ? parseFloat(dolarBlueInput.value) || 1200 : 1200;

    transactions.forEach(t => {
        let value = t.amount;
        if (t.currency === 'USD') value *= dolarRate;

        let accountStr = t.account || '';

        if (CUENTAS_LIQUIDEZ.some(c => accountStr.includes(c))) {
            liquidezTotal += value;
            const key = CUENTAS_LIQUIDEZ.find(c => accountStr.includes(c));
            breakdownLiquidez[key] = (breakdownLiquidez[key] || 0) + value;
        } else if (CUENTAS_DEUDA.some(c => accountStr.includes(c))) {
            deudaTotal += value;
            const key = CUENTAS_DEUDA.find(c => accountStr.includes(c));
            breakdownDeuda[key] = (breakdownDeuda[key] || 0) + value;
        }
    });

    const saldoNeto = liquidezTotal + deudaTotal;

    animateValue('macro-liquidez', 0, liquidezTotal);
    animateValue('macro-deuda', 0, deudaTotal);
    animateValue('macro-neto', 0, saldoNeto);

    // Update breakdowns
    const liqBreak = document.getElementById('liquidez-breakdown');
    if (liqBreak) {
        liqBreak.innerHTML = Object.entries(breakdownLiquidez)
            .map(([k, v]) => `<div class="account-line" onclick="openLedger('${k}')"><span>${k}</span><span style="font-weight:600;">${formatMoney(v)}</span></div>`).join('');
    }

    const deuBreak = document.getElementById('deuda-breakdown');
    if (deuBreak) {
        deuBreak.innerHTML = Object.entries(breakdownDeuda)
            .map(([k, v]) => `<div class="account-line" onclick="openLedger('${k}')"><span>${k}</span><span style="font-weight:600; color:var(--color-danger);">${formatMoney(v)}</span></div>`).join('');
    }
}

// --- COMPONENTES DE UI ---

function setupModals() {
    const btnNew = document.getElementById('btn-new-transaction');
    const modalOverlay = document.getElementById('transactionModal');
    const btnClose = document.getElementById('closeModal');
    const form = document.getElementById('transactionForm');
    const entitySelect = document.getElementById('t-entity');
    const accountSelect = document.getElementById('t-account');
    const typeSelect = document.getElementById('t-type');
    const categorySelect = document.getElementById('t-category');

    window.accountsData = {
        joaquin: ['Banco Hipotecario', 'VISA Hipotecario', 'Préstamo Hipotecario'],
        jorgelina: ['Banco Galicia', 'VISA Galicia', 'MASTER Galicia', 'Patagonia 365', 'Tarjeta Naranja'],
        'Lo de Karlota': [
            'Caja de Ahorro Galicia', 'Cuenta Corriente Galicia', 
            'Caja de Ahorro Chubut', 'Cuenta Corriente Chubut', 
            'MercadoPago', 'Efectivo / Caja', 'Préstamo Chubut', 'Cheques Emitidos'
        ]
    };

    const incomeCategories = {
        joaquin: ['Sueldo (💼)', 'Comisión (💰)', 'Alquiler (🏠)', 'Inversiones (📈)', 'Regalos (🎁)', 'Otros Ingresos'],
        jorgelina: ['Sueldo (💼)', 'Inversiones (📈)', 'Regalos (🎁)', 'Otros Ingresos'],
        'Lo de Karlota': ['Ventas (🧾)', 'Transferencia recibida (💸)', 'Intereses (🏦)', 'Reembolsos (📦)', 'Aporte Extraordinario', 'Otros Ingresos']
    };

    const expenseCategories = {
        joaquin: ['Comida (🍔)', 'Transporte (🚗)', 'Vivienda (🏠)', 'Servicios (💡)', 'Impuestos (🧾)', 'Salud (🏥)', 'Educación (🎓)', 'Ocio (🎮)', 'Compras (🛒)', 'Ropa (👕)', 'Tecnología (💻)', 'Deportes (🏋️)', 'Estética (💅)', 'Mascotas (🐶)', 'Pago Tarjeta (💳)', 'Otros (📦)'],
        jorgelina: ['Comida (🍔)', 'Transporte (🚗)', 'Vivienda (🏠)', 'Servicios (💡)', 'Impuestos (🧾)', 'Salud (🏥)', 'Educación (🎓)', 'Ocio (🎮)', 'Compras (🛒)', 'Ropa (👕)', 'Tecnología (💻)', 'Deportes (🏋️)', 'Estética (💅)', 'Mascotas (🐶)', 'Pago Tarjeta (💳)', 'Otros (📦)'],
        'Lo de Karlota': ['Proveedores Insumos', 'Mercadería Local', 'Alquiler Local (🏠)', 'Sueldos (💸)', 'Impuestos (🧾)', 'Servicios (💡)', 'Mantenimiento (📦)', 'Sindicato - Comercio', 'Sindicato - Otros', 'Otros Egresos']
    };

    function updateAccounts() {
        const entity = entitySelect.value;
        const type = typeSelect.value;
        let accounts = window.accountsData[entity] || [];

        // Filtramos cuentas de deuda (Tarjetas, Préstamos, Cheques) si la operación es un INGRESO
        if (type === 'ingreso') {
            const debtKeywords = ['VISA', 'MASTER', 'Patagonia 365', 'Tarjeta Naranja', 'Préstamo', 'Cheques'];
            accounts = accounts.filter(acc => !debtKeywords.some(kw => acc.includes(kw)));
        }

        accountSelect.innerHTML = '<option value="" disabled selected>Selecciona una cuenta</option>';
        accounts.forEach(acc => {
            const opt = document.createElement('option');
            opt.value = acc.toLowerCase().replace(/\s+/g, '-');
            opt.textContent = acc;
            accountSelect.appendChild(opt);
        });
    }

    function updateCategories() {
        const entity = entitySelect.value;
        const type = typeSelect.value;
        let categories = [];
        if (type === 'ingreso') categories = incomeCategories[entity] || ['Otros Ingresos'];
        else if (type === 'egreso') categories = expenseCategories[entity] || ['Otros Egresos'];
        else categories = ['Retiro de Socio', 'Aporte de Socio'];

        categorySelect.innerHTML = '<option value="" disabled selected>Selecciona una categoría</option>';
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.toLowerCase().replace(/\s+/g, '-');
            opt.textContent = cat;
            categorySelect.appendChild(opt);
        });
    }

    entitySelect.addEventListener('change', () => { updateAccounts(); updateCategories(); });
    typeSelect.addEventListener('change', () => {
        updateAccounts();
        updateCategories();
        document.getElementById('group-destino').style.display = typeSelect.value === 'transferencia' ? 'block' : 'none';
    });

    btnNew.addEventListener('click', () => {
        updateAccounts();
        updateCategories();
        modalOverlay.style.display = 'flex';
        gsap.to(modalOverlay, { opacity: 1, duration: 0.3, ease: "power2.out" });
        gsap.fromTo(".modal",
            { scale: 0.7, opacity: 0, y: 30 },
            { scale: 1, opacity: 1, y: 0, duration: 0.5, ease: "back.out(1.5)" }
        );
    });

    btnClose.addEventListener('click', closeAndClear);
    // Prevents accidental closing when clicking outside or dragging the mouse out of the modal
    // modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) closeAndClear(); });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const entity = entitySelect.value;
        const type = typeSelect.value;
        const amountValue = parseFloat(document.getElementById('t-amount').value);
        let desc = document.getElementById('t-desc').value.trim();
        const account = accountSelect.options[accountSelect.selectedIndex]?.text || '';
        const category = categorySelect.options[categorySelect.selectedIndex]?.text || '';
        const currency = document.getElementById('t-currency').value || 'ARS';
        let dateStr = document.getElementById('t-date').value;

        if (!dateStr) dateStr = new Date().toISOString().split('T')[0];
        if (!desc) desc = category;

        const entityDestino = document.getElementById('t-entity-destino').value;

        if (type === 'transferencia' && entity === entityDestino) {
            alert('La entidad destino no puede ser igual a la de origen.');
            return;
        }

        if (type === 'transferencia') {
            const transferId = Date.now();
            await fetch('/api/transactions', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: transferId, groupId: transferId,
                    entity, account, category, type: 'egreso', amount: -amountValue,
                    desc: `Transferencia a ${document.getElementById('t-entity-destino').options[document.getElementById('t-entity-destino').selectedIndex].text} - ${desc}`,
                    date: dateStr, currency
                })
            });

            await fetch('/api/transactions', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: transferId + 1, groupId: transferId,
                    entity: entityDestino, account: '', category: 'Transferencia recibida', type: 'ingreso', amount: amountValue,
                    desc: `Transferencia de ${entitySelect.options[entitySelect.selectedIndex].text} - ${desc}`,
                    date: dateStr, currency
                })
            });

        } else {
            const amount = type === 'egreso' ? -amountValue : amountValue;
            await fetch('/api/transactions', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: Date.now(), entity, account, category, type, amount, desc, date: dateStr, currency
                })
            });
        }

        transactions = await loadTransactions();
        renderTransactions();
        calculateBalances();
        updateChart(transactions);
        renderSemaforo();
        renderAccounting();
        renderPayments();
        closeAndClear();
    });

    function closeAndClear() {
        gsap.to(modalOverlay, {
            opacity: 0, duration: 0.3, ease: "power2.inOut", onComplete: () => {
                modalOverlay.style.display = 'none';
                form.reset();
            }
        });
    }

    window.openTransactionPreFilled = function (accountName, type) {
        // Encontramos que entidad es dueña de esta cuenta buscandola
        let entityOwner = 'Lo de Karlota';
        for (const [ent, accs] of Object.entries(window.accountsData)) {
            if (accs.includes(accountName)) {
                entityOwner = ent;
                break;
            }
        }

        // Simula click para abrir el modal nativamente
        btnNew.click();

        setTimeout(() => {
            entitySelect.value = entityOwner;
            entitySelect.dispatchEvent(new Event('change'));

            setTimeout(() => {
                typeSelect.value = type;
                typeSelect.dispatchEvent(new Event('change'));

                const targetVal = accountName.toLowerCase().replace(/\s+/g, '-');
                accountSelect.value = targetVal;
            }, 50);
        }, 50);
    };
}

window.deleteTransaction = async function (id) {
    if (confirm('¿Estás seguro de eliminar este movimiento?')) {
        const tx = transactions.find(t => t.id === id);
        if (!tx) return;

        const url = `/api/transactions/${id}${tx.groupId ? '?groupId=' + tx.groupId : ''}`;
        await fetch(url, { method: 'DELETE' });

        transactions = await loadTransactions();
        renderTransactions();
        calculateBalances();
        updateChart(transactions);
        renderSemaforo();
        renderAccounting();
        renderPayments();
    }
};

function renderTransactions() {
    const list = document.getElementById('transactionList');
    list.innerHTML = '';

    if (transactions.length === 0) {
        list.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--text-muted);">No hay movimientos registrados</div>';
        return;
    }

    transactions.forEach(t => {
        let entityColor, entityIcon, entityName;
        if (t.entity === 'Lo de Karlota' || t.entity === 'karlota') { entityColor = 'var(--color-karlota)'; entityIcon = 'fa-shop'; entityName = 'Lo de Karlota'; }
        else if (t.entity === 'joaquin') { entityColor = 'var(--color-joaquin)'; entityIcon = 'fa-user'; entityName = 'Joaquín'; }
        else { entityColor = 'var(--color-jorgelina)'; entityIcon = 'fa-user'; entityName = 'Jorgelina'; }

        const isPositive = t.amount > 0;
        const amountClass = isPositive ? 'text-positive' : 'text-negative';

        const item = document.createElement('div');
        item.className = 'transaction-item';
        item.innerHTML = `
            <div class="t-icon" style="background-color: ${entityColor}; opacity: 0.9; color: white;">
                <i class="fa-solid ${entityIcon}"></i>
            </div>
            <div class="t-details">
                <div class="t-title">${t.desc}</div>
                <div class="t-subtitle">
                    ${entityName} 
                    ${t.account ? '&bull; ' + t.account : ''} 
                    ${t.category ? '&bull; <span style="color: var(--color-joaquin)">' + t.category + '</span>' : ''}
                    &bull; ${t.date}
                </div>
            </div>
            <div class="t-amount ${amountClass}">${isPositive ? '+' : ''}${formatMoney(t.amount)}</div>
            <div onclick="deleteTransaction(${t.id})" style="cursor: pointer; color: var(--text-muted); transition: color 0.2s; margin-left: 16px;" onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='var(--text-muted)'">
                <i class="fa-solid fa-trash"></i>
            </div>
        `;
        list.appendChild(item);
    });
}

let mainChartInstance = null;

function initChart() {
    const canvas = document.getElementById('mainChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const gradientInc = ctx.createLinearGradient(0, 0, 0, 350);
    gradientInc.addColorStop(0, 'rgba(16, 185, 129, 0.4)');
    gradientInc.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    const gradientExp = ctx.createLinearGradient(0, 0, 0, 350);
    gradientExp.addColorStop(0, 'rgba(239, 68, 68, 0.4)');
    gradientExp.addColorStop(1, 'rgba(239, 68, 68, 0.0)');

    mainChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [], datasets: [
                { label: 'Ingresos Totales', data: [], borderColor: '#10b981', backgroundColor: gradientInc, borderWidth: 3, tension: 0.4, fill: true, pointBackgroundColor: '#10b981', pointBorderColor: '#fff', pointRadius: 4 },
                { label: 'Egresos Totales', data: [], borderColor: '#ef4444', backgroundColor: gradientExp, borderWidth: 3, tension: 0.4, fill: true, pointBackgroundColor: '#ef4444', pointBorderColor: '#fff', pointRadius: 4 },
                { label: 'Proyección de Caja', data: [], borderColor: '#f59e0b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], tension: 0.4, pointRadius: 0 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, grid: { color: 'rgba(0, 0, 0, 0.04)' }, ticks: { color: '#94a3b8' } }, x: { grid: { display: false }, ticks: { color: '#94a3b8' } } }
        }
    });
    updateChart(transactions);
}

function updateChart(txs) {
    if (!mainChartInstance) return;

    // Last 7 days + Next 14 days (21 days total)
    const daysArr = Array.from({ length: 21 }, (_, i) => {
        const d = new Date(); d.setDate(d.getDate() - 7 + i);
        return {
            dateStr: d.toISOString().split('T')[0],
            label: d.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' }),
            isFuture: i > 7
        };
    });

    const labels = daysArr.map(d => d.label);
    const dataInc = new Array(21).fill(0);
    const dataExp = new Array(21).fill(0);
    const dataProj = new Array(21).fill(null);

    const dolarBlueInput = document.getElementById('dolar-blue');
    const dolarRate = dolarBlueInput ? parseFloat(dolarBlueInput.value) || 1200 : 1200;

    txs.forEach(t => {
        if (t.entity !== 'Lo de Karlota' && t.entity !== 'karlota') return;

        let txDateIso = t.date;
        let dayIndex = -1;

        // Soporte retroactivo a formatos viejos
        if (txDateIso.includes(',')) {
            const txDate = t.date.split(',')[0];
            dayIndex = daysArr.findIndex(d => d.label.startsWith(txDate));
        } else {
            dayIndex = daysArr.findIndex(d => d.dateStr === txDateIso);
        }

        if (dayIndex !== -1) {
            let value = Math.abs(t.amount);
            if (t.currency === 'USD') value *= dolarRate;

            if (t.type === 'ingreso') dataInc[dayIndex] += value;
            else if (t.type === 'egreso') dataExp[dayIndex] += value;
        }
    });

    // Proyección de liquidez
    let currBalance = 0;
    txs.forEach(t => {
        if (t.entity === 'karlota' && t.date <= new Date().toISOString().split('T')[0]) {
            let val = t.amount;
            if (t.currency === 'USD') val *= dolarRate;
            currBalance += val;
        }
    });

    // Hoy = index 7
    dataProj[7] = currBalance;
    for (let i = 8; i < 21; i++) {
        const netChange = dataInc[i] - dataExp[i];
        dataProj[i] = dataProj[i - 1] + netChange;
    }

    mainChartInstance.data.labels = labels;
    mainChartInstance.data.datasets[0].data = dataInc;
    mainChartInstance.data.datasets[1].data = dataExp;
    mainChartInstance.data.datasets[2].data = dataProj;
    mainChartInstance.update();
}

function renderSemaforo() {
    const list = document.getElementById('semaforoList');
    if (!list) return;
    list.innerHTML = '';

    const today = new Date().toISOString().split('T')[0];
    const dolarBlueInput = document.getElementById('dolar-blue');
    const dolarRate = dolarBlueInput ? parseFloat(dolarBlueInput.value) || 1200 : 1200;

    const futurePayables = transactions.filter(t => t.type === 'egreso' && t.date > today);

    futurePayables.sort((a, b) => a.date.localeCompare(b.date)).forEach(t => {
        const diffTime = new Date(t.date).setHours(0, 0, 0, 0) - new Date(today).setHours(0, 0, 0, 0);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        let colorClass = 'var(--color-success)';
        let borderLeft = '4px solid var(--color-success)';

        if (diffDays <= 7) {
            colorClass = 'var(--color-danger)';
            borderLeft = '4px solid var(--color-danger)';
        } else if (diffDays <= 15) {
            colorClass = '#f59e0b';
            borderLeft = '4px solid #f59e0b';
        }

        let displayAmount = Math.abs(t.amount);
        if (t.currency === 'USD') displayAmount *= dolarRate;

        list.innerHTML += `
            <tr style="border-bottom: 1px solid var(--border-color);">
                <td style="padding: 12px 10px; font-weight: 600; color: ${colorClass}; border-left: ${borderLeft};">${new Date(t.date).toLocaleDateString('es-AR')}</td>
                <td>${t.desc}</td>
                <td><span class="stat-badge" style="background: rgba(0,0,0,0.05); color: var(--text-main);">${t.entity}</span></td>
                <td style="text-align: right; font-weight: 600;">$${formatMoney(displayAmount)}</td>
            </tr>
        `;
    });

    if (futurePayables.length === 0) {
        list.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px; color: var(--text-muted);">No hay vencimientos próximos</td></tr>';
    }
}

async function parseCSV(file, accountName = 'Banco Galicia') {
    const reader = new FileReader();
    reader.onload = async (e) => {
        const data = e.target.result;

        try {
            showLoader();
            const workbook = XLSX.read(data, { type: 'array' });
            const firstSheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[firstSheetName];
            const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

            let parserType = 'galicia';
            if (accountName.toLowerCase().includes('chubut')) parserType = 'chubut';
            if (accountName.toLowerCase().includes('mercado')) parserType = 'mercadopago';

            // SAFETY CHECK (Silent/Automatic)
            try {
                checkFileIntegrity(rows, parserType, accountName);
            } catch (err) {
                hideLoader();
                alert(`⚠️ ERROR DE SEGURIDAD: ${err.message}\nLa importación fue cancelada para proteger tus datos.`);
                return;
            }

            const parsedData = BankParsers[parserType](rows);
            let importedCount = 0;
            let skippedCount = 0;

            for (let i = 0; i < parsedData.length; i++) {
                const item = parsedData[i];

                // ANTI-DUPLICATE SHIELD (Escudo de Duplicados)
                const isDuplicate = transactions.some(t => 
                    (t.account || '').toLowerCase() === accountName.toLowerCase() &&
                    t.date === item.date &&
                    Math.abs(t.amount - item.amount) < 0.01 && 
                    (t.desc || '').substring(0, 50).toLowerCase() === (item.desc || '').substring(0, 50).toLowerCase()
                );

                if (isDuplicate) {
                    skippedCount++;
                    continue;
                }

                await fetch('/api/transactions', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: Date.now() + i,
                        entity: 'Lo de Karlota',
                        account: accountName,
                        category: 'Importación Automática',
                        type: item.type,
                        amount: item.amount,
                        desc: item.desc,
                        date: item.date,
                        currency: 'ARS'
                    })
                });
                importedCount++;
            }

            transactions = await loadTransactions();
            renderTransactions();
            calculateBalances();
            updateChart(transactions);
            renderSemaforo();
            renderAccounting();
            renderPayments();
            renderBankDetails(accountName);
            
            hideLoader();
            let resultMsg = `Procesado finalizado para ${accountName}.\n`;
            if (importedCount > 0) resultMsg += `✅ ${importedCount} movimientos nuevos cargados.\n`;
            if (skippedCount > 0) resultMsg += `🚫 ${skippedCount} movimientos omitidos por estar duplicados.`;
            alert(resultMsg);
        } catch (error) {
            hideLoader();
            console.error("Error procesando Archivo", error);
            alert("Error al parsear el archivo. Asegúrate que el formato sea compatible.");
        }
    };
    reader.readAsArrayBuffer(file);
}

// --- LOGICA DE LIBRO MAYOR (LEDGER) ---
window.openLedger = function (accountName) {
    const ledgerModal = document.getElementById('ledgerModal');
    if (!ledgerModal) return;

    document.getElementById('ledger-account-name').textContent = accountName;

    let balance = 0;
    const accountTxs = transactions.filter(t => (t.account || '').toLowerCase().includes(accountName.toLowerCase()));

    const dolarRate = parseFloat(document.getElementById('dolar-blue')?.value || 1200);

    accountTxs.forEach(t => {
        let val = t.amount;
        if (t.currency === 'USD') val *= dolarRate;
        balance += val;
    });

    const balanceEl = document.getElementById('ledger-balance');
    balanceEl.textContent = formatMoney(balance);
    balanceEl.style.color = balance < 0 ? 'var(--color-danger)' : (balance > 0 ? 'var(--color-success)' : 'inherit');

    const list = document.getElementById('ledgerTransactionList');
    list.innerHTML = '';

    if (accountTxs.length === 0) {
        list.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--text-muted);">No hay movimientos.</div>';
    } else {
        const sorted = [...accountTxs].sort((a, b) => new Date(b.date) - new Date(a.date));
        sorted.forEach(t => {
            const isPositive = t.amount > 0;
            const amountClass = isPositive ? 'text-positive' : 'text-negative';
            const item = document.createElement('div');
            item.className = 'transaction-item';
            item.innerHTML = `
                <div class="transaction-info">
                    <div class="transaction-icon" style="background:${isPositive ? 'var(--color-success)' : 'var(--color-danger)'}; color:white;">
                        <i class="fa-solid ${isPositive ? 'fa-arrow-down' : 'fa-arrow-up'}"></i>
                    </div>
                    <div>
                        <h4>${t.desc || t.category}</h4>
                        <p>${t.date.split('-').reverse().join('/')}</p>
                    </div>
                </div>
                <div class="transaction-amount">
                    <div class="${amountClass}">${isPositive ? '+' : ''}${formatMoney(t.amount)} ${t.currency}</div>
                </div>
            `;
            list.appendChild(item);
        });
    }

    document.getElementById('btn-ledger-egreso').onclick = () => {
        closeLedger();
        if (window.openTransactionPreFilled) window.openTransactionPreFilled(accountName, 'egreso');
    };

    document.getElementById('btn-ledger-ingreso').onclick = () => {
        closeLedger();
        if (window.openTransactionPreFilled) window.openTransactionPreFilled(accountName, 'ingreso');
    };

    ledgerModal.style.display = 'flex';
    gsap.to(ledgerModal, { opacity: 1, duration: 0.3 });
    gsap.fromTo(ledgerModal.querySelector('.modal'),
        { scale: 0.9, opacity: 0, y: 20 },
        { scale: 1, opacity: 1, y: 0, duration: 0.4, ease: "back.out(1.5)" }
    );
};

function closeLedger() {
    const m = document.getElementById('ledgerModal');
    if (m) {
        gsap.to(m, { opacity: 0, duration: 0.2, onComplete: () => m.style.display = 'none' });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btnCloseLedger = document.getElementById('closeLedgerModal');
    if (btnCloseLedger) btnCloseLedger.addEventListener('click', closeLedger);
});

// --- NAVEGACION Y MODULOS NUEVOS ---

function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view-container');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetView = item.getAttribute('data-view');

            if (!targetView) return;

            // Update UI Active State
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // Switch Views
            views.forEach(v => {
                v.classList.remove('active');
                
                let viewId = `view-${targetView}`;
                // Special handling for dynamic bank views
                if (targetView.startsWith('bank-')) {
                    viewId = 'view-bank-generic';
                    const accountName = item.getAttribute('data-account');
                    setupBankView(accountName);
                }

                if (v.id === viewId) {
                    v.classList.add('active');
                }
            });
        });
    });
}

function setupBankView(accountName) {
    document.getElementById('bank-view-title').textContent = accountName;
    document.getElementById('bank-view-subtitle').textContent = `Gestión de movimientos y conciliación para ${accountName}`;
    
    // Configurar botones de acción
    const btnImport = document.getElementById('btn-bank-import');
    const fileUpload = document.getElementById('bank-file-upload');
    const btnNew = document.getElementById('btn-bank-new-tx');
    const btnInitial = document.getElementById('btn-bank-initial-balance');

    btnImport.onclick = () => fileUpload.click();
    fileUpload.onchange = (e) => {
        if (e.target.files.length > 0) {
            parseCSV(e.target.files[0], accountName);
            e.target.value = ''; // Reset to allow re-upload
        }
    };
    
    btnNew.onclick = () => {
        if (window.openTransactionPreFilled) window.openTransactionPreFilled(accountName, 'egreso');
    };

    btnInitial.onclick = async () => {
        const amountStr = prompt(`Ingrese el SALDO INICIAL para ${accountName} (use '-' para rojo):`, "0");
        if (amountStr === null) return;
        
        const amount = parseFloat(amountStr.replace(',', '.'));
        if (isNaN(amount)) {
            alert("Monto inválido.");
            return;
        }

        const date = prompt("Fecha de apertura (YYYY-MM-DD):", "2026-01-01");
        if (!date) return;

        if (confirm(`¿Confirmas un saldo inicial de ${formatMoney(amount)} para ${accountName} al ${date}?`)) {
            await fetch('/api/transactions', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: Date.now(),
                    entity: 'Lo de Karlota',
                    account: accountName,
                    category: 'Saldo Inicial (Apertura)',
                    type: amount >= 0 ? 'ingreso' : 'egreso',
                    amount: amount,
                    desc: `Saldo Inicial / Apertura de Cuenta`,
                    date: date,
                    currency: 'ARS'
                })
            });
            transactions = await loadTransactions();
            renderTransactions();
            calculateBalances();
            renderBankDetails(accountName);
        }
    };

    renderBankDetails(accountName);
}

function renderBankDetails(accountName) {
    const list = document.getElementById('bank-transactions-list');
    const balanceEl = document.getElementById('bank-balance');
    const incEl = document.getElementById('bank-monthly-inc');
    const expEl = document.getElementById('bank-monthly-exp');

    const accTxs = transactions.filter(t => (t.account || '').toLowerCase() === accountName.toLowerCase());
    
    let balance = 0;
    let monthlyInc = 0;
    let monthlyExp = 0;
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    accTxs.forEach(t => {
        balance += t.amount;
        
        const tDate = new Date(t.date);
        if (tDate.getMonth() === currentMonth && tDate.getFullYear() === currentYear) {
            if (t.amount > 0) monthlyInc += t.amount;
            else monthlyExp += Math.abs(t.amount);
        }
    });

    balanceEl.textContent = formatMoney(balance);
    incEl.textContent = formatMoney(monthlyInc);
    expEl.textContent = formatMoney(monthlyExp);

    list.innerHTML = '';
    accTxs.sort((a,b) => new Date(b.date) - new Date(a.date)).forEach(t => {
        const item = document.createElement('div');
        item.className = 'transaction-item';
        const isPos = t.amount > 0;
        item.innerHTML = `
            <div class="t-icon" style="background: ${isPos ? 'var(--color-success)' : 'var(--color-danger)'}; color:white;">
                <i class="fa-solid ${isPos ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down'}"></i>
            </div>
            <div class="t-details">
                <div class="t-title">${t.desc}</div>
                <div class="t-subtitle">${new Date(t.date).toLocaleDateString()} &bull; ${t.category}</div>
            </div>
            <div class="t-amount ${isPos ? 'text-positive' : 'text-negative'}">${isPos ? '+' : ''}${formatMoney(t.amount)}</div>
        `;
        list.appendChild(item);
    });

    if (accTxs.length === 0) {
        list.innerHTML = '<p style="text-align:center; padding: 20px; color:var(--text-muted);">No hay movimientos registrados.</p>';
    }
}

const BankSchemes = {
    galicia: ['fecha', 'movimiento', 'débito', 'crédito'],
    chubut: ['fecha', 'movimientos', 'importe'],
    mercadopago: ['fecha', 'detalle', 'monto']
};

function checkFileIntegrity(rows, bankType, accountName = '') {
    const required = BankSchemes[bankType];
    if (!required) return true;

    const allCells = rows.flat().map(c => String(c || '').toLowerCase());
    const allText = allCells.join(' ');
    
    // 1. Check basic headers
    const missing = required.filter(word => !allCells.some(cell => cell.includes(word)));
    if (missing.length > 0) {
        throw new Error(`El archivo no parece ser un extracto de ${bankType.toUpperCase()}. Faltan encabezados críticos: ${missing.join(', ')}`);
    }

    // 2. STRENGTHENED: Account Type Check (Escudo de Precisión)
    const accLower = accountName.toLowerCase();
    if (bankType === 'galicia') {
        if (accLower.includes('corriente') && !allText.includes('corriente')) {
            throw new Error("⚠️ ERROR DE SEGURIDAD: Estás en el módulo de CUENTA CORRIENTE, pero el archivo parece ser una CAJA DE AHORRO u otro tipo.");
        }
        if (accLower.includes('ahorro') && !allText.includes('ahorro')) {
            throw new Error("⚠️ ERROR DE SEGURIDAD: Estás en el módulo de CAJA DE AHORRO, pero el archivo parece ser una CUENTA CORRIENTE u otro tipo.");
        }
    }

    if (bankType === 'chubut') {
        if (accLower.includes('corriente') && !allText.includes('corriente')) {
            throw new Error("⚠️ ERROR DE SEGURIDAD: Estás en el módulo de CUENTA CORRIENTE (CHUBUT), pero el archivo parece ser una CAJA DE AHORRO.");
        }
        if (accLower.includes('ahorro') && !allText.includes('ahorro')) {
            throw new Error("⚠️ ERROR DE SEGURIDAD: Estás en el módulo de CAJA DE AHORRO (CHUBUT), pero el archivo parece ser una CUENTA CORRIENTE.");
        }
    }

    // 3. Date Pattern Check (Flexibilizado para detectar fecha en cualquier columna)
    const datePattern = /^(\d{2}[/-]\d{2}[/-]\d{4})|(\d{4}-\d{2}-\d{2})$/;
    const hasDates = rows.some(row => 
        Array.isArray(row) && row.some(cell => String(cell || '').trim().match(datePattern))
    );
    
    if (!hasDates) {
        throw new Error("No se detectaron movimientos válidos en el archivo (¿está vacío o en otro formato?)");
    }

    return true;
}

const BankParsers = {
    galicia: (rows) => {
        const parsed = [];
        let startParsing = false;

        rows.forEach(row => {
            if (!row || row.length < 4) return;
            
            let dateStr = String(row[0] || '').trim();
            
            // Galicia Excel: Suele empezar después de los encabezados "Fecha", "Movimiento", "Débito", "Crédito"
            if (dateStr.toLowerCase().includes('fecha')) {
                startParsing = true;
                return;
            }

            if (startParsing && dateStr.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
                let desc = String(row[1] || '').replace(/\n/g, ' ').trim();
                
                let debitValue = parseSmartNumber(row[2]);
                let creditValue = parseSmartNumber(row[3]);

                let amount = 0;
                let type = 'egreso';

                if (!isNaN(creditValue) && creditValue > 0) {
                    amount = creditValue;
                    type = 'ingreso';
                } else if (!isNaN(debitValue) && debitValue !== 0) {
                    amount = Math.abs(debitValue);
                    type = 'egreso';
                }

                const [d, m, y] = dateStr.split('/');
                if (amount !== 0) {
                    parsed.push({ 
                        date: `${y}-${m}-${d}`, 
                        desc, 
                        amount: type === 'egreso' ? -amount : amount, 
                        type 
                    });
                }
            }
        });
        return parsed;
    },
    chubut: (rows) => {
        const parsed = [];
        let startParsing = false;
        rows.forEach(row => {
            if (!row || row.length < 3) return;
            
            // Convert everything to string for analysis
            const cells = row.map(c => String(c || '').trim());
            
            // Detect header for Chubut (usually Fecha, Movimientos, Código ..., Importe)
            // Según el Excel: Row 09: nan | Fecha | Movimientos | Código de movimiento | Importe
            if (cells.some(c => c.toLowerCase() === 'fecha') && cells.some(c => c.toLowerCase().includes('importe'))) {
                startParsing = true;
                return;
            }

            if (startParsing) {
                // Buscamos la columna de fecha (que tiene formato DD/MM/YYYY)
                let dateIdx = cells.findIndex(c => c.match(/^\d{2}\/\d{2}\/\d{4}$/));
                if (dateIdx === -1) return;

                let dateStr = cells[dateIdx];
                let desc = cells[dateIdx + 1] || 'Movimiento Chubut';
                
                // El importe suele ser la última columna de datos
                let amount = parseSmartNumber(row[row.length - 1]);
                
                if (!isNaN(amount) && amount !== 0) {
                    const [d, m, y] = dateStr.split('/');
                    parsed.push({ 
                        date: `${y}-${m}-${d}`, 
                        desc, 
                        amount, 
                        type: amount > 0 ? 'ingreso' : 'egreso' 
                    });
                }
            }
        });
        return parsed;
    },
    mercadopago: (rows) => {
        const parsed = [];
        let startParsing = false;
        let colMap = {};

        rows.forEach((row, rowIndex) => {
            if (!row || row.length < 2) return;
            
            // 1. Detect Headers
            const rowStr = row.join(' ').toLowerCase();
            if (rowStr.includes('fecha') || rowStr.includes('date') || rowStr.includes('settlement_date')) {
                row.forEach((cell, idx) => {
                    const c = String(cell || '').toLowerCase();
                    if (c.includes('fecha') || c.includes('date')) colMap.date = idx;
                    if (c.includes('monto_neto') || c.includes('net_amount')) colMap.amount = idx;
                    if (c.includes('monto') || c.includes('amount')) if (colMap.amount === undefined) colMap.amount = idx;
                    if (c.includes('detalle') || c.includes('type') || c.includes('transaction_type')) colMap.desc = idx;
                });
                startParsing = true;
                return;
            }

            if (startParsing) {
                let dateCell = row[colMap.date || 0];
                if (!dateCell) return;

                let dateStr = String(dateCell).split(' ')[0].split('T')[0]; // Handle YYYY-MM-DD, dates with space or T
                
                // Final validation of date format YYYY-MM-DD or DD/MM/YYYY
                if (!dateStr.match(/^\d{4}-\d{2}-\d{2}$/) && !dateStr.match(/^\d{2}\/\d{2}\/\d{4}$/)) return;

                let amount = parseSmartNumber(row[colMap.amount !== undefined ? colMap.amount : row.length - 1]);
                let desc = String(row[colMap.desc || 1] || 'Operación MercadoPago').trim();

                if (!isNaN(amount) && amount !== 0) {
                    // Convert DD/MM/YYYY to YYYY-MM-DD if needed
                    if (dateStr.includes('/')) {
                        const [d, m, y] = dateStr.split('/');
                        dateStr = `${y}-${m}-${d}`;
                    }

                    parsed.push({
                        date: dateStr,
                        desc: desc,
                        amount: amount,
                        type: amount > 0 ? 'ingreso' : 'egreso'
                    });
                } else if (!isNaN(amount) && amount !== 0 && dateStr.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
                    const [d, m, y] = dateStr.split('/');
                    parsed.push({
                        date: `${y}-${m}-${d}`,
                        desc: desc,
                        amount: amount,
                        type: amount > 0 ? 'ingreso' : 'egreso'
                    });
                }
            }
        });
        return parsed;
    }
};

function renderAccounting() {
    const taxList = document.getElementById('tax-breakdown-list');
    if (!taxList) return;

    const currentMonth = new Date().getMonth();
    const currentYear = new Date().getFullYear();

    const karlotaTxs = transactions.filter(t => t.entity === 'Lo de Karlota' || t.entity === 'karlota');
    
    // Categorías que consideramos impuestos
    const TAX_KEYWORDS = ['impuesto', 'iva', 'iibb', 'suss', 'sicore', 'tasa'];
    
    const taxTxs = karlotaTxs.filter(t => 
        TAX_KEYWORDS.some(kw => t.category.toLowerCase().includes(kw) || t.desc.toLowerCase().includes(kw))
    );

    let totalTaxes = 0;
    let totalSales = 0;

    karlotaTxs.forEach(t => {
        if (t.type === 'ingreso' && t.category.toLowerCase().includes('venta')) {
            totalSales += t.amount;
        }
    });

    taxTxs.forEach(t => totalTaxes += Math.abs(t.amount));

    document.getElementById('tax-monthly-total').textContent = formatMoney(totalTaxes);
    document.getElementById('tax-iva-estimate').textContent = formatMoney(totalSales * 0.21); // Estimación rápida
    document.getElementById('tax-retentions').textContent = formatMoney(0); // TODO: Lógica de retenciones si se agrega campo

    taxList.innerHTML = '';
    const groupedTaxes = {};
    taxTxs.forEach(t => {
        groupedTaxes[t.category] = (groupedTaxes[t.category] || 0) + Math.abs(t.amount);
    });

    Object.entries(groupedTaxes).forEach(([cat, val]) => {
        taxList.innerHTML += `
            <div class="tax-item">
                <span>${cat}</span>
                <div style="width: 200px; height: 8px; background: rgba(0,0,0,0.05); border-radius: 4px; position:relative;">
                    <div style="width: ${Math.min(100, (val/totalTaxes)*100)}%; height: 100%; background: var(--color-karlota); border-radius: 4px;"></div>
                </div>
                <span>${formatMoney(val)}</span>
            </div>
        `;
    });

    if (taxTxs.length === 0) {
        taxList.innerHTML = '<p style="text-align:center; color:var(--text-muted);">No hay registros impositivos este mes.</p>';
    }
}

function renderPayments() {
    const pendingList = document.getElementById('sindicato-pending-list');
    const historyList = document.getElementById('sindicato-history-list');
    if (!pendingList || !historyList) return;

    const today = new Date().toISOString().split('T')[0];
    
    const sindicatoTxs = transactions.filter(t => t.category.toLowerCase().includes('sindicato'));
    
    const pending = sindicatoTxs.filter(t => t.date >= today);
    const history = sindicatoTxs.filter(t => t.date < today);

    pendingList.innerHTML = '';
    pending.forEach(t => {
        pendingList.innerHTML += `
            <div class="sindicato-item">
                <div class="sindicato-info">
                    <h4>${t.desc}</h4>
                    <p><i class="fa-solid fa-calendar"></i> Vence: ${new Date(t.date).toLocaleDateString('es-AR')}</p>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight:700; color:var(--color-danger);">${formatMoney(Math.abs(t.amount))}</div>
                    <button class="btn-text" onclick="markAsPaid(${t.id})" style="color:var(--color-success); font-weight:600;">
                        <i class="fa-solid fa-check"></i> Marcar Pagado
                    </button>
                </div>
            </div>
        `;
    });

    historyList.innerHTML = '';
    history.slice(0, 10).forEach(t => {
        historyList.innerHTML += `
            <div class="sindicato-item" style="opacity: 0.7;">
                <div class="sindicato-info">
                    <h4>${t.desc}</h4>
                    <p>Pagado el ${new Date(t.date).toLocaleDateString('es-AR')}</p>
                </div>
                <div style="font-weight:700; color:var(--color-success);">${formatMoney(Math.abs(t.amount))}</div>
            </div>
        `;
    });

    const btnAddSindicato = document.getElementById('btn-add-sindicato');
    if (btnAddSindicato) {
        btnAddSindicato.onclick = () => {
            const btnNew = document.getElementById('btn-new-transaction');
            btnNew.click();
            setTimeout(() => {
                document.getElementById('t-entity').value = 'Lo de Karlota';
                document.getElementById('t-type').value = 'egreso';
                document.getElementById('t-entity').dispatchEvent(new Event('change'));
                setTimeout(() => {
                    document.getElementById('t-category').value = 'sindicato---comercio';
                }, 100);
            }, 100);
        };
    }
}

window.markAsPaid = async function(id) {
    // Al marcar como pagado, lo que hacemos es que la fecha sea HOY o ayer para que salga del semáforo/pendientes
    // o simplemente el usuario ya sabe que si cambió la fecha es porque se ejecutó.
    // Para este sistema, "Pagar" es simplemente confirmar la transaccion.
    // Podríamos cambiar la fecha a hoy.
    const tx = transactions.find(t => t.id === id);
    if (!tx) return;
    
    const today = new Date().toISOString().split('T')[0];
    tx.date = today;
    
    // Update in DB (Simulado por re-insert o update si el backend lo permitiera, 
    // pero como no hay endpoint de update directo en app.py, borramos e insertamos)
    
    const url = `/api/transactions/${id}${tx.groupId ? '?groupId=' + tx.groupId : ''}`;
    await fetch(url, { method: 'DELETE' });
    
    await fetch('/api/transactions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(tx)
    });

    transactions = await loadTransactions();
    renderTransactions();
    calculateBalances();
    renderSemaforo();
    renderAccounting();
    renderPayments();
};
