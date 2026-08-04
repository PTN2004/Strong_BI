#!/bin/bash

# Thư mục chứa dữ liệu BIRD
BIRD_DIR=${1:-"BIRD_data"}
JSON_FILE=${2:-"BIRD_data/dev.json"}
OUTPUT_FILE=${3:-"bird_results.json"}

echo "=========================================="
echo "🚀 Bắt đầu Pipeline Đánh giá Benchmark BIRD"
echo "Thư mục dữ liệu: $BIRD_DIR"
echo "Tệp đánh giá: $JSON_FILE"
echo "=========================================="

# 1. Chạy Preload Knowledge Graph
echo ""
echo "[1/2] Đang tạo Knowledge Graph từ các SQLite database..."
uv run python scripts/preload_bird_kg.py --db-dir "$BIRD_DIR"
if [ $? -ne 0 ]; then
    echo "❌ Lỗi trong quá trình tạo Knowledge Graph. Dừng pipeline."
    exit 1
fi
echo "✅ Hoàn tất tạo Knowledge Graph."

# 2. Chạy Evaluation
echo ""
echo "[2/2] Đang chạy đánh giá (Evaluation) e2e..."
uv run python run_benchmark.py --db-dir "$BIRD_DIR" --eval-json "$JSON_FILE" --mode e2e --output "$OUTPUT_FILE"
if [ $? -ne 0 ]; then
    echo "❌ Lỗi trong quá trình chạy đánh giá. Dừng pipeline."
    exit 1
fi

echo ""
echo "=========================================="
echo "🎉 Pipeline hoàn tất thành công!"
echo "📄 Xem chi tiết kết quả tại: $OUTPUT_FILE"
echo "=========================================="
