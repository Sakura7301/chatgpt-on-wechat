import random  
import time  

class CardDeck:  
    def __init__(self):  
        # 初始化49张牌  
        self.cards = list(range(1, 50))  
        self.shuffle()  
    
    # 洗牌
    def shuffle(self):  
        """  
        使用当前时间作为种子进行洗牌  
        """  
        # 使用当前时间戳的微秒部分作为种子  
        seed = int(time.time() * 1000000) % (2**32)  
        random.seed(seed)  
        random.shuffle(self.cards)  
        print(f"洗牌完成！使用种子：{seed}")  
    
    # 抽牌
    def draw_card(self, n):  
        """  
        抽取第n张牌  
        """  
        if not isinstance(n, int):  
            return "请输入整数！"  
        if n < 1 or n > 49:  
            return "请输入1-49之间的数字！"  
        return self.cards[n-1]  
    
    def show_all_cards(self):  
        """  
        显示当前牌的顺序（用于测试）  
        """  
        return self.cards  

def test_card_deck():  
    """  
    测试函数  
    """  
    print("=== 开始测试 ===")  
    
    # 创建卡牌实例  
    deck = CardDeck()  
    
    # 测试用例1：正常抽牌  
    print("\n测试1: 正常抽牌")  
    test_numbers = [1, 25, 49]  
    for n in test_numbers:  
        card = deck.draw_card(n)  
        print(f"抽取第{n}张牌：{card}")  
    
    # 测试用例2：错误输入  
    print("\n测试2: 错误输入")  
    invalid_inputs = [0, 50, -1, "abc"]  
    for n in invalid_inputs:  
        result = deck.draw_card(n)  
        print(f"输入{n}的结果：{result}")  
    
    # 测试用例3：连续洗牌  
    print("\n测试3: 连续洗牌效果")  
    print("初始顺序：", deck.cards[:5], "...")  
    time.sleep(1)  # 等待1秒确保不同的种子  
    deck.shuffle()  
    print("洗牌后顺序：", deck.cards[:5], "...")  
    
    print("\n=== 测试完成 ===")  

# 运行测试  
if __name__ == "__main__":  
    test_card_deck()  
    
    # 交互式测试  
    print("\n=== 开始交互式测试 ===")  
    deck = CardDeck()  
    while True:  
        try:  
            user_input = input("\n请输入要抽取第几张牌（1-49，输入q退出）：")  
            if user_input.lower() == 'q':  
                break  
            n = int(user_input)  
            result = deck.draw_card(n)  
            print(f"第{n}张牌是：{result}")  
        except ValueError:  
            print("请输入有效的数字！")