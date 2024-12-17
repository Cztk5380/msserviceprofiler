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
import os

import requests

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
            data_sources = response.json()
            datasource_id = get_datasource_id(data_sources)
            return datasource_id
        else:
            raise ValueError(f"Failed to fetch datasources: {response.status_code}, {response.text}")

    except requests.RequestException as e:
        logging.error(f"An error occurred while checking the datasource: {e}")
        raise
    except Exception as e:
        logging.error(f"An unknown error occurred: {e}")
        raise


def get_datasource_id(data_sources):
    datasource_id = None
    for datasource in data_sources:
        if datasource['name'] == "Profiler SQLite Datasource":
            datasource_id = datasource['id']
            logging.info(f"Datasource 'Profiler SQLite Datasource' exists, UID is {datasource_id}")
            return datasource_id
    logging.info("Datasource 'Profiler SQLite Datasource' not found, create a new datasource.")
    return datasource_id
