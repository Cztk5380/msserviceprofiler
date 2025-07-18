# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import json

import pandas as pd
from pathlib import Path
import sqlite3

from json import JSONDecodeError

from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.error import LoadDataError
from ms_service_profiler.utils.file_open_check import ms_open
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.parse import gen_msprof_command, run_msprof_command, clear_last_msprof_output, is_need_msprof
from ms_service_profiler.constant import US_PER_SECOND


@Task.register("data_source:msprof")
class MsprofDataSource(BaseDataSource):

    @classmethod
    def get_prof_paths(cls, input_path: str):
        filepaths = []
        for dp in Path(input_path).glob("**/PROF_*"):
            if dp.is_dir():
                filepaths.append(dp)

        return filepaths

    @classmethod
    def load_tx_data(cls, db_path):
        if db_path is None:
            return None
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT pid, tid, event_type, start_time, end_time, mark_id, message "
            "FROM MsprofTxEx order by start_time "
        )
        all_data = cursor.fetchall()

        columns = [description[0] if description[0] != "message" else "ori_msg" for description in cursor.description]
        if "mark_id" not in columns:
            raise ValueError(f'"mark_id" not exists in database: {db_path}, All columns: {columns}')
        columns += ["message"]
        message_dict = cls.create_span_message_dict(all_data)

        basic_df_list, message_df_list = [], []
        for cur in all_data:
            if len(cur) < 6 or cur[6].startswith("span="):
                continue
            msg = "" if cur[2] == "start/end" else cur[6]  # clean span name in range
            msg_combined = (msg + message_dict.get(str(cur[5]), "")).replace("^", "\"")
            if not (msg_combined.startswith('{') and msg_combined.endswith('}')):
                msg_combined = '{' + msg_combined[:-1] + '}'  # -1 is ,
            msg_combined_json = json.loads(msg_combined)

            basic_df_list.append(cur + (msg_combined_json,))  # also append raw dict message
            message_df_list.append(msg_combined_json)

        basic_df = pd.DataFrame(basic_df_list, columns=columns)
        message_df = pd.DataFrame(message_df_list)
        all_data_df = pd.concat([basic_df, message_df], axis=1)
        all_data_df["span_id"] = all_data_df["mark_id"]
        conn.close()
        return all_data_df

    @classmethod
    def load_cpu_data(cls, db_path):
        if db_path is None:
            return None
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM CpuUsage
            WHERE cpu_no == 'Avg'
        """)

        cpu_data = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        cpu_data_df = pd.DataFrame(cpu_data, columns=columns)
        conn.close()
        return cpu_data_df

    @classmethod
    def load_memory_data(cls, db_path):
        if db_path is None:
            return None
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM MemUsage
        """)

        data = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        df = pd.DataFrame(data, columns=columns)
        conn.close()
        return df

    @classmethod
    def load_cpu_freq(cls, info_path):
        cpu_frequency = None
        with ms_open(info_path, 'r') as info:
            try:
                data = json.load(info)
            except JSONDecodeError:
                logger.error(f"file {info_path} is not a json file. ")
                return 0
            if 'CPU' not in data or not isinstance(data['CPU'], list) or len(data['CPU']) == 0:
                raise ValueError(f"Invalid or missing 'CPU' data in {info_path}.")
            cpu_data = data['CPU'][0]
            cpu_frequency = cpu_data.get('Frequency', 0)
            if cpu_frequency != "":
                return float(cpu_frequency) * US_PER_SECOND

        logger.warning("Missing 'Frequency' value in 'CPU' data.")
        return 0

    @classmethod
    def load_time_info(cls, filepaths):
        cntvct, host_clock_monotonic_raw = cls.load_start_cnt(filepaths.get("host_start"))
        cpu_frequency = cls.load_cpu_freq(filepaths.get("info"))
        collection_time_begin, start_clock_monotonic_raw = cls.load_start_time(filepaths.get("start_info"))
        return dict(
            cntvct=cntvct,
            host_clock_monotonic_raw=host_clock_monotonic_raw,
            collection_time_begin=collection_time_begin,
            start_clock_monotonic_raw=start_clock_monotonic_raw,
            cpu_frequency=cpu_frequency
        )

    @classmethod
    def load_start_cnt(cls, config_path):
        from ms_service_profiler.parse import _parse_value
        cntvct = 0
        clock_monotonic_raw = 0

        with ms_open(config_path, 'r') as f:
            for line in f:
                cntvct_val = _parse_value(line, "cntvct")
                if cntvct_val is not None:
                    cntvct = cntvct_val
                    continue

                clock_val = _parse_value(line, "clock_monotonic_raw")
                if clock_val is not None:
                    clock_monotonic_raw = clock_val

        if cntvct == 0 or clock_monotonic_raw == 0:
            raise ValueError(
                f"Failed to find 'cntvct' or 'clock_monotonic_raw' in {config_path}, please check."
            )

        return cntvct, clock_monotonic_raw

    @classmethod
    def load_host_name(cls, tx_data_df, info_path):
        with ms_open(info_path, 'r') as info:
            try:
                data = json.load(info)
            except JSONDecodeError:
                logger.error(f"file {info_path} is not a json file. ")
                data = {
                    "hostname": "",
                    "hostUid": ""
                }
            host_name = data.get("hostname")
            host_uid = data.get("hostUid")

        tx_data_df["hostname"] = host_name
        tx_data_df["hostuid"] = host_uid

    @classmethod
    def load_start_time(cls, start_info_path):
        with ms_open(start_info_path, 'r') as info:
            data = json.load(info)
            if 'collectionTimeBegin' not in data or 'clockMonotonicRaw' not in data:
                raise ValueError(f"Invalid or missing 'CPU' data in {start_info_path}.")
            collection_time_begin = float(data['collectionTimeBegin'])
            clock_monotonic_raw = float(data['clockMonotonicRaw'])
        return collection_time_begin, clock_monotonic_raw

    @classmethod
    def create_span_message_dict(cls, data):
        span_msg_dict = {}
        for cur in data:
            if len(cur) < 6:
                continue

            msg = cur[6]
            if not (msg.startswith("span=") and "*" in msg):
                continue

            span_msg, msg = msg.split("*", 1)
            span_id = span_msg.split("=", 1)[-1]  # "=" is within "span="
            span_msg_dict.setdefault(span_id, []).append((cur, msg))

        message_dict = {}
        for span_id, cur_msg in span_msg_dict.items():
            cur_msg.sort(key=lambda xx: xx[0][3])  # Sort by cur, guaranteed longer than 6
            message_dict[span_id] = "".join((xx[1] for xx in cur_msg))
        return message_dict

    @classmethod
    def load_prof(cls, filepaths):
        tx_data_df = cls.load_tx_data(filepaths.get("tx"))
        cpu_data_df = cls.load_cpu_data(filepaths.get("cpu"))
        memory_data_df = cls.load_memory_data(filepaths.get("memory"))
        time_info = cls.load_time_info(filepaths)
        msprof_files = filepaths.get("msprof", [])
        if tx_data_df is not None:
            cls.load_host_name(tx_data_df, filepaths.get("info"))

        return dict(
            tx_data_df=tx_data_df,
            cpu_data_df=cpu_data_df,
            memory_data_df=memory_data_df,
            time_info=time_info,
            msprof_data=msprof_files
        )

    def load(self, prof_path):
        file_filter = {
            "tx": "msproftx.db",
            "host_start": "host_start.log",
            "info": "info.json",
            "start_info": "start_info",
            "msprof": ("msprof_*.json", True)
        }
        cur_path = str(prof_path)
        if is_need_msprof(cur_path):
            command = gen_msprof_command(cur_path)
            clear_last_msprof_output(cur_path)
            run_msprof_command(command)
        filepaths = self.get_filepaths(prof_path, file_filter)
        try:
            data = self.load_prof(filepaths)
        except Exception as ex:
            raise LoadDataError(str(prof_path)) from ex

        return data
