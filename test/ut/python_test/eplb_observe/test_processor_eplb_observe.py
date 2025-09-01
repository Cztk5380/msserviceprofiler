
import unittest
import numpy as np
import random
import pandas as pd

from ms_service_profiler.processor.processor_eplb_observe import \
    ProcessorEplbObserve, update_expert_map, transfer_hot_df_to_list, grouping_host_name, transpose_eplb_iteration, transfer_expert_hot


expert_num = 16
decoder_layer = 4
iteration = 4


def init_expert_routing():
    def init_per_layer():
        expert_map_per_layer = list(range(expert_num))
        random.shuffle(expert_map_per_layer)

        expert_routing_per_layer = [0] * expert_num

        for idx, expert_idx in enumerate(expert_map_per_layer):
            expert_routing_per_layer[expert_idx] = idx
        return expert_map_per_layer, expert_routing_per_layer

    expert_map = []
    expert_routing = []

    for layer_idx in range(decoder_layer):
        expert_mep_per_layer, routing_per_layer = init_per_layer()
        expert_map.append(expert_mep_per_layer)
        expert_routing.append(routing_per_layer)

    return expert_map, expert_routing


class TestProcessorEplbObserve(unittest.TestCase):
    def test_update_expert_map(self):

        golden_expert_map_list = []
        expert_map_list = []
        expert_routing_list = []
        for i in range(iteration):
            golden_expert_map, expert_routing = init_expert_routing()
            golden_expert_map = np.array(golden_expert_map)
            golden_expert_map_list.append(golden_expert_map)
            expert_routing_list.append(expert_routing)
            expert_map_list.append(-np.ones([decoder_layer, expert_num]))

        expert_map_list = update_expert_map(expert_map_list, expert_routing_list)

        for golden, real in zip(golden_expert_map_list, expert_map_list):
            self.assertTrue(np.array_equal(golden, real))

    def test_transfer_hot_df_to_list(self):
        data = []
        for _ in range(iteration):
            data.append(np.random.randint(low=0, high=255, size=[decoder_layer, expert_num]).tolist())
        df = pd.DataFrame({"expert_hot": data})
        df_list = [df]
        real = transfer_hot_df_to_list(df_list)
        self.assertTrue(np.array_equal(real[0], np.array(data)))

    def test_grouping_host_name(self):
        # k8s case
        name_list = ["mindie-server-d0-master-0", "mindie-server-d0-master-1", "mindie-server-d0-worker-0"]
        golden = {"mindie-server-d0": ["mindie-server-d0-master-0", "mindie-server-d0-master-1", "mindie-server-d0-worker-0"]}

        real = grouping_host_name(name_list)

        self.assertEqual(golden, real)

        # other case
        name_list = ["xxxxxxxxxxx", "bbbbbbbbbbb"]
        golden = {"xxxxxxxxxxx": ["xxxxxxxxxxx", "bbbbbbbbbbb"]}

        real = grouping_host_name(name_list)

        self.assertEqual(golden, real)

    def test_multiple_iterations(self):
        expert_hot = [[1, 2, 3], [4, 5, 6]]
        eplb_iteration_num = 2
        golden = [[1, 4], [2, 5]]
        real = transpose_eplb_iteration(expert_hot, eplb_iteration_num)
        self.assertEqual(real, golden)

    def test_single_instance_multiple_pods(self):
        expert_hot = {
            "pod1": {1: "expert_hot1", 2: "expert_hot2"},
            "pod2": {3: "expert_hot3", 4: "expert_hot4"}
        }
        instance_pod_map = {
            "instance1": ["pod1", "pod2"]
        }
        golden = {
            "instance1": ["expert_hot1", "expert_hot2", "expert_hot3", "expert_hot4"]
        }
        real = transfer_expert_hot(expert_hot, instance_pod_map)
        self.assertEqual(real, golden)

