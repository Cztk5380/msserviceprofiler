# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pytest
from ms_service_profiler.utils.error import ExportError, ValidationError, ParseError


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