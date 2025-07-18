#!/bin/bash
# 校验变量
validate_variable() {
    local var_value=$1
    local var_name=$2
    local var_type=${3:-none}

    case $var_type in
        path)
            if [[ -f "$var_value" ]]; then
                return 0
            else
                echo "$var_name : $var_value Variable is not a valid file path."
                return 1
            fi
            ;;
        dir)
            if [[ -d "$var_value" ]]; then
                return 0
            else
                echo "$var_name : $var_value Variable is not a valid directory path."
                return 1
            fi
            ;;
        str)
            if [[ -n "$var_value" ]]; then
                return 0
            else
                echo "$var_name : $var_value Variable is an empty string."
                return 1
            fi
            ;;
        none)
            return 0
            ;;
        *)
            echo "Invalid variable type. Valid types are: path, dir, str, none."
            return 1
            ;;
    esac
}

# 设置环境变量
set_env_variable() {
    local service_config_path=$1

    echo "in set_env_variable"
    export SERVICE_PROF_CONFIG_PATH=$service_config_path
}

# 修改服务化配置文件
bak_replace_file() {
    local src_path=$1
    local dst_path=$2

    echo "in bak_replace_file"

    # 检查源文件是否存在
    if [[ ! -f "$src_path" ]]; then
        echo "Source file does not exist, exiting."
        return 1
    fi

    # 备份目标文件
    if [[ -f "$dst_path" ]]; then
        mv "$dst_path" "$dst_path.bak"
    else
        echo "Destination file does not exist, no backup needed."
    fi

    # 复制源文件到目标文件
    cp "$src_path" "$dst_path"
}


create_config_file() {
    local config_path=${1}
    local prof_dir=${2}
    local enable=${3:-0}
    local profiler_level=${4:-"INFO"}
    local acl_task_time=${5:-0}


    # 检查配置文件路径是否已存在，如果存在则删除
    if [ -f "$config_path" ]; then
        echo "删除已存在的配置文件: $config_path"
        rm -f "$config_path"
    fi

    # 创建 JSON 对象
    local config_json=$(jq -n \
        --arg enable "$enable" \
        --arg prof_dir "$prof_dir" \
        --arg profiler_level "$profiler_level" \
        --arg acl_task_time "$acl_task_time" \
        '{ enable: ($enable | tonumber), prof_dir: $prof_dir, profiler_level: $profiler_level, acl_task_time: ($acl_task_time | tonumber) }')

    # 将 JSON 对象写入文件
    echo "$config_json" > "$config_path"

    echo "配置文件已创建: $config_path"
}

# 多次检查日志中的指定字符串
check_log_for_string() {
    local log_file_path=$1
    local checked_string=$2
    local max_attempts=${3:-5}
    local interval=${4:-60}
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if [ -f "$log_file_path" ]; then
            if grep -q "$checked_string" "$log_file_path"; then
                return 0
            fi
        else
            echo "日志文件 $log_file_path 未找到"
        fi

        echo "未找到 $checked_string 字段，等待 $interval 秒后再次检查..."
        sleep $interval
        attempt=$((attempt + 1))
    done

    echo "达到最大尝试次数，未找到 $checked_string 字段"
    return 1
}

# 启动mindie服务
start_mindie_service() {
    local log_path=$1

    echo "in start_mindie_service"
    pkill -9 mindie
    cd /usr/local/Ascend/mindie/latest/mindie-service
    chmod 640 conf/config.json
    nohup ./bin/mindieservice_daemon > $log_path 2>&1 &
    if ! check_log_for_string "$log_path" "Daemon start success"; then
        echo "Error: Daemon start failed"
        exit 1
    fi
}




# 检查参数数量
if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 SRC_SERVICE_CONFIG_PATH TEST_DIR [SRC_LIBMS_SERVICE_PROFILER_SO]"
    exit 1
fi

# 获取参数
SRC_SERVICE_CONFIG_PATH=$1
TEST_DIR=$2 # with timestamp
SRC_LIBMS_SERVICE_PROFILER_SO=$3

validate_variable "$SRC_SERVICE_CONFIG_PATH" "src_service_config_path" "path"
validate_variable "$TEST_DIR" "test_dir" "dir"

DST_SERVICE_CONFIG_PATH="/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json"
DST_LIBMS_SERVICE_PROFILER_SO="/usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/lib64/libms_service_profiler.so"

SERVICE_PROFILER_CONFIG_PATH="$TEST_DIR/profiler.json"
MINDIE_LOG_FILE="$TEST_DIR/mindie.log"

main() {
    set_env_variable "$SERVICE_PROFILER_CONFIG_PATH"

    bak_replace_file "$SRC_SERVICE_CONFIG_PATH" "$DST_SERVICE_CONFIG_PATH"

    bak_replace_file "$SRC_LIBMS_SERVICE_PROFILER_SO" "$DST_LIBMS_SERVICE_PROFILER_SO"

    create_config_file "$SERVICE_PROFILER_CONFIG_PATH" "$TEST_DIR/prof_result" 0 "INFO" 0

    if ! start_mindie_service "$MINDIE_LOG_FILE"; then
        echo "ST: test_pd_compitition FAILED: failed to start mindie service"
        return 1
    fi
}

main