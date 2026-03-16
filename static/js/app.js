/**
 * ERP Nicoletti - Lógica de Negocio y Persistencia
 * Archivo adaptado para FLASK (Backend en Python)
 */

// Ya no usamos ipcRenderer ni XLSX (ahora todo va al backend Python)
// Las dependencias de NodeJS se corren en backend ahora (o se manejan por HTML)

// --- ESTADO GLOBAL Y PERSISTENCIA ---
let transactions = [];
let facturasData = [];

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
    initFacturaFilters(); // Inicializar filtros de facturas una sola vez
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
    const isMultiProcess = (accountName === 'AUTO_DETECT');
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = async (e) => {
        const data = e.target.result;

        try {
            showLoader();
            const workbook = XLSX.read(data, { type: 'array' });
            let allRows = [];
            
            // BUSQUEDA EN TODAS LAS HOJAS: Si el Excel tiene varias pestañas, las unificamos
            workbook.SheetNames.forEach(sheetName => {
                const worksheet = workbook.Sheets[sheetName];
                const sheetRows = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
                if (sheetRows.length > 0) allRows = allRows.concat(sheetRows);
            });
            
            const rows = allRows;

            let parserType = null;
            const filename = (file.name || '').toLowerCase();
            const allText = rows.flat().map(c => String(c || '').toLowerCase()).join(' ');

            // Prioridad 1: Detección por Contenido (Infallible)
            const isFacturaFile = allText.includes('denominaci') || allText.includes('emisor') || allText.includes('receptor') || 
                                  allText.includes('proveedor') || allText.includes('cuit') || 
                                  (allText.includes('iva') && allText.includes('neto')) ||
                                  (allText.includes('factura') && allText.includes('total'));
            
            const isFacturaByFilename = filename.includes('factura') || filename.includes('comprobante') || 
                                       filename.includes('arca') || filename.includes('calim') || filename.includes('afip');

            if (isFacturaFile || isFacturaByFilename) {
                parserType = 'afip';
            } else if (allText.includes('payway') || (allText.includes('monto_bruto') && allText.includes('lote'))) {
                parserType = 'payway';
            } else if (allText.includes('mercado') || allText.includes('settlement_date')) {
                parserType = 'mercadopago';
            } else if (allText.includes('banco del chubut') || (allText.includes('chubut') && allText.includes('movimientos'))) {
                parserType = 'chubut';
            } else if (allText.includes('banco galicia') || (allText.includes('movimiento') && (allText.includes('débito') || allText.includes('crédito')))) {
                parserType = 'galicia';
            }

            // Prioridad 2: Si el contenido no fue claro, usamos el nombre o el contexto de la vista
            if (!parserType) {
                const searchStr = (accountName + ' ' + filename).toLowerCase();
                if (searchStr.includes('chubut')) parserType = 'chubut';
                else if (searchStr.includes('mercado')) parserType = 'mercadopago';
                else if (searchStr.includes('payway')) parserType = 'payway';
                else if (searchStr.includes('afip') || searchStr.includes('arca') || searchStr.includes('comprobante') || searchStr.includes('calim')) parserType = 'afip';
                else if (searchStr.includes('galicia')) parserType = 'galicia';
                else if (isMultiProcess) parserType = 'afip'; // Por defecto en el importador unificado, asumimos facturas
                else parserType = 'galicia'; // Default final
            }

            // SAFETY CHECK — saltamos para AFIP/CALIM porque no tienen formato bancario
            if (parserType !== 'afip') {
                try {
                    checkFileIntegrity(rows, parserType, accountName);
                } catch (err) {
                    hideLoader();
                    alert(`⚠️ ERROR DE SEGURIDAD: ${err.message}\nLa importación fue cancelada para proteger tus datos.`);
                    return;
                }
            }

            const parsedData = (parserType === 'afip') 
                ? BankParsers.afip(rows, filename) 
                : BankParsers[parserType](rows);
            
            // Special Case: Payway Persistence
            if (parserType === 'payway') {
                await fetch('/api/payway', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(parsedData)
                });
                hideLoader();
                alert(`✅ Reporte de Payway importado: ${parsedData.length} cupones procesados.`);
                renderConciliation();
                return;
            }

            // Special Case: AFIP/CALIM → van a /api/facturas
            if (parserType === 'afip') {
                // DOUBLE CHECK: Si el nombre del archivo dice "comprobantes", forzamos origen AFIP en cada item
                const isAfipFilename = filename.includes('comprobantes') || filename.includes('arca') || filename.includes('afip');
                if (isAfipFilename) {
                    parsedData.forEach(item => item.origen = 'AFIP');
                }

                const originLabel = isAfipFilename ? 'AFIP' : (filename.includes('calim') ? 'CALIM' : 'Comprobantes');

                if (parsedData.length === 0) {
                    hideLoader();
                    alert(`⚠️ No se encontraron facturas válidas en "${filename}".\n\nRevisá que el archivo tenga los encabezados correctos (Fecha, Proveedor, Total, etc).`);
                    return;
                }

                await fetch('/api/facturas', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(parsedData)
                });
                hideLoader();
                alert(`✅ Importación de ${originLabel} completa:\n- Se analizaron ${parsedData.length} registros.\n- Los duplicados se unificaron automáticamente.\n\nRevisá el mes correspondiente en el selector.`);
                loadAndRenderFacturas();
                return;
            }

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
            if (!isMultiProcess) hideLoader();
            resolve();
        } catch (error) {
            if (!isMultiProcess) hideLoader();
            console.error("Error procesando Archivo:", error);
            alert("❌ ERROR EN " + file.name + ":\n" + error.message + "\n\nIntentá abrir el archivo y guardarlo de nuevo como .xlsx antes de subirlo.");
            resolve(); 
        }
    };
    reader.readAsArrayBuffer(file);
    });
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

    // --- SETUP FACTURAS UNIFICADO ---
    const btnImportUnified = document.getElementById('btn-import-unified');
    const unifiedUpload = document.getElementById('unified-file-upload');
    if (btnImportUnified && unifiedUpload) {
        btnImportUnified.onclick = () => unifiedUpload.click();
        unifiedUpload.onchange = async (e) => {
            if (e.target.files.length > 0) {
                showLoader();
                // Procesamos todos los archivos seleccionados uno por uno
                for (let i = 0; i < e.target.files.length; i++) {
                    await parseCSV(e.target.files[i], 'AUTO_DETECT');
                }
                e.target.value = ''; // Reset para permitir re-subida
                hideLoader();
                alert("✅ Importación de comprobantes finalizada.");
                loadAndRenderFacturas();
            }
        };
    }

    const uploadFacturaForm = document.getElementById('upload-factura-form');
    const facturaFileInput = document.getElementById('upload-factura-file');
    const previewImg = document.getElementById('factura-preview-img');
    const previewPdf = document.getElementById('factura-preview-pdf');
    const previewPlaceholder = document.getElementById('preview-placeholder');
    const btnClearPreview = document.getElementById('btn-clear-preview');

    if (facturaFileInput) {
        facturaFileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) {
                resetPreview();
                return;
            }

            const reader = new FileReader();
            reader.onload = function(event) {
                previewPlaceholder.style.display = 'none';
                btnClearPreview.style.display = 'flex';

                if (file.type.startsWith('image/')) {
                    previewImg.src = event.target.result;
                    previewImg.style.display = 'block';
                    previewPdf.style.display = 'none';
                } else if (file.type === 'application/pdf') {
                    // Usar un blob URL para el PDF permite que se vea mejor y sea más rápido
                    const url = URL.createObjectURL(file);
                    previewPdf.src = url;
                    previewPdf.style.display = 'block';
                    previewPdf.style.height = '500px'; // Forzar altura para ver bien el contenido
                    previewImg.style.display = 'none';
                }
            };
            reader.readAsDataURL(file);
        });
    }

    if (btnClearPreview) {
        btnClearPreview.addEventListener('click', resetPreview);
    }

    function resetPreview() {
        if (facturaFileInput) facturaFileInput.value = '';
        if (previewImg) { previewImg.src = ''; previewImg.style.display = 'none'; }
        if (previewPdf) { previewPdf.src = ''; previewPdf.style.display = 'none'; }
        if (previewPlaceholder) previewPlaceholder.style.display = 'block';
        if (btnClearPreview) btnClearPreview.style.display = 'none';
        
        // Limpiar búsqueda
        if (searchStatus) searchStatus.textContent = '';
        if (searchDetail) {
            searchDetail.textContent = 'Buscaremos este número en la base de datos de ARCA/CALIM.';
            searchDetail.style.color = 'var(--text-muted)';
        }
    }

    const searchStatus = document.getElementById('search-factura-status');
    const searchDetail = document.getElementById('search-factura-detail');
    const facturaNumInput = document.getElementById('upload-factura-num');

    if (facturaNumInput) {
        facturaNumInput.addEventListener('input', function(e) {
            const val = e.target.value.trim();
            if (val.length < 3) {
                searchStatus.textContent = '';
                searchDetail.textContent = 'Buscaremos este número en la base de datos de ARCA/CALIM.';
                searchDetail.style.color = 'var(--text-muted)';
                return;
            }

            // NORMALIZACIÓN: Quitamos guiones y ceros a la izquierda para comparar "manzanas con manzanas"
            const cleanVal = val.replace(/-/g, '').replace(/^0+/, '');
            
            const match = facturasData.find(f => {
                const cleanF = f.numero_completo.replace(/-/g, '').replace(/^0+/, '');
                return cleanF === cleanVal || cleanF.endsWith(cleanVal) || cleanVal.endsWith(cleanF);
            });
            
            if (match) {
                const systems = [];
                if (match.esta_en_afip) systems.push('ARCA');
                if (match.esta_en_calim) systems.push('CALIM');
                
                const fechaPretty = match.fecha_emision ? match.fecha_emision.split('-').reverse().join('/') : 'Sin fecha';
                
                searchStatus.innerHTML = `✅ ENCONTRADA <span style="font-size:11px; font-weight:normal; opacity:0.8;">(${fechaPretty})</span>`;
                searchStatus.style.color = 'var(--color-success)';
                searchDetail.textContent = `Proveedor: ${match.proveedor || 'No especificado'}. Sistemas: ${systems.join(' + ')}.`;
                searchDetail.style.color = 'var(--color-success)';
            } else {
                searchStatus.textContent = '❓ NO ENCONTRADA';
                searchStatus.style.color = '#f59e0b';
                searchDetail.textContent = 'No figura en ARCA ni CALIM. Se marcará como "SUBIR A CALIM".';
                searchDetail.style.color = '#f59e0b';
            }
        });
    }

    if (uploadFacturaForm) {
        uploadFacturaForm.onsubmit = async (e) => {
            e.preventDefault();
            const num = document.getElementById('upload-factura-num').value.trim();
            const fileInput = document.getElementById('upload-factura-file');
            
            if (!num || fileInput.files.length === 0) {
                alert('Por favor, seleccioná primero la foto/PDF y luego ingresá los últimos 5 dígitos del N° de factura.');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('numero_completo', num);

            showLoader();
            try {
                const res = await fetch('/api/facturas/upload', {
                    method: 'POST',
                    body: formData
                });
                const result = await res.json();
                hideLoader();
                if (result.success) {
                    // Si el backend nos devolvió la fecha, avisamos al usuario
                    if (result.fecha) {
                        const [y, m, d] = result.fecha.split('-');
                        alert(`${result.msg}\n\nPeriodo vinculado: ${m}/${y}`);
                    } else {
                        alert(result.msg);
                    }
                    loadAndRenderFacturas();
                    uploadFacturaForm.reset();
                    resetPreview();
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (err) {
                hideLoader();
                alert('Error en la subida.');
            }
        };
    }
});

// --- NAVEGACION Y MODULOS NUEVOS ---

// --- CONCILIACIÓN PAYWAY ---

async function renderConciliation() {
    const paywayList = document.getElementById('payway-list');
    if (!paywayList) return;

    try {
        const response = await fetch('/api/payway');
        const paywayRecords = await response.json();

        if (paywayRecords.length === 0) {
            paywayList.innerHTML = '<p style="text-align:center; color:var(--text-muted); padding: 40px;">Importa un reporte de Payway para empezar la conciliación.</p>';
            return;
        }

        paywayList.innerHTML = '';
        
        let pendingTotal = 0;
        let clearedTotal = 0;

        paywayRecords.forEach(pw => {
            // Buscamos coincidencia en transacciones bancarias
            // Payway liquida el lote entero o cupones individuales pero el banco recibe el NETO
            // Por ahora buscamos coincidencias aproximadas por fecha y monto
            const match = transactions.find(t => 
                (t.account || '').toLowerCase().includes('galicia') && 
                t.amount > 0 &&
                Math.abs(t.amount - (pw.monto_bruto * 0.95)) < (pw.monto_bruto * 0.1) && // Aproximación (5% de arancel+impuestos)
                Math.abs(new Date(t.date) - new Date(pw.presentacion_date)) < (5 * 24 * 60 * 60 * 1000) // 5 días de ventana
            );

            const isMatched = match !== undefined;
            if (isMatched) clearedTotal += pw.monto_bruto;
            else pendingTotal += pw.monto_bruto;

            const item = document.createElement('div');
            item.className = 'transaction-item';
            item.style.padding = '12px';
            item.style.cursor = 'pointer';
            item.innerHTML = `
                <div class="t-icon" style="background:${isMatched ? 'var(--color-success)' : 'rgba(0,0,0,0.05)'}; color:${isMatched ? 'white' : 'var(--text-muted)'}">
                    <i class="fa-solid ${isMatched ? 'fa-check-double' : 'fa-hourglass-half'}"></i>
                </div>
                <div class="t-details">
                    <div class="t-title">${pw.marca} - Lote ${pw.lote}</div>
                    <div class="t-subtitle">Cupón: ${pw.cupon} &bull; ${new Date(pw.compra_date).toLocaleDateString()}</div>
                </div>
                <div style="text-align:right">
                    <div class="t-amount">${formatMoney(pw.monto_bruto)}</div>
                    <div style="font-size:11px; color:${isMatched ? 'var(--color-success)' : 'var(--color-danger)'}">
                        ${isMatched ? 'Visto en Banco' : 'Pendiente'}
                    </div>
                </div>
            `;
            
            if (isMatched) {
                item.onclick = () => {
                    const bankList = document.getElementById('bank-matches-list');
                    bankList.innerHTML = `
                        <div class="glass-panel" style="padding:16px; border-left:4px solid var(--color-success)">
                            <p style="font-size:12px; color:var(--text-muted); margin-bottom:8px;">COINCIDENCIA EN BANCO:</p>
                            <div style="font-weight:600;">${match.desc}</div>
                            <div style="font-size:14px; color:var(--color-success); font-weight:700;">${formatMoney(match.amount)}</div>
                            <div style="font-size:12px; color:var(--text-muted);">${new Date(match.date).toLocaleDateString()}</div>
                        </div>
                    `;
                };
            }

            paywayList.appendChild(item);
        });

        // Update cards
        animateValue('conc-pending', 0, pendingTotal);
        animateValue('conc-cleared', 0, clearedTotal);
        animateValue('conc-fees', 0, (clearedTotal + pendingTotal) * 0.05); // Estimado 5%

    } catch (err) {
        console.error('Error rendering conciliation', err);
    }
}

function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item, .submenu-item');
    const views = document.querySelectorAll('.view-container');

    // Submenu Toggle Logic
    const menuAccounts = document.getElementById('menu-accounts');
    const submenuAccounts = document.getElementById('submenu-accounts');

    if (menuAccounts && submenuAccounts) {
        menuAccounts.addEventListener('click', (e) => {
            e.preventDefault();
            submenuAccounts.classList.toggle('open');
            menuAccounts.classList.toggle('open');
        });
    }

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetView = item.getAttribute('data-view');
            const accountName = item.getAttribute('data-account');

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
                    if (accountName) {
                        setupBankView(accountName);
                    }
                }

                if (v.id === viewId) {
                    v.classList.add('active');
                    // Animate view entry
                    gsap.fromTo(v, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.4 });
                    
                    if (targetView === 'conciliation') {
                        renderConciliation();
                    }
                    if (targetView === 'facturas') {
                        loadAndRenderFacturas();
                    }
                }
            });
        });
    });

    // Payway Import Setup
    const btnPayway = document.getElementById('btn-import-payway');
    const paywayUpload = document.getElementById('payway-file-upload');
    if (btnPayway && paywayUpload) {
        btnPayway.onclick = () => paywayUpload.click();
        paywayUpload.onchange = (e) => {
            if (e.target.files.length > 0) {
                parseCSV(e.target.files[0], 'Payway');
                e.target.value = '';
            }
        };
    }
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
    mercadopago: ['fecha', 'detalle', 'monto'],
    payway: ['compra', 'presentacion', 'lote', 'monto_bruto']
};

