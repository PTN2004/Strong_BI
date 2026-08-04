from transformers import AutoProcessor, AutoModelForMultimodalLM

processor = AutoProcessor.from_pretrained("Tu522004/RD-9B-Distill")
model = AutoModelForMultimodalLM.from_pretrained("Tu522004/RD-9B-Distill")
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "What animal is on the candy?"}
        ]
    },
]
inputs = processor.apply_chat_template(
	messages,
	add_generation_prompt=True,
	tokenize=True,
	return_dict=True,
	return_tensors="pt",
).to(model.device)

outputs = model.generate(**inputs, max_new_tokens=40)
print(processor.decode(outputs[0][inputs["input_ids"].shape[-1]:]))