import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        # Celery worker 已给 root 配好 handler 时只向上传播，避免同条日志打两遍
        # （一次走本 handler→stdout 被 Celery 再包一层，一次走 propagate→root）
        root = logging.getLogger()
        if root.handlers:
            logger.propagate = True
        else:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False

    if level is None:
        level = logging.INFO

    logger.setLevel(level)
    return logger


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
