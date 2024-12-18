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
void write2Tx(std::vector<int> memory_info, std::string metric_name)
{
    for (int i = 0; i < memory_info.size(); i++) {
        std::cout << i << std::endl;
        std::cout << memory_info[i] << std::endl;
        msServiceProfiler::Profiler<msServiceProfiler::INFO>().Domain("npu").Metric(metric_name.c_str(), memory_info[i]).MetricScope("device", i).Launch();
    }
}

// Function that will be executed in the new thread
void threadFunction()
{
    std::cout << "Hello from the new thread!" << std::endl;
    while (true) {
        std::vector<int> memory_used;
        std::vector<int> memory_utiliza;
        int ret = GetNpuMemoryUsage(memory_used, memory_utiliza);

        std::cout << "memory_used: " << memory_used[0] << std::endl;
        std::cout << "memory_info.utiliza: " << memory_utiliza[0] << std::endl;
        std::cout << std::endl;

        write2Tx(memory_used, "usage");
        write2Tx(memory_utiliza, "utiliza");
        std::this_thread::sleep_for(std::chrono::milliseconds(10000)); // sleep 10 seconds
    }
}

int main()
{
    // Create a new thread and pass the function to be executed
    std::thread t(threadFunction);

    // Detach the thread so it runs independently
    t.join();

    // Main process ends here
    std::cout << "Main process is ending." << std::endl;

    return 0;
}