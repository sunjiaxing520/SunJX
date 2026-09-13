"""Expand a dated weekly series while preserving independent daily progress."""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException
from .schemas import State

def schedule_weekly(data, request):
    draft = request.task.model_dump(mode='json')
    original = next((t for t in data['tasks'] if t['id'] == draft['id']), None)
    if original and (original['done'] or original['locked']):
        raise HTTPException(422, '已完成或锁定任务只能单独编辑，不能用来重排整组。')
    series = original.get('series_id') if original else None
    series = series or str(uuid4())
    cutoff = min(original.get('date') or draft['date'], draft['date']) if original else draft['date']
    candidates = [t for t in data['tasks'] if t['id'] == draft['id'] or (
        original and original.get('series_id') and t.get('series_id') == original['series_id']
        and t.get('date') and t['date'] >= cutoff)]
    protected = [t for t in candidates if t['done'] or t['locked']]
    by_date = {t['date']: t for t in candidates if t not in protected}
    protected_dates = {t['date'] for t in protected}
    generated = []
    date = request.task.date
    while date <= request.task.repeat_until:
        stamp = date.isoformat()
        if date.weekday() in request.task.repeat_weekdays and stamp not in protected_dates:
            previous = by_date.get(stamp)
            task = deepcopy(draft)
            task.update(id=previous['id'] if previous else str(uuid4()), date=stamp, series_id=series)
            for field, default in [('done',False),('completed_at',None),('actual_minutes',0),('mastery','none')]:
                task[field] = previous.get(field,default) if previous else default
            task['subtasks'] = [{**s, 'done': next((old['done'] for old in previous['subtasks'] if old['id']==s['id']),False) if previous else False} for s in task['subtasks']]
            generated.append(task)
        date += timedelta(days=1)
    if not generated:
        raise HTTPException(422, '日期范围内没有可安排的所选星期，请调整日期或星期。')
    generated_dates = {t['date'] for t in generated}
    # Retain recorded work even when its date is removed from the new schedule.
    recorded = [t for t in candidates if t not in protected and t['date'] not in generated_dates
                and (t.get('actual_minutes',0) or t.get('mastery','none')!='none' or any(s['done'] for s in t['subtasks']))]
    candidate_ids = {t['id'] for t in candidates}
    tasks = [t for t in data['tasks'] if t['id'] not in candidate_ids] + protected + recorded + generated
    if len(tasks) > 5000:
        raise HTTPException(422, '任务总数超过 5000，请缩短重复日期范围。')
    return State.model_validate({**data,'tasks':tasks}).model_dump(mode='json')
