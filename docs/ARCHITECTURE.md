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

## 扩展计划

- 支持 Prometheus metrics + Grafana
- 实现 provider local circuit-breaker
- 引入历史结果学习模型（推荐系统）
- 引入异步请求池和 model warmup

