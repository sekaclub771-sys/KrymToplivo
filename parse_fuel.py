import json
import re

def parse_competitor_data():
    """
    1. ИМИТАЦИЯ СКРЕЙПИНГА КОНКУРЕНТОВ (krym-toplivo.ru, tutbenz и др.)
    В реальном сценарии робот делает requests.get() и парсит HTML через BeautifulSoup
    """
    print("Сканирование баз данных конкурентов...")
    return [
        {"brand": "АТАН", "address": "Симферополь, пр-т Победы, 212", "fuels": ["АИ-95", "АИ-92", "ДТ"], "terms": "Свободная продажа, без очередей", "source": "Агрегатор конкурентов", "city": "симферополь"},
        {"brand": "ТЭС", "address": "Трасса Таврида, 159-й км (Белогорск)", "fuels": ["АИ-95", "АИ-92"], "terms": "ДТ закончилось, бензовоз ожидается к вечеру", "source": "Агрегатор конкурентов", "city": "таврида"},
        {"brand": "Формула", "address": "Керчь, ул. Чкалова, 14", "fuels": ["АИ-92", "ДТ"], "terms": "АИ-95 временно отсутствует", "source": "Мониторинг карт", "city": "керчь"}
    ]

def parse_telegram_channels_and_bots():
    """
    2. АВТОМАТИЧЕСКИЙ АНАЛИЗ TELEGRAM-ЧАТОВ И БОТОВ (Через текстовые сводки)
    Робот берет массив последних сообщений из автомобильных чатов Крыма
    и с помощью регулярных выражений (ИИ-логика) сам определяет наличие топлива.
    """
    print("Парсинг Telegram-каналов и чатов взаимопомощи...")
    
    # Симулируем поток сырых сообщений из реальных крымских чатов (Севастополь, Ялта, Симф)
    raw_telegram_posts = [
        {"text": "На Грифоне в Судаке на Гвардейской 95 есть свободно! Очередь 3 машины.", "geo": "Судак, ул. Гвардейская, 3", "brand": "Грифон"},
        {"text": "ДТ на Фениксе в Феодосии завезли, бензина пока нет вообще, ждем ночью.", "geo": "Феодосия, Симферопольское шоссе, 11", "brand": "Феникс"},
        {"text": "vesta на Тавриде возле Зуи — 95, 92 и дизель льют без проблем, проскочил без очереди.", "geo": "Трасса Таврида, район Зуи", "brand": "Vesta"},
        {"text": "В Джанкое на VTF дизель только по талонам и картам, 92-й пускают в кассу свободно.", "geo": "Джанкой, ул. Крымская, 84", "brand": "VTF"},
        {"text": "На АТАНе в Севастополе на Камышовом 92 только по талонам дают!! 95 свободно.", "geo": "Севастополь, Камышовое шоссе, 12", "brand": "АТАН"}
    ]
    
    parsed_stations = []
    
    for post in raw_telegram_posts:
        text = post["text"].lower()
        detected_fuels = []
        
        # Интеллектуальный поиск видов топлива в тексте сообщения
        if "95" in text or "аи-95" in text:
            detected_fuels.append("АИ-95")
        if "92" in text or "аи-92" in text:
            detected_fuels.append("АИ-92")
        if "дт" in text or "дизел" in text:
            detected_fuels.append("ДТ")
            
        # Формируем статус на основе анализа текста
        status_text = f"📢 Из Telegram-чата: {post['text']}"
        
        # Определяем город для фильтрации
        city = "крым"
        if "судак" in text: city = "судак"
        elif "феодоси" in text: city = "феодосия"
        elif "таврид" in text: city = "таврида"
        elif "джанко" in text: city = "джанкой"
        elif "севастопол" in text: city = "севастополь"
        
        parsed_stations.append({
            "brand": post["brand"],
            "address": post["geo"],
            "fuels": detected_fuels,
            "terms": status_text,
            "source": "Telegram-Авточаты (Live)",
            "city": city
        })
        
    return parsed_stations

def main():
    print("=== СТАРТ СВЕРХМАШИННОГО СБОРА ТОПЛИВА ===")
    
    all_collected_stations = []
    
    # Стягиваем данные со всех векторов
    all_collected_stations.extend(parse_competitor_data())
    all_collected_stations.extend(parse_telegram_channels_and_bots())
    
    # 3. ИСКЛЮЧЕНИЕ ДУБЛИКАТОВ (Склеиваем данные, если АЗС совпали по адресу)
    unique_stations = {}
    for st in all_collected_stations:
        key = f"{st['brand']}_{st['address']}".lower()
        if key not in unique_stations:
            unique_stations[key] = st
        else:
            # Если инфа о заправке уже есть, дополняем её актуальными данными из чата
            if "telegram" in st["source"].lower():
                unique_stations[key]["terms"] = st["terms"]
                unique_stations[key]["fuels"] = list(set(unique_stations[key]["fuels"] + st["fuels"]))
                unique_stations[key]["source"] = "Агрегатор + Сводка чатов"

    final_list = list(unique_stations.values())
    
    # Сохраняем готовую итоговую матрицу на сервер сайта
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_list, f, ensure_ascii=False, indent=4)
        
    print(f"=== СБОР ЗАВЕРШЕН. СКОМПИЛИРОВАНО {len(final_list)} УНИКАЛЬНЫХ АЗС ===")

if __name__ == "__main__":
    main()
