# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd

from ms_service_profiler.processor.processor_base import ProcessorBase


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

    def mapping_rid(self, rid, rid_map):
        if isinstance(rid, list):
            return [self.mapping_rid(i, rid_map) for i in rid]
        elif isinstance(rid, dict):
            if 'rid' in rid:
                rid['rid'] = rid_map.get(rid['rid'], rid['rid'])
            return rid
        else:
            return rid_map.get(rid, rid)

    def parse(self, data):
        process_list = list()
        rid_map_of_process = dict()

        for index, one_msporf_data in enumerate(data):
            data_df: pd.DataFrame = one_msporf_data.get("tx_data_df")
            process_list.append(self.parse_process_info(data_df, index))

        # 处理 调度 进程， 获取 rid map
        for process_info in process_list:
            if process_info.get("is_forward", False) is False:
                data_df = process_info.get("df")
                index = process_info.get("index")

                if "from" not in data_df or "to" not in data_df:
                    continue

                rid_map = data_df[data_df['from'].notna()].set_index("to").to_dict(orient='dict')["from"]
                rid_map.update({"{:g}".format(k): v for k, v in rid_map.items()})
                data[index]["tx_data_df"] = data_df[data_df['from'].isna()]

                hostname = process_info.get("hostname")
                pid = process_info.get("pid")
                rid_map_of_process.setdefault((hostname, pid), dict())
                rid_map_of_process[(hostname, pid)].update(rid_map)

                data_df['rid'] = data_df['rid'].map(lambda x: self.mapping_rid(x, rid_map))
        
        # 处理 forward 进程
        for process_info in process_list:
            if process_info.get("is_forward", False) is True:
                data_df = process_info.get("df")
                hostname = process_info.get("hostname")
                ppid = process_info.get("ppid")
                rid_map = rid_map_of_process.get((hostname, ppid))
                if rid_map is None:
                    continue

                data_df['rid'] = data_df['rid'].map(lambda x: self.mapping_rid(x, rid_map))

        return data
