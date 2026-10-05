import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)


def call_llm(prompt, system="you are a helpful assistant"):
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


print("Setup Complete")


from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class RouterState(TypedDict):
    question: str
    intent: str
    context: str
    answer: str


def classify_intent(state):
    question = state["question"]

    intent = call_llm(
        f"Classify this question into exactly one category: billing, hr, or general.\n\nQuestion: {question}\n\nReply with ONLY the category word (billing, hr, or general):",
        system="You classify questions. Reply with exactly one word: billing, hr, or general."
    )

    intent = intent.strip().lower()

    if intent not in ["billing", "hr", "general"]:
        intent = "general"

    print(f"  [CLASSIFY] Intent: {intent}")

    return {"intent": intent}


def handle_billing(state):
    answer = call_llm(
        state["question"],
        system="You are a billing support agent. Answer questions about subscriptions, pricing, payments, and refunds. Be helpful and concise."
    )

    print(f"  [BILLING] Answered")

    return {
        "answer": answer,
        "context": "billing_docs"
    }


def handle_hr(state):
    answer = call_llm(
        state["question"],
        system="You are an HR assistant. Answer questions about leave policy, WFH, probation, and company policies. Be helpful and concise."
    )

    print(f"  [HR] Answered")

    return {
        "answer": answer,
        "context": "hr_docs"
    }


def handle_general(state):
    answer = call_llm(
        state["question"],
        system="You are a helpful assistant. Answer the question concisely."
    )

    print(f"  [GENERAL] Answered")

    return {
        "answer": answer,
        "context": "general_knowledge"
    }


def route_by_intent(state):
    intent = state["intent"]

    if intent == "billing":
        return "handle_billing"

    elif intent == "hr":
        return "handle_hr"

    else:
        return "handle_general"


router_graph = StateGraph(RouterState)

router_graph.add_node("classify", classify_intent)
router_graph.add_node("handle_billing", handle_billing)
router_graph.add_node("handle_hr", handle_hr)
router_graph.add_node("handle_general", handle_general)


router_graph.add_edge(START, "classify")

router_graph.add_conditional_edges(
    "classify",
    route_by_intent,
    {
        "handle_billing": "handle_billing",
        "handle_hr": "handle_hr",
        "handle_general": "handle_general",
    }
)


router_graph.add_edge("handle_billing", END)
router_graph.add_edge("handle_hr", END)
router_graph.add_edge("handle_general", END)


router_app = router_graph.compile()

print("✅ Router graph ready!")
print("   Flow: classify → (billing | hr | general) → END")


png_data = router_app.get_graph().draw_mermaid_png()

with open("langgraph.png", "wb") as f:
    f.write(png_data)

print("Graph image saved as langgraph.png")


result = router_app.invoke(
    {"question": "How do I cancel my subscription?"}
)

print(f"\nIntent: {result['intent']}")
print(f"Answer: {result['answer']}")