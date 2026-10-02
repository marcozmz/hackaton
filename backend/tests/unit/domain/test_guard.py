from app.domain.narrative import guard

CTX = {
    "cultura": "Milho",
    "resumo": "O período bom vai de 1 de setembro até 20 de fevereiro. O risco agora é baixo.",
    "janela_de_plantio": {"de": "2026-09-01", "ate": "2027-02-20"},
    "motivos": ["Vai chover muito na segunda (cerca de 58 mm)."],
    "seguro": "Em 2025, foram feitos 178 seguros, com o governo pagando cerca de 40% do custo.",
}


def test_faithful_rewrite_passes():
    text = "Agora é uma boa hora para plantar milho: o calendário oficial vai até 20 de fevereiro. Cuidado com a chuva forte de segunda, uns 58 mm."
    assert guard.check(text, CTX).ok


def test_invented_number_fails():
    r = guard.check("Plante agora, a chance de perda é de 5%.", CTX)
    assert not r.ok and any("números" in p for p in r.problems)


def test_invented_month_fails():
    r = guard.check("Você pode plantar até maio.", CTX)
    assert not r.ok and any("meses" in p for p in r.problems)


def test_promises_and_pesticides_fail():
    assert not guard.check("Plantando agora a colheita é garantida.", CTX).ok
    assert not guard.check("Use um bom inseticida antes de plantar.", CTX).ok


def test_length_markdown_and_empty():
    assert not guard.check("x" * 800, CTX).ok
    assert not guard.check("**Atenção**: plante.", CTX).ok
    assert not guard.check("  ", CTX).ok


def test_number_formats_from_context_are_accepted():
    assert guard.check("Foram 178 seguros e o governo pagou 40% do custo em 2025.", CTX).ok
