"""
蓝乐 AI 音乐创作平台 — 后端入口
FastAPI 应用主文件
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="蓝乐 AI 音乐创作平台",
    description="多智能体 AI 音乐榜单爬取 + 风格分析 + 智能创作平台",
    version="0.1.0",
)

# 允许前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 根路由：健康检查 ----------
@app.get("/")
def root():
    return {"status": "ok", "message": "蓝乐 AI 音乐创作平台运行中"}


# ---------- 健康检查接口 ----------
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "blue-music-platform",
    }
