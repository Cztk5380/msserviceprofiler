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

from collections import defaultdict
import re

import pandas as pd

from ms_service_profiler.plugins.base import PluginBase 
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger


class PluginConcat(PluginBase):
    name = "plugin_concat"
    depends = ["plugin_timestamp"]

    HASH_RID_SUFFIX_PATTERN = r'-[a-f0-9]{8}$'
    HASH_RID_SUFFIX_RE = re.compile(HASH_RID_SUFFIX_PATTERN)
    HASH_SUFFIX_LEN = 9
    ORIGINAL_RID_EVENT_NAMES = {"httpReq", "tokenize"}

    @staticmethod
    def _merge_msprof_data(data):
        """Merge msprof_data from all ranks."""
        msprof_merged = []
        for data_single in data:
            value = data_single.get("msprof_data")
            if isinstance(value, list):
                msprof_merged.extend(value)
            elif value is not None:
                msprof_merged.append(value)
        return msprof_merged

    @classmethod
    def _build_rid_hash_mapping(cls, data_df):
        """
        In vllm v1, early events such as httpReq/tokenize use the original rid,
        while queued/execution events may carry a "-xxxxxxxx" hash suffix.
        Build a mapping: hashed rid -> original rid.
        """
        if data_df is None or data_df.empty:
            return {}

        if 'rid' not in data_df.columns or 'name' not in data_df.columns:
            return {}

        original_rids = set()
        original_rid_df = data_df[data_df['name'].isin(cls.ORIGINAL_RID_EVENT_NAMES)]
        cls._collect_unique_rids_from_series(original_rid_df['rid'], original_rids)

        if not original_rids:
            return {}

        rid_columns = [col for col in ('rid', 'rid_list', 'res_list') if col in data_df.columns]
        observed_rids = set()

        for column in rid_columns:
            cls._collect_unique_rids_from_series(data_df[column], observed_rids)

        observed_rids.difference_update(original_rids)

        hash_rid_map = {}
        for rid_str in observed_rids:
            original_rid = cls._find_original_rid_for_variant(rid_str, original_rids)
            if original_rid is not None:
                hash_rid_map[rid_str] = original_rid

        return hash_rid_map

    @classmethod
    def _collect_unique_rids_from_series(cls, series, output_set):
        if series is None:
            return

        for rid_value in series.dropna():
            cls._collect_rids_from_value(rid_value, output_set)

    @classmethod
    def _collect_rids_from_value(cls, rid_value, output_set):
        if rid_value is None:
            return

        if isinstance(rid_value, str):
            if ',' not in rid_value:
                rid_str = rid_value.strip()
                if rid_str and rid_str not in ('nan', 'None'):
                    output_set.add(rid_str)
                return

            for rid_item in rid_value.split(','):
                rid_str = rid_item.strip()
                if rid_str and rid_str not in ('nan', 'None'):
                    output_set.add(rid_str)
            return

        if isinstance(rid_value, dict):
            if 'rid' in rid_value:
                cls._collect_rids_from_value(rid_value['rid'], output_set)
            return

        if isinstance(rid_value, (list, tuple)):
            for item in rid_value:
                cls._collect_rids_from_value(item, output_set)
            return

        rid_str = str(rid_value).strip()
        if rid_str and rid_str not in ('nan', 'None'):
            output_set.add(rid_str)

    @classmethod
    def _find_original_rid_for_variant(cls, rid_str, original_rids):
        if len(rid_str) > cls.HASH_SUFFIX_LEN and rid_str[-cls.HASH_SUFFIX_LEN] == '-':
            suffix = rid_str[-cls.HASH_SUFFIX_LEN:]
            if cls.HASH_RID_SUFFIX_RE.match(suffix):
                prefix = rid_str[:-cls.HASH_SUFFIX_LEN]
                if prefix in original_rids:
                    return prefix

        search_end = len(rid_str)
        while True:
            hyphen_index = rid_str.rfind('-', 0, search_end)
            if hyphen_index == -1:
                break

            prefix = rid_str[:hyphen_index]
            if prefix in original_rids:
                return prefix

            search_end = hyphen_index

        return None

    @classmethod
    def _extract_all_rid_strs(cls, rid):
        """Extract all rid strings from scalars, joined strings, dicts, or lists."""
        if rid is None:
            return

        if isinstance(rid, str):
            for rid_item in rid.split(','):
                rid_str = rid_item.strip()
                if rid_str:
                    yield rid_str
        elif isinstance(rid, dict):
            if 'rid' in rid:
                yield from cls._extract_all_rid_strs(rid['rid'])
        elif isinstance(rid, (list, tuple)):
            for item in rid:
                yield from cls._extract_all_rid_strs(item)
        else:
            yield str(rid).strip()

    @classmethod
    def _map_rid_value(cls, rid_value, rid_map):
        if rid_value is None:
            return rid_value

        if isinstance(rid_value, str):
            if ',' not in rid_value:
                rid_str = rid_value.strip()
                if not rid_str:
                    return rid_value
                return rid_map.get(rid_str, rid_str)

            mapped_rids = []
            for rid_item in rid_value.split(','):
                rid_str = rid_item.strip()
                if rid_str:
                    mapped_rids.append(rid_map.get(rid_str, rid_str))
            if not mapped_rids:
                return rid_value
            return ','.join(mapped_rids)

        if isinstance(rid_value, list):
            return [cls._map_rid_value(item, rid_map) for item in rid_value]

        if isinstance(rid_value, tuple):
            return tuple(cls._map_rid_value(item, rid_map) for item in rid_value)

        if isinstance(rid_value, dict):
            if 'rid' not in rid_value:
                return rid_value
            new_item = dict(rid_value)
            new_item['rid'] = cls._map_rid_value(rid_value['rid'], rid_map)
            return new_item

        return rid_value

    @classmethod
    def _get_mapping_rid(cls, rid, rid_map):
        format_rid = str(rid)
        try:
            format_rid = str(int(rid))
        except (ValueError, TypeError):
            pass
        if rid_map is None:
            return format_rid
        return rid_map.get(format_rid, format_rid)

    @classmethod
    def _mapping_rid(cls, rid, rid_map):
        if isinstance(rid, list):
            return [cls._mapping_rid(i, rid_map) for i in rid]
        if isinstance(rid, dict):
            if 'rid' in rid:
                rid = dict(rid)
                rid['rid'] = cls._get_mapping_rid(rid['rid'], rid_map)
            return rid
        return cls._get_mapping_rid(rid, rid_map)

    @classmethod
    def _extract_rid(cls, rid):
        rid_list, token_id_list, dp_list = [], [], []
        if isinstance(rid, list):
            for req in rid:
                if isinstance(req, dict):
                    rid_list.append(req.get('rid'))
                    if req.get('dp'):
                        dp_list.append(req.get('dp'))
                    else:
                        iter_value = req.get('iter')
                        if iter_value is not None:
                            try:
                                token_id_list.append(int(iter_value))
                            except (ValueError, TypeError):
                                token_id_list.append(None)
                        else:
                            token_id_list.append(None)
                else:
                    rid_list.append(req)
                    token_id_list.append(None)
            rid = ','.join(map(str, rid_list))
        else:
            rid_list = [rid] if rid is not None else []
            token_id_list = []
            dp_list = []
        return rid, rid_list, token_id_list, dp_list

    @classmethod
    def _apply_rid_mapping(cls, data_df, rid_map):
        """Apply rid mapping to rid/rid_list/res_list columns in the merged dataframe."""
        if data_df is None or data_df.empty or 'rid' not in data_df.columns:
            return data_df

        if not rid_map:
            return data_df

        str_cache = {}

        def map_value_with_cache(value):
            if isinstance(value, str):
                cached_value = str_cache.get(value)
                if cached_value is not None:
                    return cached_value
                mapped_value = cls._map_rid_value(value, rid_map)
                str_cache[value] = mapped_value
                return mapped_value
            return cls._map_rid_value(value, rid_map)

        data_df['rid'] = data_df['rid'].map(map_value_with_cache)

        if 'rid_list' in data_df.columns:
            data_df['rid_list'] = data_df['rid_list'].map(lambda rid_list: cls._map_rid_value(rid_list, rid_map))

        if 'res_list' in data_df.columns:
            data_df['res_list'] = data_df['res_list'].map(lambda res_list: cls._map_rid_value(res_list, rid_map))

        return data_df

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        merged_data = defaultdict(pd.DataFrame)
        merge_list = defaultdict(list)

        for data_single in data:
            for key, value in data_single.items():
                if isinstance(value, pd.DataFrame):
                    merge_list[key].append(value)

        for key, df_list in merge_list.items():
            merged_data[key] = pd.concat(df_list, ignore_index=True)

        msprof_merged = cls._merge_msprof_data(data)

        if msprof_merged:
            merged_data["msprof_data"] = msprof_merged

        # 避免丢失 pid_label_map
        pid_label_map = {}
        for data_single in data:
            if 'pid_label_map' in data_single and data_single['pid_label_map'] is not None:
                if isinstance(data_single['pid_label_map'], dict):
                    pid_label_map.update(data_single['pid_label_map'])

        if pid_label_map:
            merged_data["pid_label_map"] = pid_label_map

        for key, value in merged_data.items():
            if isinstance(value, pd.DataFrame):
                merged_data[key] = value.sort_values(by='start_time', ascending=True).reset_index(drop=True)

        tx_data_df = merged_data.get('tx_data_df')
        if tx_data_df is not None and not tx_data_df.empty:
            try:
                hash_rid_map = cls._build_rid_hash_mapping(tx_data_df)
                if hash_rid_map:
                    logger.info(
                        f"[RidMapping] PluginConcat: Built hash rid mapping for {len(hash_rid_map)} rids after merge"
                    )
                    merged_data['tx_data_df'] = cls._apply_rid_mapping(tx_data_df, hash_rid_map)
            except (TypeError, ValueError, KeyError) as ex:
                logger.warning(f"[RidMapping] PluginConcat: Failed to apply rid mapping, skip it. error: {ex}")

        return merged_data
