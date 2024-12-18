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


int DcmiInit(void* handleDcmi_)
{
    // int ret = dcmi_init();
    using DcmiInitFunc = int(*)();
    DcmiInitFunc dcmiInit = (DcmiInitFunc) dlsym(handleDcmi_, "dcmi_init");
    int ret = dcmiInit();
    return ret;
}

int InitDcmiGetCardList(int *card_num, int *card_list, int list_len, void* handleDcmi_)
{
    // int dcmi_get_card_list(int *card_num, int *card_list, int list_len)
    using DcmiGetCardListFunc = int(*)(int *, int *, int);
    DcmiGetCardListFunc dcmiGetCardList = (DcmiGetCardListFunc) dlsym(handleDcmi_,
        "dcmi_get_card_list");
    int ret = dcmiGetCardList(card_num, card_list, list_len);
    return ret;
}

int DcmiGetDeviceIdInCard(int card_id, int *device_id_max, void* handleDcmi_)
{
    // int dcmi_get_device_id_in_card(int card_id, int *device_id_max, int *mcu_id, int *cpu_id)
    using DcmiGetDeviceIdInCardFunc = int(*)(int, int *, int *, int*);
    DcmiGetDeviceIdInCardFunc dcmiGetDeviceIdInCard = (DcmiGetDeviceIdInCardFunc) dlsym(handleDcmi_,
        "dcmi_get_device_id_in_card");
    int mcu_id = 0;
    int cpu_id = 0;
    int ret = dcmiGetDeviceIdInCard(card_id, device_id_max, &mcu_id, &cpu_id);
    return ret;
}

int DcmiGetDeviceMemoryInfoV3(int card_id, int device_id, struct dcmi_get_memory_info_stru *memory_info, void* handleDcmi_)
{
    // int dcmi_get_device_memory_info_v3(int card_id, int device_id, struct dcmi_get_memory_info_stru *memory_info)
    using DcmiGetDeviceMemoryInfoV3Func = int(*)(int, int, dcmi_get_memory_info_stru *);
    DcmiGetDeviceMemoryInfoV3Func dcmiGetDeviceMemoryInfoV3 = (DcmiGetDeviceMemoryInfoV3Func) dlsym(
        handleDcmi_, "dcmi_get_device_memory_info_v3"
    );
    int ret = dcmiGetDeviceMemoryInfoV3(card_id, device_id, memory_info);
    return ret;
}

int GetNpuMemoryUsage(std::vector<int>& memory_used, std::vector<int>& memory_utiliza) {
    void *handleDcmi_ = nullptr;
    handleDcmi_ = dlopen("libdcmi.so", RTLD_LAZY | RTLD_LOCAL);

    int ret = DcmiInit(handleDcmi_);
    if (ret != 0) {
        return ret;
    }

    int card_num = 0;
    int card_list[64] = {0};
    int list_len = 64;

    ret = InitDcmiGetCardList(&card_num, card_list, list_len, handleDcmi_);
    if (ret != 0) {
        return ret;
    }

    for (int card_id = 0; card_id < card_num; card_id++) {
        int device_id_max = 0;
        ret = DcmiGetDeviceIdInCard(card_list[card_id], &device_id_max, handleDcmi_);
        for (int device_id = 0; device_id < device_id_max; device_id++) {
            struct dcmi_get_memory_info_stru memory_info = {0};
            ret = DcmiGetDeviceMemoryInfoV3(card_list[card_id], device_id, &memory_info, handleDcmi_);
            memory_used.push_back(memory_info.memory_size - memory_info.memory_available);
            memory_utiliza.push_back(memory_info.utiliza);
        }
    }

    return 0;
}