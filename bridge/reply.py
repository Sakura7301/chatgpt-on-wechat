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

    def _process_content(self, content: Any) -> Any:  
        """  
        处理不同类型的内容  
        """  
        if content is None:  
            return None  

        # 处理 BytesIO 对象  
        if isinstance(content, io.BytesIO):  
            try:  
                # 保存原始数据  
                self._raw_content = content.getvalue()  
                # 返回一个新的 BytesIO 对象  
                bio = io.BytesIO(self._raw_content)  
                bio.seek(0)  
                return bio  
            except Exception as e:  
                logger.error(f"处理 BytesIO 失败：{e}")  
                return None  
            finally:  
                try:  
                    content.close()  
                except Exception as e:  
                    logger.error(f"关闭 BytesIO 对象时出错：{e}")  
        
        # 如果是 bytes，直接保存并返回 BytesIO  
        elif isinstance(content, bytes):  
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
                self.content.seek(0)  
                return self.content  
            elif self._raw_content:  
                bio = io.BytesIO(self._raw_content)  
                bio.seek(0)  
                return bio  
        return self.content  

    def __enter__(self):  
        """进入上下文管理器"""  
        return self  

    def __exit__(self, exc_type, exc_val, exc_tb):  
        """退出上下文管理器并关闭 BytesIO 对象"""  
        self.close_content()  

    def close_content(self):  
        """关闭内容"""  
        try:  
            if isinstance(self.content, io.BytesIO):  
                self.content.close()  
        except Exception as e:  
            logger.error(f"在关闭 BytesIO 对象时出错：{e}")  

    def __del__(self):  
        """  
        析构函数，确保资源被正确释放  
        """  
        self.close_content()  

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