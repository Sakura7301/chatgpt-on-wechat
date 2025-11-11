import json
import time
import os
import sys
import threading
import webbrowser
import hashlib
import base64
import hmac
import requests
import argparse
from Crypto.Cipher import AES
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

# 确保能够导入项目模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入你的微信处理模块
try:
    from channel.wechat.wechat_channel import WechatChannel
    from channel.wechat.wechat_message import WechatMessage
    from config import conf
except ImportError:
    print("⚠️ 无法导入微信处理模块，将使用模拟模式")
    WechatChannel = None
    WechatMessage = None
    conf = None

# 全局配置 - 不再使用默认值
CONFIG = {
    "wechat": {},
    "server": {}
}

def load_config_from_files():
    """从配置文件加载配置"""
    config_file = "config.json"
    config_data = {}
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # 合并配置，后加载的文件优先级更高
                if isinstance(file_config, dict):
                    config_data.update(file_config)
            print(f"✅ 已加载配置文件: {config_file}")
        except Exception as e:
            print(f"⚠️ 加载配置文件 {config_file} 失败: {e}")
    else:
        print(f"ℹ️ 配置文件不存在: {config_file}")
    
    # 从config.json读取微信端口
    wechatmp_port = config_data.get('wechatmp_port', 8081)
    
    # 构建配置
    CONFIG['wechat'] = {
        "app_id": config_data.get('wechatmp_app_id', ''),
        "app_secret": config_data.get('wechatmp_app_secret', ''),
        "aes_key": config_data.get('wechatmp_aes_key', ''),
        "token": config_data.get('wechatmp_token', '')
    }
    
    CONFIG['server'] = {
        "port": 8082,
        "service_url": f"http://127.0.0.1:{wechatmp_port}/wx",
        "timeout": 60
    }
    
    # 验证必要配置
    required_wechat_fields = ['app_id', 'app_secret', 'aes_key', 'token']
    missing_fields = [field for field in required_wechat_fields if not CONFIG['wechat'][field]]
    
    if missing_fields:
        print(f"⚠️ 警告: 以下必要字段在配置文件中缺失: {', '.join(missing_fields)}")
        print("请在 config.json 中配置这些字段")

