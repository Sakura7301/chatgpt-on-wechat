import os  
import io  
import pytz 
import re 
import emoji  
import time
from datetime import datetime, timedelta  
from lunar_python import Solar, Lunar  
from PIL import Image, ImageDraw, ImageFont
from XuanXue.MeiHuaYiShu.wuxing_calculator import WuXingCalculator
from zhdate import ZhDate   
from config import conf 
from common.log import logger

config = conf()  

def create_font():  
    """  
    创建字体对象  
    """  
    font_size = 28  
    # 中文字体路径  
    chinese_font_paths = [  
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  
        "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",  
    ]  
    
    # 加载中文字体  
    for font_path in chinese_font_paths:  
        if os.path.exists(font_path):  
            try:  
                return ImageFont.truetype(font_path, font_size)  
            except Exception as e:  
                logger.info(f"加载字体 {font_path} 失败: {e}")  
                continue  
    
    logger.info("警告：未能加载中文字体，将使用默认字体")  
    return ImageFont.load_default()  

def get_text_size(text, font):  
    """  
    获取文本尺寸  
    """  
    try:  
        bbox = font.getbbox(text)  
        return bbox[2] - bbox[0], bbox[3] - bbox[1]  
    except:  
        return font.getlength(text), font.size  

def auto_wrap_text(text, font, max_width):  
    """  
    自动换行文本  
    """  
    lines = []  
    for line in text.split('\n'):  
        if not line:  
            lines.append('')  
            continue  
            
        current_line = ''  
        for char in line:  
            test_line = current_line + char  
            width, _ = get_text_size(test_line, font)  
            
            if width <= max_width:  
                current_line = test_line  
            else:  
                lines.append(current_line)  
                current_line = char  
        
        if current_line:  
            lines.append(current_line)  
    
    return lines  

def SaveGuaLi(final_reply, query):  
    """  
    将文本转换为图片  
    """  
    try:  
        # 基本设置  
        margin = 40  
        padding = 20  
        line_spacing = 10  
        max_width = 500  
        min_height = 100  
        
        # 创建字体对象  
        font = create_font()  
        
        # 确保存储目录存在       
        save_dir = config.get("mei_hua_yi_shu_image_path") 
        os.makedirs(save_dir, exist_ok=True)  
        
        # 生成文件名  
        beijing_tz = pytz.timezone('Asia/Shanghai')  
        current_time = datetime.now(beijing_tz)  
        filename = f"{current_time.year}_{current_time.month}_{current_time.day}_{query}.png"  
        full_path = os.path.join(save_dir, filename)  
        
        # 处理文本，直接使用原始文本，不进行emoji转换  
        text = final_reply  
        
        # 计算文本区域的最大宽度  
        text_max_width = max_width - 2 * (margin + padding)  
        
        # 自动换行处理文本  
        lines = auto_wrap_text(text, font, text_max_width)  
        
        # 计算实际需要的图片尺寸  
        total_height = 0  
        max_line_width = 0  
        
        for line in lines:  
            if not line:  # 空行处理  
                total_height += font.size + line_spacing  
                continue  
            
            width, height = get_text_size(line, font)  
            total_height += height + line_spacing  
            max_line_width = max(max_line_width, width)  
        
        # 设置图片尺寸，确保最小尺寸  
        width = max(int(min(max_line_width + 2 * (margin + padding), max_width)), 300)  
        height = max(int(total_height + 2 * (margin + padding)), min_height)  
        
        # 创建图片  
        image = Image.new('RGB', (width, height), 'white')  
        draw = ImageDraw.Draw(image)  
        
        # 创建渐变背景  
        for y in range(height):  
            r = int(252 - (y / height) * 10)  
            g = int(251 - (y / height) * 10)  
            b = int(250 - (y / height) * 10)  
            for x in range(width):  
                image.putpixel((x, y), (r, g, b))  
        
        # 绘制文本  
        y = margin + padding  
        for line in lines:  
            if not line:  # 空行处理  
                y += font.size + line_spacing  
                continue  
                
            draw.text((margin + padding, y), line, font=font, fill=(0, 0, 0))  
            _, height = get_text_size(line, font)  
            y += height + line_spacing  
        
        # 确保边框坐标正确  
        x0 = margin  
        y0 = margin  
        x1 = width - margin  
        y1 = height - margin  
        
        # 只在边框坐标有效时绘制边框  
        if x1 > x0 and y1 > y0:  
            draw.rectangle(  
                [(x0, y0), (x1, y1)],  
                outline=(0, 0, 0),  
                width=2  
            )  
        
        # 保存图片  
        try:  
            image.save(full_path, quality=95)  
        except Exception as e:  
            logger.info(f"保存图片时出错: {e}")  
            image = image.convert('RGB')  
            image.save(full_path, quality=95)  

    except Exception as e:  
        logger.info(f"生成图片时出错: {e}")  
        raise  

