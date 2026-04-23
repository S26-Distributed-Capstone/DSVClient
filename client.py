"""HTTP client for the Distributed Secrets Vault API.

Mirrors the Java Client.java implementation with retry logic for transient
failures (HTTP 503 / 429) and optional debug logging.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from typing import Optional


class ClientException(Exception):
    """Raised when a server request fails or returns an unexpected status."""

    def __init__(
        self,
        message: str,
        status_code: int = -1,
        reason: Optional[str] = None,
        response_body: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.response_body = response_body
        self.cause = cause


class Client:
    SECRETS_PATH = "/api/v1/secrets"
    HEALTH_PATH = "/health"

    def __init__(self, config: dict):
        self._base_url = config.get("base_url", "http://localhost:8080").rstrip("/")
        self._connect_timeout = float(config.get("connect_timeout", 3.0))
        self._read_timeout = float(config.get("read_timeout", 5.0))
        self._max_retries = int(config.get("max_retries", 2))
        self._retry_delay = float(config.get("retry_delay", 0.2))
        self._debug_http = self._is_debug_http_enabled(config)
        self._last_status_code = 0
        self._last_reason = ""
        self._last_body = ""

    @property
    def last_status_code(self) -> int:
        return self._last_status_code

    @property
    def last_reason(self) -> str:
        return self._last_reason

    @property
    def last_body(self) -> str:
        return self._last_body

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ping(self) -> str:
        return self._send("GET", self.HEALTH_PATH, None, 200)

    def create_secret(self, secret_name: str, secret_value: str, auth_key: str) -> str:
        payload = json.dumps(
            {
                "secretName": secret_name,
                "secretValue": secret_value,
                "user": auth_key,
            }
        )
        return self._send("POST", self.SECRETS_PATH, payload, 201)

    def get_secret(self, secret_name: str, auth_key: str = "") -> str:
        encoded_name = urllib.parse.quote(secret_name, safe="")
        path = f"{self.SECRETS_PATH}/{encoded_name}"
        if auth_key:
            path += f"?user={urllib.parse.quote(auth_key, safe='')}"
        return self._send("GET", path, None, 200)

    def update_secret(
        self, secret_name: str, secret_updated_value: str, auth_key: str
    ) -> str:
        payload = json.dumps(
            {
                "secretCurrentName": secret_name,
                "secretUpdatedValue": secret_updated_value,
                "user": auth_key,
            }
        )
        return self._send("PUT", self.SECRETS_PATH, payload, 200)

    def delete_secret(self, secret_name: str, auth_key: str) -> str:
        payload = json.dumps(
            {
                "deleteName": secret_name,
                "user": auth_key,
            }
        )
        return self._send("DELETE", self.SECRETS_PATH, payload, 204)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send(
        self, method: str, path: str, body: Optional[str], expected_status: int
    ) -> str:
        started_at_ms = int(time.time() * 1000)
        safe_path = path.split("?")[0]  # omit query params (may contain auth keys)
        self._debug(
            f"Sending {method} {safe_path} "
            f"(connect_timeout={self._connect_timeout}, read_timeout={self._read_timeout}, "
            f"max_retries={self._max_retries})"
        )
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            self._debug(f"HTTP attempt {attempt} of {max_attempts}")
            try:
                status_code, reason, response_body = self._do_request(method, path, body)
                normalized_reason = self._normalize_reason(status_code, reason)
                self._last_status_code = status_code
                self._last_reason = normalized_reason
                self._last_body = response_body or ""

                if status_code in (503, 429) and attempt < max_attempts:
                    self._debug(
                        f"Retryable status {status_code} received; sleeping "
                        f"{self._retry_delay}s before retry"
                    )
                    time.sleep(self._retry_delay)
                    continue

                elapsed_ms = int(time.time() * 1000) - started_at_ms
                self._debug(
                    f"Received {status_code} for {method} {safe_path} in {elapsed_ms} ms"
                )

                if status_code != expected_status:
                    raise ClientException(
                        f"Unexpected response status for {method} {safe_path}. "
                        f"Expected {expected_status} but got {status_code}",
                        status_code,
                        normalized_reason,
                        response_body,
                    )

                return response_body or ""

            except OSError as exc:
                self._debug(f"Attempt {attempt} failed with OSError: {exc}")
                if attempt >= max_attempts:
                    raise ClientException(
                        "Gateway request failed after retries", cause=exc
                    ) from exc
                time.sleep(self._retry_delay)
                continue

        raise ClientException("Gateway request failed unexpectedly")

    def _do_request(
        self, method: str, path: str, body: Optional[str]
    ) -> tuple[int, str, str]:
        url = self._base_url + path
        data = body.encode("utf-8") if body is not None else None
        headers: dict[str, str] = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            timeout_seconds = max(self._connect_timeout, self._read_timeout)
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                return resp.status, str(getattr(resp, "reason", "") or ""), resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, str(getattr(exc, "reason", "") or ""), exc.read().decode("utf-8")

    def _debug(self, message: str) -> None:
        if self._debug_http:
            print(f"[dsv-client-debug] {message}", file=sys.stderr)

    @staticmethod
    def _normalize_reason(status_code: int, reason: str) -> str:
        if reason and reason.strip():
            return reason.strip()
        try:
            return HTTPStatus(status_code).phrase
        except ValueError:
            return ""

    @staticmethod
    def _is_debug_http_enabled(config: dict) -> bool:
        value = config.get("debug_http", False)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)
