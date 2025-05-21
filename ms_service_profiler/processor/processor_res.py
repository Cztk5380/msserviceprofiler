# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd

from ms_service_profiler.processor.processor_base import ProcessorBase


class ProcessorRes(ProcessorBase):

    @property
    def name(self):
        return "ProcessorRes"

    def parse(self, data_df: pd.DataFrame):
        if data_df is None or data_df.empty:
            return data_df
        
        if "from" not in data_df or "to" not in data_df:
            return data_df

        rid_map = data_df[data_df['from'].notna()].set_index("to").to_dict(orient='dict')["from"]

        data_df['rid'] = data_df['rid'].map(lambda x: self.mapping_rid(x, rid_map))

        return data_df[data_df['from'].isna()]

    def mapping_rid(self, rid, rid_map):
        if isinstance(rid, list):
            return [self.mapping_rid(i, rid_map) for i in rid]
        elif isinstance(rid, dict):
            if 'rid' in rid:
                rid['rid'] = rid_map.get(rid['rid'], rid['rid'])
            return rid
        else:
            return rid_map.get(rid, rid)

    