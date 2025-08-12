from pytest_check import check

import os
import subprocess


def grep_in_directory(directory, pattern):
    """
    在指定目录下的所有文件中搜索指定的文本模式。

    :param directory: 要搜索的目录路径
    :param pattern: 要搜索的文本模式
    :return: 如果找到匹配的文件，返回 True；否则返回 False
    """
    try:
        # 使用 grep -r 命令递归搜索目录中的所有文件
        command = ['grep', '-r', pattern, directory]
        
        # 使用 subprocess.run() 执行命令
        result = subprocess.run(command)
        
        # 检查输出，如果有匹配的文件，返回 True
        return result.returncode == 0
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False
    
    
    
def mindie_key_word_checker(dump_path):
    key_names = ["from"]
    key_domains = []
    
    for key_name in key_names:
        check.is_true(grep_in_directory(dump_path, f"\\^{key_name}\\^"), f"not found {key_name} in {dump_path}")
        
    for key_domain in key_domains:
        check.is_true(grep_in_directory(dump_path,f"\\^{key_domain}\\^"), f"not found {key_domain} in {dump_path}")
