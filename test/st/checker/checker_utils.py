import os
from pathlib import Path
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


def check_df_col_unique_value_nums(df, col_name, number):
    # 检查某列 unique 值是否是 number 个
    return df[col_name].nunique() == number


def has_prof_folder(root_folder):
    # 检查文件夹下是否存在PROF_开头的子文件夹
    root_path = Path(root_folder)
    for p in root_path.rglob("*"):
        if p.is_dir() and p.name.startswith("PROF_"):
            return True
    return False


def count_files_with_single_extension(folder_path, target_extension):
    """
    统计指定文件夹内具有指定后缀名的文件数量，并确保文件夹内只有一种后缀名。

    参数:
        folder_path (str): 要搜索的文件夹路径。
        target_extension (str): 要统计的文件后缀名，例如 ".csv"。

    返回:
        int: 指定后缀名的文件数量。
    """
    if not os.path.isdir(folder_path):
        raise NotADirectoryError(f"路径 '{folder_path}' 不是有效的文件夹。")

    if not target_extension.startswith('.'):
        target_extension = '.' + target_extension

    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

    if not files:
        return 0  # 文件夹为空

    # 获取所有文件的后缀名并去重
    seen_extensions = {os.path.splitext(f)[1] for f in files}

    if len(seen_extensions) != 1:
        raise ValueError(f"文件夹 '{folder_path}' 内包含多个后缀名，不满足只有一种后缀名的条件。")

    if target_extension not in seen_extensions:
        return 0  # 指定后缀名与文件夹内的后缀名不一致

    return len(files)
