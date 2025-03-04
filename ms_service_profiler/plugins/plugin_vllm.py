# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

class VllmHelper:
    vllm_req_map = {}

    @classmethod
    def int_req(cls, rid):
        if cls.vllm_req_map.get(rid) is None:
            cls.vllm_req_map[rid] = {}
            cls.vllm_req_map[rid]['batch_iter'] = 0
            cls.vllm_req_map[rid]['model_exec_iter'] = 0
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

    @classmethod
    def get_receive_token(cls, rid):
        if cls.vllm_req_map.get(rid) is not None:
            return cls.vllm_req_map[rid]['receiveToken']
        return 0

    @classmethod
    def get_reply_token(cls, rid):
        if cls.vllm_req_map.get(rid) is not None:
            return cls.vllm_req_map[rid]['batch_iter']
        return 0

    @classmethod
    def is_vllm_parse(cls):
        return len(cls.vllm_req_map) != 0