import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.config import Config
print(f"Testing embedding model: {Config.EMBEDDING_MODEL.model_name}")
try:
    res = Config.EMBEDDING_MODEL.embed(["hello world"])
    print("Success! Size:", len(res[0]))
except Exception as e:
    print("Error:", str(e))
    import traceback
    traceback.print_exc()
