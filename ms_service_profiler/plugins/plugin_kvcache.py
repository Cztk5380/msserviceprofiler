# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import pandas as pd
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger


class PluginKVCacheMetrics(PluginBase):
    name = "plugin_kvcache_metrics"
    depends = ["plugin_timestamp"]

    # 常量定义
    PERCENTAGE_THRESHOLD = 1.0
    PERCENTAGE_CONVERSION_FACTOR = 100.0

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        """
        处理KVCache数据并计算指标，直接添加到原始DataFrame中
        """
        tx_data_df = data.get('tx_data_df')
        if tx_data_df is None:
            logger.warning("No transaction data found for KVCache metrics calculation")
            return data

        # 筛选KVCache相关事件
        kvcache_domains = ['KVCache', 'Schedule.KVCache']
        kvcache_mask = tx_data_df['domain'].isin(kvcache_domains)

        if not kvcache_mask.any():
            logger.debug("No KVCache related events found")
            return data

        try:
            # 确保所有需要的列都存在，如果不存在则创建
            cls._ensure_required_columns_exist(tx_data_df)

            # 只对KVCache事件计算指标
            kvcache_indices = tx_data_df[kvcache_mask].index
            cls._calculate_and_update_metrics(tx_data_df, kvcache_indices)

            logger.debug(f"KVCache metrics calculated for {len(kvcache_indices)} rows")
            logger.debug(f"Available columns after plugin: {tx_data_df.columns.tolist()}")

        except Exception as e:
            logger.error(f"Error calculating KVCache metrics: {e}")
        return data

    @classmethod
    def _ensure_required_columns_exist(cls, tx_data_df):
        """确保所需列存在"""
        required_columns = ['total_blocks', 'used_blocks', 'free_blocks',
                            'blocks_allocated', 'blocks_freed', 'kvcache_usage_rate']

        for col in required_columns:
            if col not in tx_data_df.columns:
                if col == 'kvcache_usage_rate':
                    tx_data_df[col] = 0.0  # float类型
                else:
                    tx_data_df[col] = 0  # int类型

    @classmethod
    def _calculate_and_update_metrics(cls, tx_data_df, kvcache_indices):
        if len(kvcache_indices) == 0:
            return

        # 使用向量化操作替代逐行处理
        kvcache_data = tx_data_df.loc[kvcache_indices]

        # 向量化计算所有指标
        metrics_df = cls._calculate_metrics_vectorized(kvcache_data)

        # 批量更新原DataFrame
        for col in metrics_df.columns:
            tx_data_df.loc[kvcache_indices, col] = metrics_df[col]

    @classmethod
    def _calculate_metrics_vectorized(cls, kvcache_data):
        """向量化计算所有KVCache指标"""
        # 初始化结果DataFrame，使用与输入相同的索引
        metrics_df = pd.DataFrame(index=kvcache_data.index)
        metrics_df['total_blocks'] = 0
        metrics_df['used_blocks'] = 0
        metrics_df['free_blocks'] = 0
        metrics_df['blocks_allocated'] = 0
        metrics_df['blocks_freed'] = 0
        metrics_df['kvcache_usage_rate'] = 0.0

        # 向量化计算总块数
        cls._calculate_total_blocks_vectorized(kvcache_data, metrics_df)

        # 向量化计算已使用和空闲块数
        cls._calculate_used_and_free_blocks_vectorized(kvcache_data, metrics_df)

        # 向量化计算块数变化
        cls._calculate_block_changes_vectorized(kvcache_data, metrics_df)

        # 向量化计算使用率
        cls._calculate_usage_rate_vectorized(kvcache_data, metrics_df)

        return metrics_df

    @classmethod
    def _calculate_total_blocks_vectorized(cls, kvcache_data, metrics_df):
        """向量化计算总块数"""
        if 'TotalBlocks=' in kvcache_data.columns:
            total_blocks_series = kvcache_data['TotalBlocks=']
            # 使用pd.to_numeric进行安全转换，并填充NaN为0
            converted_values = pd.to_numeric(total_blocks_series, errors='coerce').fillna(0).astype(int)
            metrics_df['total_blocks'] = converted_values

    @classmethod
    def _calculate_used_and_free_blocks_vectorized(cls, kvcache_data, metrics_df):
        """向量化计算已使用和空闲块数"""
        # 处理 FreeBlocksAfter= 字段 (优先级更高)
        if 'FreeBlocksAfter=' in kvcache_data.columns:
            free_after_series = kvcache_data['FreeBlocksAfter=']
            # 使用pd.to_numeric进行安全转换
            converted_values = pd.to_numeric(free_after_series, errors='coerce')
            # 只有当值有效时才更新
            valid_mask = converted_values.notna()
            if valid_mask.any():
                converted_values_int = converted_values.astype(int)
                metrics_df.loc[valid_mask, 'free_blocks'] = converted_values_int[valid_mask]
                # 计算 used_blocks
                metrics_df.loc[valid_mask, 'used_blocks'] = (
                    metrics_df.loc[valid_mask, 'total_blocks'] - converted_values_int[valid_mask]
                )

        # 处理 FreeBlocks= 字段（作为备选，且只在 FreeBlocksAfter= 无效时使用）
        if 'FreeBlocks=' in kvcache_data.columns:
            free_blocks_series = kvcache_data['FreeBlocks=']
            # 使用pd.to_numeric进行安全转换
            converted_values = pd.to_numeric(free_blocks_series, errors='coerce')
            # 只有当 free_blocks 当前为 0 (即 FreeBlocksAfter= 未设置) 且 FreeBlocks= 有效时才更新
            free_blocks_is_zero = (metrics_df['free_blocks'] == 0)
            free_blocks_valid = converted_values.notna()
            mask = free_blocks_is_zero & free_blocks_valid
            if mask.any():
                converted_values_int = converted_values.astype(int)
                metrics_df.loc[mask, 'free_blocks'] = converted_values_int[mask]
                # 计算 used_blocks
                metrics_df.loc[mask, 'used_blocks'] = (
                    metrics_df.loc[mask, 'total_blocks'] - converted_values_int[mask]
                )


    @classmethod
    def _calculate_block_changes_vectorized(cls, kvcache_data, metrics_df):
        """向量化计算块数变化"""
        # 检查 FreeBlocksBefore= 和 FreeBlocksAfter= 是否都存在
        if 'FreeBlocksBefore=' in kvcache_data.columns and 'FreeBlocksAfter=' in kvcache_data.columns:
            free_before_series = kvcache_data['FreeBlocksBefore=']
            free_after_series = kvcache_data['FreeBlocksAfter=']

            # 使用pd.to_numeric进行安全转换
            free_before_converted = pd.to_numeric(free_before_series, errors='coerce')
            free_after_converted = pd.to_numeric(free_after_series, errors='coerce')

            # 检查转换后的有效性
            valid_mask = (free_before_converted.notna() & free_after_converted.notna())
            if valid_mask.any():
                free_before_int = free_before_converted.astype(int)
                free_after_int = free_after_converted.astype(int)

                net_block_change = free_before_int - free_after_int
                # 使用 clip 确保非负值
                metrics_df.loc[valid_mask, 'blocks_allocated'] = net_block_change[valid_mask].clip(lower=0)
                metrics_df.loc[valid_mask, 'blocks_freed'] = (-net_block_change[valid_mask]).clip(lower=0)

    @classmethod
    def _calculate_usage_rate_vectorized(cls, kvcache_data, metrics_df):
        """向量化计算使用率"""
        # 处理 UsagePercent= 字段
        if 'UsagePercent=' in kvcache_data.columns:
            usage_percent_series = kvcache_data['UsagePercent=']
            # 使用pd.to_numeric进行安全转换
            usage_value_converted = pd.to_numeric(usage_percent_series, errors='coerce')
            usage_value_valid = usage_value_converted.notna()

            # 根据阈值判断是否需要转换
            convert_mask = usage_value_converted > cls.PERCENTAGE_THRESHOLD
            # 仅对有效且需要转换的值进行操作
            mask_to_convert = usage_value_valid & convert_mask
            if mask_to_convert.any():
                metrics_df.loc[mask_to_convert, 'kvcache_usage_rate'] = (
                    usage_value_converted[mask_to_convert] / cls.PERCENTAGE_CONVERSION_FACTOR
                )
            # 仅对有效且不需要转换的值进行操作
            mask_no_convert = usage_value_valid & ~convert_mask
            if mask_no_convert.any():
                metrics_df.loc[mask_no_convert, 'kvcache_usage_rate'] = usage_value_converted[mask_no_convert]

        # 处理没有 UsagePercent= 的情况，直接计算使用率
        # 找出 UsagePercent= 无效的行
        if 'UsagePercent=' in kvcache_data.columns:
            no_usage_mask = kvcache_data['UsagePercent='].isna() | kvcache_data['UsagePercent='].isnull()
        else:
            no_usage_mask = pd.Series(True, index=kvcache_data.index) # 如果列不存在，则全部为 True

        if no_usage_mask.any():
            # 避免除零错误
            total_blocks = metrics_df.loc[no_usage_mask, 'total_blocks']
            used_blocks = metrics_df.loc[no_usage_mask, 'used_blocks']

            total_blocks_safe = total_blocks.where(total_blocks > 0, 1)
            calculated_rate = used_blocks / total_blocks_safe
            # 更新这些行的使用率
            metrics_df.loc[no_usage_mask, 'kvcache_usage_rate'] = calculated_rate