import os
import re
import threading

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


model_id = os.getenv(
    "MODEL_ID",
    "Josephgflowers/FinR1-llama-8b-multi-language-thinking"
)

generation_lock = threading.Lock()


def load_model():
    """Load the multilingual financial LLM in 4-bit precision."""

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        use_fast=True
    )

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quantization_config,
        device_map="auto",
        torch_dtype=torch.float16
    )

    model.eval()

    return tokenizer, model


tokenizer, model = load_model()


def remove_thinking(text):
    """Remove model reasoning tags from the customer-facing response."""

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    text = text.replace("<think>", "")
    text = text.replace("</think>", "")

    return text.strip()


def generate_reply(message, language="en", history=None):
    """Generate one customer-facing response."""

    if history is None:
        history = []

    language_names = {
        "en": "English",
        "es": "Spanish",
        "pt": "Portuguese"
    }

    language_name = language_names.get(language, "English")

    system_message = (
        "You are a banking customer-service assistant. "
        "Answer clearly and directly. "
        f"Answer in {language_name}. "
        "Do not expose internal reasoning or thinking tags."
    )

    messages = [
        {
            "role": "system",
            "content": system_message
        }
    ]

    for item in history[-10:]:
        role = item.get("role")
        content = item.get("content")

        if role in {"user", "assistant"} and content:
            messages.append(
                {
                    "role": role,
                    "content": content
                }
            )

    messages.append(
        {
            "role": "user",
            "content": message
        }
    )

    input_ids = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)

    with generation_lock:
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                max_new_tokens=192,
                do_sample=False,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.eos_token_id
            )

    generated_ids = output_ids[0][input_ids.shape[-1]:]

    response = tokenizer.decode(
        generated_ids,
        skip_special_tokens=True
    )

    return remove_thinking(response)