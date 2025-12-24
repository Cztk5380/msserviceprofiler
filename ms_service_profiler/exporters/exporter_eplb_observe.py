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
from abc import abstractmethod
from typing import Dict, List
import numpy as np
import time

from ms_service_profiler.exporters.base import TaskExporterBase
from ms_service_profiler.utils.file_open_check import UmaskWrapper

SUMMED_OUTPUT_NAME_EXPERT = "{}_eplb_{}_summed_hot_map_by_expert.png"
SUMMED_OUTPUT_NAME_RANK = "{}_eplb_{}_summed_hot_map_by_rank.png"
SUMMED_OUTPUT_NAME_MODEL_EXPERT = "{}_eplb_{}_summed_hot_map_by_model_expert.png"
NAME = "expert_hot"
EXPERT_MAP = "expert_map"
MAX_PLT_PIXEL = 256
MIN_PLT_PIXEL = 8


class ExporterEplbObserve(TaskExporterBase):
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
        instance_time_stamp = data.get("time_stamp", {})

        cls.export_rank_summed_hot_map(expert_hot, output, instance_time_stamp)
        cls.export_model_expert_summed_hot_map(expert_hot, data, output, instance_time_stamp)

    @staticmethod
    def export_rank_summed_hot_map(expert_hot, output, instance_time_stamp):
        for instance_name, expert_hot_per_instance in expert_hot.items():
            std_balance_ratio = []
            rebalanced_point = [0]
            for eplb_iteration, expert_hot_per_eplb in enumerate(expert_hot_per_instance):
                expert_hot_per_eplb = cut2samelen(expert_hot_per_eplb)
                summed_hot_rank_output_path = \
                    os.path.join(output, SUMMED_OUTPUT_NAME_RANK.format(instance_name, eplb_iteration))
                # 将热度信息按照rank、expert_per_rank的维度进行累加
                # shape:[rank][iteration][layer][expert_per_rank] -> [layer, rank]
                expert_hot_summed_rank = np.array([item.sum(axis=(0, -1)) for item in expert_hot_per_eplb]).T
                draw_hot_map_from_arr(expert_hot_summed_rank,
                                      title=f"{instance_name} EPLB_Period_{eplb_iteration} Summed Hot Map By Rank",
                                      y_label="Decoder layers",
                                      x_label="Rank_0 to Rank_N",
                                      output_path=summed_hot_rank_output_path)

                # shape:[rank][iteration][layer][expert_per_rank] -> [rank, iteration, layer]
                expert_hot_with_iteration = np.array([item.sum(axis=(-1)) for item in expert_hot_per_eplb])
                std_balance_ratio_per_iteration = np.mean(np.std(expert_hot_with_iteration, axis=0), axis=-1)
                std_balance_ratio.extend(std_balance_ratio_per_iteration)
                rebalanced_point.append(rebalanced_point[-1] + len(std_balance_ratio_per_iteration))

                # shape: rank * iteration * layer * expert_per_rank -> rank * expert_per_rank * layer
                expert_hot_per_eplb_arr = np.array(expert_hot_per_eplb)
                expert_hot_summed_expert = expert_hot_per_eplb_arr.sum(axis=1).transpose([0, 2, 1])
                # shape: rank * expert_per_rank * layer -> layer * total_expert
                expert_hot_summed_expert = \
                    expert_hot_summed_expert.reshape(-1, expert_hot_summed_expert.shape[-1]).transpose([1, 0])
                summed_hot_expert_output_path = \
                    os.path.join(output, SUMMED_OUTPUT_NAME_EXPERT.format(instance_name, eplb_iteration))
                draw_hot_map_from_arr(expert_hot_summed_expert,
                                      title=f"{instance_name} Summed Hot Map By Expert",
                                      y_label="Decoder layers",
                                      x_label="Experts in Rank_0 to Rank_N",
                                      output_path=summed_hot_expert_output_path)

            local_time = transfer_unix_time(instance_time_stamp.get(instance_name))
            balance_ratio_path = os.path.join(output, f"{instance_name}_balance_ratio.png")
            draw_balance_ratio(std_balance_ratio, rebalanced_point, local_time, output_path=balance_ratio_path)

    @staticmethod
    def export_model_expert_summed_hot_map(expert_hot, data, output, instance_time_stamp):
        expert_map = data.get(EXPERT_MAP, None)
        if expert_map is not None:
            for instance_name, expert_map_by_instance in expert_map.items():
                # expert_map_per_eplb shape: [layer][total_expert_num]
                for eplb_iteration, expert_map_per_eplb in enumerate(expert_map_by_instance):
                    # expert_hot_per_eplb shape:[rank][iteration][layer][expert_per_rank]
                    expert_hot_per_eplb = expert_hot.get(instance_name)[eplb_iteration]
                    expert_hot_per_eplb = cut2samelen(expert_hot_per_eplb)
                    expert_hot_per_eplb_arr = np.array(expert_hot_per_eplb)
                    expert_hot_summed_expert = expert_hot_per_eplb_arr.sum(axis=1).transpose([0, 2, 1])
                    expert_hot_summed_expert = \
                        expert_hot_summed_expert.reshape(-1, expert_hot_summed_expert.shape[-1]).transpose([1, 0])

                    remapped_expert_hot = remap_expert_hot(expert_map_per_eplb, expert_hot_summed_expert)

                    summed_hot_model_expert_output_path = \
                        os.path.join(output, SUMMED_OUTPUT_NAME_MODEL_EXPERT.format(instance_name, eplb_iteration))
                    draw_hot_map_from_arr(remapped_expert_hot,
                                          title=f"{instance_name} Summed Hot Map By Expert",
                                          y_label="Decoder layers",
                                          x_label="Experts from 0 to N",
                                          output_path=summed_hot_model_expert_output_path)

    @classmethod
    def depends(cls):
        return ["pipeline:eplb_observe"]

    def do_export(self) -> None:
        data: Dict = self.get_depends_result("pipeline:eplb_observe")
        self.export(data)


