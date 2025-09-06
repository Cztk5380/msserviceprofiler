# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import numpy as np
import pandas as pd

from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer, Timer
from ms_service_profiler.processor.processor_base import ProcessorBase


# 定义常量标识是否已打印过
_batch_token_iter_warning_issued = False


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
    def parse_node_role(data_df: pd.DataFrame):
        role_df = data_df[data_df["name"].isin(["prefillRes", "decodeRes"])]
        role_dict = dict(zip(role_df['pid'], role_df['name'].map(dict(prefillRes=1, decodeRes=2))))
        return role_dict

    @staticmethod
    def batch_token_iter_to_batch_type(token_iter_list):
        global _batch_token_iter_warning_issued
        # 统一处理空值和非列表/元组类型
        if (token_iter_list is None
                or (np.isscalar(token_iter_list) and pd.isna(token_iter_list))
                or not isinstance(token_iter_list, (list, tuple))):
            if not _batch_token_iter_warning_issued:
                logger.warning(f"Warning: Skipping invalid row type {type(token_iter_list)}: {token_iter_list}")
                _batch_token_iter_warning_issued = True
            return 1

        # 处理空列表
        if not token_iter_list:
            return 1

        # 处理含NaN的列表
        if pd.isna(token_iter_list).any():
            return 1

        # 有效列表的判断（无重复）
        if all(token_iter_list):  # 全部大于0
            return 2
        elif any(token_iter_list):  # 存在0和非0
            return 0
        else:  # 全为0
            return 1

    @timer(logger.debug)
    def parse_batch(self, data_df: pd.DataFrame):
        batch_event_df = pd.DataFrame(columns=["batch_id", "event", "start_time", "end_time", "pid", "blocks"])
        batch_attr_df = pd.DataFrame(columns=["batch_id", "req_list", "req_id_list", "batch_size", "batch_type"])

        if data_df is None or data_df.empty:
            return batch_event_df, batch_attr_df
        
        if "name" not in data_df or "res_list" not in data_df or "token_id_list" not in data_df or "rid_list" not in data_df:
            return batch_event_df, batch_attr_df
        role_dict = self.parse_node_role(data_df)

        # forward 之后补充
        batch_data_df = data_df[data_df["name"].isin(["BatchSchedule", "modelExec", "batchFrameworkProcessing",
                                                      "Execute", "preprocess", "forward"])]


        # 先不考虑 batch_id 重复的情况
        batch_id_df = batch_data_df["res_list"].map(str)

        # 过滤掉PD分离场景，batch type 判断错误的数据
        role_batch_type = batch_data_df['pid'].map(role_dict)
        iter_batch_type = batch_data_df["token_id_list"].map(lambda row: self.batch_token_iter_to_batch_type(row))

        right_role_batch_type = role_batch_type.isna()  # 没有PD分离的数据
        right_iter_batch_type = iter_batch_type == role_batch_type  # 判断正确的数据
        right_decode_batch_type = batch_data_df[(role_batch_type == 2) & (iter_batch_type == 1)] \
            .groupby(['name', batch_id_df]).cumcount(ascending=False) == 0  # D节点最后一个判断为P 的数据

        right_batch_type_mask = right_role_batch_type | right_iter_batch_type | right_decode_batch_type
        batch_data_df = batch_data_df[right_batch_type_mask]

        # 过滤后数据填充 data frame 返回
        batch_event_df["batch_id"] = batch_id_df[right_batch_type_mask]
        batch_event_df["event"] = batch_data_df["name"]
        batch_event_df["pid"] = batch_data_df["pid"]

        # 只有当 blocks 列存在时才添加到 batch_event_df
        if "blocks" in batch_data_df.columns:
            batch_event_df["blocks"] = batch_data_df["blocks"]

        batch_event_df["start_time"] = batch_data_df["start_time"]
        batch_event_df["end_time"] = batch_data_df["end_time"]

        schedule_mask = batch_data_df["name"].isin(["BatchSchedule", "batchFrameworkProcessing"])
        schedule_data_df = batch_data_df[schedule_mask]
        # 创建过滤条件：所有三个列都非空列表
        schedule_data_df = schedule_data_df[
            (schedule_data_df['res_list'].apply(len) > 0) &
            (schedule_data_df['rid_list'].apply(len) > 0) &
            (schedule_data_df['token_id_list'].apply(len) > 0)
            ]
        batch_attr_df["batch_id"] = batch_event_df[schedule_mask]["batch_id"]
        batch_attr_df["req_list"] = schedule_data_df["res_list"]
        batch_attr_df["req_id_list"] = schedule_data_df["rid_list"]
        batch_attr_df["batch_size"] = schedule_data_df["rid_list"].map(len)
        batch_attr_df["batch_type"] = role_batch_type.combine_first(iter_batch_type)

        return batch_event_df, batch_attr_df

    @timer(logger.debug)
    def parse_req(self, data_df: pd.DataFrame, batch_event_df: pd.DataFrame, batch_attr_df: pd.DataFrame):
        req_event_df = pd.DataFrame(columns=["rid", "event", "iter", "start_time", "end_time", "batch_id"])
        req_attr_df = pd.DataFrame(columns=["rid", "recv_token", "reply_token", "ttft"])
        req_queue_df = pd.DataFrame(columns=["rid", "start_time", "end_time", "event", "status"])

        if data_df is None or data_df.empty:
            return req_event_df, req_attr_df, req_queue_df
        
        if "name" not in data_df or "res_list" not in data_df or "token_id_list" not in data_df or "rid_list" not in data_df:
            return req_event_df, req_attr_df, req_queue_df

        # 1. 取httpReq 和 httpRes 
        # 有问题，P 节点 和D 节点的 httpReq 和 http Res 需要区分开。需要修复 todo 
        http_event_df = data_df[data_df["name"].isin(["httpReq", "httpRes", "decode", "DecodeEnd", "sendResponse"])]
        req_event_df["rid"] = http_event_df["rid"]
        req_event_df["event"] = http_event_df["name"]
        req_event_df["start_time"] = http_event_df["start_time"]
        req_event_df["end_time"] = http_event_df["end_time"]
        req_event_df["end_flag"] = http_event_df.get("endFlag", None)
        
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

        # 2. 构建请求队列用于后续计算队列等待时长
        status_col = data_df.get('status')
        if status_col is not None:
            mask = data_df['name'].isin(['Dequeue', 'Enqueue']) & (data_df['status'] == 'waiting')
        else:
            # 处理列不存在的情况
            mask = data_df['name'].isin(['Dequeue', 'Enqueue'])  # 或者其他逻辑

        # loc 一次性赋值，不触发警告
        tmp = data_df.loc[mask, :].copy(deep=False)  # 浅拷贝，内存开销小
        tmp['rid'] = tmp['rid'].astype(str).str.strip().str.split(r'\s*,\s*')
        # 在构造 req_queue_df 时
        status_col = tmp.get('status')
        selected_columns = ['rid', 'start_time', 'end_time', 'event']
        if status_col is not None:
            selected_columns.append('status')

        req_queue_df = (
            tmp
            .explode('rid')
            .query('rid.str.strip() != ""')
            .rename(columns={'name': 'event'})
            [selected_columns]
        )

        # 3. 拆解Batch
        model_exec_df = batch_event_df[batch_event_df["event"].isin(["modelExec", "Execute"])]
        # 根据 batch id 找到 req_id_list， 拆解开

        batch_attr_explode_by_req_df = batch_attr_df.explode('req_list')
        batch_attr_explode_by_req_df['rid'] = batch_attr_explode_by_req_df['req_list'].map(
            lambda x: x.get("rid") if isinstance(x, dict) else None
        )
        batch_attr_explode_by_req_df['iter'] = batch_attr_explode_by_req_df['req_list'].map(
            lambda x: x.get("iter") if isinstance(x, dict) else None
        )

        merged = batch_attr_explode_by_req_df.join(model_exec_df.set_index('batch_id'), on='batch_id')

        req_event_df = pd.concat([req_event_df, merged[["rid", "event", "iter", "start_time", "end_time", "batch_id"]]], ignore_index=True)
        return req_event_df, req_attr_df, req_queue_df

    @timer(logger.debug)
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

        # 如果有 sendResponse，取最后一个
        last_send_response = req_event_df[req_event_df["event"] == "sendResponse"].groupby("rid").last()
        if not last_send_response.empty:
            last_send_response["rid"] = last_send_response.index
            calc_df = pd.concat([calc_df, last_send_response])

        group_by_df = calc_df.groupby("rid").agg({
            "start_time": "min",
            "end_time": "max",
            "event": ["first", 'count']
        }).reset_index()

        group_by_df.columns = ['rid', 'start_time', 'end_time', 'event_first', 'event_count']

        req_ttft_df = group_by_df[
            (group_by_df['event_count'] > 1) &
            (group_by_df['event_first'] == 'httpReq')
            ]

        req_ttft_df["ttft"] = req_ttft_df['end_time'] - req_ttft_df['start_time']
        req_ttft_df = req_ttft_df.drop(columns=['event_first', 'event_count'])
        return req_ttft_df

    @timer(logger.debug)
    def calc_que_wait(self, req_queue_df: pd.DataFrame):
        """
        队列等待时长逻辑为按rid分组后，使用Dequeue的结束时间减去Enqueue的开始时间
        由于都是瞬时的点，故开始时间和结束时间相同
        """
        req_que_wait_df = pd.DataFrame(columns=["rid", "que_wait_time"])

        if req_queue_df is None or req_queue_df.empty:
            return req_que_wait_df

        # 1. 把事件拆成两类
        enq = req_queue_df[req_queue_df["event"] == "Enqueue"]
        deq = req_queue_df[req_queue_df["event"] == "Dequeue"]

        # 2. 聚合：取 Enqueue 的最早 start_time 和 Dequeue 的最晚 end_time
        enq_agg = enq.groupby("rid")["start_time"].min().rename("enq_start")
        deq_agg = deq.groupby("rid")["end_time"].max().rename("deq_end")

        # 3. 合并、计算等待时长（秒）
        req_que_wait_df = (
            pd.concat([enq_agg, deq_agg], axis=1)
            .assign(que_wait_time=lambda x: (x["deq_end"] - x["enq_start"]))
            .reset_index()
            .loc[:, ["rid", "que_wait_time"]]
        )

        return req_que_wait_df

    def parse(self, data_df: pd.DataFrame):
        batch_event_df, batch_attr_df = self.parse_batch(data_df)
        req_event_df, req_attr_df, req_queue_df = (
            self.parse_req(data_df, batch_event_df, batch_attr_df)
        )

        req_ttft_df = self.calc_ttft(req_event_df)
        req_queue_wait_time_df = self.calc_que_wait(req_queue_df)
        req_attr_df["ttft"] = req_ttft_df["ttft"]

        # ttft 和 que_wait_time为原始数据，单位为微秒，需要exporter中调用时进行单位转换

        return {
            "req_event_df": req_event_df, 
            "req_attr_df": req_attr_df,
            "batch_event_df": batch_event_df, 
            "batch_attr_df": batch_attr_df,
            "req_ttft_df": req_ttft_df,
            "req_que_wait_df": req_queue_wait_time_df
        }
