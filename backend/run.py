"""服务启动入口：从 .env / config 读取 HOST/PORT 并绑定。

用法：
    python run.py            # 读取 .env 的 HOST/PORT（默认绑定 192 局域网 IP）

等价于：uvicorn app.main:app --host $HOST --port $PORT --reload
"""

import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
