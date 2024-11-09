import os  
import random  
import time  
from common.log import logger
from PIL import Image, ImageDraw  

# 定义塔罗牌目录  
CARDS_DIR = '/home/alex/Desktop/chatgpt-on-wechat/image/TarotCards'  
OUTPUT_DIR = '/home/alex/Desktop/chatgpt-on-wechat/image/Tarot' 
 

# 洗牌函数  
def shuffle_cards():  
    """随机洗牌并返回卡牌列表"""  
    logger.info("开始洗牌...")  
    card_files = os.listdir(CARDS_DIR)  
    random.shuffle(card_files)  
    logger.info("洗牌完成！")  
    return card_files  

# 生成抽牌标志函数  
def generate_draw_flag():  
    """生成随机的抽牌标志 (0: 逆位, 1: 正位)"""  
    random.seed(time.time())
    return random.randint(0, 1)  

# 获取牌名函数  
def get_card_name(card_file):  
    """根据文件名获取塔罗牌名称"""  
    return card_file.split('_', 1)[1].replace('.jpg', '')  

def TarotSingleCardRequest(query):
    # 定义占卜关键词列表
    divination_keywords = ['抽牌', '抽一张牌']
    return any(keyword in query for keyword in divination_keywords)

def TarotThreeCardsRequest(query):
    # 定义占卜关键词列表
    divination_keywords = ['三牌阵','三张牌阵','过去-现在-未来阵']
    return any(keyword in query for keyword in divination_keywords)

def TarotCrossCardsRequest(query):
    # 定义占卜关键词列表
    divination_keywords = ['凯尔特十字','凯尔特十字牌阵','十字牌阵','十字阵']
    return any(keyword in query for keyword in divination_keywords)

