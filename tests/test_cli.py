import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


class MockDsvHandler(BaseHTTPRequestHandler):
    flaky_counter = 0
    counter_lock = threading.Lock()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._respond(200, "OK")
            return

        if path == "/api/v1/secrets/my-secret":
            self._respond(200, "retrieved")
            return

        if path == "/api/v1/secrets/missing":
            self._respond(404, "Secret not found")
            return

        if path == "/api/v1/secrets/flaky":
            with MockDsvHandler.counter_lock:
                MockDsvHandler.flaky_counter += 1
                attempt = MockDsvHandler.flaky_counter
            if attempt < 3:
                self._respond(503, "retry")
                return
            self._respond(200, "stable")
            return

        self._respond(405, "method not allowed")

    def do_POST(self):
        if self.path == "/api/v1/secrets":
            self._consume_request_body()
            self._respond(201, "created")
            return
        self._respond(405, "method not allowed")

    def do_PUT(self):
        if self.path == "/api/v1/secrets":
            self._consume_request_body()
            self._respond(200, "updated")
            return
        self._respond(405, "method not allowed")

    def do_DELETE(self):
        if self.path == "/api/v1/secrets":
            self._consume_request_body()
            self.send_response(204)
            self.end_headers()
            return
        self._respond(405, "method not allowed")

    def _consume_request_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            self.rfile.read(content_length)

    def _respond(self, status_code: int, body: str):
        payload = body.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json" if body.startswith("{") else "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class CliTest(unittest.TestCase):
    total_tests = 0
    passed_tests = 0

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[1]
        MockDsvHandler.flaky_counter = 0
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockDsvHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)
        print(f"Passed {cls.passed_tests}/{cls.total_tests} tests.")

    def setUp(self):
        type(self).total_tests += 1

    def tearDown(self):
        outcome = getattr(self, "_outcome", None)
        if outcome is not None and getattr(outcome, "success", False):
            type(self).passed_tests += 1

    def _run_cli_script(self, commands: list[str]) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write("\n".join(commands) + "\n")
            script_path = tmp.name

        env = os.environ.copy()
        env["DSV_API_BASE_URL"] = self.base_url
        env["DSV_CLIENT_MAX_RETRIES"] = "2"
        env["DSV_CLIENT_RETRY_DELAY_MS"] = "1"

        try:
            return subprocess.run(
                [sys.executable, "cli.py", "--script", script_path],
                cwd=self.repo_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            os.unlink(script_path)

    def test_supports_crud_requests(self):
        result = self._run_cli_script(
            [
                "create db-password hunter2 auth-key",
                "get my-secret auth-key",
                "update name new auth-key",
                "delete name auth-key",
            ]
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("created", result.stdout)
        self.assertIn("retrieved", result.stdout)
        self.assertIn("updated", result.stdout)
        self.assertIn("(no response body)", result.stdout)

    def test_retries_on_503_until_success(self):
        result = self._run_cli_script(["get flaky auth-key"])

        self.assertEqual(0, result.returncode)
        self.assertIn("stable", result.stdout)

    def test_includes_server_message_body_in_errors(self):
        result = self._run_cli_script(["get missing auth-key"])

        self.assertEqual(0, result.returncode)
        self.assertIn("Secret not found", result.stdout)
        self.assertNotIn('"message":"Secret not found"', result.stdout)
        self.assertNotIn("Unexpected response status", result.stdout)
        self.assertNotIn("HTTP 404", result.stdout)

    def test_ping_returns_health_status(self):
        result = self._run_cli_script(["ping"])

        self.assertEqual(0, result.returncode)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
