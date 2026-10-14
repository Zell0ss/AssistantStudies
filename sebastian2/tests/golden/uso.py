"""Medición de tokens y coste por modelo de una pasada de goldens (H1-revision R1)."""
from collections import defaultdict

# Dólares por millón de tokens (entrada, salida). Fuente: docs/fase1/PLAN.md §1, comprobado con
# la skill claude-api el 2026-10-13. Si cambia un modelo del orquestador, se actualiza aquí.
PRECIOS_POR_MILLON = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    # Fase 2 H0 (D28). Tarifa de prompts de hasta 100.000 tokens; por encima sería 0,50 / 2,50 (los
    # prompts del planner rondan 10-20K). Comprobado en https://platform.claude.com/docs/en/about-claude/pricing
    # el 2026-10-14.
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-4-6": (3.0, 15.0),
}


def percentil(valores: list, q: float) -> float:
    """Percentil con interpolación lineal (q entre 0 y 1). Mismo método que la línea base de producción."""
    xs = sorted(valores)
    k = (len(xs) - 1) * q
    abajo = int(k)
    arriba = min(abajo + 1, len(xs) - 1)
    return xs[abajo] + (xs[arriba] - xs[abajo]) * (k - abajo)


class AcumuladorUso:
    def __init__(self):
        self.por_modelo = defaultdict(lambda: {"entrada": 0, "salida": 0})
        self.latencias_ms: list[float] = []

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

    def registrar_latencia(self, latency_ms: float) -> None:
        self.latencias_ms.append(latency_ms)

    def resumen_latencia(self) -> str:
        if not self.latencias_ms:
            return "latencia por turno: sin datos"
        xs = [m / 1000 for m in self.latencias_ms]
        return (
            f"latencia por turno (misma medida que 'Turn end'): n={len(xs)} "
            f"mediana={percentil(xs, 0.5):.2f}s p90={percentil(xs, 0.9):.2f}s "
            f"min={min(xs):.1f}s max={max(xs):.1f}s"
        )

    def tabla(self) -> list[str]:
        lineas = [f"{'modelo':<30}{'tokens entrada':>16}{'tokens salida':>16}{'$':>10}"]
        for modelo in sorted(self.por_modelo):
            t = self.por_modelo[modelo]
            lineas.append(
                f"{modelo:<30}{t['entrada']:>16}{t['salida']:>16}{self.coste(modelo):>10.4f}"
            )
        lineas.append(f"{'TOTAL':<62}{self.coste_total():>10.4f}")
        lineas.append(self.resumen_latencia())
        return lineas


USO = AcumuladorUso()
