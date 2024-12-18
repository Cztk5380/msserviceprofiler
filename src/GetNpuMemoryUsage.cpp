/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
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
#include "dcmi_interface_api.h"

#include "../include/msServiceProfiler/GetNpuMemoryUsage.h"


int DcmiInit(void* handleDcmi)
{
    using DcmiInitFunc = int(*)();
    DcmiInitFunc dcmiInit = (DcmiInitFunc) dlsym(handleDcmi, "dcmi_init");
    int ret = dcmiInit();
    return ret;
}

int InitDcmiGetCardList(int *cardNum, int *cardList, int listLen, void* handleDcmi)
{
    using DcmiGetCardListFunc = int(*)(int *, int *, int);
    DcmiGetCardListFunc dcmiGetCardList = (DcmiGetCardListFunc) dlsym(handleDcmi,
        "dcmi_get_card_list");
    int ret = dcmiGetCardList(cardNum, cardList, listLen);
    return ret;
}

int DcmiGetDeviceIdInCard(int cardId, int *deviceIdMax, void* handleDcmi)
{
    using DcmiGetDeviceIdInCardFunc = int(*)(int, int *, int *, int*);
    DcmiGetDeviceIdInCardFunc dcmiGetDeviceIdInCard = (DcmiGetDeviceIdInCardFunc) dlsym(handleDcmi,
        "dcmi_get_device_id_in_card");
    int mcuId = 0;
    int cpuId = 0;
    int ret = dcmiGetDeviceIdInCard(cardId, deviceIdMax, &mcuId, &cpuId);
    return ret;
}

int DcmiGetDeviceMemoryInfoV3(int cardId, int deviceId, struct dcmi_get_memory_info_stru *memoryInfo, void* handleDcmi)
{
    using DcmiGetDeviceMemoryInfoV3Func = int(*)(int, int, dcmi_get_memory_info_stru *);
    DcmiGetDeviceMemoryInfoV3Func dcmiGetDeviceMemoryInfoV3 = (DcmiGetDeviceMemoryInfoV3Func) dlsym(handleDcmi,
        "dcmi_get_device_memory_info_v3");
    int ret = dcmiGetDeviceMemoryInfoV3(cardId, deviceId, memoryInfo);
    return ret;
}

int GetNpuMemoryUsage(std::vector<int>& memoryUsed, std::vector<int>& memoryUtiliza)
{
    void *handleDcmi = nullptr;
    handleDcmi = dlopen("libdcmi.so", RTLD_LAZY | RTLD_LOCAL);

    int ret = DcmiInit(handleDcmi);
    if (ret != 0) {
        return ret;
    }

    int cardNum = 0;
    int cardList[64] = {0};
    int listLen = 64;

    ret = InitDcmiGetCardList(&cardNum, cardList, listLen, handleDcmi);
    if (ret != 0) {
        return ret;
    }

    for (int cardId = 0; cardId < cardNum; cardId++) {
        int deviceIdMax = 0;
        ret = DcmiGetDeviceIdInCard(cardList[cardId], &deviceIdMax, handleDcmi);
        for (int deviceId = 0; deviceId < deviceIdMax; deviceId++) {
            struct dcmi_get_memory_info_stru memoryInfo = {0};
            ret = DcmiGetDeviceMemoryInfoV3(cardList[cardId], deviceId, &memoryInfo, handleDcmi);
            memoryUsed.push_back(memoryInfo.memory_size - memoryInfo.memory_available);
            memoryUtiliza.push_back(memoryInfo.utiliza);
        }
    }

    return 0;
}