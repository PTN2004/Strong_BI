#!/usr/bin/env bash
set -e

# ==============================================================================
# Strong BI - Single-click Start Script for Local Development
# ==============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Khởi động hệ thống Strong BI...${NC}\n"

# 1. Tự động tạo file .env nếu chưa có
if [ ! -f ".env" ]; then
    if [ -f ".env.cto" ]; then
        echo -e "${YELLOW}⚙️  Tìm thấy file .env.cto, đang sử dụng làm cấu hình chính...${NC}"
        cp .env.cto .env
    elif [ -f ".env.production" ]; then
        echo -e "${YELLOW}⚙️  Tìm thấy file .env.production, đang sử dụng làm cấu hình chính...${NC}"
        cp .env.production .env
    else
        echo -e "${YELLOW}⚙️  Không tìm thấy file .env, đang tự động tạo từ .env.example...${NC}"
        cp .env.example .env
    fi
    
    # Tạo ngẫu nhiên một SECRET_KEY an toàn
    if command -v python3 &>/dev/null; then
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/replace_this_with_a_secure_random_hex_key/$SECRET_KEY/g" .env
        else
            sed -i "s/replace_this_with_a_secure_random_hex_key/$SECRET_KEY/g" .env
        fi
    fi
    echo -e "${GREEN}✅ Đã tạo file .env thành công.${NC}"
    echo -e "${YELLOW}⚠️  Lưu ý: Hệ thống đã dùng cấu hình mặc định. Bạn có thể cần bổ sung các API_KEY (OpenAI, Gemini...) vào file .env sau.${NC}\n"
else
    echo -e "${GREEN}✅ File .env đã tồn tại.${NC}\n"
fi

# 2. Khởi động Databases (Docker)
if command -v docker &>/dev/null; then
    echo -e "${BLUE}🐳 Đang khởi động các Databases (FalkorDB, Neo4j, Postgres) qua Docker...${NC}"
    if command -v docker-compose &>/dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    echo -e "${GREEN}✅ Các dịch vụ Database đã sẵn sàng.${NC}\n"
else
    echo -e "${RED}⚠️  Không tìm thấy Docker! Các dịch vụ Database sẽ không thể chạy. Vui lòng cài đặt Docker để sử dụng tính năng cơ sở dữ liệu.${NC}\n"
fi

# ==============================================================================
# Tự động nạp dữ liệu mồi (Seed Data) nếu có
# ==============================================================================
if [ -d "db-seed" ] && [ ! -f ".db_seeded" ]; then
    echo -e "${YELLOW}🌱 Tìm thấy thư mục 'db-seed/', đang nạp dữ liệu vào Database...${NC}"
    
    # Đợi vài giây cho DB khởi động hoàn toàn
    sleep 5
    
    if [ -f "db-seed/postgres.sql" ]; then
        echo "Nạp dữ liệu Postgres..."
        docker exec -i strongbi-postgres psql -U postgres -d strongbi_auth < db-seed/postgres.sql || echo "⚠️ Lỗi khi nạp Postgres"
    fi
    
    if [ -f "db-seed/dump.rdb" ]; then
        echo "Nạp dữ liệu FalkorDB..."
        docker cp db-seed/dump.rdb strongbi-falkordb:/data/dump.rdb || echo "⚠️ Lỗi khi nạp FalkorDB"
        docker restart strongbi-falkordb >/dev/null
    fi
    
    # Nạp toàn bộ dữ liệu Neo4j (Tất cả Databases)
    if ls db-seed/*.dump 1> /dev/null 2>&1; then
        echo "Nạp dữ liệu Neo4j (Graph Databases)..."
        for DUMP_FILE in db-seed/*.dump; do
            DB_NAME=$(basename "$DUMP_FILE" .dump)
            echo "-> Đang nạp database: $DB_NAME"
            
            # Copy file dump vào thư mục import
            docker cp "$DUMP_FILE" strongbi-neo4j:/var/lib/neo4j/import/"$DB_NAME.dump" || echo "⚠️ Lỗi khi copy $DB_NAME"
            
            # Tạo database nếu chưa có (Neo4j sẽ tự động tạo cấu trúc khi load nếu db chưa tồn tại)
            # Dừng database
            docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "STOP DATABASE \`$DB_NAME\`;" >/dev/null 2>&1 || true
            # Nạp dữ liệu từ dump (chấp nhận đè data cũ)
            docker exec strongbi-neo4j neo4j-admin database load $DB_NAME --from-path=/var/lib/neo4j/import --overwrite-destination=true >/dev/null 2>&1 || echo "⚠️ Lỗi khi load $DB_NAME"
            # Tạo mới database trên system (nếu đây là database mới hoàn toàn chưa từng được khai báo)
            docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "CREATE DATABASE \`$DB_NAME\` IF NOT EXISTS;" >/dev/null 2>&1 || true
            # Mở lại database
            docker exec strongbi-neo4j cypher-shell -u neo4j -p password123 -d system "START DATABASE \`$DB_NAME\`;" >/dev/null 2>&1 || true
        done
    fi
    
    # Đánh dấu đã seed để không seed lại vào lần sau
    touch .db_seeded
    echo -e "${GREEN}✅ Nạp dữ liệu thành công!${NC}\n"
fi

# ==============================================================================
# Chạy đồng thời Backend và Frontend
# ==============================================================================
echo -e "${BLUE}📦 Đang chuẩn bị Backend & Frontend...${NC}"

# Hàm xử lý dọn dẹp khi nhấn Ctrl+C
cleanup() {
    echo -e "\n${YELLOW}🛑 Đang dừng toàn bộ các dịch vụ...${NC}"
    kill 0
}
trap cleanup SIGINT SIGTERM EXIT

# Chạy Backend (Python/FastAPI)
(
    echo -e "${GREEN}🐍 Đang khởi động Python Backend (Port 8000)...${NC}"
    if command -v uv &>/dev/null; then
        uv run uvicorn api.index:app --host 0.0.0.0 --port 8000 --reload
    else
        echo -e "${YELLOW}⚠️ Không tìm thấy uv. Đang dùng pip mặc định...${NC}"
        if [ ! -d ".venv" ]; then
            python3 -m venv .venv
        fi
        source .venv/bin/activate
        pip install -r <(python3 -c "import tomli; print('\n'.join(tomli.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" 2>/dev/null || echo "fastapi uvicorn") || echo "Có thể thiếu một số package."
        uvicorn api.index:app --host 0.0.0.0 --port 8000 --reload
    fi
) &

# Chạy Frontend (React/Vite)
(
    echo -e "${GREEN}⚛️  Đang cài đặt và khởi động React Frontend...${NC}"
    cd app
    # Cài đặt (bỏ --silent để dễ xem lỗi, dùng --no-fund --no-audit để bớt rác)
    npm install --no-fund --no-audit
    echo -e "${GREEN}⚛️  Frontend chuẩn bị chạy (Port mặc định: 5173)...${NC}"
    npm run dev
) &

echo -e "\n${GREEN}🎉 Hệ thống Strong BI đang chạy!${NC}"
echo -e "👉 Backend API:  http://localhost:8000"
echo -e "👉 Frontend UI:  Vui lòng xem cổng Vite ở log bên dưới (thường là http://localhost:5173)\n"
echo -e "${YELLOW}Nhấn Ctrl+C để dừng tất cả dịch vụ.${NC}\n"

# Đợi các tiến trình con
wait
