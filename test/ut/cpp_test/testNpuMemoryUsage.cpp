/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <chrono>
#include <thread>
#include <gtest/gtest.h>
#include <mockcpp/mockcpp.hpp>

#include "msServiceProfiler/msServiceProfiler.h"
#include "msServiceProfiler/NpuMemoryUsage.h"
#include "acl/acl.h"
#include "stubs.h"

using namespace msServiceProfiler;

int DcmiStub()
{
    int retSuccess = 1;
    return retSuccess;
}

// 原始函数指针
static void * (*real_dlopen)(const char *, int) = nullptr;
static int (*real_stat)(const char*, struct stat*) = nullptr;

// Mock 控制
struct MockControl {
    bool real_func = true;
    bool bool_return = false;
    int int_return = 0;
    void * null_return = nullptr;
    int call_count = 0;
};
static MockControl mock_control;
static MockControl mock_control_stat;

// Mock 实现
extern "C" void * dlopen(const char *filename, int flags)
{
    mock_control.call_count++;
    if (mock_control.real_func) {
        real_dlopen = reinterpret_cast<decltype(real_dlopen)>(dlsym(RTLD_NEXT, "dlopen"));
        return real_dlopen(filename, flags);
    }
    return mock_control.null_return;
}

extern "C" int stat(const char* path, struct stat* buf)
{
    mock_control_stat.call_count++;
    if (mock_control_stat.real_func) {
        real_stat = reinterpret_cast<decltype(real_stat)>(
            dlsym(RTLD_NEXT, "stat")
        );
        return real_stat(path, buf);
    }
    return mock_control_stat.int_return;
}

TEST(NPUTest, TestWalkThrough) {

    std::vector<int> memoryUsed;
    std::vector<int> memoryUtiliza;

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.InitDcmiCardAndDevices();
    npuMemoryUsage.GetByDcmi(memoryUsed, memoryUtiliza);
}

TEST(NPUTest, TestDlopenFailed) {

    mock_control.real_func = false;
    int cardNum[] = {1};
    int cardList[] = {0};
    int listLen = 1;
    struct dcmi_get_memory_info_stru dsmi_stru{1, 1, 1, 1};
    struct dsmi_hbm_info_stru dsmi_stru2{1, 1, 1, 1};

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.DcmiGetCardList(cardNum, cardList, listLen);
    npuMemoryUsage.DcmiGetDeviceIdInCard(0, cardList);
    npuMemoryUsage.DcmiGetDeviceMemoryInfoV3(0, 0, &dsmi_stru);
    npuMemoryUsage.DcmiGetDeviceHbmInfo(0, 0, &dsmi_stru2);
    mock_control.real_func = true;
}

TEST(NPUTest, TestNpuMemoryUsageNotExists)
{
    mock_control_stat.real_func = false;
    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    mock_control_stat.real_func = true;
}

TEST(NPUTest, TestDcmiGetDeviceHbmInfo)
{
    struct dsmi_hbm_info_stru dsmi_stru2{1, 1, 1, 1};

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.DcmiGetDeviceHbmInfo(0, 0, &dsmi_stru2);
}

TEST(NPUTest, TestInitDcmiCard)
{
    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.InitDcmiCard();
}

TEST(NPUTest, TestInitDcmiCardDcmiInitFailed)
{
    mock_control.real_func = false;

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.InitDcmiCard();

    mock_control.real_func = true;
}

TEST(NPUTest, TestInitDcmiCardEmptyListLen)
{
    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.listLen = 0;
    npuMemoryUsage.InitDcmiCard();
}

TEST(NPUTest, TestInitDcmiCardAndDevices)
{
    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.InitDcmiCardAndDevices();
    npuMemoryUsage.InitDcmiCardAndDevices();  // call again
}

TEST(NPUTest, TestInitDcmiCardAndDevicesDcmiInitFailed)
{
    mock_control.real_func = false;

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.InitDcmiCardAndDevices();

    mock_control.real_func = true;
}

TEST(NPUTest, TestInitDcmiCardAndDevicesDcmiGetDeviceIdInCardFailed)
{
    mock_control.real_func = false;

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.cardNum = 1;
    npuMemoryUsage.InitDcmiCardAndDevices();

    mock_control.real_func = true;
}

TEST(NPUTest, TestGetByDcmi)
{
    std::vector<int> memUsed = {1};
    std::vector<int> memUtiliza = {1};
    std::vector<CardDevice> cardDevices = {};
    struct CardDevice cd1 = {0, 0};
    struct CardDevice cd2 = {1, 0};
    cardDevices.push_back(cd1);
    cardDevices.push_back(cd2);

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.isHbmDevice = true;
    npuMemoryUsage.cardDevices = cardDevices;
    npuMemoryUsage.GetByDcmi(memUsed, memUtiliza);
}

TEST(NPUTest, TestGetByDcmiWithoutDcmiForHbm)
{
    mock_control.real_func = false;

    std::vector<int> memUsed = {1};
    std::vector<int> memUtiliza = {1};
    std::vector<CardDevice> cardDevices = {};
    struct CardDevice cd1 = {0, 0};
    struct CardDevice cd2 = {1, 0};
    cardDevices.push_back(cd1);
    cardDevices.push_back(cd2);

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.isHbmDevice = true;
    npuMemoryUsage.cardDevices = cardDevices;
    npuMemoryUsage.GetByDcmi(memUsed, memUtiliza);

    mock_control.real_func = true;
}

TEST(NPUTest, TestGetByDcmiWithoutDcmiForNotHbm)
{
    mock_control.real_func = false;

    std::vector<int> memUsed = {1};
    std::vector<int> memUtiliza = {1};
    std::vector<CardDevice> cardDevices = {};
    struct CardDevice cd1 = {0, 0};
    struct CardDevice cd2 = {1, 0};
    cardDevices.push_back(cd1);
    cardDevices.push_back(cd2);

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.isHbmDevice = false;
    npuMemoryUsage.cardDevices = cardDevices;
    npuMemoryUsage.GetByDcmi(memUsed, memUtiliza);

    mock_control.real_func = true;
}

TEST(NPUTest, TestDcmiInitSuccess)
{
    int cardNum[] = {1};
    int cardList[] = {0};
    int listLen = 1;
    struct dcmi_get_memory_info_stru dsmi_stru{1, 1, 1, 1};
    struct dsmi_hbm_info_stru dsmi_stru2{1, 1, 1, 1};
    std::vector<int> memUsed = {1};
    std::vector<int> memUtiliza = {1};
    std::vector<CardDevice> cardDevices = {};
    struct CardDevice cd1 = {0, 0};
    struct CardDevice cd2 = {1, 0};
    cardDevices.push_back(cd1);
    cardDevices.push_back(cd2);

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.DcmiGetCardList(cardNum, cardList, listLen);
    npuMemoryUsage.DcmiGetDeviceIdInCard(0, cardList);
    npuMemoryUsage.DcmiGetDeviceMemoryInfoV3(0, 0, &dsmi_stru);
    npuMemoryUsage.DcmiGetDeviceHbmInfo(0, 0, &dsmi_stru2);
    npuMemoryUsage.InitDcmiCardAndDevices();

    npuMemoryUsage.isHbmDevice = true;
    npuMemoryUsage.cardDevices = cardDevices;
    npuMemoryUsage.GetByDcmi(memUsed, memUtiliza);
    
    npuMemoryUsage.handleDcmi = nullptr;
}
