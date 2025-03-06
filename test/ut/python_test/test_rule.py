# test_rule.py
import pytest
from unittest.mock import Mock, patch
from ms_service_profiler.utils.check.rule import Rule


def test_rule_none():
    mock_checker = Mock()
    mock_checker.is_none.return_value = mock_checker

    with patch("ms_service_profiler.utils.check.rule.Checker", return_value=mock_checker):
        result = Rule.none()
        mock_checker.is_none.assert_called_once()
        assert result == mock_checker


def test_rule_path():
    mock_path_checker = Mock()
    with patch("ms_service_profiler.utils.check.rule.PathChecker", return_value=mock_path_checker):
        result = Rule.path()
        assert result == mock_path_checker


def test_rule_config_file():
    mock_path_checker = Mock()

    methods = ["exists", "is_file", "is_readable", "is_not_writable_to_others",
               "is_safe_parent_dir", "max_size", "as_default"]
    for method in methods:
        getattr(mock_path_checker, method).return_value = mock_path_checker

    with patch("ms_service_profiler.utils.check.rule.PathChecker", return_value=mock_path_checker):
        Rule.config_file()

        mock_path_checker.exists.assert_called_once()
        mock_path_checker.is_file.assert_called_once()
        mock_path_checker.is_readable.assert_called_once()
        mock_path_checker.is_not_writable_to_others.assert_called_once()
        mock_path_checker.is_safe_parent_dir.assert_called_once()
        mock_path_checker.max_size.assert_called_once_with(10_000_000)
        mock_path_checker.as_default.assert_called_once()


@pytest.mark.parametrize("method_name, expected_args", [
    ("exists", ()),
    ("is_file", ()),
    ("is_readable", ()),
    ("is_not_writable_to_others", ()),
    ("is_safe_parent_dir", ()),
    ("max_size", (10_000_000,)),
    ("as_default", ()),
])
def test_config_file_methods(method_name, expected_args):
    mock_path_checker = Mock()

    methods = ["exists", "is_file", "is_readable", "is_not_writable_to_others",
               "is_safe_parent_dir", "max_size", "as_default"]
    for method in methods:
        getattr(mock_path_checker, method).return_value = mock_path_checker

    with patch("ms_service_profiler.utils.check.rule.PathChecker", return_value=mock_path_checker):
        Rule.config_file()
        getattr(mock_path_checker, method_name).assert_called_once_with(*expected_args)