import json  
import requests
from common.log import logger

def get_almanac():  
    """  
    获取历史上的今天  
    """  
    base_url = "https://v2.api-m.com/api/history"  
    
    # 打印请求信息（隐藏完整key）  
    logger.info("\n=== 请求信息 ===")  
    logger.info(f"请求URL: {base_url}")  
    
    try:  
        # 发送请求  
        logger.info("\n正在发送请求...")  
        response = requests.get(base_url)  
        response.raise_for_status()  # 检查HTTP状态码  
        
        # 尝试解析JSON  
        data = response.json()  
        
        if data:  
            if 'data' in data:  
                return data['data']  
            else:  
                logger.info("没有'data'字段！")
                return None  
        else:  
            logger.info("data is None!")
            return None  
        
    except requests.exceptions.Timeout:  
        logger.info("请求超时,请稍后重试")  
        return None  
    except requests.exceptions.HTTPError as e:  
        logger.info(f"HTTP错误: {e.response.status_code}")  
        return None  
    except requests.exceptions.RequestException as e:  
        logger.info(f"请求失败!")  
        return None  
    except json.JSONDecodeError:  
        logger.info("API返回的数据不是有效的JSON格式")  
        return None  
    except Exception as e:  
        logger.info(f"未知错误!")
        return None  

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
        logger.info(f"未知错误:!")  