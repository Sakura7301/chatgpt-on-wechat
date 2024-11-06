from bot.session_manager import Session  
from common.log import logger  


class ZhipuAISession(Session):
    def __init__(self, session_id, system_prompt=None, model="glm-4"):
        """  
        初始化会话  
        :param session_id: 会话ID  
        :param system_prompt: 系统提示语  
        :param model: 模型名称  
        :param max_tokens: 最大token数  
        """  
        super().__init__(session_id, system_prompt)
        self.model = model
        self.reset()

    def clear_messages(self):  
        """清理所有历史消息，仅保留system prompt"""  
        self.messages = []  
        self.messages.append({"role": "system", "content": self.system_prompt})  

    def reset(self):  
        """重置会话状态"""  
        super().reset()  
        self.clear_messages()  

    def discard_exceeding(self, max_tokens=None, cur_tokens=None):  
        """  
        处理超出token限制的情况  
        :param max_tokens: 最大token数  
        :param cur_tokens: 当前token数  
        :return: 处理后的token数  
        """  
        if max_tokens is None:  
            max_tokens = self.max_tokens  

        precise = True  
        try:  
            cur_tokens = self.calc_tokens()  
        except Exception as e:  
            precise = False  
            if cur_tokens is None:  
                raise e  
            logger.debug("Exception when counting tokens precisely for query: {}".format(e))  

        # 如果消息总长度超过限制  
        if cur_tokens > max_tokens:  
            # 如果消息数量大于2，逐个删除最早的消息  
            while cur_tokens > max_tokens and len(self.messages) > 2:  
                self.messages.pop(1)  # 保留system消息，删除最早的对话消息  
                if precise:  
                    cur_tokens = self.calc_tokens()  
                else:  
                    cur_tokens -= max_tokens  

            # 如果还是超过限制，且只剩下2条消息  
            if cur_tokens > max_tokens and len(self.messages) == 2:  
                if self.messages[1]["role"] == "assistant":  
                    self.messages.pop(1)  
                    cur_tokens = self.calc_tokens() if precise else cur_tokens - max_tokens  
                elif self.messages[1]["role"] == "user":  
                    logger.warn("user message exceed max_tokens. total_tokens={}".format(cur_tokens))  
                    # 强制清理所有消息  
                    self.clear_messages()  
                    cur_tokens = self.calc_tokens()  

        return cur_tokens  

    def calc_tokens(self):  
        """计算当前消息的token数量"""  
        return num_tokens_from_messages(self.messages, self.model)  

    def add_message(self, message):  
        """  
        添加新消息，并检查是否超出限制  
        :param message: 要添加的消息  
        """  
        self.messages.append(message)  
        cur_tokens = self.calc_tokens()  
        if cur_tokens > self.max_tokens:  
            self.discard_exceeding()  


def num_tokens_from_messages(messages, model):  
    """  
    计算消息列表的总token数  
    :param messages: 消息列表  
    :param model: 模型名称  
    :return: token总数  
    """  
    tokens = 0  
    for msg in messages:  
        tokens += len(msg["content"])  
    return tokens