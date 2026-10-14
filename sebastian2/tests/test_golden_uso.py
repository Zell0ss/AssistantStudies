"""H1-revision R1: el acumulador de tokens y coste por modelo del harness de goldens (sin red)."""
from types import SimpleNamespace

import pytest

from tests.golden.uso import AcumuladorUso


def _respuesta(entrada: int, salida: int):
    return SimpleNamespace(usage=SimpleNamespace(input_tokens=entrada, output_tokens=salida))


def test_totales_y_coste_por_modelo():
    uso = AcumuladorUso()
    uso.registrar(_respuesta(1000, 100), "claude-haiku-4-5-20251001")
    uso.registrar(_respuesta(3000, 200), "claude-haiku-4-5-20251001")
    uso.registrar(_respuesta(2000, 500), "claude-sonnet-4-6")

    assert uso.por_modelo["claude-haiku-4-5-20251001"] == {"entrada": 4000, "salida": 300}
    assert uso.por_modelo["claude-sonnet-4-6"] == {"entrada": 2000, "salida": 500}
    # Haiku: 4000*1 + 300*5 = 5500 → 0.0055 $ · Sonnet: 2000*3 + 500*15 = 13500 → 0.0135 $
    assert uso.coste("claude-haiku-4-5-20251001") == pytest.approx(0.0055)
    assert uso.coste("claude-sonnet-4-6") == pytest.approx(0.0135)
    assert uso.coste_total() == pytest.approx(0.019)


def test_respuesta_sin_usage_no_rompe_y_tabla_lista_modelos():
    uso = AcumuladorUso()
    uso.registrar(SimpleNamespace(), "claude-sonnet-4-6")
    texto = "\n".join(uso.tabla())
    assert "claude-sonnet-4-6" in texto and "TOTAL" in texto


def test_latencia_mediana_y_p90():
    from tests.golden.uso import percentil
    uso = AcumuladorUso()
    for ms in (1000, 2000, 3000, 4000, 10000):
        uso.registrar_latencia(ms)
    assert percentil([1, 2, 3, 4, 10], 0.5) == 3
    assert percentil([1, 2, 3, 4, 10], 0.9) == pytest.approx(7.6)
    assert "mediana=3.00s" in uso.resumen_latencia() and "p90=7.60s" in uso.resumen_latencia()
    assert "sin datos" in AcumuladorUso().resumen_latencia()


def test_precio_de_haiku_5_5():
    uso = AcumuladorUso()
    uso.registrar(_respuesta(1_000_000, 1_000_000), "claude-haiku-5-5")
    assert uso.coste("claude-haiku-5-5") == pytest.approx(0.60)
