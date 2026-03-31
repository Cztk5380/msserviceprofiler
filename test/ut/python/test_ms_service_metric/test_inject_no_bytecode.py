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

"""inject.BYTECODE_AVAILABLE False path."""

from unittest.mock import patch

import pytest


def test_given_bytecode_disabled_when_inject_function_then_raises_import_error():
    import ms_service_metric.core.hook.inject as inj

    with patch.object(inj, "BYTECODE_AVAILABLE", False):
        with pytest.raises(ImportError, match="bytecode"):
            inj.inject_function(lambda: None, [])
