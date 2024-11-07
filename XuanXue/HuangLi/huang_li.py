import json  
import requests  
from typing import Optional  
from pathlib import Path  
from datetime import datetime  
from common.log import logger

def get_almanac(api_key: str, year: Optional[str] = None,   
                month: Optional[str] = None,   
                day: Optional[str] = None) -> dict:  
    """  
    获取老黄历数据  
    """  
    base_url = "https://api.tanshuapi.com/api/almanac/v1/index"  
    
    # 构建请求参数  
    params = {'key': api_key}  
    
    # 添加可选参数（进行验证）  
    if year:  
        try:  
            year_int = int(year)  
            if not 1900 <= year_int <= 2100:  
                logger.info("年份必须在1900-2100之间")  
                return None  
            params['year'] = str(year_int)  
        except ValueError:  
            logger.info("年份必须是有效的数字")  
            return None  
            
    if month:  
        try:  
            month_int = int(month)  
            if not 1 <= month_int <= 12:  
                logger.info("月份必须在1-12之间")  
                return None  
            params['month'] = str(month_int).zfill(2)  
        except ValueError:  
            logger.info("月份必须是有效的数字")  
            return None  
            
    if day:  
        try:  
            day_int = int(day)  
            if not 1 <= day_int <= 31:  
                logger.info("日期必须在1-31之间")  
                return None  
            params['day'] = str(day_int).zfill(2)  
        except ValueError:  
            logger.info("日期必须是有效的数字")  
            return None  
    
    # 打印请求信息（隐藏完整key）  
    logger.info("\n=== 请求信息 ===")  
    logger.info(f"请求URL: {base_url}")  
    safe_params = params.copy()  
    if 'key' in safe_params:  
        key = safe_params['key']  
        safe_params['key'] = f"{key[:4]}...{key[-4:]}"  
    logger.info(f"请求参数: {safe_params}")  
    
    try:  
        # 发送请求  
        logger.info("\n正在发送请求...")  
        response = requests.get(base_url, params=params, timeout=10)  
        response.raise_for_status()  # 检查HTTP状态码  
        
        # 尝试解析JSON  
        data = response.json()  
        
        # 验证响应数据  
        if not isinstance(data, (dict, list)):  
            logger.info("API响应格式错误")  
            return None  
        
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
        logger.info(f"请求失败: {str(e)}")  
        return None  
    except json.JSONDecodeError:  
        logger.info("API返回的数据不是有效的JSON格式")  
        return None  
    except Exception as e:  
        logger.info(f"未知错误: {str(e)}")  
        return None  

def format_almanac(data: dict) -> str:  
    """  
    格式化老黄历数据为纯文本格式  
    """  
    try:    
        if not isinstance(data, dict): 
            logger.info("输入不是字典！") 
            return None 
        
        # 构建输出文本  
        sections = f"""公历：{data['solar_calendar']}\n农历：{data['lunar_calendar']}\n星期：{data['week']} ({data['en_week']})\n{data['year_of'][0]} {data['year_of'][1]} {data['year_of'][2]}\n五行：{data['five_elements']}\n冲煞：{data['conflict']}\n宜：{'、'.join(data['should'])}\n忌：{'、'.join(data['avoid'])}\n吉神宜趋：{data['lucky_god']}\n财神方位：{data['wealthy_god']}\n喜神方位：{data['happy_god']}\n福神方位：{data['bless_god']}\n煞位：{data['evil']}\n胎神：{data['fetal_god']}\n吉日：{data['auspicious_day']}"""  
        return sections  
        
    except Exception as e:  
        return f"格式化数据失败: {str(e)}"  

def HuangLiRquest(query):
    # 定义占卜关键词列表
    divination_keywords = ['黄历', "今日黄历"]
    return any(keyword in query for keyword in divination_keywords)

def GetHuangLi(api_key):  
    """使用示例"""  
    try:      
        # 获取当前日期  
        today = datetime.now()  
        
        # 查询老黄历  
        data = get_almanac(  
            api_key,  
            year=str(today.year),  
            month=str(today.month),  
            day=str(today.day)  
        )  
        
        if data:
            # 格式化并显示结果  
            return format_almanac(data) 
        else:
            return None
        
    except Exception as e:  
        logger.info(f"未知错误: {str(e)}")  