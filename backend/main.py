import enum
import os
import redis
from fastapi import FastAPI, HTTPException
import requests
import json

app = FastAPI(title="Caching Service with Vision API")

redis_host = os.getenv("REDIS_HOST", "localhost")
try:
    kanji_cache = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
    kanji_cache.ping()
    print("Successfully connected to Redis.")
except redis.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    kanji_cache = None


@app.get("/get_db")
async def get_db():
    if not kanji_cache:
        return HTTPException(500, detail="no cache idk")
    keys = kanji_cache.keys("*")
    data = ""
    for key in keys:  # type: ignore
        data += f"{key}: {kanji_cache.get(key)}\n"
    return data


@app.post("/del_db")
async def del_db(password):
    if not kanji_cache:
        return HTTPException(500, detail="no cache idk")
    if password != os.getenv("DB_PASSWORD"):
        return HTTPException(403, detail="incorrect password")
    print("Flushing the kanji database")
    return kanji_cache.flushdb()


@app.post("/del_key")
async def del_key(url, password):
    if not kanji_cache:
        return HTTPException(500, detail="no cache idk")
    if password != os.getenv("DB_PASSWORD"):
        return HTTPException(403, detail="incorrect password")
    print(f"Deleting key{url}")
    return kanji_cache.delete(url)


@app.post("/kanji_ocr")
async def kanji_ocr(urls):
    urls = json.loads(urls)

    if not kanji_cache:
        raise HTTPException(status_code=503, detail="Redis service unavailable")

    response_buffer = []
    requests_buffer = {}

    for i, url in enumerate(urls):
        kanji_cached_result = kanji_cache.get(url)
        if kanji_cached_result:
            response_buffer.append(kanji_cached_result)

        else:
            print(f"Adding {url} to the GCV queue")
            try:
                # response_buffer.append(await ocr_space(url))
                response_buffer.append("")
                requests_buffer[i] = {
                    "image": {
                        "source": {
                            "imageUri": url,
                        },
                    },
                    "features": {
                        "type": "TEXT_DETECTION",
                    },
                    "imageContext": {"languageHints": ["ja"]},
                }

            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=str(e),
                )

    if requests_buffer:
        print(f"Sending the GCV queue to process")
        try:
            response = list(
                map(
                    lambda i: i["fullTextAnnotation"]["text"],
                    requests.post(
                        "https://vision.googleapis.com/v1/images:annotate",
                        headers={
                            "Authorization": f"Bearer {os.getenv('GCLOUD_IDENTITY_TOKEN')}"
                        },
                        data=json.dumps(
                            {
                                "requests": list(requests_buffer.values()),
                            }
                        ),
                    ).json()["responses"],
                ),
            )
        except Exception as e:
            print(f"error: {e}")
            response = None

        if not response:
            return response_buffer
        for i, key in enumerate(requests_buffer.keys()):
            response_buffer[key] = response[i]
            kanji_cache.set(urls[key], response[i])
    print(f"Operation Successful returning :\n{response_buffer}")
    return response_buffer
