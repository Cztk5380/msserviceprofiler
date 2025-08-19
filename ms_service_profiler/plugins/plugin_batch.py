# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

def add_req_info(cls, batch_id, req_id, **values):
    cls.batch_req.setdefault((batch_id, req_id), dict(batch_id=batch_id, req_id=req_id))
    cls.batch_req[(batch_id, req_id)].update(**values)
