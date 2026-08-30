from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from openai import OpenAI


TUTOR_PROMPT = r"""
You are a warm, accurate math tutor. Read the equation or problem in the image.
Infer the learner's likely level from the problem itself and adapt your language:
- for early arithmetic, use concrete objects such as apples and very short steps;
- for school mathematics, use age-appropriate real-world analogies;
- for advanced mathematics, use precise notation, intuition, and a relevant example.

Respond in Markdown with:
1. the problem you read from the image;
2. the learner level you inferred;
3. the goal of the problem and why the chosen method is appropriate;
4. a careful step-by-step explanation that says why every step is valid and needed;
5. the meaning of the final answer in the context of the problem;
6. a quick check.
Write all mathematics in LaTeX. Use $...$ for inline math and $$...$$ for display
math. Never use \(...\) or \[...\] delimiters.
Do not merely give the final answer. If the image is ambiguous, ask followup questions. Do not make things up.
""".strip()


@dataclass
class Tutor:
    api_key: str
    model: str = "gpt-4.1-mini"

    def __post_init__(self) -> None:
        self.client = OpenAI(api_key=self.api_key)

    def explain_image(self, image_bytes: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": TUTOR_PROMPT},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{encoded}",
                        },
                    ],
                }
            ],
        )
        return response.output_text

    def follow_up(self, explanation: str, history: list[dict[str, str]], question: str) -> str:
        conversation = "\n".join(
            f"{message['role'].title()}: {message['content']}" for message in history[-8:]
        )
        prompt = f"""
        Continue tutoring the same learner at the same level. Be clear and detailed, use a
        matching example when helpful, and answer the learner's actual question. Write all
        mathematics in LaTeX using $...$ inline and $$...$$ for display math. Explain the
        purpose of the method and why each step works and is needed instead of only listing calculations.

        Original explanation:
        {explanation}

        Recent conversation:
        {conversation}

        Learner's new question:
        {question}
        """.strip()
        return self.client.responses.create(model=self.model, input=prompt).output_text

    def make_video_plan(self, lesson_context: str) -> list[dict[str, str]]:
        prompt = f"""
        First silently determine the final, corrected equation from the latest follow-up
        discussion. Then turn only that corrected problem and solution into 5 to 8 short
        teaching scenes. Never show, solve, mention, or compare an earlier misread equation.
        Use the original explanation only for information that was not later corrected.

        Structure the lesson in this order:
        1. Start by naming and explaining the general mathematical topic without solving
           the uploaded problem.
        2. Build intuition with an age-appropriate analogy or simple generic example.
        3. Explain the important rule or method and why it is used and how it works.
        4. Only then introduce the learner's specific equation and apply the idea step by step.
        5. End with the meaning of the answer and a brief recap of the general lesson.

        Return only valid JSON: an array of objects with exactly these string fields:
        "heading", "visual", and "narration".
        The visual is brief whiteboard text, math, or a concrete analogy. Keep it under
        160 characters and never put narration or a long paragraph in it. Narration should
        explain the scene naturally and in detail. It must explain the goal, why the method is chosen,
        and why each step is mathematically valid and needed. Do not merely read
        calculations aloud. Keep each narration under 500 characters.

        Lesson context:
        {lesson_context}
        """.strip()
        raw = self.client.responses.create(model=self.model, input=prompt).output_text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        scenes = json.loads(raw)
        return scenes

    def narrate(self, text: str, output_path: str) -> None:
        with self.client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
            instructions="Speak like a patient, encouraging math teacher.",
        ) as response:
            response.stream_to_file(output_path)
