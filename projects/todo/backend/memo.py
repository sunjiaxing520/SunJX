"""Read-only MaiMemo official study API. Never send the access token to an LLM."""
import asyncio
from datetime import datetime, timezone, timedelta
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, ConfigDict, AliasChoices

class Progress(BaseModel):
    model_config = ConfigDict(strict=True)
    finished: int = Field(ge=0)
    total: int = Field(ge=0)
    study_time: int = Field(ge=0)

class Word(BaseModel):
    model_config = ConfigDict(strict=True)
    voc_id: str
    voc_spelling: str = Field(validation_alias=AliasChoices("voc_spelling", "spelling"))
    is_new: bool
    is_finished: bool

async def read_today(key):
    async def request(client, method, payload):
        response=await client.post('https://open.maimemo.com/open/api/v1/memo/study/'+method,json=payload)
        if response.status_code == 404:
            response=await client.post('https://open.maimemo.com/open/api/v1/study/'+method,json=payload)
        if response.status_code != 200:
            raise HTTPException(422 if response.status_code in (401,403) else 424,{401:'墨墨 API Key 无效，请重新绑定。',403:'墨墨未授权读取学习数据，请检查开放 API 权限。',429:'墨墨查询频率受限，请稍后刷新。'}.get(response.status_code,'墨墨暂时不可用，请稍后重试。'))
        body=response.json()
        # Official CLI accepts both the response envelope and direct study objects.
        if not isinstance(body,dict): raise ValueError('invalid response')
        if body.get("success") is False or body.get("errors"):
            raise HTTPException(424,"墨墨未能提供学习数据，请检查开放 API 权限，并在 App 开启自动同步后重试。")
        return body.get("data",body)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20,connect=10),headers={'Authorization':f'Bearer {key}'}) as client:
            progress_body,words_body=await asyncio.gather(request(client,'get_study_progress',{}),request(client,'get_today_items',{'limit':1000}))
        progress=Progress.model_validate(progress_body['progress']).model_dump()
        raw=words_body['today_items']
        if not isinstance(raw,list): raise ValueError('invalid words')
        words=[Word.model_validate(item).model_dump() for item in raw[:1000]]
        stamp=datetime.now(timezone.utc)
        return {'progress':progress,'words':words,'checked_at':stamp.isoformat(),'date':stamp.astimezone(timezone(timedelta(hours=8))).date().isoformat(),'list_limited':len(raw)>=1000}
    except httpx.TimeoutException: raise HTTPException(424,'墨墨同步超时，请稍后刷新。')
    except httpx.RequestError: raise HTTPException(424,'无法连接墨墨，请稍后刷新。')
    except (ValueError,KeyError,TypeError,ValidationError): raise HTTPException(424,'墨墨返回的数据格式不完整，请先打开 App 并开启自动同步后重试。')