def get_num_from_text(text):  
    """  
    处理输入文本，提取数字
    
    Args:  
        text (str): 输入文本  
        
    Returns:  
        tuple: (num, flag)  
            num (int): 提取的数字，如果没有数字则为0
    """  
    # 去除所有空格  
    text = text.replace(" ", "")  
    
    # 提取连续数字  
    num_match = re.search(r'\d+', text)  
    num = int(num_match.group()) if num_match else 0  

    return num 

def GetGuaShu(query):  
    """  
    提取用户输入中头部或尾部的三位数字和问题文本  
    
    Args:  
        query: 用户输入的字符串  
    
    Returns:  
        tuple: (数字, 问题文本, 是否使用随机数)   
    """  
    # 移除所有空格  
    query_no_space = ''.join(query.split())  
    
    # 是否使用随机数标志  
    gen_random_flag = False  
    number = None  
    
    # 匹配开头或结尾的三位数字（排除中间的三位数字）  
    # (?:^|[^\d])表示字符串开头或非数字字符  
    # (?=$|[^\d])表示字符串结尾或非数字字符  
    start_pattern = r'(?:^|[^\d])(\d{3})(?=$|[^\d])'  
    
    matches = re.finditer(start_pattern, query_no_space)  
    matches = list(matches)  
    
    if matches:  
        # 获取所有匹配结果  
        potential_numbers = []  
        for match in matches:  
            num = int(match.group(1))  
            # 检查数字范围  
            if 100 <= num <= 999:  
                # 检查是否在开头或结尾  
                start_pos = match.start(1)  
                end_pos = match.end(1)  
                
                # 判断是否在开头或结尾（允许最多一个符号的偏移）  
                is_at_start = start_pos <= 1  
                is_at_end = end_pos >= len(query_no_space) - 1  
                
                if is_at_start or is_at_end:  
                    potential_numbers.append(num)  
        
        if potential_numbers:  
            number = potential_numbers[0]  # 使用第一个有效的数字  
        else:  
            gen_random_flag = True  
    else:  
        gen_random_flag = True  
    
    if gen_random_flag:  
        # 获取当前时间戳（微秒级）生成随机数  
        current_time = time.time()  
        microseconds = int(str(current_time).split('.')[1][:6])  
        number = microseconds % 900 + 100  
    
    # 去除问题中的数字（只替换找到的那个三位数）  
    if number is not None:  
        question = re.sub(rf'\b{number}\b', '', query)  
    else:  
        question = query  
        
    return number, question.strip(), gen_random_flag


def FormatZhanBuReply(gen_random_num_str: str,   
                          question: str,   
                          number: str,   
                          result: dict,   
                          reply_content: dict) -> str:  
    """  
    格式化占卜结果回复  
    
    Args:  
        gen_random_num_str (str): 生成的随机数字符串  
        question (str): 用户的问题  
        number (str): 占卜数字  
        result (dict): 占卜结果字典，包含以下键：  
            - shichen_info: 时辰信息  
            - wang_shuai: 旺衰信息  
            - ben_gua: 本卦  
            - ben_gua_sheng_ke: 本卦生克  
            - ben_gua_ji_xiong: 本卦吉凶  
            - dong_yao: 动爻  
            - hu_gua: 互卦  
            - bian_gua: 变卦  
            - bian_gua_sheng_ke: 变卦生克  
            - bian_gua_ji_xiong: 变卦吉凶  
            - fang_wei: 方位  
            - ying_qi: 应期  
        reply_content (dict): 回复内容字典，包含：  
            - content: 解析内容  
    
    Returns:  
        str: 格式化后的占卜结果字符串  
    """  

    try:  
        # 验证必需的键是否存在  
        required_keys = [  
            'shichen_info', 'wang_shuai', 
            'ben_gua',  'ben_gua_sheng_ke', 
            'hu_gua', 
            'bian_gua', 'bian_gua_sheng_ke',
        ]  
        
        if not all(key in result for key in required_keys):  
            missing_keys = [key for key in required_keys if key not in result]  
            raise ValueError(f"结果字典缺少必需的键: {missing_keys}")  
            
        # 保持占卜结果模板  
        prompt = f"""{gen_random_num_str}占卜结果出来啦~😸🔮\n问题：{question}\n{result['shichen_info']}\n{result['gan_zhi_info']}\n{result['wang_shuai']}\n数字：{number}\n[主卦] {result['ben_gua']}({result['ben_gua_sheng_ke']})\n[互卦] {result['hu_gua']}\n[动爻] {result['dong_yao']}爻动\n[变卦] {result['bian_gua']}({result['bian_gua_sheng_ke']})\n解析：\n{reply_content['content']}\n(解读仅供参考哦，我们还是要活在当下嘛~🐾)"""
        
        return prompt  

    except Exception as e:  
        logger.error(f"获取占卜结果出错：{e}")  
        raise


