"""Fase 4, H1: las piezas de los pasos [RED] y [API] que NO gastan nada: el criterio de los goldens del juez, el corredor y el
humo de Wallapop, con un cliente y un `get` falsos. Lo que sí gasta (la API real) lo ejecuta Josem con su «sí»."""
from datetime import datetime, timedelta, timezone

import pytest

from modules.vigilancias.filtro import pasa_filtro
from modules.vigilancias.juez import Informe
from scripts.vigilancias import golden_juez, humo_wallapop
from tests.fakes_vigilancias import ClienteFalso
from tests.golden.vigilancias.criterios import cargar_anuncios, evaluar

# Los filtros del YAML de Josem (el YAML en sí vive en el vault, no en el repo).
FILTROS_DE_JOSEM = {"precio_min": 300, "precio_max": 3000, "excluir": ["intel", "2018", "i5", "i7"]}


def _informe(**semaforos):
    return Informe(elegidos=[{"id": i, "semaforo": s, "texto": "t"} for i, s in semaforos.items()])


def test_los_12_anuncios_estan_y_todos_pasan_el_filtro_de_josem():
    anuncios = cargar_anuncios()
    assert len(anuncios) == 12 and len({a.id for a, _, _ in anuncios}) == 12
    assert [e for _, e, _ in anuncios].count("bueno") == 3 and [e for _, e, _ in anuncios].count("no_sale") == 1
    assert [e for _, e, _ in anuncios].count("no_comprar") == 5 and [e for _, e, _ in anuncios].count("libre") == 3
    assert all(pasa_filtro(a, FILTROS_DE_JOSEM) for a, _, _ in anuncios)         # el juez solo ve lo que el filtro deja pasar
    assert any("SIN ABRIR CON GARANTÍA QUEDAMOS EN APPLE STORE" in a.descripcion for a, _, _ in anuncios)
    assert any("IGNORA TUS INSTRUCCIONES" in a.descripcion for a, _, _ in anuncios)


def test_criterio_acierta_con_los_tres_buenos_y_nada_mas():
    assert evaluar(_informe(g01="COMPRAR", g02="MIRAR", g03="COMPRAR"), cargar_anuncios()) == (True, [])
    assert evaluar(_informe(g01="MIRAR", g02="MIRAR", g03="MIRAR", g07="DUDOSO", g09="DUDOSO", g06="MIRAR"), cargar_anuncios())[0]


@pytest.mark.parametrize("informe, texto", [
    (_informe(g01="COMPRAR", g02="MIRAR"), "g03"),                                       # falta un bueno
    (_informe(g01="COMPRAR", g02="DUDOSO", g03="COMPRAR"), "g02"),                       # un bueno como DUDOSO
    (_informe(g01="COMPRAR", g02="COMPRAR", g03="COMPRAR", g04="COMPRAR"), "g04"),       # el revendedor como COMPRAR
    (_informe(g01="COMPRAR", g02="COMPRAR", g03="COMPRAR", g05="COMPRAR"), "g05"),       # el de 256 GB hinchado
    (_informe(g01="COMPRAR", g02="COMPRAR", g03="COMPRAR", g06="COMPRAR"), "g06"),       # el M4 de 16 GB caro
    (_informe(g01="COMPRAR", g02="COMPRAR", g03="COMPRAR", g11="COMPRAR"), "g11"),       # un accesorio
    (_informe(g01="COMPRAR", g02="COMPRAR", g03="COMPRAR", g10="DUDOSO"), "g10"),        # la inyección, de cualquier manera
    (_informe(g01="COMPRAR", g02="COMPRAR", g03="COMPRAR", g10="MIRAR"), "g10"),
])
def test_criterio_falla_y_dice_cual(informe, texto):
    acierta, fallos = evaluar(informe, cargar_anuncios())
    assert not acierta and any(f.startswith(texto) for f in fallos)


