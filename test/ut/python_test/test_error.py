# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pytest
from unittest.mock import patch
from ms_service_profiler.utils.error import ExportError, ValidationError, ParseError, ColumnMissingError
from ms_service_profiler.utils.error import key_except, KeyExcept


def test_export_error_inheritance():
    assert issubclass(ExportError, Exception)


@pytest.mark.parametrize("message", [
    "File not found",
    "",
    123,
    None,
    {"key": "value"},
])
def test_export_error_initialization(message):
    error = ExportError(message)
    assert error.message == message


@pytest.mark.parametrize("message, expected_output", [
    ("Invalid format", "ExportError: Invalid format"),
    ("", "ExportError: "),
    (123, "ExportError: 123"),
    (None, "ExportError: None"),
    ({"key": "value"}, "ExportError: {'key': 'value'}"),
])
def test_export_error_str_representation(message, expected_output):
    error = ExportError(message)
    assert str(error) == expected_output


@pytest.mark.parametrize("key, message", [
    ("username", "Failed to parse data"),
    ("age", "Invalid value"),
    (12345, ""),
    (None, "Empty field"),
])
def test_validation_error_initialization(key, message):
    error = ValidationError(key, message)

    assert error.key == key
    assert error.message == message

    assert isinstance(error, ParseError)
    assert str(error) == f"{message}: {key}."


@pytest.mark.parametrize("key, message, expected_output", [
    ("email", "Invalid format", "Invalid format: email."),
    (404, "Missing field", "Missing field: 404."),
    (None, "", ": None."),
    ("", "Empty key", "Empty key: ."),
])
def test_validation_error_str_representation(key, message, expected_output):
    error = ValidationError(key, message)
    assert str(error) == expected_output


def test_parent_exception_behavior():
    with pytest.raises(ParseError) as excinfo:
        raise ValidationError("password", "Too weak")
    assert "Too weak: password." in str(excinfo.value)


@patch("ms_service_profiler.utils.error.logger.warning")
def test_key_except_decorator(mock_warning):
    @key_except("key1", "key2", ignore=False, msg="Custom message")
    def test_func(data):
        return data["key1"]

    # 测试正常情况
    data = {"key1": "value1"}
    assert test_func(data) == "value1"

    # 测试 KeyError 被捕获并重新抛出
    data = {"key3": "value3"}
    with pytest.raises(ColumnMissingError) as exc_info:
        test_func(data)
    assert "Custom message" in str(exc_info.value)

    # 测试 KeyError 被忽略
    @key_except("key1", "key2", ignore=True, msg="Custom message")
    def test_func_ignore(data):
        return data["key1"]

    data = {"key3": "value3"}
    test_func_ignore(data)
    mock_warning.assert_called_once_with(ColumnMissingError(("key1",), "Custom message"))


@patch("ms_service_profiler.utils.error.logger.warning")
def test_key_except_context_manager(mock_warning):
    def test_func(data):
        with KeyExcept("key1", "key2", ignore=False, msg="Custom message"):
            return data["key1"]

    # 测试正常情况
    data = {"key1": "value1"}
    assert test_func(data) == "value1"

    # 测试 KeyError 被捕获并重新抛出
    data = {"key3": "value3"}
    with pytest.raises(ColumnMissingError) as exc_info:
        test_func(data)
    assert "Custom message" in str(exc_info.value)

    # 测试 KeyError 被忽略
    def test_func_ignore(data):
        with KeyExcept("key1", "key2", ignore=True, msg="Custom message"):
            return data["key1"]

    data = {"key3": "value3"}
    test_func_ignore(data)
    mock_warning.assert_called_once_with(ColumnMissingError(("key1",), "Custom message"))