def GenZhanBuCueWord(result: dict, question: str) -> str:  
    """  
    生成占卜解读的提示词，保持原有格式和换行  
    
    Args:  
        result (dict): 占卜结果字典，包含以下键：  
            - wang_shuai: 旺衰信息  
            - ben_gua: 本卦  
            - ben_gua_sheng_ke: 本卦生克  
            - ben_gua_ji_xiong: 本卦吉凶  
            - hu_gua: 互卦  
            - bian_gua: 变卦  
            - bian_gua_sheng_ke: 变卦生克  
            - bian_gua_ji_xiong: 变卦吉凶  
            - dong_yao: 动爻  
        question (str): 用户的问题  
    
    Returns:  
        str: 格式化后的提示词  
    """  
    try:  
        # 验证必需的键是否存在  
        required_keys = [  
            'wang_shuai', 
            'ben_gua', 'ben_gua_sheng_ke',   
            'hu_gua', 
            'bian_gua',  'bian_gua_sheng_ke',  
            'dong_yao'  
        ]  
        
        if not all(key in result for key in required_keys):  
            missing_keys = [key for key in required_keys if key not in result]  
            raise ValueError(f"结果字典缺少必需的键: {missing_keys}")  

        # 保持原有格式的提示词模板  
        prompt = f"""请使用梅花易数对"{question}"这个问题进行断卦。时间为{result['gan_zhi_info']}，五行旺衰为：{result['wang_shuai']}。主卦为{result['ben_gua']}，{result['hu_gua']}，{result['dong_yao']}爻动而变{result['bian_gua']}。请严格遵循《梅花易数》体系进行解卦，然后给出150字以内的简要解析。严格使用文字描述，不使用任何符号，禁止使用特殊符号和重复字符；"""
        
        return prompt  

    except Exception as e:  
        logger.error(f"生成占卜提示词时出错：{e}")  
        raise


def get_bagua_direction(upper_gua_num):  
    """  
    根据上卦数值返回后天八卦方位  
    
    Args:  
        upper_gua_num: 整数，范围1-8，表示上卦数值  
        
    Returns:  
        str: 方位说明  
        
    Example:  
        >>> get_bagua_direction(1)  
        '坎卦 - 正北'  
    """  
    # 建立卦数与卦象方位的对应关系  
    bagua_directions = {  
        1: ("乾卦", "西北"),
        2: ("兑卦", "正西"), 
        3: ("离卦", "正南"),  
        4: ("震卦", "正东"),  
        5: ("巽卦", "东南"),  
        6: ("坎卦", "正北"),  
        7: ("艮卦", "东北"), 
        8: ("坤卦", "西南")
    }  
    
    try:  
        # 检查输入是否在有效范围内  
        if upper_gua_num not in bagua_directions:  
            return f"错误：输入数值 {upper_gua_num} 无效，请输入正确的卦数(1-9)"  
        
        # 获取卦象和方位  
        gua, direction = bagua_directions[upper_gua_num]  
        return f"{direction}"  
        
    except Exception as e:  
        return f"发生错误：{str(e)}"  

def SuanGuaRquest(query):
    # 定义占卜关键词列表
    divination_keywords = ['算算', "算下", '占卜' ,'开卦', '卜卦', '算卦', '算一算', '算一下']
    return any(keyword in query for keyword in divination_keywords)


