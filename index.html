<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Крым Топливо Локатор</title>
    <link rel="manifest" href="manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="КрымТопливо">
    <link rel="apple-touch-icon" href="logo.png">
    <style>
        :root {
            --cyber-bg: #05070f;
            --cyber-card: rgba(13, 18, 36, 0.75);
            --cyber-border: rgba(56, 189, 248, 0.15);
            --neon-blue: #38bdf8;
            --neon-purple: #a855f7;
            --neon-green: #22c55e;
            --neon-amber: #f59e0b;
            --text-neon: #f8fafc;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, sans-serif; }
        body { background: var(--cyber-bg); color: var(--text-neon); min-height: 100vh; padding-bottom: 60px; }
        .container { width: 92%; max-width: 540px; margin: 0 auto; }
        header { background: rgba(5, 7, 15, 0.85); backdrop-filter: blur(25px); border-bottom: 2px solid var(--cyber-border); padding: 18px 0; position: sticky; top: 0; z-index: 100; }
        .header-flex { display: flex; justify-content: space-between; align-items: center; }
        .brand-wrapper { display: flex; align-items: center; gap: 15px; }
        .crimea-flag { width: 46px; height: 28px; border-radius: 5px; display: flex; flex-direction: column; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); }
        .flag-blue { height: 16.6%; background: #0046B8; }
        .flag-white { height: 66.8%; background: #FFFFFF; }
        .flag-red { height: 16.6%; background: #D52B1E; }
        .logo-text { font-size: 24px; font-weight: 900; background: linear-gradient(to right, #ffffff, var(--neon-blue)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .control-panel { background: var(--cyber-card); border: 1px solid var(--cyber-border); border-radius: 22px; padding: 22px; margin: 25px 0; }
        input { width: 100%; background: #090c15; border: 1px solid rgba(56, 189, 248, 0.2); padding: 16px 18px; border-radius: 14px; color: white; font-size: 16px; outline: none; margin-bottom: 16px; }
        .fuel-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
        .tab-btn { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); padding: 14px 0; border-radius: 12px; color: #64748b; font-size: 14px; font-weight: 800; }
        .tab-btn.active { color: white; background: #0d1527; border-color: var(--neon-blue); }
        .map-section { background: var(--cyber-card); border: 1px solid var(--cyber-border); border-radius: 24px; padding: 12px; margin-bottom: 25px; }
        .map-title-text { font-size: 14px; font-weight: 800; text-transform: uppercase; color: var(--neon-blue); margin: 4px 0 12px 6px; }
        .map-wrapper { width: 100%; height: 300px; border-radius: 16px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); }
        iframe { width: 100%; height: 100%; border: none; }
        .grid { display: flex; flex-direction: column; gap: 20px; }
        .cyber-card { background: var(--cyber-card); border: 1px solid var(--cyber-border); border-radius: 24px; padding: 24px; position: relative; }
        .predict-widget { position: absolute; top: 22px; right: 24px; text-align: right; }
        .predict-percent { font-size: 26px; font-weight: 900; }
        .predict-label { font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; }
        .brand-name { font-size: 24px; font-weight: 900; color: white; margin-bottom: 4px; }
        .station-geo { font-size: 14px; color: #64748b; margin-bottom: 18px; display: flex; flex-direction: column; gap: 4px; }
        .distance-badge { display: inline-flex; align-items: center; background: rgba(168,85,247,0.12); border: 1px solid rgba(168,85,247,0.3); color: #e9d5ff; font-weight: 700; font-size: 12px; padding: 4px 10px; border-radius: 6px; }
        .prob-container { margin-bottom: 18px; }
        .prob-track { height: 6px; background: rgba(255,255,255,0.05); border-radius: 10px; overflow: hidden; }
        .prob-bar { height: 100%; width: 0%; border-radius: 10px; transition: width 0.8s ease; }
        .badges-row { display: flex; gap: 8px; margin-bottom: 18px; }
        .neon-badge { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); color: #475569; padding: 6px 12px; border-radius: 8px; font-size: 13px; font-weight: 800; }
        .neon-badge.on-95 { background: rgba(56,189,248,0.1); border-color: rgba(56,189,248,0.4); color: var(--neon-blue); }
        .neon-badge.on-92 { background: rgba(245,158,11,0.1); border-color: rgba(245,158,11,0.4); color: var(--neon-amber); }
        .neon-badge.on-dt { background: rgba(34,197,94,0.1); border-color: rgba(34,197,94,0.4); color: var(--neon-green); }
        .log-box { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.04); padding: 14px; border-radius: 12px; font-size: 14px; color: #94a3b8; line-height: 1.4; margin-bottom: 16px; }
        .navi-btn { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; background: linear-gradient(135deg, #ff5c00 0%, #ff9000 100%); border: none; padding: 15px; border-radius: 14px; color: white; font-size: 15px; font-weight: 800; }
        .navi-icon { width: 18px; height: 18px; fill: white; }
    </style>
</head>
<body>
    <header>
        <div class="container header-flex">
            <div class="brand-wrapper"><div class="crimea-flag"><div class="flag-blue"></div><div class="flag-white"></div><div class="flag-red"></div></div><div class="logo-text">Крым Топливо</div></div>
        </div>
    </header>
    <main class="container">
        <section class="control-panel">
            <input type="text" id="searchInput" placeholder="Поиск локации..." onkeyup="processFilters()">
            <div class="fuel-grid">
                <button class="tab-btn active" id="tab-all" onclick="switchFuelTab('all')">Все</button>
                <button class="tab-btn" id="tab-95" onclick="switchFuelTab('АИ-95')">95</button>
                <button class="tab-btn" id="tab-92" onclick="switchFuelTab('АИ-92')">92</button>
                <button class="tab-btn" id="tab-dt" onclick="switchFuelTab('ДТ')">ДТ</button>
            </div>
        </section>
        <section class="map-section">
            <div class="map-title-text">🗺️ Монитор АЗС Крым</div>
            <div class="map-wrapper"><iframe src="https://yandex.ru" allowfullscreen="true"></iframe></div>
        </section>
        <div class="grid" id="cyberCardsGrid"></div>
    </main>
    <script src="script.js"></script>
</body>
</html>
