# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from abc import abstractmethod
from typing import Dict

from ms_service_profiler.utils.trace_to_db import TRACE_TABLE_DEFINITIONS
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.base import TaskExporterBase
from ms_service_profiler.exporters.exporter_trace import save_trace_data_into_json, save_trace_data_into_db
from ms_service_profiler.exporters.utils import create_sqlite_tables
from ms_service_profiler.utils.timer import Timer


class ExporterMspti(TaskExporterBase):
    name: str = 'mspti'

    @classmethod
    @abstractmethod
    def export(cls, data: Dict) -> None:
        if 'db' not in cls.args.format and 'json' not in cls.args.format:
            return

        if not data:
            return

        output = cls.args.output_path

        api_df = data["api_df"]
        kernel_df = data["kernel_df"]

        tarce_events_list = []

        tid = 0
        api_events = export_event_from_df(api_df, "Api", tid)
        tarce_events_list.extend(api_events)

        tid = tid + 1
        kernel_events = export_event_from_df(kernel_df, "Kernel", tid)
        tarce_events_list.extend(kernel_events)

        merged_data = {"traceEvents": tarce_events_list}
        if 'json' in cls.args.format:
            save_trace_data_into_json(merged_data, output)

        if 'db' in cls.args.format:
            logger.debug('Start write trace data to db')
            create_sqlite_tables(TRACE_TABLE_DEFINITIONS)
            save_trace_data_into_db(merged_data)
            logger.debug('Write trace data to db success')

    @classmethod
    def depends(cls):
        return ["pipeline:mspti"]

    def do_export(self) -> None:
        data: Dict = self.get_depends_result("pipeline:mspti")
        if data is None:
            return
        with Timer(self.name):
            self.export(data)


def export_event_from_df(df, channel_name, tid):
    tarce_events_list = []

    name_arr = df["name"].values
    start_arr = df["start"].values
    end_arr = df["end"].values
    process_arr = df["db_id"].values

    for i in range(len(df)):
        name = name_arr[i]
        start = start_arr[i] // 1000
        end = end_arr[i] // 1000
        process_id = process_arr[i]

        trace_event = {
            "name": name,
            "ph": "X",
            "ts": int(start),
            "dur": int(end - start),
            "pid": int(process_id),
            "tid": tid,
            "args": {}
        }

        tarce_events_list.append(trace_event)

    process_ids = list(set(list(process_arr)))
    for process_id in process_ids:
        channel_event = {
            "ph": "M",
            "pid": int(process_id),
            "tid": tid,
            "name": "thread_name",
            "args": {
                "name": channel_name
            }
        }
        tarce_events_list.append(channel_event)

    return tarce_events_list