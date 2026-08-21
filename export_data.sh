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

# 3. Trích xuất Neo4j (TẤT CẢ Databases: dms, neo4j, strongbi-demo,...)
echo "Đang export toàn bộ Neo4j (Graph Databases)..."
# Lấy danh sách tất cả các databases (ngoại trừ system)
DATABASES=$(docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "SHOW DATABASES YIELD name WHERE name <> 'system' RETURN name;" | tail -n +2 | tr -d '"')

for db in $DATABASES; do
    echo "-> Đang xử lý database: $db"
    # Dừng tạm database
    docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "STOP DATABASE \`$db\`;" >/dev/null 2>&1 || true
    # Xoá file dump cũ nếu có
    docker exec strongbi-neo4j rm -f /var/lib/neo4j/import/$db.dump
    # Export (Dump)
    docker exec strongbi-neo4j neo4j-admin database dump $db --to-path=/var/lib/neo4j/import >/dev/null 2>&1 || echo "⚠️ Lỗi khi dump $db"
    # Copy ra ngoài
    docker cp strongbi-neo4j:/var/lib/neo4j/import/$db.dump db-seed/$db.dump || echo "⚠️ Không thể copy $db.dump"
    # Khởi động lại database
    docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "START DATABASE \`$db\`;" >/dev/null 2>&1 || true
done

echo -e "${GREEN}✅ Đã xuất dữ liệu thành công ra thư mục 'db-seed/'!${NC}"
echo "👉 Bạn hãy commit thư mục 'db-seed/' này lên Github."
echo "👉 Lần tới khi sếp CTO chạy file start.sh, nó sẽ tự động nạp (seed) data này vào Database."
