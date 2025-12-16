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

class VllmHelper:
    vllm_req_map = {}

    @classmethod
    def int_req(cls, rid):
        if cls.vllm_req_map.get(rid) is None:
            cls.vllm_req_map[rid] = {}
            cls.vllm_req_map[rid]['batch_iter'] = 0
            cls.vllm_req_map[rid]['receiveToken'] = 0
        return cls.vllm_req_map

    @classmethod
    def add_req_batch_iter(cls, rid, iter_size):
        if cls.vllm_req_map.get(rid) is not None and cls.vllm_req_map[rid]['receiveToken'] == 0:
            cls.vllm_req_map[rid]['receiveToken'] = iter_size
        elif cls.vllm_req_map.get(rid) is not None:
            cls.vllm_req_map[rid]['batch_iter'] += iter_size
        else:
            VllmHelper.int_req(rid)
            cls.vllm_req_map[rid]['receiveToken'] = iter_size
        return cls.vllm_req_map[rid]['batch_iter']