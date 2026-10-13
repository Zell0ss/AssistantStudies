"""Medición de tokens y coste por modelo de una pasada de goldens (H1-revision R1)."""
from collections import defaultdict

# Dólares por millón de tokens (entrada, salida). Fuente: docs/fase1/PLAN.md §1, comprobado con
# la skill claude-api el 2026-10-13. Si cambia un modelo del orquestador, se actualiza aquí.
PRECIOS_POR_MILLON = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
}


class AcumuladorUso:
    def __init__(self):
        self.por_modelo = defaultdict(lambda: {"entrada": 0, "salida": 0})

    def registrar(self, response, model: str) -> None:
        usage = getattr(response, "usage", None)
        acumulado = self.por_modelo[model]
        if usage is not None:
            acumulado["entrada"] += getattr(usage, "input_tokens", 0) or 0
            acumulado["salida"] += getattr(usage, "output_tokens", 0) or 0

    def coste(self, model: str) -> float:
        # Un modelo sin precio conocido hace fallar la tabla: mejor eso que un coste inventado.
        precio_entrada, precio_salida = PRECIOS_POR_MILLON[model]
        t = self.por_modelo[model]
        return (t["entrada"] * precio_entrada + t["salida"] * precio_salida) / 1_000_000

    def coste_total(self) -> float:
        return sum(self.coste(m) for m in self.por_modelo)

    def tabla(self) -> list[str]:
        lineas = [f"{'modelo':<30}{'tokens entrada':>16}{'tokens salida':>16}{'$':>10}"]
        for modelo in sorted(self.por_modelo):
            t = self.por_modelo[modelo]
            lineas.append(
                f"{modelo:<30}{t['entrada']:>16}{t['salida']:>16}{self.coste(modelo):>10.4f}"
            )
        lineas.append(f"{'TOTAL':<62}{self.coste_total():>10.4f}")
        return lineas


USO = AcumuladorUso()
