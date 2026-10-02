"""Parâmetros do engine. Valores `provisional` precisam de fonte/validação técnica."""

# Descontos de confiança (heurística explicável, não probabilidade).
CONFIDENCE_PENALTY = {
    "soil_unspecified": 0.15,
    "soil_ad_approximation": 0.05,
    "zarc_old_season": 0.15,
    "cultivar_by_uf": 0.05,
    "cultivar_unknown": 0.05,
    "location_approximate": 0.05,
    "forecast_unavailable": 0.20,
    "forecast_stale": 0.10,
}
CONFIDENCE_HIGH = 0.75
CONFIDENCE_MEDIUM = 0.5

# Quantos decêndios antes do fim da janela avisamos "a janela está acabando".
WINDOW_CLOSING_DECENDIOS = 1  # provisional
# Até quantos decêndios à frente consideramos "a próxima janela está perto".
NEXT_WINDOW_SOON_DECENDIOS = 3  # provisional

MAX_VARIETIES_SHOWN = 8

# --- Previsão (provisional: referência = avisos do INMET para chuva acumulada no dia) ---
# INMET: "chuvas intensas" amarelo até ~50 mm/dia; laranja 50–100 mm/dia.
HEAVY_RAIN_MM_DAY = 50.0  # provisional
MODERATE_RAIN_MM_DAY = 30.0  # provisional
RAIN_MM_DAY = 10.0
LIGHT_RAIN_MM_DAY = 1.0
FORECAST_HORIZON_DAYS = 5  # chuva forte: olhar só os próximos dias
DRY_SPELL_DAYS = 7  # provisional
DRY_SPELL_MAX_MM = 10.0  # provisional: pouca chuva somada no período
GOOD_MOISTURE_MM = 20.0  # provisional: chuva somada nos próximos dias boa para semear
HOT_DAY_C = 35.0  # provisional
COLD_NIGHT_C = 3.0  # provisional (risco de geada em baixada)

# --- Melhor dia de semeadura (otimização; pesos provisórios, explicáveis) ---
SOWING_HORIZON_DAYS = 10
SOWING_GOOD_AFTER_MM = 10.0  # chuva somada nos 3 dias seguintes boa para germinar
SOWING_SOME_AFTER_MM = 4.0
SOWING_MIN_SCORE = 30  # abaixo disso não sugerimos "melhor dia"
