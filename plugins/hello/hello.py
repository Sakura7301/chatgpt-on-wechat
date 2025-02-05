# encoding:utf-8

import plugins
from bridge.context import ContextType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import *


@plugins.register(
    name="Hello",
    desire_priority=-1,
    hidden=True,
    desc="A simple plugin that says hello",
    version="0.1",
    author="other",
)


class Hello(Plugin):
    def __init__(self):
        super().__init__()
        try:
            self.config = super().load_config()
            self.group_welc_prompt = "请你随机使用一种风格说一句问候语来欢迎新用户\"{nickname}\"加入群聊。"
            self.group_exit_prompt = "请你随机使用一种风格介绍你自己，并告诉用户输入#help可以查看帮助信息。"
            self.patpat_prompt = "请你随机使用一种风格跟其他群用户说他违反规则\"{nickname}\"退出群聊。"
            logger.info("[Hello] inited")
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        except Exception as e:
            logger.error(f"[Hello]初始化异常：{e}")
            raise "[Hello] init failed, ignore "

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
            ContextType.JOIN_GROUP,
        ]:
            return
        msg: ChatMessage = e_context["context"]["msg"]
        if e_context["context"].type == ContextType.JOIN_GROUP:
            e_context["context"].type = ContextType.TEXT
            e_context["context"].content = self.group_welc_prompt.format(nickname=msg.actual_user_nickname)
            e_context.action = EventAction.BREAK  # 事件结束，进入默认处理逻辑
            if not self.config or not self.config.get("use_character_desc"):
                e_context["context"]["generate_breaked_by"] = EventAction.BREAK
            return