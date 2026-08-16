"""Reusable collection prompt template CRUD."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.collection_schemas import PromptTemplateCreate, PromptTemplateOut, PromptTemplateUpdate
from app.database import get_db
from app.models import PromptTemplate, Topic
from app.prompt_seed import SUPPLY_CHAIN_EXPERT_PROMPT_ID

router = APIRouter(prefix="/api/v1/prompt-templates", tags=["prompt-templates"])


def _topic_count(db: Session, prompt_id: str) -> int:
    return sum(
        prompt_id in (topic.prompt_template_ids or [])
        for topic in db.query(Topic).all()
    )


def _out(db: Session, prompt: PromptTemplate) -> PromptTemplateOut:
    data = PromptTemplateOut.model_validate(prompt)
    linked_experts = ["供应链专家"] if prompt.id == SUPPLY_CHAIN_EXPERT_PROMPT_ID else []
    return data.model_copy(update={
        "topic_count": _topic_count(db, prompt.id),
        "linked_experts": linked_experts,
    })


@router.get("", response_model=list[PromptTemplateOut])
def list_prompt_templates(db: Session = Depends(get_db)):
    prompts = db.query(PromptTemplate).order_by(PromptTemplate.updated_at.desc()).all()
    return [_out(db, prompt) for prompt in prompts]


@router.post("", response_model=PromptTemplateOut, status_code=201)
def create_prompt_template(data: PromptTemplateCreate, db: Session = Depends(get_db)):
    prompt_id = data.id or f"prompt-{uuid4().hex[:8]}"
    if db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first():
        raise HTTPException(400, f"提示词 '{prompt_id}' 已存在")
    prompt = PromptTemplate(**data.model_dump(exclude={"id"}), id=prompt_id)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return _out(db, prompt)


@router.put("/{prompt_id}", response_model=PromptTemplateOut)
def update_prompt_template(prompt_id: str, data: PromptTemplateUpdate, db: Session = Depends(get_db)):
    prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not prompt:
        raise HTTPException(404, "提示词不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(prompt, key, value)
    db.commit()
    db.refresh(prompt)
    return _out(db, prompt)


@router.delete("/{prompt_id}")
def delete_prompt_template(prompt_id: str, db: Session = Depends(get_db)):
    prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not prompt:
        raise HTTPException(404, "提示词不存在")
    for topic in db.query(Topic).all():
        linked = topic.prompt_template_ids or []
        if prompt_id in linked:
            topic.prompt_template_ids = [value for value in linked if value != prompt_id]
    db.delete(prompt)
    db.commit()
    return {"ok": True}
