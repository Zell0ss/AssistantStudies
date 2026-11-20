"""Fase 4, H1b-revision R9 (D68): `_send_markdown` parte los mensajes de más de 4000 caracteres (el límite de Telegram es 4096).
Bot falso, sin red ni API."""
from bot.handlers import _MAX_TROZO, _partir_en_trozos, _send_markdown


class BotFalso:
    def __init__(self):
        self.llamadas = []

    def send_message(self, chat_id, text, entities=None, **kwargs):
        self.llamadas.append({"chat_id": chat_id, "text": text, "entities": entities})


def _lineas(n, ancho=99):
    return "\n".join(["x" * ancho] * n)                      # cada línea ocupa `ancho + 1` con su salto


def test_el_trozo_maximo_es_4000():
    assert _MAX_TROZO == 4000


def test_r9_1_nueve_mil_caracteres_en_lineas_de_100_salen_en_3_llamadas_en_orden():
    texto = _lineas(90)                                      # 8999 caracteres
    bot = BotFalso()
    _send_markdown(bot, 123, texto)
    assert len(bot.llamadas) == 3
    assert all(len(c["text"]) <= 4000 for c in bot.llamadas) and all(c["chat_id"] == 123 for c in bot.llamadas)
    assert "\n".join(c["text"] for c in bot.llamadas) == texto             # todo el texto, en orden
    assert [len(c["text"]) for c in bot.llamadas] == [3999, 3999, 999]     # 40 líneas, 40 líneas y las 10 que quedan


def test_r9_2_una_negrita_del_segundo_trozo_lleva_su_entidad_con_el_offset_de_ese_trozo():
    lineas = ["a" * 99] * 44 + ["x **negrita** y"]            # 45 líneas: el primer trozo se llena con 40, la negrita cae en el segundo
    bot = BotFalso()
    _send_markdown(bot, 1, "\n".join(lineas))
    primero, segundo = bot.llamadas
    assert primero["entities"] is None
    assert "**" not in segundo["text"] and "negrita" in segundo["text"]
    (entidad,) = segundo["entities"]
    assert entidad.type == "bold" and entidad.length == len("negrita")
    assert entidad.offset == segundo["text"].index("negrita") == 4 * 100 + 2                   # relativo al segundo trozo, no al texto entero
    assert segundo["text"][entidad.offset:entidad.offset + entidad.length] == "negrita"


def test_r9_3_una_linea_sola_de_5000_caracteres_se_manda_en_2_llamadas():
    texto = "y" * 5000
    bot = BotFalso()
    _send_markdown(bot, 1, texto)
    assert [len(c["text"]) for c in bot.llamadas] == [4000, 1000]
    assert "".join(c["text"] for c in bot.llamadas) == texto


def test_r9_4_un_texto_corto_sale_en_1_llamada_igual_que_hoy():
    bot = BotFalso()
    _send_markdown(bot, 7, "Hola **señor**, buenos días.")
    (llamada,) = bot.llamadas
    assert llamada["text"] == "Hola señor, buenos días." and llamada["chat_id"] == 7
    (entidad,) = llamada["entities"]
    assert (entidad.type, entidad.offset, entidad.length) == ("bold", 5, 5)
    bot = BotFalso()
    _send_markdown(bot, 7, "z" * 4000)                       # justo en el límite: una llamada
    assert len(bot.llamadas) == 1 and len(bot.llamadas[0]["text"]) == 4000
    bot = BotFalso()
    _send_markdown(bot, 7, "z" * 4001)
    assert [len(c["text"]) for c in bot.llamadas] == [4000, 1]


def test_una_linea_larga_en_medio_se_corta_a_la_fuerza_sin_perder_las_demas():
    texto = "\n".join(["antes " * 10, "L" * 4500, "después " * 10])
    trozos = _partir_en_trozos(texto)
    assert all(len(t) <= 4000 for t in trozos) and len(trozos) == 3
    assert trozos[0] == "antes " * 10 and trozos[1] == "L" * 4000 and trozos[2] == "L" * 500 + "\n" + "después " * 10
    assert "L" * 4500 in "".join(trozos) and "después " * 10 in trozos[2]


def test_h1e_6_no_hay_trozos_vacios_con_una_linea_en_blanco_antes_de_una_linea_larga():
    for texto in ("\n" + "x" * 4500, "a" * 3999 + "\n\n" + "x" * 4500, "\n\n" + "x" * 4500 + "\n\n"):
        trozos = _partir_en_trozos(texto)
        assert trozos and all(t.strip() for t in trozos), repr(texto[:6])          # ninguno vacío ni de solo espacios
        assert all(len(t) <= 4000 for t in trozos)
        assert "x" * 4500 in "".join(trozos).replace("\n", "")                      # el contenido sigue entero
    bot = BotFalso()
    _send_markdown(bot, 1, "\n" + "x" * 4500)
    assert [len(c["text"]) for c in bot.llamadas] == [4000, 500]                    # y nada de mensajes vacíos a Telegram


def test_un_texto_que_cabe_no_se_toca_ni_con_saltos_de_linea_al_final():
    assert _partir_en_trozos("a\nb\n") == ["a\nb\n"]
    assert _partir_en_trozos("") == [""]
