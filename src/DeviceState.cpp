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
#include "acl/acl.h"
#include "msServiceProfiler/DeviceState.h"

namespace msServiceProfiler {
uint32_t g_deviceID = INVALID_DEVICE_ID;

int32_t MsprofSetDeviceCallbackImpl(VOID_PTR data, uint32_t len)
{
    if (len != sizeof(ProfSetDevPara)) {
        return EXITCODE_DEVICE_STATE_INVALID_DATA;
    }
    if (data == nullptr) {
        return EXITCODE_DEVICE_STATE_INVALID_DATA;
    }
    ProfSetDevPara *setCfg = (struct ProfSetDevPara *)data;
    g_deviceID = setCfg->isOpen ? setCfg->deviceId : INVALID_DEVICE_ID;
    return EXITCODE_DEVICE_STATE_SUCCESS;
}

void RegisterSetDeviceCallback()
{
    void *handle = dlopen("libprofapi.so", RTLD_LAZY | RTLD_LOCAL);
    if (handle == nullptr) {
        std::cerr << "[WARNING] failed to dlopen libprofapi.so. Will be not able to get MPU usage data. " <<
            "Check whether a NPU server or if NPU driver installed." << std::endl;
        return;
    }

    using ProfSetDeviceHandle = int32_t (*)(VOID_PTR, uint32_t);
    using ProfRegDeviceStateCallbackFunc = int32_t (*)(ProfSetDeviceHandle);
    ProfRegDeviceStateCallbackFunc profRegDeviceStateCallback =
        (ProfRegDeviceStateCallbackFunc)dlsym(handle, "profRegDeviceStateCallback");

    profRegDeviceStateCallback(MsprofSetDeviceCallbackImpl);
}
}
