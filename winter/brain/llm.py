"""Local LLM access via Ollama — intent parsing and in-character replies."""
from __future__ import annotations

import json

# keep the model resident in RAM between commands so there is no reload lag
_KEEP_ALIVE = "30m"

# every reply is spoken aloud — keep the model from emitting unspeakable text
_SPOKEN_STYLE = (
    "Everything you say is spoken aloud. Reply in plain, natural speech — no "
    "asterisks, emotes, stage directions, action descriptions, or markdown. "
    "Keep it very short: one sentence, two at the very most."
)

INTENT_SYSTEM_PROMPT = """You convert a user's spoken command to a desktop \
assistant into ONE JSON object. Output only the JSON, nothing else.

Schema (always include every field):
{
  "type": "volume_change" | "volume_set" | "media" | "play_youtube" | "question" | "chitchat" | "unknown",
  "amount": integer,
  "media_action": "play_pause" | "next" | "previous" | null,
  "query": string
}

Rules:
- "volume up 3", "louder", "turn it up" -> type "volume_change". "amount" is the
  number of steps; positive raises, negative lowers. Use 1 if no number is said.
  "volume down 2" -> amount -2.
- "set volume to 40", "volume 40 percent" -> type "volume_set", amount = 40.
- "next", "skip", "next song/video" -> type "media", media_action "next".
  A bare "pause", "play", "stop" with no song named -> "play_pause".
  "previous", "go back" -> "previous".
- A request to play a specific named song or video ("play heaven by clairo on
  youtube", "put on bohemian rhapsody", "play despacito") -> type
  "play_youtube", query = just the song or video to search for (no "on
  youtube").
- A factual question needing the web -> type "question", query = the question.
- Greetings / small talk -> type "chitchat".
- Anything unclear -> type "unknown".
Use 0, null or "" for fields that do not apply.

Examples:
"pause the music" -> {"type":"media","amount":0,"media_action":"play_pause","query":""}
"volume up three" -> {"type":"volume_change","amount":3,"media_action":null,"query":""}
"set volume to 40" -> {"type":"volume_set","amount":40,"media_action":null,"query":""}
"play heaven by clairo on youtube" -> {"type":"play_youtube","amount":0,"media_action":null,"query":"heaven by clairo"}
"what time is it in Tokyo" -> {"type":"question","amount":0,"media_action":null,"query":"what time is it in Tokyo"}"""


def _message_content(response) -> str:
    """Read message content from an ollama response (dict or pydantic model)."""
    message = response["message"]
    content = message["content"]
    return content if isinstance(content, str) else str(content)


class OllamaClient:
    def __init__(self, model: str, host: str):
        import ollama

        self.model = model
        self._client = ollama.Client(host=host)

    def parse_intent(self, text: str) -> dict:
        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            format="json",
            options={"temperature": 0.0},
            keep_alive=_KEEP_ALIVE,
        )
        return json.loads(_message_content(response))

    def roleplay(self, system_prompt: str, user_text: str,
                 context: str = "") -> str:
        messages = [{"role": "system",
                     "content": f"{system_prompt}\n\n{_SPOKEN_STYLE}"}]
        if context:
            messages.append({
                "role": "system",
                "content": f"Use this reference information:\n{context}",
            })
        messages.append({"role": "user", "content": user_text})
        response = self._client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": 0.7},
            keep_alive=_KEEP_ALIVE,
        )
        return _message_content(response).strip()

    def answer(self, personality_prompt: str, question: str,
               search_results: list[str]) -> str:
        """Answer a question in character, grounded in web search results."""
        context = "\n".join(f"- {r}" for r in search_results) or "(no results)"
        system = (
            f"{personality_prompt}\n\n{_SPOKEN_STYLE}\n\n"
            "Answer the user's question staying fully in character, in one or "
            "two short sentences suitable for speaking aloud. Base the answer "
            "on the search results below; if they do not contain the answer, "
            f"say so briefly.\n\nSearch results:\n{context}"
        )
        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            options={"temperature": 0.6},
            keep_alive=_KEEP_ALIVE,
        )
        return _message_content(response).strip()

    def warm_up(self) -> None:
        """Load the model into memory so the first real call is fast."""
        try:
            self._client.chat(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                options={"num_predict": 1},
                keep_alive=_KEEP_ALIVE,
            )
        except Exception:
            pass
