import os  
import io  
import re  
import time
from PIL import Image  
from config import conf 
from common.log import logger

config = conf()  

# 定义卦名映射字典  
GUA_MAPPING = {  
    # 八个纯卦使用第一个字映射  
    "乾": "乾为天",  
    "坤": "坤为地",  
    "震": "震为雷",  
    "巽": "巽为风",  
    "坎": "坎为水",  
    "离": "离为火",  
    "艮": "艮为山",  
    "兑": "兑为泽",  
    
    # 其余卦使用前两个字映射  
    "天风": "天风姤",  
    "天山": "天山遁",  
    "天地": "天地否",  
    "天雷": "天雷无妄",  
    "天火": "天火同人",  
    "天水": "天水讼",  
    "天泽": "天泽履",  
    
    "地风": "地风升",  
    "地山": "地山谦",  
    "地天": "地天泰",  
    "地雷": "地雷复",  
    "地火": "地火明夷",  
    "地水": "地水师",  
    "地泽": "地泽临",  
    
    "雷风": "雷风恒",  
    "雷山": "雷山小过",  
    "雷天": "雷天大壮",  
    "雷地": "雷地豫",  
    "雷火": "雷火丰",  
    "雷水": "雷水解",  
    "雷泽": "雷泽归妹",  
    
    "风山": "风山渐",  
    "风天": "风天小畜",  
    "风地": "风地观",  
    "风雷": "风雷益",  
    "风火": "风火家人",  
    "风水": "风水涣",  
    "风泽": "风泽中孚",  
    
    "水风": "水风井",  
    "水山": "水山蹇",  
    "水天": "水天需",  
    "水地": "水地比",  
    "水雷": "水雷屯",  
    "水火": "水火既济",  
    "水泽": "水泽节",  
    
    "火风": "火风鼎",  
    "火山": "火山旅",  
    "火天": "火天大有",  
    "火地": "火地晋",  
    "火雷": "火雷噬嗑",  
    "火水": "火水未济",  
    "火泽": "火泽睽",  
    
    "山风": "山风蛊",  
    "山天": "山天大畜",  
    "山地": "山地剥",  
    "山雷": "山雷颐",  
    "山火": "山火贲",  
    "山水": "山水蒙",  
    "山泽": "山泽损",  
    
    "泽风": "泽风大过",  
    "泽山": "泽山咸",  
    "泽天": "泽天夬",  
    "泽地": "泽地萃",  
    "泽雷": "泽雷随",  
    "泽火": "泽火革",  
    "泽水": "泽水困"  
}  

def GuaTuRequest(query):
    # 定义占卜关键词列表
    divination_keywords = ['卦图']
    return any(keyword in query for keyword in divination_keywords)

def GuaTuReDailyRequest(query):
    # 定义占卜关键词列表
    divination_keywords = ['每日一卦']
    return any(keyword in query for keyword in divination_keywords)

