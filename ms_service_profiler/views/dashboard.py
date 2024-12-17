import json
import requests
import logging

logging.basicConfig(level=logging.INFO)

batch_query_text = """
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


def create_dashboard(grafana_url, token, datasource_uid):
    dashboard_json = {
        "dashboard": {
            "id": None,
            "title": "Profiler Visualization",
            "panels": [
                {
                    "type": "xychart",
                    "title": "Batch Size by Batch ID",
                    "fieldConfig": {
                        "defaults": {
                            "custom": {
                                "show": "lines",
                                "pointShape": "circle",
                            },
                            "color": {
                                "mode": "palette-classic"
                            },
                        },
                        "overrides": []
                    },
                    "pluginVersion": "11.3.0",
                    "targets": [
                        {
                            "datasource": {
                                "type": "frser-sqlite-datasource",
                                "uid": f"{datasource_uid}"
                            },
                            "queryText": batch_query_text,
                            "queryType": "table",
                            "rawQueryText": batch_query_text,
                            "refId": "A",
                        }
                    ],
                    "datasource": {
                        "type": "frser-sqlite-datasource",
                        "uid": f"{datasource_uid}"
                    },
                    "options": {
                        "legend": {
                            "showLegend": True,
                            "displayMode": "list",
                            "placement": "bottom",
                            "calcs": []
                        }
                    }
                }
            ],
        },
        "overwrite": True  # 如果为 True，则会覆盖已有的同名仪表盘
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    # 创建仪表盘
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
