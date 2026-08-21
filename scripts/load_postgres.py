import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from api.core.schema_loader import load_database

async def main():
    print("⏳ Đang quét cấu trúc Database từ Postgres...")
    url = "postgresql://postgres:password123@192.168.1.5:5434/dms"
    
    # We will consume the generator to completion
    generator = await load_database(url, "cli_user")
    
    try:
        while True:
            item = await generator.__anext__()
            # print(item)
    except StopAsyncIteration:
        pass
        
    print("✅ Đã hoàn tất nạp Table và Column vào Graph!")
    print("🔄 Đang liên kết lại Semantic Layer...")
    
    # Now run semantic
    import subprocess
    subprocess.run(["uv", "run", "python", "scripts/load_semantic.py"])
    print("🎉 Hoàn tất toàn bộ hệ thống!")

if __name__ == "__main__":
    asyncio.run(main())
