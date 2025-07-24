import os
from hashlib import sha256

import requests
from define_types import *
from gemini_webapi.constants import Model


class PromblemSolver:
    def __init__(
        self, questions: list[Question], cache=None, gemini_client=None
    ) -> None:
        self.gemini_client = gemini_client
        self.cache = cache
        self.questions: list[Question] = questions
        self.llm_queue: list[Question] = []

    async def solve(self) -> list[int | str | None]:
        self.answers: list[str | int | None] = [None for _ in self.questions]
        for i, v in enumerate(self.questions):
            question = Question(
                image_url=v.image_url,
                text=v.text,
                choices=v.choices,
                key=self.get_key(v),
            )
            await self.get_image(question)
            cached_answer = self.cache_get(question.key)
            if cached_answer:
                print("Got an answer from cache")
                self.answers[i] = (
                    question.choices.index(cached_answer)
                    if question.choices
                    else cached_answer
                )
                continue
            else:
                print("No answer in cache, adding to queue")

                answer = await self.ask_llm(question)
            if answer is not None and question.choices:
                self.answers[i] = (
                    question.choices.index(answer)
                    if answer in question.choices
                    else answer
                )

        return self.answers

    # get the image and store it in images/{it's sha256 hash}.jpg
    async def get_image(self, question: Question) -> str | None:
        if not question.image_url:
            return None

        # Generate a unique filename based on the image URL
        image_hash = sha256(question.image_url.encode()).hexdigest()
        image_path = f"/app/images/{image_hash}.jpg"

        # Check if the image already exists
        if os.path.exists(image_path):
            print(f"Image already exists: {image_path}")
            return image_path

        # Download the image and save it
        try:
            response = requests.get(question.image_url, timeout=10)
            response.raise_for_status()  # Raise an error for bad responses
            with open(image_path, "wb") as image_file:
                image_file.write(response.content)
            print(f"Image downloaded and saved: {image_path}")
            return image_path
        except requests.RequestException as e:
            print(f"Failed to download image: {e}")
            return None

    # generate a key for the question
    def get_key(self, question: Question) -> str:
        if question.choices is not None:
            sorted_question = question.model_copy(deep=True)
            sorted_question.choices.sort()
            return str(sha256(sorted_question.model_dump_json().encode()).hexdigest())
        return str(sha256(question.model_dump_json().encode()).hexdigest())

    def cache_set(self, key, value):
        if not self.cache:
            return
        return self.cache.set(key, value)

    def cache_get(self, key):
        if not self.cache:
            return
        return self.cache.get(key)

    async def ask_llm(self, question: Question) -> str | None:
        # Generate a prompt for the LLM based on the question
        if question.choices:
            self.is_choices = True
            choices_str = "\n".join(
                [f"{i + 1}. {choice}" for i, choice in enumerate(question.choices)]
            )
            prompt = f"{question.text}\n\n{choices_str}\n\nPlease select the correct answer by its number and return the number only, without any additional text or explanation. DO NOT format the answer in any way, just return the number of the answer.\n\nAnswer:"
        else:
            self.is_choices = False
            prompt = question.text

        # Call the LLM to generate an answer
        answer = (
            await self.gemini_client.generate_content(
                prompt,
                model=Model.G_2_5_FLASH,
                files=[await self.get_image(question)] if question.image_url else None,
            )
        ).text

        # Process the LLM's response
        if self.is_choices and question.choices:
            try:
                index = int(answer.strip())
                if index < 1 or index > len(question.choices):
                    raise ValueError("Answer out of range")
                answer = question.choices[index - 1]
            except ValueError:
                if answer.strip() in question.choices:
                    answer = answer.strip()
                else:
                    print(f"Invalid answer: {answer}")
                    answer = None

        # Log the LLM's response and cache it
        print(f"LLM response: {answer}")
        if answer is not None:
            self.cache_set(question.key, answer)
        return answer
