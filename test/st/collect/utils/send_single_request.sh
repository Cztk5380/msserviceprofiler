send_single_request() {
    local ip_address=$1

    curl -X POST -d '{
    "model":"Qwen2.5",
    "messages": [{
        "role": "system",
        "content": "你是谁？"
    }],
    "max_tokens": 20,
"stream": false
}' "$ip_address"

}

# 检查参数数量
if [ "$#" -ne 1 ] ; then
    echo "Usage: $0 IP_ADDRESS"
    exit 1
fi

IP_ADDRESS=$1

send_single_request "$IP_ADDRESS"