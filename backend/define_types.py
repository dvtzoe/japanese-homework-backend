from pydantic import BaseModel


class Response(BaseModel):
    status: int
    message: str | None = None


class Question(BaseModel):
    image_url: str | None = None
    text: str | None = None
    choices: list[str] | None = None
    key: str | None = None


class Questions(BaseModel):
    questions: list[Question] = []


class Answer(Response):
    answers: list[str | int | None] = []
