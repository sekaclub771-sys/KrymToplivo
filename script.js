let crimeaDatabase = [];
let currentFilterTab = 'all';
let userCoords = null;

function startCyberEngine() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                userCoords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
                loadFuelDatabase();
            },
            () => { loadFuelDatabase(); },
            { enableHighAccuracy: true, timeout: 5000 }
        );
    } else {
        loadFuelDatabase();
    }
}

function loadFuelDatabase() {
    const grid = document.getElementById('cyberCardsGrid');
    if (!grid) return;
    grid.innerHTML = '<p style="text-align:center; opacity:0.4; font-size:14px; margin-top:30px;">ЗАГРУЗКА БОРТОВЫХ СИСТЕМ...</p>';

    fetch('data.json?v=' + Date.now())
        .then(res => {
            if (!res.ok) throw new Error("JSON Error");
            return res.json();
        })
        .then(rawData => {
            crimeaDatabase = rawData.map(st => {
                const probability = calculateProbability(st.fuels, st.source, st.terms);
                const coords = st.lat && st.lon ? { lat: st.lat, lon: st.lon } : fallbackCoordinates(st.city);
                let distance = userCoords ? calculateHaversineDistance(userCoords.lat, userCoords.lon, coords.lat, coords.lon) : null;
                return { ...st, probability, lat: coords.lat, lon: coords.lon, distance };
            });

            if (userCoords) {
                crimeaDatabase.sort((a, b) => {
                    if (a.fuels.length === 0) return 1;
                    if (b.fuels.length === 0) return -1;
                    return a.distance - b.distance;
                });
            } else {
                crimeaDatabase.sort((a, b) => b.probability - a.probability);
            }

            renderSummaryDashboard(crimeaDatabase);
            renderCyberCards(crimeaDatabase);
        })
        .catch(err => {
            console.error(err);
            grid.innerHTML = '<p style="text-align:center; color:#f87171; font-size:14px; margin-top:30px;">СБОЙ СИНХРОНИЗАЦИИ БАЗЫ.</p>';
        });
}

function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return parseFloat((R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))).toFixed(1));
}

function calculateProbability(fuels, source, terms) {
    if (!fuels || fuels.length === 0) return 0;
    let score = 50;
    const text = terms.toLowerCase();
    if (source.toLowerCase().includes('официальный') || source.toLowerCase().includes('минтопэнерго')) score += 25;
    if (text.includes('свободный') || text.includes('ограничений нет')) score += 25;
    if (text.includes('очередь') || text.includes('талонам')) score -= 20;
    if (text.includes('закончился') || text.includes('нет в наличии')) score -= 45;
    return Math.max(5, Math.min(100, score));
}

function renderSummaryDashboard(dataset) {
    let ok = 0, warn = 0, alert = 0;
    dataset.forEach(st => {
        if (st.probability >= 70) ok++;
        else if (st.probability >= 30) warn++;
        else alert++;
    });
    const eOk = document.getElementById('sum-ok');
    const eWarn = document.getElementById('sum-warn');
    const eAlert = document.getElementById('sum-alert');
    if (eOk) eOk.innerText = ok;
    if (eWarn) eWarn.innerText = warn;
    if (eAlert) eAlert.innerText = alert;
}

function openYandexNavigator(lat, lon) {
    window.location.href = `yandexnavi://build_route_on_map?lat_to=${lat}&lon_to=${lon}`;
    setTimeout(() => { window.open(`https://yandex.ru{lat},${lon}&rtt=auto`, '_blank'); }, 500);
}

function fallbackCoordinates(city) {
    const points = {
        'симферополь': { lat: 44.952117, lon: 34.102417 },
        'севастополь': { lat: 44.588837, lon: 33.522402 },
        'ялта': { lat: 44.498114, lon: 34.168541 },
        'керчь': { lat: 45.356219, lon: 36.467371 },
        'евпатория': { lat: 45.198144, lon: 33.364024 },
        'феодосия': { lat: 45.031737, lon: 35.382632 },
        'таврида': { lat: 45.054452, lon: 34.603351 }
    };
    return points[city] || { lat: 44.952117, lon: 34.102417 };
}

function renderCyberCards(dataset) {
    const grid = document.getElementById('cyberCardsGrid');
    if (!grid) return;
    grid.innerHTML = '';
    if (dataset.length === 0) {
        grid.innerHTML = '<p style="text-align:center; opacity:0.3; font-size:13px; padding:20px;">ЛОКАЦИИ ПОД ПАРАМЕТРЫ НЕ НАЙДЕНЫ</p>';
        return;
    }
    dataset.forEach(st => {
        const card = document.createElement('div');
        card.className = 'cyber-card';
        let clr = st.probability >= 70 ? 'var(--neon-green)' : st.probability >= 30 ? 'var(--neon-amber)' : 'var(--neon-red)';
        const b95 = st.fuels.includes('АИ-95') ? 'active-95' : '';
        const b92 = st.fuels.includes('АИ-92') ? 'active-92' : '';
        const bDt = st.fuels.includes('ДТ') ? 'active-dt' : '';
        const distHtml = st.distance !== null ? `<div class="geo-pill">📡 Дистанция: ${st.distance} км</div>` : '';

        card.innerHTML = `
            <div class="status-container">
                <div class="status-val" style="color: ${clr}; text-shadow: 0 0 10px ${clr}30;">${st.probability}%</div>
                <div class="status-lbl">Наличие</div>
            </div>
            <div class="station-title">${st.brand}</div>
            <div class="station-address"><span>📍 ${st.address}</span>${distHtml}</div>
            <div class="bar-container">
                <div class="bar-track"><div class="bar-fill" style="width: ${st.probability}%; background: ${clr}; box-shadow: 0 0 8px ${clr}60;"></div></div>
            </div>
            <div class="badges-list">
                <span class="badge-node ${b95}">АИ-95</span>
                <span class="badge-node ${b92}">АИ-92</span>
                <span class="badge-node ${bDt}">ДТ</span>
            </div>
            <div class="info-panel">${st.terms}</div>
            <button class="route-button" onclick="openYandexNavigator(${st.lat}, ${st.lon})">Проложить маршрут в Навигатор</button>
        `;
        grid.appendChild(card);
    });
}

function switchFuelTab(fuelType) {
    currentFilterTab = fuelType;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    let targetId = 'btn-all';
    if (fuelType === 'АИ-95') targetId = 'btn-95';
    if (fuelType === 'АИ-92') targetId = 'btn-92';
    if (fuelType === 'ДТ') targetId = 'btn-dt';
    const activeBtn = document.getElementById(targetId);
    if (activeBtn) activeBtn.classList.add('active');
    processFilters();
}

function processFilters() {
    const searchInput = document.getElementById('searchInput');
    const query = searchInput ? searchInput.value.toLowerCase() : '';
    const filtered = crimeaDatabase.filter(st => {
        const searchMatch = st.city.includes(query) || st.address.toLowerCase().includes(query) || st.brand.toLowerCase().includes(query);
        const fuelMatch = currentFilterTab === 'all' || st.fuels.includes(currentFilterTab);
        return searchMatch && fuelMatch;
    });
    renderSummaryDashboard(filtered);
    renderCyberCards(filtered);
}

window.addEventListener('load', startCyberEngine);
