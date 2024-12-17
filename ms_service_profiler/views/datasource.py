import json
import requests
import os


def create_datasource(grafana_url, token, db_path):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'  # 使用 Bearer Token 认证
    }
    url = f"{grafana_url}/api/datasources"
    datasource_json = {
        "name": "Profiler SQLite Datasource",  # 数据源名称
        "type": "frser-sqlite-datasource",  # 数据源类型
        "typeName": "SQLite",
        "access": "proxy",  # 代理方式
        "isDefault": True,  # 设置为默认数据源
        "jsonData": {
            "attachLimit": 0,
            "path": f"{os.path.abspath(db_path)}",
            "pathPrefix": "file:"
        }
    }
    try:
        response = requests.post(url, data=json.dumps(datasource_json), headers=headers)

        if response.status_code == 200:
            datasource_uid = response.json()['datasource']['uid']
            return datasource_uid
        else:
            raise ValueError(f"Failed to configure datasource: {response.status_code}, {response.text}")

    except requests.RequestException as e:
        print(f"An error occurred during the request: {e}")
    except ValueError as ve:
        print(f"Error while processing the response: {ve}")
    except Exception as e:
        print(f"An unknown error occurred: {e}")
