# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import json

import requests

from ms_service_profiler.utils.log import logger

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
    CASE 
        WHEN batch_type = 'Prefill' THEN batch_size
        ELSE NULL
    END AS Prefill_batch_size,
    CASE 
        WHEN batch_type = 'Decode' THEN batch_size
        ELSE NULL
    END AS Decode_batch_size
FROM numbered_data
ORDER BY batch_id;
"""

FIRST_TOKEN_LATENCY_SQL = """
WITH converted AS (
    SELECT
        substr(timestamp, 1, 10) || 'T' || substr(timestamp, 12, 8) || 'Z' AS datetime,
        avg,
        p99,
        p90,
        p50
    FROM
        first_token_latency
)
SELECT
    datetime as time,
    cast(avg as REAL) as "avg",
    cast(p99 as REAL) as "p99",
    cast(p90 as REAL) as "p90",
    cast(p50 as REAL) as "p50"
FROM
    converted
ORDER BY
    datetime ASC;
"""

PREFILL_GEN_SPEED_LATENCY_SQL = """
WITH converted AS (
    SELECT
        substr(timestamp, 1, 10) || 'T' || substr(timestamp, 12, 8) || 'Z' AS datetime,
        avg,
        p99,
        p90,
        p50
    FROM
        prefill_gen_speed
)
SELECT
    datetime as time,
    cast(avg as REAL) as "avg",
    cast(p99 as REAL) as "p99",
    cast(p90 as REAL) as "p90",
    cast(p50 as REAL) as "p50"
FROM
    converted
ORDER BY
    datetime ASC;
"""

DECODE_GEN_SPEED_LATENCY_SQL = """
WITH converted AS (
    SELECT
        substr(timestamp, 1, 10) || 'T' || substr(timestamp, 12, 8) || 'Z' AS datetime,
        avg,
        p99,
        p90,
        p50
    FROM
        decode_gen_speed
)
SELECT
    datetime as time,
    cast(avg as REAL) as "avg",
    cast(p99 as REAL) as "p99",
    cast(p90 as REAL) as "p90",
    cast(p50 as REAL) as "p50"
FROM
    converted
ORDER BY
    datetime ASC;
"""

REQ_LATENCY_SQL = """
WITH converted AS (
    SELECT
        substr(timestamp, 1, 10) || 'T' || substr(timestamp, 12, 8) || 'Z' AS datetime,
        avg,
        p99,
        p90,
        p50
    FROM
        req_latency
)
SELECT
    datetime as time,
    cast(avg as REAL) as "avg",
    cast(p99 as REAL) as "p99",
    cast(p90 as REAL) as "p90",
    cast(p50 as REAL) as "p50"
FROM
    converted
ORDER BY
    datetime ASC;
"""

KVCACHE_QUERY_TEXT = """
WITH converted AS (
    SELECT
        kvcache_usage_rate * 100 AS kvcache_usage_percent,
        substr(real_start_time, 1, 10) || 'T' || substr(real_start_time, 12, 8) || 'Z' AS datetime
    FROM
        kvcache
)
SELECT
    datetime as time,
    cast(kvcache_usage_percent as REAL) as "kvcacge_usage"
FROM
    converted
ORDER BY
    datetime ASC;
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
        logger.error(f"An error occurred during the request: {e}")
        raise
    except Exception as e:
        logger.error(f"An unknown error occurred: {e}")
        raise


