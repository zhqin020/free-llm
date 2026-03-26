# FreeLLM Router 系统设计

## 目标

构建一个动态、可监控、可调度的 LLM 资源池，并实现一个自适应调度系统。

核心需求：
- OpenAI 兼容接口
- 多 provider 自动切换
- 超时、限流、失败自动回退
- 自动淘汰不稳定 provider
- 自动发现最快模型
- 任务类型调度（交易/分析/文本）
- 成本优化（优先免费）
- 管理界面及 GitHub 清单同步

## 主要模块

1. Provider Registry
2. Health Manager
3. Scheduler
4. Router API
5. 管理控制面板
6. GitHub 同步

## 数据流

1. 读取 `config.yaml` 初始化 provider --> registry
2. 调度请求：`/v1/chat/completions` -> Scheduler -> Router -> Provider
3. 监控：record_result -> HealthManager -> evaluate
4. 管理操作：`/admin/providers/*` -> provider 状态改变/同步

## 核心原理与工作机制

### 1. 资源发现与同步 (Sync Logic)
项目通过 `src/admin.py` 中的同步脚本，自动从外部资源库（如 `freellm-res`）解析 `README.md` 文件。它能识别各个服务商（Provider）及其提供的模型（Model），并将它们动态加载到内存中的**注册表 (Provider Registry)**。

### 2. 状态监控与健康检查 (Health Management)
系统通过 `src/health.py` 实时追踪每个模型的性能指标：
- **成功率**：监控错误频率，自动熔断故障节点。
- **延迟 (Latency)**：记录并计算 P99 延迟，确保低延迟响应。
- **状态切换**：利用滑动窗口算法，对不稳定 Provider 进行自动淘汰及冷却恢复。

### 3. 智能调度算法 (Scheduler & Scoring)
`src/scheduler.py` 根据以下维度动态计算模型得分并选出最优解：
- **成本优先级**：强制优先选择标记为 `free` 的资源。
- **任务适配度**：根据请求的 `task_type` 匹配模型标签（Tags）。
- **性能评估**：实时高错误率和延迟会产生显著减分。
- **配置校验**：自动识别并降权未配置 API Key 或使用占位符的 Provider。

### 4. 适配器模式 (Adapter Pattern)
在 `src/adapters.py` 中封装了多种 API 协议（OpenRouter, Google AI Studio, Generic OpenAI 等），将异质的后端接口统一转化为标准的 OpenAI 兼容响应格式。

### 5. 高可用路由转发 (Routing & Proxy)
`src/router.py` 实现了 OpenAI 兼容的 `/v1/chat/completions` 入口。当首选模型请求失败时，系统会依托重试机制（Max Retries）自动、无感地切换到备选的高分资源。

---

## 扩展计划

- 支持 Prometheus metrics + Grafana
- 实现 provider local circuit-breaker
- 引入历史结果学习模型（推荐系统）
- 引入异步请求池和 model warmup

