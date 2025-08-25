from pytest_check import check


def check_df_expected_column(df, expected_columns):
    # 检查是否有缺失的列
    missing_columns = set(expected_columns) - set(df.columns.tolist())
    assert len(missing_columns) == 0, f"missing columns: {missing_columns}"


def check_df_has_no_empty_line(df):
    # 没有空行
    empty_rows = df.eq("").all(axis=1)
    num_empty_rows = empty_rows.sum()
    assert num_empty_rows == 0, f"has empty lines."


def check_df_col_has_no_nan_value(df, col_name):
    # 检查某列没有Nan值
    check.is_false(df[col_name].isna().any(), f"column {col_name} has nan value.")


def check_df_col_has_value(df, col_name, value, times=None, empty_enable=False):
    # 检查某列某个值出现的次数
    check.is_true(col_name in df, f"check {col_name} in dataframe failed.")
    value_count_series = df[col_name].value_counts()
    if empty_enable and value not in value_count_series: 
        return
    check.is_true(value in value_count_series, f"check {col_name} has {value} failed(not in).")
    count = value_count_series[value] if value in value_count_series else 0
    check.is_true(count > 0 if times is None else count == times, f"check {col_name} has {value} failed({times}).")


def check_df_col_type(df, col_name, checker):
    # 检查某列的类型
    return df[col_name].apply(checker).all()
