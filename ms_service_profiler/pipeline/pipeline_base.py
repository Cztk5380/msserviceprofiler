# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import ParseError
from ms_service_profiler.utils.timer import Timer


class PipelineBase(Task):
    def __init__(self, args) -> None:
        super().__init__(args)
        self.cur_step_id = 0

    def run_step(self, processor, name, data, is_key_step=True):
        self.cur_step_id += 1
        with Timer(f'[{self.task_name}] [step {self.cur_step_id}] {name}', log_enter=True) as timer:
            try:
                data = processor.parse(data)
                timer.set_done_state("success")
            except Exception as ex:
                # 关键plugins失败，程序执行结束
                if is_key_step:
                    logger.exception(f'{name} failure. Program stopped.')
                    timer.set_done_state("failure")
                    raise ParseError(f'{name} failure. Program stopped.') from ex
                else:
                    # 非关键plugins失败，程序继续执行
                    logger.exception(f'{name} failure. Skip it.')
                    timer.set_done_state("failure")
            return data