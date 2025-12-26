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

import os
import json
import subprocess
from pathlib import Path
from json import JSONDecodeError
import sqlite3

import pandas as pd

from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.error import LoadDataError
from ms_service_profiler.utils.file_open_check import ms_open
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.constant import US_PER_SECOND, MSPROF_REPORTS_PATH
from ms_service_profiler.exporters.utils import (
    create_sqlite_db, check_input_dir_valid, check_output_path_valid,
    find_file_in_dir, delete_dir_safely, find_all_file_complete
)


@Task.register("data_source:msprof")
class MsprofDataSource(BaseDataSource):

    @classmethod
    def outputs(cls):
        return ["data_source:service"]

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

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT pid, tid, event_type, start_time, end_time, mark_id, message "
                "FROM MsprofTxEx order by start_time "
            )
            all_data = cursor.fetchall()

            columns = []
            for description in cursor.description:
                if description[0] != "message":
                    columns.append(description[0])
                else:
                    columns.append("ori_msg")

            if "mark_id" not in columns:
                raise ValueError(f'"mark_id" not exists in database: {db_path!r}, All columns: {columns}')
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
            return all_data_df

    @classmethod
    def load_cpu_data(cls, db_path):
        if db_path is None:
            return None

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM CpuUsage
                WHERE cpu_no == 'Avg'
            """)
            cpu_data = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            cpu_data_df = pd.DataFrame(cpu_data, columns=columns)
            return cpu_data_df

    @classmethod
    def load_memory_data(cls, db_path):
        if db_path is None:
            return None

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM MemUsage
            """)
            data = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            df = pd.DataFrame(data, columns=columns)
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

        logger.warning("Missing 'Frequency' value in 'CPU' data. The time display will be incorrect. ")
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
        cntvct = 0
        clock_monotonic_raw = 0

        with ms_open(config_path, 'r') as f:
            for line in f:
                cntvct_val = cls._parse_value(line, "cntvct")
                if cntvct_val is not None:
                    cntvct = cntvct_val
                    continue

                clock_val = cls._parse_value(line, "clock_monotonic_raw")
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
                    "hostUid": "",
                    "pid": None
                }
            host_name = data.get("hostname")
            host_uid = data.get("hostUid")
        if tx_data_df is not None:
            tx_data_df["hostname"] = host_name
            tx_data_df["hostuid"] = host_uid
        return data

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
        
        host_info = cls.load_host_name(tx_data_df, filepaths.get("info"))
        if host_info is None:
            host_info = {}
        
        host_info["msprof_files"] = msprof_files

        return dict(
            tx_data_df=tx_data_df,
            cpu_data_df=cpu_data_df,
            memory_data_df=memory_data_df,
            time_info=time_info,
            msprof_data=host_info,
        )

    @classmethod
    def gen_msprof_command(cls, full_path):
        if len(full_path.split()) != 1:
            raise ValueError(f"{full_path} is invalid.")

        command = f"msprof --export=on --output={full_path}"
        logger.debug("command: %s", command)
        return command

    @classmethod
    def run_msprof_command(cls, command):
        command_list = command.split()
        try:
            subprocess.run(command_list, stdout=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError as e:
            logger.error("parse msprof data failed using command %r, error is: %r", command, str(e))
        except Exception as e:
            logger.error("parse msprof data failed using command %r, error is: %r", command, str(e))

    @classmethod
    def clear_last_msprof_output(cls, full_path):
        # 调用msprof前删除mindstudio_profiler_output文件夹
        msprof_output_path = os.path.join(full_path, 'mindstudio_profiler_output')

        #  如果不存在mindstudio_profiler_output文件夹，则不需要清理
        if not os.path.isdir(msprof_output_path):
            return

        delete_dir_safely(msprof_output_path)

    @classmethod
    def is_need_msprof(cls, full_path):
        if not find_all_file_complete(full_path, 'all_file.complete'):
            return True

        msprof_output_path = os.path.join(full_path, 'mindstudio_profiler_output')
        if not os.path.isdir(msprof_output_path):
            return True

        return False

    @classmethod
    def _parse_value(cls, line, key):
        if f"{key}:" not in line:
            return None

        parts = line.strip().split(": ")
        if len(parts) < 2:
            return None

        try:
            return int(parts[1])
        except (ValueError, IndexError):
            return None

    def load(self, prof_path):
        file_filter = {
            "tx": "msproftx.db",
            "host_start": "host_start.log",
            "info": "info.json",
            "start_info": "start_info",
            "msprof": ("msprof_*.json", True)
        }
        cur_path = str(prof_path)
        if self.is_need_msprof(cur_path):
            command = self.gen_msprof_command(cur_path)
            self.clear_last_msprof_output(cur_path)
            self.run_msprof_command(command)
        filepaths = self.get_filepaths(prof_path, file_filter)
        try:
            data = self.load_prof(filepaths)
        except Exception as ex:
            raise LoadDataError(str(prof_path), str(ex)) from ex

        return data
