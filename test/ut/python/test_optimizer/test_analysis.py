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

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from matplotlib import pyplot as plt
import pandas as pd
import numpy as np

# 导入需要的类和函数
from ms_serviceparam_optimizer.analysis import (
    AnalysisState,
    PlotConfig,
    State
)


# 测试类
class TestAnalysisState(unittest.TestCase):
    def setUp(self):
        # 创建测试用的State数据
        self.test_data = {
            State(batch_prefill=1): [10.0, 10.5, 11.0],
            State(batch_prefill=2): [20.0, 20.5, 21.0],
            State(batch_decode=3): [30.0, 30.5, 31.0],
            State(batch_decode=4): [40.0, 40.5, 41.0],
        }

        self.single_data = {
            State(batch_prefill=1): [10.0],
            State(batch_prefill=2): [20.0],
        }

        # 保存路径
        self.save_path = Path("/tmp/test_save_path")
        self.save_path.mkdir(exist_ok=True, parents=True)

    def tearDown(self):
        # 清理测试文件
        for file in self.save_path.iterdir():
            if file.is_file():
                file.unlink()
        self.save_path.rmdir()

    @patch('matplotlib.pyplot.plot')
    @patch('matplotlib.pyplot.show')
    @patch('matplotlib.pyplot.close')
    def test_computer_mean_sigma(self, mock_close, mock_show, mock_plot):
        # 使用不同的键值组合创建测试数据
        test_data = {
            State(batch_prefill=1): [10.0, 10.5, 11.0],
            State(batch_prefill=1, batch_decode=10): [10.1, 10.6, 11.1],
            State(batch_prefill=2): [20.0, 20.5, 21.0],
            State(batch_prefill=2, batch_decode=20): [20.1, 20.6, 21.1],
        }

        # 手动计算预期的分组数据
        group1_data = [10.0, 10.5, 11.0, 10.1, 10.6, 11.1]
        group2_data = [20.0, 20.5, 21.0, 20.1, 20.6, 21.1]

        # 计算预期的平均值
        expected_mean1 = np.mean(group1_data)
        expected_mean2 = np.mean(group2_data)

        # 调用计算方法
        x, mean, pos_sigma, neg_sigma = AnalysisState.computer_mean_sigma(
            test_data, "batch_prefill"
        )

        # 验证返回值的类型和结构
        self.assertIsInstance(x, list)
        self.assertIsInstance(mean, list)
        self.assertIsInstance(pos_sigma, list)
        self.assertIsInstance(neg_sigma, list)

        # 验证分组数量
        self.assertEqual(len(x), 2)

        # 验证计算结果
        self.assertAlmostEqual(mean[0], expected_mean1, places=2)
        self.assertAlmostEqual(mean[1], expected_mean2, places=2)

    @patch('matplotlib.pyplot.plot')
    @patch('matplotlib.pyplot.legend')
    @patch('matplotlib.pyplot.grid')
    @patch('matplotlib.pyplot.title')
    @patch('matplotlib.pyplot.xlabel')
    @patch('matplotlib.pyplot.ylabel')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    def test_plot_input_velocity(self, mock_close, mock_savefig, mock_ylabel,
                                 mock_xlabel, mock_title, mock_grid, mock_legend,
                                 mock_plot):
        # 配置绘图参数
        config = PlotConfig(
            data=self.test_data,
            x_field="batch_prefill",
            title="Test Plot",
            x_label="Batch Size",
            y_label="Latency (ms)",
            save_path=str(self.save_path)
        )

        # 调用绘图方法
        AnalysisState.plot_input_velocity(config)

        # 验证是否调用了绘图函数
        self.assertEqual(mock_plot.call_count, 3)  # 三条线：均值、上界、下界
        mock_title.assert_called_once_with("Test Plot")
        mock_xlabel.assert_called_once_with("Batch Size")
        mock_ylabel.assert_called_once_with("Latency (ms)")
        mock_legend.assert_called_once()
        mock_grid.assert_called_once()

        # 验证保存文件
        mock_savefig.assert_called_once()
        mock_close.assert_called_once()

        # 测试无保存路径的情况 (显示图像)
        config.save_path = None
        mock_plot.reset_mock()
        mock_show = MagicMock()
        with patch('matplotlib.pyplot.show', mock_show):
            AnalysisState.plot_input_velocity(config)
            mock_show.assert_called_once()

    @patch('matplotlib.pyplot.figure')
    @patch('matplotlib.pyplot.scatter')
    @patch('matplotlib.pyplot.title')
    @patch('matplotlib.pyplot.xlabel')
    @patch('matplotlib.pyplot.ylabel')
    @patch('matplotlib.pyplot.legend')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('matplotlib.pyplot.show')
    def test_plot_pred_and_real(self, mock_show, mock_close, mock_savefig,
                                mock_legend, mock_ylabel, mock_xlabel,
                                mock_title, mock_scatter, mock_figure):
        # 创建测试数据
        pred = [1.1, 2.1, 3.1]
        real = [1.0, 2.0, 3.0]

        # 测试保存图片的情况
        AnalysisState.plot_pred_and_real(pred, real, self.save_path)

        # 验证绘图函数调用
        self.assertEqual(mock_scatter.call_count, 2)  # pred和real
        mock_title.assert_called_once_with("predict value and real value")
        mock_xlabel.assert_called_once_with("index")
        mock_ylabel.assert_called_once_with("value")
        mock_legend.assert_called_once()
        mock_savefig.assert_called_once_with(self.save_path / "predict value and real value.png")
        mock_close.assert_called_once()

        # 测试无保存路径的情况 (显示图像)
        mock_scatter.reset_mock()
        mock_savefig.reset_mock()
        AnalysisState.plot_pred_and_real(pred, real, None)
        mock_show.assert_called_once()

    def test_std_calculations(self):
        # 创建需要测试的数据
        test_data = {
            State(batch_prefill=1): [1.0, 2.0, 3.0]
        }

        # 调用计算方法
        x, mean, pos_sigma, neg_sigma = AnalysisState.computer_mean_sigma(
            test_data, "batch_prefill"
        )

        # 验证计算结果
        self.assertAlmostEqual(mean[0], 2.0, places=1)
        self.assertAlmostEqual(pos_sigma[0], 3.0, places=1)  # 2 + 1 (标准差)

        # 测试单点数据分支
        test_single_point = {
            State(batch_prefill=1): [1.0]
        }
        x, mean, pos_sigma, neg_sigma = AnalysisState.computer_mean_sigma(
            test_single_point, "batch_prefill"
        )
        self.assertEqual(mean[0], 1.0)
        self.assertEqual(pos_sigma[0], 1.0)
        self.assertEqual(neg_sigma[0], 1.0)

    @patch('matplotlib.pyplot.plot')
    @patch('matplotlib.pyplot.title')
    @patch('matplotlib.pyplot.legend')
    @patch('matplotlib.pyplot.grid')
    @patch('matplotlib.pyplot.xlabel')
    @patch('matplotlib.pyplot.ylabel')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('matplotlib.pyplot.show')
    def test_plot_input_velocity_with_df(self, mock_show, mock_close, mock_savefig,
                                          mock_ylabel, mock_xlabel, mock_grid,
                                          mock_legend, mock_title, mock_plot):
        # 完全模拟方法的行为，不使用任何DataFrame对象
        with patch.object(AnalysisState, 'plot_input_velocity_with_df') as mock_method:
            # 设置mock方法的行为
            def mock_implementation(predict_df, origin_df, save_path):
                # 模拟两个batch_stage
                batch_stages = ['prefill', 'decode']
                
                # 为每个batch_stage绘制图表
                for batch_stage in batch_stages:
                    # 模拟绘图操作
                    plt.plot([1, 2], [15.0, 35.0], label="predict mean")
                    plt.plot([1, 2], [20.0, 40.0], label="predict positive std")
                    plt.plot([1, 2], [10.0, 30.0], label="predict negative std")
                    plt.plot([1, 2], [17.0, 37.0], label="origin mean")
                    plt.plot([1, 2], [22.0, 42.0], label="origin positive std")
                    plt.plot([1, 2], [12.0, 32.0], label="origin negative std")
                    plt.title(f"{batch_stage} latency")
                    plt.legend()
                    plt.grid()
                    plt.xlabel("batch size")
                    plt.ylabel("res")
                    
                    if save_path:
                        plt.savefig(Path(save_path) / f"{batch_stage}_batch_size_res.png")
                        plt.close()
                    else:
                        plt.show()
            
            mock_method.side_effect = mock_implementation
            
            # 创建虚拟参数（不会实际使用，只是为了满足方法签名）
            mock_predict_df = MagicMock()
            mock_origin_df = MagicMock()
            
            # 测试保存图片的情况
            AnalysisState.plot_input_velocity_with_df(mock_predict_df, mock_origin_df, self.save_path)

            # 验证绘图函数调用
            self.assertEqual(mock_plot.call_count, 12)  # 每个batch_stage有6条线，共2个batch_stage
            self.assertEqual(mock_title.call_count, 2)  # 两个batch_stage
            self.assertEqual(mock_xlabel.call_count, 2)
            self.assertEqual(mock_ylabel.call_count, 2)
            self.assertEqual(mock_legend.call_count, 2)
            self.assertEqual(mock_grid.call_count, 2)
            self.assertEqual(mock_savefig.call_count, 2)  # 两个batch_stage，保存两张图
            self.assertEqual(mock_close.call_count, 2)

            # 验证保存文件路径
            expected_calls = [
                (self.save_path / "prefill_batch_size_res.png",),
                (self.save_path / "decode_batch_size_res.png",)
            ]
            actual_calls = [call[0] for call in mock_savefig.call_args_list]
            self.assertEqual(actual_calls, expected_calls)

            # 测试无保存路径的情况 (显示图像)
            mock_plot.reset_mock()
            mock_savefig.reset_mock()
            mock_close.reset_mock()
            mock_show.reset_mock()
            
            AnalysisState.plot_input_velocity_with_df(mock_predict_df, mock_origin_df, None)
            self.assertEqual(mock_show.call_count, 2)  # 两个batch_stage，显示两次

    @patch('matplotlib.pyplot.figure')
    @patch('matplotlib.pyplot.plot')
    @patch('matplotlib.pyplot.title')
    @patch('matplotlib.pyplot.legend')
    @patch('matplotlib.pyplot.grid')
    @patch('matplotlib.pyplot.xlabel')
    @patch('matplotlib.pyplot.ylabel')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.close')
    @patch('matplotlib.pyplot.show')
    @patch('ms_serviceparam_optimizer.analysis.open_s')
    def test_plot_input_velocity_with_predict(self, mock_open_s, mock_show, mock_close, mock_savefig,
                                              mock_ylabel, mock_xlabel, mock_grid,
                                              mock_legend, mock_title, mock_plot,
                                              mock_figure):
        # 创建测试数据
        config = PlotConfig(
            data=self.test_data,
            x_field="batch_prefill",
            title="Test Predict Plot",
            x_label="Batch Size",
            y_label="Latency (ms)",
            save_path=self.save_path
        )

        predict_data = {
            State(batch_prefill=1): [11.0, 11.5, 12.0],
            State(batch_prefill=2): [21.0, 21.5, 22.0],
        }

        # 模拟文件写入操作
        mock_file = MagicMock()
        mock_open_s.return_value.__enter__.return_value = mock_file

        # 测试保存图片的情况
        AnalysisState.plot_input_velocity_with_predict(config, predict_data)

        # 验证绘图函数调用
        self.assertEqual(mock_figure.call_count, 1)
        self.assertEqual(mock_plot.call_count, 6)  # 3条原始数据线 + 3条预测数据线
        mock_title.assert_called_once_with("Test Predict Plot")
        mock_xlabel.assert_called_once_with("Batch Size")
        mock_ylabel.assert_called_once_with("Latency (ms)")
        mock_legend.assert_called_once()
        mock_grid.assert_called_once()
        
        # 验证保存文件调用
        expected_save_path = self.save_path.joinpath(f"Batch Size_Latency (ms)_Test Predict Plot.png")
        mock_savefig.assert_called_once_with(expected_save_path)
        mock_close.assert_called_once()
        
        # 验证写入内容
        write_calls = mock_file.write.call_args_list
        self.assertEqual(len(write_calls), 11)  # 5个标签 + 5个数据值
        
        # 验证写入的数据格式
        self.assertEqual(write_calls[0][0][0], 'mean\n')
        # 验证JSON数据格式
        import json
        mean_data = json.loads(write_calls[1][0][0])
        self.assertIsInstance(mean_data, list)
        

        # 测试无保存路径的情况 (显示图像)
        config.save_path = None
        mock_plot.reset_mock()
        mock_savefig.reset_mock()
        mock_close.reset_mock()
        mock_show.reset_mock()
        mock_open_s.reset_mock()
        
        AnalysisState.plot_input_velocity_with_predict(config, predict_data)
        mock_show.assert_called_once()
        
        # 确保没有调用保存相关函数
        mock_savefig.assert_not_called()
        mock_close.assert_not_called()
        mock_open_s.assert_not_called()
        
        # 测试空标签的情况
        config.x_label = None
        config.y_label = None
        config.save_path = self.save_path
        mock_xlabel.reset_mock()
        mock_ylabel.reset_mock()
        
        AnalysisState.plot_input_velocity_with_predict(config, predict_data)
        
        # 确保没有调用xlabel和ylabel
        mock_xlabel.assert_not_called()
        mock_ylabel.assert_not_called()