def draw_hot_map_from_arr(arr, title="", x_label="", y_label="", output_path="hot_map.png"):
    import matplotlib.pyplot as plt

    if len(arr.shape) != 2:
        raise ValueError("arr shape size != 2")

    div = np.expand_dims(np.sum(arr, axis=1), axis=1)
    div[div == 0] = 1  # 实际不可能为0
    arr = arr / div

    x_pixel = max(min(arr.shape[1] // 8, MAX_PLT_PIXEL), MIN_PLT_PIXEL)
    y_pixel = max(min(arr.shape[0] // 8, MAX_PLT_PIXEL), MIN_PLT_PIXEL)

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
    plt.colorbar()
    plt.tight_layout()
    with UmaskWrapper(umask=0o137):
        plt.savefig(output_path)

    plt.cla()


def transfer_unix_time(unix_time_list):
    res = []
    for unix_time in unix_time_list:
        local_time = time.localtime(unix_time)
        res.append(f"{local_time.tm_hour:02d}:{local_time.tm_min:02d}:{local_time.tm_sec:02d}")
    return res


def draw_balance_ratio(std_balance_ratio, rebalanced_time_points, d_time, figsize=(60, 8),
                       output_path="balance_ratio.png"):
    import matplotlib.pyplot as plt
    # 创建图形和坐标轴
    _, ax = plt.subplots(figsize=figsize)

    # 绘制折线
    x_data = np.arange(len(std_balance_ratio))
    line = ax.plot(x_data, std_balance_ratio, marker='o', label="std", linewidth=2, markersize=5)
    color = line[0].get_color()

    # 在标注点处添加特殊标记
    for point in rebalanced_time_points:
        if 0 <= point < len(std_balance_ratio):
            ax.plot(point, std_balance_ratio[point], 'o',
                    markerfacecolor='white', markeredgecolor=color,
                    markersize=8, markeredgewidth=2)

    # 在横轴上标注特定点
    for point, local_time in zip(rebalanced_time_points, d_time):
        if 0 <= point <= len(std_balance_ratio):
            # 添加垂直线
            ax.axvline(x=point, color='red', linestyle='--', alpha=0.5, linewidth=1)

            # 在横轴下方添加标注
            ax.text(point, ax.get_ylim()[0] - 0.1 * (ax.get_ylim()[1] - ax.get_ylim()[0]),
                    f'{local_time}',
                    rotation=45, horizontalalignment='right',
                    color='red', fontweight='bold', fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))

    # 设置图表属性
    ax.set_xlabel('tokens num', fontsize=12)
    ax.set_ylabel('balance ratio', fontsize=12)
    ax.set_title('average of expert balance ratio by token num', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.spines['left'].set_position('zero')

    # 设置x轴刻度

    x_ticks = get_x_ticks(len(std_balance_ratio))
    ax.set_xticks(x_ticks)

    # 调整布局并显示
    plt.tight_layout()

    with UmaskWrapper(umask=0o137):
        plt.savefig(output_path)

    plt.cla()


def remap_expert_hot(expert_map_per_eplb, expert_hot_summed_expert):
    model_expert_num = np.max(expert_map_per_eplb) + 1
    remapped_expert_hot = np.zeros([expert_map_per_eplb.shape[0], model_expert_num])

    if expert_map_per_eplb.shape != expert_hot_summed_expert.shape:
        raise ValueError(f"Shape of expert_map and expert_hot are not equal, "
                         f"please check profiling input.Expert_map shape: "
                         f"{expert_map_per_eplb.shape}, expert_hot shape: {expert_hot_summed_expert.shape}")

    for layer_index in range(expert_hot_summed_expert.shape[0]):
        for expert_index in range(expert_hot_summed_expert.shape[1]):
            model_expert_index = expert_map_per_eplb[layer_index][expert_index]
            remapped_expert_hot[layer_index][model_expert_index] += \
                expert_hot_summed_expert[layer_index][expert_index]

    return remapped_expert_hot


def cut2samelen(array_list: List[np.ndarray]):
    len_list = [len(arr) for arr in array_list]
    min_len = min(len_list)
    if min_len == 0:
        raise ValueError("Expert hot data in certain rank is empty.")
    return [arr[:min_len] for arr in array_list]


def get_x_ticks(x):
    if x < 100:
        return [i for i in range(x + 1)]

    bit = 10 ** (len(str(x)) - 2)
    return [i * bit for i in range(x // bit + 1)]

