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
import unittest
from unittest.mock import patch, MagicMock

import pandas as pd

from ms_service_profiler.exporters.exporter_moe import ExporterMoe, OUTPUT_CSV_NAME, OUTPUT_PNG_NAME, NAME


class TestExporterMoe(unittest.TestCase):

    @patch('ms_service_profiler.exporters.exporter_moe.save_dataframe_to_csv')
    @patch('ms_service_profiler.exporters.exporter_moe.add_table_into_visual_db')
    @patch('ms_service_profiler.exporters.exporter_moe.plot_confidence_interval')
    def test_export_no_data(self, mock_plot, mock_add_table, mock_save_csv):
        args = MagicMock()
        args.output_path = "/tmp"
        args.format = ["csv", "db", "png"]

        data = {}
        ExporterMoe.initialize(args)
        ExporterMoe.export(data)

        mock_save_csv.assert_not_called()
        mock_add_table.assert_not_called()
        mock_plot.assert_not_called()

    @patch('ms_service_profiler.exporters.exporter_moe.save_dataframe_to_csv')
    @patch('ms_service_profiler.exporters.exporter_moe.add_table_into_visual_db')
    @patch('ms_service_profiler.exporters.exporter_moe.plot_confidence_interval')
    def test_export_empty_data(self, mock_plot, mock_add_table, mock_save_csv):
        args = MagicMock()
        args.output_path = "/tmp"
        args.format = ["csv", "db", "png"]

        data = {NAME: pd.DataFrame()}
        ExporterMoe.initialize(args)
        ExporterMoe.export(data)

        mock_save_csv.assert_not_called()
        mock_add_table.assert_not_called()
        mock_plot.assert_not_called()

    @patch('ms_service_profiler.exporters.exporter_moe.save_dataframe_to_csv')
    @patch('ms_service_profiler.exporters.exporter_moe.add_table_into_visual_db')
    @patch('ms_service_profiler.exporters.exporter_moe.plot_confidence_interval')
    def test_export_csv_format(self, mock_plot, mock_add_table, mock_save_csv):
        args = MagicMock()
        args.output_path = "/tmp"
        args.format = ["csv"]

        moe_analysis_df = pd.DataFrame({
            'Dataset': [1, 2],
            'Mean': [10, 20],
            'CI_Lower': [8, 18],
            'CI_Upper': [12, 22]
        })
        data = {NAME: moe_analysis_df}
        ExporterMoe.initialize(args)
        ExporterMoe.export(data)

        mock_save_csv.assert_called_once_with(moe_analysis_df, args.output_path, OUTPUT_CSV_NAME)
        mock_add_table.assert_not_called()
        mock_plot.assert_called_once_with(moe_analysis_df, os.path.join(args.output_path, OUTPUT_PNG_NAME))

    @patch('ms_service_profiler.exporters.exporter_moe.save_dataframe_to_csv')
    @patch('ms_service_profiler.exporters.exporter_moe.add_table_into_visual_db')
    @patch('ms_service_profiler.exporters.exporter_moe.plot_confidence_interval')
    def test_export_db_format(self, mock_plot, mock_add_table, mock_save_csv):
        args = MagicMock()
        args.output_path = "/tmp"
        args.format = ["db"]

        moe_analysis_df = pd.DataFrame({
            'Dataset': [1, 2],
            'Mean': [10, 20],
            'CI_Lower': [8, 18],
            'CI_Upper': [12, 22]
        })
        data = {NAME: moe_analysis_df}
        ExporterMoe.initialize(args)
        ExporterMoe.export(data)

        mock_save_csv.assert_not_called()
        mock_plot.assert_called_once_with(moe_analysis_df, os.path.join(args.output_path, OUTPUT_PNG_NAME))

    @patch('ms_service_profiler.exporters.exporter_moe.save_dataframe_to_csv')
    @patch('ms_service_profiler.exporters.exporter_moe.add_table_into_visual_db')
    @patch('ms_service_profiler.exporters.exporter_moe.plot_confidence_interval')
    def test_export_png_format(self, mock_plot, mock_add_table, mock_save_csv):
        args = MagicMock()
        args.output_path = "/tmp"
        args.format = ["png"]

        moe_analysis_df = pd.DataFrame({
            'Dataset': [1, 2],
            'Mean': [10, 20],
            'CI_Lower': [8, 18],
            'CI_Upper': [12, 22]
        })
        data = {NAME: moe_analysis_df}
        ExporterMoe.initialize(args)
        ExporterMoe.export(data)

        mock_save_csv.assert_not_called()
        mock_add_table.assert_not_called()
        mock_plot.assert_called_once_with(moe_analysis_df, os.path.join(args.output_path, OUTPUT_PNG_NAME))

    @patch('ms_service_profiler.exporters.exporter_moe.save_dataframe_to_csv')
    @patch('ms_service_profiler.exporters.exporter_moe.add_table_into_visual_db')
    @patch('ms_service_profiler.exporters.exporter_moe.plot_confidence_interval')
    def test_export_all_formats(self, mock_plot, mock_add_table, mock_save_csv):
        args = MagicMock()
        args.output_path = "/tmp"
        args.format = ["csv", "db", "png"]

        moe_analysis_df = pd.DataFrame({
            'Dataset': [1, 2],
            'Mean': [10, 20],
            'CI_Lower': [8, 18],
            'CI_Upper': [12, 22]
        })
        data = {NAME: moe_analysis_df}
        ExporterMoe.initialize(args)
        ExporterMoe.export(data)

        mock_save_csv.assert_called_once_with(moe_analysis_df, args.output_path, OUTPUT_CSV_NAME)
        mock_plot.assert_called_once_with(moe_analysis_df, os.path.join(args.output_path, OUTPUT_PNG_NAME))
