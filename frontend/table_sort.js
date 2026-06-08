document.addEventListener('DOMContentLoaded', function() {
    // Add sorting styles dynamically
    const style = document.createElement('style');
    style.innerHTML = `
        th {
            cursor: pointer;
            user-select: none;
            position: relative;
            transition: background-color 0.2s ease;
        }
        th:hover {
            background-color: rgba(9, 105, 218, 0.08) !important;
        }
        .sort-indicator {
            display: inline-block;
            margin-left: 6px;
            font-size: 0.8rem;
            color: var(--accent-color, #0969da);
            font-weight: bold;
        }
    `;
    document.head.appendChild(style);

    // Event Delegation to handle HTMX dynamic content swaps
    document.body.addEventListener('click', function(e) {
        const th = e.target.closest('th');
        if (!th) return;
        const table = th.closest('table');
        if (!table) return;
        
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        
        // Find column index
        const index = Array.from(th.parentNode.children).indexOf(th);
        
        // Avoid sorting action columns (like edit/delete columns which usually have buttons or no header name)
        const headerText = th.textContent.trim().toLowerCase();
        if (headerText === 'acciones' || headerText === '' || th.querySelector('button') || th.querySelector('input')) {
            return;
        }
        
        const rows = Array.from(tbody.querySelectorAll('tr'));
        if (rows.length <= 1 && rows[0] && rows[0].querySelector('td[colspan]')) {
            // It's an empty row message, skip sorting
            return;
        }
        
        const currentIsAsc = th.getAttribute('data-order') === 'asc';
        const nextOrder = currentIsAsc ? 'desc' : 'asc';
        
        // Reset order attribute and remove indicators from all siblings in the same row
        Array.from(th.parentNode.children).forEach(sibling => {
            sibling.removeAttribute('data-order');
            const indicator = sibling.querySelector('.sort-indicator');
            if (indicator) indicator.remove();
        });
        
        th.setAttribute('data-order', nextOrder);
        
        // Add visual sorting arrow
        const indicator = document.createElement('span');
        indicator.className = 'sort-indicator';
        indicator.innerHTML = nextOrder === 'asc' ? ' 🔼' : ' 🔽';
        th.appendChild(indicator);
        
        // Helper to extract clean cell value for comparison
        const getCellValue = (row, idx) => {
            const cell = row.children[idx];
            if (!cell) return '';
            
            let val = cell.textContent || cell.innerText || '';
            val = val.trim();
            
            // Clean currencies like "$ 12.345,67" or "$ -12.345,67"
            if (val.includes('$')) {
                const numStr = val.replace(/\$/g, '').replace(/\./g, '').replace(/,/g, '.').replace(/\s/g, '').trim();
                const num = parseFloat(numStr);
                if (!isNaN(num)) return num;
            }
            
            // Clean general numbers
            if (/^-?[\d\s]+([.,]\d+)?$/.test(val)) {
                const numStr = val.replace(/\s/g, '').replace(/\./g, '').replace(/,/g, '.');
                const num = parseFloat(numStr);
                if (!isNaN(num)) return num;
            }
            
            // Try matching date pattern (YYYY-MM-DD or DD/MM/YYYY)
            if (/^\d{4}-\d{2}-\d{2}$/.test(val)) {
                return new Date(val).getTime();
            }
            if (/^\d{2}\/\d{2}\/\d{4}$/.test(val)) {
                const parts = val.split('/');
                return new Date(parts[2], parts[1] - 1, parts[0]).getTime();
            }
            
            return val.toLowerCase();
        };
        
        rows.sort((a, b) => {
            const valA = getCellValue(a, index);
            const valB = getCellValue(b, index);
            
            if (typeof valA === 'number' && typeof valB === 'number') {
                return nextOrder === 'asc' ? valA - valB : valB - valA;
            }
            
            return nextOrder === 'asc'
                ? String(valA).localeCompare(String(valB), undefined, { numeric: true, sensitivity: 'base' })
                : String(valB).localeCompare(String(valA), undefined, { numeric: true, sensitivity: 'base' });
        });
        
        // Re-append sorted rows to the body
        rows.forEach(row => tbody.appendChild(row));
    });
});
