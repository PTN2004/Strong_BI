#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📦 Đang trích xuất dữ liệu từ Docker...${NC}"

# Tạo thư mục chứa data
mkdir -p db-seed

# 1. Trích xuất Postgres
echo "Đang export Postgres..."
docker exec strongbi-postgres pg_dump -U postgres strongbi_auth -c > db-seed/postgres.sql || echo "⚠️ Lỗi khi export Postgres (có thể container chưa chạy hoặc chưa có data)"

# 2. Trích xuất FalkorDB (Graph Schema - nếu có dùng)
echo "Đang export FalkorDB (nếu có dùng)..."
docker exec strongbi-falkordb redis-cli SAVE >/dev/null 2>&1 || echo "⚠️ Bỏ qua FalkorDB (không hoạt động hoặc không dùng)"
docker cp strongbi-falkordb:/data/dump.rdb db-seed/dump.rdb >/dev/null 2>&1 || true

# 3. Trích xuất Neo4j
echo "Đang export Neo4j (Graph Database chính)..."
# Cần dùng cypher-shell kết nối vào system để dừng tạm database (phiên bản Neo4j 5 enterprise cho phép)
docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "STOP DATABASE neo4j;" >/dev/null 2>&1 || echo "⚠️ Có thể neo4j đã dừng"
# Xoá file dump cũ bên trong container nếu có
docker exec strongbi-neo4j rm -f /var/lib/neo4j/import/neo4j.dump
# Chạy lệnh dump ra thư mục import bên trong container
docker exec strongbi-neo4j neo4j-admin database dump neo4j --to-path=/var/lib/neo4j/import
# Copy file ra thư mục db-seed
docker cp strongbi-neo4j:/var/lib/neo4j/import/neo4j.dump db-seed/neo4j.dump || echo "⚠️ Không thể copy neo4j.dump"
# Mở lại database
docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "START DATABASE neo4j;" >/dev/null 2>&1 || true

echo -e "${GREEN}✅ Đã xuất dữ liệu thành công ra thư mục 'db-seed/'!${NC}"
echo "👉 Bạn hãy commit thư mục 'db-seed/' này lên Github."
echo "👉 Lần tới khi sếp CTO chạy file start.sh, nó sẽ tự động nạp (seed) data này vào Database."
