from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Topic(BaseModel):
    title: str = Field(description="Название основной темы из учебника")
    summary: str = Field(description="Краткое описание, о чем эта тема (1-2 предложения)")


class Question(BaseModel):
    topic: str = Field(description="Название темы, к которой относится вопрос")
    difficulty: int = Field(ge=1, le=5, description="Уровень сложности от 1 до 5")
    question_type: Literal["multiple_choice", "open"] = Field(
        description="Тип вопроса: тестовый или открытый"
    )
    question_text: str = Field(description="Текст самого вопроса")
    options: Optional[List[str]] = Field(
        default=None,
        description="Ровно 4 варианта ответа для тестового вопроса, иначе None"
    )
    correct_answer: str = Field(description="Правильный ответ")
    explanation: str = Field(description="Краткое объяснение, почему ответ правильный")
    source_reference: Optional[str] = Field(
        default=None,
        description="Страница или раздел документа, откуда взят материал"
    )


class QuestionSet(BaseModel):
    questions: List[Question]