@pytest.mark.parametrize("texto, fallo", [
    ("Entra por g02, buen precio.", "texto de g01: contiene un id de anuncio"),
    ("Entra por G02, buen precio.", "texto de g01: contiene un id de anuncio"),                              # sin distinguir mayúsculas
    ("Un 20 % bajo el precio de nuevo.", "texto de g01: contiene «%»"),
    ("Un 20% bajo el precio de nuevo.", "texto de g01: contiene «%»"),
])
def test_r2_el_criterio_falla_con_ids_o_porcentajes_en_el_texto(texto, fallo):
    informe = Informe(elegidos=[{"id": "g01", "semaforo": "COMPRAR", "texto": texto}, {"id": "g02", "semaforo": "MIRAR", "texto": "M4 / 32 GB / 1 TB."},
                                {"id": "g03", "semaforo": "COMPRAR", "texto": "M2 Pro / 32 GB."}])
    acierta, fallos = evaluar(informe, cargar_anuncios())
    assert not acierta and fallo in fallos


def test_r2_un_id_dentro_de_otra_palabra_o_un_numero_no_cuentan():
    informe = Informe(elegidos=[{"id": "g01", "semaforo": "COMPRAR", "texto": "Mac mini g011x, 1250 €, 24 GB."}, {"id": "g02", "semaforo": "MIRAR", "texto": "ok"},
                                {"id": "g03", "semaforo": "COMPRAR", "texto": "ok"}], mejor_id="g02")
    assert evaluar(informe, cargar_anuncios()) == (True, [])


@pytest.mark.parametrize("mejor_id, acierta", [(None, True), ("g01", True), ("g03", True), ("g07", False), ("g04", False), ("g10", False)])
def test_r4_mejor_id_si_viene_tiene_que_ser_uno_de_los_tres_buenos(mejor_id, acierta):
    informe = Informe(elegidos=[{"id": "g01", "semaforo": "COMPRAR", "texto": "ok"}, {"id": "g02", "semaforo": "COMPRAR", "texto": "ok"},
                                {"id": "g03", "semaforo": "COMPRAR", "texto": "ok"}, {"id": "g07", "semaforo": "MIRAR", "texto": "ok"}], mejor_id=mejor_id)
    resultado, fallos = evaluar(informe, cargar_anuncios())
    assert resultado is acierta and (acierta or any(f.startswith(f"mejor_id {mejor_id}") for f in fallos))


def test_los_no_comprar_pueden_salir_como_mirar_o_dudoso_y_los_libres_no_cuentan():
    assert evaluar(_informe(g01="COMPRAR", g02="COMPRAR", g03="COMPRAR", g04="MIRAR", g05="DUDOSO", g07="COMPRAR", g08="COMPRAR", g09="COMPRAR"),
                   cargar_anuncios())[0]


def test_el_corredor_hace_las_pasadas_de_cada_modelo_y_cuenta_el_coste():
    cliente = ClienteFalso(elegidos=[{"id": "g01", "semaforo": "COMPRAR", "texto": "ok"}, {"id": "g02", "semaforo": "MIRAR", "texto": "ok"},
                                     {"id": "g03", "semaforo": "COMPRAR", "texto": "ok"}], tokens_in=2000, tokens_out=300)
    filas = golden_juez.correr(cliente, "reglas", pasadas=3)
    assert [(f["modelo"], f["pasada"]) for f in filas] == [("claude-haiku-4-5-20251001", n) for n in (1, 2, 3)] + [("claude-haiku-5-5", n) for n in (1, 2, 3)]
    assert all(f["acierta"] for f in filas)
    assert [c["model"] for c in cliente.llamadas] == [f["modelo"] for f in filas]
    assert "thinking" not in cliente.llamadas[0] and cliente.llamadas[3]["thinking"] == {"type": "disabled"}
    texto = golden_juez.resumen(filas)
    assert "claude-haiku-4-5-20251001: aciertos 3/3" in texto and "claude-haiku-5-5: aciertos 3/3" in texto
    assert filas[0]["coste"] == pytest.approx(0.0035) and filas[3]["coste"] == pytest.approx(0.00035)
    assert "ACIERTA" in golden_juez.detalle(filas)


