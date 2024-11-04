# encoding:utf-8  
import io  
import logging  
from enum import Enum  
from typing import Union, Optional, Any  


# 配置日志  
logging.basicConfig(level=logging.INFO)  
logger = logging.getLogger(__name__)  


class ReplyType(Enum):  
    TEXT = 1  # 文本  
    VOICE = 2  # 音频文件  
    IMAGE = 3  # 图片文件  
    IMAGE_URL = 4  # 图片URL  
    VIDEO_URL = 5  # 视频URL  
    FILE = 6  # 文件  
    CARD = 7  # 微信名片，仅支持ntchat  
    INVITE_ROOM = 8  # 邀请好友进群  
    INFO = 9  
    ERROR = 10  
    TEXT_ = 11  # 强制文本  
    VIDEO = 12  
    MINIAPP = 13  # 小程序  

    def __str__(self):  
        return self.name  


class Reply:  
    def __init__(self, type: Optional[ReplyType] = None, content: Any = None):  
        """  
        初始化Reply对象  
        
        Args:  
            type (ReplyType, optional): 回复类型  
            content (Any): 回复内容  
        """  
        self.type = type  
        self._raw_content = None  
        self.content = self._process_content(content)  
        # logger.info(f"创建了新的 Reply 对象，类型: {type}")  

    def _process_content(self, content: Any) -> Any:  
        """  
        处理不同类型的内容  
        """  
        if content is None:  
            return None  

        # 处理 BytesIO 对象  
        if isinstance(content, io.BytesIO):  
            try:  
                # logger.info("正在处理 BytesIO 对象...")  
                # 保存原始数据  
                self._raw_content = content.getvalue()  
                # 返回一个新的 BytesIO 对象  
                bio = io.BytesIO(self._raw_content)  
                bio.seek(0)  
                # logger.info(f"成功创建新的 BytesIO 对象，大小: {len(self._raw_content)} 字节")  
                return bio  
            except Exception as e:  
                logger.error(f"处理 BytesIO 失败：{e}")  
                return None  
            finally:  
                try:  
                    content.close()  
                    # logger.info("原始 BytesIO 对象已关闭")  
                except Exception as e:  
                    logger.error(f"关闭 BytesIO 对象时出错：{e}")  
        
        # 如果是 bytes，直接保存并返回 BytesIO  
        elif isinstance(content, bytes):  
            # logger.info(f"处理 bytes 对象，大小: {len(content)} 字节")  
            self._raw_content = content  
            bio = io.BytesIO(content)  
            bio.seek(0)  
            return bio  

        return content  

    def get_content(self) -> Any:  
        """  
        获取内容。对于图片类型，始终返回新的 BytesIO 对象  
        """  
        if self.type == ReplyType.IMAGE:  
            if isinstance(self.content, io.BytesIO):  
                # logger.info("返回现有的 BytesIO 对象")  
                # 重置位置  
                self.content.seek(0)  
                return self.content  
            elif self._raw_content:  
                # logger.info("从原始数据创建新的 BytesIO 对象")  
                # 如果有原始数据，创建新的 BytesIO  
                bio = io.BytesIO(self._raw_content)  
                bio.seek(0)  
                return bio  
        return self.content  

    def __del__(self):  
        """  
        析构函数，确保资源被正确释放  
        """  
        try:  
            if isinstance(self.content, io.BytesIO):  
                self.content.close()  
                # logger.info("在对象销毁时关闭了 BytesIO 对象")  
        except Exception as e:  
            logger.error(f"在销毁对象时关闭 BytesIO 失败：{e}")  

    def __str__(self) -> str:  
        """  
        字符串表示  
        """  
        content_preview = str(self.content)  
        if len(content_preview) > 100:  
            content_preview = content_preview[:100] + '...'  
        return f"Reply(type={self.type}, content={content_preview})"  

    def __repr__(self) -> str:  
        return self.__str__()  