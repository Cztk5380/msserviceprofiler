# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger


class PluginBatch(PluginBase):
    name = "plugin_batch"
    depends = ["plugin_common", "plugin_req_status"]
    batch_req = dict()
    batch_exec = dict()
    batch_list = dict()

    @classmethod
    def add_req_info(cls, batch_id, req_id, **values):
        cls.batch_req.setdefault((batch_id, req_id), dict(batch_id=batch_id, req_id=req_id))
        cls.batch_req[(batch_id, req_id)].update(**values)

    @classmethod
    def add_exec_info(cls, batch_id, pid, exec_name, start, end):
        cls.batch_exec.setdefault((batch_id, pid, exec_name), (batch_id, exec_name, pid, start, end))

    @classmethod
    def clear_batch(cls, time):
        pop_keys = []
        for key, value in cls.batch_list.items():
            if value.get("time", time) < time:
                pop_keys.append(key)
        for k in pop_keys:
            cls.batch_list.pop(k)

    @classmethod
    def deal_with_batch_row(cls, row, batch_index):
        cls.clear_batch(row.start_time)
        cls.batch_list[tuple(row.rid_list)] = dict()
        cls.batch_list[tuple(row.rid_list)]["id"] = batch_index
        cls.add_exec_info(batch_index, row.pid, row.name, row.start_time, row.end_time)
        for rinfo in row.res_list:
            if isinstance(rinfo, dict):
                rid = rinfo.get("rid")
                cls.add_req_info(batch_index, rid, **rinfo)

    @classmethod
    def deal_with_model_exec_row(cls, row):
        batch_info = cls.batch_list.get(tuple(row.rid_list))
        if batch_info is None:
            return
        batch_id = batch_info.get("id", 0)
        if batch_id == 0:
            return
        cls.batch_list[tuple(row.rid_list)]["time"] = row.end_time
        cls.add_exec_info(batch_id, row.pid, row.name, row.start_time, row.end_time)

    @classmethod
    def deal_with_preprocess_row(cls, row, last_preprocess):
        batch_info = cls.batch_list.get(tuple(row.rid_list))
        if batch_info is None:
            return
        batch_id = batch_info.get("id", 0)
        if batch_id == 0:
            return
        last_preprocess[(row.pid, row.tid, row.hostname)] = dict(rid_list=row.rid_list)
        cls.add_exec_info(batch_id, row.pid, row.name, row.start_time, row.end_time)
        try:
            if row.blocks and len(row.blocks) != len(row.rid_list):
                return
        except AttributeError as ex:
            return
        for index, rid in enumerate(row.rid_list):
            cls.add_req_info(batch_id, rid, block=row.blocks[index])

    @classmethod
    def deal_with_forward_row(cls, row, last_preprocess):
        rid_list = last_preprocess.get((row.pid, row.tid, row.hostname), dict()).get("rid_list", None)
        if rid_list is None:
            return
        batch_info = cls.batch_list.get(tuple(rid_list))
        if batch_info is None:
            return
        batch_id = batch_info.get("id", 0)
        if batch_id == 0:
            return
        if batch_info.get("time", 0) > row.end_time:
            cls.add_exec_info(batch_id, row.pid, row.name, row.start_time, row.end_time)

    @classmethod
    def extract_batch_info(cls, batch_df):
        last_preprocess = dict()
        batch_index = 0
        for row in batch_df.itertuples():
            if row.name in ('BatchSchedule', 'batchFrameworkProcessing'):
                batch_index = batch_index + 1
                cls.deal_with_batch_row(row, batch_index)
            if row.name == 'modelExec':
                cls.deal_with_model_exec_row(row)
            if row.name == 'preprocess':
                cls.deal_with_preprocess_row(row, last_preprocess)
            if row.name == 'forward':
                cls.deal_with_forward_row(row, last_preprocess)

    @classmethod
    @timer(logger.info)
    def parse(cls, data):
        tx_data_df = data.get('tx_data_df')
        if tx_data_df is None:
            raise ValueError("tx_data_df is None")

        batch_df = tx_data_df[tx_data_df['name'].isin(['BatchSchedule', 'batchFrameworkProcessing', \
            'modelExec', 'preprocess', 'forward'])]

        # 从 preprocess 中读取 res_list 和 rid_list 信息到它后面的 forward
        batch_df = batch_df.sort_values(by=['hostname', 'start_time', 'pid', 'tid'])
        cls.extract_batch_info(batch_df)

        data['batch_req_df'] = pd.DataFrame(cls.batch_req.values())
        data['batch_exec_df'] = pd.DataFrame(cls.batch_exec.values(),
            columns=["batch_id", "name", "pid", "start", "end"])
        return data
