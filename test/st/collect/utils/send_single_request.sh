send_single_request() {
    local ip_address=$1

    curl -H "Accept: application/json" -H "Content-type: application/json"  -X POST -d '{
    "inputs": "My name is Olivier and I",
    "stream": true,
    "parameters": {
    "temperature": 0.5,
    "top_k": 10,
    "top_p": 0.95,
    "max_new_tokens": 120,
    "do_sample": true,
    "seed": null,
    "repetition_penalty": 1.03,
    "details": true,
    "typical_p": 0.5,
    "watermark": false
    }
    }' "$ip_address"
}

# 检查参数数量
if [ "$#" -ne 1 ] ; then
    echo "Usage: $0 IP_ADDRESS"
    exit 1
fi

IP_ADDRESS=$1

send_single_request "$IP_ADDRESS"