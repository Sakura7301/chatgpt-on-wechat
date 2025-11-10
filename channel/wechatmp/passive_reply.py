import asyncio
import time

import web
from wechatpy import parse_message
from wechatpy.replies import ImageReply, VoiceReply, VideoReply, create_reply
import textwrap
from bridge.context import *
from bridge.reply import *
from channel.wechatmp.common import *
from channel.wechatmp.wechatmp_channel import WechatMPChannel
from channel.wechatmp.wechatmp_message import WeChatMPMessage
from common.log import logger
from common.utils import split_string_by_utf8_length
from config import conf, subscribe_msg


# This class is instantiated once per query
class Query:
    def GET(self):
        return verify_server(web.input())

    def POST(self):
        try:
            args = web.input()
            verify_server(args)
            request_time = time.time()
            channel = WechatMPChannel()
            message = web.data()
            encrypt_func = lambda x: x
            
            if args.get("encrypt_type") == "aes":
                logger.debug("[wechatmp] Receive encrypted post data:\n" + message.decode("utf-8"))
                if not channel.crypto:
                    raise Exception("Crypto not initialized, Please set wechatmp_aes_key in config.json")
                message = channel.crypto.decrypt_message(message, args.msg_signature, args.timestamp, args.nonce)
                encrypt_func = lambda x: channel.crypto.encrypt_message(x, args.nonce, args.timestamp)
            else:
                logger.debug("[wechatmp] Receive post data:\n" + message.decode("utf-8"))
                
            msg = parse_message(message)
            
            if msg.type in ["text", "voice", "image"]:
                wechatmp_msg = WeChatMPMessage(msg, client=channel.client)
                from_user = wechatmp_msg.from_user_id
                content = wechatmp_msg.content
                message_id = wechatmp_msg.msg_id

                supported = True
                if "【收到不支持的消息类型，暂无法显示】" in content:
                    supported = False

                # ✅ 判断是否需要创建新任务
                if (
                    channel.cache_dict.get(from_user) is None
                    and from_user not in channel.running
                    or content.startswith("#")
                    and message_id not in channel.request_cnt
                ):
                    if msg.type == "voice" and wechatmp_msg.ctype == ContextType.TEXT and conf().get("voice_reply_voice", False):
                        context = channel._compose_context(wechatmp_msg.ctype, content, isgroup=False, desire_rtype=ReplyType.VOICE, msg=wechatmp_msg)
                    else:
                        context = channel._compose_context(wechatmp_msg.ctype, content, isgroup=False, msg=wechatmp_msg)
                    logger.debug("[wechatmp] context: {} {} {}".format(context, wechatmp_msg, supported))

                    if supported and context:
                        logger.debug(f"[wechatmp] 🚀 开始处理新任务: {from_user}")
                        channel.running.add(from_user)
                        channel.produce(context)
                    else:
                        trigger_prefix = conf().get("single_chat_prefix", [""])[0]
                        if trigger_prefix or not supported:
                            if trigger_prefix:
                                reply_text = textwrap.dedent(
                                    f"""\
                                    请输入'{trigger_prefix}'接你想说的话跟我说话。
                                    例如:
                                    {trigger_prefix}你好，很高兴见到你。"""
                                )
                            else:
                                reply_text = textwrap.dedent(
                                    """\
                                    你好，很高兴见到你。
                                    请跟我说话吧。"""
                                )
                        else:
                            logger.error(f"[wechatmp] unknown error")
                            reply_text = textwrap.dedent(
                                """\
                                未知错误，请稍后再试"""
                            )

                        replyPost = create_reply(reply_text, msg)
                        return encrypt_func(replyPost.render())

                # 记录请求次数
                request_cnt = channel.request_cnt.get(message_id, 0) + 1
                channel.request_cnt[message_id] = request_cnt
                if request_cnt < 2:
                    logger.debug(
                        "[wechatmp] Request {} from {} {} {}:{}\n{}".format(
                            request_cnt, from_user, message_id, web.ctx.env.get("REMOTE_ADDR"), web.ctx.env.get("REMOTE_PORT"), content
                        )
                    )
                else:
                    logger.info(
                        "[wechatmp] Request {} from {} {} {}:{}\n{}".format(
                            request_cnt, from_user, message_id, web.ctx.env.get("REMOTE_ADDR"), web.ctx.env.get("REMOTE_PORT"), content
                        )
                    )

                # ✅ 被动等待任务完成
                task_running = True
                waiting_until = request_time + 4.5
                
                while time.time() < waiting_until:
                    if from_user in channel.running:
                        time.sleep(0.1)
                    else:
                        task_running = False
                        logger.debug(f"[wechatmp] ✅ 任务已完成: {from_user}")
                        break

                # ✅ 如果任务还在运行
                if task_running:
                    logger.debug(f"[wechatmp] ⏳ 任务处理中 (请求{request_cnt}次): {from_user}")
                    
                    if request_cnt < 3:
                        # 前两次请求，返回 success，让微信继续重试
                        time.sleep(2)
                        return "success"
                    else:
                        # 第3次及以后，返回友好提示
                        reply_text = "⏳ 请求正在处理中~\n请稍等10秒后再发送任意文字获取结果"
                        replyPost = create_reply(reply_text, msg)
                        return encrypt_func(replyPost.render())

                # ✅ 清理请求计数
                if message_id in channel.request_cnt:
                    del channel.request_cnt[message_id]

                # ✅ 检查是否有缓存结果
                if from_user not in channel.cache_dict and from_user not in channel.running:
                    logger.warning(f"[wechatmp] ⚠️ 没有缓存结果: {from_user}")
                    return "success"

                # ✅ 获取缓存结果
                try:
                    (reply_type, reply_content) = channel.cache_dict[from_user].pop(0)
                    if not channel.cache_dict[from_user]:
                        del channel.cache_dict[from_user]
                        logger.debug(f"[wechatmp] 🧹 清理缓存: {from_user}")
                except IndexError:
                    logger.warning(f"[wechatmp] ⚠️ 缓存为空: {from_user}")
                    return "success"

                # ✅ 根据类型返回结果
                if reply_type == "text":
                    if len(reply_content.encode("utf8")) <= MAX_UTF8_LEN:
                        reply_text = reply_content
                    else:
                        continue_text = "\n【未完待续，回复任意文字以继续】"
                        splits = split_string_by_utf8_length(
                            reply_content,
                            MAX_UTF8_LEN - len(continue_text.encode("utf-8")),
                            max_split=1,
                        )
                        reply_text = splits[0] + continue_text
                        channel.cache_dict[from_user].append(("text", splits[1]))

                    logger.info(
                        "[wechatmp] Request {} do send to {} {}: {}\n{}".format(
                            request_cnt,
                            from_user,
                            message_id,
                            content,
                            reply_text[:100],
                        )
                    )
                    replyPost = create_reply(reply_text, msg)
                    return encrypt_func(replyPost.render())

                elif reply_type == "voice":
                    media_id = reply_content
                    asyncio.run_coroutine_threadsafe(channel.delete_media(media_id), channel.delete_media_loop)
                    logger.info(
                        "[wechatmp] 🎤 发送语音 Request {} to {} {}: media_id {}".format(
                            request_cnt,
                            from_user,
                            message_id,
                            media_id,
                        )
                    )
                    replyPost = VoiceReply(message=msg)
                    replyPost.media_id = media_id
                    return encrypt_func(replyPost.render())

                elif reply_type == "image":
                    media_id = reply_content
                    asyncio.run_coroutine_threadsafe(channel.delete_media(media_id), channel.delete_media_loop)
                    logger.debug(
                        "[wechatmp] 🖼️ 发送图片 Request {} to {} {}: media_id {}".format(
                            request_cnt,
                            from_user,
                            message_id,
                            media_id,
                        )
                    )
                    replyPost = ImageReply(message=msg)
                    replyPost.media_id = media_id
                    return encrypt_func(replyPost.render())

                elif reply_type == "video":
                    media_id = reply_content
                    asyncio.run_coroutine_threadsafe(channel.delete_media(media_id), channel.delete_media_loop)
                    logger.info(
                        "[wechatmp] 📹 发送视频 Request {} to {} {}: media_id {}".format(
                            request_cnt,
                            from_user,
                            message_id,
                            media_id,
                        )
                    )
                    replyPost = VideoReply(message=msg)
                    replyPost.media_id = media_id
                    replyPost.title = "🎬视频 "  # 添加标题
                    replyPost.description = "▶️点击播放精彩内容~"  # 添加描述
                    return encrypt_func(replyPost.render())

            elif msg.type == "event":
                logger.info("[wechatmp] Event {} from {}".format(msg.event, msg.source))
                if msg.event in ["subscribe", "subscribe_scan"]:
                    reply_text = subscribe_msg()
                    if reply_text:
                        replyPost = create_reply(reply_text, msg)
                        return encrypt_func(replyPost.render())
                else:
                    return "success"
            else:
                logger.info("暂且不处理")
            return "success"
        except Exception as exc:
            logger.exception(exc)
            return exc