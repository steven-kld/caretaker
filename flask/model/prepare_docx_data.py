import os
import json
from zipfile import ZipFile
from lxml import etree
from docx import Document
from pathlib import Path
import openai

# --- CONFIG ---
OPENAI_API_KEY="sk-proj-..."

RAW_DIR = Path("raw")
OUT_DIR = Path("instructions")
MODEL = "gpt-4-turbo"
MAX_TOKENS = 2400
KEY_LINE_PROMPT = """
Ты анализируешь внутреннюю инструкцию компании, написанную на русском языке.

Эти документы обычно начинаются с вводной информации и метаданных (например, сроки, роли, комментарии), а только потом переходят к пошаговым действиям.

Твоя задача - определить первую строку, с которой начинается именно практическая часть инструкции.

Ответь ТОЧНО этой строкой - без комментариев, пояснений или дополнительных символов. Если точно не уверен - выбери наиболее подходящую строку.
"""

MAIN_PROMPT = """
Отвечай строго на русском языке.
ВАЖНО: Не оборачивай вывод в Markdown. Не используй тройные кавычки, кавычки вокруг JSON или любые символы до или после JSON. Выводи только чистый JSON.

Ты - технический аналитик. Тебе предоставлены:
- intro - текст вводной части документа, до начала шагов
- steps - список шагов, каждый из которых может включать изображения

Сформируй структурированный JSON следующего вида:
{
  "task_id": "string",
  "title": "string",
  "intro": "string",
  "steps": [
    {
      "step_num": 1,
      "summary": "обобщенный смысл шага...",
      "text": "инструкция...",
      "images": ["image_0.png", "image_1.png"],
      "keywords": ["поле", "фильтр", "контрагент", "..."]
    }
  ]
}

title должен быть кратким и отражать основную цель задачи (вводная тебе поможет).
intro должен быть вставлен как единое текстовое поле (вся вводная часть документа).
steps - только действия. Не дублируй абзацы из intro туда.
steps - абсолютно весь предоставленный текст шагов важен и обязательно должен пристуствовать в steps.
steps - число шагов не должно превышать 3-4 шага, старайся объединить связанные действия в один шаг.
steps.summary - обобщающий короткий текст, максимум 150 символов.
steps.text - текст дословно без сокращений (весь текст шагов должен быть использован)
steps.keywords - добавляй основные ключи, 3-6 ключей.
"""

openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

def extract_text(docx_path):
    doc = Document(docx_path)
    return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

def detect_entry_line(docx_path):
    text = extract_text(docx_path)
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": KEY_LINE_PROMPT},
                  {"role": "user", "content": text}]
    )
    return response.choices[0].message.content.strip()

def parse_docx_to_elements(docx_path, img_dir):
    elements = []
    os.makedirs(img_dir, exist_ok=True)
    with ZipFile(docx_path) as z:
        doc_xml = z.read("word/document.xml")
        rels_xml = z.read("word/_rels/document.xml.rels")
        media = {n: z.read(n) for n in z.namelist() if n.startswith("word/media/")}

    rels = etree.fromstring(rels_xml)
    rel_map = {
        r.attrib["Id"]: r.attrib["Target"]
        for r in rels if r.attrib["Target"].startswith("media/")
    }

    tree = etree.fromstring(doc_xml)
    nsmap = tree.nsmap
    body = tree.find(".//w:body", namespaces=nsmap)

    img_count = 0
    for node in body:
        if etree.QName(node).localname != "p":
            continue
        text = "".join(node.itertext()).strip()
        if text:
            elements.append({ "type": "normal", "text": text })

        for blip in node.findall(".//a:blip", namespaces=nsmap):
            rId = blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            filename = rel_map.get(rId)
            if filename:
                img_bytes = media.get("word/" + filename)
                img_name = f"image_{img_count}.png"
                with open(img_dir / img_name, "wb") as f:
                    f.write(img_bytes)
                elements.append({ "type": "image", "placeholder": img_name })
                img_count += 1

    return elements

def merge_images_to_previous(elements):
    steps = []
    for el in elements:
        if el["type"] == "normal" and el["text"].strip():
            steps.append({ "type": "step", "text": el["text"].strip(), "images": [] })
        elif el["type"] == "image" and steps:
            steps[-1]["images"].append(el["placeholder"])
    return steps

def process_docx(docx_path):
    task_id = docx_path.stem
    task_dir = OUT_DIR / task_id
    img_dir = task_dir / "img"
    os.makedirs(task_dir, exist_ok=True)

    print(f"📄 Processing {task_id}...")
    elements = parse_docx_to_elements(docx_path, img_dir)

    with open(task_dir / "docx_parsed.json", "w", encoding="utf-8") as f:
        json.dump(elements, f, ensure_ascii=False, indent=2)

    entry_line = detect_entry_line(docx_path)

    split_index = next((i for i, el in enumerate(elements) if el.get("text") == entry_line), 0)
    intro = "\n".join(el["text"] for el in elements[:split_index] if el["type"] == "normal")

    steps = merge_images_to_previous(elements[split_index:])
    payload = { "intro": intro, "steps": steps }
    print("🤖 Calling GPT for structure...")
    
    response = openai_client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0.2,
        messages=[
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ]
    )

    text = response.choices[0].message.content.strip()

    # Soft validation and trim fallback
    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    if not text.endswith("}"):
        print("⚠️ GPT response was cut off. Attempting soft trim...")
        last_valid = text.rfind("},")
        if last_valid != -1:
            text = text[:last_valid+1] + "\n  ]\n}"

    try:
        structured = json.loads(text)
        with open(task_dir / "structured_output.json", "w", encoding="utf-8") as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved to {task_dir}/structured_output.json")
    except json.JSONDecodeError:
        print(f"❌ GPT returned invalid JSON for {task_id}")
        print(text)

def run():
    for docx_file in RAW_DIR.glob("*.docx"):
        process_docx(docx_file)

if __name__ == "__main__":
    run()