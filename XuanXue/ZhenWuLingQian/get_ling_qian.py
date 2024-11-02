import os   
import io  

def get_local_image(number):  
    """  
    在./ZhenWuLingQian目录下查找指定数字前缀的图片  
    支持1-100的数字，自动处理补零  
    返回完整的文件路径或None  
    """  
    if not isinstance(number, int) or number < 1 or number > 59:  
        print(f"数字必须在1-100之间，当前数字：{number}")  
        return None  
        
    # 获取ZhenWuLingQian目录的完整路径  
    current_dir = os.path.dirname(os.path.abspath(__file__))  
    target_dir = os.path.join(current_dir, "/home/alex/chatgpt-on-wechat/XuanXue/ZhenWuLingQian/image")  
    
    # 确保目录存在  
    if not os.path.exists(target_dir):  
        print(f"目录不存在：{target_dir}")  
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
                    print(f"找到匹配图片：{filename}")  
                    return full_path  
                    
    print(f"未找到数字{number}对应的签文图片")  
    return None  

def ZhenWuLingQian(number):  
    """  
    读取本地图片并返回BytesIO对象  
    """  
    image_path = get_local_image(number)  
    
    if image_path and os.path.exists(image_path):  
        try:  
            # 读取图片内容并创建BytesIO对象  
            with open(image_path, 'rb') as f:  
                image_content = f.read()  
            image_io = io.BytesIO(image_content)  
            print(f"成功读取图片：{image_path}")  
            return image_io  
        except Exception as e:  
            print(f"读取图片失败：{e}")  
            return None  
    return None   

# 测试代码  
if __name__ == "__main__":  
    test_numbers = [1, 6, 14, 99, 0, 100]  
    for num in test_numbers:  
        print(f"\n测试数字: {num}")  
        result = ZhenWuLingQian(num)  
        if result:  
            print(f"成功获取图片内容，大小：{result.getbuffer().nbytes} 字节")