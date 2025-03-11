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

    def test_add_req_batch_iter_existing_rid_with_receiveToken(self):
        # 测试当rid存在于vllm_req_map中且receiveToken不为0时，add_req_batch_iter方法是否正确地增加了batch_iter
        rid = '123'
        iter_size = 5
        VllmHelper.int_req(rid)
        VllmHelper.vllm_req_map[rid]['receiveToken'] = 1
        VllmHelper.add_req_batch_iter(rid, iter_size)
        self.assertEqual(VllmHelper.vllm_req_map[rid]['batch_iter'], iter_size)
