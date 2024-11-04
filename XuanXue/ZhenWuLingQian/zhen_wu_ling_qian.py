import os   
import io  
import time
from config import conf 
from common.log import logger
from datetime import datetime


config = conf()  

def get_local_image(number):  
    """  
    在./ZhenWuLingQian目录下查找指定数字前缀的图片  
    支持1-100的数字，自动处理补零  
    返回完整的文件路径或None  
    """  
    if not isinstance(number, int) or number < 1 or number > 59:  
        logger.info(f"数字必须在1-100之间，当前数字：{number}")  
        return None  
        
    # 获取ZhenWuLingQian目录的完整路径  
    target_dir = config.get("zhen_wu_ling_qian_image_path") 
    
    # 确保目录存在  
    if not os.path.exists(target_dir):  
        logger.info(f"目录不存在：{target_dir}")  
        return None  
    
    # 生成可能的文件名模式  
    patterns = [  
        f"{number:02d}_",     # 补零，如："01_"  
        f"{number}_"          # 不补零，如："1_"  
    ]  
    
    # 在目录中查找匹配的文件  
    for filename in os.listdir(target_dir):  
        if filename.endswith('.png'):  
            for pattern in patterns:  
                if filename.startswith(pattern):  
                    full_path = os.path.join(target_dir, filename)  
                    logger.info(f"找到匹配图片：{filename}")  
                    return full_path  
                    
    logger.info(f"未找到数字{number}对应的签文图片")  
    return None  

def ZhenWuLingQian():  
    """  
    读取本地图片并返回BytesIO对象  
    """  
    # 随机抽签
    # 获取当前时间戳（微秒级）  
    current_time = time.time()  
    # 取小数部分后的6位  
    microseconds = int(str(current_time).split('.')[1][:6])  
    # 映射到1-49范围  
    gen_random_num = microseconds % 49 + 1
    # 获取图片路径
    image_path = get_local_image(gen_random_num)  
    
    if image_path and os.path.exists(image_path):  
        try:  
            # 读取图片内容并创建BytesIO对象  
            with open(image_path, 'rb') as f:  
                image_content = f.read()  
            image_io = io.BytesIO(image_content)  
            logger.info(f"成功读取图片：{image_path}")  
            return image_io  
        except Exception as e:  
            logger.info(f"读取图片失败：{e}")  
            return None  
    return None 


def ZhenWuLingQianNum(number):  
    """  
    读取本地图片并返回BytesIO对象  
    """  
    # 打乱顺序
    glob_deck.shuffle()
    # 抽签
    card_num = glob_deck.draw_card(number)
    # 获取图片路径
    image_path = get_local_image(card_num)  
    
    if image_path and os.path.exists(image_path):  
        try:  
            # 读取图片内容并创建BytesIO对象  
            with open(image_path, 'rb') as f:  
                image_content = f.read()  
            image_io = io.BytesIO(image_content)  
            logger.info(f"成功读取图片：{image_path}")  
            return image_io  
        except Exception as e:  
            logger.info(f"读取图片失败：{e}")  
            return None  
    return None 

# 测试代码  
if __name__ == "__main__":  
    test_numbers = [1, 6, 14, 99, 0, 100]  
    for num in test_numbers:  
        logger.info(f"\n测试数字: {num}")  
        result = ZhenWuLingQian(num)  
        if result:  
            logger.info(f"成功获取图片内容，大小：{result.getbuffer().nbytes} 字节")