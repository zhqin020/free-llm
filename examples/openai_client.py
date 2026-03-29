import openai

# 配置 OpenAI 客户端指向本地的 FreeLLM Router
# Router 遵循 OpenAI 标准协议，因此可以直接使用官方 SDK
client = openai.OpenAI(
    # 指向本地路由器的 v1 路径
    base_url="http://localhost:8000/v1",
    
    # 本地路由器不需要真实的 API Key，但 SDK 要求必须提供一个非空字符串
    api_key="none"
)

def chat_example():
    print("正在通过 OpenAI SDK 调用 FreeLLM Router...")
    try:
        # 使用标准的 chat.completions 接口
        response = client.chat.completions.create(
            # 'model' 设置为 'adaptive' 触发路由器的自动调度逻辑
            model="adaptive",
            
            messages=[
                {"role": "system", "content": "你是一个专业的助手。"},
                {"role": "user", "content": "用一句话概括什么是量子纠缠。"}
            ],
            
            # 使用 extra_body 传入路由器特有的参数：
            # 'task_type': 提示调度器采用何种策略（text/trading/analysis）
            extra_body={"task_type": "analysis"} 
        )
        
        # 打印响应结果
        print("\n--- 客户端接收到的回复 ---")
        print(response.choices[0].message.content)
        
        # 打印实际由哪个后端模型生成
        print(f"\n[响应模型: {response.model}]")
        
    except Exception as e:
        print(f"调用发生错误: {e}")

if __name__ == "__main__":
    chat_example()
