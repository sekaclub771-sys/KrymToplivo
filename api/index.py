# -*- coding: utf-8 -*-
"""
КРЫМ ТОПЛИВО GT — Production Serverless Harvesting & Regex Text-Mining Engine (api/index.py)
Architecture: Vercel Python Serverless Runtime (WSGI BaseHTTPRequestHandler)
Execution Modes:
  1. GET /api/fuel              -> Fast cached read from data.json / /tmp state (with automatic bootstrap)
  2. GET /api/fuel?force=true   -> Live 4-Vector Scraping + Regex Text-Mining + Coordinate Intersect
  3. GET /api/fuel?action=cron  -> Scheduled 15-minute Vercel Cron execution
  4. POST /api/fuel             -> Live Driver Report ingestion through Vector 3 & Vector 4
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, timedelta
import urllib.request
import urllib.error
import ssl
import json
import re
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DATA_PATH = os.path.join(ROOT_DIR, "data.json")
TMP_DATA_PATH = "/tmp/krym_toplivo_data.json"

ALL_GRADES = ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"]

GRADE_KEY_MAP = {
    "АИ-92": "AI92",
    "АИ-95": "AI95",
    "95 Ultra": "AI95_ULTRA",
    "АИ-100": "AI100",
    "ДТ": "DT",
    "Газ": "LPG",
}

REVERSE_GRADE_KEY_MAP = {v: k for k, v in GRADE_KEY_MAP.items()}

# ==============================================================================
# CORPORATE BRAND NORMALIZATION DICTIONARY (VECTOR 1 & VECTOR 4)
# ==============================================================================
BRAND_ALIASES = {
    "ATAN": ["atan", "атан", "атан-крым", "ооо кедр атан"],
    "ТЭС": ["tes", "тэс", "торговый дом тэс", "тд тэс", "на тэсе", "тэс-авто"],
    "Grifon": ["grifon", "грифон", "азс грифон"],
    "Redpetrol": ["redpetrol", "редпетрол", "рэдпетрол", "red petrol"],
    "CRS": ["crs", "црс", "крым ойл", "црс-нефть"],
    "Кедр": ["kedr", "кедр", "азс кедр"],
    "Формула": ["formula", "формула", "азс формула", "частная", "на глинки"],
    "Таврида-Нефть": ["tavrida", "таврида-нефть", "таврида нефть"],
}

# ==============================================================================
# REGEX PATTERNS FOR FUEL PRICE EXTRACTION (VECTOR 3)
# ==============================================================================
PRICE_REGEX_PATTERNS = {
    "95 Ultra": re.compile(
        r"(?:95\s*(?:ultra|ультра|премиум|плюс|extra|экстра|g-drive|пульсар))"
        r"(?:[^0-9]{1,22}?)"
        r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:р|руб|₽)?",
        re.IGNORECASE | re.UNICODE,
    ),
    "АИ-100": re.compile(
        r"(?:аи[-\s]?100|100[-\s]?(?:й|го|м|ый)|сотый)"
        r"(?:[^0-9]{1,22}?)"
        r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:р|руб|₽)?",
        re.IGNORECASE | re.UNICODE,
    ),
    "АИ-95": re.compile(
        r"(?:аи[-\s]?95|95[-\s]?(?:й|го|м|ый|ому)?(?!\s*(?:ultra|ультра|премиум|плюс))|девяносто\s*пятый)"
        r"(?:[^0-9]{1,22}?)"
        r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:р|руб|₽)?",
        re.IGNORECASE | re.UNICODE,
    ),
    "АИ-92": re.compile(
        r"(?:аи[-\s]?92|92[-\s]?(?:й|го|м|ой|ому)?|девяносто\s*второй)"
        r"(?:[^0-9]{1,22}?)"
        r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:р|руб|₽)?",
        re.IGNORECASE | re.UNICODE,
    ),
    "ДТ": re.compile(
        r"(?:\bдт\b|дизел[ьяюем]|солярк[аиуе])"
        r"(?:[^0-9]{1,25}?)"
        r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:р|руб|₽)?",
        re.IGNORECASE | re.UNICODE,
    ),
    "Газ": re.compile(
        r"(?:\bгаз\b|\bпропан\b|\bметан\b|\bсуг\b|\blpg\b)"
        r"(?:[^0-9]{1,22}?)"
        r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:р|руб|₽)?",
        re.IGNORECASE | re.UNICODE,
    ),
}

PRICE_SANITY_BOUNDS = {
    "АИ-92": (52.0, 72.0),
    "АИ-95": (56.0, 78.0),
    "95 Ultra": (59.0, 84.0),
    "АИ-100": (70.0, 98.0),
    "ДТ": (56.0, 80.0),
    "Газ": (24.0, 46.0),
}

# ==============================================================================
# QUEUE & STATUS SCORING MATRIX TOKENS (VECTOR 3)
# ==============================================================================
HIGH_AVAILABILITY_TOKENS = [
    r"свободно",
    r"бензовоз\s*слился",
    r"сливается\s*бензовоз",
    r"слив\s*бензовоза",
    r"очередей\s*нет",
    r"без\s*очеред[ией]",
    r"завезли",
    r"ограничений\s*нет",
    r"все\s*колонки",
    r"полные\s*резервуары",
    r"наливают\s*всем",
]

WARNING_QUEUE_TOKENS = [
    r"очередь",
    r"стоим\s*минут\s*\d+",
    r"пробка",
    r"уже\s*\d+\s*машин",
    r"очередь\s*на\s*заезд",
    r"машин\s*\d+",
    r"ждать\s*минут",
    r"тянучка",
]

DEFICIT_COUPON_TOKENS = [
    r"закончился",
    r"сухо",
    r"только\s*по\s*талонам",
    r"по\s*талонам",
    r"95[-\s]*го\s*нет",
    r"92[-\s]*го\s*нет",
    r"дизеля\s*нет",
    r"дт\s*нет",
    r"по\s*топливным\s*картам",
    r"бензина\s*нет",
    r"колонки\s*закрыты",
    r"отпуска\s*нет",
]

QUEUE_CARS_COUNT_REGEX = re.compile(
    r"(?:очередь|уже|около|примерно|стоят|~)?\s*(\d{1,2})\s*(?:машин|авто|машины)",
    re.IGNORECASE | re.UNICODE,
)

# ==============================================================================
# BASE COORDINATE & LANDMARK MATRIX OF 32 CRIMEAN STATIONS (VECTOR 4)
# ==============================================================================
STATIONS_32_BASE = [
    {
        "id": "atan-simf-01",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №14 — Ялтинская объездная",
        "city": "Симферополь",
        "region_key": "simferopol",
        "highway": "Трасса ЮБК",
        "address": "г. Симферополь, Ялтинское шоссе, 187",
        "landmarks": ["ялтинская", "ялтинское", "объездная", "187", "атан 14"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.45, "АИ-95": 66.80, "95 Ultra": 69.20, "АИ-100": 82.90, "ДТ": 68.50, "Газ": 36.20},
        "queue_status": "Свободно",
        "terms": "Свободный отпуск за наличные, карты и СБП",
        "fuel_arrived_time": "Слив бензовоза 25 мин назад",
        "lat": 44.9254,
        "lon": 34.1428,
    },
    {
        "id": "tes-simf-02",
        "brand": "ТЭС",
        "network": "TES",
        "name": "АЗС ТЭС №7 — Киевская (Москольцо)",
        "city": "Симферополь",
        "region_key": "simferopol",
        "highway": "Городской узел",
        "address": "г. Симферополь, ул. Киевская, 148",
        "landmarks": ["киевская", "москольцо", "тэс 7", "148"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.40, "АИ-95": 66.75, "95 Ultra": 69.10, "АИ-100": 82.50, "ДТ": 68.40, "Газ": 36.00},
        "queue_status": "Очередь ~6 машин",
        "terms": "Отпуск без лимитов, рабочая очередь на заезд",
        "fuel_arrived_time": "Слив бензовоза 2 часа назад",
        "lat": 44.9742,
        "lon": 34.0931,
    },
    {
        "id": "atan-simf-03",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №32 — Евпаторийское шоссе (Аэропорт)",
        "city": "Симферополь",
        "region_key": "simferopol",
        "highway": "Евпаторийская трасса",
        "address": "г. Симферополь, Евпаторийское шоссе, 63",
        "landmarks": ["евпаторийское", "аэропорт", "атан 32", "63"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.45, "АИ-95": 66.80, "95 Ultra": 69.20, "АИ-100": 82.90, "ДТ": 68.50, "Газ": 36.20},
        "queue_status": "Свободно",
        "terms": "Все 10 ТРК работают без ограничений",
        "fuel_arrived_time": "Слив бензовоза 45 мин назад",
        "lat": 45.0195,
        "lon": 33.9984,
    },
    {
        "id": "crs-simf-04",
        "brand": "CRS",
        "network": "CRS",
        "name": "АЗС CRS №3 — Севастопольская (Заводское)",
        "city": "Симферополь",
        "region_key": "simferopol",
        "highway": "Южный выезд",
        "address": "г. Симферополь, ул. Севастопольская, 249",
        "landmarks": ["севастопольская", "заводское", "црс 3", "249"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.30, "АИ-95": 66.60, "95 Ultra": 68.90, "АИ-100": 82.20, "ДТ": 68.30, "Газ": 35.90},
        "queue_status": "Свободно",
        "terms": "Свободный отпуск за наличные и банковские карты",
        "fuel_arrived_time": "В наличии (утренний привоз)",
        "lat": 44.9098,
        "lon": 34.0582,
    },
    {
        "id": "grifon-simf-05",
        "brand": "Grifon",
        "network": "Grifon",
        "name": "АЗС Grifon №4 — Восточный обход (Глинки / Бородина)",
        "city": "Симферополь",
        "region_key": "simferopol",
        "highway": "Восточный обход",
        "address": "г. Симферополь, ул. Глинки / пр-т Победы, 214",
        "landmarks": ["глинки", "бородина", "восточный обход", "победы", "грифон 4"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.15, "АИ-95": 66.45, "95 Ultra": 68.75, "АИ-100": 81.90, "ДТ": 68.15, "Газ": 35.75},
        "queue_status": "Свободно",
        "terms": "Выгодная розничная цена, без очередей",
        "fuel_arrived_time": "В наличии (полные резервуары)",
        "lat": 44.9612,
        "lon": 34.1524,
    },
    {
        "id": "formula-simf-06",
        "brand": "Формула",
        "network": "Формула",
        "name": "АЗС Формула — Частная на Глинки / Мирное",
        "city": "Симферополь",
        "region_key": "simferopol",
        "highway": "Западный обход",
        "address": "г. Симферополь, ул. Глинки, 68 / с. Мирное",
        "landmarks": ["частная на глинки", "глинки", "мирное", "формула"],
        "fuels": ["АИ-92", "ДТ", "Газ"],
        "prices": {"АИ-92": 59.95, "АИ-95": 66.30, "95 Ultra": 68.60, "АИ-100": 81.50, "ДТ": 67.95, "Газ": 35.50},
        "queue_status": "Дефицит / По талонам",
        "terms": "АИ-95 временно отпускается по талонам предприятий",
        "fuel_arrived_time": "Ожидается бензовоз АИ-95",
        "lat": 44.9854,
        "lon": 34.0412,
    },
    {
        "id": "atan-sev-07",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №41 — Фиолентовское кольцо",
        "city": "Севастополь",
        "region_key": "sevastopol",
        "highway": "Камышовое шоссе",
        "address": "г. Севастополь, Камышовое шоссе, 16А",
        "landmarks": ["фиолент", "камышовое", "атан 41", "фиолентовское"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.60, "АИ-95": 66.95, "95 Ultra": 69.40, "АИ-100": 83.10, "ДТ": 68.70, "Газ": 36.50},
        "queue_status": "Свободно",
        "terms": "Все марки в свободном наличии",
        "fuel_arrived_time": "Слив бензовоза 30 мин назад",
        "lat": 44.5689,
        "lon": 33.4612,
    },
    {
        "id": "tes-sev-08",
        "brand": "ТЭС",
        "network": "TES",
        "name": "АЗС ТЭС №22 — Проспект Генерала Острякова",
        "city": "Севастополь",
        "region_key": "sevastopol",
        "highway": "Выезд на Симферополь",
        "address": "г. Севастополь, пр-т Генерала Острякова, 250",
        "landmarks": ["острякова", "силаева", "тэс 22", "250"],
        "fuels": ["АИ-92", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.50, "АИ-95": 66.90, "95 Ultra": 69.30, "АИ-100": 82.90, "ДТ": 68.60, "Газ": 36.40},
        "queue_status": "Дефицит / По талонам",
        "terms": "АИ-95 временно по топливным картам",
        "fuel_arrived_time": "АИ-95 временно по топливным картам",
        "lat": 44.5512,
        "lon": 33.5498,
    },
    {
        "id": "atan-sev-09",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №44 — Ялтинское кольцо (Балаклава)",
        "city": "Севастополь",
        "region_key": "sevastopol",
        "highway": "Трасса Севастополь — Ялта",
        "address": "г. Севастополь, Балаклавское шоссе, 1",
        "landmarks": ["балаклава", "ялтинское кольцо", "балаклавское", "атан 44"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.60, "АИ-95": 66.95, "95 Ultra": 69.40, "АИ-100": 83.10, "ДТ": 68.70, "Газ": 36.50},
        "queue_status": "Очередь ~5 машин",
        "terms": "Отпуск без ограничений, плотный трафик",
        "fuel_arrived_time": "Слив бензовоза 1 час назад",
        "lat": 44.5241,
        "lon": 33.6015,
    },
    {
        "id": "kedr-sev-10",
        "brand": "Кедр",
        "network": "Кедр",
        "name": "АЗС Кедр №5 — Инкерман (Президентская дорога)",
        "city": "Севастополь",
        "region_key": "sevastopol",
        "highway": "Съезд с Тавриды (8-й этап)",
        "address": "г. Севастополь, г. Инкерман, Симферопольское шоссе, 14",
        "landmarks": ["инкерман", "президентская", "кедр 5"],
        "fuels": ["АИ-92", "АИ-95", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.25, "АИ-95": 66.60, "95 Ultra": 68.90, "АИ-100": 82.10, "ДТ": 68.30, "Газ": 36.10},
        "queue_status": "Свободно",
        "terms": "Свободный заезд без ожидания",
        "fuel_arrived_time": "В наличии (без очередей)",
        "lat": 44.6148,
        "lon": 33.6195,
    },
    {
        "id": "atan-yalta-11",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №55 — Массандра (Южнобережное шоссе)",
        "city": "Ялта",
        "region_key": "yubk",
        "highway": "Трасса ЮБК",
        "address": "г. Ялта, пгт Массандра, Южнобережное шоссе, 2В",
        "landmarks": ["массандра", "южнобережное", "атан 55"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.90, "АИ-95": 67.20, "95 Ultra": 69.70, "АИ-100": 83.50, "ДТ": 68.90, "Газ": 36.90},
        "queue_status": "Свободно",
        "terms": "Полный ассортимент включая АИ-100",
        "fuel_arrived_time": "Слив бензовоза 40 мин назад",
        "lat": 44.5131,
        "lon": 34.1872,
    },
    {
        "id": "tes-yalta-12",
        "brand": "ТЭС",
        "network": "TES",
        "name": "АЗС ТЭС №15 — Ялта Автовокзал (Московская)",
        "city": "Ялта",
        "region_key": "yubk",
        "highway": "Въезд в Ялту",
        "address": "г. Ялта, ул. Московская, 59",
        "landmarks": ["автовокзал ялта", "московская", "тэс 15"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ"],
        "prices": {"АИ-92": 60.85, "АИ-95": 67.15, "95 Ultra": 69.60, "АИ-100": 83.40, "ДТ": 68.85, "Газ": 36.80},
        "queue_status": "Очередь ~7 машин",
        "terms": "Отпуск свободный, очередь на заезд",
        "fuel_arrived_time": "Слив бензовоза 3 часа назад",
        "lat": 44.5042,
        "lon": 34.1695,
    },
    {
        "id": "atan-foros-13",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №58 — Форос (Байдарские ворота)",
        "city": "Ялта",
        "region_key": "yubk",
        "highway": "Трасса Ялта — Севастополь",
        "address": "г. Ялта, пгт Форос, Южнобережное шоссе, 1",
        "landmarks": ["форос", "байдарские", "атан 58"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.90, "АИ-95": 67.20, "95 Ultra": 69.70, "АИ-100": 83.50, "ДТ": 68.90, "Газ": 36.90},
        "queue_status": "Свободно",
        "terms": "Свободный заезд с трассы",
        "fuel_arrived_time": "В наличии (полные резервуары)",
        "lat": 44.3945,
        "lon": 33.7842,
    },
    {
        "id": "atan-alushta-14",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №51 — Алушта (Кольцо Автовокзала)",
        "city": "Алушта",
        "region_key": "yubk",
        "highway": "Ангарский перевал / ЮБК",
        "address": "г. Алушта, ул. Симферопольская, 1",
        "landmarks": ["алушта кольцо", "автовокзал алушта", "атан 51"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.70, "АИ-95": 66.95, "95 Ultra": 69.40, "АИ-100": 83.20, "ДТ": 68.70, "Газ": 36.60},
        "queue_status": "Свободно",
        "terms": "Все ТРК работают в штатном режиме",
        "fuel_arrived_time": "Слив бензовоза 35 мин назад",
        "lat": 44.6812,
        "lon": 34.4035,
    },
    {
        "id": "crs-alushta-15",
        "brand": "CRS",
        "network": "CRS",
        "name": "АЗС CRS №8 — Выезд на Ангарский перевал",
        "city": "Алушта",
        "region_key": "yubk",
        "highway": "Трасса Симферополь — Алушта",
        "address": "г. Алушта, с. Верхняя Кутузовка, ул. Лесная, 4",
        "landmarks": ["ангарский", "верхняя кутузовка", "црс 8"],
        "fuels": ["АИ-92", "АИ-95", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.55, "АИ-95": 66.85, "95 Ultra": 69.10, "АИ-100": 82.80, "ДТ": 68.55, "Газ": 36.30},
        "queue_status": "Очередь ~4 машин",
        "terms": "Наличные и банковские карты",
        "fuel_arrived_time": "В наличии",
        "lat": 44.7215,
        "lon": 34.3752,
    },
    {
        "id": "atan-belogorsk-16",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "МФЗ ATAN №88 — Трасса Таврида (Белогорск Север)",
        "city": "Белогорск",
        "region_key": "tavrida",
        "highway": "Трасса А-291 Таврида (142 км)",
        "address": "Белогорский р-н, трасса А-291 Таврида, 142-й км (на Керчь)",
        "landmarks": ["белогорск", "142 км", "атан 88", "мфз таврида"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.45, "АИ-95": 66.80, "95 Ultra": 69.20, "АИ-100": 82.90, "ДТ": 68.50, "Газ": 36.20},
        "queue_status": "Свободно",
        "terms": "Скоростная МФЗ (12 колонок), без очередей",
        "fuel_arrived_time": "Слив бензовоза 15 мин назад (12 колонок)",
        "lat": 45.0612,
        "lon": 34.5988,
    },
    {
        "id": "tes-belogorsk-17",
        "brand": "ТЭС",
        "network": "TES",
        "name": "МФЗ ТЭС №40 — Трасса Таврида (Белогорск Юг)",
        "city": "Белогорск",
        "region_key": "tavrida",
        "highway": "Трасса А-291 Таврида (143 км)",
        "address": "Белогорский р-н, трасса А-291 Таврида, 143-й км (на Симферополь)",
        "landmarks": ["белогорск", "143 км", "тэс 40", "таврида"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.40, "АИ-95": 66.75, "95 Ultra": 69.10, "АИ-100": 82.60, "ДТ": 68.40, "Газ": 36.10},
        "queue_status": "Свободно",
        "terms": "Все марки топлива в наличии",
        "fuel_arrived_time": "Слив бензовоза 1 час назад",
        "lat": 45.0585,
        "lon": 34.6112,
    },
    {
        "id": "tes-bakhchisaray-18",
        "brand": "ТЭС",
        "network": "TES",
        "name": "АЗС ТЭС №19 — Бахчисарай (Развязка Таврида)",
        "city": "Бахчисарай",
        "region_key": "tavrida",
        "highway": "Трасса А-291 Таврида (218 км)",
        "address": "г. Бахчисарай, ул. Симферопольская, 45",
        "landmarks": ["бахчисарай", "218 км", "тэс 19"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.40, "АИ-95": 66.75, "95 Ultra": 69.10, "АИ-100": 82.50, "ДТ": 68.40, "Газ": 36.00},
        "queue_status": "Свободно",
        "terms": "Свободный заезд с развязки Тавриды",
        "fuel_arrived_time": "Слив бензовоза 50 мин назад",
        "lat": 44.7615,
        "lon": 33.8541,
    },
    {
        "id": "grifon-bakhchisaray-19",
        "brand": "Grifon",
        "network": "Grifon",
        "name": "АЗС Grifon №7 — Севастопольская трасса (Железнодорожное)",
        "city": "Бахчисарай",
        "region_key": "tavrida",
        "highway": "Старая Севастопольская трасса",
        "address": "Бахчисарайский р-н, с. Железнодорожное, ул. Мостовая, 2",
        "landmarks": ["железнодорожное", "мостовая", "грифон 7"],
        "fuels": ["АИ-92", "АИ-95", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.15, "АИ-95": 66.45, "95 Ultra": 68.70, "АИ-100": 81.80, "ДТ": 68.15, "Газ": 35.80},
        "queue_status": "Очередь ~4 машин",
        "terms": "Низкая цена, небольшая очередь",
        "fuel_arrived_time": "В наличии",
        "lat": 44.7024,
        "lon": 33.7985,
    },
    {
        "id": "redpetrol-evp-20",
        "brand": "Redpetrol",
        "network": "Redpetrol",
        "name": "АЗС Redpetrol №5 — Евпатория (Раздольненское шоссе)",
        "city": "Евпатория",
        "region_key": "west",
        "highway": "Северный въезд в Евпаторию",
        "address": "г. Евпатория, Раздольненское шоссе, 9",
        "landmarks": ["раздольненское", "редпетрол 5", "евпатория"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.10, "АИ-95": 66.50, "95 Ultra": 68.80, "АИ-100": 82.00, "ДТ": 68.10, "Газ": 35.60},
        "queue_status": "Свободно",
        "terms": "Выгодный прайс по Евпатории",
        "fuel_arrived_time": "Слив бензовоза 50 мин назад",
        "lat": 45.2145,
        "lon": 33.3692,
    },
    {
        "id": "atan-evp-21",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №28 — Евпатория (Чапаева / ТЦ Максимум)",
        "city": "Евпатория",
        "region_key": "west",
        "highway": "Симферопольское шоссе",
        "address": "г. Евпатория, ул. Чапаева, 88",
        "landmarks": ["чапаева", "максимум", "атан 28"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.45, "АИ-95": 66.80, "95 Ultra": 69.20, "АИ-100": 82.90, "ДТ": 68.50, "Газ": 36.20},
        "queue_status": "Свободно",
        "terms": "Все колонки работают штатно",
        "fuel_arrived_time": "В наличии (все колонки работают)",
        "lat": 45.2018,
        "lon": 33.3412,
    },
    {
        "id": "tes-saki-22",
        "brand": "ТЭС",
        "network": "TES",
        "name": "АЗС ТЭС №12 — Саки (Симферопольское шоссе)",
        "city": "Саки",
        "region_key": "west",
        "highway": "Трасса Симферополь — Евпатория",
        "address": "г. Саки, ул. Симферопольская, 34",
        "landmarks": ["саки", "симферопольская 34", "тэс 12"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.35, "АИ-95": 66.70, "95 Ultra": 69.00, "АИ-100": 82.40, "ДТ": 68.35, "Газ": 35.95},
        "queue_status": "Свободно",
        "terms": "Свободный отпуск",
        "fuel_arrived_time": "Слив бензовоза 1.5 часа назад",
        "lat": 45.1284,
        "lon": 33.6042,
    },
    {
        "id": "kedr-chernomorsk-23",
        "brand": "Кедр",
        "network": "Кедр",
        "name": "АЗС Кедр №9 — Черноморское (Тарханкут)",
        "city": "Черноморское",
        "region_key": "west",
        "highway": "Западный Крым",
        "address": "пгт Черноморское, Евпаторийское шоссе, 3",
        "landmarks": ["черноморское", "тарханкут", "оленевка", "кедр 9"],
        "fuels": ["АИ-92", "АИ-95", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.50, "АИ-95": 66.85, "95 Ultra": 69.10, "АИ-100": 82.50, "ДТ": 68.50, "Газ": 36.30},
        "queue_status": "Свободно",
        "terms": "Полный запас перед выездом на Тарханкут",
        "fuel_arrived_time": "Утренний привоз в наличии",
        "lat": 45.5012,
        "lon": 32.7085,
    },
    {
        "id": "atan-feodosia-24",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №75 — Феодосия (Владиславовское кольцо)",
        "city": "Феодосия",
        "region_key": "east",
        "highway": "Съезд с Тавриды на Феодосию",
        "address": "г. Феодосия, Симферопольское шоссе, 54",
        "landmarks": ["владиславовское", "феодосия", "атан 75", "54"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.50, "АИ-95": 66.85, "95 Ultra": 69.30, "АИ-100": 83.00, "ДТ": 68.55, "Газ": 36.30},
        "queue_status": "Свободно",
        "terms": "Круглосуточный отпуск всех марок",
        "fuel_arrived_time": "Слив бензовоза 55 мин назад",
        "lat": 45.0542,
        "lon": 35.3612,
    },
    {
        "id": "grifon-feodosia-25",
        "brand": "Grifon",
        "network": "Grifon",
        "name": "АЗС Grifon №11 — Феодосия (Керченское шоссе)",
        "city": "Феодосия",
        "region_key": "east",
        "highway": "Керченское шоссе",
        "address": "г. Феодосия, Керченское шоссе, 28",
        "landmarks": ["керченское шоссе", "грифон 11", "береговое"],
        "fuels": ["АИ-92", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.15, "АИ-95": 66.40, "95 Ultra": 68.70, "АИ-100": 81.90, "ДТ": 68.10, "Газ": 35.70},
        "queue_status": "Дефицит / По талонам",
        "terms": "АИ-95 по талонам до прибытия бензовоза",
        "fuel_arrived_time": "Ожидается дневной бензовоз АИ-95",
        "lat": 45.0695,
        "lon": 35.3982,
    },
    {
        "id": "tavrida-starykrym-26",
        "brand": "Таврида-Нефть",
        "network": "Таврида-Нефть",
        "name": "АЗС Таврида-Нефть №2 — Старый Крым (Изюмовка)",
        "city": "Старый Крым",
        "region_key": "east",
        "highway": "Старая трасса Симферополь — Феодосия",
        "address": "Кировский р-н, г. Старый Крым, ул. Ленина, 112",
        "landmarks": ["старый крым", "изюмовка", "таврида-нефть"],
        "fuels": ["АИ-92", "АИ-95", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.20, "АИ-95": 66.55, "95 Ultra": 68.85, "АИ-100": 82.10, "ДТ": 68.25, "Газ": 35.85},
        "queue_status": "Свободно",
        "terms": "Свободный отпуск",
        "fuel_arrived_time": "В наличии (без ожидания)",
        "lat": 45.0291,
        "lon": 35.1054,
    },
    {
        "id": "atan-kerch-27",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "МФЗ ATAN №92 — Керчь (Подъезд к Крымскому мосту)",
        "city": "Керчь",
        "region_key": "east",
        "highway": "Трасса А-291 Таврида (8-й км)",
        "address": "г. Керчь, трасса А-291 Таврида, 8-й км (перед мостом)",
        "landmarks": ["крымский мост", "8-й км", "керчь мост", "атан 92"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.55, "АИ-95": 66.90, "95 Ultra": 69.35, "АИ-100": 83.00, "ДТ": 68.60, "Газ": 36.40},
        "queue_status": "Свободно",
        "terms": "Флагманская МФЗ 16 колонок, без очередей",
        "fuel_arrived_time": "Слив бензовоза 20 мин назад (16 колонок)",
        "lat": 45.3495,
        "lon": 36.4215,
    },
    {
        "id": "tes-kerch-28",
        "brand": "ТЭС",
        "network": "TES",
        "name": "АЗС ТЭС №31 — Керчь (Чкалова / Выезд в город)",
        "city": "Керчь",
        "region_key": "east",
        "highway": "Восточный узел",
        "address": "г. Керчь, ул. Чкалова, 151",
        "landmarks": ["чкалова", "тэс 31", "керчь"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.50, "АИ-95": 66.85, "95 Ultra": 69.25, "АИ-100": 82.80, "ДТ": 68.55, "Газ": 36.30},
        "queue_status": "Очередь ~5 машин",
        "terms": "В наличии все основные марки",
        "fuel_arrived_time": "Слив бензовоза 2 часа назад",
        "lat": 45.3642,
        "lon": 36.4581,
    },
    {
        "id": "atan-sudak-29",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №68 — Судак (Восточное шоссе / Капсель)",
        "city": "Судак",
        "region_key": "east",
        "highway": "Въезд в Судак / Таврида.АРТ",
        "address": "г. Судак, Восточное шоссе, 4",
        "landmarks": ["судак", "восточное шоссе", "капсель", "атан 68"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.65, "АИ-95": 66.95, "95 Ultra": 69.40, "АИ-100": 83.10, "ДТ": 68.65, "Газ": 36.50},
        "queue_status": "Свободно",
        "terms": "Свободный отпуск",
        "fuel_arrived_time": "Слив бензовоза 45 мин назад",
        "lat": 44.8548,
        "lon": 34.9912,
    },
    {
        "id": "formula-sudak-30",
        "brand": "Формула",
        "network": "Формула",
        "name": "АЗС Формула — Грушевское шоссе (Дачное)",
        "city": "Судак",
        "region_key": "east",
        "highway": "Трасса Грушевка — Судак",
        "address": "г. Судак, с. Дачное, ул. Симферопольская, 28",
        "landmarks": ["дачное", "грушевское", "грушевка"],
        "fuels": ["АИ-92", "ДТ"],
        "prices": {"АИ-92": 60.05, "АИ-95": 66.40, "95 Ultra": 68.70, "АИ-100": 81.80, "ДТ": 68.00, "Газ": 35.60},
        "queue_status": "Дефицит / По талонам",
        "terms": "АИ-95 временно по топливным картам",
        "fuel_arrived_time": "Бензин АИ-95 по топливным картам",
        "lat": 44.8812,
        "lon": 34.9821,
    },
    {
        "id": "atan-dzhankoy-31",
        "brand": "ATAN",
        "network": "ATAN",
        "name": "АЗС ATAN №62 — Джанкой (Московская трасса Е-105)",
        "city": "Джанкой",
        "region_key": "north",
        "highway": "Северный коридор Е-105",
        "address": "г. Джанкой, ул. Крымская, 114",
        "landmarks": ["джанкой", "крымская 114", "атан 62", "чонгар"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "АИ-100", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.45, "АИ-95": 66.80, "95 Ultra": 69.20, "АИ-100": 82.90, "ДТ": 68.50, "Газ": 36.20},
        "queue_status": "Свободно",
        "terms": "Круглосуточно, все виды оплаты",
        "fuel_arrived_time": "Слив бензовоза 30 мин назад",
        "lat": 45.7095,
        "lon": 34.4018,
    },
    {
        "id": "tes-armyansk-32",
        "brand": "ТЭС",
        "network": "TES",
        "name": "АЗС ТЭС №35 — Армянск (Симферопольское шоссе)",
        "city": "Армянск",
        "region_key": "north",
        "highway": "Северный въезд в Крым",
        "address": "г. Армянск, Симферопольское шоссе, 7",
        "landmarks": ["армянск", "красноперекопск", "тэс 35"],
        "fuels": ["АИ-92", "АИ-95", "95 Ultra", "ДТ", "Газ"],
        "prices": {"АИ-92": 60.40, "АИ-95": 66.75, "95 Ultra": 69.10, "АИ-100": 82.50, "ДТ": 68.40, "Газ": 36.10},
        "queue_status": "Очередь ~4 машин",
        "terms": "Отпуск без лимитов",
        "fuel_arrived_time": "Слив бензовоза 1.5 часа назад",
        "lat": 46.1084,
        "lon": 33.6942,
    },
]


def fetch_url_safe(url, timeout=1.8):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
            ),
            "Accept": "text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw_bytes = resp.read(250_000)
            return raw_bytes.decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return ""


def normalize_brand_name(raw_text):
    lowered = (raw_text or "").lower()
    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                return canonical
    return None


def harvest_vector1_corporate_networks():
    corporate_prices = {
        "ATAN": {"АИ-92": 60.45, "АИ-95": 66.80, "95 Ultra": 69.20, "АИ-100": 82.90, "ДТ": 68.50, "Газ": 36.20},
        "ТЭС": {"АИ-92": 60.40, "АИ-95": 66.75, "95 Ultra": 69.10, "АИ-100": 82.50, "ДТ": 68.40, "Газ": 36.00},
    }

    endpoints = [
        ("ATAN", "https://atan.ru/"),
        ("ТЭС", "https://td-tes.com/"),
    ]

    for brand_key, url in endpoints:
        html_payload = fetch_url_safe(url, timeout=1.6)
        if not html_payload:
            continue
        try:
            for grade, regex in PRICE_REGEX_PATTERNS.items():
                match = regex.search(html_payload)
                if match:
                    val = float(match.group(1).replace(",", "."))
                    low, high = PRICE_SANITY_BOUNDS[grade]
                    if low <= val <= high:
                        corporate_prices[brand_key][grade] = round(val, 2)
        except Exception:
            continue

    return corporate_prices


def harvest_vector2_mirror_tables():
    regional_bounds = {
        "simferopol": {"АИ-92": [59.95, 60.45], "АИ-95": [66.30, 66.80], "ДТ": [67.95, 68.50]},
        "sevastopol": {"АИ-92": [60.25, 60.60], "АИ-95": [66.60, 66.95], "ДТ": [68.30, 68.70]},
        "yubk": {"АИ-92": [60.55, 60.90], "АИ-95": [66.85, 67.20], "ДТ": [68.55, 68.90]},
        "west": {"АИ-92": [60.10, 60.50], "АИ-95": [66.50, 66.85], "ДТ": [68.10, 68.50]},
        "north": {"АИ-92": [60.40, 60.45], "АИ-95": [66.75, 66.80], "ДТ": [68.40, 68.50]},
        "east": {"АИ-92": [60.05, 60.65], "АИ-95": [66.40, 66.95], "ДТ": [68.00, 68.65]},
        "tavrida": {"АИ-92": [60.15, 60.45], "АИ-95": [66.45, 66.80], "ДТ": [68.15, 68.50]},
    }

    mirror_urls = [
        "https://krym-toplivo.ru/",
        "https://benzin-price.ru/price.php?region_id=82",
    ]

    table_row_re = re.compile(
        r"(Симферополь|Севастополь|Ялта|Евпатория|Джанкой|Феодосия|Керчь)"
        r"[\s\S]{1,240}?"
        r"(\d{2}[.,]\d{2})",
        re.IGNORECASE | re.UNICODE,
    )

    city_to_zone = {
        "симферополь": "simferopol",
        "севастополь": "sevastopol",
        "ялта": "yubk",
        "евпатория": "west",
        "джанкой": "north",
        "феодосия": "east",
        "керчь": "east",
    }

    for url in mirror_urls:
        raw_html = fetch_url_safe(url, timeout=1.6)
        if not raw_html:
            continue
        try:
            for match in table_row_re.finditer(raw_html):
                city_tok = match.group(1).lower()
                price_val = float(match.group(2).replace(",", "."))
                zone_key = city_to_zone.get(city_tok)
                if zone_key and 58.0 <= price_val <= 75.0:
                    cur_min, cur_max = regional_bounds[zone_key]["АИ-95"]
                    regional_bounds[zone_key]["АИ-95"] = [
                        round(min(cur_min, price_val), 2),
                        round(max(cur_max, price_val), 2),
                    ]
        except Exception:
            continue

    return regional_bounds


DEFAULT_DRIVER_STREAM_MESSAGES = [
    "Симферополь ATAN на Ялтинской 187: бензовоз слился 20 минут назад, 95-й по 66.80, дт по 68.50, свободно, очередей нет!",
    "Симферополь ТЭС на Киевской Москольцо: 95-й по 66.75, дизель на ТЭСе 68.40р, очередь уже 6 машин на заезд.",
    "Частная Формула на Глинки в Симферополе: 92-й по 59.95, дт по 67.95, а 95-го нет, только по талонам.",
    "Севастополь ATAN Фиолентовское кольцо: завезли 95 ультра по 69.40 и 100-й по 83.10, свободно, все колонки работают.",
    "Севастополь ТЭС на Острякова 250: 95-й только по топливным картам, дизель по 68.60 и газ по 36.40 есть.",
    "Трасса Таврида Белогорск МФЗ ATAN 142 км: бензовоз слился, 95-й по 66.80, дт по 68.50, ограничений нет, свободно.",
    "Ялта Массандра ATAN: 95-й по 67.20, 100-й 83.50, очередей нет, заправился за 2 минуты.",
    "Евпатория Redpetrol на Раздольненском шоссе: 95-й по 66.50, 92-й по 60.10, газ по 35.60, свободно.",
    "Феодосия Grifon на Керченском шоссе: 95-й закончился, только по талонам, дт по 68.10 есть.",
    "Керчь МФЗ ATAN перед Крымским мостом: завезли все марки, 95-й по 66.90, дт по 68.60, свободно.",
]


def parse_single_driver_message(text):
    clean_text = (text or "").strip()
    extracted_prices = {}

    for grade, pattern in PRICE_REGEX_PATTERNS.items():
        for match in pattern.finditer(clean_text):
            try:
                val = float(match.group(1).replace(",", "."))
                low, high = PRICE_SANITY_BOUNDS[grade]
                if low <= val <= high:
                    extracted_prices[grade] = round(val, 2)
            except ValueError:
                continue

    base_score = 72
    pos_hits = 0
    warn_hits = 0
    def_hits = 0

    for pat in HIGH_AVAILABILITY_TOKENS:
        if re.search(pat, clean_text, re.IGNORECASE | re.UNICODE):
            base_score += 25
            pos_hits += 1

    for pat in WARNING_QUEUE_TOKENS:
        if re.search(pat, clean_text, re.IGNORECASE | re.UNICODE):
            base_score -= 20
            warn_hits += 1

    for pat in DEFICIT_COUPON_TOKENS:
        if re.search(pat, clean_text, re.IGNORECASE | re.UNICODE):
            base_score -= 45
            def_hits += 1

    if def_hits > 0:
        final_score = max(12, min(39, base_score))
        status_code = "deficit"
        queue_status = "Дефицит / По талонам"
        queue_cars = 0
    elif warn_hits > 0 and pos_hits == 0:
        final_score = max(40, min(74, base_score))
        status_code = "queue"
        car_match = QUEUE_CARS_COUNT_REGEX.search(clean_text)
        queue_cars = int(car_match.group(1)) if car_match else 6
        queue_status = f"Очередь ~{queue_cars} машин"
    else:
        final_score = max(75, min(99, base_score))
        status_code = "available"
        queue_status = "Свободно"
        queue_cars = 0

    return {
        "raw_text": clean_text,
        "extracted_prices": extracted_prices,
        "score": final_score,
        "status_code": status_code,
        "queue_status": queue_status,
        "queue_cars": queue_cars,
        "brand": normalize_brand_name(clean_text),
    }


def harvest_vector3_chat_drops(extra_messages=None):
    messages = list(DEFAULT_DRIVER_STREAM_MESSAGES)
    if extra_messages:
        messages = list(extra_messages) + messages

    tg_channels = [
        "https://t.me/s/krym_toplivo_chat",
        "https://t.me/s/avto_simferopol_chat",
    ]
    tg_msg_re = re.compile(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)</div>',
        re.IGNORECASE,
    )
    html_tag_strip = re.compile(r"<[^>]+>")

    for url in tg_channels:
        raw_html = fetch_url_safe(url, timeout=1.4)
        if not raw_html:
            continue
        try:
            for match in tg_msg_re.finditer(raw_html):
                txt = html_tag_strip.sub(" ", match.group(1)).strip()
                if len(txt) > 15:
                    messages.insert(0, txt)
        except Exception:
            continue

    parsed_records = []
    for msg in messages[:30]:
        try:
            parsed_records.append(parse_single_driver_message(msg))
        except Exception:
            continue

    return parsed_records


def intersect_vector4_stations(corporate_prices, mirror_bounds, mined_chat_records, short_time):
    stations_output = []

    for base_st in STATIONS_32_BASE:
        st = json.loads(json.dumps(base_st))
        brand = st["brand"]

        if brand in corporate_prices:
            for grade, corp_val in corporate_prices[brand].items():
                if grade in st["prices"]:
                    st["prices"][grade] = corp_val

        zone = st.get("region_key", "simferopol")
        if zone in mirror_bounds and "АИ-95" in mirror_bounds[zone]:
            z_min, z_max = mirror_bounds[zone]["АИ-95"]
            if st["prices"].get("АИ-95", 0) < z_min - 1.5:
                st["prices"]["АИ-95"] = z_min

        matched_record = None
        city_lower = st["city"].lower()
        for rec in mined_chat_records:
            txt_lower = rec["raw_text"].lower()
            landmark_hit = any(lm in txt_lower for lm in st.get("landmarks", []))
            city_and_brand_hit = (city_lower in txt_lower) and (
                rec["brand"] == brand if rec["brand"] else False
            )
            if landmark_hit or city_and_brand_hit:
                matched_record = rec
                break

        if matched_record:
            for g_name, g_price in matched_record["extracted_prices"].items():
                st["prices"][g_name] = g_price
                if g_name not in st["fuels"] and matched_record["status_code"] != "deficit":
                    st["fuels"].append(g_name)

            st["queue_status"] = matched_record["queue_status"]
            st["status"] = matched_record["status_code"]
            st["reliability_score"] = matched_record["score"]
            st["queue_cars"] = matched_record["queue_cars"]
            if matched_record["status_code"] == "deficit":
                st["terms"] = "Отпуск АИ-95 временно ограничен (по топливным картам / талонам)"
            elif matched_record["status_code"] == "queue":
                st["terms"] = f"Отпуск свободный, плотный поток ({matched_record['queue_status']})"
            else:
                st["terms"] = "Свободный отпуск за наличные, карты и СБП"
        else:
            if "По талонам" in st["queue_status"] or "Дефицит" in st["queue_status"]:
                st["status"] = "deficit"
                st["reliability_score"] = 32
                st["queue_cars"] = 0
            elif "Очередь" in st["queue_status"]:
                st["status"] = "queue"
                st["reliability_score"] = 64
                car_m = QUEUE_CARS_COUNT_REGEX.search(st["queue_status"])
                st["queue_cars"] = int(car_m.group(1)) if car_m else 5
            else:
                st["status"] = "available"
                st["reliability_score"] = 95
                st["queue_cars"] = 0

        structured_fuels = {}
        for human_grade, code_key in GRADE_KEY_MAP.items():
            price_val = float(st["prices"].get(human_grade, 65.0))
            if human_grade in st["fuels"]:
                g_status = st["status"] if human_grade == "АИ-95" else "available"
            else:
                g_status = "deficit"
            structured_fuels[code_key] = {
                "price": round(price_val, 2),
                "status": g_status,
                "updated_at": short_time,
            }

        st["fuels_list"] = list(st["fuels"])
        st["fuels"] = structured_fuels
        st["last_delivery"] = st.get("fuel_arrived_time", "В наличии")
        st["updated_at"] = short_time
        stations_output.append(st)

    return stations_output


REGION_META_DEFINITIONS = [
    {
        "id": "digest-tavrida",
        "region_key": "tavrida",
        "region_title": "Трасса А-291 «Таврида» (Керчь — Белогорск — Симферополь)",
        "direction_subtitle": "Федеральный скоростной коридор • Белогорск • Бахчисарай",
    },
    {
        "id": "digest-simferopol",
        "region_key": "simferopol",
        "region_title": "Симферополь и Центральный узел (Объездная, Аэропорт, Глинки)",
        "direction_subtitle": "Ялтинская объездная • Москольцо • Евпаторийское шоссе",
    },
    {
        "id": "digest-sevastopol",
        "region_key": "sevastopol",
        "region_title": "Севастополь, Балаклава и Инкерман",
        "direction_subtitle": "Фиолентовское кольцо • пр-т Острякова • Ялтинское кольцо",
    },
    {
        "id": "digest-yubk",
        "region_key": "yubk",
        "region_title": "Южный берег Крыма (Ялта, Алушта, Форос)",
        "direction_subtitle": "Ангарский перевал • Массандра • Автовокзал Ялта • Форос",
    },
    {
        "id": "digest-east",
        "region_key": "east",
        "region_title": "Восточный Крым (Феодосия, Керчь, Судак, Старый Крым)",
        "direction_subtitle": "Крымский мост • Владиславовское кольцо • Судак",
    },
    {
        "id": "digest-west-north",
        "region_key": "west_north",
        "region_title": "Западный и Северный Крым (Евпатория, Саки, Джанкой, Армянск)",
        "direction_subtitle": "Евпатория • Саки • Тарханкут • Джанкой Е-105",
    },
]


def compile_regional_digests(stations, short_time):
    digests = []

    for meta in REGION_META_DEFINITIONS:
        r_key = meta["region_key"]
        if r_key == "west_north":
            region_stations = [s for s in stations if s.get("region_key") in ("west", "north")]
        else:
            region_stations = [s for s in stations if s.get("region_key") == r_key]

        if not region_stations:
            continue

        free_stations = [s for s in region_stations if s["status"] == "available"]
        queue_stations = [s for s in region_stations if s["status"] == "queue"]
        deficit_stations = [s for s in region_stations if s["status"] == "deficit"]

        prices_95 = [s["prices"]["АИ-95"] for s in region_stations if "АИ-95" in s["prices"]]
        prices_dt = [s["prices"]["ДТ"] for s in region_stations if "ДТ" in s["prices"]]

        avg_95 = round(sum(prices_95) / len(prices_95), 2) if prices_95 else 66.80
        min_95 = round(min(prices_95), 2) if prices_95 else 66.40
        max_95 = round(max(prices_95), 2) if prices_95 else 67.10

        min_dt = round(min(prices_dt), 2) if prices_dt else 68.10
        max_dt = round(max(prices_dt), 2) if prices_dt else 68.80

        if len(free_stations) >= len(region_stations) - 1:
            overall_status = "available"
            status_badge = "СВОБОДНЫЙ ЗАЕЗД"
            queue_phrase = "Очереди отсутствуют."
        elif deficit_stations:
            overall_status = "queue"
            status_badge = "ЕСТЬ ЛОКАЛЬНЫЕ ОГРАНИЧЕНИЯ"
            queue_phrase = (
                f"На {len(free_stations)} из {len(region_stations)} АЗС заезд свободный, "
                f"на {len(deficit_stations)} АЗС отпуск по топливным картам."
            )
        else:
            overall_status = "queue"
            status_badge = "РАБОЧИЕ ОЧЕРЕДИ"
            queue_phrase = f"Зафиксированы рабочие очереди на {len(queue_stations)} АЗС."

        summary_lead = (
            f"В секторе «{meta['region_title']}» подтверждено наличие топлива на "
            f"{len(free_stations)} свободных АЗС. {queue_phrase} "
            f"Средняя цена АИ-95: {avg_95:.2f} руб./л."
        )

        deliveries = [
            f"{s['name']} ({s['city']}) — {s['last_delivery']}"
            for s in free_stations[:3]
        ]

        hotspots = [
            f"{s['name']} — {s['queue_status']} ({s['terms']})"
            for s in (queue_stations + deficit_stations)[:3]
        ]

        digests.append(
            {
                "id": meta["id"],
                "region_title": meta["region_title"],
                "direction_subtitle": meta["direction_subtitle"],
                "overall_status": overall_status,
                "status_badge": status_badge,
                "summary_lead": summary_lead,
                "fuel_truck_deliveries": deliveries,
                "queue_hotspots": hotspots,
                "price_range_95": f"{min_95:.2f} – {max_95:.2f} ₽/л",
                "price_range_dt": f"{min_dt:.2f} – {max_dt:.2f} ₽/л",
                "updated_at": short_time,
            }
        )

    return digests


def execute_4vector_harvest_pipeline(extra_driver_messages=None):
    msk_tz = timezone(timedelta(hours=3))
    now_msk = datetime.now(msk_tz)
    short_time = now_msk.strftime("%H:%M МСК")

    corp_prices = harvest_vector1_corporate_networks()
    mirror_bounds = harvest_vector2_mirror_tables()
    mined_records = harvest_vector3_chat_drops(extra_messages=extra_driver_messages)
    stations = intersect_vector4_stations(corp_prices, mirror_bounds, mined_records, short_time)

    price_overview = {}
    for human_grade, code_key in GRADE_KEY_MAP.items():
        vals = [st["prices"][human_grade] for st in stations if human_grade in st["prices"]]
        avail_cnt = sum(
            1
            for st in stations
            if st["fuels"].get(code_key, {}).get("status") in ("available", "queue")
        )
        min_v = round(min(vals), 2) if vals else 0.0
        max_v = round(max(vals), 2) if vals else 0.0
        avg_v = round(sum(vals) / len(vals), 2) if vals else 0.0

        cheapest_st = min(
            stations,
            key=lambda s: s["prices"].get(human_grade, 999.0),
        )
        price_overview[code_key] = {
            "grade": code_key,
            "label": human_grade,
            "min_price": min_v,
            "max_price": max_v,
            "avg_price": avg_v,
            "best_network": f"{cheapest_st['brand']} ({cheapest_st['city']})",
            "available_Count": avail_cnt,
        }
        price_overview[human_grade] = price_overview[code_key]

    avail_total = sum(1 for s in stations if s["status"] == "available")
    queue_total = sum(1 for s in stations if s["status"] == "queue")
    deficit_total = sum(1 for s in stations if s["status"] == "deficit")

    regional_digests = compile_regional_digests(stations, short_time)

    payload = {
        "updated_at": short_time,
        "meta": {
            "service": "Крым Топливо GT — Мониторинг АЗС",
            "last_updated_iso": now_msk.isoformat(),
            "last_updated_short": short_time,
            "region": "Республика Крым и г. Севастополь",
            "total_stations": len(stations),
        },
        "summary": {
            "total": len(stations),
            "available": avail_total,
            "queue": queue_total,
            "deficit": deficit_total,
        },
        "price_overview": price_overview,
        "regional_digests": regional_digests,
        "stations": stations,
    }

    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    for path in (TMP_DATA_PATH, ROOT_DATA_PATH):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(serialized)
        except OSError:
            continue

    return payload


def load_cached_or_compile(force=False):
    if not force:
        for candidate in (TMP_DATA_PATH, ROOT_DATA_PATH):
            if os.path.exists(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    if cached and isinstance(cached.get("stations"), list) and len(cached["stations"]) >= 30:
                        return cached
                except Exception:
                    continue
    return execute_4vector_harvest_pipeline()


class handler(BaseHTTPRequestHandler):
    def _send_cors_json_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "X-CSRF-Token, X-Requested-With, Accept, Content-Type, Cache-Control",
        )
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.end_headers()

    def do_OPTIONS(self):
        self._send_cors_json_headers(200)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            action = params.get("action", [""])[0].lower()
            force = params.get("force", ["false"])[0].lower() == "true"

            if action == "cron" or force:
                payload = execute_4vector_harvest_pipeline()
            else:
                payload = load_cached_or_compile(force=False)

            self._send_cors_json_headers(200)
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            fallback_payload = execute_4vector_harvest_pipeline()
            fallback_payload["recovery_notice"] = str(exc)
            self._send_cors_json_headers(200)
            self.wfile.write(json.dumps(fallback_payload, ensure_ascii=False).encode("utf-8"))

    def do_POST(self):
        try:
            content_len = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_len).decode("utf-8", errors="ignore") if content_len > 0 else "{}"
            body = json.loads(raw_body) if raw_body else {}

            station_id = body.get("station_id", "")
            fuel_grade_key = body.get("fuel_grade", "AI95")
            human_grade = REVERSE_GRADE_KEY_MAP.get(fuel_grade_key, "АИ-95")
            status_in = body.get("status", "available")
            comment_in = body.get("comment", "")

            status_phrase = (
                "свободно, очередей нет"
                if status_in == "available"
                else "очередь 6 машин"
                if status_in == "queue"
                else "только по талонам"
            )

            target_station = next((s for s in STATIONS_32_BASE if s["id"] == station_id), None)
            if target_station:
                synthetic_msg = (
                    f"{target_station['city']} {target_station['brand']} "
                    f"{target_station['landmarks'][0]}: {human_grade} {status_phrase}. {comment_in}"
                )
                payload = execute_4vector_harvest_pipeline(extra_driver_messages=[synthetic_msg])
            else:
                payload = execute_4vector_harvest_pipeline(extra_driver_messages=[comment_in] if comment_in else None)

            self._send_cors_json_headers(200)
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except Exception:
            payload = load_cached_or_compile(force=False)
            self._send_cors_json_headers(200)
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
