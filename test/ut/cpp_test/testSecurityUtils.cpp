// Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include "msServiceProfiler/SecurityUtils.h"
#include <sys/stat.h>
#include <unistd.h>
#include <string>
#include <vector>
#include <cstdlib>
#include "stubs.h"

using namespace SecurityUtils;
using namespace testing;

class SecurityUtilsTest : public Test {
protected:
    void SetUp() override
    {
        // 创建临时文件和目录
        const char* tempFile = "testfile.txt";
        const char* tempDir = "testdir";
        const char* tempLink = "testlink";

        // 创建临时文件
        FILE* file = fopen(tempFile, "w");
        if (file) {
            fclose(file);
        }
        // 创建临时目录
        mkdir(tempDir, 0755);
        // 创建符号链接
        symlink(tempFile, tempLink);
    }

    void TearDown() override
    {
        // 清理临时文件和目录
        const char* tempFile = "testfile.txt";
        const char* tempDir = "testdir";
        const char* tempLink = "testlink";

        // 删除文件
        unlink(tempFile);
        // 删除目录
        rmdir(tempDir);
        // 删除符号链接
        unlink(tempLink);
    }
};

TEST_F(SecurityUtilsTest, TestIsExist)
{
    // 测试文件存在的情况
    const std::string existingFile = "testfile.txt";
    EXPECT_TRUE(IsExist(existingFile));

    // 测试文件不存在的情况
    const std::string nonExistingFile = "nonexistent.txt";
    EXPECT_FALSE(IsExist(nonExistingFile));
}

TEST_F(SecurityUtilsTest, TestIsReadable)
{
    // 测试可读文件
    const std::string readableFile = "testfile.txt";
    EXPECT_TRUE(IsReadable(readableFile));

    // 测试不可读文件（需要修改权限）
    const std::string unreadableFile = "testfile.txt";
    chmod(unreadableFile.c_str(), 0000);
    EXPECT_FALSE(IsReadable(unreadableFile));
    // 恢复权限
    chmod(unreadableFile.c_str(), 0644);
}

TEST_F(SecurityUtilsTest, TestIsWritable)
{
    // 测试可写文件
    const std::string writableFile = "testfile.txt";
    EXPECT_TRUE(IsWritable(writableFile));

    // 测试不可写文件（需要修改权限）
    const std::string unwritableFile = "testfile.txt";
    chmod(unwritableFile.c_str(), 0444);
    EXPECT_FALSE(IsWritable(unwritableFile));
    // 恢复权限
    chmod(unwritableFile.c_str(), 0644);
}

TEST_F(SecurityUtilsTest, TestIsExecutable)
{
    // 测试可执行文件（假设testfile.txt不可执行）
    const std::string nonExecutableFile = "testfile.txt";
    EXPECT_FALSE(IsExecutable(nonExecutableFile));

    // 测试可执行文件（需要一个可执行文件）
    const std::string executableFile = "test.sh";
    FILE* file = fopen(executableFile.c_str(), "w");
    if (file) {
        fclose(file);
        chmod(executableFile.c_str(), 0755);
        EXPECT_TRUE(IsExecutable(executableFile));
        // 清理
        unlink(executableFile.c_str());
    }
}

TEST_F(SecurityUtilsTest, TestIsSoftLink)
{
    // 测试符号链接
    const std::string softLink = "testlink";
    EXPECT_TRUE(IsSoftLink(softLink));

    // 测试非符号链接
    const std::string nonSoftLink = "testfile.txt";
    EXPECT_FALSE(IsSoftLink(nonSoftLink));
}

TEST_F(SecurityUtilsTest, TestIsFile)
{
    // 测试普通文件
    const std::string regularFile = "testfile.txt";
    EXPECT_TRUE(IsFile(regularFile));

    // 测试目录
    const std::string directory = "testdir";
    EXPECT_FALSE(IsFile(directory));
}

TEST_F(SecurityUtilsTest, TestIsDir)
{
    // 测试目录
    const std::string directory = "testdir";
    EXPECT_TRUE(IsDir(directory));

    // 测试普通文件
    const std::string regularFile = "testfile.txt";
    EXPECT_FALSE(IsDir(regularFile));
}

TEST_F(SecurityUtilsTest, TestIsPathLenLegal)
{
    // 测试路径长度合法
    const std::string shortPath = "testfile.txt";
    EXPECT_TRUE(IsPathLenLegal(shortPath));

    // 测试路径长度超过限制
    std::string longPath(PATH_MAX, 'a');
    EXPECT_FALSE(IsPathLenLegal(longPath));
}

TEST_F(SecurityUtilsTest, TestIsPathDepthLegal)
{
    // 测试路径深度合法
    const std::string shallowPath = "testdir/testfile.txt";
    EXPECT_TRUE(IsPathDepthLegal(shallowPath));

    // 测试路径深度超过限制
    std::string deepPath;
    for (int i = 0; i < PATH_DEPTH_MAX + 1; ++i) {
        deepPath += "/testdir";
    }
    EXPECT_FALSE(IsPathDepthLegal(deepPath));
}

TEST_F(SecurityUtilsTest, TestIsFileSizeLegal)
{
    // 测试文件大小合法
    const std::string smallFile = "testfile.txt";
    const long long maxSize = 1024; // 1KB
    EXPECT_TRUE(IsFileSizeLegal(smallFile, maxSize));

    // 测试文件大小超过限制
    const std::string largeFile = "testfile.txt";
    // 创建一个大文件（假设大小超过maxSize）
    FILE* file = fopen(largeFile.c_str(), "w");
    if (file) {
        // 写入大量数据
        const char* data = "0123456789";
        for (int i = 0; i < 1000; ++i) {
            fwrite(data, sizeof(char), strlen(data), file);
        }
        fclose(file);
        EXPECT_FALSE(IsFileSizeLegal(largeFile, maxSize));
        // 清理
        unlink(largeFile.c_str());
    }
}

TEST_F(SecurityUtilsTest, TestIsPathCharactersValid)
{
    // 测试有效路径
    const std::string validPath = "testfile.txt";
    EXPECT_TRUE(IsPathCharactersValid(validPath));

    // 测试无效路径（包含非法字符）
    const std::string invalidPath = "test?file.txt";
    EXPECT_FALSE(IsPathCharactersValid(invalidPath));
}

TEST_F(SecurityUtilsTest, TestCheckPathContainSoftLink)
{
    // 测试包含符号链接的路径
    const std::string pathWithLink = "testlink";
    EXPECT_TRUE(CheckPathContainSoftLink(pathWithLink));

    // 测试不包含符号链接的路径
    const std::string pathWithoutLink = "testfile.txt";
    EXPECT_FALSE(CheckPathContainSoftLink(pathWithoutLink));
}

TEST_F(SecurityUtilsTest, TestCheckFileBeforeWrite)
{
    // 测试文件写入检查
    const std::string validFile = "testfile.txt";
    EXPECT_TRUE(CheckFileBeforeWrite(validFile));

    // 测试符号链接
    const std::string link = "testlink";
    EXPECT_FALSE(CheckFileBeforeWrite(link));
}

TEST_F(SecurityUtilsTest, TestCheckFileBeforeRead)
{
    // 测试文件读取检查
    const std::string validFile = "testfile.txt";
    const long long maxSize = 1024;
    EXPECT_FALSE(CheckFileBeforeRead(validFile, maxSize));

    // 测试符号链接
    const std::string link = "testlink";
    EXPECT_FALSE(CheckFileBeforeRead(link, maxSize));
}
