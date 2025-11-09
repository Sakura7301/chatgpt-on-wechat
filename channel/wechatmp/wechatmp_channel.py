# -*- coding: utf-8 -*-
import asyncio
import imghdr
import io
import os
import threading
import time

import requests
import web
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import WeChatClientException
from collections import defaultdict

from bridge.context import *
from bridge.reply import *
from channel.chat_channel import ChatChannel
from channel.wechatmp.common import *
from channel.wechatmp.wechatmp_client import WechatMPClient
from common.log import logger
from common.singleton import singleton
from common.utils import split_string_by_utf8_length, remove_markdown_symbol
from config import conf
from voice.audio_convert import any_to_mp3, split_audio

# If using SSL, uncomment the following lines, and modify the certificate path.
# from cheroot.server import HTTPServer
# from cheroot.ssl.builtin import BuiltinSSLAdapter
# HTTPServer.ssl_adapter = BuiltinSSLAdapter(
#         certificate='/ssl/cert.pem',
#         private_key='/ssl/cert.key')


@singleton
class WechatMPChannel(ChatChannel):
    def __init__(self, passive_reply=True):
        super().__init__()
        self.passive_reply = passive_reply
        self.NOT_SUPPORT_REPLYTYPE = []
        appid = conf().get("wechatmp_app_id")
        secret = conf().get("wechatmp_app_secret")
        token = conf().get("wechatmp_token")
        aes_key = conf().get("wechatmp_aes_key")
        self.client = WechatMPClient(appid, secret)
        self.crypto = None
        if aes_key:
            self.crypto = WeChatCrypto(token, aes_key, appid)
        if self.passive_reply:
            # Cache the reply to the user's first message
            self.cache_dict = defaultdict(list)
            # Record whether the current message is being processed
            self.running = set()
            # Count the request from wechat official server by message_id
            self.request_cnt = dict()
            # The permanent media need to be deleted to avoid media number limit
            self.delete_media_loop = asyncio.new_event_loop()
            t = threading.Thread(target=self.start_loop, args=(self.delete_media_loop,))
            t.setDaemon(True)
            t.start()

    def startup(self):
        if self.passive_reply:
            urls = ("/wx", "channel.wechatmp.passive_reply.Query")
        else:
            urls = ("/wx", "channel.wechatmp.active_reply.Query")
        app = web.application(urls, globals(), autoreload=False)
        port = conf().get("wechatmp_port", 8080)
        web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", port))

    def start_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async def delete_media(self, media_id):
        logger.debug("[wechatmp] permanent media {} will be deleted in 10s".format(media_id))
        await asyncio.sleep(10)
        self.client.material.delete(media_id)
        logger.info("[wechatmp] permanent media {} has been deleted".format(media_id))

    def send(self, reply: Reply, context: Context):
        receiver = context["receiver"]
        if self.passive_reply:
            if reply.type == ReplyType.TEXT or reply.type == ReplyType.INFO or reply.type == ReplyType.ERROR:
                reply_text = remove_markdown_symbol(reply.content)
                logger.info("[wechatmp] text cached, receiver {}\n{}".format(receiver, reply_text))
                self.cache_dict[receiver].append(("text", reply_text))
            elif reply.type == ReplyType.VOICE:
                voice_file_path = reply.content
                duration, files = split_audio(voice_file_path, 60 * 1000)
                if len(files) > 1:
                    logger.info("[wechatmp] voice too long {}s > 60s , split into {} parts".format(duration / 1000.0, len(files)))

                for path in files:
                    # support: <2M, <60s, mp3/wma/wav/amr
                    try:
                        with open(path, "rb") as f:
                            response = self.client.material.add("voice", f)
                            logger.debug("[wechatmp] upload voice response: {}".format(response))
                            f_size = os.fstat(f.fileno()).st_size
                            time.sleep(1.0 + 2 * f_size / 1024 / 1024)
                            # todo check media_id
                    except WeChatClientException as e:
                        logger.error("[wechatmp] upload voice failed: {}".format(e))
                        return
                    media_id = response["media_id"]
                    logger.info("[wechatmp] voice uploaded, receiver {}, media_id {}".format(receiver, media_id))
                    self.cache_dict[receiver].append(("voice", media_id))

            elif reply.type == ReplyType.IMAGE_URL:  # 从网络下载图片
                img_url = reply.content
                pic_res = requests.get(img_url, stream=True)
                image_storage = io.BytesIO()
                for block in pic_res.iter_content(1024):
                    image_storage.write(block)
                image_storage.seek(0)
                image_type = imghdr.what(image_storage)
                filename = receiver + "-" + str(context["msg"].msg_id) + "." + image_type
                content_type = "image/" + image_type
                try:
                    response = self.client.material.add("image", (filename, image_storage, content_type))
                    logger.debug("[wechatmp] upload image response: {}".format(response))
                except WeChatClientException as e:
                    logger.error("[wechatmp] upload image failed: {}".format(e))
                    return
                media_id = response["media_id"]
                logger.info("[wechatmp] image uploaded, receiver {}, media_id {}".format(receiver, media_id))
                self.cache_dict[receiver].append(("image", media_id))
                
            elif reply.type == ReplyType.IMAGE:  # 从文件读取图片
                image_storage = reply.content
                image_storage.seek(0)
                image_type = imghdr.what(image_storage)
                filename = receiver + "-" + str(context["msg"].msg_id) + "." + image_type
                content_type = "image/" + image_type
                try:
                    response = self.client.material.add("image", (filename, image_storage, content_type))
                    logger.debug("[wechatmp] upload image response: {}".format(response))
                except WeChatClientException as e:
                    logger.error("[wechatmp] upload image failed: {}".format(e))
                    return
                media_id = response["media_id"]
                logger.info("[wechatmp] image uploaded, receiver {}, media_id {}".format(receiver, media_id))
                self.cache_dict[receiver].append(("image", media_id))
                
            elif reply.type == ReplyType.VIDEO_URL:  # ✅ 从网络下载视频（带详细日志）
                video_url = reply.content
                total_start_time = time.time()
                logger.info(f"[wechatmp] 🎬 开始处理视频: {video_url}")
                
                try:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    # ✅ 步骤1：发起下载请求
                    request_start = time.time()
                    logger.info(f"[wechatmp] 📡 正在连接视频服务器...")
                    
                    video_res = requests.get(
                        video_url, 
                        stream=True, 
                        verify=False,
                        timeout=30,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    video_res.raise_for_status()
                    
                    request_time = time.time() - request_start
                    logger.info(f"[wechatmp] ✅ 连接成功 (耗时: {request_time:.2f}s)")
                    
                    # 获取文件大小
                    content_length = video_res.headers.get('content-length')
                    if content_length:
                        total_size = int(content_length)
                        logger.info(f"[wechatmp] 📦 视频大小: {total_size/1024/1024:.2f} MB")
                    else:
                        total_size = None
                        logger.info(f"[wechatmp] 📦 视频大小: 未知")
                    
                    # ✅ 步骤2：下载视频到内存
                    download_start = time.time()
                    video_storage = io.BytesIO()
                    downloaded_size = 0
                    last_log_size = 0
                    
                    logger.info(f"[wechatmp] ⬇️ 开始下载视频...")
                    
                    for block in video_res.iter_content(8192):
                        video_storage.write(block)
                        downloaded_size += len(block)
                        
                        # 每下载 1MB 打印一次进度
                        if downloaded_size - last_log_size >= 1024 * 1024:
                            elapsed = time.time() - download_start
                            speed = downloaded_size / elapsed / 1024 / 1024 if elapsed > 0 else 0
                            
                            if total_size:
                                progress = downloaded_size / total_size * 100
                                logger.debug(f"[wechatmp] ⬇️ 下载中: {downloaded_size/1024/1024:.2f}/{total_size/1024/1024:.2f} MB ({progress:.1f}%), 速度: {speed:.2f} MB/s")
                            else:
                                logger.debug(f"[wechatmp] ⬇️ 已下载: {downloaded_size/1024/1024:.2f} MB, 速度: {speed:.2f} MB/s")
                            
                            last_log_size = downloaded_size
                    
                    download_time = time.time() - download_start
                    avg_speed = downloaded_size / download_time / 1024 / 1024 if download_time > 0 else 0
                    
                    logger.info(f"[wechatmp] ✅ 下载完成: {downloaded_size/1024/1024:.2f} MB, 耗时: {download_time:.2f}s, 平均速度: {avg_speed:.2f} MB/s")
                    video_storage.seek(0)
                    
                    # ✅ 步骤3：上传到微信
                    upload_start = time.time()
                    video_type = 'mp4'
                    filename = receiver + "-" + str(context["msg"].msg_id) + "." + video_type
                    
                    try:
                        logger.info(f"[wechatmp] ☁️ 开始上传到微信服务器: {filename}")
                        
                        # 使用 media.upload（临时素材）
                        response = self.client.media.upload(
                            'video',
                            (filename, video_storage, 'video/mp4')
                        )
                        
                        upload_time = time.time() - upload_start
                        logger.info(f"[wechatmp] ✅ 上传成功，耗时: {upload_time:.2f}s")
                        logger.debug("[wechatmp] upload video response: {}".format(response))
                        
                        media_id = response['media_id']
                        
                        total_time = time.time() - total_start_time
                        logger.info(f"[wechatmp] 🎉 视频处理完成！总耗时: {total_time:.2f}s (下载: {download_time:.2f}s, 上传: {upload_time:.2f}s)")
                        logger.info(f"[wechatmp] 📺 media_id: {media_id}")
                        
                        self.cache_dict[receiver].append(("video", media_id))
                        
                    except AssertionError as e:
                        logger.error(f"[wechatmp] ❌ 上传参数错误: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        self.cache_dict[receiver].append(("text", "❌ 视频上传参数错误"))
                        return
                        
                    except WeChatClientException as e:
                        logger.error(f"[wechatmp] ❌ 微信API错误: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        self.cache_dict[receiver].append(("text", f"❌ 视频上传到微信失败: {str(e)}"))
                        return
                        
                    except Exception as e:
                        logger.error(f"[wechatmp] ❌ 上传视频时出错: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        self.cache_dict[receiver].append(("text", "❌ 视频上传出错"))
                        return
                        
                except requests.exceptions.Timeout:
                    logger.error(f"[wechatmp] ⏱️ 下载视频超时 (30s): {video_url}")
                    self.cache_dict[receiver].append(("text", "⏱️ 视频下载超时，请稍后再试"))
                    return
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"[wechatmp] 📹 下载视频失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    self.cache_dict[receiver].append(("text", f"📹 视频下载失败: {str(e)}"))
                    return
                    
                except Exception as e:
                    logger.error(f"[wechatmp] 💥 处理视频时出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    self.cache_dict[receiver].append(("text", "💥 视频处理出错"))
                    return
                    
            elif reply.type == ReplyType.VIDEO:  # ✅ 从文件读取视频
                video_storage = reply.content
                video_storage.seek(0)
                video_type = 'mp4'
                filename = receiver + "-" + str(context["msg"].msg_id) + "." + video_type
                
                try:
                    logger.info(f"[wechatmp] 开始上传本地视频到微信（临时素材）: {filename}")
                    
                    # 使用 media.upload 上传临时素材
                    response = self.client.media.upload(
                        'video',
                        (filename, video_storage, 'video/mp4')
                    )
                    
                    logger.debug("[wechatmp] upload video response: {}".format(response))
                    
                    media_id = response["media_id"]
                    logger.info("[wechatmp] ✅ video uploaded, receiver {}, media_id {}".format(receiver, media_id))
                    self.cache_dict[receiver].append(("video", media_id))
                    
                except AssertionError as e:
                    logger.error(f"[wechatmp] ❌ 上传参数错误: {e}")
                    self.cache_dict[receiver].append(("text", "❌ 视频上传参数错误"))
                    return
                    
                except WeChatClientException as e:
                    logger.error(f"[wechatmp] ❌ upload video failed: {e}")
                    self.cache_dict[receiver].append(("text", "❌ 视频上传失败"))
                    return
                    
                except Exception as e:
                    logger.error(f"[wechatmp] ❌ 上传视频时出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return
                    
        else:  # 主动回复模式
            if reply.type == ReplyType.TEXT or reply.type == ReplyType.INFO or reply.type == ReplyType.ERROR:
                reply_text = reply.content
                texts = split_string_by_utf8_length(reply_text, MAX_UTF8_LEN)
                if len(texts) > 1:
                    logger.info("[wechatmp] text too long, split into {} parts".format(len(texts)))
                for i, text in enumerate(texts):
                    self.client.message.send_text(receiver, text)
                    if i != len(texts) - 1:
                        time.sleep(0.5)  # 休眠0.5秒，防止发送过快乱序
                logger.info("[wechatmp] Do send text to {}: {}".format(receiver, reply_text))
                
            elif reply.type == ReplyType.VOICE:
                try:
                    file_path = reply.content
                    file_name = os.path.basename(file_path)
                    file_type = os.path.splitext(file_name)[1]
                    if file_type == ".mp3":
                        file_type = "audio/mpeg"
                    elif file_type == ".amr":
                        file_type = "audio/amr"
                    else:
                        mp3_file = os.path.splitext(file_path)[0] + ".mp3"
                        any_to_mp3(file_path, mp3_file)
                        file_path = mp3_file
                        file_name = os.path.basename(file_path)
                        file_type = "audio/mpeg"
                    logger.info("[wechatmp] file_name: {}, file_type: {} ".format(file_name, file_type))
                    media_ids = []
                    duration, files = split_audio(file_path, 60 * 1000)
                    if len(files) > 1:
                        logger.info("[wechatmp] voice too long {}s > 60s , split into {} parts".format(duration / 1000.0, len(files)))
                    for path in files:
                        # support: <2M, <60s, AMR\MP3
                        response = self.client.media.upload("voice", (os.path.basename(path), open(path, "rb"), file_type))
                        logger.debug("[wechatcom] upload voice response: {}".format(response))
                        media_ids.append(response["media_id"])
                        os.remove(path)
                except WeChatClientException as e:
                    logger.error("[wechatmp] upload voice failed: {}".format(e))
                    return

                try:
                    os.remove(file_path)
                except Exception:
                    pass

                for media_id in media_ids:
                    self.client.message.send_voice(receiver, media_id)
                    time.sleep(1)
                logger.info("[wechatmp] Do send voice to {}".format(receiver))
                
            elif reply.type == ReplyType.IMAGE_URL:  # 从网络下载图片
                img_url = reply.content
                pic_res = requests.get(img_url, stream=True)
                image_storage = io.BytesIO()
                for block in pic_res.iter_content(1024):
                    image_storage.write(block)
                image_storage.seek(0)
                image_type = imghdr.what(image_storage)
                filename = receiver + "-" + str(context["msg"].msg_id) + "." + image_type
                content_type = "image/" + image_type
                try:
                    response = self.client.media.upload("image", (filename, image_storage, content_type))
                    logger.debug("[wechatmp] upload image response: {}".format(response))
                except WeChatClientException as e:
                    logger.error("[wechatmp] upload image failed: {}".format(e))
                    return
                self.client.message.send_image(receiver, response["media_id"])
                logger.info("[wechatmp] Do send image to {}".format(receiver))
                
            elif reply.type == ReplyType.IMAGE:  # 从文件读取图片
                image_storage = reply.content
                image_storage.seek(0)
                image_type = imghdr.what(image_storage)
                filename = receiver + "-" + str(context["msg"].msg_id) + "." + image_type
                content_type = "image/" + image_type
                try:
                    response = self.client.media.upload("image", (filename, image_storage, content_type))
                    logger.debug("[wechatmp] upload image response: {}".format(response))
                except WeChatClientException as e:
                    logger.error("[wechatmp] upload image failed: {}".format(e))
                    return
                self.client.message.send_image(receiver, response["media_id"])
                logger.info("[wechatmp] Do send image to {}".format(receiver))
                
            elif reply.type == ReplyType.VIDEO_URL:  # 从网络下载视频
                video_url = reply.content
                video_res = requests.get(video_url, stream=True)
                video_storage = io.BytesIO()
                for block in video_res.iter_content(8192):
                    video_storage.write(block)
                video_storage.seek(0)
                video_type = 'mp4'
                filename = receiver + "-" + str(context["msg"].msg_id) + "." + video_type
                try:
                    response = self.client.media.upload("video", (filename, video_storage, 'video/mp4'))
                    logger.debug("[wechatmp] upload video response: {}".format(response))
                except WeChatClientException as e:
                    logger.error("[wechatmp] upload video failed: {}".format(e))
                    return
                self.client.message.send_video(receiver, response["media_id"])
                logger.info("[wechatmp] Do send video to {}".format(receiver))
                
            elif reply.type == ReplyType.VIDEO:  # 从文件读取视频
                video_storage = reply.content
                video_storage.seek(0)
                video_type = 'mp4'
                filename = receiver + "-" + str(context["msg"].msg_id) + "." + video_type
                try:
                    response = self.client.media.upload("video", (filename, video_storage, 'video/mp4'))
                    logger.debug("[wechatmp] upload video response: {}".format(response))
                except WeChatClientException as e:
                    logger.error("[wechatmp] upload video failed: {}".format(e))
                    return
                self.client.message.send_video(receiver, response["media_id"])
                logger.info("[wechatmp] Do send video to {}".format(receiver))
        return

    def _success_callback(self, session_id, context, **kwargs):  # 线程异常结束时的回调函数
        logger.debug("[wechatmp] Success to generate reply, msgId={}".format(context["msg"].msg_id))
        if self.passive_reply:
            self.running.remove(session_id)

    def _fail_callback(self, session_id, exception, context, **kwargs):  # 线程异常结束时的回调函数
        logger.exception("[wechatmp] Fail to generate reply to user, msgId={}, exception={}".format(context["msg"].msg_id, exception))
        if self.passive_reply:
            assert session_id not in self.cache_dict
            self.running.remove(session_id)