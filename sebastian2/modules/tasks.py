# modules/tasks.py
"""
Tasks module - atomic tasks over project_tasks (shared with glasspannel).

Unlike other modules, project_tasks is NOT scoped by user_id — it's a
cross-project table shared with glasspannel, scoped by `project` instead.
"""
from modules.base import BaseModule
from logcentral_client import get_logger

logger = get_logger("sebastian")


class TasksModule(BaseModule):

    def list(self, project=None, state='open'):
        """
        List tasks, optionally filtered by project and state.

        Args:
            project: Project name to filter by (optional)
            state: 'open' (default, done=0), 'done' (done=1), or 'all'

        Returns:
            List of task dicts
        """
        conditions = []
        params = []

        if project:
            conditions.append("project = %s")
            params.append(project)

        if state == 'open':
            conditions.append("done = 0")
        elif state == 'done':
            conditions.append("done = 1")
        elif state != 'all':
            raise ValueError(f"Invalid state: {state!r} (expected 'open', 'done', or 'all')")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM project_tasks {where} ORDER BY created_at DESC"
        cursor = self.execute_query(query, tuple(params))
        return cursor.fetchall()

    def create(self, project, title, priority='normal', known_projects=None):
        """
        Create a task in a project.

        Args:
            project: Project name (validated against known_projects if given)
            title: Task title
            priority: 'high' | 'normal' | 'low' (default 'normal')
            known_projects: optional set of known project slugs for validation

        Returns:
            {'status': 'created', 'task_id': int} | {'status': 'unknown_project', 'known_projects': [...]}
        """
        if known_projects is not None:
            from modules.project_registry import is_known_project
            if not is_known_project(project, known_projects):
                return {'status': 'unknown_project', 'known_projects': sorted(known_projects)}

        query = """
            INSERT INTO project_tasks (title, project, priority)
            VALUES (%s, %s, %s)
        """
        cursor = self.execute_query(query, (title, project, priority))
        self.commit()

        task_id = cursor.lastrowid
        logger.info(f"Created task {task_id} in project {project}: {title}")
        return {'status': 'created', 'task_id': task_id}

    def complete(self, task_id):
        """
        Mark a task as done.

        Args:
            task_id: Task ID

        Returns:
            {'status': 'completed', 'task_id': int} | {'status': 'not_found'}
        """
        cursor = self.execute_query("SELECT id FROM project_tasks WHERE id = %s", (task_id,))
        if not cursor.fetchone():
            return {'status': 'not_found'}

        self.execute_query("UPDATE project_tasks SET done = 1 WHERE id = %s", (task_id,))
        self.commit()
        logger.info(f"Completed task {task_id}")
        return {'status': 'completed', 'task_id': task_id}
