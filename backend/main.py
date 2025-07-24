import os
from contextlib import asynccontextmanager

import redis
from define_types import *
from fastapi import FastAPI
from gemini_webapi import GeminiClient
from problem_solver import PromblemSolver

Secure_1PSID = os.getenv("SECURE_1PSID")
Secure_1PSIDTS = os.getenv("SECURE_1PSIDTS")

gemini_client = GeminiClient(Secure_1PSID, Secure_1PSIDTS, proxy=None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(Secure_1PSID, Secure_1PSIDTS)
    await gemini_client.init(
        timeout=30, auto_close=False, close_delay=300, auto_refresh=True
    )
    yield


app = FastAPI(lifespan=lifespan)

redis_host = os.getenv("REDIS_HOST", "localhost")
try:
    cache = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
    cache.ping()
    print("Successfully connected to Redis.")
except redis.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    cache = None


@app.get("/get_db")
async def get_db():
    if not cache:
        return Response(status=500, message="Redis service unavailable")
    keys = cache.keys("*")
    data = ""
    for key in keys:  # type: ignore
        data += f"{key}: {cache.get(key)}\n"
    return Response(status=200, message=data)


@app.post("/del_db")
async def del_db(password):
    if not cache:
        return Response(status=500, message="Redis service unavailable")
    if password != os.getenv("DB_PASSWORD"):
        return Response(status=500, message="Incorrect password")
    print("Flushing database 0")
    try:
        return Response(status=200 if cache.flushdb() else 500)
    except Exception as e:
        return Response(status=500, message=str(e))


@app.post("/del_key")
async def del_key(key, password):
    if not cache:
        return Response(status=500, message="Redis service unavailable")
    if password != os.getenv("DB_PASSWORD"):
        return Response(status=500, message="Incorrect password")
    print(f"Deleting key {key}")
    try:
        return Response(status=200 if cache.delete(key) else 500)
    except Exception as e:
        return Response(status=500, message=str(e))


@app.post("/get_answers")
async def get_answer(questions: Questions) -> Answer:
    if not cache:
        return Answer(status=500, message="Redis service unavailable", answers=[])
    if not questions.questions:
        return Answer(status=400, message="No questions provided", answers=[])
    question_list = questions.questions
    print(question_list)
    problem_solver = PromblemSolver(
        question_list, cache=cache, gemini_client=gemini_client
    )
    answers = await problem_solver.solve()
    try:
        response = Answer(status=200, answers=answers)
        print(response)
        return response
    except Exception as e:
        response = Answer(status=500, message=str(e), answers=[])
        print(response)
        return response
