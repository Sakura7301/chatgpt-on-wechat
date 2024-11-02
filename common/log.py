import logging
import sys


def _reset_logger(log):  
    # 清除现有的所有处理器  
    for handler in log.handlers:  
        handler.close()  
        log.removeHandler(handler)  
        del handler  
    log.handlers.clear()  
    
    # 设置不传播到父logger  
    log.propagate = False  
    
    # 只添加控制台处理器  
    console_handle = logging.StreamHandler(sys.stdout)  
    console_handle.setFormatter(  
        logging.Formatter(  
            "[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] - %(message)s",  
            datefmt="%Y-%m-%d %H:%M:%S",  
        )  
    )  
    log.addHandler(console_handle)


def _get_logger():
    log = logging.getLogger("log")
    _reset_logger(log)
    log.setLevel(logging.INFO)
    return log


# 日志句柄
logger = _get_logger()
