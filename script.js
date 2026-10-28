let crimeaDatabase = [];
let currentFilterTab = 'all';
let userCoords = null; // Переменная для хранения координат смартфона

async function startCyberEngine() {
    // 1. Пробуем запросить геопозицию пользователя прямо при старте приложения
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                userCoords = {
                    lat: position.coords.latitude,
                    lon: position.coords.longitude
                };
                console.log("Геопозиция успешно получена:", userCoords);
                loadFuelDatabase(); // Загружаем базу после получения GPS
            },
            (error) => {
                console.warn("Доступ к GPS отклонен водителем:", error.message);
                loadFuelDatabase(); // Всё равно загружаем базу, но без расчета расстояний
            },
            { enableHighAccuracy: true, timeout: 5000 }
        );
    } else {
        loadFuelDatabase();
    }
}

async function loadFuelDatabase() {
    const grid = document.getElementById('cyberCardsGrid');
    grid.innerHTML = '<p style="text-align:center; opacity:0.4; font-size:14px; letter-spacing:1px; margin-top:30px;">ЗАГРУЗКА ИИ-МАТРИЦЫ ТОПЛИВА...</p>';
    
    try {
        const res = await fetch('data.json?v=' + Date.now());
        const rawData = await res.json();
        
        crimeaDatabase = rawData.map(st => {
            const probability = calculateProbability(st.fuels, st.source, st.terms);
            const coords = st.lat && st.lon ? { lat: st.lat, lon: st.lon } : fallbackCoordinates(st.city);
            
            // Если координаты водителя доступны, рассчитываем точную дистанцию в км
            let distance = null;
            if (userCoords) {
                distance = calculateHaversineDistance(userCoords.lat, userCoords.lon, coords.lat, coords.lon);
            }

            return { ...st, probability, lat: coords.lat, lon: coords.lon, distance };
        });
        
        // Мощная сортировка: если GPS доступен, автоматически поднимаем наверх самые БЛИЗКИЕ к водителю АЗС с топливом
        if (userCoords) {
            crimeaDatabase.sort((a, b) => {
                if (a.fuels.length === 0) return 1;  // Пустые заправки кидаем в самый низ
                if (b.fuels.length === 0) return -1;
                return a.distance - b.distance;     // Сортировка от ближних к дальним
            });
        } else {
            crimeaDatabase.sort((a, b) => b.probability - a.probability);
        }
        
        renderCyberCards(crimeaDatabase);
    } catch (err) {
        console.error("Ошибка матричного движка:", err);
        grid.innerHTML = '<p style="text-align:center; color:#ef4444; font-size:14px;">КРИТИЧЕСКАЯ ОШИБКА СИНХРОНИЗАЦИИ БАЗЫ.</p>';
    }
}

/**
 * 📐 МАТЕМАТИЧЕСКАЯ ФОРМУЛА ХАВЕРСИНА
 * Считает точное расстояние между двумя точками на сфере (Земле) по широте и долготе
 */
function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Радиус Земли в километрах
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return parseFloat((R * c).toFixed(1)); // Возвращаем расстояние с округлением до 1 знака (например, 14.5 км)
}

function calculateProbability(fuels, source, terms) {
    if (!fuels || fuels.length === 0) return 0;
    let score = 50;
    const text = terms.toLowerCase();
    const src = source.toLowerCase();

    if (src.includes('минтопэнерго') || src.includes('официальный')) score += 20;
    if (src.includes('мониторинг сайта')) score += 15;
    if (src.includes('чат') || src.includes('народный')) score += 5;

    if (text.includes('свободный') || text.includes('ограничений нет')) score += 20;
    if (text.includes('очередь отсутствует') || text.includes('без очередей')) score += 10;
    if (text.includes('бензовоз был') || text.includes('завезли')) score += 15;
    
    if (text.includes('только по талонам') || text.includes('топливным картам')) score -= 35;
    if (text.includes('закончился') || text.includes('ожидают')) score -= 40;

    return Math.max(5, Math.min(100, score));
}

function openYandexNavigator(lat, lon) {
    const naviUrl = `yandexnavi://build_route_on_map?lat_to=${lat}&lon_to=${lon}`;
    const webUrl = `https://yandex.ru{lat},${lon}&rtt=auto`;
    const start = Date.now();
    window.location.href = naviUrl;
    setTimeout(() => { if (Date.now() - start < 600) window.open(webUrl, '_blank'); }, 500);
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
    grid.innerHTML = '';

    if (dataset.length === 0) {
        grid.innerHTML = '<p style="text-align:center; opacity:0.3; font-size:14px; margin-top:20px;">ЛОКАЦИИ ПОД ДАННЫЙ ПАРАМЕТР НЕ НАЙДЕНЫ.</p>';
        return;
    }

    dataset.forEach(st => {
        const card = document.createElement('div');
        card.className = 'cyber-card';

        let colorClass = '#ef4444';
        if (st.probability >= 40 && st.probability < 75) colorClass = '#f59e0b';
        if (st.probability >= 75) colorClass = '#22c55e';

        const badge95 = st.fuels.includes('АИ-95') ? 'on-95' : '';
        const badge92 = st.fuels.includes('АИ-92') ? 'on-92' : '';
        const badgeDt = st.fuels.includes('ДТ') ? 'on-dt' : '';

        // Генерируем плашку с расстоянием, только если координаты пользователя определены
        const distanceHtml = st.distance !== null ? `<div class="distance-badge">📡 Дистанция: ${st.distance} км</div>` : '';

        card.innerHTML = `
            <div class="predict-widget">
                <div class="predict-percent" style="color: ${colorClass}; text-shadow: 0 0 10px ${colorClass}40;">${st.probability}%</div>
                <div class="predict-label">Наличие</div>
            </div>
            <div class="brand-name">${st.brand}</div>
            <div class="station-geo">
                <span>📍 ${st.address}</span>
                ${distanceHtml}
            </div>
            
            <div class="prob-container">
                <div class="prob-track">
                    <div class="prob-bar" style="width: ${st.probability}%; background: ${colorClass}; box-shadow: 0 0 8px ${colorClass};"></div>
                </div>
            </div>

            <div class="badges-row">
                <span class="neon-badge ${badge95}">АИ-95</span>
                <span class="neon-badge ${badge92}">АИ-92</span>
                <span class="neon-badge ${badgeDt}">ДТ</span>
            </div>
            <div class="log-box">${st.terms}</div>
            
            <button class="navi-btn" onclick="openYandexNavigator(${st.lat}, ${st.lon})">
                <svg class="navi-icon" viewBox="0 0 24 24">
                    <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
                </svg>
                Построить маршрут в Навигатор
            </button>
        `;
        grid.appendChild(card);
    });
}

function switchFuelTab(fuelType) {
    currentFilterTab = fuelType;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + (fuelType === 'all' ? 'all' : fuelType === 'АИ-95' ? '95' : fuelType === 'АИ-92' ? '92' : 'dt')).classList.add('active');
    processFilters();
}

function processFilters() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    const filtered = crimeaDatabase.filter(st => {
        const searchMatch = st.city.includes(query) || st.address.toLowerCase().includes(query) || st.brand.toLowerCase().includes(query);
        const fuelMatch = currentFilterTab === 'all' || st.fuels.includes(currentFilterTab);
        return searchMatch && fuelMatch;
    });
    renderCyberCards(filtered);
}

// Запускаем движок с опросом геопозиции при старте
document.addEventListener('DOMContentLoaded', startCyberEngine);
