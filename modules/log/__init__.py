"""_项目日志库，定义日志系统行为，采用 loguru 实现。_
"""

from .logger import logger as TaPetKeyLogger
import sys

TaPetKeyLogger.add("app.log")

# 打包（--noconsole）运行时 sys.stdout 为 None，需跳过控制台输出
if sys.stdout is not None:
    TaPetKeyLogger.add(sys.stdout)

TaPetKeyLogger.remove(0)  # 移除默认处理器
TaPetKeyLogger.add(
    "app.log",  # 文件名格式
    retention="1 days",     # 保留1天
    delay=True              # 有日志才创建文件
)
__all__ = [
    'TaPetKeyLogger'
]