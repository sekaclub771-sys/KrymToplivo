let crimeaDatabase = [];
let currentFilterTab = 'all';
let userCoords = null;

function startCyberEngine() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                userCoords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
                console.log("GPS координаты получены:", userCoords);
                loadFuelDatabase();
            },
            (err) => {
                console.warn("GPS отклонен или недоступен:", err.message);
                loadFuelDatabase();
            },
            { enableHighAccuracy: true, timeout: 5000 }
        );
    } else {
        loadFuelDatabase();
    }
}

function loadFuelDatabase() {
    const grid = document.getElementById('cyberCardsGrid');
    if (!grid) return;
    grid.innerHTML = '<p style="text-align:center; opacity:0.4; font-size:14px; margin-top:30px;">СИНХРОНИЗАЦИЯ СЕТИ АЗС...</p>';

    fetch('data.json?v=' + Date.now())
        .then(res => {
            if (!res.ok) throw new Error("Ошибка чтения JSON файла");
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

            renderCyberCards(crimeaDatabase);
        })
        .catch(err => {
            console.error(err);
            grid.innerHTML = '<p style="text-align:center; color:#ef4444; font-size:14px; margin-top:30px;">ОШИБКА ЗАГРУЗКИ БАЗЫ ДАННЫХ.</p>';
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
    const src = source.toLowerCase();
    if (src.includes('минтопэнерго') || src.includes('официальный')) score += 20;
    if (text.includes('свободный') || text.includes('ограничений нет')) score += 20;
    if (text.includes('только по талонам')) score -= 35;
    if (text.includes('закончился')) score -= 40;
    return Math.max(5, Math.min(100, score));
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
        grid.innerHTML = '<p style="text-align:center; opacity:0.3; font-size:14px; margin-top:20px;">ЛОКАЦИИ НЕ НАЙДЕНЫ.</p>';
        return;
    }

    dataset.forEach(st => {
        const card = document.createElement('div');
        card.className = 'cyber-card';
        let clr = st.probability >= 75 ? '#22c55e' : st.probability >= 40 ? '#f59e0b' : '#ef4444';
        
        const b95 = st.fuels.includes('АИ-95') ? 'on-95' : '';
        const b92 = st.fuels.includes('АИ-92') ? 'on-92' : '';
        const bDt = st.fuels.includes('ДТ') ? 'on-dt' : '';
        
        const distHtml = st.distance !== null ? `<div class="distance-badge">📡 Дистанция: ${st.distance} км</div>` : '';
        
        card.innerHTML = `
            <div class="predict-widget">
                <div class="predict-percent" style="color: ${clr}">${st.probability}%</div>
                <div class="predict-label">Наличие</div>
            </div>
            <div class="brand-name">${st.brand}</div>
            <div class="station-geo"><span>📍 ${st.address}</span>${distHtml}</div>
            <div class="prob-container">
                <div class="prob-track">
                    <div class="prob-bar" style="width: ${st.probability}%; background: ${clr}"></div>
                </div>
            </div>
            <div class="badges-row">
                <span class="neon-badge ${b95}">АИ-95</span>
                <span class="neon-badge ${b92}">АИ-92</span>
                <span class="neon-badge ${bDt}">ДТ</span>
            </div>
            <div class="log-box">${st.terms}</div>
            <button class="navi-btn" onclick="openYandexNavigator(${st.lat}, ${st.lon})">Построить маршрут</button>
        `;
        grid.appendChild(card);
    });
}

function switchFuelTab(fuelType) {
    currentFilterTab = fuelType;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    
    let btnId = 'tab-all';
    if (fuelType === 'АИ-95') btnId = 'tab-95';
    if (fuelType === 'АИ-92' btnId = 'tab-92';
    if (fuelType === 'ДТ') btnId = 'tab-dt';
    
    const activeBtn = document.getElementById(btnId);
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
    renderCyberCards(filtered);
}

window.addEventListener('load', startCyberEngine);