class WeChatCrypto:
    """微信消息加解密"""
    def __init__(self, token, encoding_aes_key, app_id):
        self.token = token
        self.app_id = app_id
        encoding_aes_key = encoding_aes_key + "=" * ((4 - len(encoding_aes_key) % 4) % 4)
        self.aes_key = base64.b64decode(encoding_aes_key + "===")
        self.iv = self.aes_key[:16]

    def check_signature(self, signature, timestamp, nonce, echo_str=None):
        """验证签名"""
        params = [self.token, timestamp, nonce]
        if echo_str:
            params.append(echo_str)
        params.sort()
        sha1 = hashlib.sha1()
        sha1.update(''.join(params).encode())
        return sha1.hexdigest() == signature

    def encrypt(self, text):
        """加密消息"""
        random_str = os.urandom(16).hex()[:16]
        text_bytes = text.encode('utf-8')
        text_len = len(text_bytes)
        content = random_str.encode() + text_len.to_bytes(4, byteorder='big') + text_bytes + self.app_id.encode()
        
        pad_len = 32 - (len(content) % 32)
        padded_content = content + bytes([pad_len] * pad_len)
        
        encryptor = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
        encrypted = encryptor.encrypt(padded_content)
        
        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt(self, encrypted_text):
        """解密消息"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_text)
            decryptor = AES.new(self.aes_key, AES.MODE_CBC, self.iv)
            decrypted = decryptor.decrypt(encrypted_bytes)
            
            pad_len = decrypted[-1]
            if pad_len < 1 or pad_len > 32:
                pad_len = 0
            content = decrypted[:-pad_len]
            
            app_id_len = len(self.app_id)
            xml_len = int.from_bytes(content[16:20], byteorder='big')
            xml_content = content[20:20+xml_len]
            app_id = content[20+xml_len:20+xml_len+app_id_len].decode()
            
            if app_id != self.app_id:
                raise ValueError("AppID不匹配")
                
            return xml_content.decode('utf-8')
        except Exception as e:
            print(f"解密失败: {e}")
            return ""

class MockMessage:
    """模拟微信消息"""
    def __init__(self, msg_type, content="", media_id="", user_id="mock_user", encrypted=False):
        self.id = str(int(time.time()))
        self.type = msg_type
        self.content = content
        self.media_id = media_id
        self.create_time = int(time.time())
        self.user_id = user_id
        self.encrypted = encrypted

    def to_xml(self):
        """转换为微信XML格式"""
        root = ET.Element('xml')
        ET.SubElement(root, 'ToUserName').text = f"gh_{CONFIG['wechat']['app_id'][-8:]}"
        ET.SubElement(root, 'FromUserName').text = self.user_id
        ET.SubElement(root, 'CreateTime').text = str(self.create_time)
        ET.SubElement(root, 'MsgType').text = self.type
        ET.SubElement(root, 'MsgId').text = self.id
        
        if self.type == 'text':
            ET.SubElement(root, 'Content').text = self.content
        elif self.type == 'image':
            ET.SubElement(root, 'PicUrl').text = 'http://example.com/image.jpg'
            ET.SubElement(root, 'MediaId').text = self.media_id or f"mock_media_{int(time.time())}"
        elif self.type == 'voice':
            ET.SubElement(root, 'MediaId').text = self.media_id or f"mock_media_{int(time.time())}"
            ET.SubElement(root, 'Format').text = 'amr'
        elif self.type == 'video':
            ET.SubElement(root, 'MediaId').text = self.media_id or f"mock_media_{int(time.time())}"
            ET.SubElement(root, 'ThumbMediaId').text = f"thumb_{int(time.time())}"
        elif self.type == 'location':
            ET.SubElement(root, 'Location_X').text = '39.90'
            ET.SubElement(root, 'Location_Y').text = '116.40'
            ET.SubElement(root, 'Scale').text = '15'
            ET.SubElement(root, 'Label').text = self.content or "模拟位置"
        elif self.type == 'link':
            ET.SubElement(root, 'Title').text = self.content or "模拟链接标题"
            ET.SubElement(root, 'Description').text = "模拟链接描述"
            ET.SubElement(root, 'Url').text = "http://example.com/mock-link"
        elif self.type == 'event':
            ET.SubElement(root, 'Event').text = self.content or "subscribe"
            if self.content == "CLICK":
                ET.SubElement(root, 'EventKey').text = "mock_menu_id"
                
        xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
        
        if self.encrypted and CONFIG['wechat']['aes_key']:
            crypto = WeChatCrypto(
                CONFIG['wechat']['token'], 
                CONFIG['wechat']['aes_key'], 
                CONFIG['wechat']['app_id']
            )
            encrypted_text = crypto.encrypt(xml_str)
            
            new_root = ET.Element('xml')
            ET.SubElement(new_root, 'ToUserName').text = f"gh_{CONFIG['wechat']['app_id'][-8:]}"
            ET.SubElement(new_root, 'Encrypt').text = encrypted_text
            
            timestamp = str(int(time.time()))
            nonce = str(int(time.time()))[-6:]
            
            params = [CONFIG['wechat']['token'], timestamp, nonce, encrypted_text]
            params.sort()
            signature = hashlib.sha1(''.join(params).encode()).hexdigest()
            
            ET.SubElement(new_root, 'MsgSignature').text = signature
            ET.SubElement(new_root, 'TimeStamp').text = timestamp
            ET.SubElement(new_root, 'Nonce').text = nonce
            
            return ET.tostring(new_root, encoding='utf-8')
        
        return xml_str.encode('utf-8')

    def to_dict(self):
        """转换为字典格式便于JSON传输"""
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "media_id": self.media_id,
            "create_time": self.create_time,
            "user_id": self.user_id,
            "encrypted": self.encrypted
        }

def parse_xml_response(xml_str):
    """解析XML响应为字典"""
    debug_info = {
        "original_type": str(type(xml_str)),
        "original_repr": repr(xml_str)[:200],
    }
    
    try:
        # 处理字节串
        if isinstance(xml_str, bytes):
            debug_info["is_bytes"] = True
            debug_info["bytes_length"] = len(xml_str)
            xml_str = xml_str.decode('utf-8')
        else:
            debug_info["is_bytes"] = False
        
        # 解析 XML
        root = ET.fromstring(xml_str.encode('utf-8') if isinstance(xml_str, str) else xml_str)
        result = {"_debug": debug_info}
        
        for child in root:
            text = child.text or ""
            if text.startswith("<![CDATA[") and text.endswith("]]>"):
                text = text[9:-3]
            result[child.tag] = text
        
        return result
    except Exception as e:
        print(f"解析XML失败: {e}")
        debug_info["error"] = str(e)
        return {"error": str(e), "raw": str(xml_str)[:200], "_debug": debug_info}

class MockWechatHandler:
    """模拟微信消息处理"""
    def __init__(self):
        self.channel = WechatChannel() if WechatChannel else None
        
    def handle_message(self, msg):
        """处理模拟消息"""
        xml_msg = msg.to_xml()
        
        if self.channel:
            try:
                print(f"\n{'='*60}")
                print(f"[DEBUG] 本地处理消息")
                print(f"发送的XML:\n{xml_msg.decode('utf-8') if isinstance(xml_msg, bytes) else xml_msg}")
                
                wechat_msg = WechatMessage(xml_msg)
                reply_text = self.channel._handle(wechat_msg)
                
                print(f"收到回复 (类型: {type(reply_text)}):")
                print(f"原始内容: {repr(reply_text)}")
                print(f"显示内容: {reply_text}")
                
                if isinstance(reply_text, bytes):
                    print(f"字节内容: {reply_text}")
                    print(f"UTF-8解码: {reply_text.decode('utf-8')}")
                
                print(f"{'='*60}\n")
                
                return reply_text
            except Exception as e:
                print(f"处理消息时出错: {e}")
                import traceback
                traceback.print_exc()
                return f"处理失败: {str(e)}"
        else:
            if msg.type == 'text':
                return f"收到文本消息: {msg.content}"
            else:
                return f"收到{msg.type}类型消息"
    
    def forward_to_service(self, msg):
        """转发消息到实际服务"""
        try:
            xml_data = msg.to_xml()
            
            timestamp = str(int(time.time()))
            nonce = str(int(time.time()))[-6:]
            
            params = [CONFIG['wechat']['token'], timestamp, nonce]
            params.sort()
            signature = hashlib.sha1(''.join(params).encode()).hexdigest()
            
            url = f"{CONFIG['server']['service_url']}?signature={signature}&timestamp={timestamp}&nonce={nonce}"
            
            print(f"[{time.strftime('%H:%M:%S')}] 转发消息到: {url}")
            print(f"[{time.strftime('%H:%M:%S')}] 发送的XML:\n{xml_data.decode('utf-8')}")
            start_time = time.time()
            
            headers = {'Content-Type': 'text/xml; charset=utf-8'}
            timeout = CONFIG['server'].get('timeout', 60)
            response = requests.post(url, data=xml_data, headers=headers, timeout=timeout, verify=False)
            
            elapsed_time = time.time() - start_time
            
            # ✅ 关键修复：强制使用UTF-8编码
            response.encoding = 'utf-8'
            
            # 或者直接从字节内容解码（更可靠）
            response_text = response.content.decode('utf-8')
            
            print(f"\n{'='*60}")
            print(f"[{time.strftime('%H:%M:%S')}] 收到响应 (耗时: {elapsed_time:.2f}秒)")
            print(f"状态码: {response.status_code}")
            print(f"响应头 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            # print(f"requests自动检测的编码: {response.apparent_encoding}")
            print(f"响应内容:\n{response_text[:200]}")
            print(f"{'='*60}\n")
            
            if response.status_code == 200:
                return response_text  # ✅ 返回正确编码的文本
            else:
                return f"转发失败: HTTP {response.status_code}"
        except requests.exceptions.Timeout:
            return f"转发超时: 请求超过{CONFIG['server'].get('timeout', 60)}秒"
        except requests.exceptions.ConnectionError as e:
            return f"连接错误: {str(e)}"
        except Exception as e:
            print(f"转发异常: {e}")
            import traceback
            traceback.print_exc()
            return f"转发错误: {str(e)}"

class MockServerHandler(SimpleHTTPRequestHandler):
    """Web界面处理器"""
    def __init__(self, *args, **kwargs):
        self.mock_handler = MockWechatHandler()
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            with open('mock_wechat_ui.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/config':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(CONFIG).encode())
        elif self.path.startswith('/wechat'):
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            signature = query_params.get('signature', [''])[0]
            timestamp = query_params.get('timestamp', [''])[0]
            nonce = query_params.get('nonce', [''])[0]
            echostr = query_params.get('echostr', [''])[0]
            
            if self._check_signature(signature, timestamp, nonce):
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(echostr.encode('utf-8'))
            else:
                self.send_response(403)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/send_message':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = json.loads(post_data)
            
            if 'config' in params:
                temp_config = params['config']
                for section in temp_config:
                    if section in CONFIG:
                        for key, value in temp_config[section].items():
                            CONFIG[section][key] = value
            
            msg = MockMessage(
                msg_type=params.get('type', 'text'),
                content=params.get('content', ''),
                media_id=params.get('media_id', ''),
                user_id=params.get('user_id', 'mock_user'),
                encrypted=params.get('encrypted', False)
            )
            
            start_time = time.time()
            
            try:
                if params.get('forward', False):
                    result = self.mock_handler.forward_to_service(msg)
                else:
                    result = self.mock_handler.handle_message(msg)
                
                elapsed_time = time.time() - start_time
                
                # ✅ 收集调试信息
                debug_info = {
                    "result_type": str(type(result)),
                    "result_repr": repr(result)[:500],
                    "result_length": len(result) if result else 0,
                }
                
                # 尝试不同方式处理结果
                if isinstance(result, bytes):
                    debug_info["is_bytes"] = True
                    result_str = result.decode('utf-8')
                    debug_info["decoded_utf8"] = result_str[:200]
                else:
                    debug_info["is_bytes"] = False
                    result_str = str(result)
                
                # 解析响应
                parsed_response = parse_xml_response(result)
                
                # 提取显示内容
                display_content = ""
                if parsed_response and 'Content' in parsed_response:
                    display_content = parsed_response['Content']
                elif parsed_response and 'MsgType' in parsed_response:
                    display_content = f"收到{parsed_response['MsgType']}类型消息"
                else:
                    display_content = result_str[:500] if result else "无响应"
                
                response_data = {
                    'status': 'success', 
                    'response': result_str,
                    'response_raw': repr(result)[:500],  # ✅ 原始 repr
                    'parsed': parsed_response,
                    'display_content': display_content,
                    'sent_message': msg.to_dict(),
                    'elapsed_time': round(elapsed_time, 2),
                    'debug': debug_info  # ✅ 调试信息
                }
                
                # print(f"\n[DEBUG] 返回给前端的数据:")
                # print(json.dumps(response_data, ensure_ascii=False, indent=2))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                elapsed_time = time.time() - start_time
                print(f"处理消息异常: {e}")
                import traceback
                traceback.print_exc()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'error',
                    'error': str(e),
                    'error_traceback': traceback.format_exc(),
                    'sent_message': msg.to_dict(),
                    'elapsed_time': round(elapsed_time, 2)
                }, ensure_ascii=False).encode('utf-8'))
                
        elif self.path == '/update_config':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            new_config = json.loads(post_data)
            
            for section in new_config:
                if section in CONFIG:
                    for key, value in new_config[section].items():
                        CONFIG[section][key] = value
            
            print(f"配置已更新: {CONFIG}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'success',
                'config': CONFIG
            }).encode())
        elif self.path.startswith('/wechat'):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                root = ET.fromstring(post_data)
                
                encrypt_element = root.find('Encrypt')
                if encrypt_element is not None:
                    crypto = WeChatCrypto(
                        CONFIG['wechat']['token'], 
                        CONFIG['wechat']['aes_key'], 
                        CONFIG['wechat']['app_id']
                    )
                    decrypted_xml = crypto.decrypt(encrypt_element.text)
                    root = ET.fromstring(decrypted_xml)
                
                msg_type = root.find('MsgType').text
                from_user = root.find('FromUserName').text
                content = ''
                media_id = ''
                
                if msg_type == 'text':
                    content_element = root.find('Content')
                    if content_element is not None:
                        content = content_element.text
                elif msg_type in ['image', 'voice', 'video']:
                    media_element = root.find('MediaId')
                    if media_element is not None:
                        media_id = media_element.text
                
                msg = MockMessage(
                    msg_type=msg_type,
                    content=content,
                    media_id=media_id,
                    user_id=from_user
                )
                
                result = self.mock_handler.handle_message(msg)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/xml')
                self.end_headers()
                self.wfile.write(result.encode('utf-8'))
                
            except Exception as e:
                print(f"处理微信消息失败: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def _check_signature(self, signature, timestamp, nonce):
        """验证微信签名"""
        params = [CONFIG['wechat']['token'], timestamp, nonce]
        params.sort()
        sha1 = hashlib.sha1()
        sha1.update(''.join(params).encode())
        return sha1.hexdigest() == signature

def create_ui_file():
    """创建新的UI文件"""
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>微信公众号消息模拟器</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            flex-direction: column;
        }
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 15px 30px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        .header h1 {
            color: #07C160;
            font-size: 24px;
            margin: 0;
        }
        .container {
            display: flex;
            flex: 1;
            padding: 20px;
            gap: 20px;
            overflow: hidden;
        }
        .left-panel {
            flex: 3;
            display: flex;
            flex-direction: column;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        .right-panel {
            flex: 2;
            display: flex;
            flex-direction: column;
            gap: 20px;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 5px;
            scrollbar-width: thin;
            scrollbar-color: #07C160 #f0f2f5;
        }
        .right-panel::-webkit-scrollbar {
            width: 8px;
        }
        .right-panel::-webkit-scrollbar-track {
            background: #f0f2f5;
            border-radius: 4px;
        }
        .right-panel::-webkit-scrollbar-thumb {
            background: #07C160;
            border-radius: 4px;
        }
        .right-panel::-webkit-scrollbar-thumb:hover {
            background: #06AD56;
        }
        .config-section {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            flex: 1;
        }
        .input-section {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            flex: 1;
        }
        .chat-header {
            background: #07C160;
            color: white;
            padding: 15px 20px;
            font-weight: bold;
            font-size: 16px;
        }
        .chat-container {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f0f2f5;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .message {
            padding: 8px 12px;               /* ✅ 减小内边距 */
            border-radius: 8px;
            max-width: 60%;                  /* ✅ 最大宽度限制 */
            word-wrap: break-word;
            white-space: pre-wrap;
            word-break: break-word;
            animation: fadeIn 0.3s ease-out;
            display: inline-block;           /* ✅ 关键：让宽度适应内容 */
            width: fit-content;              /* ✅ 关键：宽度自适应内容 */
        }

        .user-message {
            background-color: #9EEA6A;
            align-self: flex-end;
        }

        .bot-message {
            background-color: white;
            align-self: flex-start;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }
        .message-time {
            font-size: 11px;
            opacity: 0.7;
            margin-top: 5px;
        }
        .message-type {
            font-size: 12px;
            background: rgba(0, 0, 0, 0.1);
            padding: 2px 6px;
            border-radius: 10px;
            margin-left: 8px;
        }
        .section-title {
            color: #07C160;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #07C160;
            font-size: 18px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #555;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #07C160;
        }
        textarea {
            resize: vertical;
            min-height: 80px;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 15px 0;
        }
        .checkbox-group input {
            width: auto;
        }
        .mode-selector {
            display: flex;
            gap: 10px;
            margin: 15px 0;
        }
        .mode-btn {
            flex: 1;
            padding: 10px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            text-align: center;
            transition: all 0.3s;
        }
        .mode-btn.active {
            border-color: #07C160;
            background: #e8f5e8;
            color: #07C160;
            font-weight: bold;
        }
        .btn {
            background: #07C160;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: background 0.3s;
            width: 100%;
        }
        .btn:hover {
            background: #06AD56;
        }
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .btn-secondary {
            background: #6c757d;
        }
        .btn-secondary:hover {
            background: #5a6268;
        }
        .action-buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .raw-data {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin-top: 10px;
            font-size: 12px;
            font-family: 'Courier New', monospace;
            align-self: stretch;
        }
        .raw-data summary {
            cursor: pointer;
            font-weight: bold;
            color: #07C160;
            margin-bottom: 10px;
            user-select: none;
        }
        .raw-data summary:hover {
            color: #06AD56;
        }
        .raw-data pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 400px;
            overflow-y: auto;
            background: white;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
            font-size: 12px;
            line-height: 1.5;
        }
        .copy-btn {
            padding: 4px 8px;
            background: #07C160;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            margin-left: 10px;
        }
        .copy-btn:hover {
            background: #06AD56;
        }
        .data-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
        }
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #07C160;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online {
            background: #07C160;
        }
        .status-offline {
            background: #dc3545;
        }
        .config-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .hidden {
            display: none;
        }
        @media (max-width: 1200px) {
            .container {
                flex-direction: column;
            }
            .left-panel {
                height: 400px;
                min-height: 400px;
            }
            .right-panel {
                flex-direction: row;
                overflow-x: auto;
                overflow-y: hidden;
            }
            .config-section,
            .input-section {
                min-width: 500px;
            }
        }
        @media (max-width: 768px) {
            .config-grid {
                grid-template-columns: 1fr;
            }
            .right-panel {
                flex-direction: column;
                overflow-x: hidden;
                overflow-y: auto;
            }
            .config-section,
            .input-section {
                min-width: auto;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 微信公众号消息模拟器</h1>
    </div>
    
    <div class="container">
        <!-- 左侧消息窗口 -->
        <div class="left-panel">
            <div class="chat-header">
                💬 消息窗口
                <span style="float: right; font-size: 12px;">
                    <span class="status-indicator status-online"></span>
                    在线
                </span>
            </div>
            <div class="chat-container" id="chatContainer">
                <div style="text-align: center; color: #999; padding: 40px;">
                    <div style="font-size: 48px; margin-bottom: 20px;">💭</div>
                    <h3>开始对话</h3>
                    <p>在右侧配置并发送消息开始测试</p>
                </div>
            </div>
        </div>
        
        <!-- 右侧面板 -->
        <div class="right-panel">            
            <!-- 输入区域 -->
            <div class="input-section">
                <h3 class="section-title">📝 消息发送</h3>
                
                <div class="form-group">
                    <label for="user_id">用户 ID</label>
                    <input type="text" id="user_id" value="mock_user_001" placeholder="发送消息的用户ID">
                </div>
                
                <div class="form-group">
                    <label for="msg_type">消息类型</label>
                    <select id="msg_type">
                        <option value="text">文本消息</option>
                        <option value="image">图片消息</option>
                        <option value="voice">语音消息</option>
                        <option value="video">视频消息</option>
                        <option value="location">位置消息</option>
                        <option value="link">链接消息</option>
                        <option value="event">事件消息</option>
                    </select>
                </div>
                
                <div class="form-group" id="content_group">
                    <label for="content">消息内容</label>
                    <textarea id="content" placeholder="请输入消息内容..."></textarea>
                </div>
                
                <div class="form-group hidden" id="media_id_group">
                    <label for="media_id">媒体 ID</label>
                    <input type="text" id="media_id" placeholder="留空将自动生成">
                </div>
                
                <div class="form-group hidden" id="event_type_group">
                    <label for="event_type">事件类型</label>
                    <select id="event_type">
                        <option value="subscribe">关注</option>
                        <option value="unsubscribe">取消关注</option>
                        <option value="SCAN">扫描二维码</option>
                        <option value="LOCATION">上报位置</option>
                        <option value="CLICK">点击菜单</option>
                        <option value="VIEW">查看菜单</option>
                    </select>
                </div>
                
                <div class="checkbox-group">
                    <input type="checkbox" id="encrypted">
                    <label for="encrypted">使用加密消息</label>
                </div>
                
                <button id="sendBtn" class="btn">📤 发送消息</button>
                <div style="text-align: center; margin-top: 10px; color: #666; font-size: 12px;">
                    提示：按 Enter 键快速发送消息
                </div>
            </div>
        </div>
    </div>

    <script>
        let isSending = false;
        let messageHistory = [];
        
        const DEFAULT_CONFIG = {
            app_id: "test_id",
            app_secret: "4321",
            aes_key: "1234",
            token: "sakura7301",
            target_ip: "127.0.0.1",
            target_port: "8081"
        };
        
        window.onload = function() {
            loadSavedConfig();
            setupEventListeners();
        };
        
        function loadSavedConfig() {
            const savedConfig = localStorage.getItem('wechat_mock_config');
            if (savedConfig) {
                const config = JSON.parse(savedConfig);
                document.getElementById('app_id').value = config.app_id || DEFAULT_CONFIG.app_id;
                document.getElementById('app_secret').value = config.app_secret || DEFAULT_CONFIG.app_secret;
                document.getElementById('aes_key').value = config.aes_key || DEFAULT_CONFIG.aes_key;
                document.getElementById('token').value = config.token || DEFAULT_CONFIG.token;
                document.getElementById('target_ip').value = config.target_ip || DEFAULT_CONFIG.target_ip;
                document.getElementById('target_port').value = config.target_port || DEFAULT_CONFIG.target_port;
            }
        }
        
        function setupEventListeners() {
            document.querySelectorAll('.mode-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    currentMode = this.dataset.mode;
                });
            });
            
            document.getElementById('msg_type').addEventListener('change', handleMessageTypeChange);
            document.getElementById('resetConfigBtn').addEventListener('click', resetConfig);
            document.getElementById('sendBtn').addEventListener('click', sendMessage);
            
            document.getElementById('content').addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }
        
        function handleMessageTypeChange() {
            const msgType = this.value;
            const contentGroup = document.getElementById('content_group');
            const mediaIdGroup = document.getElementById('media_id_group');
            const eventTypeGroup = document.getElementById('event_type_group');
            
            contentGroup.classList.add('hidden');
            mediaIdGroup.classList.add('hidden');
            eventTypeGroup.classList.add('hidden');
            
            if (msgType === 'text' || msgType === 'location' || msgType === 'link') {
                contentGroup.classList.remove('hidden');
            } else if (msgType === 'image' || msgType === 'voice' || msgType === 'video') {
                mediaIdGroup.classList.remove('hidden');
            } else if (msgType === 'event') {
                eventTypeGroup.classList.remove('hidden');
            }
        }
        
        function applyConfig() {
            const config = {
                app_id: document.getElementById('app_id').value,
                app_secret: document.getElementById('app_secret').value,
                aes_key: document.getElementById('aes_key').value,
                token: document.getElementById('token').value,
                target_ip: document.getElementById('target_ip').value,
                target_port: document.getElementById('target_port').value
            };
            
            localStorage.setItem('wechat_mock_config', JSON.stringify(config));
            
            fetch('/update_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    wechat: {
                        app_id: config.app_id,
                        app_secret: config.app_secret,
                        aes_key: config.aes_key,
                        token: config.token
                    },
                    server: {
                        service_url: `http://${config.target_ip}:${config.target_port}/wx`,
                        port: 8082,
                        timeout: 60
                    }
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showNotification('✅ 配置已更新', 'success');
                } else {
                    showNotification('❌ 更新失败', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('❌ 更新失败: ' + error.message, 'error');
            });
        }
        
        function resetConfig() {
            if (confirm('确定要重置为默认配置吗？')) {
                document.getElementById('app_id').value = DEFAULT_CONFIG.app_id;
                document.getElementById('app_secret').value = DEFAULT_CONFIG.app_secret;
                document.getElementById('aes_key').value = DEFAULT_CONFIG.aes_key;
                document.getElementById('token').value = DEFAULT_CONFIG.token;
                document.getElementById('target_ip').value = DEFAULT_CONFIG.target_ip;
                document.getElementById('target_port').value = DEFAULT_CONFIG.target_port;
                applyConfig();
            }
        }
        
        function sendMessage() {
            if (isSending) {
                showNotification('正在发送消息，请稍候...', 'warning');
                return;
            }
            
            const msgType = document.getElementById('msg_type').value;
            const userId = document.getElementById('user_id').value;
            let content = document.getElementById('content').value;
            const mediaId = document.getElementById('media_id').value;
            const encrypted = document.getElementById('encrypted').checked;
            const forward = 'remote';
            
            if (msgType === 'event') {
                content = document.getElementById('event_type').value;
            }
            
            if (!content && msgType === 'text') {
                showNotification('请输入消息内容', 'warning');
                return;
            }
            
            addMessageToChat('user', content || `[${msgType}消息]`, msgType);
            
            isSending = true;
            const sendBtn = document.getElementById('sendBtn');
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<span class="spinner"></span>发送中...';
            
            const config = {
                app_id: document.getElementById('app_id').value,
                app_secret: document.getElementById('app_secret').value,
                aes_key: document.getElementById('aes_key').value,
                token: document.getElementById('token').value,
                target_ip: document.getElementById('target_ip').value,
                target_port: document.getElementById('target_port').value
            };
            
            const startTime = Date.now();
            
            fetch('/send_message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: msgType,
                    content: content,
                    media_id: mediaId,
                    user_id: userId,
                    encrypted: encrypted,
                    forward: forward,
                    config: {
                        wechat: {
                            app_id: config.app_id,
                            app_secret: config.app_secret,
                            aes_key: config.aes_key,
                            token: config.token
                        },
                        server: {
                            service_url: `http://${config.target_ip}:${config.target_port}/wx`,
                            timeout: 60
                        }
                    }
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
                
                console.log('=== 收到的响应数据 ===');
                console.log('完整data:', data);
                console.log('data.response:', data.response);
                console.log('data.response类型:', typeof data.response);
                
                if (data.status === 'success') {
                    const displayContent = data.display_content || '收到回复';
                    addMessageToChat('bot', displayContent, data.parsed?.MsgType || 'text', elapsedTime);
                    
                    messageHistory.push({
                        sent: data.sent_message,
                        received: data.parsed,
                        raw: data.response,
                        elapsed: data.elapsed_time || elapsedTime
                    });
                    
                    showRawData(data.sent_message, data.parsed, data.response);
                } else {
                    addMessageToChat('bot', `❌ 错误: ${data.error || '未知错误'}`, 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                addMessageToChat('bot', `❌ 网络错误: ${error.message}`, 'error');
            })
            .finally(() => {
                isSending = false;
                sendBtn.disabled = false;
                sendBtn.innerHTML = '📤 发送消息';
                
                if (msgType === 'text') {
                    document.getElementById('content').value = '';
                }
            });
        }
        
        function addMessageToChat(sender, content, msgType, elapsedTime = null) {
            const chatContainer = document.getElementById('chatContainer');
            
            const welcomeMsg = chatContainer.querySelector('[style*="text-align: center"]');
            if (welcomeMsg) {
                chatContainer.innerHTML = '';
            }
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender === 'user' ? 'user-message' : 'bot-message'}`;
            
            let typeBadge = '';
            if (msgType && msgType !== 'text') {
                typeBadge = `<span class="message-type">${msgType}</span>`;
            }
            
            let timeBadge = '';
            if (elapsedTime) {
                timeBadge = `<div class="message-time">${elapsedTime}s</div>`;
            }
            
            messageDiv.innerHTML = `
                ${content}
                ${typeBadge}
                ${timeBadge}
            `;
            
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        function escapeHtml(text) {
            if (!text) return '(无数据)';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function copyToClipboard(text, event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            navigator.clipboard.writeText(text).then(() => {
                showNotification('✅ 已复制到剪贴板', 'success');
            }).catch(err => {
                console.error('复制失败:', err);
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                try {
                    document.execCommand('copy');
                    showNotification('✅ 已复制到剪贴板', 'success');
                } catch (e) {
                    showNotification('❌ 复制失败', 'error');
                }
                document.body.removeChild(textarea);
            });
        }
        
        function showRawData(sent, received, raw) {
            const chatContainer = document.getElementById('chatContainer');
            
            console.log('showRawData 参数:', {sent, received, raw});
            console.log('raw长度:', raw ? raw.length : 0);
            
            const rawDataDiv = document.createElement('div');
            rawDataDiv.className = 'raw-data';
            
            const sentJson = JSON.stringify(sent, null, 2);
            const receivedJson = JSON.stringify(received, null, 2);
            const rawText = typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2);
            
            rawDataDiv.innerHTML = `
                <details>
                    <summary>📋 查看原始数据 (点击展开)</summary>
                    
                    <div style="margin-top: 10px;">
                        <div class="data-header">
                            <strong>发送的数据:</strong>
                            <button class="copy-btn" onclick='copyToClipboard(${JSON.stringify(sentJson)}, event)'>📋 复制</button>
                        </div>
                        <pre>${escapeHtml(sentJson)}</pre>
                    </div>
                    
                    <div style="margin-top: 15px;">
                        <div class="data-header">
                            <strong>接收的数据:</strong>
                        </div>
                        <pre>${escapeHtml(receivedJson)}</pre>
                    </div>
                    
                    <div style="margin-top: 15px;">
                        <div class="data-header">
                            <strong>原始XML (${rawText.length} 字符):</strong>
                            <button class="copy-btn" onclick='copyToClipboard(${JSON.stringify(rawText)}, event)'>📋 复制</button>
                        </div>
                        <pre>${escapeHtml(rawText)}</pre>
                    </div>
                </details>
            `;
            
            chatContainer.appendChild(rawDataDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 12px 20px;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                z-index: 1000;
                animation: slideIn 0.3s ease-out;
            `;
            
            const colors = {
                success: '#07C160',
                error: '#dc3545',
                warning: '#ffc107',
                info: '#17a2b8'
            };
            
            notification.style.backgroundColor = colors[type] || colors.info;
            notification.textContent = message;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.remove();
            }, 3000);
        }
    </script>
</body>
</html>
'''
    with open('mock_wechat_ui.html', 'w', encoding='utf-8') as f:
        f.write(html)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='微信公众号消息模拟器')
    
    parser.add_argument('--port', type=int, help='模拟器端口')
    parser.add_argument('--service-url', type=str, help='实际服务URL')
    parser.add_argument('--timeout', type=int, default=60, help='请求超时时间（秒）')
    
    parser.add_argument('--app-id', type=str, help='微信公众号AppID')
    parser.add_argument('--app-secret', type=str, help='微信公众号AppSecret')
    parser.add_argument('--aes-key', type=str, help='微信公众号AES密钥')
    parser.add_argument('--token', type=str, help='微信公众号Token')
    
    return parser.parse_args()

def start_mock_server():
    """启动模拟服务器"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    create_ui_file()
    server_address = ('', CONFIG['server']['port'])
    httpd = HTTPServer(server_address, MockServerHandler)
    print(f'''
============================================================
🚀 微信公众号模拟器已启动!

📱 访问地址: http://localhost:{CONFIG['server']['port']}/

🔑 当前配置:
  - AppID: {CONFIG['wechat']['app_id']}
  - Token: {CONFIG['wechat']['token']}
  - AES Key: {CONFIG['wechat']['aes_key']}
  - App Secret: {CONFIG['wechat']['app_secret']}
  - 服务URL: {CONFIG['server']['service_url']}
  - 超时时间: {CONFIG['server'].get('timeout', 60)}秒
============================================================
    ''')
    
    threading.Timer(1, lambda: webbrowser.open(f'http://localhost:{CONFIG["server"]["port"]}/')).start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")

if __name__ == '__main__':
    try:
        try:
            from Crypto.Cipher import AES
        except ImportError:
            print("⚠️ 缺少必要依赖: pycryptodome")
            print("请安装: pip install pycryptodome")
            sys.exit(1)
        
        try:
            import requests
        except ImportError:
            print("⚠️ 缺少必要依赖: requests")
            print("请安装: pip install requests")
            sys.exit(1)
        
        # 从配置文件加载配置
        load_config_from_files()
        
        args = parse_args()
        
        # 命令行参数覆盖配置
        if args.port:
            CONFIG['server']['port'] = args.port
        if args.service_url:
            CONFIG['server']['service_url'] = args.service_url
        if args.timeout:
            CONFIG['server']['timeout'] = args.timeout
        if args.app_id:
            CONFIG['wechat']['app_id'] = args.app_id
        if args.app_secret:
            CONFIG['wechat']['app_secret'] = args.app_secret
        if args.aes_key:
            CONFIG['wechat']['aes_key'] = args.aes_key
        if args.token:
            CONFIG['wechat']['token'] = args.token
        
        start_mock_server()
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()