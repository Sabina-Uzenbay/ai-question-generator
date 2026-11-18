import os
import time
from typing import List, Literal, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
from schemas import Question, QuestionSet

load_dotenv()

# Краткие описания уровней сложности из ТЗ (чтобы модуль работал автономно,
# пока Участник 3 не подключит свои расширенные правила)
DEFAULT_DIFFICULTY_GUIDES = {
    1: "Уровень 1 (Очень легкий): простые определения, базовые термины и факты напрямую из текста.",
    2: "Уровень 2 (Легкий): проверка понимания материала, пересказ своими словами, сравнение базовых понятий.",
    3: "Уровень 3 (Средний): применение знаний на практике, решение типовых примеров или задач по тексту.",
    4: "Уровень 4 (Сложный): анализ ситуаций, поиск ошибок в примерах, выявление причинно-следственных связей.",
    5: "Уровень 5 (Очень сложный): решение нестандартных комплексных задач, синтез нескольких концепций из материала."
}


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Не найден GEMINI_API_KEY в файле .env")
    return genai.Client(api_key=api_key)


def generate_questions(
    text: str,
    topic: str,
    num_questions: int = 5,
    difficulty: int = 3,
    question_type: Literal["multiple_choice", "open"] = "multiple_choice",
    custom_prompt_rules: Optional[str] = None
) -> List[Question]:
    """
    Главная функция генерации вопросов.
    Эту функцию будут вызывать Участник 3 (проверка качества) и Участник 4 (интерфейс Streamlit).
    """
    client = get_client()

    difficulty_desc = custom_prompt_rules or DEFAULT_DIFFICULTY_GUIDES.get(
        difficulty, DEFAULT_DIFFICULTY_GUIDES[3]
    )

    if question_type == "multiple_choice":
        type_instruction = (
            "Создай ТЕСТОВЫЕ вопросы (question_type = 'multiple_choice'). "
            "В поле 'options' обязательно укажи ровно 4 правдоподобных варианта ответа. "
            "Поле 'correct_answer' должно точно совпадать с одним из этих 4 вариантов."
        )
    else:
        type_instruction = (
            "Создай ОТКРЫТЫЕ вопросы (question_type = 'open'), требующие развернутого ответа или решения. "
            "Поле 'options' должно быть пустым (None / null). "
            "В поле 'correct_answer' напиши эталонный правильный ответ."
        )

    prompt = f"""
Ты — опытный преподаватель и методист. Твоя задача — составить проверочные вопросы строго на основе переданного учебного материала.

ПАРАМЕТРЫ ГЕНЕРАЦИИ:
- Выбранная тема: "{topic}"
- Количество вопросов: {num_questions}
- Уровень сложности: {difficulty} из 5. {difficulty_desc}
- Формат вопросов: {type_instruction}

ПРАВИЛА:
1. Используй ТОЛЬКО факты и информацию из приведенного ниже текста учебника. Не придумывай информацию извне.
2. Все вопросы должны относиться исключительно к теме "{topic}".
3. Вопросы не должны повторять друг друга по смыслу.
4. В поле 'explanation' дай краткое и понятное объяснение, почему правильный ответ именно такой.
5. В поле 'source_reference' укажи главу, раздел или примерное место в тексте, откуда взят вопрос.
6. Язык вопросов и ответов должен совпадать с языком учебного материала.

УЧЕБНЫЙ МАТЕРИАЛ:
\"\"\"
{text}
\"\"\"
"""

# Автоматически берем доступные модели Gemini Flash под твой ключ
    available_models = [
        m.name.replace("models/", "")
        for m in client.models.list()
        if "flash" in m.name.lower() and "tts" not in m.name.lower() and "image" not in m.name.lower()
    ]
    # Ставим gemini-3.8-flash первой в приоритет, если она есть в списке
    models_to_try = sorted(
        available_models,
        key=lambda name: 0 if "3.8-flash" in name else 1
    ) or ["gemini-3.8-flash"]

    response = None
    last_error = None

    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=QuestionSet,
                        temperature=0.4,
                    ),
                )
                break
            except Exception as e:
                last_error = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep(2)
                    continue
                if "404" in err_str or "NOT_FOUND" in err_str:
                    break  # сразу переходим к следующей доступной модели
                raise e
        if response:
            break

    if not response:
        raise RuntimeError(f"Серверы Gemini сейчас перегружены. Попробуйте через минуту. Детали: {last_error}")

    result = QuestionSet.model_validate_json(response.text)
    return result.questions


# --- БЛОК ДЛЯ ТЕСТИРОВАНИЯ ---
if __name__ == "__main__":
    sample_text = """
    Глава 3. Функции в Python.
    Функция — это именованный блок кода, который выполняет определенную задачу и может вызываться многократно.
    Для создания функции используется ключевое слово def, за которым следует имя функции и круглые скобки.
    Параметры — это переменные, указанные в круглых скобках при объявлении функции.
    Аргументы — это реальные значения, которые передаются в функцию при ее вызове.
    Оператор return завершает выполнение функции и возвращает результат вызывающему коду.
    Если оператор return отсутствует, функция автоматически возвращает специальное значение None.
    """

    print("Тестируем генерацию тестовых вопросов...")
    questions = generate_questions(
        text=sample_text,
        topic="Функции в Python",
        num_questions=2,
        difficulty=2,
        question_type="multiple_choice"
    )

    for i, q in enumerate(questions, 1):
        print(f"\nВопрос {i} (Сложность {q.difficulty}): {q.question_text}")
        if q.options:
            for opt in q.options:
                print(f"  - {opt}")
        print(f"Правильный ответ: {q.correct_answer}")
        print(f"Объяснение: {q.explanation}")