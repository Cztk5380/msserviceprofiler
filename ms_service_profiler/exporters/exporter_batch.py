# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import save_dataframe_to_csv
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import add_table_into_visual_db
from ms_service_profiler.constant import US_PER_MS


def is_contained_vaild_dp_batch_info(rid_list, dp_id_list):
    if rid_list is None or dp_id_list is None or len(rid_list) != len(dp_id_list):
        return False
    return True


def get_forward_info(df):
    forward_df = df[df['name'] == 'forward']
    df_list = forward_df.groupby('pid')
    forward_df_list = []
    for _, pre_df in df_list:
        forward_df_list.append(pre_df.reset_index(drop=True))
    if len(forward_df_list) <= 0:
        logger.warning("msproftx.db has no forward info, please check.")
        return pd.DataFrame()

    # 初始化一个字典来存储每行,每个dp域forward最大during_time值
    all_max_forward_during_time = []
    for row_index in forward_df_list[0].index:
        max_forward_during_time = {}
        max_during_time = {}
        max_df_index = {}
        for df_index, df in enumerate(forward_df_list):
            current_dp_rank_id = df.loc[row_index, 'rid']
            if current_dp_rank_id is None:
                continue
            current_during_time = df.loc[row_index, 'during_time']
            if current_dp_rank_id not in max_during_time or current_during_time > max_during_time[current_dp_rank_id]:
                max_during_time[current_dp_rank_id] = current_during_time
                max_df_index[current_dp_rank_id] = df_index

        for key, value in max_df_index.items():
            select_row = forward_df_list[value].loc[row_index]
            dp_name = 'dp' + key + '-forward(ms)'
            max_forward_during_time[dp_name] = select_row.get('during_time') / US_PER_MS
        all_max_forward_during_time.append(max_forward_during_time)

    return pd.DataFrame(all_max_forward_during_time)


def get_certain_indices(row_name, fields_number_map, df):
    rec_indices = df[df['name'] == row_name].index
    rec_indices_length = len(rec_indices)
    fields_number_map[row_name] = rec_indices_length
    logger.debug(f"{row_name}_length:{rec_indices_length}, content:{rec_indices}")
    return rec_indices


def get_pairs_df_by_pid(name_a, name_b, fields_number_map, df):
    a_df_indices = []
    b_df_indices = []
    df_list = df.groupby('pid')
    for pid, df in df_list:
        a_df_indices = get_certain_indices(name_a, fields_number_map, df)
        b_df_indices = get_certain_indices(name_b, fields_number_map, df)
        if len(a_df_indices) != 0 and len(b_df_indices) != 0:
            logger.debug(f"Select dp-batch pid:{pid}")
            break
    return df.loc[a_df_indices].copy(), df.loc[b_df_indices].copy()


def check_dp_batch_info_length(fields_number_map):
    unique_length = set(fields_number_map.values())
    # 若各字段个数不一致，则打印warning信息
    if len(unique_length) > 1:
        logger.warning("The number of dp-batch info fields has different length.")
        for name, length in fields_number_map.items():
            logger.warning(f"{name}_length: {length}")


def extract_dp_info_each_row(row):
    rid_list = row.get('rid_list')
    dp_id_list = row.get('dp_list')
    if not is_contained_vaild_dp_batch_info(rid_list, dp_id_list):
        logger.warning('rid_list length is not equal to dp_id_list')
        return {}

    pre_dp_map = {}
    for i, value in enumerate(dp_id_list):
        value = str(value)
        dp_name = 'dp' + value
        if dp_name not in pre_dp_map:
            pre_dp_map[dp_name] = []
        pre_dp_map[dp_name].append(rid_list[i])

    result_columns = {}
    for key, value in pre_dp_map.items():
        rid_name = key + '-rid'
        size_name = key + '-size'
        result_columns[rid_name] = str(value)
        result_columns[size_name] = len(value)
    return result_columns


def get_dp_batch_info(dp_batch_df, dp_rank_id_df):
    if dp_batch_df.empty or dp_rank_id_df.empty:
        logger.warning("msproftx.db has no dpBatch info, please check.")
        return pd.DataFrame()

    # 确保dpBatch和dpRankId字段数量一致
    min_len = min(len(dp_batch_df), len(dp_rank_id_df))
    dp_batch_df = dp_batch_df.head(min_len)
    dp_rank_id_df = dp_rank_id_df.head(min_len)

    dp_df = pd.concat([dp_batch_df['rid_list'].reset_index(drop=True),
        dp_rank_id_df['rid_list'].reset_index(drop=True)], axis=1, keys=["rid_list", "dp_list"])

    # 根据rid_list和dp_list，逐行获取dp域信息，并更新新列
    new_cols_df = dp_df.apply(extract_dp_info_each_row, axis=1, result_type="expand")
    dp_df = pd.concat([dp_df, new_cols_df], axis=1)

    dp_df = dp_df.drop(['dp_list', 'rid_list'], axis=1)

    return dp_df


def write_to_ori_df(ori_df_indices, new_df, ori_df):
    if new_df.empty:
        return ori_df

    # 防止写入越界，取最小值
    min_row = min(len(ori_df_indices), len(new_df))

    # 创建new_df的临时副本，索引设置为ori_df_indices的前n个
    tmp_df = new_df.iloc[:min_row].copy()
    tmp_df.index = ori_df_indices[:min_row]

    # 如果已经存在改列，则直接更新
    ori_df.update(tmp_df)
    
    new_clos = tmp_df.columns.difference(ori_df.columns)
    if not new_clos.empty:
        ori_df = pd.concat([ori_df, tmp_df[new_clos]], axis=1)
    return ori_df


