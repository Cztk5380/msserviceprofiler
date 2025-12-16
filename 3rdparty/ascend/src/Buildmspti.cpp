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
#include "mspti/mspti.h"
namespace UTHelper {
msptiResult g_utStatusMsptiActivityRegisterCallbacks = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiActivityEnable = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiActivityFlushAll = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiSubscribe = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiUnsubscribe = msptiResult::MSPTI_SUCCESS;
}

using namespace UTHelper;

msptiResult msptiActivityRegisterCallbacks(bufferRequestFunctionPtr, bufferCompleteFunctionPtr)
{
    return g_utStatusMsptiActivityRegisterCallbacks;
}

msptiResult msptiActivityEnable(int kind)
{
    return g_utStatusMsptiActivityEnable;
}

msptiResult msptiActivityGetNextRecord(uint8_t *buffer, size_t validBufferSizeBytes, msptiActivity **record)
{
    // for ut
    thread_local uint8_t *localBuffer = nullptr;
    if (buffer == localBuffer) {
        localBuffer = nullptr;
        return MSPTI_ERROR_MAX_LIMIT_REACHED;
    }
    localBuffer = buffer;
    *record = reinterpret_cast<msptiActivity *>(buffer);
    if (buffer == nullptr) {
        return MSPTI_ERROR_INVALID_PARAMETER;
    } else if (validBufferSizeBytes < sizeof(msptiActivity)) {
        return MSPTI_ERROR_MAX_LIMIT_REACHED;
    } else {
        return MSPTI_SUCCESS;
    }
}

msptiResult msptiActivityFlushAll(int kind)
{
    return g_utStatusMsptiActivityFlushAll;
}

msptiResult msptiSubscribe(msptiSubscriberHandle *subscriber, int *callback, int *userdata)
{
    return g_utStatusMsptiSubscribe;
}

msptiResult msptiUnsubscribe(msptiSubscriberHandle subscriber)
{
    return g_utStatusMsptiUnsubscribe;
}