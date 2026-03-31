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

from ms_service_metric.utils.exceptions import (
    ConfigError,
    HandlerError,
    HookError,
    MetricsError,
    ServiceMetricError,
    SharedMemoryError,
    SymbolError,
)


class TestServiceMetricErrorGivenVariousInputs:
    def test_given_message_only_when_constructed_then_str_is_message(self):
        error = ServiceMetricError("test message")
        assert str(error) == "test message"

    def test_given_message_and_error_code_when_constructed_then_str_contains_both(self):
        error = ServiceMetricError("test message", error_code="E001")
        assert "[E001]" in str(error)
        assert "test message" in str(error)


class TestConfigErrorGivenInvalidConfiguration:
    def test_given_config_error_when_constructed_then_is_service_metric_subclass(self):
        error = ConfigError("config error")
        assert isinstance(error, ServiceMetricError)


class TestSymbolErrorGivenInvalidSymbol:
    def test_given_symbol_error_when_constructed_then_is_service_metric_subclass(self):
        error = SymbolError("symbol error")
        assert isinstance(error, ServiceMetricError)


class TestHandlerErrorGivenInvalidHandler:
    def test_given_handler_error_when_constructed_then_is_service_metric_subclass(self):
        error = HandlerError("handler error")
        assert isinstance(error, ServiceMetricError)


class TestHookErrorGivenHookFailure:
    def test_given_hook_error_when_constructed_then_is_service_metric_subclass(self):
        error = HookError("hook error")
        assert isinstance(error, ServiceMetricError)


class TestMetricsErrorGivenMetricFailure:
    def test_given_metrics_error_when_constructed_then_is_service_metric_subclass(self):
        error = MetricsError("metrics error")
        assert isinstance(error, ServiceMetricError)


class TestSharedMemoryErrorGivenShmFailure:
    def test_given_shm_error_when_constructed_then_is_service_metric_subclass(self):
        error = SharedMemoryError("shm error")
        assert isinstance(error, ServiceMetricError)

class TestServiceMetricErrorGivenEdgeCases:
    def test_given_empty_message_when_constructed_then_str_is_empty(self):
        error = ServiceMetricError("")
        assert str(error) == ""

    def test_given_none_message_when_constructed_then_str_raises_type_error(self):
        error = ServiceMetricError(None)
        import pytest

        with pytest.raises(TypeError):
            str(error)


class TestExceptionSubclassesGivenErrorCode:
    def test_given_config_error_with_error_code_when_constructed_then_str_contains_both(self):
        error = ConfigError("config error", error_code="C001")
        assert "[C001]" in str(error)
        assert "config error" in str(error)

    def test_given_symbol_error_with_error_code_when_constructed_then_str_contains_both(self):
        error = SymbolError("symbol error", error_code="S001")
        assert "[S001]" in str(error)

    def test_given_handler_error_with_error_code_when_constructed_then_str_contains_both(self):
        error = HandlerError("handler error", error_code="H001")
        assert "[H001]" in str(error)

    def test_given_hook_error_with_error_code_when_constructed_then_str_contains_both(self):
        error = HookError("hook error", error_code="K001")
        assert "[K001]" in str(error)

    def test_given_metrics_error_with_error_code_when_constructed_then_str_contains_both(self):
        error = MetricsError("metrics error", error_code="M001")
        assert "[M001]" in str(error)

    def test_given_shm_error_with_error_code_when_constructed_then_str_contains_both(self):
        error = SharedMemoryError("shm error", error_code="SHM1")
        assert "[SHM1]" in str(error)
