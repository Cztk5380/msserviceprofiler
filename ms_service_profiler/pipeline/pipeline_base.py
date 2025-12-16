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

from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import ParseError
from ms_service_profiler.utils.timer import Timer


class PipelineBase(Task):
    def __init__(self, args) -> None:
        super().__init__(args)
        self.cur_step_id = 0

    def run_step(self, processor, name, data, *more_params, is_key_step=True):
        self.cur_step_id += 1
        with Timer(f'[{self.task_name} {self.task_index}] [step {self.cur_step_id}] {name}', log_enter=True) as timer:
            try:
                data = processor.parse(data, *more_params)
                timer.set_done_state("success")
            except Exception as ex:
                # 关键plugins失败，程序执行结束
                if is_key_step:
                    logger.exception(f'{name}-{self.task_index} failure. Program stopped.')
                    timer.set_done_state("failure")
                    raise ParseError(f'{name}-{self.task_index} failure. Program stopped. {str(ex)}') from ex
                else:
                    # 非关键plugins失败，程序继续执行
                    logger.exception(f'{name}-{self.task_index} failure. Skip it.')
                    timer.set_done_state("failure")
            return data
