import requests
import json

def chat_via_requests():
    # FreeLLM Router 的标准 HTTP 接口地址
    url = "http://localhost:8000/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # 构建请求负载
    payload = {
        # 'model' 设置为 'adaptive' 会启用智能调度引擎
        # 路由器会根据当前各供应商的健康度、延迟和配额自动选择最优模型
        "model": "adaptive",
        
        "messages": [
            {"role": "user", "content": "请写一首关于编程的小诗。"}
        ],
        
        # 'task_type' 是调度器的重要提示参数：
        # - 'text': 通用文本生成，优先选取高质量模型
        # - 'trading': 交易助手，优先选取低延迟模型
        # - 'analysis': 深入分析，优先选取长上下文和逻辑强的模型
        "task_type": "text",
        
        "temperature": 0.8
    }

    print("正在通过 requests 发送请求到 FreeLLM Router...")
    try:
        # 发送 POST 请求
        response = requests.post(url, headers=headers, json=payload)
        
        # 检查 HTTP 状态码（429/402 会被路由器捕获并返回 500 或降级，此处直接抛出异常）
        response.raise_for_status()
        
        # 解析返回结果
        result = response.json()
        print("\n--- 路由器返回内容 ---")
        print(result['choices'][0]['message']['content'])
        
        # 打印实际使用的模型（如果有返回）
        actual_model = result.get('model', 'unknown')
        print(f"\n[实际使用的响应模型: {actual_model}]")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP 错误: {e}")
        if e.response is not None:
            print(f"服务器返回详情: {e.response.text}")
    except Exception as e:
        print(f"发生非预期错误: {e}")

if __name__ == "__main__":
    chat_via_requests()