function checkFileIntegrity(rows, bankType, accountName = '') {
    const required = BankSchemes[bankType];
    if (!required) return true;

    const allCells = rows.flat().map(c => String(c || '').toLowerCase());
    const allText = allCells.join(' ');
    
    // 1. Check basic headers (Special handling for MercadoPago to allow Settlement reports)
    let missing = required.filter(word => !allCells.some(cell => cell.includes(word)));
    
    // If it's MercadoPago and standard headers are missing, check for Settlement headers
    if (bankType === 'mercadopago' && missing.length > 0) {
        const settlementHeaders = ['settlement_date', 'settlement_net_amount', 'transaction_type'];
        const missingSettlement = settlementHeaders.filter(word => !allCells.some(cell => cell.includes(word)));
        
        // If settlement headers are present, it's NOT missing
        if (missingSettlement.length === 0) {
            missing = [];
        }
    }

    // Special handling for Payway
    if (bankType === 'payway' && missing.length > 0) {
        const altPayway = ['compra', 'monto_bruto', 'lote'];
        const missingAlt = altPayway.filter(word => !allCells.some(cell => cell.includes(word)));
        if (missingAlt.length === 0) missing = [];
    }

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

    // 3. Date Pattern Check (Flexibilizado para detectar fecha en cualquier columna, incluyendo formatos ISO con T)
    const datePattern = /^(\d{2}[/-]\d{2}[/-]\d{4})|(\d{4}-\d{2}-\d{2}(T|\s|$))/;
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
    },
    payway: (rows) => {
        const parsed = [];
        let startParsing = false;
        let colMap = {};

        rows.forEach(row => {
            if (!row || row.length < 5) return;
            const rowStr = row.join(' ').toUpperCase();
            
            // Header detection
            if (rowStr.includes('COMPRA') && rowStr.includes('MONTO_BRUTO')) {
                row.forEach((cell, idx) => {
                    const c = String(cell || '').toUpperCase();
                    if (c.includes('COMPRA')) colMap.compra = idx;
                    if (c.includes('PRESENTACION')) colMap.presentacion = idx;
                    if (c.includes('LOTE')) colMap.lote = idx;
                    if (c.includes('CUPON')) colMap.cupon = idx;
                    if (c.includes('MARCA')) colMap.marca = idx;
                    if (c.includes('MONTO_BRUTO')) colMap.bruto = idx;
                });
                startParsing = true;
                return;
            }

            if (startParsing) {
                let compra = String(row[colMap.compra] || '');
                let presentacion = String(row[colMap.presentacion] || '');
                let lote = parseInt(row[colMap.lote]);
                let cupon = String(row[colMap.cupon] || '');
                let marca = String(row[colMap.marca] || '');
                let bruto = parseSmartNumber(row[colMap.bruto]);

                if (compra && !isNaN(bruto)) {
                    // Convert dates to YYYY-MM-DD
                    const cleanDate = (d) => {
                        const parts = d.split('/');
                        if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`;
                        return d;
                    };

                    parsed.push({
                        compra_date: cleanDate(compra),
                        presentacion_date: cleanDate(presentacion),
                        lote: lote,
                        cupon: cupon,
                        marca: marca,
                        monto_bruto: bruto
                    });
                }
            }
        });
        return parsed;
    },

    // =====================================================================
    // PARSER UNIFICADO: AFIP (ARCA) y CALIM
    // Auto-detecta el formato y extrae Neto, IVA, Total, Proveedor, Fecha
    // =====================================================================
    afip: (rows, filename = '') => {
        const parsed = [];
        let colMap = {};
        let isCalim = false;
        let headerRowIndex = -1;

        const fileLower = filename.toLowerCase();
        const forceAfip = fileLower.includes('comprobantes') || fileLower.includes('arca') || fileLower.includes('afip');
        const forceCalim = fileLower.includes('calim');

        // Paso 1: detectar fila de encabezados mediante SCORING (más robusto)
        let maxScore = 0;
        for (let i = 0; i < Math.min(rows.length, 60); i++) {
            const rowStr = (rows[i] || []).join(' ').toLowerCase();
            let score = 0;
            if (rowStr.includes('fecha')) score += 5;
            if (rowStr.includes('punto de venta') || rowStr.includes('pto. vta.') || rowStr.includes('p.v.')) score += 10;
            if (rowStr.includes('número desde') || rowStr.includes('nro. desde') || rowStr.includes('número hasta')) score += 10;
            if (rowStr.includes('proveedor') || rowStr.includes('denominación') || rowStr.includes('emisor')) score += 5;
            if (rowStr.includes('iva') || rowStr.includes('impuesto') || rowStr.includes('cuit')) score += 5;
            if (rowStr.includes('neto') || rowStr.includes('total') || rowStr.includes('gravado')) score += 5;

            if (score > maxScore) {
                maxScore = score;
                headerRowIndex = i;
            }
        }

        if (headerRowIndex === -1 || maxScore < 15) {
            console.error("❌ No se pudo encontrar una cabecera válida en el archivo:", filename);
            return parsed;
        }

        // DETERMINAR ORIGEN basado en columnas específicas de AFIP
        const headerStr = rows[headerRowIndex].join(' ').toLowerCase();
        isCalim = !(headerStr.includes('punto de venta') || headerStr.includes('pto. vta.') || headerStr.includes('número desde'));
        if (forceAfip) isCalim = false;
        if (forceCalim) isCalim = true;
        
        console.log(`🔍 [${filename}] Fila Cabecera: ${headerRowIndex}, Origen: ${isCalim ? 'CALIM' : 'AFIP'}`);

        // Paso 2: mapear columnas con un espectro mucho más amplio de nombres
        rows[headerRowIndex].forEach((cell, idx) => {
            const h = String(cell || '').toLowerCase().trim();
            
            // Fecha: Prioridad absoluta a "fecha" o "fecha de emisión"
            if (h === 'fecha' || h === 'emisión' || h === 'fecha de emisión') {
                colMap.fecha = idx;
            } else if (!colMap.fecha && (h.includes('fecha') || h.includes('emisi') || h.includes('date'))) {
                // Solo asignamos si no encontramos una exacta antes, para evitar el overwrite de "Fecha Vto"
                if (!h.includes('vencimiento') && !h.includes('vto')) {
                    colMap.fecha = idx;
                }
            }
            
            // Tipo
            if (h.includes('tipo') || h.includes('clase') || h.includes('comprobante')) colMap.tipo = idx;
            
            // Proveedor
            if (h.includes('denominaci') || h.includes('proveedor') || h.includes('emisor') || h.includes('nombre') || h.includes('raz') || h.includes('vendedor')) colMap.proveedor = idx;
            
            // Punto de Venta y Número (AFIP estándar)
            if (h.includes('punto de venta') || h.includes('p.v.') || h.includes('pto. vta.')) colMap.pv = idx;
            if (h.includes('número desde') || h.includes('numero desde') || h.includes('nro. desde') || h.includes('número hasta')) colMap.num = idx;
            
            // Número Directo (CALIM o Excel simplificado)
            if (h === 'numero' || h === 'número' || h === 'nro' || h === 'nro.' || h.includes('factura') || h.includes('comprobante')) {
                if (colMap.numero_calim === undefined) colMap.numero_calim = idx;
            }

            // Neto
            if (h.includes('neto') || h.includes('gravado') || h.includes('subtotal') || h.includes('base imponible')) colMap.neto = idx;
            
            // IVA
            if (h.includes('iva') || h.includes('impuesto') || h.includes('21%') || h.includes('10.5%')) colMap.iva = idx;
            
            // Total
            if (h.includes('total') || h.includes('importe') || h.includes('monto') || h.includes('suma')) colMap.total = idx;
        });

        // Paso 3: parsear filas de datos con validaciones de seguridad
        let importadosAFIP = 0;
        let importadosCALIM = 0;

        for (let i = headerRowIndex + 1; i < rows.length; i++) {
            const row = rows[i];
            if (!row || !Array.isArray(row) || row.every(c => !c)) continue;
            
            const getVal = (key) => {
                if (colMap[key] === undefined) return '';
                const val = row[colMap[key]];
                return val !== undefined && val !== null ? String(val).trim() : '';
            };

            // Extracción de Número Unificada
            let rawPv = getVal('pv') || '';
            let rawNum = getVal('num') || getVal('numero_calim') || '';

            // Si el número contiene el PV (formato XXXX-XXXXXXXX)
            if (rawNum.includes('-')) {
                const p = rawNum.split('-');
                if (p.length >= 2) {
                    rawPv = rawPv || p[0];
                    rawNum = p[1];
                }
            }
            
            const pv = rawPv.replace(/\D/g, '').padStart(4, '0');
            const num = rawNum.replace(/\D/g, '').padStart(8, '0');
            let numeroCompleto = (pv + num).replace(/^0+/, '');
            
            if (!numeroCompleto || numeroCompleto.length < 2) continue; 

            // Fecha con detección ULTRA-ROBUSTA
            let fechaRaw = getVal('fecha');
            let fechaParsed = null;
            
            if (fechaRaw) {
                // Caso A: Ya es un objeto Date de JS (XLSX puede devolver esto)
                if (fechaRaw instanceof Date) {
                    fechaParsed = fechaRaw.toISOString().split('T')[0];
                } 
                // Caso B: Es un número serial de Excel (ej: 46053)
                else if (!isNaN(fechaRaw) && parseFloat(fechaRaw) > 30000) {
                    const excelDate = new Date(Math.round((parseFloat(fechaRaw) - 25569) * 86400 * 1000));
                    fechaParsed = excelDate.toISOString().split('T')[0];
                } 
                // Caso C: Es texto (DD/MM/YYYY, YYYY-MM-DD, etc)
                else if (typeof fechaRaw === 'string') {
                    const cleanDateStr = fechaRaw.split(' ')[0].trim(); 
                    const parts = cleanDateStr.split(/[\/\-\.]/); // Soporta /, - y .
                    
                    if (parts.length === 3) {
                        let y, m, d;
                        if (parts[0].length === 4) { // YYYY-MM-DD
                            y = parts[0]; m = parts[1]; d = parts[2];
                        } else if (parts[2].length === 4) { // DD/MM/YYYY o MM/DD/YYYY
                            y = parts[2];
                            const p0 = parseInt(parts[0]);
                            const p1 = parseInt(parts[1]);
                            
                            // Lógica inteligente: Si el del medio es mayor a 12, el otro es el mes
                            if (p1 > 12) { // Formato MM/DD/YYYY
                                m = p0; d = p1;
                            } else { // Formato estándar DD/MM/YYYY
                                m = p1; d = p0;
                            }
                        }
                        
                        if (y && m && d) {
                            fechaParsed = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                        }
                    }
                }
            }

            if (!fechaParsed) {
                console.warn(`⚠️ Fila ${i}: No se pudo parsear fecha del valor:`, fechaRaw);
            }

            const tipoComp = getVal('tipo') || 'Factura';
            const isNC = tipoComp.toLowerCase().includes('nota de crédito') || tipoComp.toLowerCase().includes('nota de credito');

            // Si es Nota de Crédito, los montos deben ser negativos para que resten
            const factor = isNC ? -1 : 1;

            parsed.push({
                numero_completo: numeroCompleto,
                tipo_comprobante: tipoComp,
                proveedor: getVal('proveedor') || 'Proveedor Desconocido',
                fecha_emision: fechaParsed,
                neto_gravado: parseSmartNumber(getVal('neto')) * factor,
                monto_iva: parseSmartNumber(getVal('iva')) * factor,
                monto_total: parseSmartNumber(getVal('total')) * factor,
                origen: isCalim ? 'CALIM' : 'AFIP'
            });

            if (isCalim) importadosCALIM++; else importadosAFIP++;
        }

        if (parsed.length === 0 && rows.length > 5) {
            throw new Error("No se detectaron facturas válidas. Revisá que el archivo tenga números de factura legibles.");
        }
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

// =====================================================================
// GESTIÓN DE FACTURAS (COMPROBANTES)
// =====================================================================

function initFacturaFilters() {
    const fMonth = document.getElementById('facturas-filter-month');
    const fYear = document.getElementById('facturas-filter-year');
    if (fMonth && fYear) {
        const now = new Date();
        fMonth.value = String(now.getMonth() + 1).padStart(2, '0');
        fYear.value = String(now.getFullYear());
        
        fMonth.onchange = () => loadAndRenderFacturas();
        fYear.onchange = () => loadAndRenderFacturas();
    }
}

async function loadAndRenderFacturas() {
    const list = document.getElementById('facturas-list');
    if (!list) return;

    try {
        const res = await fetch('/api/facturas');
        facturasData = await res.json();
        
        const monthEl = document.getElementById('facturas-filter-month');
        const yearEl = document.getElementById('facturas-filter-year');

        if (!monthEl || !yearEl) {
            console.error("❌ Los selectores de mes/año no se encuentran en el HTML. Por favor, pulsa CTRL + F5 para recargar la página.");
            // Fallback: mostrar todas si no hay selectores (versión vieja del HTML)
            renderFacturaRows(facturasData);
            return;
        }

        const selMonth = monthEl.value;
        const selYear = yearEl.value;

        // Filtrar facturas por el mes y año seleccionados
        const facturas = facturasData.filter(f => {
            if (selMonth === 'all') return true;
            if (!f.fecha_emision) return false;
            const [y, m, d] = f.fecha_emision.split('-');
            return y === selYear && m === selMonth;
        });

        renderFacturaRows(facturas, selMonth, selYear);

    } catch (err) {
        console.error("Error cargando facturas", err);
    }
}

function renderFacturaRows(facturas, selMonth = '', selYear = '') {
    const list = document.getElementById('facturas-list');
    if (!list) return;

    if (facturas.length === 0) {
        const msg = selMonth ? `No hay comprobantes cargados para ${selMonth}/${selYear}.` : "No hay comprobantes cargados.";
        list.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 40px; color: var(--text-muted);">${msg}</td></tr>`;
        animateValue('facturas-total-iva', 0, 0);
        animateValue('facturas-total-neto', 0, 0);
        document.getElementById('facturas-faltantes').textContent = 0;
        return;
    }

    let totalIva = 0;
    let totalNeto = 0;
    let faltantes = 0;

    list.innerHTML = facturas.map(f => {
        totalIva += (f.monto_iva || 0);
        totalNeto += (f.neto_gravado || 0);
        
        let statusLabel = '';
        let statusColor = '';
        
        if (f.estado_proceso === 'ARCHIVADO') {
            statusLabel = 'NORMALIZADA';
            statusColor = 'var(--color-success)';
        } else if (f.estado_proceso === 'A_SUBIR') {
            statusLabel = 'SUBIR A CALIM';
            statusColor = '#f59e0b'; // Naranja vibrante
            faltantes++;
        } else {
            statusLabel = 'FALTA FÍSICO';
            statusColor = 'var(--color-danger)';
            faltantes++;
        }

        const systems = `
            <div style="display:flex; gap:4px;">
                <span style="padding:2px 6px; border-radius:4px; background:${f.esta_en_afip ? '#10b981' : 'rgba(0,0,0,0.05)'}; color:${f.esta_en_afip ? 'white' : '#aaa'}; font-size:9px; font-weight:900; letter-spacing:0.5px; border: 1px solid ${f.esta_en_afip ? '#059669' : 'transparent'};">AFIP</span>
                <span style="padding:2px 6px; border-radius:4px; background:${f.esta_en_calim ? '#0ea5e9' : 'rgba(0,0,0,0.05)'}; color:${f.esta_en_calim ? 'white' : '#aaa'}; font-size:9px; font-weight:900; letter-spacing:0.5px; border: 1px solid ${f.esta_en_calim ? '#0284c7' : 'transparent'};">CALIM</span>
            </div>
        `;

        return `
            <tr style="border-bottom: 1px solid var(--border-color);">
                <td style="padding: 12px 8px;">${f.fecha_emision ? f.fecha_emision.split('-').reverse().join('/') : '-'}</td>
                <td style="padding: 12px 8px; font-size:11px; opacity:0.8;">${f.tipo_comprobante || 'Factura'}</td>
                <td style="padding: 12px 8px; font-family: 'Inter'; font-weight:600;">${f.numero_completo}</td>
                <td style="padding: 12px 8px; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${f.proveedor || ''}">${f.proveedor || '-'}</td>
                <td style="padding: 12px 8px;">${systems}</td>
                <td style="padding: 12px 8px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:${statusColor}; font-weight:800; font-size:10px; letter-spacing:0.5px;">${statusLabel}</span>
                        ${f.ruta_archivo ? `<a href="${f.ruta_archivo}" target="_blank" style="color:${statusColor};"><i class="fa-solid fa-file-invoice"></i></a>` : ''}
                    </div>
                </td>
                <td style="padding: 12px 8px; text-align: right; font-weight: 700; color: ${f.monto_total < 0 ? '#f59e0b' : 'inherit'};">
                    ${formatMoney(f.monto_total || 0)}
                </td>
            </tr>
        `;
    }).join('');

    animateValue('facturas-total-iva', 0, totalIva);
    animateValue('facturas-total-neto', 0, totalNeto);
    document.getElementById('facturas-faltantes').textContent = faltantes;
}
