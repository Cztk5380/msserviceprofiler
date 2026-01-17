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
import numpy as np
import pytest

from ms_serviceparam_optimizer.inference.common import get_bins_and_label, \
    get_field_bins_count  


def test_get_bins_and_label():
    # Test case 1: Test with default parameters
    result = get_bins_and_label('test')
    assert "label" in result
    assert "bins" in result
    assert len(result["label"]) == 51
    assert len(result["bins"]) == 52
    assert len([True for k in result["label"] if k.startswith("test")]) == 51
    assert result["bins"][-1] == float('inf')
    assert result["bins"][0] == 0


class RequestInfo:
    def __init__(self, field):
        self.field = field


def test_get_field_bins_count_empty_target():
    target = []
    field = 'field'
    bins = [0, 1, 2, 3]
    assert get_field_bins_count(target, field, bins) == [0, 0, 0]


def test_get_field_bins_count_no_field():
    target = [RequestInfo(None)]
    field = 'field'
    bins = [0, 1, 2, 3]
    with pytest.raises(TypeError):
        get_field_bins_count(target, field, bins)


def test_get_field_bins_count_field_is_zero():
    target = [RequestInfo(0)]
    field = 'field'
    bins = [0, 1, 2, 3]
    assert np.array_equal(get_field_bins_count(target, field, bins), np.array([1, 0, 0]))


def test_get_field_bins_count_field_is_non_zero():
    target = [RequestInfo(1), RequestInfo(2), RequestInfo(3)]
    field = 'field'
    bins = [0, 1, 2, 3]
    assert np.array_equal(np.array([0, 1, 2]), get_field_bins_count(target, field, bins))
