# Metric ST

The default command runs only the stable basic scenario:

```bash
python run_metric_st.py \
  --model-path /data/models/Qwen3-8B \
  --metric-source /home/user/msserviceprofiler \
  --workspace /tmp/metric-st
```

Special scenarios are selected explicitly:

```bash
python run_metric_st.py --scenario eplb --model-path /data/models/MoE --device 0 --device 1
python run_metric_st.py --scenario dplb --model-path /data/models/model --device 0 --device 1
```

The EPLB scenario sets `DYNAMIC_EPLB=true`, enables expert parallelism, uses
tensor parallel size equal to the selected device count, and injects the
vllm-ascend `eplb_config` through `--additional-config`.

The runner owns vLLM scenario arguments and capability checks. Advanced arguments
can be appended with `--vllm-extra-arg=--option`.
The default smoke request driver uses short OpenAI-compatible `curl` requests to
avoid depending on version-specific `vllm bench` CLI flags. Increase request
coverage with `--metric-request-count`; EPLB and DPLB also send multiple requests
by default to make runtime metrics easier to trigger.

Each scenario starts an isolated vLLM service. Failed or debug runs keep artifacts
under `<workspace>/metric-smoke/<scenario>/<uuid>/`, including preflight, install,
service, request, raw metrics, and assertion reports.
