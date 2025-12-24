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

import os
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from ms_service_profiler.exporters.exporter_eplb_observe import (
    draw_hot_map_from_arr, remap_expert_hot, get_x_ticks, draw_balance_ratio)


class TestDrawHotMapFromArr(unittest.TestCase):
    def setUp(self):
        self.output_path = "test_hot_map.png"
        self.arr_valid = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.arr_invalid = np.array([1, 2, 3])

    def tearDown(self):
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def test_valid_input(self):
        try:
            draw_hot_map_from_arr(self.arr_valid, title="Test Title", x_label="X Label", y_label="Y Label", output_path=self.output_path)
            self.assertTrue(os.path.exists(self.output_path))
        except Exception as e:
            self.fail(f"Test failed with exception: {e}")

    def test_invalid_arr_shape(self):
        with self.assertRaises(ValueError) as context:
            draw_hot_map_from_arr(self.arr_invalid)
        self.assertEqual(str(context.exception), "arr shape size != 2")

    def test_empty_title(self):
        try:
            draw_hot_map_from_arr(self.arr_valid, title="", output_path=self.output_path)
            self.assertTrue(os.path.exists(self.output_path))
        except Exception as e:
            self.fail(f"Test failed with exception: {e}")

    def test_empty_x_label(self):
        try:
            draw_hot_map_from_arr(self.arr_valid, x_label="", output_path=self.output_path)
            self.assertTrue(os.path.exists(self.output_path))
        except Exception as e:
            self.fail(f"Test failed with exception: {e}")

    def test_empty_y_label(self):
        try:
            draw_hot_map_from_arr(self.arr_valid, y_label="", output_path=self.output_path)
            self.assertTrue(os.path.exists(self.output_path))
        except Exception as e:
            self.fail(f"Test failed with exception: {e}")

    def test_output_path(self):
        custom_output_path = "custom_test_hot_map.png"
        try:
            draw_hot_map_from_arr(self.arr_valid, output_path=custom_output_path)
            self.assertTrue(os.path.exists(custom_output_path))
        finally:
            if os.path.exists(custom_output_path):
                os.remove(custom_output_path)


class TestRemapExpertHot(unittest.TestCase):
    def test_remap_expert_hot(self):
        expert_map_per_eplb = np.array([[0, 1], [1, 0]])
        expert_hot_summed_expert = np.array([[1, 2], [3, 4]])
        expected_output = np.array([[1, 2], [4, 3]])
        self.assertTrue(np.array_equal(remap_expert_hot(expert_map_per_eplb, expert_hot_summed_expert), expected_output))

    def test_remap_expert_hot_different_shape(self):
        expert_map_per_eplb = np.array([[0, 1], [1, 0]])
        expert_hot_summed_expert = np.array([[1, 2]])
        with self.assertRaises(ValueError):
            remap_expert_hot(expert_map_per_eplb, expert_hot_summed_expert)

    def test_remap_expert_hot_single_element(self):
        expert_map_per_eplb = np.array([[0]])
        expert_hot_summed_expert = np.array([[1]])
        expected_output = np.array([[1]])
        self.assertTrue(np.array_equal(remap_expert_hot(expert_map_per_eplb, expert_hot_summed_expert), expected_output))


class TestGetXticks(unittest.TestCase):
    def test_x_less_than_100(self):
        # 测试x小于100的情况
        self.assertEqual(get_x_ticks(0), [0])
        self.assertEqual(get_x_ticks(1), [0, 1])
        self.assertEqual(get_x_ticks(99), [i for i in range(100)])

    def test_x_greater_than_or_equal_to_100(self):
        # 测试x大于等于100的情况
        self.assertEqual(get_x_ticks(100), [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        self.assertEqual(get_x_ticks(150), [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150])

    def test_x_equal_to_1000(self):
        # 测试x等于1000的情况
        self.assertEqual(get_x_ticks(1000), [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])

    def test_x_greater_than_1000(self):
        # 测试x大于1000的情况
        self.assertEqual(get_x_ticks(1001), [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
        self.assertEqual(get_x_ticks(2000), [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000,
                                             1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000])


class TestDrawBalanceRatio(unittest.TestCase):
    def setUp(self):
        self.output_path = "test_hot_map.png"
        self.std_balance_ratio = [0.5, 0.6, 0.7, 0.8, 0.9]
        self.rebalanced_time_points = [1, 3]
        self.d_time = ['2023-01-01 12:00:00', '2023-01-01 12:01:00']
        self.figsize = (60, 8)
        self.output_path = "balance_ratio.png"

    def tearDown(self):
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def test_valid_input(self):
        try:
            draw_balance_ratio(self.std_balance_ratio, self.rebalanced_time_points, self.d_time, figsize=self.figsize,
                               output_path=self.output_path)
            self.assertTrue(os.path.exists(self.output_path))
        except Exception as e:
            self.fail(f"Test failed with exception: {e}")

    def test_output_path(self):
        custom_output_path = "custom_test_hot_map.png"
        try:
            draw_balance_ratio(self.std_balance_ratio, self.rebalanced_time_points, self.d_time, figsize=self.figsize,
                               output_path=custom_output_path)
            self.assertTrue(os.path.exists(custom_output_path))
        finally:
            if os.path.exists(custom_output_path):
                os.remove(custom_output_path)
