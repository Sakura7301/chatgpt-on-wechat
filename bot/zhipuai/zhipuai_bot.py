# encoding:utf-8

import time
import re
import os  
import openai
import openai.error

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
from XuanXue.MeiHuaYiShu.meihuaxinyi import SuanGuaRquest
from XuanXue.MeiHuaYiShu.meihuaxinyi import SaveGuaLi
from XuanXue.MeiHuaYiShu.meihuaxinyi import GetGuaShu
from XuanXue.MeiHuaYiShu.meihuaxinyi import FormatZhanBuReply
from XuanXue.MeiHuaYiShu.meihuaxinyi import GenZhanBuCueWord
from XuanXue.ZhenWuLingQian.zhen_wu_ling_qian import ZhenWuLingQian
from XuanXue.ZhenWuLingQian.rush_card import CardDeck
from XuanXue.SanMingZhan.san_ming_zhan import SanMingJiuGong
from XuanXue.DuanYiTianJi.duan_yi_tian_ji import GuaTu
from XuanXue.DuanYiTianJi.duan_yi_tian_ji import GuaTuNum


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
        # 判断是否为文本消息
        if context.type == ContextType.TEXT:
            logger.info("[ZHIPU_AI] query={}".format(query))

            # init reply
            session_id = context["session_id"]
            reply = None

            # 判断用户是否表达了占卜的需求
            if SuanGuaRquest(query):
                # 获取起卦数
                qi_gua_num_result = GetGuaShu(query)
                if qi_gua_num_result and qi_gua_num_result[2] is True:
                    # 使用了随机数，需要进行说明
                    gen_random_num_str = f"卜卦要准确提供3个数字哦，不然会影响准确率哒,下次别忘咯~\n这次我就先用随机数{gen_random_num}帮你起卦叭~\n"
                else:
                    gen_random_num_str = ""
                # 数字
                number = qi_gua_num_result[0]
                # 问题
                question = qi_gua_num_result[1]
                # 调用 MeiHuaXinYi 函数获取结果
                result = MeiHuaXinYi(number)
                if result:
                    # 生成占卜提示词
                    prompt = GenZhanBuCueWord(result, question)
                    # 获取会话
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
                    # 检查token
                    if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                        # token不足
                        reply = Reply(ReplyType.ERROR, reply_content["content"])
                    elif reply_content["completion_tokens"] > 0:
                        # 按照指定格式回复用户
                        final_reply = FormatZhanBuReply(gen_random_num_str,question,number,result,reply_content)
                        # 获取ZHIPU AI回复结果
                        self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                        reply = Reply(ReplyType.TEXT, final_reply)
                        # 保存卦例
                        SaveGuaLi(final_reply, question)
                    else:
                        # token不足
                        reply = Reply(ReplyType.ERROR, reply_content["content"])
                        logger.debug("[ZHIPU_AI] reply {} used 0 tokens.".format(reply_content))
                    return reply
                else:
                    # MeiHuaXinYi 函数返回 None，说明数字不在范围内
                    reply = Reply(ReplyType.ERROR, "输入的数字不在指定范围内，请提供一个介于100到999之间的数字。")
                    return reply
            elif "抽签" == query:
                # 进入抽签逻辑
                ling_qian_result = ZhenWuLingQian()  
                logger.info("已获取到灵签")
                if ling_qian_result:  
                    # 直接传入BytesIO对象  
                    return Reply(ReplyType.IMAGE, ling_qian_result)
                else:  
                    return Reply(ReplyType.TEXT, "未找到指定灵签🐾")
            elif "解签" == query:
                # 解签
                return Reply(ReplyType.TEXT, "签文都给你啦😾！你自己看看嘛~🐾") 
            elif "三命占" == query:
                # 三命占排盘
                pai_pan_result = SanMingJiuGong()
                if pai_pan_result:
                    return Reply(ReplyType.IMAGE, pai_pan_result) 
                else:
                    return Reply(ReplyType.TEXT, "排盘失败！") 
            elif "每日一卦" == query:
                # 每日一卦(卦图)
                gua_tu_result = GuaTuNum()
                return Reply(ReplyType.IMAGE, gua_tu_result) 
            elif "卦图" in query:
                # 卦图
                gua_tu_result = GuaTu(query)
                if gua_tu_result:
                    return Reply(ReplyType.IMAGE, gua_tu_result) 
                else :
                    return Reply(ReplyType.TEXT, "获取卦图需要提供卦名！") 
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