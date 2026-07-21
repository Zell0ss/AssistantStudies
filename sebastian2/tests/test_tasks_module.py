# tests/test_tasks_module.py
import pytest

from modules.tasks import TasksModule
from db.connection import get_connection, close_connection

TEST_PROJECT = "test_project_tasks_module"
TEST_PROJECT_2 = "test_project_tasks_module_2"


@pytest.fixture
def tasks_module():
    """Fixture to create TasksModule instance. project_tasks is NOT user-scoped
    (shared with glasspannel), so isolation uses a dedicated fake `project` value."""
    conn = get_connection()
    module = TasksModule(conn, user_id="unused")

    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_tasks WHERE project IN (%s, %s)", (TEST_PROJECT, TEST_PROJECT_2))
    conn.commit()

    yield module

    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_tasks WHERE project IN (%s, %s)", (TEST_PROJECT, TEST_PROJECT_2))
    conn.commit()
    close_connection()


def test_create_task_returns_created_status_and_id(tasks_module):
    result = tasks_module.create(TEST_PROJECT, "revisar fuzzy match")
    assert result["status"] == "created"
    assert isinstance(result["task_id"], int)


def test_create_task_defaults_to_normal_priority_and_open(tasks_module):
    tasks_module.create(TEST_PROJECT, "tarea sin prioridad")
    tasks = tasks_module.list(project=TEST_PROJECT, state="all")
    assert len(tasks) == 1
    assert tasks[0]["priority"] == "normal"
    assert tasks[0]["done"] == 0


def test_create_task_with_explicit_priority(tasks_module):
    tasks_module.create(TEST_PROJECT, "tarea urgente", priority="high")
    tasks = tasks_module.list(project=TEST_PROJECT, state="all")
    assert tasks[0]["priority"] == "high"


def test_create_task_rejects_unknown_project_when_known_projects_given(tasks_module):
    result = tasks_module.create(
        "proyecto-inventado-xyz", "tarea", known_projects={TEST_PROJECT}
    )
    assert result["status"] == "unknown_project"
    assert "known_projects" in result


def test_create_task_accepts_known_project_when_known_projects_given(tasks_module):
    result = tasks_module.create(
        TEST_PROJECT, "tarea válida", known_projects={TEST_PROJECT}
    )
    assert result["status"] == "created"


def test_list_defaults_to_open_only(tasks_module):
    tasks_module.create(TEST_PROJECT, "abierta 1")
    done_result = tasks_module.create(TEST_PROJECT, "para completar")
    tasks_module.complete(done_result["task_id"])

    open_tasks = tasks_module.list(project=TEST_PROJECT)
    assert len(open_tasks) == 1
    assert open_tasks[0]["title"] == "abierta 1"


def test_list_state_done_returns_only_completed(tasks_module):
    tasks_module.create(TEST_PROJECT, "abierta")
    done_result = tasks_module.create(TEST_PROJECT, "completada")
    tasks_module.complete(done_result["task_id"])

    done_tasks = tasks_module.list(project=TEST_PROJECT, state="done")
    assert len(done_tasks) == 1
    assert done_tasks[0]["title"] == "completada"


def test_list_state_all_returns_everything(tasks_module):
    tasks_module.create(TEST_PROJECT, "abierta")
    done_result = tasks_module.create(TEST_PROJECT, "completada")
    tasks_module.complete(done_result["task_id"])

    all_tasks = tasks_module.list(project=TEST_PROJECT, state="all")
    assert len(all_tasks) == 2


def test_list_filters_by_project(tasks_module):
    tasks_module.create(TEST_PROJECT, "tarea proyecto 1")
    tasks_module.create(TEST_PROJECT_2, "tarea proyecto 2")

    tasks = tasks_module.list(project=TEST_PROJECT, state="all")
    assert len(tasks) == 1
    assert tasks[0]["project"] == TEST_PROJECT


def test_list_without_project_does_not_raise(tasks_module):
    tasks_module.create(TEST_PROJECT, "tarea sin filtro")
    tasks = tasks_module.list(state="all")
    assert any(t["project"] == TEST_PROJECT for t in tasks)


def test_complete_marks_task_done(tasks_module):
    created = tasks_module.create(TEST_PROJECT, "tarea a completar")
    result = tasks_module.complete(created["task_id"])
    assert result["status"] == "completed"

    tasks = tasks_module.list(project=TEST_PROJECT, state="done")
    assert len(tasks) == 1


def test_complete_missing_task_returns_not_found(tasks_module):
    result = tasks_module.complete(999999999)
    assert result["status"] == "not_found"
