# encoding:utf-8

import importlib
import importlib.util
import json
import os
import sys

from common.log import logger
from common.singleton import singleton
from common.sorted_dict import SortedDict
from config import conf, remove_plugin_config, write_plugin_config

from .event import *


@singleton
class PluginManager:
    def __init__(self):
        self.plugins = SortedDict(lambda k, v: v.priority, reverse=True)
        self.listening_plugins = {}
        self.instances = {}
        self.pconf = {}
        self.current_plugin_path = None
        self.loaded = {}

    def register(self, name: str, desire_priority: int = 0, **kwargs):
        def wrapper(plugincls):
            plugincls.name = name
            plugincls.priority = desire_priority
            plugincls.desc = kwargs.get("desc")
            plugincls.author = kwargs.get("author")
            plugincls.path = self.current_plugin_path
            plugincls.version = kwargs.get("version") if kwargs.get("version") != None else "1.0"
            plugincls.namecn = kwargs.get("namecn") if kwargs.get("namecn") != None else name
            plugincls.hidden = kwargs.get("hidden") if kwargs.get("hidden") != None else False
            plugincls.enabled = True
            if self.current_plugin_path == None:
                raise Exception("Plugin path not set")
            self.plugins[name.upper()] = plugincls
            logger.info("Plugin %s_v%s registered, path=%s" % (name, plugincls.version, plugincls.path))

        return wrapper

    def save_config(self):
        with open("./plugins/plugins.json", "w", encoding="utf-8") as f:
            json.dump(self.pconf, f, indent=4, ensure_ascii=False)

    def load_config(self):
        logger.info("Loading plugins config...")

        modified = False
        if os.path.exists("./plugins/plugins.json"):
            with open("./plugins/plugins.json", "r", encoding="utf-8") as f:
                pconf = json.load(f)
                pconf["plugins"] = SortedDict(lambda k, v: v["priority"], pconf["plugins"], reverse=True)
        else:
            modified = True
            pconf = {"plugins": SortedDict(lambda k, v: v["priority"], reverse=True)}
        self.pconf = pconf
        if modified:
            self.save_config()
        return pconf

    @staticmethod
    def _load_all_config():
        """
        背景: 目前插件配置存放于每个插件目录的config.json下，docker运行时不方便进行映射，故增加统一管理的入口，优先
        加载 plugins/config.json，原插件目录下的config.json 不受影响

        从 plugins/config.json 中加载所有插件的配置并写入 config.py 的全局配置中，供插件中使用
        插件实例中通过 config.pconf(plugin_name) 即可获取该插件的配置
        """
        all_config_path = "./plugins/config.json"
        try:
            if os.path.exists(all_config_path):
                # read from all plugins config
                with open(all_config_path, "r", encoding="utf-8") as f:
                    all_conf = json.load(f)
                    logger.info(f"load all config from plugins/config.json: {all_conf}")

                # write to global config
                write_plugin_config(all_conf)
        except Exception as e:
            logger.error(e)

    def scan_plugins(self):
        logger.info("Scaning plugins ...")
        plugins_dir = "./plugins"
        raws = [self.plugins[name] for name in self.plugins]
        for plugin_name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, plugin_name)
            if os.path.isdir(plugin_path):
                # 判断插件是否包含同名__init__.py文件
                main_module_path = os.path.join(plugin_path, "__init__.py")
                if os.path.isfile(main_module_path):
                    # 导入插件
                    import_path = "plugins.{}".format(plugin_name)
                    try:
                        self.current_plugin_path = plugin_path
                        if plugin_path in self.loaded:
                            if plugin_name.upper() != 'GODCMD':
                                logger.info("reload module %s" % plugin_name)
                                self.loaded[plugin_path] = importlib.reload(sys.modules[import_path])
                                dependent_module_names = [name for name in sys.modules.keys() if name.startswith(import_path + ".")]
                                for name in dependent_module_names:
                                    logger.info("reload module %s" % name)
                                    importlib.reload(sys.modules[name])
                        else:
                            self.loaded[plugin_path] = importlib.import_module(import_path)
                        self.current_plugin_path = None
                    except Exception as e:
                        logger.warn("Failed to import plugin %s: %s" % (plugin_name, e))
                        continue
        pconf = self.pconf
        news = [self.plugins[name] for name in self.plugins]
        new_plugins = list(set(news) - set(raws))
        modified = False
        for name, plugincls in self.plugins.items():
            rawname = plugincls.name
            if rawname not in pconf["plugins"]:
                modified = True
                logger.info("Plugin %s not found in pconfig, adding to pconfig..." % name)
                pconf["plugins"][rawname] = {
                    "enabled": plugincls.enabled,
                    "priority": plugincls.priority,
                }
            else:
                self.plugins[name].enabled = pconf["plugins"][rawname]["enabled"]
                self.plugins[name].priority = pconf["plugins"][rawname]["priority"]
                self.plugins._update_heap(name)  # 更新下plugins中的顺序
        if modified:
            self.save_config()
        return new_plugins

    def refresh_order(self):
        for event in self.listening_plugins.keys():
            self.listening_plugins[event].sort(key=lambda name: self.plugins[name].priority, reverse=True)

    def activate_plugins(self):  # 生成新开启的插件实例
        failed_plugins = []
        for name, plugincls in self.plugins.items():
            if plugincls.enabled:
                if 'GODCMD' in self.instances and name == 'GODCMD':
                    continue
                # if name not in self.instances:
                try:
                    instance = plugincls()
                except Exception as e:
                    logger.warn("Failed to init %s, diabled. %s" % (name, e))
                    self.disable_plugin(name)
                    failed_plugins.append(name)
                    continue
                if name in self.instances:
                    self.instances[name].handlers.clear()
                self.instances[name] = instance
                for event in instance.handlers:
                    if event not in self.listening_plugins:
                        self.listening_plugins[event] = []
                    self.listening_plugins[event].append(name)
        self.refresh_order()
        return failed_plugins

    def reload_plugin(self, name: str):
        name = name.upper()
        remove_plugin_config(name)
        if name in self.instances:
            for event in self.listening_plugins:
                if name in self.listening_plugins[event]:
                    self.listening_plugins[event].remove(name)
            if name in self.instances:
                self.instances[name].handlers.clear()
            del self.instances[name]
            self.activate_plugins()
            return True
        return False

    def load_plugins(self):
        self.load_config()
        self.scan_plugins()
        # 加载全量插件配置
        self._load_all_config()
        pconf = self.pconf
        logger.debug("plugins.json config={}".format(pconf))
        for name, plugin in pconf["plugins"].items():
            if name.upper() not in self.plugins:
                logger.error("Plugin %s not found, but found in plugins.json" % name)
        self.activate_plugins()

    def emit_event(self, e_context: EventContext, *args, **kwargs):
        if e_context.event in self.listening_plugins:
            for name in self.listening_plugins[e_context.event]:
                if self.plugins[name].enabled and e_context.action == EventAction.CONTINUE:
                    logger.debug("Plugin %s triggered by event %s" % (name, e_context.event))
                    instance = self.instances[name]
                    instance.handlers[e_context.event](e_context,*args,**kwargs)
                    if e_context.is_break():
                        e_context["breaked_by"] = name
                        logger.debug("Plugin %s breaked event %s" % (name, e_context.event))
        return e_context

    def set_plugin_priority(self, name: str, priority: int):
        name = name.upper()
        if name not in self.plugins:
            return False
        if self.plugins[name].priority == priority:
            return True
        self.plugins[name].priority = priority
        self.plugins._update_heap(name)
        rawname = self.plugins[name].name
        self.pconf["plugins"][rawname]["priority"] = priority
        self.pconf["plugins"]._update_heap(rawname)
        self.save_config()
        self.refresh_order()
        return True

    def enable_plugin(self, name: str):
        name = name.upper()
        if name not in self.plugins:
            return False, "插件不存在"
        if not self.plugins[name].enabled:
            self.plugins[name].enabled = True
            rawname = self.plugins[name].name
            self.pconf["plugins"][rawname]["enabled"] = True
            self.save_config()
            failed_plugins = self.activate_plugins()
            if name in failed_plugins:
                return False, "插件开启失败"
            return True, "插件已开启"
        return True, "插件已开启"

    def disable_plugin(self, name: str):
        name = name.upper()
        if name not in self.plugins:
            return False
        if self.plugins[name].enabled:
            self.plugins[name].enabled = False
            rawname = self.plugins[name].name
            self.pconf["plugins"][rawname]["enabled"] = False
            self.save_config()
            return True
        return True

    def list_plugins(self):
        return self.plugins

    def _normalize_github_url(self, repo_url):
        """
        标准化 GitHub 仓库地址为 HTTPS 格式
        
        支持的输入格式：
        - git@github.com:user/repo.git
        - https://github.com/user/repo.git
        - https://github.com/user/repo
        """
        # SSH 格式转换: git@github.com:user/repo.git -> https://github.com/user/repo.git
        if repo_url.startswith('git@github.com:'):
            repo_url = repo_url.replace('git@github.com:', 'https://github.com/')
        
        # 确保有 https:// 前缀
        if repo_url.startswith('github.com/'):
            repo_url = 'https://' + repo_url
        
        # 确保有 .git 后缀
        if not repo_url.endswith('.git'):
            repo_url += '.git'
        
        return repo_url

    def _download_github_zip(self, user: str, repo_name: str, target_dir: str):
        """
        通过下载 ZIP 文件的方式安装 GitHub 仓库（使用可用的镜像）
        
        Args:
            user: GitHub 用户名
            repo_name: 仓库名
            target_dir: 目标目录
        
        Returns:
            bool: 是否成功
        """
        try:
            import requests
            import zipfile
            from io import BytesIO
            import shutil
        except ImportError as e:
            logger.warning(f"requests 或 zipfile 未安装，无法使用 ZIP 下载方式: {e}")
            return False
        
        # 尝试的分支列表
        branches = ['main', 'master']
        
        # 镜像列表（只使用你网络环境下可用的镜像）
        mirrors = [
            ("ghps.cc", "https://ghps.cc/"),
            ("gh-proxy.com", "https://gh-proxy.com/"),
            ("GitHub 直连", "")  # 原始地址作为最后备选
        ]
        
        for branch in branches:
            # 构建原始 ZIP URL
            original_zip_url = f"https://github.com/{user}/{repo_name}/archive/refs/heads/{branch}.zip"
            
            for mirror_name, mirror_prefix in mirrors:
                try:
                    download_url = mirror_prefix + original_zip_url if mirror_prefix else original_zip_url
                    
                    logger.info(f"尝试从 {mirror_name} 下载 {branch} 分支")
                    logger.info(f"下载地址: {download_url}")
                    
                    # 下载 ZIP（30秒超时）
                    response = requests.get(
                        download_url, 
                        timeout=30, 
                        stream=True,
                        allow_redirects=True
                    )
                    
                    if response.status_code != 200:
                        logger.warning(f"{mirror_name} 返回状态码: {response.status_code}")
                        continue
                    
                    # 读取内容
                    logger.info(f"正在下载... (使用 {mirror_name})")
                    content = BytesIO()
                    downloaded = 0
                    chunk_count = 0
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            content.write(chunk)
                            downloaded += len(chunk)
                            chunk_count += 1
                            # 每下载 1MB 输出一次进度
                            if chunk_count % 128 == 0:  # 128 * 8KB = 1MB
                                logger.info(f"已下载: {downloaded // 1024} KB")
                    
                    content.seek(0)
                    logger.info(f"✅ 下载完成，总大小: {downloaded // 1024} KB")
                    
                    # 解压 ZIP
                    logger.info("正在解压文件...")
                    with zipfile.ZipFile(content) as zip_ref:
                        namelist = zip_ref.namelist()
                        if not namelist:
                            raise Exception("ZIP 文件为空")
                        
                        root_dir = namelist[0].split('/')[0]
                        
                        # 解压到临时目录
                        temp_dir = os.path.join(os.path.dirname(target_dir), f"_temp_{repo_name}_{branch}")
                        
                        # 清理可能存在的临时目录
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                        
                        zip_ref.extractall(temp_dir)
                        
                        # 移动到目标目录
                        extracted_dir = os.path.join(temp_dir, root_dir)
                        
                        if not os.path.exists(extracted_dir):
                            raise Exception(f"解压后找不到目录: {extracted_dir}")
                        
                        shutil.move(extracted_dir, target_dir)
                        
                        # 清理临时目录
                        shutil.rmtree(temp_dir)
                    
                    logger.info(f"✅ 插件安装成功！使用 {mirror_name} ({branch} 分支)")
                    return True
                    
                except requests.Timeout:
                    logger.warning(f"{mirror_name} 下载超时（30秒）")
                    continue
                except requests.RequestException as e:
                    logger.warning(f"{mirror_name} 网络请求失败: {e}")
                    continue
                except zipfile.BadZipFile:
                    logger.warning(f"{mirror_name} 下载的文件不是有效的 ZIP 格式")
                    continue
                except Exception as e:
                    logger.warning(f"{mirror_name} 处理失败: {e}")
                    # 清理可能的残留文件
                    temp_dir = os.path.join(os.path.dirname(target_dir), f"_temp_{repo_name}_{branch}")
                    if os.path.exists(temp_dir):
                        try:
                            shutil.rmtree(temp_dir)
                        except:
                            pass
                    continue
        
        logger.error("所有 ZIP 下载方式都失败了")
        return False

    def install_plugin(self, repo: str):
        try:
            import common.package_manager as pkgmgr
            pkgmgr.check_dulwich()
        except Exception as e:
            logger.error("Failed to install plugin, {}".format(e))
            return False, "无法导入dulwich，安装插件失败"
        
        import re
        import shutil

        logger.info("开始安装插件: {}".format(repo))

        match = re.match(r"^(https?:\/\/|git@)([^\/:]+)[\/:]([^\/:]+)\/(.+?)(?:\.git)?$", repo)

        if not match:
            try:
                with open("./plugins/source.json", "r", encoding="utf-8") as f:
                    source = json.load(f)
                if repo in source["repo"]:
                    repo = source["repo"][repo]["url"]
                    match = re.match(r"^(https?:\/\/|git@)([^\/:]+)[\/:]([^\/:]+)\/(.+?)(?:\.git)?$", repo)
                    if not match:
                        return False, "安装插件失败，source中的仓库地址不合法"
                else:
                    return False, "安装插件失败，仓库地址不合法"
            except Exception as e:
                logger.error("Failed to install plugin, {}".format(e))
                return False, "安装插件失败，请检查仓库地址是否正确"
        
        user = match.group(3)
        repo_name = match.group(4)
        dirname = os.path.join("./plugins", repo_name)
        
        try:
            # 如果目录已存在，先删除
            if os.path.exists(dirname):
                logger.info(f"检测到插件目录已存在，删除旧版本: {dirname}")
                shutil.rmtree(dirname)
            
            install_success = False
            last_error = None
            
            if "github.com" in repo:
                logger.info(f"检测到 GitHub 仓库: {user}/{repo_name}")
                
                # 优先使用 ZIP 下载方式（更快更稳定）
                logger.info("使用 ZIP 下载方式安装...")
                install_success = self._download_github_zip(user, repo_name, dirname)
                
                if not install_success:
                    logger.warning("ZIP 下载失败，尝试使用 git clone...")
                    # ZIP 下载失败，尝试使用 dulwich（虽然可能会卡，但作为备选）
                    from dulwich import porcelain
                    
                    https_url = self._normalize_github_url(repo)
                    mirrors = [
                        ("gh-proxy.com", f"https://gh-proxy.com/{https_url}"),
                        ("GitHub", https_url)
                    ]
                    
                    for mirror_name, mirror_url in mirrors:
                        try:
                            logger.info(f"尝试 git clone: {mirror_name}")
                            porcelain.clone(mirror_url, dirname, checkout=True)
                            logger.info(f"✅ 克隆成功！使用 {mirror_name}")
                            install_success = True
                            break
                        except Exception as e:
                            last_error = e
                            logger.warning(f"{mirror_name} 克隆失败: {e}")
                            if os.path.exists(dirname):
                                shutil.rmtree(dirname)
                            continue
            else:
                # 非 GitHub 仓库，直接使用 dulwich
                from dulwich import porcelain
                try:
                    logger.info("克隆非 GitHub 仓库...")
                    porcelain.clone(repo, dirname, checkout=True)
                    install_success = True
                except Exception as e:
                    last_error = e
                    logger.error(f"克隆失败: {e}")
            
            if not install_success:
                raise last_error or Exception("所有安装方式都失败了，请检查网络连接")
            
            # 安装依赖（使用国内镜像源）
            requirements_file = os.path.join(dirname, "requirements.txt")
            if os.path.exists(requirements_file):
                logger.info("检测到 requirements.txt，正在安装依赖...")
                dep_success = self._install_requirements_with_mirror(requirements_file)
                if not dep_success:
                    logger.warning("依赖安装失败，但插件已下载成功，可以稍后手动安装依赖")
            
            return True, "✅ 安装插件成功！请使用 #scanp 命令扫描插件或重启程序。安装前请检查插件是否需要额外配置。"
            
        except Exception as e:
            logger.error("Failed to install plugin, {}".format(e))
            # 清理失败的目录
            if os.path.exists(dirname):
                try:
                    logger.info("清理失败的安装目录...")
                    shutil.rmtree(dirname)
                except Exception as cleanup_error:
                    logger.warning(f"清理目录失败: {cleanup_error}")
            return False, f"❌ 安装插件失败: {str(e)}"

    def _install_requirements_with_mirror(self, requirements_file: str):
        """
        使用国内镜像源安装依赖（带重试机制）
        
        Args:
            requirements_file: requirements.txt 文件路径
        
        Returns:
            bool: 是否安装成功
        """
        import subprocess
        
        # 国内 PyPI 镜像源列表（按速度和稳定性排序）
        pip_mirrors = [
            ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
            ("阿里云", "https://mirrors.aliyun.com/pypi/simple/"),
            ("中国科技大学", "https://pypi.mirrors.ustc.edu.cn/simple/"),
            ("腾讯云", "https://mirrors.cloud.tencent.com/pypi/simple"),
            ("豆瓣", "https://pypi.douban.com/simple/"),
            ("官方源", None)  # 最后尝试官方源
        ]
        
        for mirror_name, mirror_url in pip_mirrors:
            try:
                logger.info(f"尝试使用 {mirror_name} 镜像安装依赖...")
                
                # 构建 pip 安装命令
                cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
                
                # 如果有镜像源，添加参数
                if mirror_url:
                    cmd.extend(["-i", mirror_url, "--trusted-host", mirror_url.split("//")[1].split("/")[0]])
                
                # 添加超时和重试参数
                cmd.extend(["--timeout", "60", "--retries", "3"])
                
                logger.info(f"执行命令: {' '.join(cmd)}")
                
                # 执行安装
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                
                if result.returncode == 0:
                    logger.info(f"✅ 依赖安装成功！使用 {mirror_name}")
                    return True
                else:
                    logger.warning(f"{mirror_name} 安装失败: {result.stderr}")
                    continue
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"{mirror_name} 安装超时（5分钟）")
                continue
            except Exception as e:
                logger.warning(f"{mirror_name} 安装出错: {e}")
                continue
        
        logger.error("所有镜像源都安装失败")
        return False

    def update_plugin(self, name: str):
        try:
            import common.package_manager as pkgmgr

            pkgmgr.check_dulwich()
        except Exception as e:
            logger.error("Failed to install plugin, {}".format(e))
            return False, "无法导入dulwich，更新插件失败"
        from dulwich import porcelain

        name = name.upper()
        if name not in self.plugins:
            return False, "插件不存在"
        if name in [
            "HELLO",
            "GODCMD",
            "ROLE",
            "TOOL",
            "BDUNIT",
            "BANWORDS",
            "FINISH",
            "DUNGEON",
        ]:
            return False, "预置插件无法更新，请更新主程序仓库"
        dirname = self.plugins[name].path
        try:
            porcelain.pull(dirname, "origin")
            if os.path.exists(os.path.join(dirname, "requirements.txt")):
                logger.info("detect requirements.txt，installing...")
            pkgmgr.install_requirements(os.path.join(dirname, "requirements.txt"))
            return True, "更新插件成功，请重新运行程序"
        except Exception as e:
            logger.error("Failed to update plugin, {}".format(e))
            return False, "更新插件失败，" + str(e)

    def uninstall_plugin(self, name: str):
        name = name.upper()
        if name not in self.plugins:
            return False, "插件不存在"
        if name in self.instances:
            self.disable_plugin(name)
        dirname = self.plugins[name].path
        try:
            import shutil

            shutil.rmtree(dirname)
            rawname = self.plugins[name].name
            for event in self.listening_plugins:
                if name in self.listening_plugins[event]:
                    self.listening_plugins[event].remove(name)
            del self.plugins[name]
            del self.pconf["plugins"][rawname]
            self.loaded[dirname] = None
            self.save_config()
            return True, "卸载插件成功"
        except Exception as e:
            logger.error("Failed to uninstall plugin, {}".format(e))
            return False, "卸载插件失败，请手动删除文件夹完成卸载，" + str(e)