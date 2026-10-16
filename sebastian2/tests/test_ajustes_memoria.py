"""H1 (fase 2): umbrales de la memoria, por defecto y desde config (D35)."""
from core.memoria.ajustes import propietario_vault, umbrales


def test_umbrales_por_defecto_son_los_calibrados():
    u = umbrales({})
    assert u["reutilizar"] == {"puntuacion": 0.58, "margen": 0.03}
    assert u["sustituir"] == {"puntuacion": 0.68, "margen": 0.05}


def test_config_pisa_solo_lo_que_trae():
    u = umbrales({"memoria": {"umbrales": {"reutilizar": {"puntuacion": 0.7}}}})
    assert u["reutilizar"] == {"puntuacion": 0.7, "margen": 0.03}
    assert u["sustituir"]["puntuacion"] == 0.68


def test_propietario_vault_por_defecto_es_el_chat_del_cuaderno():
    assert propietario_vault({"cuaderno_chat_id": 815566372}) == "815566372"
    assert propietario_vault({"cuaderno_chat_id": 1, "memoria": {"propietario_vault": 2}}) == "2"