# 修改时辰计算方式  
def get_shichen(hour):  
    if hour == 23 or hour == 0:  
        shichen = 1  # 子时  
    elif hour >= 1 and hour < 3:  
        shichen = 2  # 丑时  
    elif hour >= 3 and hour < 5:  
        shichen = 3  # 寅时  
    elif hour >= 5 and hour < 7:  
        shichen = 4  # 卯时  
    elif hour >= 7 and hour < 9:  
        shichen = 5  # 辰时  
    elif hour >= 9 and hour < 11:  
        shichen = 6  # 巳时  
    elif hour >= 11 and hour < 13:  
        shichen = 7  # 午时  
    elif hour >= 13 and hour < 15:  
        shichen = 8  # 未时  
    elif hour >= 15 and hour < 17:  
        shichen = 9  # 申时  
    elif hour >= 17 and hour < 19:  
        shichen = 10  # 酉时  
    elif hour >= 19 and hour < 21:  
        shichen = 11  # 戌时  
    else:  # hour >= 21 and hour < 23  
        shichen = 12  # 亥时  
    
    return shichen   

def ChangeYao(bengua_lines, move_line):  
    biangua_lines = bengua_lines.copy()
    index = move_line - 1
    # 变动指定的爻  
    if biangua_lines[index] == 'yin':  
        biangua_lines[index] = 'yang'  
    elif biangua_lines[index] == 'yang':  
        biangua_lines[index] = 'yin'  
    
    return biangua_lines  

def GanZhi():  
    # 获取当前时间的干支  
    solar = Solar.fromDate(datetime.utcnow() + timedelta(hours=8))  
    lunar = solar.getLunar()  
    
    # 获取年月日时的干支  
    year_ganzhi = lunar.getYearInGanZhi()  # 年干支  
    month_ganzhi = lunar.getMonthInGanZhi()  # 月干支  
    day_ganzhi = lunar.getDayInGanZhi()  # 日干支  
    hour_ganzhi = lunar.getTimeInGanZhi()  # 时辰干支  
    
    return [year_ganzhi, month_ganzhi, day_ganzhi, hour_ganzhi]   

def GetNongLiMonth(input_str):  
    print(type(input_str))
    month = 1
    # 定义地支与月份的对应关系字典  
    branch_to_month = {  
        '寅': 1,  # 正月  
        '卯': 2,  # 二月  
        '辰': 3,  # 三月  
        '巳': 4,  # 四月  
        '午': 5,  # 五月  
        '未': 6,  # 六月  
        '申': 7,  # 七月  
        '酉': 8,  # 八月  
        '戌': 9,  # 九月  
        '亥': 10, # 十月  
        '子': 11, # 十一月  
        '丑': 12  # 十二月  
    }  
    
    # 检查输入是否为空  
    if not input_str:  
        print("Invalid Input: Empty string") 
        return month
    
    # 获取地支（如果输入是两个字符，取第二个；如果是一个字符，直接使用）  
    earthly_branch = input_str[-1]  # 取最后一个字符作为地支  
    
    # 检查提取的地支是否有效  
    if earthly_branch not in branch_to_month:  
        print("Invalid Earthly Branch")
        return month
    
    # 返回对应的月份  
    month = branch_to_month[earthly_branch] 
    return  month

