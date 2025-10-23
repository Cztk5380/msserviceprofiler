# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
from collections import defaultdict
import numpy as np
import pandas as pd

from ms_service_profiler.processor.processor_base import ProcessorBase
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import KeyExcept
from enum import IntEnum, auto

MOE_HOT_DOMAIN_NAME = "eplb_observe"
EXPERT_ROUTING_NAME = "expert_routing"


class ProcessorEplbObserve(ProcessorBase):

    @property
    def name(self):
        return "ProcessorEplbObserve"

    def parse(self, data):
        if data is None:
            logger.warning("Input data is None, skip eplb_observe analysis.")
            return None

        data = [item for item in data if isinstance(item, pd.DataFrame) and not item.empty]

        tx_data_df = pd.concat(data)

        if tx_data_df is None:
            logger.warning("No tx data in profiling data, skip moe eplb analysis.")
            return None

        # 从tx_data_df中筛选出专家负载对应domain域的数据
        moe_hot_df = tx_data_df[tx_data_df["domain"] == MOE_HOT_DOMAIN_NAME]
        if moe_hot_df.empty:
            logger.warning("No eplb_observe data found in profiling data, skip eplb_observe analysis.")
            return None

        logger.info("Find eplb_observe data in profiling data, launch eplb observe analysis.")

        # expert_hot_by_host data
        expert_hot_by_host = defaultdict(dict)
        expert_routing = {}
        for pod_name, df_by_host in moe_hot_df.groupby("hostuid"):
            expert_routing_per_pod = defaultdict(list)

            for _, df_by_pid in df_by_host.groupby("pid"):
                # expert_routing_by_pid shape: list: [eplb_perid][layer][instance_expert_num]
                # expert_hot_per_pid shape: [eplb_period][iteration * layer * expert_per_rank]
                expert_hot_per_pid, rank, expert_routing_by_pid = self.process_expert_hot(df_by_pid)
                expert_hot_by_host[pod_name][rank] = expert_hot_per_pid
                if len(expert_routing_by_pid) > 0:
                    expert_routing_per_pod[rank] = expert_routing_by_pid

            if expert_routing_per_pod:
                expert_routing[pod_name] = expert_routing_per_pod

        # expert_hot_by_host shape: ["pod_name"]["rank"][eplb_period][iteration * layer * expert_per_rank]
        # expert_routing shape: ["pod_name"]["rank"][eplb_period][layer][instance_expert_num]

        # 获得实例instance-节点pod的映射
        instance_pod_map = grouping_host_name(list(expert_hot_by_host.keys()))

        # expert_hot_by_instance shape: ["instance_name"][rank][eplb_period][iteration][layer][expert_per_rank]
        expert_hot_by_instance = transfer_expert_hot(expert_hot_by_host, instance_pod_map)

        res = {}

        # 不存在路由表则直接返回
        if not expert_routing:
            # transposed_expert_hot shape: ["instance_name"][eplb_period][rank][iteration][layer][expert_per_rank]
            transposed_expert_hot = {
                key: transpose_eplb_iteration(value)
                for key, value in expert_hot_by_instance.items()
            }
            res["expert_hot"] = transposed_expert_hot
            return res

        expert_map = self.mapping_expert_hot(expert_hot_by_instance, instance_pod_map, expert_routing)
        transposed_expert_hot = {instance_name: transpose_eplb_iteration(value, len(expert_map.get(instance_name, [0])))
                                 for instance_name, value in expert_hot_by_instance.items()}
        res["expert_hot"] = transposed_expert_hot
        # expert_map shape: ["instance_name][eplb_period][layer][total_expert_num]
        res["expert_map"] = expert_map
        return res

    @staticmethod
    def mapping_expert_hot(expert_hot_by_instance, instance_pod_map, expert_routing):
        # 每个instance对应的专家映射表是一致的 根据各卡的路由表 生成专家映射表
        expert_map = {}
        for instance_name, pod_name_list in instance_pod_map.items():
            pod_name = pod_name_list[0]

            # 每个instance的专家数 = instance中的rank数 * 每个rank的专家数
            instance_expert_num = len(expert_hot_by_instance[instance_name]) * \
                len(expert_hot_by_instance[instance_name][0][0][0][0])

            layer_num = len(list(expert_routing[pod_name].values())[0][0])

            rank = list(expert_routing[pod_name].keys())[0]

            eplb_iteration_num = len(expert_routing[pod_name][rank])

            instance_expert_map = []

            for _ in range(eplb_iteration_num):
                instance_expert_map.append(-np.ones([layer_num, instance_expert_num], dtype=np.int32))

            for pod_name in pod_name_list:
                for rank, routing_list in expert_routing[pod_name].items():
                    instance_expert_map = update_expert_map(instance_expert_map, routing_list)

                expert_map[instance_name] = instance_expert_map
        return expert_map

    @staticmethod
    def process_expert_hot(df_by_pid):
        if EXPERT_ROUTING_NAME in df_by_pid.columns:
            logger.debug("profiling data with eplb.")
            expert_routing_df_by_pid = df_by_pid.loc[df_by_pid[EXPERT_ROUTING_NAME].dropna().index]
        else:
            logger.debug("profiling data without eplb.")
            expert_routing_df_by_pid = pd.DataFrame()

        if len(expert_routing_df_by_pid) == 0:
            # 没开负载均衡
            split_expert_hot = [df_by_pid]
            expert_routing_by_pid = []
        else:
            # 静态负载均衡 or 动态负载均衡
            # expert_routing_by_pid shape: list: [eplb_perid][layer][instance_expert_num]
            expert_routing_by_pid = expert_routing_df_by_pid[EXPERT_ROUTING_NAME].values.tolist()

            mark_id_list = expert_routing_df_by_pid["markId"].values.tolist()
            for item in mark_id_list:
                if not isinstance(item, int):
                    raise ValueError("Illegal markId type, please check profiling input.")
            mark_id_list.append(len(df_by_pid) - 1)
            mark_id_list = list(set(mark_id_list))
            mark_id_list.sort()
            split_expert_hot = []
            for i in range(len(mark_id_list) - 1):
                up_mark_id = mark_id_list[i]
                down_mark_id = mark_id_list[i + 1]
                split_expert_hot.append(
                    df_by_pid[(df_by_pid["markId"] > up_mark_id) & (df_by_pid["markId"] < down_mark_id)])

        # 检查rank的格式
        rank_list = list(set(df_by_pid["rank"].values.tolist()))
        if len(rank_list) != 1 or not isinstance(rank_list[0], int):
            raise ValueError("Expert hot map format illegal. Value rank in one file not same.")

        # split_expert_hot shape: [eplb_period][dataframe]
        # expert_hot shape: [eplb_period][iteration * layer * expert_per_rank]
        expert_hot = transfer_hot_df_to_list(split_expert_hot)

        rank = rank_list[0]

        return expert_hot, rank, expert_routing_by_pid


