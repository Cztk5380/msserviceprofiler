/*
* Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include <gtest/gtest.h>
#include <string>
#include <dlfcn.h>
#include <unistd.h>

// 包含你项目中的头文件
#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"

// 定义一个全局变量，用于控制 gethostname 返回值
int mock_gethostname_return_value = 0;

// 保存真正的 gethostname 函数指针
static int (*real_gethostname)(char*, size_t) = nullptr;

extern "C" {

// 替换的 gethostname 函数
int gethostname(char* name, size_t len)
{
    if (!real_gethostname) {
        real_gethostname = (int (*)(char*, size_t)) dlsym(RTLD_NEXT, "gethostname");
    }

    if (mock_gethostname_return_value != 0) {
        return mock_gethostname_return_value; // 模拟失败
    }

    return real_gethostname(name, len); // 正常调用
}

// 设置 mock 返回值的 API
void SetMockGetHostNameReturnValue(int value)
{
    mock_gethostname_return_value = value;
}

} // extern "C"

TEST(GetHostNameTest, GetHostName_Failure_ReturnsEmptyString)
{
    // 设置 gethostname 返回 -1（模拟失败）
    SetMockGetHostNameReturnValue(-1);

    // 调用被测函数（使用命名空间）
    std::string result = msServiceProfiler::GetHostName();

    // 验证返回值为空字符串
    EXPECT_TRUE(result.empty());
}

TEST(GetHostNameTest, GetHostName_Success_ReturnsValidHostname)
{
    // 设置 gethostname 返回 0（模拟成功）
    SetMockGetHostNameReturnValue(0);

    // 调用被测函数（使用命名空间）
    std::string result = msServiceProfiler::GetHostName();

    // 验证返回值不为空字符串
    EXPECT_FALSE(result.empty());
}

class ServiceProfilerWriterManagerTest : public ::testing::Test {
protected:
    void SetUp() override {
        // 初始化测试环境
        manager_ = std::make_unique<msServiceProfiler::ServiceProfilerWriterManager>();
    }

    void TearDown() override {
        // 清理测试环境
        manager_.reset();
    }

    std::unique_ptr<msServiceProfiler::ServiceProfilerWriterManager> manager_;
};

TEST_F(ServiceProfilerWriterManagerTest, Register_Unregister_Success) {
    // 创建一个 ServiceProfilerThreadWriter 实例
    msServiceProfiler::ServiceProfilerThreadWriter threadWriter;

    // 注册
    msServiceProfiler::DbBuffer *buffer = manager_->Register(&threadWriter);
    ASSERT_NE(buffer, nullptr);

    // 验证注册成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 1);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 1);

    // 注销
    manager_->Unregister(&threadWriter);

    // 验证注销成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 0);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 1);
    EXPECT_EQ(manager_->disableDbBuffers_.size(), 1);
}

TEST_F(ServiceProfilerWriterManagerTest, Register_MultipleThreads_Success) {
    // 创建多个 ServiceProfilerThreadWriter 实例
    msServiceProfiler::ServiceProfilerThreadWriter threadWriter1;
    msServiceProfiler::ServiceProfilerThreadWriter threadWriter2;

    // 注册
    msServiceProfiler::DbBuffer *buffer1 = manager_->Register(&threadWriter1);
    msServiceProfiler::DbBuffer *buffer2 = manager_->Register(&threadWriter2);
    ASSERT_NE(buffer1, nullptr);
    ASSERT_NE(buffer2, nullptr);

    // 验证注册成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 2);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 2);

    // 注销
    manager_->Unregister(&threadWriter1);
    manager_->Unregister(&threadWriter2);

    // 验证注销成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 0);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 2);
    EXPECT_EQ(manager_->disableDbBuffers_.size(), 2);
}

TEST_F(ServiceProfilerWriterManagerTest, Unregister_NonExistent_Thread_Success) {
    // 创建一个未注册的 ServiceProfilerThreadWriter 实例
    msServiceProfiler::ServiceProfilerThreadWriter threadWriter;

    // 尝试注销
    manager_->Unregister(&threadWriter);

    // 验证状态不变
    EXPECT_EQ(manager_->mapBuffer_.size(), 0);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 0);
    EXPECT_EQ(manager_->disableDbBuffers_.size(), 0);
}

TEST_F(ServiceProfilerWriterManagerTest, Unregister_MultipleTimes_Success) {
    // 创建一个 ServiceProfilerThreadWriter 实例
    msServiceProfiler::ServiceProfilerThreadWriter threadWriter;

    // 注册
    msServiceProfiler::DbBuffer *buffer = manager_->Register(&threadWriter);
    ASSERT_NE(buffer, nullptr);

    // 验证注册成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 1);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 1);

    // 第一次注销
    manager_->Unregister(&threadWriter);
    // 验证注销成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 0);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 1);  // 由于 Unregister 没有从 workingDbBuffers_ 中移除
    EXPECT_EQ(manager_->disableDbBuffers_.size(), 1);

    // 第二次注销
    manager_->Unregister(&threadWriter);
    // 验证第二次注销不影响状态
    EXPECT_EQ(manager_->mapBuffer_.size(), 0);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 1);
    EXPECT_EQ(manager_->disableDbBuffers_.size(), 1);
}


TEST_F(ServiceProfilerWriterManagerTest, Register_After_Unregister_Success) {
    // 创建一个 ServiceProfilerThreadWriter 实例
    msServiceProfiler::ServiceProfilerThreadWriter threadWriter;

    // 注册
    msServiceProfiler::DbBuffer *buffer = manager_->Register(&threadWriter);
    ASSERT_NE(buffer, nullptr);

    // 验证注册成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 1);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 1);

    // 注销
    manager_->Unregister(&threadWriter);
    // 验证注销成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 0);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 1);
    EXPECT_EQ(manager_->disableDbBuffers_.size(), 1);

    // 重新注册
    msServiceProfiler::DbBuffer *newBuffer = manager_->Register(&threadWriter);
    ASSERT_NE(newBuffer, nullptr);

    // 验证重新注册成功
    EXPECT_EQ(manager_->mapBuffer_.size(), 1);
    EXPECT_EQ(manager_->workingDbBuffers_.size(), 2);
    EXPECT_EQ(manager_->disableDbBuffers_.size(), 1);
}

TEST_F(ServiceProfilerWriterManagerTest, Start_With_Valid_OutputPath_Success) {
    // 设置输出路径
    std::string outputPath = "/path/to/output";

    // 调用 Start 方法
    manager_->Start(outputPath);

    // 验证 closeFlag_ 和 profPath_ 的值
    EXPECT_FALSE(manager_->closeFlag_);
    EXPECT_EQ(manager_->profPath_, outputPath);
}

TEST_F(ServiceProfilerWriterManagerTest, Start_With_Empty_OutputPath_Success) {
    // 设置空的输出路径
    std::string outputPath = "";

    // 调用 Start 方法
    manager_->Start(outputPath);

    // 验证 closeFlag_ 和 profPath_ 的值
    EXPECT_FALSE(manager_->closeFlag_);
    EXPECT_EQ(manager_->profPath_, outputPath);
}

TEST_F(ServiceProfilerWriterManagerTest, Start_With_Special_Characters_OutputPath_Success) {
    // 设置包含特殊字符的输出路径
    std::string outputPath = "/path/with spaces and/special!chars";

    // 调用 Start 方法
    manager_->Start(outputPath);

    // 验证 closeFlag_ 和 profPath_ 的值
    EXPECT_FALSE(manager_->closeFlag_);
    EXPECT_EQ(manager_->profPath_, outputPath);
}

TEST_F(ServiceProfilerWriterManagerTest, Start_Multiple_Times_Success) {
    // 第一次设置输出路径
    std::string outputPath1 = "/path/to/output1";
    manager_->Start(outputPath1);
    EXPECT_FALSE(manager_->closeFlag_);
    EXPECT_EQ(manager_->profPath_, outputPath1);

    // 第二次设置输出路径
    std::string outputPath2 = "/path/to/output2";
    manager_->Start(outputPath2);
    EXPECT_FALSE(manager_->closeFlag_);
    EXPECT_EQ(manager_->profPath_, outputPath2);
}

TEST_F(ServiceProfilerWriterManagerTest, Start_Reset_OutputPath_Success) {
    // 第一次设置输出路径为空
    std::string outputPath1 = "";
    manager_->Start(outputPath1);
    EXPECT_FALSE(manager_->closeFlag_);
    EXPECT_EQ(manager_->profPath_, outputPath1);

    // 第二次设置有效的输出路径
    std::string outputPath2 = "/path/to/output";
    manager_->Start(outputPath2);
    EXPECT_FALSE(manager_->closeFlag_);
    EXPECT_EQ(manager_->profPath_, outputPath2);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}