def MeiHuaXinYi(value):  
    """  
    梅花易数卜卦函数。  
    输入：100到999的整数。  
    输出：包含本卦、互卦、变卦名称、动爻和时辰信息的字典。如果输入不在范围内，返回None。  
    """  
    if not isinstance(value, int):  
        raise ValueError("输入必须是整数。")  
    if value < 100 or value > 999:  
        return None  

    # 八卦映射  
    trigrams = {  
        1: {'name': '乾', 'lines': ['yang', 'yang', 'yang']},  
        2: {'name': '兑', 'lines': ['yang', 'yang', 'yin']},  
        3: {'name': '离', 'lines': ['yang', 'yin', 'yang']},  
        4: {'name': '震', 'lines': ['yang', 'yin', 'yin']},  
        5: {'name': '巽', 'lines': ['yin', 'yang', 'yang']},  
        6: {'name': '坎', 'lines': ['yin', 'yang', 'yin']},  
        7: {'name': '艮', 'lines': ['yin', 'yin', 'yang']},  
        8: {'name': '坤', 'lines': ['yin', 'yin', 'yin']}  
    }  

    # 六十四卦映射  
    hexagram_mapping = {  
        (1, 1): '乾为天', (1, 2): '天泽履', (1, 3): '天火同人', (1, 4): '天雷无妄',  
        (1, 5): '天风姤', (1, 6): '天水讼', (1, 7): '天山遁', (1, 8): '天地否',  
        (2, 1): '泽天夬', (2, 2): '兑为泽', (2, 3): '泽火革', (2, 4): '泽雷随',  
        (2, 5): '泽风大过', (2, 6): '泽水困', (2, 7): '泽山咸', (2, 8): '泽地萃',  
        (3, 1): '火天大有', (3, 2): '火泽睽', (3, 3): '离为火', (3, 4): '火雷噬嗑',  
        (3, 5): '火风鼎', (3, 6): '火水未济', (3, 7): '火山旅', (3, 8): '火地晋',  
        (4, 1): '雷天大壮', (4, 2): '雷泽归妹', (4, 3): '雷火丰', (4, 4): '震为雷',  
        (4, 5): '雷风恒', (4, 6): '雷水解', (4, 7): '雷山小过', (4, 8): '雷地豫',  
        (5, 1): '风天小畜', (5, 2): '风泽中孚', (5, 3): '风火家人', (5, 4): '风雷益',  
        (5, 5): '巽为风', (5, 6): '风水涣', (5, 7): '风山渐', (5, 8): '风地观',  
        (6, 1): '水天需', (6, 2): '水泽节', (6, 3): '水火既济', (6, 4): '水雷屯',  
        (6, 5): '水风井', (6, 6): '坎为水', (6, 7): '水山蹇', (6, 8): '水地比',  
        (7, 1): '山天大畜', (7, 2): '山泽损', (7, 3): '山火贲', (7, 4): '山雷颐',  
        (7, 5): '山风蛊', (7, 6): '山水蒙', (7, 7): '艮为山', (7, 8): '山地剥',  
        (8, 1): '地天泰', (8, 2): '地泽临', (8, 3): '地火明夷', (8, 4): '地雷复',  
        (8, 5): '地风升', (8, 6): '地水师', (8, 7): '地山谦', (8, 8): '坤为地'  
    }  

    # 1. 计算上卦数  
    hundreds_digit = value // 100  
    upper_num = hundreds_digit % 8  
    upper_num = upper_num if upper_num != 0 else 8  

    # 2. 计算下卦数  
    tens_digit = (value // 10) % 10  
    units_digit = value % 10  
    lower_sum = tens_digit + units_digit  
    lower_num = lower_sum % 8  
    lower_num = lower_num if lower_num != 0 else 8  

    # 3. 计算动爻数  
    digit_sum = hundreds_digit + tens_digit + units_digit  
    print(f"{hundreds_digit} + {tens_digit} + {units_digit} = {digit_sum}")

    # 获取当前时间  
    now = datetime.now()  

    hour = now.hour  

    # 定义时辰对应的值和名称  
    shichen_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]  
    shichen_names = {  
        1: '子时',  
        2: '丑时',  
        3: '寅时',  
        4: '卯时',  
        5: '辰时',  
        6: '巳时',  
        7: '午时',  
        8: '未时',  
        9: '申时',  
        10: '酉时',  
        11: '戌时',  
        12: '亥时'  
    }  

    # 获取时辰数
    shichen = get_shichen(hour)  
    shichen_name = shichen_names[shichen]  

    total = digit_sum + shichen  
    moving_line = total % 6  
    print(f"{total} = {digit_sum} + {shichen}")
    print(f"{moving_line} = {total} % 6 ")
    if moving_line == 0:
        moving_line = 6

    # 4. 得到本卦  
    try:  
        lower_trigram = trigrams[lower_num]['lines']  
        lower_name = trigrams[lower_num]['name']  
        upper_trigram = trigrams[upper_num]['lines']  
        upper_name = trigrams[upper_num]['name']  
    except KeyError:  
        raise ValueError("上卦数或下卦数无效。")  

    bengua_lines = lower_trigram + upper_trigram  # 自下而上六爻  
    bengua_name = hexagram_mapping.get((upper_num, lower_num), '未知卦')  

    # 5. 得到互卦  
    hugua_lines = bengua_lines[1:5]  
    hugua_lower_lines = hugua_lines[:3]  
    hugua_upper_lines = hugua_lines[1:]  

    def get_trigram_from_lines(lines):  
        for num, trigram in trigrams.items():  
            if trigram['lines'] == lines:  
                return num, trigram['name']  
        return None, '未知'  

    hugua_lower_num, hugua_lower_name = get_trigram_from_lines(hugua_lower_lines)  
    hugua_upper_num, hugua_upper_name = get_trigram_from_lines(hugua_upper_lines)  

    hugua_name_pro = hexagram_mapping.get((hugua_upper_num, hugua_lower_num), '未知卦')

    # 修改此处，互卦名称直接输出上卦和下卦名称  
    hugua_name = f"互见{hugua_upper_name}{hugua_lower_name}"  

    # 6. 得到变卦  
    biangua_lines = ChangeYao(bengua_lines, moving_line) 
    print("bengua_lines:", bengua_lines)
    print("biangua_lines:", biangua_lines)
    biangua_lower_lines = biangua_lines[:3]  
    print("biangua_lower_lines:", biangua_lower_lines)
    biangua_upper_lines = biangua_lines[3:]
    print("biangua_upper_lines:", biangua_upper_lines)  

    biangua_lower_num, biangua_lower_name = get_trigram_from_lines(biangua_lower_lines)  
    biangua_upper_num, biangua_upper_name = get_trigram_from_lines(biangua_upper_lines)  

    biangua_name = hexagram_mapping.get((biangua_upper_num, biangua_lower_num), '未知卦')  

    # 7. 获取动爻，六爻顺序为自下而上，索引为0表示初爻，动爻是 moving_line  
    dong_yao = ['初', '二', '三', '四', '五', '上'][moving_line - 1]  
    dong_yao_full = f"{dong_yao}"  

    logger.info(f"上卦数:{upper_num}   下卦数:{lower_sum}")
    logger.info(f"时  辰:{shichen_name}   时辰数:{shichen}")
    logger.info(f"动爻数:{moving_line}   动  爻:{dong_yao}")

    # 8. 获取时辰信息  
    datetime_str = f"{now.year}-{now.month}-{now.day} {now.hour}:{now.minute}:{now.second}"  

    # 整合信息，准备获取五行生克结果
    if 1 <= moving_line < 3: 
        # 动爻在下卦，上卦为体
        dong_yao_flag = 1
    else:
        # 动爻在上卦，下卦为体
        dong_yao_flag = 0

    # 获取干支
    gan_zhi = GanZhi()
    ganzhi_info = f"{gan_zhi[0]}年 {gan_zhi[1]}月 {gan_zhi[2]}日 {gan_zhi[3]}时"

    # 获取农历月份数
    nongli_month = GetNongLiMonth(gan_zhi[1])

    print("nongli_month = ", nongli_month)

    # 调用 WuXingCalculator 函数获取体用生克信息以及吉凶结果
    bengua_wuxing_result = WuXingCalculator(upper_num, lower_num, dong_yao_flag, nongli_month)
    biangua_wuxing_result = WuXingCalculator(biangua_upper_num, biangua_lower_num, dong_yao_flag, nongli_month)

    # # 计算应期
    # ying_qi = (upper_num + lower_num + shichen)

    # if moving_line > 3:
    #     fang_wei = get_bagua_direction(biangua_upper_num)
    # else :
    #     fang_wei = get_bagua_direction(biangua_lower_num)

    # 构造结果字典  
    result = {  
        "gan_zhi_info":ganzhi_info,
        "ben_gua": bengua_name,  
        "wang_shuai": bengua_wuxing_result['wang_shuai'],
        "ben_gua_sheng_ke":bengua_wuxing_result['sheng_ke'],
        # "ben_gua_ji_xiong":bengua_wuxing_result['ji_xiong'],
        # "fang_wei": fang_wei,
        "hu_gua": hugua_name,  
        "bian_gua": biangua_name,  
        "bian_gua_sheng_ke":biangua_wuxing_result['sheng_ke'],
        # "bian_gua_ji_xiong":biangua_wuxing_result['ji_xiong'],
        "dong_yao": dong_yao_full,  
        # "ying_qi": ying_qi,
        "shichen_info": datetime_str  
    }  

    return result  


def run():  
    num = 746  
    result = MeiHuaXinYi(num)  
    logger.info("报数：", num)  
    # logger.info(result)
    if result:  
        logger.info("时间", result["shichen_info"])  
        logger.info("旺衰：", result["wang_shuai"])
        logger.info("本卦：", result["ben_gua"])
        logger.info("方位：", result["fang_wei"])
        logger.info("互卦：", result["hu_gua"])  
        logger.info("变卦：", result["bian_gua"])
        logger.info("动爻：", result["dong_yao"]) 
    else:  
        logger.info("输入的数字不在指定范围内。")  


if __name__ == "__main__":  
    run()