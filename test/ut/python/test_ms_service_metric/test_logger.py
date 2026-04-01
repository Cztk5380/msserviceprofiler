# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import logging
import uuid

import pytest

from ms_service_metric.utils.logger import get_logger, get_log_level, setup_logging


@pytest.fixture
def isolated_ms_metric_logger_name():
    """Yield a unique logger short name and tear down handlers after the test.

    Ensures ``get_logger`` runs its ``setup_logging`` path on a fresh logger and
    that StreamHandlers are closed so they do not leak across tests.
    """
    name = f"ut_iso_{uuid.uuid4().hex[:16]}"
    yield name
    logger = logging.getLogger(f"ms_service_metric.{name}")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)


class TestGetLoggerGivenValidName:
    def test_when_get_logger_with_name_then_return_logger(self):
        logger = get_logger("test_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "ms_service_metric.test_logger"

    def test_when_get_logger_multiple_times_then_return_same_logger(self):
        logger1 = get_logger("test_logger")
        logger2 = get_logger("test_logger")
        assert logger1 is logger2

    def test_when_get_logger_with_empty_name_then_return_root_logger(self):
        logger = get_logger("")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "ms_service_metric."

    def test_when_get_logger_multiple_times_then_handlers_not_duplicated(
        self, isolated_ms_metric_logger_name
    ):
        """Calling get_logger twice must not append extra handlers on the same logger."""
        logger_name = isolated_ms_metric_logger_name

        logger1 = get_logger(logger_name)
        handler_count_first = len(logger1.handlers)
        assert handler_count_first > 0

        logger2 = get_logger(logger_name)
        handler_count_second = len(logger2.handlers)

        assert handler_count_first == handler_count_second
        assert logger1 is logger2


class TestGetLogLevelGivenEnvironmentVariable:
    def test_when_env_set_to_debug_then_return_debug_level(self, monkeypatch):
        monkeypatch.setenv("PROF_LOG_LEVEL", "DEBUG")
        assert get_log_level() == logging.DEBUG

    def test_when_env_set_to_info_then_return_info_level(self, monkeypatch):
        monkeypatch.setenv("PROF_LOG_LEVEL", "INFO")
        assert get_log_level() == logging.INFO

    def test_when_env_set_to_warning_then_return_warning_level(self, monkeypatch):
        monkeypatch.setenv("PROF_LOG_LEVEL", "WARNING")
        assert get_log_level() == logging.WARNING

    def test_when_env_set_to_error_then_return_error_level(self, monkeypatch):
        monkeypatch.setenv("PROF_LOG_LEVEL", "ERROR")
        assert get_log_level() == logging.ERROR

    def test_when_env_not_set_then_return_default_info_level(self, monkeypatch):
        monkeypatch.delenv("PROF_LOG_LEVEL", raising=False)
        assert get_log_level() == logging.INFO

    def test_when_env_set_to_invalid_value_then_return_default_info_level(self, monkeypatch):
        monkeypatch.setenv("PROF_LOG_LEVEL", "INVALID")
        assert get_log_level() == logging.INFO


class TestSetupLoggingGivenValidLogger:
    def test_when_setup_logging_then_handlers_are_configured(self):
        logger = logging.getLogger("test_setup_logging")
        setup_logging(logger)
        assert len(logger.handlers) > 0
        assert logger.level is not None

    def test_when_setup_logging_with_custom_level_then_level_is_set(self):
        logger = logging.getLogger("test_setup_logging_level")
        setup_logging(logger, level=logging.DEBUG)
        assert logger.level == logging.DEBUG


class TestLoggerFunctionality:
    def test_when_log_debug_message_then_no_error_raised(self):
        logger = get_logger("test_debug")
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("test debug message")
        assert True

    def test_when_log_info_message_then_no_error_raised(self):
        logger = get_logger("test_info")
        logger.info("test info message")
        assert True

    def test_when_log_warning_message_then_no_error_raised(self):
        logger = get_logger("test_warning")
        logger.warning("test warning message")
        assert True

    def test_when_log_error_message_then_no_error_raised(self):
        logger = get_logger("test_error")
        logger.error("test error message")
        assert True

    def test_when_log_exception_with_exc_info_then_no_error_raised(self):
        logger = get_logger("test_exception")
        try:
            raise ValueError("test exception")
        except ValueError:
            logger.exception("test exception message")
        assert True

