# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
sys.path.append('..')

import unittest
from ms_server_profiler.plugins.base import PluginBase
from ms_server_profiler.plugins.sort_plugins import sort_plugins, DependencyNotFoundError, DependencyCycleError


class TestSortPlugins(unittest.TestCase):
    
    def setUp(self):
        class PluginA(PluginBase):
            name = "A"
            depends = []

        class PluginB(PluginBase):
            name = "B"
            depends = ["A"]

        class PluginC(PluginBase):
            name = "C"
            depends = ["A"]

        class PluginD(PluginBase):
            name = "D"
            depends = ['B', 'C']

        class PluginE(PluginBase):
            name = "E"
            depends = ['D']

        self.plugin_a = PluginA
        self.plugin_b = PluginB
        self.plugin_c = PluginC
        self.plugin_d = PluginD
        self.plugin_e = PluginE
    
    
    def test_no_dependencies(self):
        plugins = [self.plugin_a]
        sorted_plugins = sort_plugins(plugins)
        self.assertEqual(sorted_plugins, [self.plugin_a])

    def test_simple_dependencies(self):
        plugins = [self.plugin_a, self.plugin_b]
        sorted_plugins = sort_plugins(plugins)
        self.assertEqual(sorted_plugins, [self.plugin_a, self.plugin_b])

    def test_multiple_dependencies(self):
        plugins = [self.plugin_a, self.plugin_b, self.plugin_c, self.plugin_d]
        sorted_plugins = sort_plugins(plugins)
        self.assertEqual(sorted_plugins, [self.plugin_a, self.plugin_b, self.plugin_c, self.plugin_d])
    
    def test_chain_of_dependencies(self):
        plugins = [self.plugin_a, self.plugin_b, self.plugin_d, self.plugin_e]
        with self.assertRaises(Exception) as context:
            sort_plugins(plugins)
        self.assertIsInstance(context.exception, DependencyNotFoundError)

    def test_cycle_detection(self):
        class PluginF(PluginBase):
            name = "F"
            depends = ['G']

        class PluginG(PluginBase):
            name = "G"
            depends = ['F']
        plugin_f = PluginF
        plugin_g = PluginG  # Cycle here
        plugins = [self.plugin_a, plugin_f, plugin_g]

        with self.assertRaises(Exception) as context:
            sort_plugins(plugins)
        self.assertIsInstance(context.exception, DependencyCycleError)
    
    
if __name__ == '__main__':
    unittest.main()

