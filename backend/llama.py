import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

client = InferenceClient(
    provider="auto",
    api_key=os.getenv("HF_TOKEN"),
)

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

    # Llama-3.1-8B-Instruct has a ~8k token context window. Each token is
    # roughly 4 chars; we reserve ~1500 tokens for system prompt + question +
    # output, leaving ~6500 tokens (~26000 chars) for transcript context.
    MAX_CONTEXT_CHARS = 26_000
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n[...transcript truncated...]"

    messages.append(
        {
            "role": "user",
            "content": (
                f"Transcript excerpts:\n{context}\n\nQuestion:\n{question}"
                if transcript_available
                else f"Question:\n{question}"
            ),
        }
    )

    completion = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=messages,
        max_tokens=600,
        temperature=0.25,
    )

    return completion.choices[0].message.content.strip()