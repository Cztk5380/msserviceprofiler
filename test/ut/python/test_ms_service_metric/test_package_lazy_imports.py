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

"""Exercise ms_service_metric.__getattr__ lazy exports."""

import pytest


def test_lazy_import_symbol_watcher():
    import ms_service_metric as pkg

    cls = pkg.SymbolWatcher
    assert cls.__name__ == "SymbolWatcher"


def test_lazy_import_metric_control_watch():
    import ms_service_metric as pkg

    cls = pkg.MetricControlWatch
    assert cls.__name__ == "MetricControlWatch"


def test_getattr_unknown_raises():
    import ms_service_metric as pkg

    try:
        _ = pkg.this_attribute_does_not_exist_ever  # noqa: B018
        pytest.fail("expected AttributeError")
    except AttributeError as e:
        assert "no attribute" in str(e).lower()
