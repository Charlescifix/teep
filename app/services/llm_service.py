# app/services/llm_service.py (example)

import openai
from app.config import settings

openai.api_key = settings.OPENAI_API_KEY

def generate_llm_answer(user_query: str, combined_context: str) -> str:
    """
    Calls OpenAI ChatCompletion with user_query + combined_context.
    Returns a single, coherent answer to the user's question.
    """

    # -- ONE system message that merges both sets of instructions:
    system_message = (
        "You are TEEP's customer support assistant, helping users with questions "
        "about TEEP's digital payment platform. You must only respond to questions "
        "about:\n"
        "- Airtime & Data purchase: (Instantly top up your mobile and data plans.)\n"
        "- TV/Cable subscription: (Pay for your TV and cable on time.)\n"
        "- Tuition payment: (Settle school fees for all educational institutions, hassle-free.)\n"
        "- Tickets purchase: (Secure tickets for events and travel with fast, reliable payments.)\n"
        "\n"
        "If a question is outside these topics, politely decline to answer and guide the user "
        "to ask TEEP payment-related questions or contact TEEP support.\n\n"

        "Additional context:\n"
        "TEEP operates as a fintech aggregator or digital payments platform, offering a one-stop hub "
        "for multiple bill payment needs (like mobile top-ups, utility bills, cable subscriptions, and more). "
        "Use the provided context to answer the user's question accurately. If the answer isn't "
        "in the context, say you don't have that information.\n"
    )

    # -- The user prompt includes their actual question + the retrieved chunked context
    user_prompt = (
        f"Question: {user_query}\n\n"
        f"Context:\n{combined_context}\n\n"
        "Answer the question above based on the context. "
        "If the question is outside TEEP’s payment topics, politely refuse and guide them accordingly."
    )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.5,       # adjust as desired
        max_tokens=500,        # adjust as desired
    )

    final_answer = response["choices"][0]["message"]["content"]
    return final_answer
