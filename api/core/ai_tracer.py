import json
import os
from datetime import datetime
import logging

def save_ai_trace(agent_name: str, input_data: dict, output_data: dict):
    try:
        log_dir = os.path.join(os.getcwd(), "logs", "ai_traces")
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = os.path.join(log_dir, f"{agent_name}_{timestamp_str}.json")
        
        # 3. Gom dữ liệu
        trace_data = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "inputs": input_data,
            "outputs": output_data
        }
        

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, ensure_ascii=False, indent=4, default=str)
            
    except Exception as e:

        logging.error(f"⚠️ Không thể lưu AI trace cho {agent_name}: {e}")