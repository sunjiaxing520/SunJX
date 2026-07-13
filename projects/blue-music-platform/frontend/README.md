# 蓝乐正式前端

技术栈：React、TypeScript、Vite、Ant Design、React Router。

## 本地启动

先启动 `8000` 端口的后端，再运行：

```powershell
cd D:\SunJX\projects\blue-music-platform\frontend
D:\Program Files\nodejs\npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

打开 `http://127.0.0.1:5173`。

## 质量检查

```powershell
D:\Program Files\nodejs\npm.cmd run build
D:\Program Files\nodejs\npm.cmd run lint
D:\Program Files\nodejs\npm.cmd test
```

接口地址由 `VITE_API_BASE_URL` 控制，默认是 `http://127.0.0.1:8000/api/v1`。生产构建时必须设置实际后端地址，并在后端 `CORS_ORIGINS` 中加入正式前端域名。
