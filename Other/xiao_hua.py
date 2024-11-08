import json  
import requests

def get_almanac():  
    """  
    获取历史上的今天  
    """  
    base_url = "https://api.apiopen.top/getJoke?page=1&count=1&type=text"  
    
    # 打印请求信息（隐藏完整key）  
    print("\n=== 请求信息 ===")  
    print(f"请求URL: {base_url}")  
    
    try:
        print("\n正在发送请求...")
        response = requests.get(base_url)
        response.raise_for_status()  # 检查HTTP状态码

        # 打印状态码和响应内容，便于调试
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.text}")

        # 尝试解析JSON
        data = response.json()
        print("JSON解析成功:", data)

    except requests.exceptions.HTTPError as e:
        print(f"HTTP错误: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"连接错误: {e}")
    except requests.exceptions.Timeout as e:
        print(f"请求超时: {e}")
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
    except Exception as e:
        print(f"其他错误: {e}")

def HistoryRquest(query):
    # 定义占卜关键词列表
    divination_keywords = ['历史上的今天']
    return any(keyword in query for keyword in divination_keywords)


def GetHistory():  
    """使用示例"""  
    try:      
        # 查询历史上的今天
        result = get_almanac()
        #格式化数据
        data = "\n".join(result)

        return data()
        
    except Exception as e:  
        print(f"未知错误:!")  

def main():  
    GetHistory()

if __name__ == "__main__":  
    main()  