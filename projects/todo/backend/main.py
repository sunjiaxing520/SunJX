import os, secrets, hashlib, json, time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
from urllib.parse import urlparse
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, update, delete, text
from sqlalchemy.exc import IntegrityError
from pwdlib import PasswordHash
from cryptography.fernet import Fernet
from pydantic import ValidationError
from .db import Base, engine, Session, User, LoginSession, Message, ROOT, now
from .schemas import Auth, StateWrite, State, AIConfig, ChatInput
from .ai import PROMPT, call_model, prepare_changes, apply_changes, fetch_balance

hasher=PasswordHash.recommended()
crypto_key=os.getenv('ENCRYPTION_KEY')
if not crypto_key:
    if os.getenv('ENVIRONMENT')=='production': raise RuntimeError('ENCRYPTION_KEY must be configured')
    keyfile=ROOT/'.runtime'/'encryption.key'
    if not keyfile.exists(): keyfile.write_bytes(Fernet.generate_key())
    crypto_key=keyfile.read_text().strip()
cipher=Fernet(crypto_key.encode())
COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true'
attempts=defaultdict(deque)

def limit(key,maximum,seconds):
    queue=attempts[key]; stamp=time.monotonic()
    while queue and queue[0]<stamp-seconds: queue.popleft()
    if len(queue)>=maximum: raise HTTPException(429,'操作较频繁，请稍后重试。')
    queue.append(stamp)

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield

app=FastAPI(title='一件 API',version='0.2.0',lifespan=lifespan)

@app.middleware('http')
async def protections(request:Request, call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('x-todo-client')!='web': return JSONResponse({'detail':'请求来源校验失败'},403)
        origin=request.headers.get('origin')
        if origin and urlparse(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'detail':'不允许跨站请求'},403)
        length=request.headers.get('content-length')
        if length and int(length)>5_000_000: return JSONResponse({'detail':'请求内容太大'},413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    if request.url.path.startswith('/api'): response.headers['Cache-Control']='no-store'
    return response

def db():
    with Session() as session:
        try: yield session
        except Exception:
            session.rollback(); raise

def current(request:Request,session=Depends(db)):
    token=request.cookies.get('yijian_session','')
    login=session.get(LoginSession,hashlib.sha256(token.encode()).hexdigest()) if token else None
    if not login or login.expires.replace(tzinfo=timezone.utc)<now(): raise HTTPException(401,'请先登录。')
    user=session.get(User,login.user_id)
    if not user: raise HTTPException(401,'账号不存在。')
    return user

def public_user(user): return {'id':user.id,'name':user.name,'username':user.username,'ai_enabled':bool(user.key_cipher),'model':user.model}
def state_result(user): return {**user.data,'revision':user.revision}
def save_state(session,user,data,revision):
    changed=session.execute(update(User).where(User.id==user.id,User.revision==revision).values(data=data,revision=revision+1),execution_options={'synchronize_session':False})
    if changed.rowcount!=1: raise HTTPException(409,'另一台设备已更新内容。已刷新最新数据，请重新操作。')
    session.flush()
    session.expire(user)
    return state_result(user)

def issue_session(session,user,response):
    session.execute(delete(LoginSession).where(LoginSession.expires<now()))
    token=secrets.token_urlsafe(40)
    session.add(LoginSession(digest=hashlib.sha256(token.encode()).hexdigest(),user_id=user.id,expires=now()+timedelta(days=30)))
    session.commit()
    response.set_cookie('yijian_session',token,httponly=True,secure=COOKIE_SECURE,samesite='lax',max_age=30*86400,path='/')

@app.get('/api/health')
def health(session=Depends(db)):
    session.execute(text('SELECT 1'))
    return {'status':'ok','database':engine.dialect.name}

@app.post('/api/auth/register')
def register(body:Auth,request:Request,response:Response,session=Depends(db)):
    limit(('register',request.client.host),8,600)
    username=body.username.lower()
    default={'id':str(uuid4()),'name':'日常清单','kind':'general','color':'blue','goal':'','deadline':None,'hours':2,'details':''}
    user=User(id=str(uuid4()),username=username,password_hash=hasher.hash(body.password),name=body.name.strip() or username,data={'projects':[default],'tasks':[]})
    session.add(user)
    try: session.flush()
    except IntegrityError: raise HTTPException(409,'这个用户名已经被使用。')
    issue_session(session,user,response)
    return public_user(user)

@app.post('/api/auth/login')
def login(body:Auth,request:Request,response:Response,session=Depends(db)):
    limit(('login',request.client.host),20,300)
    user=session.scalar(select(User).where(User.username==body.username.lower()))
    if not user or not hasher.verify(body.password,user.password_hash): raise HTTPException(401,'用户名或密码不正确。')
    issue_session(session,user,response)
    return public_user(user)

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,session=Depends(db)):
    token=request.cookies.get('yijian_session','')
    session.execute(delete(LoginSession).where(LoginSession.digest==hashlib.sha256(token.encode()).hexdigest()))
    session.commit(); response.delete_cookie('yijian_session',path='/')
    return {'ok':True}

