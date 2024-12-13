import unittest
import coverage
import logging


def run_tests_with_coverage(test_directory):
    # 初始化coverage对象
    cov = coverage.Coverage(omit=["testcase/*"])

    # 开始收集覆盖率数据
    cov.start()

    # 查找并加载测试用例
    loader = unittest.TestLoader()
    suite = loader.discover(test_directory)

    # 运行测试用例
    runner = unittest.TextTestRunner()
    runner.run(suite)

    # 停止收集覆盖率数据
    cov.stop()

    # 生成覆盖率报告
    cov.save()

    # 获取覆盖率
    total_statements = cov.html_report(directory="coverage_report")

    # 输出覆盖率
    print(f"行覆盖率: {total_statements:.2f}%")


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)
    # sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
    # print(sys.path[-1])

    # 指定测试用例所在的目录
    test_directory = "./testcase"  # 替换为你的测试用例目录

    # 运行测试并输出覆盖率
    run_tests_with_coverage(test_directory)
