# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import os
from abc import abstractmethod
from typing import Dict
import numpy as np

from ms_service_profiler.exporters.base import TaskExporterBase
from ms_service_profiler.utils.file_open_check import UmaskWrapper

OUTPUT_CSV_NAME = "ep_balance.csv"
OUTPUT_PNG_NAME = "ep_balance.png"
SUMMED_OUTPUT_NAME_EXPERT = "{}_eplb_{}_summed_hot_map_by_expert.png"
SUMMED_OUTPUT_NAME_RANK = "{}_eplb_{}_summed_hot_map_by_rank.png"
SUMMED_OUTPUT_NAME_MODEL_EXPERT = "{}_eplb_{}_summed_hot_map_by_model_expert.png"
NAME = "expert_hot"
EXPERT_MAP = "expert_map"
DYNAMIC_EXPERT_MAP = "dynamic_expert_map"
INSTANCE_POD_MAP = "instance_pod_map"
MAX_PLT_PIXEL = 256
MIN_PLT_PIXEL = 32


class ExporterDyEpBalance(TaskExporterBase):
    name: str = NAME

    @classmethod
    @abstractmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @abstractmethod
    def export(cls, data: Dict) -> None:
        if not data:
            return

        output = cls.args.output_path

        if NAME not in data.keys() or not data.get(NAME):
            return

        expert_hot = data[NAME]  # ["instance_name"][eplb_period][rank][iteration][layer][expert_per_rank]

        for instance_name, expert_hot_per_instance in expert_hot.items():
            for eplb_iteration, expert_hot_per_eplb in enumerate(expert_hot_per_instance):
                summed_hot_rank_output_path = \
                    os.path.join(output, SUMMED_OUTPUT_NAME_RANK.format(instance_name, eplb_iteration))
                # 将热度信息按照rank、expert_per_rank的维度进行累加
                # shape:[rank][iteration][layer][expert_per_rank] -> [layer, expert_iteration]
                expert_hot_summed_rank = expert_hot_per_eplb.sum(axis=(0, -1))
                draw_hot_map_from_arr(expert_hot_summed_rank,
                                      title=f"{instance_name} EPLB_Period_{eplb_iteration} Summed Hot Map By Rank",
                                      y_label="Decoder layers",
                                      x_label="Rank_0 to Rank_N",
                                      output_path=summed_hot_rank_output_path)

                # shape: rank * iteration * layer * expert_per_rank -> rank * expert_per_rank * layer
                expert_hot_summed_expert = expert_hot_per_eplb.sum(axis=1).transpose([0, 2, 1])
                # shape: rank * expert_per_rank * layer -> layer * total_expert
                expert_hot_summed_expert = \
                    expert_hot_per_instance.reshape(-1, expert_hot_summed_expert.shape[-1]).transpose([1, 0])
                summed_hot_expert_output_path = \
                    os.path.join(output, SUMMED_OUTPUT_NAME_EXPERT.format(instance_name, eplb_iteration))
                draw_hot_map_from_arr(expert_hot_summed_expert,
                                      title=f"{instance_name} Summed Hot Map By Expert",
                                      y_label="Decoder layers",
                                      x_label="Experts in Rank_0 to Rank_N",
                                      output_path=summed_hot_expert_output_path)

        expert_map = data.get(EXPERT_MAP, None)
        if expert_map is not None:
            for instance_name, expert_map_by_instance in expert_map.items():
                # expert_map_per_eplb shape: [layer][total_expert_num]
                for eplb_iteration, expert_map_per_eplb in enumerate(expert_map_by_instance):
                    # expert_hot_per_eplb shape:[rank][iteration][layer][expert_per_rank]
                    expert_hot_per_eplb = expert_hot.get(instance_name)[eplb_iteration]
                    expert_hot_summed_expert = expert_hot_per_eplb.sum(axis=1).transpose([0, 2, 1])
                    expert_hot_summed_expert = \
                        expert_hot_summed_expert.reshape(-1, expert_hot_summed_expert.shape[-1]).transpose([1, 0])

                    model_expert_num = np.max(expert_map_per_eplb)
                    remapped_expert_hot = np.zeros([expert_map_per_eplb.shape[0], model_expert_num])

                    if expert_map_per_eplb.shape != expert_hot_summed_expert.shape:
                        raise ValueError("Shape of expert_map and expert_hot are not equal, "
                                         "please check profiling input.")

                    for layer_index in range(expert_hot_summed_expert.shape[0]):
                        for expert_index in range(expert_hot_summed_expert.shape[1]):
                            model_expert_index = expert_map_per_eplb[expert_index]
                            remapped_expert_hot[layer_index][model_expert_index] += \
                                expert_hot_summed_expert[layer_index][expert_index]

                    summed_hot_model_expert_output_path = \
                        os.path.join(output, SUMMED_OUTPUT_NAME_MODEL_EXPERT.format(instance_name, eplb_iteration))
                    draw_hot_map_from_arr(remapped_expert_hot,
                                          title=f"{instance_name} Summed Hot Map By Expert",
                                          y_label="Decoder layers",
                                          x_label="Experts from 0 to N",
                                          output_path=summed_hot_model_expert_output_path)


    @classmethod
    def depends(cls):
        return ["pipeline:service"]

    def do_export(self) -> None:
        data: Dict = self.get_depends_result("pipeline:service")
        self.export(data)


def draw_hot_map_from_arr(arr, title="", x_label="", y_label="", output_path="hot_map.png"):
    import matplotlib.pyplot as plt

    if len(arr.shape) != 2:
        raise ValueError("arr shape size != 2")

    x_pixel = max(min(arr.shape[0] // 10, MAX_PLT_PIXEL), MIN_PLT_PIXEL)
    y_pixel = max(min(arr.shape[1] // 10, MAX_PLT_PIXEL), MIN_PLT_PIXEL)

    plt.figure(figsize=(x_pixel, y_pixel))
    plt.imshow(arr)
    if isinstance(title, str) and title:
        plt.title(title)
    if isinstance(x_label, str) and x_label:
        plt.xlabel(x_label)
    if isinstance(y_label, str) and y_label:
        plt.ylabel(y_label)

    plt.xticks(ticks=[i for i in range(arr.shape[1])], labels=list(range(arr.shape[1])), rotation=90)
    plt.yticks(ticks=[i for i in range(arr.shape[0])], labels=list(range(arr.shape[0])))
    plt.tight_layout()
    with UmaskWrapper(umask=0o137):
        plt.savefig(output_path)

    plt.cla()
