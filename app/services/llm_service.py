# app/services/llm_service.py (example)

import openai
from app.config import settings

openai.api_key = settings.OPENAI_API_KEY

def generate_llm_answer(user_query: str, combined_context: str) -> str:
    """
    Calls OpenAI ChatCompletion with user_query + combined_context.
    Returns a single, coherent answer to the user's question.
    """

    # -- ONE system message that merges both sets of instructions.
    # The in-scope list below tracks the sections of data/teep_knowledge_base.md.
    # Anything the knowledge base answers has to be listed here, or retrieval
    # surfaces the right chunk and the model then refuses to use it.
    system_message = (
        "You are TEEP's customer support assistant, helping users with questions "
        "about TEEP's digital payment platform. You may respond to questions about:\n"
        "- Services & payments: Airtime & Data top-ups, TV/Cable subscriptions, "
        "Education payments (JAMB and selected school fees), flight and event Tickets, "
        "Betting via partners, electricity and other supported bills.\n"
        "- Using the app: creating an account, paying a bill from the dashboard, "
        "topping up, spend Insights and analytics, getting help when something goes wrong.\n"
        "- Pricing: setup and 24/7 support fees.\n"
        "- Refunds: failed transactions, how to request a refund, processing times.\n"
        "- The Referral Program: how it works, the bonus, who counts as a referred customer.\n"
        "- Privacy & security: what data TEEP collects and how it is used or shared, "
        "encryption and two-factor authentication, NDPR/NDPC compliance, children's privacy, "
        "opting out, and account deletion.\n"
        "- About TEEP: what TEEP is and does, who built it (Teksag Energy LTD), "
        "its mission, vision and goals, integrations and partners, and customer reviews.\n"
        "- Contact details: support email, phone number, address and social media.\n"
        "\n"
        "If a question is outside these topics, politely decline to answer and guide the user "
        "to ask a TEEP-related question or to contact TEEP support at support@teep.africa.\n\n"

        "Additional context:\n"
        "TEEP operates as a fintech aggregator or digital payments platform, offering a one-stop hub "
        "for multiple bill payment needs (like mobile top-ups, utility bills, cable subscriptions, and more). "
        "Use the provided context to answer the user's question accurately.\n\n"

        "Grounding rules, which override the desire to be helpful:\n"
        "- State only what the context says. Never add a fact, figure, fee, timeline, policy "
        "term, supported country, supported provider or contact detail that is not in it.\n"
        "- If the context does not answer the question, say plainly that you don't have that "
        "information and point the user to support@teep.africa. Do not guess, and do not "
        "soften a gap into a partial 'yes'.\n"
        "- Never confirm that a service, bill type, provider or location is supported unless "
        "the context names it. If a user asks about one that is not named, say you cannot "
        "confirm it and refer them to support.\n"
    )

    # -- The user prompt includes their actual question + the retrieved chunked context
    user_prompt = (
        f"Question: {user_query}\n\n"
        f"Context:\n{combined_context}\n\n"
        "Answer the question above based on the context. "
        "If the question is outside the TEEP topics listed in your instructions, "
        "politely refuse and guide them accordingly."
    )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ],
        # Low temperature: this is a grounded support bot, so faithfulness to the
        # retrieved context matters more than varied phrasing. At 0.5 the model
        # embellished answers with details the knowledge base never stated.
        temperature=0.2,
        max_tokens=500,        # adjust as desired
    )

    final_answer = response["choices"][0]["message"]["content"]
    return final_answer
