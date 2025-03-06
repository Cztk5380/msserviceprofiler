import pytest
from unittest.mock import Mock
from enum import Enum
from ms_service_profiler.utils.check.checker import CheckerInstence, CheckResult


class EnumInstance(Enum):
    NO_INSTANCE = 0
    VALID_INSTANCE = 1
    INVALID_INSTANCE = 2


@pytest.mark.parametrize("instance, converter", [
    (EnumInstance.NO_INSTANCE, None),
    (EnumInstance.VALID_INSTANCE, lambda x: (x, True, "")),
    (EnumInstance.INVALID_INSTANCE, lambda x: (x, False, "Invalid")),
])
def test_checker_instance_initialization(instance, converter):
    checker = CheckerInstence(instance, converter)
    assert checker.instance == instance
    assert checker.converter == converter


@pytest.mark.parametrize("instance, expected", [
    (EnumInstance.VALID_INSTANCE, True),
    (EnumInstance.INVALID_INSTANCE, True),
])
def test_has_instance(instance, expected):
    checker = CheckerInstence(instance)
    assert checker.has_instance() == expected


@pytest.mark.parametrize("instance", [
    EnumInstance.VALID_INSTANCE,
    EnumInstance.INVALID_INSTANCE,
])
def test_get_instance_and_value(instance):
    checker = CheckerInstence(instance)
    assert checker.get_instance() == instance
    assert checker.get_value() == instance


def test_convert_instance_without_converter():
    checker = CheckerInstence(EnumInstance.VALID_INSTANCE)
    result = checker.convert_instance()
    assert isinstance(result, CheckResult)
    assert result.passed


def test_convert_instance_with_converter_success():
    mock_converter = Mock(return_value=(EnumInstance.VALID_INSTANCE, True, ""))
    checker = CheckerInstence(EnumInstance.NO_INSTANCE, mock_converter)
    result = checker.convert_instance()
    mock_converter.assert_called_once_with(EnumInstance.NO_INSTANCE)
    assert result.passed
    assert result.msg == ""
    assert checker.instance == EnumInstance.VALID_INSTANCE


def test_convert_instance_with_converter_failure():
    mock_converter = Mock(return_value=(EnumInstance.INVALID_INSTANCE, False, "Invalid"))
    checker = CheckerInstence(EnumInstance.VALID_INSTANCE, mock_converter)
    result = checker.convert_instance()
    mock_converter.assert_called_once_with(EnumInstance.VALID_INSTANCE)
    assert not result.passed
    assert result.msg == "Invalid"
    assert checker.instance == EnumInstance.INVALID_INSTANCE