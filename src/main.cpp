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
#include <fstream>
#include <vector>
#include <thread>
#include "mstx/ms_tools_ext.h"

#include "../include/msServiceProfiler/GetNpuMemoryUsage.h"
#include "../include/msServiceProfiler/ServiceProfilerManager.h"
#include "../include/msServiceProfiler/Profiler.h"


// Funtion that write info to txt
void Write2Tx(std::vector<int> memoryInfo, std::string metricName)
{
    for (int i = 0; i < memoryInfo.size(); i++) {
        msServiceProfiler::Profiler<msServiceProfiler::INFO>()
            .Domain("npu")
            .Metric(metricName.c_str(), memoryInfo[i])
            .MetricScope("device", i)
            .Launch();
    }
}

// Function that will be executed in the new thread
void ThreadFunction()
{
    while (true) {
        std::vector<int> memoryUsed;
        std::vector<int> memoryUtiliza;
        int ret = GetNpuMemoryUsage(memoryUsed, memoryUtiliza);
        Write2Tx(memoryUsed, "usage");
        Write2Tx(memoryUtiliza, "utiliza");
        int sleepTime = 10000;
        std::this_thread::sleep_for(std::chrono::milliseconds(sleepTime)); // sleep 10 seconds
    }
}

int main()
{
    // Create a new thread and pass the function to be executed
    std::thread t(ThreadFunction);

    // Detach the thread so it runs independently
    t.join();

    // Main process ends here
    std::cout << "Main process is ending." << std::endl;

    return 0;
}