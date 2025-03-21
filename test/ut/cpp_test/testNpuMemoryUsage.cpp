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

using namespace msServiceProfiler;


int DcmiStub()
{
    int retSuccess = 1;
    return retSuccess;
}

TEST(NPUTest, TestDlopenFailed)
{
    MOCKER(dlopen).stubs().will(returnValue((void*)nullptr));

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

    GlobalMockObject::reset();
}

TEST(NPUTest, TestDcmiGetDeviceHbmInfo)
{
    struct dsmi_hbm_info_stru dsmi_stru2{1, 1, 1, 1};

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.DcmiGetDeviceHbmInfo(0, 0, &dsmi_stru2);
}

TEST(NPUTest, TestInitDcmiCardAndDevicesDcmiInitFailed)
{
    MOCKER(dlopen).stubs().will(returnValue((void*)nullptr));

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.InitDcmiCardAndDevices();

    GlobalMockObject::reset();
}

TEST(NPUTest, TestInitDcmiCardAndDevicesDcmiGetCardListFailed)
{
    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();
    npuMemoryUsage.DcmiInit();
    npuMemoryUsage.InitDcmiCardAndDevices();
}

TEST(NPUTest, TestGetByDcmi)
{
    MOCKER(dlopen).stubs().will(returnValue((void*)nullptr));

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

    GlobalMockObject::reset();
}

TEST(NPUTest, TestDcmiInitSuccess)
{
    MOCKER(dlopen).stubs().will(returnValue((void*)(1)));
    MOCKER(dlsym).stubs().will(returnValue((void*)DcmiStub));

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
    GlobalMockObject::reset();
}