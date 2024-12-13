import unittest
import coverage
import logging


def run_tests_with_coverage(test_directory):
    cov = coverage.Coverage(omit=["testcase/*"])

    cov.start()

    loader = unittest.TestLoader()
    suite = loader.discover(test_directory)

    runner = unittest.TextTestRunner()
    runner.run(suite)

    cov.stop()

    cov.save()

    total_statements = cov.html_report(directory="coverage_report")

    print(f"Coverage rate: {total_statements:.2f}%")


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)

    test_directory = "./testcase"

    run_tests_with_coverage(test_directory)
