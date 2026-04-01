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

"""Extra branch coverage for utils/version.py (complements test_version_utils.py)."""

import types
from unittest.mock import patch

from ms_service_metric.utils.version import check_version_match, get_package_version


def test_given_only_min_bound_when_check_version_match_then_respects_min():
    assert check_version_match("1.5.0", "1.0.0", None) is True
    assert check_version_match("0.5.0", "1.0.0", None) is False


def test_given_only_max_bound_when_check_version_match_then_respects_max():
    assert check_version_match("1.5.0", None, "2.0.0") is True
    assert check_version_match("3.0.0", None, "2.0.0") is False


def test_given_metadata_version_raises_when_get_package_version_then_falls_back_to_module_version():
    fake_mod = types.ModuleType("fallback_pkg")
    fake_mod.__version__ = "2.0.0"
    with patch("importlib.metadata.version", side_effect=RuntimeError("no metadata")):
        with patch("importlib.import_module", return_value=fake_mod):
            assert get_package_version("fallback_pkg") == "2.0.0"


def test_given_metadata_and_import_fail_when_get_package_version_then_none():
    with patch("importlib.metadata.version", side_effect=RuntimeError("no metadata")):
        with patch("importlib.import_module", side_effect=ImportError("no module")):
            assert get_package_version("missing_pkg") is None
