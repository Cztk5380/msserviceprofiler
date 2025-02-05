/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <iostream>
#include <vector>
#include <dlfcn.h>
#include "msServiceProfiler/NpuMemoryUsage.h"

namespace msServiceProfiler {
NpuMemoryUsage::NpuMemoryUsage()
{
    handleDcmi = dlopen("libdcmi.so", RTLD_LAZY | RTLD_LOCAL);
    if (handleDcmi == nullptr) {
        std::cerr << "[WARNING] failed to dlopen libdcmi.so. Will be not able to get MPU usage data. " <<
            "Check whether a NPU server or if NPU driver installed." << std::endl;
    }
}
NpuMemoryUsage::~NpuMemoryUsage()
{
    if (handleDcmi != nullptr) {
        dlclose(handleDcmi);
        handleDcmi = nullptr;
    }
}
int NpuMemoryUsage::DcmiInit() const
{
    using DcmiInitFunc = int (*)();
    if (handleDcmi == nullptr) {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }

    DcmiInitFunc dcmiInit = (DcmiInitFunc)dlsym(handleDcmi, "dcmi_init");
    int ret = dcmiInit();
    return ret;
}

int NpuMemoryUsage::DcmiGetCardList(int *cardNum, int *cardList, int listLen) const
{
    using DcmiGetCardListFunc = int (*)(int *, int *, int);
    if (handleDcmi == nullptr) {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetCardListFunc dcmiGetCardList = (DcmiGetCardListFunc)dlsym(handleDcmi, "dcmi_get_card_list");
    int ret = dcmiGetCardList(cardNum, cardList, listLen);
    return ret;
}

int NpuMemoryUsage::DcmiGetDeviceIdInCard(int cardId, int *deviceIdMax) const
{
    using DcmiGetDeviceIdInCardFunc = int (*)(int, int *, int *, int *);
    if (handleDcmi == nullptr) {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetDeviceIdInCardFunc dcmiGetDeviceIdInCard =
        (DcmiGetDeviceIdInCardFunc)dlsym(handleDcmi, "dcmi_get_device_id_in_card");
    int mcuId = 0;
    int cpuId = 0;
    int ret = dcmiGetDeviceIdInCard(cardId, deviceIdMax, &mcuId, &cpuId);
    return ret;
}

int NpuMemoryUsage::DcmiGetDeviceMemoryInfoV3(int cardId, int deviceId,
                                              struct dcmi_get_memory_info_stru *memoryInfo) const
{
    using DcmiGetDeviceMemoryInfoV3Func = int (*)(int, int, dcmi_get_memory_info_stru *);
    if (handleDcmi == nullptr) {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetDeviceMemoryInfoV3Func dcmiGetDeviceMemoryInfoV3 =
        (DcmiGetDeviceMemoryInfoV3Func)dlsym(handleDcmi, "dcmi_get_device_memory_info_v3");
    int ret = dcmiGetDeviceMemoryInfoV3(cardId, deviceId, memoryInfo);
    return ret;
}

int NpuMemoryUsage::DcmiGetDeviceHbmInfo(int cardId, int deviceId, struct dsmi_hbm_info_stru *hbmInfo) const
{
    using DcmiGetDeviceHbmInfoFunc = int(*)(int, int, dsmi_hbm_info_stru *);
    if (handleDcmi == nullptr) {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetDeviceHbmInfoFunc dcmiGetDeviceHbmInfo =
        (DcmiGetDeviceHbmInfoFunc) dlsym(handleDcmi, "dcmi_get_device_hbm_info");
    int ret = dcmiGetDeviceHbmInfo(cardId, deviceId, hbmInfo);
    return ret;
}

int NpuMemoryUsage::InitDcmiCardAndDevices()
{
    int ret = DcmiInit();
    if (ret != EXITCODE_SUCCESS) {
        return ret;
    }

    int cardNum = 0;
    int cardList[64] = {0};
    int listLen = 64;

    ret = DcmiGetCardList(&cardNum, cardList, listLen);
    if (ret != EXITCODE_SUCCESS) {
        return ret;
    }

    for (int cardId = 0; cardId < cardNum; cardId++) {
        int deviceIdMax = 0;
        int curRet = DcmiGetDeviceIdInCard(cardList[cardId], &deviceIdMax);
        if (curRet != EXITCODE_SUCCESS) {
            ret = ret + curRet;
            continue;
        }
        for (int deviceId = 0; deviceId < deviceIdMax; deviceId++) {
            cardDevices.push_back({cardList[cardId], deviceId});
        }
    }

    return ret;
}

int NpuMemoryUsage::GetByDcmi(std::vector<int> &memoryUsed, std::vector<int> &memoryUtiliza)
{
    int ret = EXITCODE_SUCCESS;
    for (const auto &cardDevice : cardDevices) {
        int curRet = EXITCODE_SUCCESS;
        // Could either be getting by DcmiGetDeviceMemoryInfoV3 or DcmiGetDeviceHbmInfo
        if (not isHbmDevice) { // Global value
            struct dcmi_get_memory_info_stru memoryInfo;
            curRet = DcmiGetDeviceMemoryInfoV3(cardDevice.cardId, cardDevice.deviceId, &memoryInfo);
            if (curRet != EXITCODE_SUCCESS) {
                isHbmDevice = true;  // Will try DcmiGetDeviceHbmInfo later, and skip this next time
            } else {
                memoryUsed.push_back(memoryInfo.memory_size - memoryInfo.memory_available);
                memoryUtiliza.push_back(memoryInfo.utiliza);
            }
        }

        if (isHbmDevice) {
            struct dsmi_hbm_info_stru hbmInfo;
            curRet = DcmiGetDeviceHbmInfo(cardDevice.cardId, cardDevice.deviceId, &hbmInfo);
            if (curRet != EXITCODE_SUCCESS) {
                ret = ret + curRet;
                continue;
            } else {
                memoryUsed.push_back(hbmInfo.memory_usage);
                memoryUtiliza.push_back(hbmInfo.memory_usage * PERCENTAGE_SCALE / hbmInfo.memory_size);
            }
        }
    }
    return ret;
}
}  // namespace msServiceProfiler
