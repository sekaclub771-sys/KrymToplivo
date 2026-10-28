let fuelStations = [];
let selectedFuelType = 'all';

async function fetchDatabase() {
    const container = document.getElementById('cardsContainer');
    container.innerHTML = '<p style="text-align:center; opacity:0.6; font-size:15px; margin-top:20px;">Синхронизация с базой данных АЗС...</p>';
    
    try {
        const res = await fetch('data.json?cache_buster=' + Date.now());
        fuelStations = await res.json();
        displayStations(fuelStations);
    } catch (err) {
        console.error("Ошибка загрузки данных:", err);
        container.innerHTML = '<p style="text-align:center; color:#ef4444; font-size:15px; margin-top:20px;">Ошибка связи. Потяните страницу вниз для обновления.</p>';
    }
}

function displayStations(dataset) {
    const container = document.getElementById('cardsContainer');
    container.innerHTML = '';

    if (dataset.length === 0) {
        container.innerHTML = '<p style="text-align:center; opacity:0.5; font-size:15px; margin-top:20px;">По данному запросу заправок не найдено.</p>';
        return;
    }

    dataset.forEach(station => {
        const block = document.createElement('div');
        block.className = 'card';

        const badgeHtml = station.fuels.map(f => {
            let modifier = '';
            if (f === 'АИ-92') modifier = 'active-92';
            if (f === 'ДТ') modifier = 'active-dt';
            return `<span class="fuel-badge ${modifier}">${f}</span>`;
        }).join(' ');

        block.innerHTML = `
            <div class="card-header">
                <span class="brand">${station.brand}</span>
            </div>
            <div class="address">📍 ${station.address}</div>
            <div class="fuel-row">${badgeHtml || '<em style="color:#ef4444; font-size:14px; font-weight:600;">Топливо раскупили</em>'}</div>
            <div class="notes">${station.terms}</div>
            <div class="meta">Источник данных: ${station.source}</div>
        `;
        container.appendChild(block);
    });
}

function selectFuel(fuelType) {
    selectedFuelType = fuelType;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    
    if (fuelType === 'all') document.getElementById('btn-all').classList.add('active');
    if (fuelType === 'АИ-95') document.getElementById('btn-95').classList.add('active');
    if (fuelType === 'АИ-92') document.getElementById('btn-92').classList.add('active');
    if (fuelType === 'ДТ') document.getElementById('btn-dt').classList.add('active');
    
    runFilters();
}

function runFilters() {
    const textQuery = document.getElementById('searchInput').value.toLowerCase();

    const result = fuelStations.filter(st => {
        const textMatch = st.city.includes(textQuery) || st.address.toLowerCase().includes(textQuery) || st.brand.toLowerCase().includes(textQuery);
        const fuelMatch = selectedFuelType === 'all' || st.fuels.includes(selectedFuelType);
        return textMatch && fuelMatch;
    });

    displayStations(result);
}

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('data:text/javascript;base64,' + btoa(`
            self.addEventListener('fetch', function(e) { e.respondWith(fetch(e.request)); });
        `)).catch(() => {});
    });
}

document.addEventListener('DOMContentLoaded', fetchDatabase);
