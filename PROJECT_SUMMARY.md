# FreeLLM Router 项目总结

## 1. 项目概述
FreeLLM Router 是一个生产级的 LLM 路由与管理系统，旨在整合并优化 [Free LLM API resources](https://github.com/freellm-res) 提供的免费大模型资源。它不仅是一个简单的转发代理，更是一个具备自适应调度、健康监测和弹性容错能力的智能网关。

## 2. 核心架构与技术栈
*   **后端**: Python 3.13 (FastAPI / Uvicorn)
*   **数据库**: SQLite 3 (持久化存储 Provider 状态与模型清单)
*   **管理界面**: Vanilla JS + CSS (响应式仪表盘，支持实时状态监控)
*   **环境管理**: Conda (`freellm` 虚拟环境)

## 3. 核心功能与技术亮点

### 🚀 智能调度与自适应路由 (Smart Scheduling)
*   **任务感知**: 支持 `text` (通用), `trading` (低延迟), `analysis` (长上下文) 等任务画像。
*   **模型优先级**: 自动评估延迟 (P99)、错误率和成本，优先选择高质量且免费的资源。
*   **显式模型覆盖**: 支持在请求中指定特定模型（如 `meta/llama-3.1-405b-instruct`），若指定模型不可用则自动回退至最优推荐。

### 🛡️ 高级弹性与容错 (Resilience Engine)
*   **Smart 429/402 处理器**: 
    *   自动识别 `429 Too Many Requests` (速率限制) 和 `402 Payment Required` (额度耗尽)。
    *   **每日配额检测**: 能够从 API 响应中识别 "Daily Quota" 或 "PerDay" 字样，触发 1 小时防御性冷却。
*   **模型级黑名单**: 
    *   针对 NVIDIA NIM 等提供商的账号权限限制（如 "Function Not Found"），实现模型级冷却。
    *   如果某个模型在您的账号下无法访问，系统会临时将其屏蔽并自动轮换至其他可用模型（如从 405B 切换至 8B 或 Mistral）。

### 📊 仪表盘与管理 (Admin Dashboard)
*   **实时监控**: 直观展示所有 Provider 的健康度、延迟波动、P99 时间和剩余额度。
*   **动态同步**: 支持从 GitHub 资源库实时发现并更新 Provider 模板。
*   **探测与测试**: 提供内置探测引擎，支持自动发现 Provider 后台的所有可用模型 ID。

### 💾 稳健的持久化层 (Persistence Layer)
*   **SQLite 存储**: 替代了不稳定的 YAML 配置，确保在服务器重启后，所有模型状态、冷却时间、API Key 和额度信息均能完整保留。
*   **数据隔离**: 运行时的延迟统计和成功率保存在内存中（滑动窗口），而配置和核心状态保存在磁盘中。

## 4. 关键改进 (Resilience Hardening 阶段)
*   解决了 SambaNova 和 NVIDIA NIM 的 **404/500** 路由兼容性问题。
*   强化了 **User-Agent** 和 **模型 ID 清洗**，防止因多余空格或安全过滤导致的请求失败。
*   实现了 **Registry 动态重载**，允许在不重启服务器的情况下更新模型清单。
