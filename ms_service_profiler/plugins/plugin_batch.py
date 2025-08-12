# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import KeyExcept
from ms_service_profiler.constant import LARGE_TIME_STAMP


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
                rid = str(rinfo.get("rid"))
                rinfo["rid"] = rid
                cls.add_req_info(batch_index, rid, **rinfo)

    @classmethod
    def deal_with_model_exec_row(cls, row):
        batch_info = cls.batch_list.get(tuple(row.rid_list))
        if batch_info is None:
            return
        batch_id = batch_info.get("id", 0)
        if batch_id == 0:
            return
        if row.name == 'modelExec':
            cls.batch_list[tuple(row.rid_list)]["time"] = row.end_time
        else:
            cls.batch_list[tuple(row.rid_list)]["time"] = LARGE_TIME_STAMP
        cls.add_exec_info(batch_id, row.pid, row.name, row.start_time, row.end_time)

    @classmethod
    def _add_blocks_for_batch(cls, batch_id, rid_list, blocks):
        def is_invalid_block(value):
            """通用缺失值检测"""
            try:
                return pd.isna(value)
            except TypeError:
                # 处理非标准类型（如字符串、对象等）
                return False

        if not batch_id or not rid_list or not blocks:
            return False

        try:
            if blocks is None:
                return False

            # 长度验证
            if len(blocks) != len(rid_list):
                return False

            # 通用缺失值检测
            has_nan = any(is_invalid_block(b) for b in blocks)
            if has_nan:
                return False

            # 添加block信息
            for rid, block in zip(rid_list, blocks):
                # 类型安全转换
                clean_block = float(block) if not pd.isna(block) else 0.0
                cls.add_req_info(batch_id, rid, block=clean_block)

            # 状态标记优化
            cls.batch_req.get(batch_id, {}).update({"block_processed": True})
            return True
        except Exception as e:
            error_msg = f"Block addition failed: {type(e).__name__} - {str(e)}"
            if isinstance(e, (TypeError, ValueError)):
                logger.warning(f"Data validation error: {error_msg}")
            else:
                logger.error(f"System exception: {error_msg}", exc_info=True)
            return False

    @classmethod
    def deal_with_preprocess_row(cls, row, last_preprocess, batch_index):
        if not cls.batch_req:
            return

        # 获取未分配block的batch
        unassigned_batches = [b for b in cls.batch_req.values() if "block" not in b]

        # 旧版逻辑：通过rid_list查找batch
        if row.rid_list:  # 旧版数据
            batch_info = cls.batch_list.get(tuple(row.rid_list))
            batch_id = batch_info.get("id", 0) if batch_info else 0
            if not batch_id and unassigned_batches:
                batch_id = unassigned_batches[0]["batch_id"]

        # 新版逻辑：无rid_list时使用未分配batch
        else:
            batch_id = (
                unassigned_batches[0].get('batch_id', 0)
                if unassigned_batches and isinstance(unassigned_batches[0], dict)
                else 0
            )
            cls.add_exec_info(batch_index, row.pid, row.name, row.start_time, row.end_time)

        if not batch_id:
            return

        # 更新缓存
        last_preprocess[(row.pid, row.tid, row.hostname)] = {
            "batch_id": batch_id
        }

        # 记录执行信息
        cls.add_exec_info(batch_index, row.pid, row.name, row.start_time, row.end_time)

        # 旧版特有：在preprocess中处理blocks
        if row.rid_list and row.blocks:  # 旧版数据
            cls._add_blocks_for_batch(batch_id, row.rid_list, row.blocks)

    @classmethod
    def deal_with_forward_row(cls, row, last_preprocess, batch_index):
        # 获取缓存数据
        cache_key = (row.pid, row.tid, row.hostname)
        cached_data = last_preprocess.get(cache_key, {})
        batch_id = cached_data.get("batch_id")

        cls.add_exec_info(batch_index, row.pid, row.name, row.start_time, row.end_time)

        # 回退逻辑：新版数据可能通过rid_list查找
        if not batch_id and row.rid_list:  # 新版数据
            batch_info = cls.batch_list.get(tuple(row.rid_list))
            if batch_info:
                batch_id = batch_info.get("id", 0)

        # 最终回退：使用未分配batch
        if not batch_id:
            unassigned = next((b for b in cls.batch_req.values() if "block" not in b), None)
            batch_id = unassigned["batch_id"] if unassigned else 0

        if not batch_id:
            return

        # 新版特有：在forward中处理blocks
        if row.rid_list and row.blocks:  # 新版数据
            cls._add_blocks_for_batch(batch_id, row.rid_list, row.blocks)

    @classmethod
    def extract_batch_info(cls, batch_df):
        last_preprocess = dict()
        batch_index = 0
        for row in batch_df.itertuples():
            if row.name in ('BatchSchedule', 'batchFrameworkProcessing'):
                batch_index = batch_index + 1
                cls.deal_with_batch_row(row, batch_index)
            if row.name in ('modelExec', 'Execute'):
                cls.deal_with_model_exec_row(row)
            if row.name == 'preprocess':
                cls.deal_with_preprocess_row(row, last_preprocess, batch_index)
            if row.name == 'forward':
                cls.deal_with_forward_row(row, last_preprocess, batch_index)

    @classmethod
    @timer(logger.info)
    def parse(cls, data):
        with KeyExcept('name', 'hostname', 'pid', 'tid', 'start_time', ignore=True,
            msg="ignoring current process by default."):

            tx_data_df = data.get('tx_data_df')
            if tx_data_df is None:
                raise ValueError("tx_data_df is None")

            batch_df = tx_data_df[tx_data_df['name'].isin(['BatchSchedule', 'batchFrameworkProcessing', \
                'modelExec', 'preprocess', 'forward', 'Execute'])]

            # 从 preprocess 中读取 res_list 和 rid_list 信息到它后面的 forward
            batch_df = batch_df.sort_values(by=['hostname', 'start_time', 'pid', 'tid'])
            cls.extract_batch_info(batch_df)

            data['batch_req_df'] = pd.DataFrame(cls.batch_req.values())
            data['batch_exec_df'] = pd.DataFrame(cls.batch_exec.values(),
                columns=["batch_id", "name", "pid", "start", "end"])
        return data
