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

import unittest
from unittest.mock import patch
from ms_service_profiler.plugins.plugin_vllm_helper import VllmHelper


class TestVllmHelper(unittest.TestCase):

    def setUp(self):
        VllmHelper.vllm_req_map = {}

    def test_int_req(self):
        # 测试当rid不存在于vllm_req_map中时，int_req方法是否正确地创建了一个新的字典项
        rid = '123'
        VllmHelper.int_req(rid)
        self.assertIn(rid, VllmHelper.vllm_req_map)
        self.assertEqual(VllmHelper.vllm_req_map[rid]['batch_iter'], 0)
        self.assertEqual(VllmHelper.vllm_req_map[rid]['receiveToken'], 0)

    def test_add_req_batch_iter_new_rid(self):
        # 测试当rid不存在于vllm_req_map中时，add_req_batch_iter方法是否正确地创建了一个新的字典项并设置了receiveToken
        rid = '123'
        iter_size = 5
        VllmHelper.add_req_batch_iter(rid, iter_size)
        self.assertIn(rid, VllmHelper.vllm_req_map)
        self.assertEqual(VllmHelper.vllm_req_map[rid]['batch_iter'], 0)
        self.assertEqual(VllmHelper.vllm_req_map[rid]['receiveToken'], iter_size)

    def test_add_req_batch_iter_existing_rid(self):
        # 测试当rid存在于vllm_req_map中且receiveToken为0时，add_req_batch_iter方法是否正确地设置了receiveToken
        rid = '123'
        iter_size = 5
        VllmHelper.int_req(rid)
        VllmHelper.add_req_batch_iter(rid, iter_size)
        self.assertEqual(VllmHelper.vllm_req_map[rid]['receiveToken'], iter_size)
