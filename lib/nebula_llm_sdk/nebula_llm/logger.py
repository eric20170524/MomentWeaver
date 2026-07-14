import logging

# 默认提供一个名为 nebula_llm 的 logger
# 使用者可以通过 logging.getLogger("nebula_llm") 获取并配置（如设置 level、handler 等）
logger = logging.getLogger("nebula_llm")

# 提供一个便捷的方法让 SDK 使用者可以一键配置基础控制台输出
def setup_default_logger(level=logging.INFO):
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