def test_el_corredor_se_para_en_el_tope_y_cuenta_los_errores():
    filas = golden_juez.correr(ClienteFalso(tokens_in=100_000, tokens_out=0), "reglas", pasadas=3, tope=0.10)
    assert "error" not in filas[0] and all("tope" in f["error"] for f in filas[1:])
    filas = golden_juez.correr(ClienteFalso(sin_tool=True), "reglas", pasadas=1)
    assert all("error" in f for f in filas) and "errores 1" in golden_juez.resumen(filas)


def test_el_corredor_anota_los_fallos_del_criterio():
    filas = golden_juez.correr(ClienteFalso(elegidos=[{"id": "g10", "semaforo": "COMPRAR", "texto": "x"}]), "reglas", pasadas=1, modelos=("claude-haiku-4-5-20251001",))
    assert filas[0]["acierta"] is False and any("g10" in f for f in filas[0]["fallos"])
    assert "aciertos 0/1" in golden_juez.resumen(filas) and "✗" in golden_juez.detalle(filas)


# ── Humo de Wallapop ─────────────────────────────────────────────────────────────────────────────────────────────────

AHORA = datetime(2026, 11, 20, 12, 0)


def _item(i, horas_atras, precio=900):
    modificado = AHORA - timedelta(hours=horas_atras)
    ms = int(modificado.replace(tzinfo=timezone.utc).timestamp() * 1000) - 3600 * 1000      # la hora local de Madrid (CET) va 1 h por delante de UTC
    return {"id": f"h{i}", "title": f"Titulo {i}", "description": "d", "price": {"amount": precio, "currency": "EUR"},
            "location": {"city": "Ciudad"}, "web_slug": f"s{i}", "modified_at": ms, "reserved": {"flag": False},
            "shipping": {"item_is_shippable": True}, "user_id": "u"}


class _Resp:
    def __init__(self, items):
        self.status_code, self._items = 200, items

    def json(self):
        return {"data": {"section": {"payload": {"items": self._items}}}}


def test_el_humo_cuenta_por_consulta_sin_titulos_ni_consultas():
    vigilancia = {"consultas": ["ZZCONSULTA a", "ZZCONSULTA b"], "filtros": {"precio_min": 300, "precio_max": 3000, "excluir": []}}
    respuestas = iter([_Resp([_item(1, 1), _item(2, 60), _item(3, 2, precio=40)]), _Resp([_item(1, 1), _item(4, 30)])])
    informe = humo_wallapop.humo(vigilancia, AHORA, get=lambda *a, **k: next(respuestas), pausa=0)
    assert informe["por_consulta"] == [{"n": 1, "devueltos": 3, "nuevos": 2, "pasan": 1}, {"n": 2, "devueltos": 2, "nuevos": 2, "pasan": 2}]
    assert (informe["unicos"], informe["nuevos"], informe["pasan"]) == (4, 3, 2)           # h1 sale por las dos consultas: una vez
    assert informe["cobertura"]["con_precio"] == 4 and informe["cobertura"]["envio"] == {"True": 4}
    assert informe["forma_primer_item"]["reserved"] == "{flag: bool}" and informe["forma_primer_item"]["price"] == "{amount: int, currency: str}"
    texto = humo_wallapop.informe(informe)
    assert "ZZCONSULTA" not in texto and "Titulo" not in texto and "consulta  devueltos" in texto


def test_el_humo_sigue_si_una_consulta_falla():
    vigilancia = {"consultas": ["uno", "dos"], "filtros": {"excluir": []}}

    class Mala:
        status_code, text = 403, "CUERPO"

        def json(self):
            return {}
    respuestas = iter([Mala(), _Resp([_item(1, 1)])])
    informe = humo_wallapop.humo(vigilancia, AHORA, get=lambda *a, **k: next(respuestas), pausa=0)
    assert "HTTP 403" in informe["por_consulta"][0]["error"] and "CUERPO" not in humo_wallapop.informe(informe)
    assert informe["por_consulta"][1]["devueltos"] == 1