# 单张塔罗牌抽取函数  
def TarotSingleCard(m=None):  
    """抽取单张塔罗牌，支持指定牌位"""  
    card_files = shuffle_cards()  
    draw_flag = generate_draw_flag()  # 生成抽牌标志  

    output_filename = "Single"

    # 如果指定了牌位  
    if m is not None:  
        if 0 <= m < len(card_files):  
            selected_card = card_files[m]  
            card_name = get_card_name(selected_card)  
            logger.info(f"抽取的牌为: {card_name} (标志: {draw_flag})")  
        else:  
            logger.info("参数m超出范围，使用随机数抽取牌")  
            selected_card = card_files[random.randint(0, len(card_files) - 1)]  
            card_name = get_card_name(selected_card)  
            logger.info(f"抽取的牌为: {card_name} (标志: {draw_flag})")  
    else:  
        selected_card = card_files[random.randint(0, len(card_files) - 1)]  
        card_name = get_card_name(selected_card)  
        logger.info(f"抽取的牌为: {card_name} (标志: {draw_flag})")  
        

    # 根据抽牌标志处理图像  
    if draw_flag == 0:  # 逆位处理  
        logger.info(f"抽到：{card_name}(逆位)")  
        output_filename += f"_{card_name}逆"
    else:  
        logger.info(f"抽到：{card_name}(正位)")  
        output_filename += f"_{card_name}正"
    
    # 生成路径
    output_filename += ".png"  
    output_path = os.path.join(OUTPUT_DIR, output_filename) 

    # 检查文件是否已存在  
    if os.path.exists(output_path):  
        #存在就直接返回
        logger.info(f"找到已存在的图片：{output_path}") 
    else:

        card_path = os.path.join(CARDS_DIR, selected_card)  
        card_image = Image.open(card_path).convert("RGBA")  

        if draw_flag == 0:
            # 逆位处理  
            card_image = card_image.transpose(Image.FLIP_TOP_BOTTOM)  # 反转图像 

        # 压缩图像  
        card_image = card_image.resize((card_image.width//3, card_image.height//3), Image.LANCZOS)

        # 保存合成的图片 
        card_image.save(output_path)  

    return open(output_path, 'rb')

# 三张塔罗牌抽取函数  
def TarotThreeCards(query=None):  
    """抽取三张塔罗牌并生成合成图像"""  
    # 洗牌
    card_files = shuffle_cards()  
    selected_cards = []  # 用于保存选中的卡牌信息  
    output_filename = "Three"

    for i in range(3):  
        draw_flag = generate_draw_flag()  # 生成抽牌标志  
        #按顺序抽
        selected_card = card_files[i]  
        card_name = get_card_name(selected_card)  
        selected_cards.append((selected_card, card_name, draw_flag))  # 保存完整信息  
        
        if draw_flag == 0:  # 逆位处理  
            logger.info(f"抽到：{card_name}(逆位)")  
            output_filename += f"_{card_name}逆"
        else:  
            logger.info(f"抽到：{card_name}(正位)")  
            output_filename += f"_{card_name}正"

    logger.info("抽取的三张牌为: " + ", ".join([f"{name}({'正位' if flag == 1 else '逆位'})" for _, name, flag in selected_cards]))  

    # 生成路径
    output_filename += ".png"  
    output_path = os.path.join(OUTPUT_DIR, output_filename) 

    # 检查文件是否已存在  
    if os.path.exists(output_path):  
        #存在就直接返回
        logger.info(f"找到已存在的图片：{output_path}") 
    else:
        # 生成合成图像逻辑  
        card_images = []  
        
        for selected_card, card_name, draw_flag in selected_cards:  
            card_path = os.path.join(CARDS_DIR, selected_card)  
            card_image = Image.open(card_path).convert("RGBA")  
            
            # 根据抽牌标志处理图像  
            if draw_flag == 0:  # 逆位处理  
                card_image = card_image.transpose(Image.FLIP_TOP_BOTTOM)  # 反转图像  
            
            card_images.append(card_image)  # 添加处理后的图像  

        total_width = sum(img.width for img in card_images) + 100  # 3张牌的宽度加上间隔  
        total_height = max(img.height for img in card_images) + 20  # 适当增加高度  
        background_color = (200, 220, 255)  # 背景颜色  
        new_image = Image.new('RGBA', (total_width, total_height), background_color)  

        draw = ImageDraw.Draw(new_image)  
        border_color = (0, 0, 0)  # 边框颜色  
        border_thickness = 3  

        # 将三张牌放入新图片  
        x_offset = 20  
        for img in card_images:  
            new_image.paste(img, (x_offset, 10))  
            draw.rectangle([x_offset, 10, x_offset + img.width, 10 + img.height], outline=border_color, width=border_thickness)  
            x_offset += img.width + 30  

        # 压缩图像  
        new_image = new_image.resize((total_width//5, total_height//5), Image.LANCZOS)

        # 保存合成的图片  
        new_image.save(output_path)  

        logger.info(f"合成的三张牌图片已保存: {output_path}")  
    return open(output_path, 'rb')  

# 十字塔罗牌抽取函数  
def TarotCrossCards(query=None):  
    """抽取十张塔罗牌并生成合成图像"""  
    # 洗牌
    card_files = shuffle_cards()  
    selected_cards = []  

    output_filename = "Cross"

    for i in range(5):  
        draw_flag = generate_draw_flag()  # 生成抽牌标志  
        #按顺序抽
        selected_card = card_files[i]  
        card_name = get_card_name(selected_card)  
        selected_cards.append((selected_card, card_name, draw_flag))  # 保存完整信息   
        
        if draw_flag == 0:  # 逆位处理  
            logger.info(f"抽到：{card_name}(逆位)")  
            output_filename += f"_{card_name}逆"
        else:  
            logger.info(f"抽到：{card_name}(正位)")  
            output_filename += f"_{card_name}正"

    logger.info("抽取的五张牌为: " + ", ".join([f"{name}({'正位' if flag == 1 else '逆位'})" for _, name, flag in selected_cards]))  

    # 生成路径
    output_filename += ".png"  
    output_path = os.path.join(OUTPUT_DIR, output_filename) 

    # 检查文件是否已存在  
    if os.path.exists(output_path):  
        #存在就直接返回
        logger.info(f"找到已存在的图片：{output_path}") 
    else:
    
        card_images = []  
        
        for selected_card, card_name, draw_flag in selected_cards:  
            card_path = os.path.join(CARDS_DIR, selected_card)  
            card_image = Image.open(card_path).convert("RGBA")  
            
            # 根据抽牌标志处理图像  
            if draw_flag == 0:  # 逆位处理  
                card_image = card_image.transpose(Image.FLIP_TOP_BOTTOM)  # 反转图像  
                
            card_images.append(card_image)  # 添加处理后的图像  
        
        card_width, card_height = card_images[0].size  
        total_width = card_width * 3 + 120  
        total_height = card_height * 3 + 120  

        # 创建新图像  
        background_color = (200, 220, 255)  
        new_image = Image.new('RGBA', (total_width, total_height), background_color)  
        draw = ImageDraw.Draw(new_image)  
        
        border_color = (0, 0, 0)  
        border_thickness = 3  

        center_x = (total_width - card_width) // 2  
        center_y = (total_height - card_height) // 2  

        # 中心
        new_image.paste(card_images[0], (center_x, center_y))  
        draw.rectangle([center_x, center_y, center_x + card_width, center_y + card_height], outline=border_color, width=border_thickness)  

        # 上方
        new_image.paste(card_images[1], (center_x, center_y - card_height - 30))  
        draw.rectangle([center_x, center_y - card_height - 30, center_x + card_width, center_y - 30], outline=border_color, width=border_thickness)  

        # 下方
        new_image.paste(card_images[2], (center_x, center_y + card_height + 30))  
        draw.rectangle([center_x, center_y + card_height + 30, center_x + card_width, center_y + card_height * 2 + 30], outline=border_color, width=border_thickness)  


        # 左侧
        new_image.paste(card_images[3], (center_x - card_width - 30, center_y))  
        draw.rectangle([center_x - card_width - 30, center_y, center_x - 30, center_y + card_height], outline=border_color, width=border_thickness)  

        # 右侧
        new_image.paste(card_images[4], (center_x + card_width + 30, center_y))  
        draw.rectangle([center_x + card_width + 30, center_y, center_x + card_width * 2 + 30, center_y + card_height], outline=border_color, width=border_thickness)  

        # 压缩图像  
        new_image = new_image.resize((total_width//5, total_height//5), Image.LANCZOS)

        # 保存合成的图片  
        new_image.save(output_path)  

        logger.info(f"合成的五张牌图片已保存: {output_path}")  
    return open(output_path, 'rb')  

# 示例程序  
if __name__ == "__main__":  
    random.seed(time.time())  # 使用时间作为随机数种子  
    # # 测试单张牌抽取  
    # logger.info("单张牌抽取示例:")  
    for i in range(10):
        single_card_io = TarotSingleCard()  

    # # 测试三张牌抽取  
    # logger.info("\n三张牌抽取示例:")  
    for i in range(10):
        three_cards_io = TarotThreeCards()  

    # # 测试十字牌抽取  
    # logger.info("\n十字牌抽取示例:")  
    for i in range(50):
        cross_cards_io = TarotCrossCards()