import os
from dotenv import load_dotenv

load_dotenv()

from api.app_factory import create_app

app = create_app()

def main() -> None:
    import uvicorn

    debug_mode = os.environ.get('FASTAPI_DEBUG', 'False').lower() == 'true'
    uvicorn.run(
        "api.index:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=debug_mode,
        log_level="info" if debug_mode else "warning",
    )

if __name__ == "__main__":
    main()
