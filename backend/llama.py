import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from openai import OpenAI

load_dotenv()

_HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
_OPENAI_MODEL = "gpt-4o-mini"

# Llama 3.1's officially supported languages are English, German, French,
# Italian, Portuguese, Hindi, Spanish and Thai — Greek is not among them. On
# Greek questions the 8B model mis-accents words ("ορίσμα" for "όρισμα"),
# leaves dangling references and repeats itself. So OpenAI is preferred
# whenever a key is present; HF stays as a fallback so the app still answers
# when OpenAI is unreachable.
_openai_api_key = os.getenv("OPENAI_API_KEY")
_hf_token = os.getenv("HF_TOKEN")

_openai_client = OpenAI(api_key=_openai_api_key) if _openai_api_key else None

# Kept at module level under the old name: this client is the HF fallback.
client = InferenceClient(provider="auto", api_key=_hf_token) if _hf_token else None

if _openai_client:
    print(f"[LLM] Using {_OPENAI_MODEL} (fallback: {_HF_MODEL})")
elif client:
    print(f"[LLM] Using {_HF_MODEL}")
else:
    print("[LLM] No OPENAI_API_KEY or HF_TOKEN set — answering is disabled")

# gpt-4o-mini has a 128k-token window, so the transcript no longer has to be
# squeezed to fit. Llama 3.1 8B has ~8k: at ~4 chars/token, 26k chars leaves
# ~1500 tokens for the system prompt, question and output.
_MAX_CONTEXT_CHARS = {"openai": 120_000, "hf": 26_000}

_MAX_OUTPUT_TOKENS = 600
_TEMPERATURE = 0.25


def ask_llama(
    question: str,
    context: str,
    history: list[dict] | None = None,
    answer_language: str = "same as the question",
    summary_mode: bool = False,
    transcript_available: bool = True,
):
    if not transcript_available:
        style_instruction = (
            "No transcript excerpts are available. Answer the user's question "
            "using your general knowledge and any video cues that may be "
            "available in the surrounding context. Do not ask the user to "
            "provide transcript excerpts. Keep the answer concise, helpful, "
            "and honest about any uncertainty. "
        )
    elif summary_mode:
        style_instruction = (
            "The user wants a summary of the entire video. You are given ALL "
            "the transcript segments in chronological order. Write a thorough "
            "summary that covers the main topic, every significant concept or "
            "point the video introduces, key examples, and the overall flow. "
            "After summarising the video content, add a short paragraph of "
            "relevant general knowledge that gives the user useful context "
            "about the subject matter. Keep the tone clear and educational. "
        )
    else:
        style_instruction = (
            "Structure your answer as one educational paragraph (or a few short "
            "paragraphs if the topic needs it). First convey what the video "
            "explains about the topic, then enrich it with accurate general "
            "knowledge. Where it helps understanding, include a concrete, simple "
            "example — clearly presented but not prefaced with a label like "
            "'Example:'. Everything should read as a single natural explanation. "
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an intelligent educational assistant. "
                "The user is watching a video and asks questions about it. "
                "Timestamped transcript excerpts from the video are provided "
                "below (format \"[mm:ss-mm:ss] text\"). "
                "\n\nYour job:\n"
                "1. Read the transcript excerpts carefully and identify every "
                "relevant fact, definition, rule, or example the video provides "
                "about the topic.\n"
                "2. Use that video content as the foundation of your answer — "
                "it must be the dominant source.\n"
                "3. Expand on it with accurate general knowledge to make the "
                "answer educational and complete.\n"
                "4. Where useful, include a simple concrete example that "
                "illustrates the concept — blend it naturally into the text.\n"
                "\nRules:\n"
                "- Never copy transcript text word-for-word; paraphrase into "
                "clean, fluent prose.\n"
                "- Skip any garbled or incomplete transcript segment.\n"
                "- Separate the video's substantive content from the speaker's "
                "colloquial asides, jokes, visual mnemonics and figures of "
                "speech. Never restate an aside as a definition or as a "
                "technical property of the subject. If an aside genuinely aids "
                "intuition, attribute it as the speaker's informal way of "
                "describing something; otherwise leave it out.\n"
                "- Never produce circular definitions (do not define a word "
                "using the same word).\n"
                "- Do not invent facts; if something is uncertain say so briefly.\n"
                "- Do not label sections ('From the video:', 'Example:', etc.) — "
                "the answer must read as one cohesive explanation.\n"
                "- When referring to the person speaking in the video, use a "
                "neutral term such as 'the speaker' (or the equivalent in the "
                "response language, e.g. 'ο ομιλητής' in Greek). Never assume "
                "or invent a role, title, or name for them.\n"
                f"{style_instruction}"
                "Use prior conversation turns (if any) to understand follow-up "
                "questions.\n"
                f"Respond in {answer_language}."
            ),
        },
    ]

    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    def messages_for(backend: str):
        """Same conversation, with the transcript trimmed to that backend's window."""
        limit = _MAX_CONTEXT_CHARS[backend]
        trimmed = context
        if len(trimmed) > limit:
            trimmed = trimmed[:limit] + "\n[...transcript truncated...]"

        return messages + [
            {
                "role": "user",
                "content": (
                    f"Transcript excerpts:\n{trimmed}\n\nQuestion:\n{question}"
                    if transcript_available
                    else f"Question:\n{question}"
                ),
            }
        ]

    if _openai_client:
        try:
            completion = _openai_client.chat.completions.create(
                model=_OPENAI_MODEL,
                messages=messages_for("openai"),
                max_tokens=_MAX_OUTPUT_TOKENS,
                temperature=_TEMPERATURE,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if not client:
                raise
            print(f"[LLM] {_OPENAI_MODEL} failed ({type(e).__name__}: {e}); falling back to {_HF_MODEL}")

    if not client:
        raise RuntimeError("No LLM backend configured: set OPENAI_API_KEY or HF_TOKEN.")

    completion = client.chat.completions.create(
        model=_HF_MODEL,
        messages=messages_for("hf"),
        max_tokens=_MAX_OUTPUT_TOKENS,
        temperature=_TEMPERATURE,
    )

    return completion.choices[0].message.content.strip()