def get_new_columns_order(ori_columns, new_columns, dp_number):
    for i in range(dp_number):
        ori_columns.append('dp' + str(i) + '-rid')
        ori_columns.append('dp' + str(i) + '-size')
        ori_columns.append('dp' + str(i) + '-forward(ms)')

    # 创建过滤后的顺序列表
    existing_cols = [col for col in ori_columns if col in new_columns]
    remaining_cols = [col for col in new_columns if col not in ori_columns]
    new_columns_order = existing_cols + remaining_cols

    return new_columns_order


def exporter_dp_batch(batch_name, all_dp_batch_df):
    ori_columns = ['name', 'res_list', 'start_time', 'end_time', 'batch_size', \
        'batch_type', 'during_time', 'pid', 'rid_list', 'rid']
    all_dp_batch_df = all_dp_batch_df[ori_columns]

    # 获取原始数据中各打点字段个数，用于后续校验
    fields_number_map = {}

    # 获取每个dp域最长的forward执行时间
    forward_df = pd.DataFrame()
    try:
        forward_df = get_forward_info(all_dp_batch_df)
        fields_number_map['forward'] = len(forward_df)
        logger.debug(f"forward_info_length:{fields_number_map['forward']}, content:{forward_df.columns}")
    except Exception as e:
        logger.warning(f'get forward info failed: {e}')

    # 获取单个线程dp域batch及对应dpRanlIds的信息 (多个线程中的信息一致，只选取其中某一个线程)
    dp_batch_df, dp_rank_id_df = get_pairs_df_by_pid('dpBatch', \
        'dpRankIds', fields_number_map, all_dp_batch_df)
    dp_df = get_dp_batch_info(dp_batch_df, dp_rank_id_df)
    logger.debug(f"dp_info_length:{len(dp_df)}, content:{dp_df.columns}")

    # 获取组batch和modelExec行的index
    model_exec_indices = get_certain_indices('modelExec', fields_number_map, all_dp_batch_df)
    batch_indices = get_certain_indices(batch_name, fields_number_map, all_dp_batch_df)

    # 检查原始数据中各字段信息是否一致
    check_dp_batch_info_length(fields_number_map)

    # 写回组batch和modelExec行
    all_dp_batch_df = write_to_ori_df(model_exec_indices, dp_df, all_dp_batch_df)
    all_dp_batch_df = write_to_ori_df(batch_indices, dp_df, all_dp_batch_df)
    all_dp_batch_df = write_to_ori_df(model_exec_indices, forward_df, all_dp_batch_df)
    all_dp_batch_df = write_to_ori_df(batch_indices, forward_df, all_dp_batch_df)

    # 自定义列顺序
    new_columns_order = get_new_columns_order(ori_columns, all_dp_batch_df.columns, len(forward_df.columns))
    all_dp_batch_df = all_dp_batch_df[new_columns_order]

    return all_dp_batch_df


def filter_batch_df(batch_name, batch_df):
    batch_df = batch_df[batch_df['name'].isin(['modelExec', batch_name])]
    batch_df = batch_df.drop(['pid', 'rid_list', 'rid'], axis=1)
    batch_df['during_time'] = batch_df['during_time'] / US_PER_MS
    batch_df['start_time'] = batch_df['start_time'] / US_PER_MS
    batch_df['end_time'] = batch_df['end_time'] / US_PER_MS
    batch_df = batch_df.rename(columns={
        'start_time': 'start_time(ms)',
        'end_time': 'end_time(ms)',
        'during_time': 'during_time(ms)'
    })
    return batch_df


class ExporterBatchData(ExporterBase):
    name = "batch_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')
        if df is None:
            logger.warning("The data is empty, please check")
            return

        # 获取组batch字段名称，旧版本为BatchScheduler，新版本为batchFrameworkProcessing
        batch_name = 'BatchSchedule' if (df['name'] == 'BatchSchedule').any() else 'batchFrameworkProcessing'
        batch_df = df[df['name'].isin([batch_name, 'modelExec', 'dpBatch', 'forward', 'dpRankIds'])]
        if batch_df.empty:
            logger.warning("No batch data found. Please check msproftx.db.")
            return

        try:
            # 区分dp域显示，假如为动态启停采集的数据，从第一次组batch开始算起
            if batch_name in batch_df['name'].values:
                start_index = (batch_df['name'] == batch_name).idxmax()
                batch_df = batch_df.loc[start_index:]

            # 给组batch和modelExec列新增dp域信息
            batch_df = exporter_dp_batch(batch_name, batch_df)

            # 筛选显示
            batch_df = filter_batch_df(batch_name, batch_df)
        except KeyError as e:
            logger.warning(f"Field '{e.args[0]}' not found in msproftx.db.")

        output = cls.args.output_path
        save_dataframe_to_csv(batch_df, output, "batch.csv")

        for col in batch_df:
            if batch_df[col].dtype == 'object':
                batch_df[col] = batch_df[col].astype(str)
            if col == 'batch_size':
                batch_df[col] = batch_df[col].astype(float)
        add_table_into_visual_db(batch_df, 'batch')
        add_table_into_visual_db(data.get('batch_req_df'), 'batch_req')
        add_table_into_visual_db(data.get('batch_exec_df'), 'batch_exec')