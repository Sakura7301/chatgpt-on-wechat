from common.log import logger

# -*- coding: utf-8 -*-
"""
五行计算程序，包含WuXingCalculator函数和测试函数test_WuXingCalculator。
"""

# 定义八卦对应的五行
gua_wuxing_dict = {
    1: '金',  # 乾
    2: '金',  # 兑
    3: '火',  # 离
    4: '木',  # 震
    5: '木',  # 巽
    6: '水',  # 坎
    7: '土',  # 艮
    8: '土'   # 坤
}

# 定义五行的生克关系
sheng_dict = {
    '金': '水',
    '水': '木',
    '木': '火',
    '火': '土',
    '土': '金'
}
ke_dict = {
    '金': '木',
    '木': '土',
    '土': '水',
    '水': '火',
    '火': '金'
}

# 定义每个月令对应的五行旺相休囚死状态  
month_wuxing_state = {  
    # 当令者旺，令生者相，生令者休，克令者囚，令克者死。
    # 1月2月属木  
    1: {'木': '旺', '火': '相', '水': '休', '金': '囚', '土': '死'},  
    2: {'木': '旺', '火': '相', '水': '休', '金': '囚', '土': '死'},  
    # 3月属土  
    3: {'土': '旺', '金': '相', '火': '休', '木': '囚', '水': '死'},  
    # 4月5月属火  
    4: {'火': '旺', '土': '相', '木': '休', '水': '囚', '金': '死'},  
    5: {'火': '旺', '土': '相', '木': '休', '水': '囚', '金': '死'},  
    # 6月属土  
    6: {'土': '旺', '金': '相', '火': '休', '木': '囚', '水': '死'},  
    # 7月8月属金  
    7: {'金': '旺', '水': '相', '土': '休', '火': '囚', '木': '死'},  
    8: {'金': '旺', '水': '相', '土': '休', '火': '囚', '木': '死'},  
    # 9月属土  
    9: {'土': '旺', '金': '相', '火': '休', '木': '囚', '水': '死'},  
    # 10月11月属水  
    10: {'水': '旺', '木': '相', '金': '休', '土': '囚', '火': '死'},  
    11: {'水': '旺', '木': '相', '金': '休', '土': '囚', '火': '死'},  
    # 12月属土  
    12: {'土': '旺', '金': '相', '火': '休', '木': '囚', '水': '死'}  
}

# 月令对应的五行
month_wuxing_dict = {
    1: '木', 2: '木',          # 1月、2月
    3: '土',                   # 3月
    4: '火', 5: '火',          # 4月、5月
    6: '土',                   # 6月
    7: '金', 8: '金',          # 7月、8月
    9: '土',                   # 9月
    10: '水', 11: '水',        # 10月、11月
    12: '土'                   # 12月
}

# 旺相休囚死对应的气数变化比例
qi_change_dict = {
    '旺': 0.6,
    '相': 0.3,
    '休': 0.0,
    '囚': -0.3,
    '死': -0.6
}

# ANSI转义序列颜色代码  
class Colors:  
    YELLOW = '\033[93m'  
    GREEN = '\033[92m'  
    RED = '\033[91m'  
    BLUE = '\033[94m'  
    ENDC = '\033[0m'

class LogManager:  
    """日志管理类"""  
    _instance = None  
    _enabled = 0  # 默认不输出日志  

    def __new__(cls):  
        if cls._instance is None:  
            cls._instance = super(LogManager, cls).__new__(cls)  
        return cls._instance  

    @classmethod  
    def enable_log(cls):  
        """启用日志输出"""  
        cls._enabled = 1  

    @classmethod  
    def disable_log(cls):  
        """禁用日志输出"""  
        cls._enabled = 0  

    @classmethod  
    def log(cls, message, color=None):  
        """输出日志"""  
        if cls._enabled:  
            if color:  
                logger.info(f"{color}{message}{Colors.ENDC}")  
            else:  
                logger.info(message)  


# 创建全局日志管理器实例  
logger = LogManager()  