@app.get('/api/auth/me')
def me(user=Depends(current)): return public_user(user)

@app.get('/api/state')
def read_state(user=Depends(current)): return state_result(user)

@app.put('/api/state')
def write_state(body:StateWrite,user=Depends(current),session=Depends(db)):
    data=body.model_dump(mode='json',exclude={'revision'})
    old_projects={p['id'] for p in user.data['projects']}
    new_projects={p['id'] for p in data['projects']}
    result=save_state(session,user,data,body.revision)
    removed=old_projects-new_projects
    if removed: session.execute(delete(Message).where(Message.user_id==user.id,Message.project_id.in_(removed)))
    session.commit()
    return result

@app.put('/api/settings/ai')
def settings(body:AIConfig,user=Depends(current),session=Depends(db)):
    if body.key is not None:
        key=body.key.strip()
        if key and len(key)<10: raise HTTPException(422,'请输入完整的 API Key。')
        user.key_cipher=cipher.encrypt(key.encode()).decode() if key else None
    user.model=body.model
    session.commit()
    return public_user(user)

@app.post('/api/settings/ai/test')
async def test_ai(user=Depends(current)):
    if not user.key_cipher: raise HTTPException(400,'请先保存 Kimi Key。')
    limit(('ai',user.id),8,60)
    await call_model(cipher.decrypt(user.key_cipher.encode()).decode(),user.model,[{'role':'user','content':'只输出JSON：{"message":"连接成功","changes":[]}'}])
    return {'ok':True,'message':'Kimi 连接成功，可以开始商议计划。'}

@app.get('/api/settings/ai/balance')
async def balance(user=Depends(current),session=Depends(db)):
    if not user.key_cipher: raise HTTPException(400,'请先保存 Kimi Key，再查询余额。')
    limit(('balance',user.id),12,60)
    key=cipher.decrypt(user.key_cipher.encode()).decode()
    session.rollback()
    result=await fetch_balance(key)
    return {**result,'checked_at':now().isoformat()}

def message_result(m):
    return {'id':m.id,'role':m.role,'content':m.content,'created':m.created.isoformat(),'proposal':m.proposal,'status':m.status,'base_revision':m.base_revision}

@app.get('/api/chat/{project_id}')
def get_chat(project_id:str,user=Depends(current),session=Depends(db)):
    rows=session.scalars(select(Message).where(Message.user_id==user.id,Message.project_id==project_id).order_by(Message.created,Message.id)).all()
    return [message_result(m) for m in rows]

