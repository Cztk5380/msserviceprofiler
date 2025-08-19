# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd
from ms_service_profiler.processor.processor_base import ProcessorBase


class ProcessorMeta(ProcessorBase):

    @property
    def name(self):
        return "ProcessorMeta"

    def convert_to_format_str(self, x):
        try:
            return str(int(x))
        except Exception as ex:
            return x

    def parse_process_info(self, data_df):
        # 判断当前是调度进程还是执行进程
        # 获取父进程 id
        # 获取device id
        if data_df is None or data_df.empty:
            return dict()

        if "hostname" not in data_df or "pid" not in data_df or "name" not in data_df:
            return dict()
        
        if "from" in data_df:
            rid_map = data_df[data_df['from'].notna()].set_index("to").to_dict(orient='dict')["from"]
            rid_map = (
                {self.convert_to_format_str(k): self.convert_to_format_str(v) for k, v in rid_map.items()}
            )
        else:
            rid_map = None

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

        return dict(hostname=hostname, pid=str(pid), ppid=ppid, device_id=device_id,
                    is_forward=is_forward, rid_map=rid_map)

    def parse(self, data):
        data_df: pd.DataFrame = data.get("tx_data_df")
        data_meta: pd.DataFrame = data.get("meta", dict())
        data_meta.update(self.parse_process_info(data_df))

        return data_meta