def GuaTu(input_text):  
    """  
    根据输入文本读取对应的卦图  
    
    参数:  
    input_text (str): 包含卦图信息的文本，可以是数字、卦名或卦名前缀  
    
    返回:  
    bytes: 图片的二进制数据  
    """  
    try:  
        # 移除多余的空格并统一替换全角空格  
        input_text = input_text.replace('　', ' ').strip()  
        
        gua_dir = config.get("duan_yi_tian_ji_image_path")
        
        # 获取目录下所有文件  
        files = os.listdir(gua_dir)  
        
        # 移除输入中的"卦图"字样，并去除多余空格  
        input_text = input_text.replace('卦图', '').strip()  
        
        target_file = None  
        gua_name = None  
        
        # 尝试解析数字  
        number_match = re.search(r'\d+', input_text)  
        if number_match:  
            number = int(number_match.group())  
            if 1 <= number <= 64:  
                prefix = f"{number:02d}_"  
                for file in files:  
                    if file.startswith(prefix):  
                        target_file = file  
                        break  
        
        # 如果没找到文件，尝试通过卦名匹配  
        if not target_file:  
            # 移除所有空格  
            search_text = input_text.replace(' ', '')  
            
            # 先尝试作为纯卦（单字）查找  
            if len(search_text) >= 1 and search_text[0] in GUA_MAPPING:  
                gua_name = GUA_MAPPING[search_text[0]]  
            # 再尝试作为复卦（两字）查找  
            elif len(search_text) >= 2 and search_text[:2] in GUA_MAPPING:  
                gua_name = GUA_MAPPING[search_text[:2]]  
            
            if gua_name:  
                # 查找对应的文件  
                for file in files:  
                    # 从文件名中提取卦名部分（去掉编号和扩展名）  
                    file_gua_name = file.split('_')[1].replace('.png', '')  
                    if file_gua_name == gua_name:  
                        target_file = file  
                        break  
        
        if target_file is None:  
            raise FileNotFoundError(f"找不到与 '{input_text}' 匹配的卦图")  
            
        # 读取图片  
        image_path = os.path.join(gua_dir, target_file)  
        with Image.open(image_path) as img:  
            image_io = io.BytesIO()  
            img.save(image_io, format='PNG')  
            image_io.seek(0)  
            logger.info(f"成功找到并读取卦图：{target_file}")  
            return image_io  
            
    except Exception as e:  
        logger.info(f"错误：{str(e)}")  
        return None  

def GuaTuNum():  
    """  
    根据数字（1-64）读取对应的卦图  
    
    参数:  
    num (int): 卦序号，范围1-64  
    
    返回:  
    bytes: 图片的二进制数据，如果出错返回None  
    """  
    try:  
        # 获取当前时间戳（微秒级）  
        current_time = time.time()  
        # 取小数部分后的6位  
        microseconds = int(str(current_time).split('.')[1][:6])  
        # 映射到100-999范围  
        gen_random_num = microseconds % 64 + 1
            
        # 获取图片目录路径  
        gua_dir = config.get("duan_yi_tian_ji_image_path")  
        
        # 获取目录下所有文件  
        files = os.listdir(gua_dir)  
        
        # 构建文件名前缀（如：01_，02_，...，64_）  
        prefix = f"{gen_random_num:02d}_"  
        
        # 查找匹配的文件  
        target_file = None  
        for file in files:  
            if file.startswith(prefix):  
                target_file = file  
                break  
                
        if target_file is None:  
            raise FileNotFoundError(f"找不到序号为 {num} 的卦图")  
            
        # 读取图片  
        image_path = os.path.join(gua_dir, target_file)  
        with Image.open(image_path) as img:  
            image_io = io.BytesIO()  
            img.save(image_io, format='PNG')  
            image_io.seek(0)  
            logger.info(f"成功找到并读取卦图：{target_file}")  
            return image_io  
            
    except Exception as e:  
        logger.info(f"错误：{str(e)}")  
        return None  
        # 读取并返回新生成的图片  

# 测试新接口  
def test_GuaTuNum():  
    """  
    测试 GuaTuNum 函数  
    """  
    logger.info("=== 开始测试 GuaTuNum ===")  
    
    # 测试用例  
    test_cases = [  
        1,      # 第一卦  
        64,     # 最后一卦  
        32,     # 中间的卦  
        0,      # 错误：超出范围  
        65,     # 错误：超出范围  
        "1"     # 错误：类型错误  
    ]  
    
    for test in test_cases:  
        logger.info(f"\n测试输入: {test}")  
        result = GuaTuNum(test)  
        if result:  
            logger.info("成功读取卦图")  
        else:  
            logger.info("未能找到对应卦图")  
    
    logger.info("\n=== 测试完成 ===")  

if __name__ == "__main__":  
    # 可以同时测试两个函数  
    test_GuaTu()  
    test_GuaTuNum()