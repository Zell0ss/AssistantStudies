"""H3 (fase 2, plan §3 H3.1, D37): lectura de `30-projects/*/proyecto.md`. Solo lectura, sin BD ni API."""
import os

from core.memoria.vault import CAMPOS_CONTRATO, leer_proyectos, proyecto_por_nombre


def _proyecto(base, carpeta, frontmatter, cuerpo="# nota\n"):
    d = base / carpeta
    d.mkdir(parents=True)
    (d / "proyecto.md").write_text(f"---\n{frontmatter}\n---\n{cuerpo}", encoding="utf-8")


def test_lee_los_campos_del_contrato_como_texto(tmp_path):
    _proyecto(tmp_path, "proyecto-prueba",
              "contrato: 2\nnombre: proyecto-prueba\nhost: seb01\nestado: stable\nstack: Python, MariaDB\n"
              "repo: https://github.com/x/y\ndb: prueba_db\nservicios:\n  - a.service\nruta: /data/x")
    assert leer_proyectos(str(tmp_path)) == {"proyecto-prueba": {
        "estado": "stable", "host": "seb01", "stack": "Python, MariaDB",
        "repo": "https://github.com/x/y", "db": "prueba_db"}}
    assert set(CAMPOS_CONTRATO) == {"estado", "host", "stack", "repo", "db"}   # servicios y ruta no son hechos


def test_solo_lee_el_frontmatter_no_el_cuerpo(tmp_path):
    _proyecto(tmp_path, "uno", "contrato: 2\nestado: activo", cuerpo="estado: pausado\nhost: otra\n")
    assert leer_proyectos(str(tmp_path))["uno"] == {"estado": "activo"}


def test_usa_yaml_seguro_y_un_frontmatter_malo_no_rompe_a_los_demas(tmp_path):
    _proyecto(tmp_path, "peligroso", "estado: !!python/object/apply:os.system ['echo hola']")
    _proyecto(tmp_path, "roto", "estado: [sin cerrar")
    _proyecto(tmp_path, "sano", "estado: activo")
    assert leer_proyectos(str(tmp_path)) == {"sano": {"estado": "activo"}}


def test_ignora_carpetas_sin_proyecto_md_y_ficheros_sueltos(tmp_path):
    (tmp_path / "sin-contrato").mkdir()
    (tmp_path / "PROJECTS.md").write_text("---\nestado: x\n---\n", encoding="utf-8")
    (tmp_path / "sin-frontmatter").mkdir()
    (tmp_path / "sin-frontmatter" / "proyecto.md").write_text("# solo cuerpo\n", encoding="utf-8")
    assert leer_proyectos(str(tmp_path)) == {}


def test_ruta_inexistente_o_vacia_devuelve_vacio(tmp_path):
    assert leer_proyectos(str(tmp_path / "no-existe")) == {}
    assert leer_proyectos(None) == {}
    assert leer_proyectos("") == {}


def test_vault_confinado(tmp_path):
    """Un `proyecto.md` (o una carpeta) que es symlink fuera de 30-projects se ignora, igual que en consult_docs."""
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (fuera / "secreto.md").write_text("---\nestado: filtrado\n---\n", encoding="utf-8")
    base = tmp_path / "30-projects"
    _proyecto(base, "legitimo", "estado: stable")

    (base / "enlace-fichero").mkdir()
    os.symlink(fuera / "secreto.md", base / "enlace-fichero" / "proyecto.md")
    _proyecto(fuera, "carpeta-ajena", "estado: filtrado")
    os.symlink(fuera / "carpeta-ajena", base / "enlace-carpeta")

    assert leer_proyectos(str(base)) == {"legitimo": {"estado": "stable"}}


def test_symlink_dentro_del_vault_si_vale(tmp_path):
    base = tmp_path / "30-projects"
    _proyecto(base, "real", "estado: activo")
    os.symlink(base / "real", base / "alias")
    assert "real" in leer_proyectos(str(base))


def test_proyecto_por_nombre_usa_el_mismo_normalizador_que_los_alias(tmp_path):
    _proyecto(tmp_path, "proyecto-prueba", "estado: stable")
    proyectos = leer_proyectos(str(tmp_path))
    assert proyecto_por_nombre(proyectos, "Proyecto Prueba") == ("proyecto-prueba", {"estado": "stable"})
    assert proyecto_por_nombre(proyectos, "el proyecto-prueba") == ("proyecto-prueba", {"estado": "stable"})
    assert proyecto_por_nombre(proyectos, "otro") is None
    assert proyecto_por_nombre(proyectos, "") is None
