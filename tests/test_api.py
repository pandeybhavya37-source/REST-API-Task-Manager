import json
import os
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from app import main


class APITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.tmp_dir.name, "test_tasks.db")
        main.DB_PATH = cls.db_path
        main.init_db()

        cls.server = main.ThreadingHTTPServer(("127.0.0.1", 0), main.TaskHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=1)
        cls.tmp_dir.cleanup()

    def request(self, method, path, payload=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        data = json.loads(raw.decode("utf-8")) if raw else None
        conn.close()
        return response.status, data

    def test_task_lifecycle(self):
        status, task = self.request("POST", "/tasks", {"title": "Write tests", "description": "for API"})
        self.assertEqual(status, 201)
        self.assertEqual(task["title"], "Write tests")
        task_id = task["id"]

        status, all_tasks = self.request("GET", "/tasks")
        self.assertEqual(status, 200)
        self.assertEqual(len(all_tasks), 1)

        status, fetched = self.request("GET", f"/tasks/{task_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["id"], task_id)

        status, updated = self.request(
            "PUT",
            f"/tasks/{task_id}",
            {"title": "Write more tests", "description": "expanded", "completed": True},
        )
        self.assertEqual(status, 200)
        self.assertTrue(updated["completed"])

        status, completed = self.request("PATCH", f"/tasks/{task_id}/complete")
        self.assertEqual(status, 200)
        self.assertTrue(completed["completed"])

        status, filtered = self.request("GET", "/tasks?completed=true")
        self.assertEqual(status, 200)
        self.assertEqual(len(filtered), 1)

        status, _ = self.request("DELETE", f"/tasks/{task_id}")
        self.assertEqual(status, 204)

        status, missing = self.request("GET", f"/tasks/{task_id}")
        self.assertEqual(status, 404)
        self.assertEqual(missing["detail"], "Task not found")


if __name__ == "__main__":
    unittest.main()
