"""_项目日志库，定义日志系统行为，采用 loguru 实现。_
"""

from .logger import logger as TaPetKeyLogger
import sys

TaPetKeyLogger.add("app.log")

TaPetKeyLogger.add(sys.stdout)

TaPetKeyLogger.remove(0)  # 移除默认处理器
TaPetKeyLogger.add(
    "logs/{time:YYYY-MM-DD-HH-mm-ss}.log",  # 文件名格式
    retention="1 days",     # 保留1天
    delay=True              # 有日志才创建文件
)
__all__ = [
    'TaPetKeyLogger'
]