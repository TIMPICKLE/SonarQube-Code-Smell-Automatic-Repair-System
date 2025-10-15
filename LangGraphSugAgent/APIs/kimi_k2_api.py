import json
import requests
import time
from langsmith.run_helpers import traceable


def initialize_kimi_client(base_url='http://127.0.0.1:6091/v1'):
    """
    初始化DeepSeek客户端配置
    
    参数:
        base_url (str): API基础URL
    
    返回:
        dict: 包含API配置的字典
    """
    return {
        "base_url": base_url,
        "headers": {
            "Content-Type": "application/json"
        }
    }

# 2. 在你的 Kimi 调用函数上添加装饰器
@traceable(run_type="llm")
def call_kimi(prompt, system_prompt="你是一个有用的AI助手。", 
                   client=None, 
                   base_url='http://127.0.0.1:6091/v1', 
                   model="Kimi-K2", 
                   stream=False,
                   temperature=0.3):
    """
    调用Kimi-K2模型获取回复
    
    参数:
        prompt (str): 用户提问内容
        system_prompt (str): 系统提示词
        client (dict, optional): 已初始化的客户端配置，如不提供则新建一个
        base_url (str): API基础URL，当client未提供时使用
        model (str): 模型名称
        stream (bool): 是否使用流式输出
        temperature (float): 温度参数，控制输出的随机性。值越低(如0.1)，回答越确定；值越高(如0.9)，回答越多样
    
    返回:
        str: 模型的文本回复
    """
    # 如果没有提供客户端配置，则创建一个
    if client is None:
        client = initialize_kimi_client(base_url)
    
    # 构建请求URL
    url = f"{client['base_url']}/chat/completions"
    
    # 构建请求体
    data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": stream,
        "temperature": temperature
    }

    print(f"调用Kimi-K2模型, 时间点: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
    print(f"请求URL: {url}")
    print(f"请求体: {json.dumps(data, ensure_ascii=False, indent=2)}")

    # 发送请求到Kimi-K2模型
    try:
        if not stream:
            response = requests.post(url, headers=client["headers"], json=data)
            response.raise_for_status()
            response_json = response.json()
            return response_json["choices"][0]["message"]["content"]
        else:
            # 流式输出处理
            headers = client["headers"].copy()
            response = requests.post(url, headers=headers, json=data, stream=True)
            response.raise_for_status()
            return response
    except requests.exceptions.RequestException as e:
        print(f"API请求错误: {str(e)}")
        raise

# 如果直接运行此文件，则执行示例调用
if __name__ == "__main__":
    # 示例使用
    prompt = "请用简短的话介绍一下你自己。"
    response = call_kimi(prompt)
    print("模型响应:")
    print(response)
