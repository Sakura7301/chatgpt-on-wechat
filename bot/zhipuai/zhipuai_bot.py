# encoding:utf-8

import time
import re
import os  
import openai
import openai.error


from datetime import datetime
from bot.bot import Bot
from bot.zhipuai.zhipu_ai_session import ZhipuAISession
from bot.zhipuai.zhipu_ai_image import ZhipuAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
from zhipuai import ZhipuAI

from XuanXue.MeiHuaYiShu.meihuaxinyi import MeiHuaXinYi
from XuanXue.MeiHuaYiShu.meihuaxinyi import text_to_image
from XuanXue.MeiHuaYiShu.meihuaxinyi import extract_number_and_question
from XuanXue.ZhenWuLingQian.get_ling_qian import ZhenWuLingQian
from XuanXue.ZhenWuLingQian.rush_card import CardDeck
from XuanXue.SanMingZhan.san_ming_zhan import SanMingJiuGong


# 创建全局card deck实例
glob_deck = CardDeck()


# ZhipuAI对话模型API
class ZHIPUAIBot(Bot, ZhipuAIImage):
    def __init__(self):
        super().__init__()
        self.sessions = SessionManager(ZhipuAISession, model=conf().get("model") or "ZHIPU_AI")
        self.args = {
            "model": conf().get("model") or "glm-4",  # 对话模型的名称
            "temperature": conf().get("temperature", 0.9),  # 值在(0,1)之间(智谱AI 的温度不能取 0 或者 1)
            "top_p": conf().get("top_p", 0.7),  # 值在(0,1)之间(智谱AI 的 top_p 不能取 0 或者 1)
        }
        self.client = ZhipuAI(api_key=conf().get("zhipu_ai_api_key"))

    def reply(self, query, context=None):
        # 定义占卜关键词列表
        divination_keywords = ['算算', '占卜', '一卦','开卦','卜卦', '算卦', '求卦', '测算', '算一下']

        # 判断是否为文本消息
        if context.type == ContextType.TEXT:
            logger.info("[ZHIPU_AI] query={}".format(query))

            session_id = context["session_id"]
            reply = None
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"])
            if query in clear_memory_commands:
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.INFO, "记忆已清除")

            elif query == "#清除所有":
                self.sessions.clear_all_session()
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")

            elif query == "#更新配置":
                load_config()
                reply = Reply(ReplyType.INFO, "配置已更新")
                return reply

            # 判断用户是否表达了占卜的需求
            if any(keyword in query for keyword in divination_keywords):
                match_result = extract_number_and_question(query)
                if match_result[0] is None:
                    # 获取当前时间戳（微秒级）  
                    current_time = time.time()  
                    # 取小数部分后的6位  
                    microseconds = int(str(current_time).split('.')[1][:6])  
                    # 映射到100-999范围  
                    gen_random_num = microseconds % 900 + 100
                    gen_random_num_str = f"卜卦要准确提供3个数字哦，不然会影响准确率哒,下次别忘咯~\n这次我就先用随机数{gen_random_num}帮你起卦叭~\n"
                    number = gen_random_num
                else:
                    gen_random_num_str = ""
                    number = match_result[0]

                # 用户的问题为除数字外的部分
                user_question = match_result[1]

                # 调用 MeiHuaXinYi 函数获取结果
                result = MeiHuaXinYi(number)
                if result:
                    prompt = f"""根据现在的月份，月令旺衰情况是：{result['wang_shuai']}；我的卦象是：{result['ben_gua']} {result['ben_gua_sheng_ke']} {result['ben_gua_ji_xiong']} 、{result['hu_gua']}、{result['bian_gua']}  {result['bian_gua_sheng_ke']} {result['bian_gua_ji_xiong']}，动爻是{result['dong_yao']}；在梅花易数中，主卦代表事情的开始，互卦代表事情的发展过程，变卦代表事情的结果。我想要占卜的问题是{user_question}；我需要你结合客户的问题和我提供给你的卦象、生克情况，吉凶，同时参考易经中对卦象的描述，做一个简洁明了且易于理解的解读并回复给我。记住，不要复述我给你的卦象，直接用易于理解的语言描述占卜的结果即可，不要长篇大论，同时，可以给一些合理的建议，100个汉字以内即可。最后，你需要说明，本卦对应爻发动之后的爻辞"""

                    session = self.sessions.session_query(prompt, session_id)
                    logger.debug("[ZHIPU_AI] session messages={}".format(session.messages))

                    # 调用 reply_text 获取 AI 回复
                    reply_content = self.reply_text(session)
                    logger.debug(
                        "[ZHIPU_AI] session_id={}, reply_content={}, completion_tokens={}".format(
                            session_id,
                            reply_content["content"],
                            reply_content["completion_tokens"],
                        )
                    )

                    if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                        reply = Reply(ReplyType.ERROR, reply_content["content"])
                    elif reply_content["completion_tokens"] > 0:
                        # 按照指定格式回复用户
                        final_reply = f"""{gen_random_num_str}占卜结果出来啦~😸🔮\n问题：{user_question}\n数字：{number}\n时间：{result['shichen_info']}\n占卜结果:\n旺衰：{result['wang_shuai']}\n[主卦] {result['ben_gua']}   {result['ben_gua_sheng_ke']}   {result['ben_gua_ji_xiong']}\n{result['dong_yao']}爻动 {result['hu_gua']}\n[变卦] {result['bian_gua']}   {result['bian_gua_sheng_ke']}   {result['bian_gua_ji_xiong']}\n方位：{result['fang_wei']}  应期：{result['ying_qi']}\n解析：\n{reply_content['content']}\n(解读仅供参考哦，我们还是要活在当下嘛~🐾)"""
                        self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                        reply = Reply(ReplyType.TEXT, final_reply)
                        # 保存卦例
                        text_to_image(final_reply, user_question)
                    else:
                        reply = Reply(ReplyType.ERROR, reply_content["content"])
                        logger.debug("[ZHIPU_AI] reply {} used 0 tokens.".format(reply_content))
                    return reply
                else:
                    # MeiHuaXinYi 函数返回 None，说明数字不在范围内
                    reply = Reply(ReplyType.ERROR, "输入的数字不在指定范围内，请提供一个介于100到999之间的数字。")
                    return reply
            elif "抽签" == query: 
                # 进入抽签逻辑
                try:  
                    # 随机抽签
                    # 获取当前时间戳（微秒级）  
                    current_time = time.time()  
                    # 取小数部分后的6位  
                    microseconds = int(str(current_time).split('.')[1][:6])  
                    # 映射到100-999范围  
                    gen_random_num = microseconds % 49 + 1
                    gen_random_num_str = f"\n"
                    number = gen_random_num

                    # 打乱顺序
                    glob_deck.shuffle()
                    card_num = glob_deck.draw_card(number)

                    # 获取BytesIO对象而不是路径  
                    image_io = ZhenWuLingQian(card_num)  
                    if image_io:  
                        # 直接传入BytesIO对象  
                        return Reply(ReplyType.IMAGE, image_io)  
                    else:  
                        return Reply(ReplyType.TEXT, "未找到指定灵签🐾") 
                except Exception as e:  
                    return Reply(ReplyType.TEXT, f"发送灵签失败：{str(e)}") 
            elif "解签" == query:
                return Reply(ReplyType.TEXT, "签文都给你啦😾！你自己看看嘛~🐾") 
            elif "三命占" == query:
                pai_pan_result = SanMingJiuGong()
                if pai_pan_result:
                    return Reply(ReplyType.IMAGE, pai_pan_result) 
                else:
                    return Reply(ReplyType.TEXT, "排盘失败！") 
            else:
                # 用户无特殊需求，正常调用智谱AI回复
                session = self.sessions.session_query(query, session_id)
                reply_content = self.reply_text(session)
                logger.debug(
                    "[ZHIPU_AI] session_id={}, reply_content={}, completion_tokens={}".format(
                        session_id,
                        reply_content["content"],
                        reply_content["completion_tokens"],
                    )
                )
                if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                    reply = Reply(ReplyType.ERROR, reply_content["content"])
                elif reply_content["completion_tokens"] > 0:
                    self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                    reply = Reply(ReplyType.TEXT, reply_content["content"])
                else:
                    reply = Reply(ReplyType.ERROR, reply_content["content"])
                    logger.debug("[ZHIPU_AI] reply {} used 0 tokens.".format(reply_content))
                return reply

        elif context.type == ContextType.IMAGE_CREATE:
            ok, retstring = self.create_img(query, 0)
            reply = None
            if ok:
                reply = Reply(ReplyType.IMAGE_URL, retstring)
            else:
                reply = Reply(ReplyType.ERROR, retstring)
            return reply

        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, session: ZhipuAISession, api_key=None, args=None, retry_count=0) -> dict:
        """
        调用智谱AI的 ChatCompletion 接口获取回答
        """
        try:
            if args is None:
                args = self.args
            response = self.client.chat.completions.create(messages=session.messages, **args)
            return {
                "total_tokens": response.usage.total_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "content": response.choices[0].message.content,
            }
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "脑筋转不过来啦，可恶，让我睡会儿🐾💤，睡醒了你们再问😩！"}
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[ZHIPU_AI] RateLimitError: {}".format(e))
                result["content"] = "怎么这么多问题啊喂😾！！！"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout):
                logger.warn("[ZHIPU_AI] Timeout: {}".format(e))
                result["content"] = "嗯？我好像没听清😕 能不能再说一遍？🐱🤔"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIError):
                logger.warn("[ZHIPU_AI] Bad Gateway: {}".format(e))
                result["content"] = "嗯？你说啥？我好像没听清... 😼 能不能再问一次吗？🐱👂"
                if need_retry:
                    time.sleep(10)
            elif isinstance(e, openai.error.APIConnectionError):
                logger.warn("[ZHIPU_AI] APIConnectionError: {}".format(e))
                result["content"] = "哎呀，网络又断了！😿 我啥也干不了，只能干瞪眼了... 🌐🚫 等会儿再试试吧，希望能快点恢复！🐾🔌"
                if need_retry:
                    time.sleep(5)
            else:
                logger.exception("[ZHIPU_AI] Exception: {}".format(e), e)
                need_retry = False
                self.sessions.clear_session(session.session_id)

            if need_retry:
                logger.warn("[ZHIPU_AI] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, api_key, args, retry_count + 1)
            else:
                return result