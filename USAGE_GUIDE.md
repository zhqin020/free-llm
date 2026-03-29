# FreeLLM Router 使用指南

## 1. 环境准备与启动

### 环境激活 (Conda)
推荐在 `freellm` conda 虚拟环境下运行：
```bash
conda activate freellm
```

### 启动服务器
运行以下命令启动 FastAPI 后端服务（默认端口 8000）：
```bash
/home/watson/miniconda3/envs/freellm/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```
*   **注意**: 系统会自动加载当前目录下的 `freellm.db` 数据库。

## 2. 管理后台使用 (Dashboard)
访问 `http://<your-ip>:8000/` 进入 Web 管理界面。

### 核心操作流程：
1.  **同步资源 (Sync)**: 点击 "Sync Resources" 从仓库拉取最新的 Provider 模板。
2.  **配置 API Key**: 在相应 Provider 栏位填入 API Key。系统会自动持久化保存。
3.  **自动探测 (Probe)**: 点击 "Probe" 按钮，系统会尝试连接供应商并自动补全所有可用的模型 ID（解决 404/Function Not Found 的关键）。
4.  **冒烟测试 (Test)**: 在测试弹窗中选择一个模型 ID（推荐首选 8B 或 Small 模型），点击 "Test" 验证连通性。

## 3. API 接口调用

### 路径
`POST /v1/chat/completions`

### 标准请求 (自适应路由)
将 `model` 设置为 `adaptive`，并提供 `task_type` 引导调度器：
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "adaptive",
    "task_type": "text",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 显式模型指定
如果您需要精准控制（例如测试刚添加的高级模型）：
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta/llama-3.1-405b-instruct",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## 4. 故障排查与维护

### 数据库维护
*   所有持久化数据存储在 `freellm.db` 中。
*   如需手动重置，可删除该文件并重启服务器（系统会自动重建）。

### 冷却机制 (Cooldown)
*   **状态码 429**: 触发 "Smart Delay"（依据 API 返回的 retry-after 时间）。
*   **状态码 402**: 触发 "Exhausted" (1小时防御性锁定)。
*   **Function Not Found**: 自动黑名单单个模型 ID 1小时，不干扰其他模型。

### 关键日志
*   服务器运行时会输出 `DEBUG` 和 `INFO` 日志，记录每次路由选取的模型、延迟和成功情况。

## 5. 示例代码 (Examples)

项目中提供了两个示例脚本，展示了如何通过不同方式调用路由器。代码中包含详细的中文字释。

### 方式 A: 使用标准 requests 库
适用于不需要安装额外 SDK 的场景。
*   **文件**: `examples/requests_example.py`
*   **亮点**: 展示了如何构建 JSON 负载，以及如何通过 `task_type` 引导路由器。
*   **运行**: 
    ```bash
    python examples/requests_example.py
    ```

### 方式 B: 使用 OpenAI 官方 SDK
最推荐的集成方式，兼容性最强。
*   **文件**: `examples/openai_client.py`
*   **亮点**: 展示了如何通过 `base_url` 切换至本地路由器，并使用 `extra_body` 传递自定义参数。
*   **运行**:
    ```bash
    python examples/openai_client.py
    ```
