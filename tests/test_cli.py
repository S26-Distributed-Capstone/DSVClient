import os
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs


class MockDsvHandler(BaseHTTPRequestHandler):
    flaky_counter = 0
    counter_lock = threading.Lock()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        if path == "/health":
            self._respond(200, "OK")
            return

        if path == "/api/v1/secrets/my-secret":
            # Check if version parameter is present
            if "version" in query_params:
                version = query_params["version"][0]
                self._respond(200, f"version-{version}")
                return
            self._respond(200, "retrieved")
            return

        # Handle get all versions: /api/v1/secrets/my-secret/all
        if path == "/api/v1/secrets/my-secret/all":
            self._respond(200, '["version1", "version2", "version3"]')
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
            body = self._consume_request_body()
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {}
            if payload.get("deleteName") == "missing-delete":
                self._respond(404, "Secret not found")
                return
            self.send_response(204)
            self.end_headers()
            return
        self._respond(405, "method not allowed")

    def _consume_request_body(self) -> str:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            return self.rfile.read(content_length).decode("utf-8")
        return ""

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
        return self._run_cli(
            ["--script", self._build_script(commands)],
            cleanup_script=True,
        )

    def _build_script(self, commands: list[str]) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write("\n".join(commands) + "\n")
            return tmp.name

    def _run_cli(
        self,
        args: list[str],
        input_text: str = "",
        cleanup_script: bool = False,
        config_data: dict | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_home:
            home_dir = Path(temp_home)
            self._write_config(
                home_dir,
                config_data
                or {
                    "base_url": self.base_url,
                    "username": "test-user",
                },
            )
            try:
                return self._run_cli_in_home(home_dir, args, input_text=input_text)
            finally:
                if cleanup_script and args and args[0] == "--script":
                    os.unlink(args[1])

    def _write_config(self, home_dir: Path, config_data: dict) -> None:
        config_dir = home_dir / ".dsv_client"
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_dir / "config.json", "w", encoding="utf-8") as fh:
            json.dump(config_data, fh)

    def _run_cli_in_home(
        self,
        home_dir: Path,
        args: list[str],
        input_text: str = "",
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)
        return subprocess.run(
            [sys.executable, "cli.py", *args],
            cwd=self.repo_root,
            env=env,
            text=True,
            input=input_text,
            capture_output=True,
            check=False,
        )

    def test_supports_crud_requests(self):
        result = self._run_cli_script(
            [
                "create db-password hunter2",
                "get my-secret",
                "update name new",
                "delete name",
            ]
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("created", result.stdout)
        self.assertIn("retrieved", result.stdout)
        self.assertIn("updated", result.stdout)
        self.assertIn("Delete succeeded (HTTP 204 No Content).", result.stdout)

    def test_delete_reports_error_status(self):
        result = self._run_cli_script(["delete missing-delete"])

        self.assertEqual(0, result.returncode)
        self.assertIn("Delete failed (HTTP 404 Not Found).", result.stdout)
        self.assertIn("Secret not found", result.stdout)

    def test_retries_on_503_until_success(self):
        result = self._run_cli_script(["get flaky"])

        self.assertEqual(0, result.returncode)
        self.assertIn("stable", result.stdout)

    def test_includes_server_message_body_in_errors(self):
        result = self._run_cli_script(["get missing"])

        self.assertEqual(0, result.returncode)
        self.assertIn("Secret not found", result.stdout)
        self.assertNotIn('"message":"Secret not found"', result.stdout)
        self.assertNotIn("Unexpected response status", result.stdout)
        self.assertNotIn("HTTP 404", result.stdout)

    def test_ping_returns_health_status(self):
        result = self._run_cli(["ping"])

        self.assertEqual(0, result.returncode)
        self.assertIn("OK", result.stdout)

    def test_no_args_prints_help_and_exits(self):
        result = self._run_cli([])

        self.assertEqual(0, result.returncode)
        self.assertIn("usage:", result.stdout)
        self.assertIn("dsvc --script <file>", result.stdout)

    def test_repl_command_is_rejected(self):
        result = self._run_cli(["repl"])
        self.assertEqual(0, result.returncode)
        self.assertIn("Unknown command: repl", result.stdout)

    def test_requires_login_for_secret_commands(self):
        result = self._run_cli(
            ["get", "my-secret"],
            config_data={"base_url": self.base_url, "username": ""},
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("Please log in first: dsvc login <username>", result.stdout)

    def test_login_logout_and_relogin_flow(self):
        with tempfile.TemporaryDirectory() as temp_home:
            home_dir = Path(temp_home)
            self._write_config(home_dir, {"base_url": self.base_url, "username": ""})

            login = self._run_cli_in_home(home_dir, ["login", "alice"])
            self.assertIn("Logged in as 'alice'.", login.stdout)

            relogin = self._run_cli_in_home(home_dir, ["login", "bob"])
            self.assertIn("Already logged in as 'alice'.", relogin.stdout)
            self.assertIn("Please run 'dsvc logout' before logging in again.", relogin.stdout)

            logout = self._run_cli_in_home(home_dir, ["logout"])
            self.assertIn("Logged out.", logout.stdout)

            login_again = self._run_cli_in_home(home_dir, ["login", "bob"])
            self.assertIn("Logged in as 'bob'.", login_again.stdout)

    def test_logout_when_already_logged_out(self):
        result = self._run_cli(
            ["logout"],
            config_data={"base_url": self.base_url, "username": ""},
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("You are already logged out.", result.stdout)

    def test_missing_server_configuration_is_reported(self):
        result = self._run_cli(
            ["ping"],
            config_data={"base_url": "", "username": "test-user"},
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("Server URL is not configured.", result.stdout)

    def test_invalid_parameter_messages(self):
        login_result = self._run_cli(["login"])
        self.assertIn("Invalid parameters for 'login'.", login_result.stdout)
        self.assertIn("Expected: login <username>", login_result.stdout)

        create_result = self._run_cli(["create", "name"])
        self.assertIn("Invalid parameters for 'create'.", create_result.stdout)
        self.assertIn("Expected: create <secretName> <secretValue>", create_result.stdout)

    def test_login_rejects_blank_username(self):
        with tempfile.TemporaryDirectory() as temp_home:
            home_dir = Path(temp_home)
            self._write_config(home_dir, {"base_url": self.base_url, "username": ""})

            result = self._run_cli_in_home(home_dir, ["login", "   "])
            self.assertEqual(0, result.returncode)
            self.assertIn("Username cannot be empty.", result.stdout)

            with open(home_dir / ".dsv_client" / "config.json", "r", encoding="utf-8") as fh:
                config = json.load(fh)
            self.assertEqual("", config.get("username"))

    def test_script_mode_can_login_then_run_commands(self):
        result = self._run_cli(
            ["--script", self._build_script(["login alice", "get my-secret"])],
            cleanup_script=True,
            config_data={"base_url": self.base_url, "username": ""},
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("Logged in as 'alice'.", result.stdout)
        self.assertIn("retrieved", result.stdout)

    def test_script_mode_rejects_command_without_login(self):
        result = self._run_cli(
            ["--script", self._build_script(["get my-secret"])],
            cleanup_script=True,
            config_data={"base_url": self.base_url, "username": ""},
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("Please log in first: dsvc login <username>", result.stdout)

    def test_get_current_version_still_works(self):
        result = self._run_cli(["get", "my-secret"])
        self.assertEqual(0, result.returncode)
        self.assertIn("retrieved", result.stdout)

    def test_get_all_versions(self):
        result = self._run_cli(["get", "my-secret", "--all"])
        self.assertEqual(0, result.returncode)
        self.assertIn("version1", result.stdout)
        self.assertIn("version2", result.stdout)
        self.assertIn("version3", result.stdout)

    def test_get_specific_version(self):
        result = self._run_cli(["get", "my-secret", "--version", "2"])
        self.assertEqual(0, result.returncode)
        self.assertIn("version-2", result.stdout)

    def test_get_with_invalid_version_option_syntax(self):
        result = self._run_cli(["get", "my-secret", "--version"])
        self.assertEqual(0, result.returncode)
        self.assertIn("Invalid parameters for 'get'.", result.stdout)
        self.assertIn("Expected:", result.stdout)

    def test_get_with_unknown_option(self):
        result = self._run_cli(["get", "my-secret", "--unknown"])
        self.assertEqual(0, result.returncode)
        self.assertIn("Invalid parameters for 'get'.", result.stdout)

    def test_get_all_versions_in_script_mode(self):
        result = self._run_cli(
            ["--script", self._build_script(["login alice", "get my-secret --all"])],
            cleanup_script=True,
            config_data={"base_url": self.base_url, "username": ""},
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("version1", result.stdout)
        self.assertIn("version2", result.stdout)

    def test_get_specific_version_in_script_mode(self):
        result = self._run_cli(
            ["--script", self._build_script(["login alice", "get my-secret --version 3"])],
            cleanup_script=True,
            config_data={"base_url": self.base_url, "username": ""},
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("version-3", result.stdout)


if __name__ == "__main__":
    unittest.main()
