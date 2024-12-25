# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import patch
from ms_service_profiler.views.dashboard import (
    create_first_token_panel, get_lantency_default_panel, 
    create_prefill_gen_speed_panel, create_request_latency_panel, 
    FIRST_TOKEN_LATENCY_SQL, PREFILL_GEN_SPEED_LATENCY_SQL, REQ_LATENCY_SQL
)


class TestCreateFirstTokenPanel(unittest.TestCase):
    def test_create_lantency_default_panel(self):
        result = get_lantency_default_panel()
        self.assertIsInstance(result, dict)
        self.assertIn('custom', result)
        self.assertIn('drawStyle', result['custom'])
        self.assertEqual(result['custom']['drawStyle'], 'line')
        self.assertIn('lineInterpolation', result['custom'])
        self.assertEqual(result['custom']['lineInterpolation'], 'linear')


    @patch('ms_service_profiler.views.dashboard.get_lantency_default_panel')
    def test_create_first_token_panel(self, mock_get_lantency_default_panel):
        mock_get_lantency_default_panel.return_value = {"mock": "mock"}

        result = create_first_token_panel('0123')

        self.assertEqual(result['type'], 'timeseries')
        self.assertEqual(result['title'], 'first_token_latency')
        self.assertEqual(result['targets'][0]['queryText'], FIRST_TOKEN_LATENCY_SQL)
        self.assertEqual(result['targets'][0]['queryType'], 'time series')
        self.assertEqual(result['targets'][0]['timeColumns'], ['time', 'ts'])
        self.assertEqual(result['datasource']['type'], 'frser-sqlite-datasource')
        self.assertEqual(result['datasource']['uid'], '0123')

        mock_get_lantency_default_panel.assert_called_once()


    @patch('ms_service_profiler.views.dashboard.get_lantency_default_panel')
    def test_create_prefill_gen_speed_panel(self, mock_get_lantency_default_panel):
        mock_get_lantency_default_panel.return_value = {"mock": "mock"}

        result = create_prefill_gen_speed_panel('0123')

        self.assertEqual(result['type'], 'timeseries')
        self.assertEqual(result['title'], 'prefill_generate_speed_latency')
        self.assertEqual(result['targets'][0]['queryText'], PREFILL_GEN_SPEED_LATENCY_SQL)
        self.assertEqual(result['targets'][0]['queryType'], 'time series')
        self.assertEqual(result['targets'][0]['timeColumns'], ['time', 'ts'])
        self.assertEqual(result['datasource']['type'], 'frser-sqlite-datasource')
        self.assertEqual(result['datasource']['uid'], '0123')

    @patch('ms_service_profiler.views.dashboard.get_lantency_default_panel')
    def test_create_request_latency_panel(self, mock_get_lantency_default_panel):
        mock_get_lantency_default_panel.return_value = {"mock": "defaults"}

        result = create_request_latency_panel('0123')

        self.assertEqual(result['type'], 'timeseries')
        self.assertEqual(result['title'], 'request_latency')
        self.assertEqual(result['targets'][0]['queryText'], REQ_LATENCY_SQL)
        self.assertEqual(result['targets'][0]['queryType'], 'time series')
        self.assertEqual(result['targets'][0]['timeColumns'], ['time', 'ts'])
        self.assertEqual(result['datasource']['type'], 'frser-sqlite-datasource')
        self.assertEqual(result['datasource']['uid'], '0123')

        mock_get_lantency_default_panel.assert_called_once()


if __name__ == '__main__':
    unittest.main()