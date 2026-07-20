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
            "The user is asking for a summary. Give a concise but useful "
            "overview of the video, focusing on the main topic, the most "
            "important events or ideas, and any noteworthy details from the "
            "transcript. You may add brief general knowledge naturally when "
            "it helps explain the video, but keep the answer short and "
            "summary-like. "
        )
    else:
        style_instruction = (
            "Answer normally and naturally, using the transcript as the main "
            "source while blending in helpful general knowledge where it adds "
            "value. "
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that answers questions about a video. "
                "Timestamped transcript excerpts from the video are provided "
                "below (format \"[mm:ss-mm:ss] text\"). Write one unified "
                "answer that blends the transcript excerpts with helpful "
                "general knowledge naturally, without labeling the answer "
                "into separate sections. Use the transcript excerpts as the "
                "main source, but you may add concise background knowledge "
                "when it helps explain the topic or fill small gaps. Do not "
                "pretend general knowledge came from the video. If the video "
                "does not fully cover something, weave in the extra context "
                "smoothly and honestly. "
                f"{style_instruction}"
                "Use the prior conversation turns (if any) to understand "
                "follow-up questions, but still ground video-specific claims "
                "in the transcript excerpts when they exist. "
                f"Respond in {answer_language}."
            ),
        },
    ]

    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

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
        max_tokens=450,
        temperature=0.3,
    )

    return completion.choices[0].message.content.strip()