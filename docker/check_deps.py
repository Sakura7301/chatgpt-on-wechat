#!/usr/bin/env python3
"""
自动检测 plugins 目录下缺少的依赖并安装
"""
import os
import re
import sys
import ast
import subprocess
from pathlib import Path
from typing import Set, List

# Python 标准库列表（Python 3.10）
STDLIB_MODULES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
    'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
    'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
    'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
    'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
    'dis', 'distutils', 'doctest', 'email', 'encodings', 'enum', 'errno', 'faulthandler',
    'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'formatter', 'fractions', 'ftplib',
    'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib', 'grp',
    'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'idlelib', 'imaplib',
    'imghdr', 'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json',
    'keyword', 'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox',
    'mailcap', 'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib',
    'msvcrt', 'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator',
    'optparse', 'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle', 'pickletools',
    'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'posixpath',
    'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc',
    'queue', 'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
    'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
    'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd',
    'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct',
    'subprocess', 'sunau', 'symbol', 'symtable', 'sys', 'sysconfig', 'syslog',
    'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap',
    'threading', 'time', 'timeit', 'tkinter', 'token', 'tokenize', 'tomllib', 'trace',
    'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing',
    'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave',
    'weakref', 'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml',
    'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib', '_thread'
}

# 项目内部模块（根据项目结构）
PROJECT_MODULES = {
    'bridge', 'channel', 'common', 'config', 'plugins', 'lib', 'voice', 'bot'
}

# 包名映射（import 名 -> pip 包名）
PACKAGE_MAPPING = {
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'sklearn': 'scikit-learn',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
    'bs4': 'beautifulsoup4',
    'MySQLdb': 'mysqlclient',
    'psycopg2': 'psycopg2-binary',
    'lunar_python': 'lunar-python',
}


def extract_imports_from_file(filepath: Path) -> Set[str]:
    """从 Python 文件提取所有 import 的模块名"""
    imports = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用 AST 解析（更准确）
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # import xxx
                        module = alias.name.split('.')[0]
                        imports.add(module)
                elif isinstance(node, ast.ImportFrom):
                    # from xxx import yyy
                    if node.module and not node.module.startswith('.'):
                        module = node.module.split('.')[0]
                        imports.add(module)
        except SyntaxError:
            # 如果 AST 解析失败，使用正则表达式
            import_pattern = re.compile(r'^(?:from\s+([^\s.]+)|import\s+([^\s,]+))', re.MULTILINE)
            for match in import_pattern.finditer(content):
                module = match.group(1) or match.group(2)
                if module:
                    imports.add(module.split('.')[0])
    
    except Exception as e:
        print(f"⚠️  读取文件失败 {filepath}: {e}")
    
    return imports


def scan_plugins_dir(plugins_dir: str = 'plugins') -> Set[str]:
    """扫描 plugins 目录下所有 Python 文件的 import"""
    print(f"📂 扫描目录: {plugins_dir}")
    all_imports = set()
    
    plugins_path = Path(plugins_dir)
    if not plugins_path.exists():
        print(f"❌ 目录不存在: {plugins_dir}")
        return all_imports
    
    python_files = list(plugins_path.rglob('*.py'))
    print(f"📄 找到 {len(python_files)} 个 Python 文件")
    
    for filepath in python_files:
        imports = extract_imports_from_file(filepath)
        all_imports.update(imports)
    
    return all_imports

