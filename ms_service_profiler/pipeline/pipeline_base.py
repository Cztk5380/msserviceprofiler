# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import ParseError


class PipelineBase(Task):
    def __init__(self, args) -> None:
        super().__init__(args)
        self.cur_step_id = 0

    def run_step(self, processor, name, data, is_key_step=True):
        self.cur_step_id += 1
        try:
            data = processor.parse(data)
            logger.info(f'[step {self.cur_step_id}] {name} success.')
        except Exception as ex:
            # 关键plugins失败，程序执行结束
            if is_key_step:
                logger.exception(f'{name} failure. Program stopped.')
                raise ParseError(f'{name} failure. Program stopped.') from ex
            else:
                # 非关键plugins失败，程序继续执行
                logger.exception(f'{name} failure. Skip it.')
        return data