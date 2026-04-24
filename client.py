"""HTTP client for the Distributed Secrets Vault API.

Mirrors the Java Client.java implementation with retry logic for transient
failures (HTTP 503 / 429).
"""

import json
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
    CONNECT_TIMEOUT_SECONDS = 3.0
    READ_TIMEOUT_SECONDS = 5.0
    MAX_RETRIES = 2
    RETRY_DELAY_SECONDS = 0.2
    def __init__(self, config: dict):
        self._base_url = config.get("base_url", "http://localhost:8080").rstrip("/")
        self._connect_timeout = self.CONNECT_TIMEOUT_SECONDS
        self._read_timeout = self.READ_TIMEOUT_SECONDS
        self._max_retries = self.MAX_RETRIES
        self._retry_delay = self.RETRY_DELAY_SECONDS

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
        safe_path = path.split("?")[0]  # omit query params (may contain auth keys)
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                status_code, reason, response_body = self._do_request(method, path, body)
                normalized_reason = self._normalize_reason(status_code, reason)

                if status_code in (503, 429) and attempt < max_attempts:
                    time.sleep(self._retry_delay)
                    continue

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

    @staticmethod
    def _normalize_reason(status_code: int, reason: str) -> str:
        if reason and reason.strip():
            return reason.strip()
        try:
            return HTTPStatus(status_code).phrase
        except ValueError:
            return ""