@app.post('/api/chat')
async def chat(body:ChatInput,user=Depends(current),session=Depends(db)):
    if not body.message.strip(): raise HTTPException(422,'请输入消息。')
    if not user.key_cipher: raise HTTPException(400,'在设置中添加 Kimi Key 后，即可使用 AI。')
    project=next((p for p in user.data['projects'] if p['id']==body.project_id),None)
    if not project: raise HTTPException(404,'计划不存在。')
    existing=session.get(Message,body.request_id)
    if existing:
        if existing.user_id!=user.id: raise HTTPException(409,'请求编号重复，请重试。')
        return message_result(existing)
    limit(('ai',user.id),8,60)
    revision=user.revision
    initial=deepcopy(user.data)
    history=session.scalars(select(Message).where(Message.user_id==user.id,Message.project_id==body.project_id).order_by(Message.created.desc()).limit(16)).all()
    context={'today':str(body.today),'project':project,'tasks':[t for t in initial['tasks'] if t['project_id']==body.project_id][-300:]}
    messages=[{'role':'system','content':PROMPT+'\n当前真实数据：'+json.dumps(context,ensure_ascii=False)}]
    messages.extend({'role':m.role,'content':m.content} for m in reversed(history))
    messages.append({'role':'user','content':body.message})
    key=cipher.decrypt(user.key_cipher.encode()).decode()
    model=user.model
    session.rollback()  # release connection while waiting on the external provider
    reply=await call_model(key,model,messages)
    try: changes=prepare_changes(initial,body.project_id,reply.changes)
    except ValidationError: raise HTTPException(502,'AI 草稿包含无效任务，请重新生成。')
    current_user=session.get(User,user.id)
    if not any(p['id']==body.project_id for p in current_user.data['projects']): raise HTTPException(409,'这份计划已被删除。')
    session.add(Message(id=str(uuid4()),user_id=user.id,project_id=body.project_id,role='user',content=body.message))
    answer=Message(id=body.request_id,user_id=user.id,project_id=body.project_id,role='assistant',content=reply.message,proposal={'changes':changes} if changes else None,status='pending' if changes else 'message',base_revision=revision)
    session.add(answer)
    try: session.commit()
    except IntegrityError:
        session.rollback()
        existing=session.get(Message,body.request_id)
        if existing and existing.user_id==user.id: return message_result(existing)
        raise HTTPException(409,'请求编号重复，请重试。')
    return message_result(answer)

@app.post('/api/proposals/{message_id}/apply')
def apply(message_id:str,user=Depends(current),session=Depends(db)):
    m=session.get(Message,message_id)
    if not m or m.user_id!=user.id: raise HTTPException(404,'找不到草稿。')
    if m.status=='applied': return state_result(user)
    if m.status!='pending' or not m.proposal: raise HTTPException(409,'草稿已失效。')
    before=deepcopy(user.data)
    data=apply_changes(before,m.project_id,m.proposal['changes'])
    result=save_state(session,user,data,m.base_revision)
    m.previous_data=before; m.applied_revision=result['revision']; m.status='applied'
    session.commit()
    return result

@app.post('/api/proposals/{message_id}/undo')
def undo(message_id:str,user=Depends(current),session=Depends(db)):
    m=session.get(Message,message_id)
    if not m or m.user_id!=user.id: raise HTTPException(404,'找不到这次调整。')
    if m.status!='applied' or m.previous_data is None: raise HTTPException(409,'此调整不能撤销。')
    result=save_state(session,user,m.previous_data,m.applied_revision)
    m.status='undone'; session.commit()
    return result

@app.post('/api/proposals/{message_id}/dismiss')
def dismiss(message_id:str,user=Depends(current),session=Depends(db)):
    m=session.get(Message,message_id)
    if not m or m.user_id!=user.id: raise HTTPException(404,'找不到草稿。')
    if m.status!='pending': raise HTTPException(409,'草稿状态已经变化。')
    m.status='dismissed'; session.commit()
    return {'ok':True}

@app.get('/api/export')
def export(user=Depends(current),session=Depends(db)):
    messages=session.scalars(select(Message).where(Message.user_id==user.id).order_by(Message.created)).all()
    return {'format':'yijian-v1','exported_at':now().isoformat(),**user.data,'messages':[{**message_result(m),'project_id':m.project_id} for m in messages]}

@app.get('/{path:path}')
def frontend(path:str):
    if path.startswith('api/'): raise HTTPException(404,'接口不存在')
    root=(ROOT/'dist').resolve()
    target=(root/path).resolve()
    if not target.is_relative_to(root): raise HTTPException(404)
    if target.is_file(): return FileResponse(target)
    if (root/'index.html').exists(): return FileResponse(root/'index.html')
    raise HTTPException(404,'请先构建前端，或使用开发服务器。')
