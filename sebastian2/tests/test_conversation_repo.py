"""H2 (fase 1): ConversationRepository contra sebastian_test — D21, D23."""
from datetime import datetime, timedelta

import pytest

from db.connection import close_connection, get_connection
from db.conversation_repo import ConversationRepository

USER = "test_user_conversation_repo"
OTRO = "test_user_conversation_repo_otro"


@pytest.fixture
def repo_y_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM conversations WHERE user_id IN (%s, %s)", (USER, OTRO))
    conn.commit()
    yield ConversationRepository(conn), conn
    cur = conn.cursor()
    cur.execute("DELETE FROM conversations WHERE user_id IN (%s, %s)", (USER, OTRO))
    conn.commit()
    close_connection()


def _insertar(conn, user_id, user_msg, bot_reply, hace: timedelta):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (user_id, user_msg, bot_reply, created_at) VALUES (%s, %s, %s, %s)",
        (user_id, user_msg, bot_reply, (datetime.now() - hace).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()


def test_recientes_orden_cronologico_y_limite(repo_y_db):
    repo, _ = repo_y_db
    for i in range(8):
        repo.guardar(USER, f"msg {i}", f"resp {i}")

    resultado = repo.recientes(USER, limite=6)

    assert [r["user_msg"] for r in resultado] == [f"msg {i}" for i in range(2, 8)]
    assert resultado[0]["bot_reply"] == "resp 2"


def test_recientes_respeta_ventana(repo_y_db):
    repo, conn = repo_y_db
    _insertar(conn, USER, "viejo", "r viejo", timedelta(hours=3))
    _insertar(conn, USER, "reciente", "r reciente", timedelta(minutes=10))

    resultado = repo.recientes(USER, ventana_min=120)

    assert [r["user_msg"] for r in resultado] == ["reciente"]


def test_recientes_solo_del_usuario(repo_y_db):
    repo, _ = repo_y_db
    repo.guardar(USER, "mío", "r mío")
    repo.guardar(OTRO, "ajeno", "r ajeno")

    assert [r["user_msg"] for r in repo.recientes(USER)] == ["mío"]


def test_limpiar_borra_mas_de_7_dias(repo_y_db):
    repo, conn = repo_y_db
    repo.limpiar(7)  # limpia antes lo viejo que haya en la BD de test, para contar solo lo nuestro
    _insertar(conn, USER, "hace 8 días", "r", timedelta(days=8))
    _insertar(conn, USER, "hace 6 días", "r", timedelta(days=6))

    borradas = repo.limpiar(7)

    assert borradas == 1
    cur = conn.cursor()
    cur.execute("SELECT user_msg FROM conversations WHERE user_id = %s", (USER,))
    assert [f["user_msg"] for f in cur.fetchall()] == ["hace 6 días"]