def transfer_hot_df_to_list(dataframe_list):
    # 将dataframe中的专家热点数据转换为np.array数据
    res = []
    for dataframe in dataframe_list:
        # item shape: [iteration * layer * expert_per_rank]
        item = np.array(dataframe["expert_hot"].values.tolist())
        if item.ndim != 3:
            raise ValueError("Expert hot format illegal, should be [iteration, layer_num, expert_num_per_rank")
        res.append(item)
    # res shape: [eplb_period][iteration * layer * expert_per_rank]
    return res


def grouping_host_name(host_name_list):
    """
    对hostuid进行分组, mindie节点名称类似[mindie-server-d0-master-0, mindie-server-d0-worker-0, mindie-server-d0-worker-1]的
    为同一实例的一组节点。按照'-'进行分解，去掉后两位实例内区分的字段，重新合并作为实例的名称
    """
    grouping_dict = defaultdict(list)
    for host_name in host_name_list:
        if not isinstance(host_name, str):
            raise ValueError("hostuid should be str.")
        split_host_name = host_name.split("-")
        # 如果按照"-"划分失败 则默认所有数据是属于同一个instance
        if len(split_host_name) < 3:
            return {host_name_list[0]: host_name_list}
        instance_name = '-'.join(split_host_name[:-2])
        grouping_dict[instance_name].append(host_name)
    return grouping_dict


def update_expert_map(expert_map_list, expert_routing_list):
    # 将expert_routing转换为expert_map
    for eplb_iter, expert_map in enumerate(expert_map_list):
        expert_map = expert_map_list[eplb_iter]
        for layer_index, expert_routing_per_layer in enumerate(expert_routing_list[eplb_iter]):
            for expert_index, routing_index in enumerate(expert_routing_per_layer):
                expert_map[layer_index][routing_index] = expert_index
    # expert_map_list shape: [eplb_iteration][layer_num][instance_expert_num]
    return expert_map_list


def transfer_expert_hot(expert_hot, instance_pod_map):
    res = {}
    for instance_name, pod_name_list in instance_pod_map.items():
        instance_expert_hot_dict = {}
        for pod_name in pod_name_list:
            instance_expert_hot_dict.update(expert_hot[pod_name])

        instance_expert_hot_list = [instance_expert_hot_dict.get(rank, None) for rank in sorted(instance_expert_hot_dict)]
        res[instance_name] = instance_expert_hot_list
    return res


def transpose_eplb_iteration(expert_hot, eplb_iteration_num=1):
    # 转置 输入 ["instance_name"][rank][eplb_period][iteration][layer][expert_per_rank]
    # 转置为 ["instance_name"][eplb_period][rank][iteration][layer][expert_per_rank]

    def split_expert_hot(input_expert_hot):
        if input_expert_hot.shape[0] == 1:
            return input_expert_hot
        input_expert_hot[1:] -= input_expert_hot[:-1].copy()
        return input_expert_hot

    res = [[] for _ in range(eplb_iteration_num)]
    for _, expert_hot_per_rank in enumerate(expert_hot):  # _ is rank
        for eplb_iteration in range(eplb_iteration_num):
            res[eplb_iteration].append(split_expert_hot(expert_hot_per_rank[eplb_iteration]))
    return res
