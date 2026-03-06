/**
 * ERP Nicoletti - Lógica de Negocio y Persistencia
 * Desarrollador: Senior Frontend
 */

// --- ESTADO GLOBAL Y PERSISTENCIA ---
let transactions = [];
const STORAGE_KEY = 'erp_transactions';

/**
 * Carga las transacciones desde LocalStorage
 */
function loadTransactions() {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : [];
}

/**
 * Guarda las transacciones en LocalStorage
 */
function saveTransactions(data) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

// --- UTILIDADES ---
const formatMoney = (val) => new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 0
}).format(val);

/**
 * Inicialización de la App
 */
document.addEventListener('DOMContentLoaded', () => {
    // 1. Cargar datos persistidos
    transactions = loadTransactions();

    // 2. Inicializar componentes visuales
    initChart();
    renderTransactions();
    calculateBalances();
    setupModals();

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
});

// --- LÓGICA DE NEGOCIO (FRONTERAS DE PATRIMONIO) ---

/**
 * Calcula y actualiza los saldos en las tarjetas de estadísticas
 * Aplica lógica de ingresos (+) y egresos (-) por entidad.
 */
function calculateBalances() {
    const balances = {
        karlota: 0,
        joaquin: 0,
        jorgelina: 0
    };

    transactions.forEach(t => {
        // En un sistema real, los montos ya vendrían con su signo desde el guardado,
        // pero aseguramos la lógica de "Fronteras de Patrimonio" aquí.
        if (balances.hasOwnProperty(t.entity)) {
            balances[t.entity] += t.amount;
        }
    });

    // Actualizar el DOM con los resultados calculados
    document.getElementById('balance-karlota').textContent = formatMoney(balances.karlota);
    document.getElementById('balance-joaquin').textContent = formatMoney(balances.joaquin);
    document.getElementById('balance-jorgelina').textContent = formatMoney(balances.jorgelina);
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

    const accountsData = {
        joaquin: ['CA$ Hipotecario', 'USD Hipotecario', 'CA$ Credicoop', 'MercadoPago', 'Billetera (Efectivo)'],
        jorgelina: ['CA$ Chubut', 'CC$ Chubut', 'CA$ Galicia', 'USD Galicia', 'CC Galicia', 'MercadoPago', 'Naranja', 'Billetera (Efectivo)'],
        karlota: ['CA$ Chubut', 'CC$ Chubut', 'CA$ Galicia', 'USD Galicia', 'CC Galicia', 'MercadoPago', 'Naranja', 'Billetera (Efectivo)']
    };

    const incomeCategories = {
        joaquin: ['Sueldo (💼)', 'Comisión (💰)', 'Alquiler (🏠)', 'Inversiones (📈)', 'Regalos (🎁)', 'Otros Ingresos'],
        jorgelina: ['Sueldo (💼)', 'Inversiones (📈)', 'Regalos (🎁)', 'Otros Ingresos'],
        karlota: ['Ventas (🧾)', 'Transferencia recibida (💸)', 'Intereses (🏦)', 'Reembolsos (📦)', 'Aporte Extraordinario', 'Otros Ingresos']
    };

    const expenseCategories = {
        joaquin: ['Comida (🍔)', 'Transporte (🚗)', 'Vivienda (🏠)', 'Servicios (💡)', 'Impuestos (🧾)', 'Salud (🏥)', 'Educación (🎓)', 'Ocio (🎮)', 'Compras (🛒)', 'Ropa (👕)', 'Tecnología (💻)', 'Deportes (🏋️)', 'Estética (💅)', 'Mascotas (🐶)', 'Pago Tarjeta (💳)', 'Otros (📦)'],
        jorgelina: ['Comida (🍔)', 'Transporte (🚗)', 'Vivienda (🏠)', 'Servicios (💡)', 'Impuestos (🧾)', 'Salud (🏥)', 'Educación (🎓)', 'Ocio (🎮)', 'Compras (🛒)', 'Ropa (👕)', 'Tecnología (💻)', 'Deportes (🏋️)', 'Estética (💅)', 'Mascotas (🐶)', 'Pago Tarjeta (💳)', 'Otros (📦)'],
        karlota: ['Proveedores Insumos', 'Mercadería Local', 'Alquiler Local (🏠)', 'Sueldos (💸)', 'Impuestos (🧾)', 'Servicios (💡)', 'Mantenimiento (📦)', 'Otros Egresos']
    };

    function updateAccounts() {
        const entity = entitySelect.value;
        const accounts = accountsData[entity] || [];
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
        updateCategories();
        document.getElementById('group-destino').style.display = typeSelect.value === 'transferencia' ? 'block' : 'none';
    });

    btnNew.addEventListener('click', () => {
        updateAccounts();
        updateCategories();
        modalOverlay.style.display = 'flex';
        gsap.to(modalOverlay, { opacity: 1, duration: 0.3, ease: "power2.out" });
        gsap.fromTo(".modal",
            { scale: 0.8, opacity: 0, y: 30 },
            { scale: 1, opacity: 1, y: 0, duration: 0.5, ease: "back.out(1.5)" }
        );
    });

    btnClose.addEventListener('click', closeAndClear);
    modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) closeAndClear(); });

    // --- MANEJO DEL FORMULARIO (FLUJO DE DATOS) ---
    form.addEventListener('submit', (e) => {
        e.preventDefault();

        const entity = entitySelect.value;
        const type = typeSelect.value;
        const amountValue = parseFloat(document.getElementById('t-amount').value);
        let desc = document.getElementById('t-desc').value.trim();
        const account = accountSelect.options[accountSelect.selectedIndex]?.text || '';
        const category = categorySelect.options[categorySelect.selectedIndex]?.text || '';

        if (!desc) desc = category;

        const entityDestino = document.getElementById('t-entity-destino').value;

        if (type === 'transferencia' && entity === entityDestino) {
            alert('La entidad destino no puede ser igual a la de origen.');
            return;
        }

        const dateStr = new Date().toLocaleDateString('es-AR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

        if (type === 'transferencia') {
            const transferId = Date.now();
            transactions.unshift({
                id: transferId,
                groupId: transferId,
                entity, account, category, type: 'egreso', amount: -amountValue,
                desc: `Transferencia a ${document.getElementById('t-entity-destino').options[document.getElementById('t-entity-destino').selectedIndex].text} - ${desc}`,
                date: dateStr
            });
            transactions.unshift({
                id: transferId + 1,
                groupId: transferId,
                entity: entityDestino, account: '', category: 'Transferencia recibida', type: 'ingreso', amount: amountValue,
                desc: `Transferencia de ${entitySelect.options[entitySelect.selectedIndex].text} - ${desc}`,
                date: dateStr
            });
        } else {
            const amount = type === 'egreso' ? -amountValue : amountValue;
            transactions.unshift({
                id: Date.now(), entity, account, category, type, amount, desc, date: dateStr
            });
        }

        saveTransactions(transactions);
        renderTransactions();
        calculateBalances();
        updateChart(transactions);
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
}

window.deleteTransaction = function (id) {
    if (confirm('¿Estás seguro de eliminar este movimiento?')) {
        const tx = transactions.find(t => t.id === id);
        if (!tx) return;
        if (tx.groupId) {
            transactions = transactions.filter(t => t.groupId !== tx.groupId);
        } else {
            transactions = transactions.filter(t => t.id !== id);
        }
        saveTransactions(transactions);
        renderTransactions();
        calculateBalances();
        updateChart(transactions);
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
        if (t.entity === 'karlota') { entityColor = 'var(--color-karlota)'; entityIcon = 'fa-shop'; entityName = 'Lo de Karlota'; }
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
                { label: 'Egresos Totales', data: [], borderColor: '#ef4444', backgroundColor: gradientExp, borderWidth: 3, tension: 0.4, fill: true, pointBackgroundColor: '#ef4444', pointBorderColor: '#fff', pointRadius: 4 }
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

    const last7Days = Array.from({ length: 7 }, (_, i) => {
        const d = new Date(); d.setDate(d.getDate() - i);
        return d.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' });
    }).reverse();

    const dataInc = new Array(7).fill(0);
    const dataExp = new Array(7).fill(0);

    txs.forEach(t => {
        if (t.entity !== 'karlota') return;
        const txDate = t.date.split(',')[0];
        const dayIndex = last7Days.findIndex(d => txDate.startsWith(d));
        if (dayIndex !== -1) {
            if (t.type === 'ingreso') dataInc[dayIndex] += t.amount;
            else if (t.type === 'egreso') dataExp[dayIndex] += Math.abs(t.amount);
        }
    });

    mainChartInstance.data.labels = last7Days;
    mainChartInstance.data.datasets[0].data = dataInc;
    mainChartInstance.data.datasets[1].data = dataExp;
    mainChartInstance.update();
}
