# FreeLLM Router

FreeLLM Router 是一个利用 [Free LLM API resources](https://github.com/freellm-res) 提供的免费资源开发的 LLM 路由器，为本地应用提供免费的 LLM 服务池。

## 核心目标

构建一个动态、可监控、可调度的 LLM 资源池，以及一个自适应 LLM 调度系统，能力包括：

- 自动淘汰不稳定 provider
- 自动发现最快模型
- 按任务选择模型（交易 / 分析 / 文本）
- 成本优化（优先免费）

## 功能特性

- ✅ OpenAI 兼容接口（API 路由、请求格式、响应结构）
- ✅ 多 Provider 自动切换（OpenRouter、Google AI Studio、HuggingFace Inference、Vercel AI 等）
- ✅ 超时 / 限流 / 失败自动 fallback（基于 token、QPS、重试机制）
- ✅ 动态健康检查+状态评分（将 provider 评估为稳定/不稳定）
- ✅ 任务感知调度（model tag + scene 优先策略）
- ✅ 成本感知路由（免费优先/信用额度、收费优先/低成本）

## 系统设计概览

### 1. 组件架构

- Provider Registry：维护所有 Provider 配置、模型清单、权重、限额、状态
- Health Manager：定期运行健康检测、响应时间统计、成功率评估
- Scheduler：基于策略选择最佳 Provider+Model
- Fallback Engine：支持超时、限流、失败、降级、备用 Provider
- Metrics/监控：Prometheus、Grafana、日志、事件告警
- API Adapter：提供 OpenAI 兼容 HTTP 接口（`/v1/chat/completions` 等）

### 2. 调度策略（Scheduler）

- 自动淘汰机制：
  - 连续错误次数、超时率、P99 延迟超过阈值时标记为 `unstable`
  - 不稳定 Provider 进入冷却窗口（如 5-10 分钟），之后重新探测
- 快速模型发现：
  - 动态采样：短时间内跟踪不同モデル latency 分布
  - 选取 P50/P90 最佳模型，按任务类型动态映射
- 任务分类（示例场景）：
  - 交易：低延迟、确定性、支持结构化处理
  - 分析：中等延迟、大上下文、稳定吞吐
  - 文本：高质量、创意、长输出
- 成本优先：
  - 首选 `free` tag provider/model；不足时回退 paid 低成本
  - 自定义权重（free=100, paid=50）与预算控制

### 3. 监控与可观测性

- 实时监控指标：
  - Provider: latency, success_rate, error_rate, qps
  - Model: tokens_per_request, cost_estimate, availability
  - 任务: 调度决策、执行时长、失败率、降级次数
- 支持日志+事件：
  - 失败原因、fallback 链、重试计数、超时阈值
- 运行时 Dashboard：
  - 当前活动 Provider 列表/状态、候补池、机器人决策来源

## 示例配置（config.yaml）

```yaml
providers:
  - name: openrouter
    type: openrouter
    api_key: "OPENROUTER_KEY"
    free: true
    models:
      - id: "gemma-3-12b-it:free"
        tags: ["analysis","text"]
      - id: "llama-3.2-3b-instruct:free"
        tags: ["trading","text"]
  - name: google_ai_studio
    type: google
    api_key: "GOOGLE_KEY"
    free: false
    models:
      - id: "gemini-3-flash"
        tags: ["analysis","text"]

scheduler:
  strategy: "adaptive"
  max_retries: 3
  timeout_seconds: 20
  eviction:
    error_rate: 0.2
    p90_latency_ms: 1200
    cool_down_sec: 300

task_profiles:
  trading:
    priority: ["low_latency","reliability"]
    candidate_tags: ["trading"]
  analysis:
    priority: ["throughput","context"]
    candidate_tags: ["analysis"]
  text:
    priority: ["quality","free"]
    candidate_tags: ["text"]
```

## 快速开始

1. 运行服务：
   ```bash
   python main.py --config config.yaml
   ```
2. 触发任务：
   ```bash
   curl -X POST http://127.0.0.1:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"adaptive","messages":[{"role":"user","content":"写一段交易策略"}],"task_type":"trading"}'
   ```

## 设计预备工作

下一步：
1. 详细定义核心模块接口（ProviderAdapter, HealthMonitor, Scheduler, FallbackPolicy）
2. 实现监控组件（Prometheus metrics + Grafana dashboard）
3. 编写单元测试和压力测试（多 provider 并发调度，故障注入）
4. 优化自适应策略（在线学习：历史表现 + 负载预测）

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 参考

- [Free LLM API resources](https://github.com/freellm-res) - 免费 LLM API 资源列表
