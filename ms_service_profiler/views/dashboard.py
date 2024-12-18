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

import json
import logging

import requests

logging.basicConfig(level=logging.INFO)

BATCH_QUERY_TEXT = """
WITH numbered_data AS (
    SELECT 
        ROW_NUMBER() OVER (ORDER BY batch_size) - 1 AS batch_id,
        batch_size,
        batch_type
    FROM batch
    WHERE name = 'BatchSchedule'
)
SELECT 
    batch_id, 
    batch_size, 
    batch_type
FROM numbered_data
ORDER BY batch_id;
"""


REQ_STATUS_QUERY_TEXT = """
SELECT 
    *
FROM request_status
ORDER BY "time/us";
"""


def create_dashboard(grafana_url, token, datasource_uid):
    dashboard_json = create_dashboard_json(datasource_uid)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    url = f"{grafana_url}/api/dashboards/db"

    try:
        response = requests.post(url, data=json.dumps(dashboard_json), headers=headers)

        if response.status_code == 200:
            return grafana_url
        else:
            raise ValueError(f"Failed to configure dashboard: {response.status_code}, {response.text}")
    except requests.RequestException as e:
        logging.error(f"An error occurred during the request: {e}")
        raise
    except Exception as e:
        logging.error(f"An unknown error occurred: {e}")
        raise


def create_dashboard_json(datasource_uid):
    return {
        "dashboard": {
            "id": None,
            "title": "Profiler Visualization RNX11111",
            "panels": [
                create_batch_panel(datasource_uid),
                create_req_status_panel(datasource_uid),
                ],
        },
        "overwrite": True,
    }


def create_req_status_panel(datasource_uid):
    return {
        "type": "xychart",
        "title": "Request Status",
        "gridPos": {
            "x": 0,
            "y": 0,
            "h": 8,
            "w": 12
        },
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "show": "lines",
                    "pointShape": "circle",
                },
            },
        },
        "pluginVersion": "11.3.0",
        "targets": [create_req_status_target(datasource_uid)],
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}",
        },
        "options": {
            "legend": {
                "showLegend": True,
                "displayMode": "list",
                "placement": "bottom",
            }
        },
    }


def create_batch_panel(datasource_uid):
    return {
        "type": "xychart",
        "title": "Batch Size by Batch ID",
        "gridPos": {
            "x": 0,
            "y": 0,
            "h": 8,
            "w": 12
        },
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "show": "lines",
                    "pointShape": "circle",
                },
            },
        },
        "pluginVersion": "11.3.0",
        "targets": [create_batch_target(datasource_uid)],
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}",
        },
        "options": {
            "legend": {
                "showLegend": True,
                "displayMode": "list",
                "placement": "bottom",
            }
        },
    }


def create_batch_target(datasource_uid):
    return {
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}",
        },
        "queryText": BATCH_QUERY_TEXT,
        "queryType": "table",
        "rawQueryText": BATCH_QUERY_TEXT,
        "refId": "A",
    }


def create_req_status_target(datasource_uid):
    return {
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}",
        },
        "queryText": REQ_STATUS_QUERY_TEXT,
        "queryType": "table",
        "rawQueryText": REQ_STATUS_QUERY_TEXT,
        "refId": "A",
    }