def WuXingCalculator(shanggua_num, xiagua_num, ti_flag, month):
    """
    五行计算函数。

    参数：
    - shanggua_num: 上卦数（1-8）
    - xiagua_num: 下卦数（1-8）
    - ti_flag: 体卦标志（0或1），0表示下卦为体卦，1表示上卦为体卦
    - month: 月令（1-12）

    返回：
    - dict，包含旺相休囚死、生克关系、吉凶判断
    """
    try:
        # 验证输入参数
        if shanggua_num not in range(1, 9) or xiagua_num not in range(1, 9):  
            logger.log("错误：上卦数和下卦数必须在1到8之间。")  
            return None  
        if ti_flag not in [0, 1]:  
            logger.log("错误：体卦标志必须为0或1。")  
            return None  
        if month not in range(1, 13):  
            logger.log("错误：月令必须在1到12之间。")  
            return None

        # 五行的旺相休囚死
        wuxing_sequence = ['木', '火', '土', '金', '水']

        month_wuxing = month_wuxing_dict[month]
        month_index = wuxing_sequence.index(month_wuxing)

        # 确定旺相休囚死
        wangxiangxiuqiusi_dict = month_wuxing_state[month]  

        # 获取体卦和用卦的五行
        ti_gua_num = shanggua_num if ti_flag == 1 else xiagua_num
        yong_gua_num = xiagua_num if ti_flag == 1 else shanggua_num

        ti_wuxing = gua_wuxing_dict[ti_gua_num]
        yong_wuxing = gua_wuxing_dict[yong_gua_num]

        logger.log(f"体卦五行：{ti_wuxing}")
        logger.log(f"用卦五行：{yong_wuxing}")

        # 初始化气数
        ti_qi = 10
        yong_qi = 10

        # 第一轮：按照旺相休囚死调整气数
        ti_state = wangxiangxiuqiusi_dict[ti_wuxing]
        yong_state = wangxiangxiuqiusi_dict[yong_wuxing]

        ti_qi += ti_qi * qi_change_dict[ti_state]
        yong_qi += yong_qi * qi_change_dict[yong_state]

        logger.log(f"第一轮修正：")
        logger.log(f"体卦气数: {ti_qi}")
        logger.log(f"用卦气数: {yong_qi}")

        # 保存初始气数供后续比较
        ti_initial_qi = ti_qi
        yong_initial_qi = yong_qi

        # 第二轮：按照生克关系调整气数
        if ti_wuxing == yong_wuxing:  
            relation = '体用比和'  
            # 比和情况下，气数不变  
        elif yong_wuxing == sheng_dict[ti_wuxing]:  
            # 体生用：检查用卦的五行是否是体卦五行所生  
            relation = '体生用'  
            transfer_qi = ti_qi * 0.25  
            ti_qi -= transfer_qi  
            yong_qi += transfer_qi  
        elif ti_wuxing == sheng_dict[yong_wuxing]:  
            # 用生体：检查体卦的五行是否是用卦五行所生  
            relation = '用生体'  
            transfer_qi = yong_qi * 0.25  
            yong_qi -= transfer_qi  
            ti_qi += transfer_qi  
        elif yong_wuxing == ke_dict[ti_wuxing]:  
            # 体克用：检查用卦的五行是否是体卦五行所克  
            relation = '体克用'  
            yong_qi *= 0.5  
        elif ti_wuxing == ke_dict[yong_wuxing]:  
            # 用克体：检查体卦的五行是否是用卦五行所克  
            relation = '用克体'  
            ti_qi *= 0.5  
        else:  
            relation = '无生克关系'  
            # 无生克关系，气数不变
        
        logger.log(f"第二轮修正：")
        logger.log(f"体卦气数: {ti_qi}")
        logger.log(f"用卦气数: {yong_qi}")

        # 判断吉凶
        if ti_wuxing == yong_wuxing:
            # 比和情况下，仅考虑体卦气数与初始值比较
            if ti_qi > 10:
                result = '小吉'
            else:
                result = '小凶'
        else:
            if relation in ['体生用', '体克用', '体用比和']:
                if ti_qi > yong_qi:
                    if yong_qi * 2 < ti_qi:
                        result = '大吉'
                    else:
                        result = '小吉'
                else:
                    if ti_qi * 2 < yong_qi:
                        result = '大凶'
                    else:
                        result = '小凶'
            else:
                # 用生体、用克体的情况
                if ti_qi > yong_qi:
                    if yong_qi * 2 < ti_qi:
                        result = '大吉'
                    else:
                        result = '小吉'
                else:
                    if ti_qi * 2 < yong_qi:
                        result = '大凶'
                    else:
                        result = '小凶'
        
        logger.log(f"比较完毕，结果为：{result}")

        # 构建旺相休囚死的字符串
        wangxiangxiuqiusi_str = '，'.join([
            f"{wx}{wangxiangxiuqiusi_dict[wx]}" for wx in wuxing_sequence
        ])

        return {
            'wang_shuai': wangxiangxiuqiusi_str,
            'sheng_ke': relation,
            'ji_xiong': result
        }

    except Exception as e:  
        logger.log(f"发生错误：{e}")  
        return None  

