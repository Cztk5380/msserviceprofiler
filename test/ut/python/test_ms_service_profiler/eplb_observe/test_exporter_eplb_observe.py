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

import numpy as np

from ms_service_profiler.exporters.exporter_eplb_observe import draw_hot_map_from_arr, remap_expert_hot

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
