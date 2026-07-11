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
- 鼠标右键：打开菜单
- 双击：切换大小
- 菜单里的 `置顶`：切换是否始终置顶
- 菜单里的 `退出`：关闭桌宠

## 文件

- `assets/girl-pet.png`：透明桌宠素材
- `assets/girl-pet-chromakey.png`：生成时的绿幕源图
- `pet.py`：桌宠程序

