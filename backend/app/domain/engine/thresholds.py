"""Parâmetros do engine. Valores `provisional` precisam de fonte/validação técnica."""

# Descontos de confiança (heurística explicável, não probabilidade).
CONFIDENCE_PENALTY = {
    "soil_unspecified": 0.15,
    "soil_ad_approximation": 0.05,
    "zarc_old_season": 0.15,
    "cultivar_by_uf": 0.05,
    "cultivar_unknown": 0.05,
    "location_approximate": 0.05,
}
CONFIDENCE_HIGH = 0.75
CONFIDENCE_MEDIUM = 0.5

# Quantos decêndios antes do fim da janela avisamos "a janela está acabando".
WINDOW_CLOSING_DECENDIOS = 1  # provisional
# Até quantos decêndios à frente consideramos "a próxima janela está perto".
NEXT_WINDOW_SOON_DECENDIOS = 3  # provisional

MAX_VARIETIES_SHOWN = 8
