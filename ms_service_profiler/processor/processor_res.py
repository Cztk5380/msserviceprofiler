# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd
import numpy as np
from ms_service_profiler.processor.processor_base import ProcessorBase
from ms_service_profiler.plugins.plugin_vllm_helper import VllmHelper
from ms_service_profiler.utils.log import logger


class ProcessorRes(ProcessorBase):

    @property
    def name(self):
        return "ProcessorRes"

    @staticmethod
    def parse_process_info(data_df, index):
        # 判断当前是调度进程还是执行进程
        # 获取父进程 id
        # 获取device id
        if data_df is None or data_df.empty:
            return dict()

        if "hostname" not in data_df or "pid" not in data_df or "name" not in data_df:
            return dict()

        hostname = data_df.iloc[-1]["hostname"]
        pid = data_df.iloc[-1]["pid"]
        is_forward = any(data_df["name"] == "forward")
        ppid = None
        device_id = None

        if "ppid" in data_df:
            ppid_info_df = data_df[data_df["ppid"].notna()]
            if not ppid_info_df.empty:
                ppid = ppid_info_df.iloc[-1]["ppid"]
        
        if "deviceid" in data_df:
            deviceid_info_df = data_df[data_df["deviceid"].notna()]
            if not deviceid_info_df.empty:
                device_id = deviceid_info_df.iloc[-1]["deviceid"]

        return dict(hostname=hostname, pid=str(pid), index=index,
                    ppid=ppid, device_id=device_id, is_forward=is_forward, 
                    df=data_df)

    def convert_to_format_str(self, x):
        try:
            return str(int(x))
        except Exception as ex:
            return x

    def get_mapping_rid(self, rid, rid_map):
        format_rid = self.convert_to_format_str(rid)
        if rid_map is None:
            return format_rid
        else:
            return rid_map.get(format_rid, format_rid)

    def mapping_rid(self, rid, rid_map):
        if isinstance(rid, list):
            return [self.mapping_rid(i, rid_map) for i in rid]

        if isinstance(rid, dict):
            if 'rid' in rid:
                rid['rid'] = self.get_mapping_rid(rid['rid'], rid_map)
            return rid

        return self.get_mapping_rid(rid, rid_map)

    # 只有vllm框架数据解析会走这部分流程，从batchSchdule中的iter_size中获取迭代信息
    def extract_iter_from_batch(self, req):
        rid = req.get('rid')
        iter_size = req.get('iter_size')
        return VllmHelper.add_req_batch_iter(rid, iter_size)

    def extract_ids_from_reslist(self, rid):
        rid_list = []
        token_id_list = []
        dp_list = []

        for req in rid:
            if isinstance(req, dict):
                rid_list.append(req.get('rid'))
                if req.get('iter_size'):  # iter_size 为vllm数据采集特有字段
                    token_id_list.append(self.extract_iter_from_batch(req))
                elif req.get('dp'):  # dp域信息
                    dp_list.append(req.get('dp'))
                else:
                    token_id_list.append(req.get('iter'))
            else:
                rid_list.append(req)
                token_id_list.append(None)

        return rid_list, token_id_list, dp_list

    def extract_rid(self, rid):
        rid_list, token_id_list, dp_list = None, None, None

        if isinstance(rid, list):
            rid_list, token_id_list, dp_list = self.extract_ids_from_reslist(rid)
            rid = ','.join(map(str, rid_list))

        return rid, rid_list, token_id_list, dp_list


    def process_each_df(self, data_df, rid_map):
        if 'rid' not in data_df.columns:
            return
        # 映射rid
        data_df['res_list'] = data_df['rid'].map(lambda x: self.mapping_rid(x, rid_map))
        # 提取rid中的各种信息
        extract_df = data_df['res_list'].map(lambda x: self.extract_rid(x))
        data_df[['rid', 'rid_list', 'token_id_list', 'dp_list']] = pd.DataFrame(
            extract_df.tolist(), index=data_df.index
        )

    def can_convert_to_int(self, x):
        try:
            int(x)
            return True
        except Exception as _:
            return False


    def parse(self, data, meta_data, meta_data_list):
        data_df = data.get("tx_data_df")
        if data_df is None:
            return data
        
        rid_map = dict()
        if meta_data.get("is_forward", False) is False:
            rid_map = meta_data.get("rid_map")

            self.process_each_df(data_df, rid_map)
            # 删除from to
            if "from" in data_df:
                data["tx_data_df"] = data_df[data_df['from'].isna()]
        else:
            hostname = meta_data.get("hostname")
            ppid = meta_data.get("ppid")

            rid_map_all = {}
            for meta_data_process in meta_data_list:
                rid_map_all.update(meta_data_process.get("rid_map") or {})

            # 兼容最开始数值的 rid ,如果是数值，那么绝对会重复
            if all(self.can_convert_to_int(x) for x in rid_map_all.keys()):
                rid_map_all = {}

            for meta_data_process in meta_data_list:
                if meta_data_process.get("hostname") == hostname and meta_data_process.get("pid") == ppid:
                    rid_map = meta_data_process.get("rid_map")
                    break
            else:
                rid_map = rid_map_all
            self.process_each_df(data_df, rid_map)

        return data