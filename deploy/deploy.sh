#!/usr/bin/env bash
# 本地 -> 阿里云 一键同步脚本（在你的 Mac 上运行）
# 用法：编辑下面的 SERVER / SSH_KEY，然后  bash deploy/deploy.sh  [backend|frontend|all]
set -euo pipefail

# ===== 改成你的服务器信息 =====
SERVER="root@taoism.test.doouu.cc"   # 改成你的登录用户@服务器IP/域名
SSH_PORT="22"
REMOTE_BASE="/root/taoism"
# ===============================

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-all}"
SSH="ssh -p ${SSH_PORT}"

sync_backend() {
  echo ">> 同步后端代码 + 知识库数据（含 chroma 向量库）..."
  rsync -avz --delete -e "${SSH}" \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.venv/' \
    --exclude '.env' \
    --exclude 'data/reports/' \
    "${PROJECT_ROOT}/backend/" \
    "${SERVER}:${REMOTE_BASE}/backend/"
  echo ">> 后端同步完成。首次部署记得在服务器建 .venv 并 pip install；改完代码后重启服务："
  echo "   sudo systemctl restart lsz-backend"
}

# 前端静态文件目录：放在 /var/www（nginx www-data 可读），不能放 /root(700)
FRONTEND_REMOTE="/var/www/taoism/frontend"

build_and_sync_frontend() {
  echo ">> 本地构建 PC 管理端（使用 .env.production 中的线上 API 地址）..."
  ( cd "${PROJECT_ROOT}/frontend" && npm run build )
  echo ">> 同步 dist 到 nginx 根目录 ${FRONTEND_REMOTE} ..."
  ${SSH} "${SERVER}" "mkdir -p ${FRONTEND_REMOTE}"
  rsync -avz --delete -e "${SSH}" \
    "${PROJECT_ROOT}/frontend/dist/" \
    "${SERVER}:${FRONTEND_REMOTE}/"
  echo ">> 修正属主为 www-data，使 nginx 可读 ..."
  ${SSH} "${SERVER}" "chown -R www-data:www-data /var/www/taoism"
  echo ">> 前端同步完成。"
}

case "${TARGET}" in
  backend)  sync_backend ;;
  frontend) build_and_sync_frontend ;;
  all)      sync_backend; build_and_sync_frontend ;;
  *) echo "用法: bash deploy/deploy.sh [backend|frontend|all]"; exit 1 ;;
esac
