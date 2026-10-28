let crimeaDatabase = [];
let currentFilterTab = 'all';

async function loadCyberEngine() {
    const grid = document.getElementById('cyberCardsGrid');
    grid.innerHTML = '<p style="text-align:center; opacity:0.4; font-size:14px; letter-spacing:1px; margin-top:30px;">ЗАГРУЗКА ИИ-МАТРИЦЫ ТОПЛИВА...</p>';
    
    try {
        const res = await fetch('data.json?v=' + Date.now());
        const rawData = await res.json();
        
        // Модифицируем базу данных: прогоняем каждую АЗС через математическую модель предсказания процентов
        crimeaDatabase = rawData.map(st => {
            const probability = calculateProbability(st.fuels, st.source, st.terms);
            return { ...st, probability };
        });
        
        // Сортируем заправки: сначала показываем те, где процент наличия бензина выше
        crimeaDatabase.sort((a, b) => b.probability - a.probability);
        
        renderCyberCards(crimeaDatabase);
    } catch (err) {
        console.error("Ошибка матричного движка:", err);
        grid.innerHTML = '<p style="text-align:center; color:#ef4444; font-size:14px;">КРИТИЧЕСКАЯ ОШИБКА СИНХРОНИЗАЦИИ БАЗЫ.</p>';
    }
}

/**
 * 🧠 МАТЕМАТИЧЕСКАЯ МОДЕЛЬ ВЕРОЯТНОСТИ (Процент наличия топлива)
 * Рассчитывает надежность точки исходя из количества источников и контекста текста
 */
function calculateProbability(fuels, source, terms) {
    if (!fuels || fuels.length === 0) return 0; // Топлива нет вообще — 0%
    
    let score = 50; // Базовый уровень уверенности (50%)
    const text = terms.toLowerCase();
    const src = source.toLowerCase();

    // 1. Оценка по надежности первоисточника информации
    if (src.includes('минтопэнерго') || src.includes('официальный')) score += 20; // Гос-данные дают +20%
    if (src.includes('мониторинг сайта')) score += 15;                             // Прямой API сайта дает +15%
    if (src.includes('чат') || src.includes('народный')) score += 5;                // Сообщения водителей дают +5% (требуют проверки)

    // 2. Семантический анализ контекста текста (Ищем триггеры)
    if (text.includes('свободный') || text.includes('ограничений нет')) score += 20;
    if (text.includes('очередь отсутствует') || text.includes('без очередей')) score += 10;
    if (text.includes('бензовоз был') || text.includes('завезли')) score += 15;
    
    // Понижающие коэффициенты (Штрафы)
    if (text.includes('только по талонам') || text.includes('топливным картам')) score -= 35;
    if (text.includes('закончился') || text.includes('ожидают')) score -= 40;
    if (text.includes('очередь около') || text.includes('очередь 10 машин')) score -= 10;
    if (text.includes('временно')) score -= 15;

    // Ограничиваем рамки математического процента от 5% до 100%
    return Math.max(5, Math.min(100, score));
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

        // Определяем цвет индикатора вероятности
        let colorClass = '#ef4444'; // Красный (0-39%)
        if (st.probability >= 40 && st.probability < 75) colorClass = '#f59e0b'; // Оранжевый (40-74%)
        if (st.probability >= 75) colorClass = '#22c55e'; // Зеленый (75-100%)

        const badge95 = st.fuels.includes('АИ-95') ? 'on-95' : '';
        const badge92 = st.fuels.includes('АИ-92') ? 'on-92' : '';
        const badgeDt = st.fuels.includes('ДТ') ? 'on-dt' : '';

        card.innerHTML = `
            <div class="predict-widget">
                <div class="predict-percent" style="color: ${colorClass}; text-shadow: 0 0 10px ${colorClass}40;">${st.probability}%</div>
                <div class="predict-label">Вероятность</div>
            </div>
            <div class="brand-name">${st.brand}</div>
            <div class="station-geo">📍 ${st.address}</div>
            
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

// Фоновый Service Worker для мобильного PWA статуса
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('data:text/javascript;base64,' + btoa(`
            self.addEventListener('fetch', function(e) { e.respondWith(fetch(e.request)); });
        `)).catch(() => {});
    });
}

document.addEventListener('DOMContentLoaded', loadCyberEngine);
