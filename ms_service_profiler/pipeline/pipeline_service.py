# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import ParseError
from ms_service_profiler.processor.processor_res import ProcessorRes
from ms_service_profiler.plugins.plugin_common import PluginCommon
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStamp
from ms_service_profiler.plugins.plugin_metric import PluginMetric
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus
from ms_service_profiler.plugins.plugin_concat import PluginConcat
from ms_service_profiler.plugins.plugin_trace import PluginTrace
from ms_service_profiler.plugins.plugin_process_name import PluginProcessName
from ms_service_profiler.plugins.plugin_batch import PluginBatch


@Task.register("pipeline:service")
class PipelineService(PipelineBase):
    def __init__(self, args) -> None:
        super().__init__(args)
        self.key_plugin_error = False
        self.total_plugins = 9
        self.cur_id = 0

    @classmethod
    def depends(cls):
        return ["data_source:msprof"]
    
    @timer(logger.info)
    def run(self):
        data = self.get_depends_result("data_source:msprof")

        data = self.run_step(PluginTimeStamp, PluginTimeStamp.name, data)
        for one_msporf_data in data:
            one_msporf_data["tx_data_df"] = ProcessorRes().parse(one_msporf_data.get("tx_data_df"))
        data = self.run_step(PluginConcat, PluginConcat.name, data)
        data = self.run_step(PluginCommon, PluginCommon.name, data)
        data = self.run_step(PluginReqStatus, PluginReqStatus.name, data)
        data = self.run_step(PluginMetric, PluginMetric.name, data)
        data = self.run_step(PluginTrace, PluginTrace.name, data)
        data = self.run_step(PluginProcessName, PluginProcessName.name, data)
        data = self.run_step(PluginBatch, PluginBatch.name, data)

        return data

    def run_step(self, processor, name, data):
        self.cur_id += 1
        if self.key_plugin_error:
            return data
        try:
            data = processor.parse(data)
            logger.info(f'[{self.cur_id + 1}/{self.total_plugins}] {name} success.')
        except ParseError as ex:
            # 关键plugins失败，程序执行结束
            if name in ['plugin_timestamp', 'plugin_concat']:
                logger.exception(f'{name} failure. Program stopped.')
                self.key_plugin_error = True
                return data
            else:
                # 非关键plugins失败，程序继续执行
                logger.exception(f'{name} failure. Skip it.')
        except Exception as ex:
            logger.exception(f'{name} failure. Skip it.')
        return data
        