def test_WuXingCalculator():
    """
    测试函数，用于测试WuXingCalculator函数的正确性。
    """
    logger.log("开始测试WuXingCalculator函数...\n")

    test_cases = [
        {
            # 上卦乾金为体
            'input': (1, 6, 1, 10),
            'expected_relation': '体生用',
            'expected_result': '小凶',
            'description': '五行相生：金生水'
        },
        {
            # 下卦离火为体
            'input': (5, 3, 0, 4),
            'expected_relation': '用生体',
            'expected_result': '小吉',
            'description': '五行相生：木生火'
        },
        {
            # 上卦兑金为体
            'input': (2, 4, 1, 7),
            'expected_relation': '体克用',
            'expected_result': '大吉',
            'description': '五行相克：金克木'
        },
        {
            # 下卦离火为体
            'input': (6, 3, 0, 10),
            'expected_relation': '用克体',
            'expected_result': '大凶',
            'description': '五行相克：水克火'
        },
        {
            # 下卦坤土为体
            'input': (7, 8, 0, 3),
            'expected_relation': '体用比和',
            'expected_result': '小吉',
            'description': '五行相克：二者比和'
        },
        {
            # 异常用例1
            'input': (0, 3, 0, 10),
            'expected_relation': None,
            'expected_result': None,
            'description': '异常测试1'
        },
        {
            # 异常用例2
            'input': (6, 9, 0, 10),
            'expected_relation': None,
            'expected_result': None,
            'description': '异常测试2'
        },
        {
            # 异常用例3
            'input': (6, 3, 3, 10),
            'expected_relation': None,
            'expected_result': None,
            'description': '异常测试3'
        },
        {
            # 异常用例4
            'input': (6, 3, 0, 0),
            'expected_relation': None,
            'expected_result': None,
            'description': '异常测试4'
        },
        {
            # 异常用例5
            'input': (6, 3, 0, 13),
            'expected_relation': None,
            'expected_result': None,
            'description': '异常测试5'
        },
        {
            # 异常用例8
            'input': (0, 9, 3, 13),
            'expected_relation': None,
            'expected_result': None,
            'description': '异常测试8'
        }
    ]

    passed = 0
    total = len(test_cases)

    for idx, case in enumerate(test_cases):  
        logger.log(f"[测试用例{idx + 1}]", Colors.YELLOW)  
        logger.log(f"{case['description']}")  

        result = WuXingCalculator(*case['input'])  
        if result:  
            relation_pass = result['sheng_ke'] == case['expected_relation']  
            result_pass = result['ji_xiong'] == case['expected_result']  
            logger.log(f"旺衰：{result['wang_shuai']}")
            logger.log(f"输入：{case['input']}")  
            logger.log(f"预期结果：{case['expected_relation']}，{case['expected_result']}")
            logger.log(f"实际结果：{result['sheng_ke']}，{result['ji_xiong']}")  
            if relation_pass and result_pass:
                logger.log("测试结果: 通过✓\n", Colors.GREEN)
                passed += 1  
            else:  
                # logger.log(f"预期生克关系：{case['expected_relation']}，实际生克关系：{result['sheng_ke']}")  
                # logger.log(f"预期吉凶：{case['expected_result']}，实际吉凶：{result['ji_xiong']}")
                # 这一行打印成红色  
                logger.log("测试结果: 失败✗\n", Colors.RED)
        else:  
            if case['expected_relation'] is None and case['expected_result'] is None:  
                # 这一行打印成绿色
                logger.log("测试结果: 通过✓\n", Colors.GREEN) 
                passed += 1  
            else:  
                # 这一行打印成红色  
                logger.log("测试结果: 失败✗\n", Colors.RED) 

    # 这一行打印成蓝色
    logger.log(f"测试完成，通过率：{passed}/{total}\n", Colors.BLUE)

if __name__ == "__main__":
    logger.enable_log()
    test_WuXingCalculator()

