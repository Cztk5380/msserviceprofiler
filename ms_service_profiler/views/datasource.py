import json
import requests
import os
import logging

logging.basicConfig(level=logging.INFO)


def create_datasource(grafana_url, token, db_path):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'  # 使用 Bearer Token 认证
    }

    # 数据源的 JSON 配置
    datasource_json = {
        "name": "Profiler SQLite Datasource",  # 数据源名称
        "type": "frser-sqlite-datasource",  # 数据源类型
        "typeName": "SQLite",
        "access": "proxy",  # 代理方式
        "isDefault": True,  # 设置为默认数据源
        "jsonData": {
            "attachLimit": 0,
            "path": os.path.abspath(db_path),  # 使用绝对路径
            "pathPrefix": "file:"
        }
    }

    # 获取数据源ID，如果已存在则更新
    datasource_id = is_datasource_exists(grafana_url, token)

    if datasource_id:
        # 如果数据源已存在，更新数据源
        update_url = f'{grafana_url}/api/datasources/{datasource_id}'
        return update_or_create_datasource(update_url, datasource_json, headers, is_update=True)
    else:
        # 如果数据源不存在，创建数据源
        create_url = f"{grafana_url}/api/datasources"
        return update_or_create_datasource(create_url, datasource_json, headers, is_update=False)


def update_or_create_datasource(url, datasource_json, headers, is_update=False):
    try:
        if is_update:
            response = requests.put(url, data=json.dumps(datasource_json), headers=headers)
        else:
            response = requests.post(url, data=json.dumps(datasource_json), headers=headers)

        if response.status_code == 200:
            datasource_uid = response.json()['datasource']['uid']
            logging.info(f"Datasource {'updated' if is_update else 'created'} successfully. UID: {datasource_uid}")
            return datasource_uid
        else:
            raise ValueError(f"Failed to configure datasource: {response.status_code}, {response.text}")

    except requests.RequestException as e:
        logging.error(f"An error occurred during the request: {e}")
        raise
    except Exception as e:
        logging.error(f"An unknown error occurred: {e}")
        raise


def is_datasource_exists(grafana_url, token):
    url = f"{grafana_url}/api/datasources"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            datasources = response.json()
            for datasource in datasources:
                if datasource['name'] == "Profiler SQLite Datasource":
                    logging.info(f"Datasource 'Profiler SQLite Datasource' exists.")
                    return datasource['id']
            logging.info("Datasource 'Profiler SQLite Datasource' not found, create a new datasource.")
        else:
            raise ValueError(f"Failed to fetch datasources: {response.status_code}, {response.text}")

    except requests.RequestException as e:
        logging.error(f"An error occurred while checking the datasource: {e}")
        raise
    except Exception as e:
        logging.error(f"An unknown error occurred: {e}")