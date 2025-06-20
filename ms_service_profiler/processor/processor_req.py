# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd

from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer, Timer
from ms_service_profiler.processor.processor_base import ProcessorBase


class ProcessorReq(ProcessorBase):

    @property
    def name(self):
        return "ProcessorReq"

    @staticmethod
    def ensure_list_size(lst, ensure_size, fill_value=0):
        if len(lst) >= ensure_size:
            return lst
        return lst + [fill_value] * (ensure_size - len(lst))


    @staticmethod
    def ensure_list_size(lst, ensure_size, fill_value=0):
        if len(lst) >= ensure_size:
            return lst
        return lst + [fill_value] * (ensure_size - len(lst))


    @staticmethod
    def parse_node_role(data_df: pd.DataFrame):
        role_df = data_df[data_df["name"].isin(["prefillRes", "decodeRes"])]
        role_dict = dict(zip(role_df['pid'], role_df['name'].map(dict(prefillRes=1, decodeRes=2))))
        return role_dict

    @staticmethod
    def batch_token_iter_to_batch_type(token_iter_list):
        if all(token_iter_list):  # 全部大于 0
            return 2
        elif any(token_iter_list): # 存在0，也存在1 
            return 0
        else:
            return 1

    @timer(logger.info)
    def parse_batch(self, data_df: pd.DataFrame):
        batch_event_df = pd.DataFrame(columns=["batch_id", "event", "start_time", "end_time"])
        batch_attr_df = pd.DataFrame(columns=["batch_id", "req_list", "req_id_list", "batch_size", "batch_type"])

        if data_df is None or data_df.empty:
            return batch_event_df, batch_attr_df
        
        if "name" not in data_df or "res_list" not in data_df or "token_id_list" not in data_df or "rid_list" not in data_df:
            return batch_event_df, batch_attr_df

        role_dict = self.parse_node_role(data_df)

        # forward 之后补充
        batch_data_df = data_df[data_df["name"].isin(["BatchSchedule", "modelExec", "batchFrameworkProcessing"])]
        # 先不考虑 batch_id 重复的情况
        batch_id_df = batch_data_df["res_list"].map(str)

        # 过滤掉PD分离场景，batch type 判断错误的数据
        role_batch_type = batch_data_df['pid'].map(role_dict)
        iter_batch_type = batch_data_df["token_id_list"].map(lambda row: self.batch_token_iter_to_batch_type(row))

        right_role_batch_type = role_batch_type.isna()  # 没有PD分离的数据
        right_iter_batch_type = iter_batch_type == role_batch_type  # 判断正确的数据
        right_decode_batch_type = batch_data_df[(role_batch_type == 2) & (iter_batch_type == 1)].groupby(['name', batch_id_df]).cumcount(ascending=False) == 0  #  D节点最后一个判断为P 的数据

        right_batch_type_mask = right_role_batch_type | right_iter_batch_type | right_decode_batch_type
        batch_data_df = batch_data_df[right_batch_type_mask]

        # 过滤后数据填充 data frame 返回
        batch_event_df["batch_id"] = batch_id_df[right_batch_type_mask]
        batch_event_df["event"] = batch_data_df["name"]
        batch_event_df["start_time"] = batch_data_df["start_time"]
        batch_event_df["end_time"] = batch_data_df["end_time"]

        schedule_mask = batch_data_df["name"].isin(["BatchSchedule", "batchFrameworkProcessing"])
        schedule_data_df = batch_data_df[schedule_mask]
        batch_attr_df["batch_id"] = batch_event_df[schedule_mask]["batch_id"]
        batch_attr_df["req_list"] = schedule_data_df["res_list"]
        batch_attr_df["req_id_list"] = schedule_data_df["rid_list"]
        batch_attr_df["batch_size"] = schedule_data_df["rid_list"].map(len)
        batch_attr_df["batch_type"] = role_batch_type.combine_first(iter_batch_type) # PD分离的话，已节点角色为准

        return batch_event_df, batch_attr_df

    @timer(logger.info)
    def parse_req(self, data_df: pd.DataFrame, batch_event_df: pd.DataFrame, batch_attr_df: pd.DataFrame):
        req_event_df = pd.DataFrame(columns=["rid", "event", "iter", "start_time", "end_time", "batch_id"])
        req_attr_df = pd.DataFrame(columns=["rid", "recv_token", "reply_token", "ttft"])

        if data_df is None or data_df.empty:
            return req_event_df, req_attr_df
        
        if "name" not in data_df or "res_list" not in data_df or "token_id_list" not in data_df or "rid_list" not in data_df:
            return req_event_df, req_attr_df

        # 1. 取httpReq 和 httpRes 
        # 有问题，P 节点 和D 节点的 httpReq 和 http Res 需要区分开。需要修复 todo 
        http_event_df = data_df[data_df["name"].isin(["httpReq", "httpRes", "decode", "DecodeEnd"])]
        req_event_df["rid"] = http_event_df["rid"]
        req_event_df["event"] = http_event_df["name"]
        req_event_df["start_time"] = http_event_df["start_time"]
        req_event_df["end_time"] = http_event_df["end_time"]
        
        rid_recv_token_map = dict()
        rid_reply_token_map = dict()

        if "recvTokenSize=" in data_df:
            recv_token_df = data_df[data_df["recvTokenSize="].notna()]
            rid_recv_token_map = recv_token_df.set_index('rid')['recvTokenSize='].to_dict()
        if "replyTokenSize=" in data_df:
            reply_token_df = data_df[data_df["replyTokenSize="].notna()]
            rid_reply_token_map = reply_token_df.set_index('rid')['replyTokenSize='].to_dict()
        
        req_attr_df = pd.DataFrame({'recv_token': rid_recv_token_map, 'reply_token': rid_reply_token_map})
        req_attr_df['rid'] = req_attr_df.index

        # 2. 拆解Batch 
        model_exec_df = batch_event_df[batch_event_df["event"] == "modelExec"]
        # 根据 batch id 找到 req_id_list， 拆解开

        batch_attr_explode_by_req_df = batch_attr_df.explode('req_list')
        batch_attr_explode_by_req_df['rid'] = batch_attr_explode_by_req_df['req_list'].map(lambda x: x.get('rid'))
        batch_attr_explode_by_req_df['iter'] = batch_attr_explode_by_req_df['req_list'].map(lambda x: x.get('iter'))

        merged = batch_attr_explode_by_req_df.join(model_exec_df.set_index('batch_id'), on='batch_id')

        req_event_df = pd.concat([req_event_df, merged[["rid", "event", "iter", "start_time", "end_time", "batch_id"]]], ignore_index=True)
        return req_event_df, req_attr_df

    @timer(logger.info)
    def calc_ttft(self, req_event_df: pd.DataFrame):
        req_ttft_df = pd.DataFrame(columns=["rid", "ttft", "start", "end"])

        if req_event_df is None or req_event_df.empty:
            return req_ttft_df

        # 取请求到达时间和第一个迭代时间
        calc_df = req_event_df[(req_event_df["event"] == "httpReq") | (req_event_df["iter"] == 0)]
        # 如果有decode ，取第一个 decode
        first_decode = req_event_df[req_event_df["event"] == "decode"].groupby("rid").first()
        first_decode["rid"] = first_decode.index
        calc_df = pd.concat([calc_df, first_decode])

        group_by_df = calc_df.groupby("rid").agg({"start_time": "min", "end_time": "max", "event": ["first", 'count']})

        req_ttft_df = group_by_df[(group_by_df["event"]["count"] > 1) & (group_by_df["event"]["first"] == 'httpReq')]
        req_ttft_df["ttft"] = req_ttft_df["end_time"]["max"] - req_ttft_df["start_time"]["min"]
        req_ttft_df["rid"] = req_ttft_df.index
        req_ttft_df = req_ttft_df.drop(columns=["event"])
        req_ttft_df.columns = req_ttft_df.columns.map(lambda x: x[0])
        return req_ttft_df


    def parse(self, data_df: pd.DataFrame):
        batch_event_df, batch_attr_df = self.parse_batch(data_df)
        req_event_df, req_attr_df = self.parse_req(data_df, batch_event_df, batch_attr_df)
        req_ttft_df = self.calc_ttft(req_event_df)
        req_attr_df["ttft"] = req_ttft_df["ttft"]
        
        return {
            "req_event_df": req_event_df, 
            "req_attr_df": req_attr_df,
            "batch_event_df": batch_event_df, 
            "batch_attr_df": batch_attr_df,
            "req_ttft_df": req_ttft_df
        }
