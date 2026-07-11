# Photo Desktop Pet

把照片里的女生做成一个 Windows 桌宠小程序。

## 运行

```powershell
cd D:\SunJX\projects\photo-desktop-pet
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe pet.py
```

## 操作

- 鼠标左键拖动：移动桌宠
- 鼠标双击：让桌宠跳一下
- 鼠标右键：打开动作菜单
- 自动动作：待机时随机散步、跳跃、打招呼或摇摆
- 始终置顶：控制桌宠是否显示在其他窗口上方
- 切换大小：循环切换三种显示尺寸
- 退出：关闭桌宠

## 文件

- `assets/girl-pet.png`：透明桌宠素材
- `assets/girl-pet-chromakey.png`：生成时的绿幕源图
- `pet.py`：桌宠程序
