/* -------------------------------------------------------------------------
 * This file is part of the MindStudio project.
 * Copyright (c) 2025 Huawei Technologies Co.,Ltd.
 *
 * MindStudio is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *
 *          http://license.coscl.org.cn/MulanPSL2
 *
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 * -------------------------------------------------------------------------
*/
#ifndef GET_NPU_MEMORY_USAGE_H
#define GET_NPU_MEMORY_USAGE_H

#include <vector>


namespace msServiceProfiler {
struct dcmi_get_memory_info_stru {
    unsigned long long memory_size;      /* unit:MB */
    unsigned long long memory_available; /* free + hugepages_free * hugepagesize */
    unsigned int freq;
    unsigned long hugepagesize;          /* unit:KB */
    unsigned long hugepages_total;
    unsigned long hugepages_free;
    unsigned int utiliza;                /* ddr memory info usages */
    unsigned char reserve[60];           /* the size of dcmi_memory_info is 96 */
};

struct dsmi_hbm_info_stru {
    unsigned long long memory_size;  /**< HBM total size, MB */
    unsigned int freq;               /**< HBM freq, MHz */
    unsigned long long memory_usage; /**< HBM memory_usage, MB */
    int temp;                        /**< HBM temperature */
    unsigned int bandwith_util_rate;
};

const int EXITCODE_SUCCESS = 0;
const int EXITCODE_EMPTY_DCMI_HANDLER = 1;
constexpr int EXITCODE_EMPTY_DLSYM_ADDR = 2;
const int PERCENTAGE_SCALE = 100;
constexpr long long unsigned int HBM_MEMORY_SIZE_FALL_BACK = 1;
constexpr int MAX_CHIP_NUM = 64;

struct CardDevice {
    int cardId;
    int deviceId;
};

class NpuMemoryUsage {
public:
    NpuMemoryUsage();
    ~NpuMemoryUsage();
    int InitDcmiCard();
    int InitDcmiCardAndDevices();
    int GetByDcmi(std::vector<int> &memoryUsed, std::vector<int> &memoryUtiliza);

private:
    void *handleDcmi = nullptr;
    bool isHbmDevice = false;
    bool isDcmiInited = false;
    int cardNum = 0;
    int cardList[MAX_CHIP_NUM] = {0};
    int listLen = MAX_CHIP_NUM;
    std::vector<CardDevice> cardDevices;

    int DcmiInit();
    int DcmiGetCardList(int *paramCardNum, int *paramCardList, int paramListLen) const;
    int DcmiGetDeviceIdInCard(int cardId, int *deviceIdMax) const;
    int DcmiGetDeviceMemoryInfoV3(
        int cardId, int deviceId, struct dcmi_get_memory_info_stru *memoryInfo) const;
    int DcmiGetDeviceHbmInfo(int cardId, int deviceId, struct dsmi_hbm_info_stru *hbmInfo) const;
};
}  // namespace msServiceProfiler
#endif  // GET_NPU_MEMORY_USAGE_H