def filter_third_party_modules(imports: Set[str]) -> Set[str]:
    """过滤出第三方模块（排除标准库和项目模块）"""
    third_party = set()
    
    # 获取 plugins 目录下的所有子目录名和模块名
    plugins_dir = 'plugins' if os.path.exists('plugins') else '../plugins'
    plugin_dirs = {d.name for d in Path(plugins_dir).iterdir() if d.is_dir()}
    plugin_modules = set()
    
    # 递归获取插件目录下所有子模块名
    for plugin_dir in plugin_dirs:
        plugin_path = Path(plugins_dir) / plugin_dir
        for py_file in plugin_path.rglob('*.py'):
            if py_file.stem != '__init__':
                plugin_modules.add(py_file.stem)
    
    # 这些词可能是常见项目内部模块，不是 PyPI 包
    common_internal = {'main', 'plugin', 'utils', 'config', 'event', 'player', 'core', 'manager', 'summary', 'tool', 'shop'}
    
    for module in imports:
        # 跳过标准库
        if module in STDLIB_MODULES:
            continue
        # 跳过项目内部模块
        if module in PROJECT_MODULES:
            continue
        # 跳过私有模块
        if module.startswith('_'):
            continue
        # 跳过插件目录名
        if module in plugin_dirs:
            continue
        # 跳过插件子模块名
        if module in plugin_modules:
            continue
        # 跳过常见内部模块名
        if module in common_internal:
            continue
        
        third_party.add(module)
    
    return third_party

def check_missing_packages(modules: Set[str]) -> List[str]:
    """检查哪些包未安装"""
    missing = []
    
    print(f"\n🔍 检查 {len(modules)} 个第三方模块...")
    for module in sorted(modules):
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} - 未安装")
            missing.append(module)
    
    return missing


def get_pip_package_name(module: str) -> str:
    """获取 pip 包名（处理特殊映射）"""
    return PACKAGE_MAPPING.get(module, module)


def install_packages(packages: List[str], pip_mirror: str = "https://pypi.tuna.tsinghua.edu.cn/simple"):
    """安装缺失的包"""
    if not packages:
        print("\n✅ 所有依赖都已安装！")
        return True
    
    # 转换为 pip 包名
    pip_packages = [get_pip_package_name(pkg) for pkg in packages]
    
    print(f"\n📦 需要安装 {len(pip_packages)} 个包:")
    for pkg in pip_packages:
        print(f"  - {pkg}")
    
    # 构建安装命令
    cmd = [sys.executable, '-m', 'pip', 'install', '--no-cache-dir']
    cmd.extend(pip_packages)
    cmd.extend(['-i', pip_mirror])
    
    print(f"\n🚀 执行安装命令:")
    print(' '.join(cmd))
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print("\n✅ 安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 安装失败:")
        print(e.stderr)
        return False


def main():
    print("=" * 60)
    print("🔧 自动检测并安装 plugins 依赖")
    print("=" * 60)
    
    # 自动查找 plugins 目录（支持在项目根目录或 docker 子目录运行）
    if os.path.exists('plugins'):
        plugins_dir = 'plugins'
    elif os.path.exists('../plugins'):
        plugins_dir = '../plugins'
    else:
        print("❌ 找不到 plugins 目录！")
        sys.exit(1)
    
    # 1. 扫描 plugins 目录
    all_imports = scan_plugins_dir(plugins_dir)
    print(f"\n📊 共找到 {len(all_imports)} 个不同的 import")
    
    # 2. 过滤第三方模块
    third_party = filter_third_party_modules(all_imports)
    print(f"📊 其中 {len(third_party)} 个是第三方模块")
    
    # 3. 检查缺失的包
    missing = check_missing_packages(third_party)
    
    # 4. 安装缺失的包
    if missing:
        print("\n" + "=" * 60)
        
        # 检查是否自动安装模式
        auto_install = '--auto-install' in sys.argv or '-y' in sys.argv
        
        if auto_install:
            print(f"🤖 自动安装模式，将安装 {len(missing)} 个缺失的包")
            success = install_packages(missing)
            sys.exit(0 if success else 1)
        else:
            install = input(f"❓ 是否安装这 {len(missing)} 个缺失的包？(y/n): ").lower()
            if install == 'y':
                success = install_packages(missing)
                sys.exit(0 if success else 1)
            else:
                print("\n⏭️  跳过安装")
                print(f"\n手动安装命令:")
                pip_packages = [get_pip_package_name(pkg) for pkg in missing]
                print(f"pip3 install {' '.join(pip_packages)} -i https://pypi.tuna.tsinghua.edu.cn/simple")
                sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()