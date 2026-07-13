import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import JsonLogFormatter, LOGGER_NAME, TextLogFormatter
from app.main import create_app


def _error_test_app() -> FastAPI:
    test_app = create_app()

    @test_app.get("/test/validation")
    def validation_endpoint(password: int) -> dict[str, int]:
        return {"password": password}

    @test_app.get("/test/unhandled")
    def unhandled_endpoint() -> None:
        raise RuntimeError("private internal detail")

    return test_app


def test_valid_incoming_request_id_is_preserved() -> None:
    test_app = _error_test_app()

    with TestClient(test_app) as client:
        response = client.get(
            "/",
            headers={"X-Request-ID": "proxy-request-123"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "proxy-request-123"


def test_invalid_incoming_request_id_is_replaced() -> None:
    test_app = _error_test_app()

    with TestClient(test_app) as client:
        response = client.get("/", headers={"X-Request-ID": "bad id"})

    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 200
    assert request_id != "bad id"
    assert len(request_id) == 32


def test_validation_error_does_not_echo_input_value() -> None:
    test_app = _error_test_app()

    with TestClient(test_app) as client:
        response = client.get(
            "/test/validation",
            params={"password": "raw-secret-value"},
        )

    content = response.json()
    assert response.status_code == 422
    assert content["error"]["code"] == "VALIDATION_ERROR"
    assert content["error"]["request_id"] == response.headers["X-Request-ID"]
    assert content["error"]["detail"] == [
        {
            "location": "query.password",
            "message": "Input should be a valid integer, unable to parse string as an integer",
            "type": "int_parsing",
        }
    ]
    assert "raw-secret-value" not in response.text


def test_unhandled_error_returns_safe_response() -> None:
    test_app = _error_test_app()

    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.get("/test/unhandled")

    content = response.json()
    assert response.status_code == 500
    assert content["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert content["error"]["message"] == "服务器内部错误"
    assert content["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "private internal detail" not in response.text


def test_error_is_written_to_searchable_log(tmp_path: Path) -> None:
    test_app = _error_test_app()
    request_id = "manual-search-request-123"
    log_file = tmp_path / "app.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(TextLogFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(file_handler)

    try:
        with TestClient(test_app) as client:
            response = client.get(
                "/missing",
                headers={"X-Request-ID": request_id},
            )
    finally:
        file_handler.close()
        logger.removeHandler(file_handler)

    assert response.status_code == 404
    assert request_id in log_file.read_text(encoding="utf-8")


def test_json_log_formatter_keeps_request_and_task_context() -> None:
    record = logging.LogRecord(
        name=f"{LOGGER_NAME}.tasks",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="task_failed",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-123"
    record.task_id = "task-456"
    record.error_code = "TASK_FAILED"

    content = json.loads(JsonLogFormatter().format(record))

    assert content["event"] == "task_failed"
    assert content["request_id"] == "request-123"
    assert content["task_id"] == "task-456"
    assert content["error_code"] == "TASK_FAILED"


def test_json_log_formatter_redacts_sensitive_values() -> None:
    record = logging.LogRecord(
        name=f"{LOGGER_NAME}.security",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="password=raw-password token:raw-token",
        args=(),
        exc_info=None,
    )

    formatted = JsonLogFormatter().format(record)

    assert "raw-password" not in formatted
    assert "raw-token" not in formatted
    assert "password=***" in formatted
    assert "token:***" in formatted
