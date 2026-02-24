# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
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

from typing import List, Optional, Dict, Any

import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import get_filter_span_df
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.constant import US_PER_MS

TOP_N_REQUESTS = 5
HORIZONTAL_TABLE_WIDTH = 135
FIRST_COLUMN_WIDTH = 30
DEFAULT_STATISTIC_SPAN = ['forward', 'BatchSchedule', 'batchFrameworkProcessing']
REQUEST_STATISTIC_SPANS = ['forward', 'BatchSchedule', 'batchFrameworkProcessing']
REQUIRED_COLUMNS = ["name", "start_time", "end_time", "during_time", "rid", "pid"]
TIME_COLUMNS = ["start_time", "end_time", "during_time"]
BUBBLE_SPAN_NAME = ['forward']


class ExporterStatistic(ExporterBase):
    name = "statistic"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.debug)
    def export(cls, data) -> None:
        df = data.get("tx_data_df")
        if df is None:
            logger.warning("There is no service prof data, statistic data will not be generated. please check.")
            return

        span_df = cls._prepare_span_data(df)
        if span_df.empty:
            logger.warning("There is no span data, statistic will not be generated. please check.")
            return
        try:
            cls._print_span_statistics(span_df)
            top_forward_bubble_stats = cls._calculate_top_forward_bubble_stats(span_df)
            if top_forward_bubble_stats:
                cls._print_request_statistics(span_df, top_forward_bubble_stats)
                cls._print_bubble_statistics(df, top_forward_bubble_stats)
        except Exception as e:
            logger.warning(f"export statistic failed, error: {e}", exc_info=True)

    @classmethod
    def _format_rid_column(cls, rid_series: pd.Series) -> pd.Series:
        """格式化rid列"""
        def process_rid(x):
            if isinstance(x, list):
                return x
            elif pd.isna(x) or x == '':
                return []
            elif isinstance(x, str):
                if ',' in x:
                    return [rid.strip() for rid in x.split(',') if rid.strip()]
                else:
                    return [x.strip()]
            else:
                return [x]

        return rid_series.apply(process_rid)

    @classmethod
    def _prepare_and_expand_rids(cls, df: pd.DataFrame, span_names: List[str]) -> Optional[pd.DataFrame]:
        """准备并展开rid数据"""
        result_df = get_filter_span_df(df, REQUIRED_COLUMNS, TIME_COLUMNS)
        result_df = result_df[result_df['name'].isin(span_names)]

        if result_df.empty:
            return None

        if 'start_time' not in result_df.columns or 'end_time' not in result_df.columns:
            logger.warning(f"Data does not have start_time or end_time columns.")
            return None

        result_df['rid'] = cls._format_rid_column(result_df['rid'])
        result_df = result_df.explode('rid').reset_index(drop=True)
        result_df = result_df[result_df['rid'].notna() & (result_df['rid'] != '')]
        return result_df

    @classmethod
    def _prepare_span_data(cls, df: pd.DataFrame) -> pd.DataFrame:
        """准备span数据"""
        span_df = get_filter_span_df(df, REQUIRED_COLUMNS, TIME_COLUMNS)
        span_names = cls._get_span_names()
        return span_df[span_df['name'].isin(span_names)]

    @classmethod
    def _get_span_names(cls) -> List[str]:
        """获取需要统计的span名称列表"""
        span_names = DEFAULT_STATISTIC_SPAN
        if hasattr(cls, 'args') and cls.args.span:
            span_names = list(set(span_names + cls.args.span))
        return span_names

    @classmethod
    def _prepare_forward_data(cls, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """准备forward数据用于空泡统计"""
        forward_df = cls._prepare_and_expand_rids(df, BUBBLE_SPAN_NAME)
        if forward_df is None:
            logger.warning(f"There is no {BUBBLE_SPAN_NAME} data, bubble statistics will not be generated.")
            return None
        return forward_df.sort_values(['pid', 'rid', 'start_time']).reset_index(drop=True)

    @classmethod
    def _calculate_top_forward_bubble_stats(cls, span_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """计算forward+空泡时间最长的5个请求"""
        forward_df = cls._prepare_and_expand_rids(span_df, BUBBLE_SPAN_NAME)
        if forward_df is None:
            return []
        return cls._calculate_forward_bubble_stats(forward_df)

    @classmethod
    def _calculate_forward_bubble_stats(cls, forward_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """计算每个请求的forward+空泡时间统计"""
        if forward_df is None or forward_df.empty:
            return []

        pid_rid_stats = []
        for (pid, rid), group in forward_df.groupby(['pid', 'rid']):
            group_sorted = group.sort_values('start_time').reset_index(drop=True)
            if len(group_sorted) >= 2:
                first_forward_end = group_sorted.iloc[0]['end_time']
                last_forward_end = group_sorted.iloc[-1]['end_time']
                forward_count = len(group_sorted)
                total_time = last_forward_end - first_forward_end
                avg_time = total_time / (forward_count - 1)
                pid_rid_stats.append({'rid': rid, 'pid': pid, 'avg_time': avg_time, 'total_time': total_time,
                                  'count': forward_count - 1})

        rid_merged_stats = {}
        for stat in pid_rid_stats:
            rid = stat['rid']
            if rid not in rid_merged_stats:
                rid_merged_stats[rid] = {
                    'rid': rid,
                    'total_avg_time': 0,
                    'total_total_time': 0,
                    'total_count': 0,
                    'pid_stats': []
                }
            rid_merged_stats[rid]['total_avg_time'] += stat['avg_time'] * stat['count']
            rid_merged_stats[rid]['total_total_time'] += stat['total_time']
            rid_merged_stats[rid]['total_count'] += stat['count']
            rid_merged_stats[rid]['pid_stats'].append(stat)

        final_stats = []
        for rid, data in rid_merged_stats.items():
            if data['total_count'] > 0:
                final_avg_time = data['total_avg_time'] / data['total_count']
                final_stats.append({
                    'rid': rid,
                    'avg_time': final_avg_time,
                    'total_time': data['total_total_time'],
                    'count': data['total_count'],
                    'pid_stats': data['pid_stats']
                })

        final_stats_sorted = sorted(final_stats, key=lambda x: x['avg_time'], reverse=True)
        return final_stats_sorted[:TOP_N_REQUESTS]

    @classmethod
    def _calculate_bubble_times(cls, forward_df: pd.DataFrame) -> Dict[str, Any]:
        """计算空泡时间（两个forward之间的时间间隔）"""
        all_bubble_times = []
        rid_bubble_times = {}

        if forward_df is None or forward_df.empty:
            return {'all_times': all_bubble_times, 'rid_times': rid_bubble_times}

        for (pid, rid), group in forward_df.groupby(['pid', 'rid']):
            group_sorted = group.sort_values('start_time').reset_index(drop=True)
            if len(group_sorted) >= 2:
                for i in range(1, len(group_sorted)):
                    pre_span = group_sorted.iloc[i - 1]
                    cur_span = group_sorted.iloc[i]
                    bubble_time = cur_span['start_time'] - pre_span['end_time']

                    if bubble_time > 0:
                        all_bubble_times.append(bubble_time)
                        if rid not in rid_bubble_times:
                            rid_bubble_times[rid] = []
                        rid_bubble_times[rid].append(bubble_time)

        return {'all_times': all_bubble_times, 'rid_times': rid_bubble_times}

    @classmethod
    def _print_span_statistics(cls, span_df: pd.DataFrame) -> None:
        """打印span级别统计信息"""
        span_list = []
        for span_name, group_df in span_df.groupby('name'):
            stats = calculate_stats(group_df['during_time'])
            span_list.append({'name': span_name, 'stats': stats})

        if not span_list:
            logger.info("No valid data for span statistics, skip printing.")
            return

        print("\n=== Span Statistics ===")
        cls.print_statistics(span_list, print_header_label='Category of span')

    @classmethod
    def _print_request_statistics(cls, span_df: pd.DataFrame, top_forward_bubble_stats: List[Dict[str, Any]]) -> None:
        """打印请求级别统计信息"""
        data_list = []
        expanded_span_df = cls._prepare_and_expand_rids(span_df.copy(), REQUEST_STATISTIC_SPANS)
        if expanded_span_df is None:
            logger.info("No valid data for request statistics, skip printing.")
            return

        for span_name in REQUEST_STATISTIC_SPANS:
            group_df = expanded_span_df[expanded_span_df['name'] == span_name]
            if group_df.empty:
                continue

            rid_group_df = group_df.dropna(subset=['rid'])
            if rid_group_df.empty:
                continue

            rid_stats = cls._calculate_rid_stats(rid_group_df)
            span_data_list = cls._build_request_stats_data(rid_group_df, rid_stats, top_forward_bubble_stats)
            data_list.append({'name': span_name, 'data_list': span_data_list})

        if not data_list:
            logger.info("No valid data for request statistics, skip printing.")
            return

        print("\n=== Request Statistics ===")
        for item in data_list:
            cls.print_statistics(item['data_list'], print_header_label=f'Span:{item["name"]}')

    @classmethod
    def _calculate_rid_stats(cls, rid_group_df: pd.DataFrame) -> pd.DataFrame:
        """计算每个rid的统计信息"""
        rid_stats = rid_group_df.groupby('rid')['during_time'].agg([
            'mean', 'min', 'max', 'sum',
            lambda x: x.quantile(0.5),
            lambda x: x.quantile(0.9),
            lambda x: x.quantile(0.99)
        ]).reset_index()
        rid_stats.columns = ['rid', 'avg_duration', 'min_duration', 'max_duration',
                             'total_duration', 'p50_duration', 'p90_duration', 'p99_duration']
        return rid_stats

    @classmethod
    def _build_request_stats_data(cls, rid_group_df: pd.DataFrame, rid_stats: pd.DataFrame,
                                  top_forward_bubble_stats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建请求统计数据列表"""
        data_list = []
        all_stats = cls._calculate_all_stats(rid_group_df)
        data_list.append(all_stats)

        if top_forward_bubble_stats:
            top_rid_stats = cls._get_top_rid_stats_from_forward_bubble(rid_stats, top_forward_bubble_stats)
            data_list.extend(top_rid_stats)
        return data_list

    @classmethod
    def _calculate_all_stats(cls, rid_group_df: pd.DataFrame) -> Dict[str, Any]:
        """计算所有请求的统计信息"""
        during_times = rid_group_df['during_time']
        return {
            'name': 'ALL',
            'stats': {
                'min': during_times.min(),
                'max': during_times.max(),
                'avg': during_times.mean(),
                'P50': during_times.quantile(0.5),
                'P90': during_times.quantile(0.9),
                'P99': during_times.quantile(0.99),
                'total': during_times.sum()
            }
        }

    @classmethod
    def _get_top_rid_stats_from_forward_bubble(cls, rid_stats: pd.DataFrame,
                                               top_forward_bubble_stats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从forward+空泡统计中获取Top 5请求的统计信息"""
        result = []
        for stat in top_forward_bubble_stats:
            rid = stat['rid']
            rid_row = rid_stats[rid_stats['rid'] == rid]
            if not rid_row.empty:
                row = rid_row.iloc[0]
                rid_stats_item = {
                    'name': rid,
                    'stats': {
                        'min': row['min_duration'],
                        'max': row['max_duration'],
                        'avg': row['avg_duration'],
                        'P50': row['p50_duration'],
                        'P90': row['p90_duration'],
                        'P99': row['p99_duration'],
                        'total': row['total_duration']
                    }
                }
                result.append(rid_stats_item)
        return result

    @classmethod
    def _print_bubble_statistics(cls, df: pd.DataFrame, top_forward_bubble_stats: List[Dict[str, Any]]) -> None:
        """打印空泡时间统计"""
        forward_df = cls._prepare_forward_data(df)
        if forward_df is None:
            return

        bubble_data = cls._calculate_bubble_times(forward_df)
        if not bubble_data['all_times']:
            logger.warning("No bubble time data found, skip bubble statistics.")
            return

        data_list = cls._build_bubble_stats_data(bubble_data, top_forward_bubble_stats)

        print(f"\n=== Bubble Statistics ===")
        cls.print_statistics(data_list)

    @classmethod
    def _build_bubble_stats_data(cls, bubble_data: Dict[str, Any], top_forward_bubble_stats: List[Dict[str, Any]]) -> \
        List[Dict[str, Any]]:
        """构建空泡统计数据列表"""
        data_list = []
        all_stats = {
            'name': 'ALL',
            'stats': calculate_stats(pd.Series(bubble_data['all_times']))
        }
        data_list.append(all_stats)

        for stat in top_forward_bubble_stats:
            rid = stat['rid']
            if rid in bubble_data['rid_times']:
                stats = calculate_stats(pd.Series(bubble_data['rid_times'][rid]))
                data_list.append({'name': rid, 'stats': stats})

        return data_list



    @classmethod
    def print_statistics(cls, data_source_list: List[Dict[str, Any]], print_header_label: Optional[str] = '') -> None:
        """打印统计表格"""
        border = '-' * HORIZONTAL_TABLE_WIDTH
        unit = "μs" if cls.args.span is not None else "ms"

        print(border)
        print(
            f"| {print_header_label:<{FIRST_COLUMN_WIDTH}} "
            f"| {'min(' + unit + ')':>10} | {'avg(' + unit + ')':>10} | {'P50(' + unit + ')':>10} "
            f"| {'P90(' + unit + ')':>10} | {'P99(' + unit + ')':>10} | {'max(' + unit + ')':>10} "
            f"| {'total(' + unit + ')':>20} |"
        )
        print(border)

        # --span模式，数据单位为微秒
        need_convert = cls.args.span is not None
        for data_source in data_source_list:
            name = data_source.get('name', 'Unknown')
            stats = data_source.get('stats', {})
            divisor = US_PER_MS if need_convert else 1
            print(

                f"| {name:<{FIRST_COLUMN_WIDTH}} "
                f"| {stats.get('min', 0) / divisor:>10.2f} | {stats.get('avg', 0) / divisor:>10.2f} | {stats.get('P50', 0) / divisor:>10.2f} "
                f"| {stats.get('P90', 0) / divisor:>10.2f} | {stats.get('P99', 0) / divisor:>10.2f} | {stats.get('max', 0) / divisor:>10.2f} "
                f"| {stats.get('total', 0) / divisor:>20.2f} |"
            )
        print(border)


def calculate_stats(series: pd.Series) -> Dict[str, float]:
    """计算统计指标"""
    series = series.dropna()
    if series.empty:
        return {
            'min': 0.0, 'max': 0.0, 'avg': 0.0,
            'P50': 0.0, 'P90': 0.0, 'P99': 0.0, 'total': 0.0
        }
    return {
        'min': series.min(),
        'max': series.max(),
        'avg': series.mean(),
        'P50': series.quantile(0.5),
        'P90': series.quantile(0.9),
        'P99': series.quantile(0.99),
        'total': series.sum()
    }