def create_dashboard_json(datasource_uid):
    return {
        "dashboard": {
            "id": None,
            "title": "Profiler Visualization",
            "panels": [
                create_batch_panel(datasource_uid),
                create_first_token_panel(datasource_uid),
                create_prefill_gen_speed_panel(datasource_uid),
                create_decode_gen_speed_panel(datasource_uid),
                create_request_latency_panel(datasource_uid),
                create_req_status_panel(datasource_uid),
                create_kvcache_panel(datasource_uid)
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


def get_kvcache_default_panel():
    return {
        "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "lineWidth": 1,
            "fillOpacity": 0,
            "gradientMode": "none",
            "spanNulls": False,
            "insertNulls": False,
            "showPoints": "auto",
            "pointSize": 5,
            "stacking": {
            "mode": "none",
            "group": "A"
            },
            "axisPlacement": "auto",
            "axisLabel": "",
            "axisColorMode": "text",
            "axisBorderShow": False,
            "scaleDistribution": {
                "type": "linear"
            },
            "axisCenteredZero": False,
            "hideFrom": {
                "tooltip": False,
                "viz": False,
                "legend": False
            },
            "thresholdsStyle": {
            "mode": "off"
            }
        },
    }


def get_lantency_default_panel():
    return {
        "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "barAlignment": 0,
            "barWidthFactor": 0.6,
            "lineWidth": 1,
            "fillOpacity": 0,
            "gradientMode": "none",
            "spanNulls": False,
            "insertNulls": False,
            "showPoints": "auto",
            "pointSize": 5,
            "stacking": {
            "mode": "none",
            "group": "A"
            },
            "axisPlacement": "auto",
            "axisLabel": "",
            "axisColorMode": "text",
            "axisBorderShow": False,
            "scaleDistribution": {
            "type": "linear"
            },
            "axisCenteredZero": False,
            "hideFrom": {
            "tooltip": False,
            "viz": False,
            "legend": False
            },
            "thresholdsStyle": {
            "mode": "off"
            }
        }
    }


def create_first_token_panel(datasource_uid):
    return {
        "type": "timeseries",
        "title": "first_token_latency",
        "gridPos": {
            "x": 0,
            "y": 16,
            "h": 8,
            "w": 12
        },
        "fieldConfig": {
            "defaults": get_lantency_default_panel(),
            "overrides": []
        },
        "pluginVersion": "11.3.0",
        "targets": [
            {
            "queryText": FIRST_TOKEN_LATENCY_SQL,
            "queryType": "time series",
            "rawQueryText": FIRST_TOKEN_LATENCY_SQL,
            "refId": "A",
            "timeColumns": [
                "time",
                "ts"
            ]
            }
        ],
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}"
        }
    }


def create_prefill_gen_speed_panel(datasource_uid):
    return {
        "type": "timeseries",
        "title": "prefill_generate_speed_latency",
        "gridPos": {
            "x": 0,
            "y": 16,
            "h": 8,
            "w": 12
        },
        "fieldConfig": {
            "defaults": get_lantency_default_panel(),
            "overrides": []
        },
        "pluginVersion": "11.3.0",
        "targets": [
            {
            "queryText": PREFILL_GEN_SPEED_LATENCY_SQL,
            "queryType": "time series",
            "rawQueryText": PREFILL_GEN_SPEED_LATENCY_SQL,
            "refId": "A",
            "timeColumns": [
                "time",
                "ts"
            ]
            }
        ],
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}"
        }
    }


def create_decode_gen_speed_panel(datasource_uid):
    return {
        "type": "timeseries",
        "title": "decode_generate_speed_latency",
        "gridPos": {
            "x": 0,
            "y": 16,
            "h": 8,
            "w": 12
        },
        "fieldConfig": {
            "defaults": get_lantency_default_panel(),
            "overrides": []
        },
        "pluginVersion": "11.3.0",
        "targets": [
            {
            "queryText": DECODE_GEN_SPEED_LATENCY_SQL,
            "queryType": "time series",
            "rawQueryText": DECODE_GEN_SPEED_LATENCY_SQL,
            "refId": "A",
            "timeColumns": [
                "time",
                "ts"
            ]
            }
        ],
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}"
        }
    }


def create_kvcache_panel(datasource_uid):
    return {
        "type": "graph",
        "title": "Kvcache usage percent",
        "gridPos": {
            "x": 0,
            "y": 0,
            "h": 8,
            "w": 12
        },
        "fieldConfig": {
            "defaults": get_kvcache_default_panel(),
        },
        "pluginVersion": "11.3.0",
        "targets": [create_kvcache_target(datasource_uid)],
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


def create_request_latency_panel(datasource_uid):
    return {
        "type": "timeseries",
        "title": "request_latency",
        "gridPos": {
            "x": 0,
            "y": 16,
            "h": 8,
            "w": 12
        },
        "fieldConfig": {
            "defaults": get_lantency_default_panel(),
            "overrides": []
        },
        "pluginVersion": "11.3.0",
        "targets": [
            {
            "queryText": REQ_LATENCY_SQL,
            "queryType": "time series",
            "rawQueryText": REQ_LATENCY_SQL,
            "refId": "A",
            "timeColumns": [
                "time",
                "ts"
            ]
            }
        ],
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}"
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


def create_kvcache_target(datasource_uid):
    return {
        "datasource": {
            "type": "frser-sqlite-datasource",
            "uid": f"{datasource_uid}",
        },
        "queryText": KVCACHE_QUERY_TEXT,
        "queryType": "time series",
        "rawQueryText": KVCACHE_QUERY_TEXT,
        "refId": "A",
        "timeColumns": [
            "time",
            "ts"
        ]
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
