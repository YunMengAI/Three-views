from pathlib import Path


PROMPT_TYPE_TO_KEY = {
    "人物三视图": "character_turnaround",
    "人物面部三视图": "face_turnaround",
    "人物面部增强三视图": "face_plus_turnaround",
    "人物面部+三视图": "face_plus_turnaround",
    "人物角色卡": "character_card",
}


PROMPT_TYPE_TO_FILE = {
    "人物三视图": "人物三视图系统提示词.txt",
    "人物面部三视图": "人物面部三视图系统提示词.txt",
    "人物面部增强三视图": "人物面部增强三视图系统提示词.txt",
    "人物面部+三视图": "人物面部增强三视图系统提示词.txt",
    "人物角色卡": "人物角色卡系统提示词.txt",
}


PROMPT_TYPE_OPTIONS = [
    "人物三视图",
    "人物面部三视图",
    "人物面部增强三视图",
    "人物角色卡",
]


FALLBACK_REQUIREMENTS = {
    "人物三视图": "standard full-body character turnaround, front view, side view, back view, A-pose standing pose, identical costume in all views",
    "人物面部三视图": "upper body face turnaround from chest up, front face view, side face view, back head view, consistent facial features and hairstyle",
    "人物面部增强三视图": "combined character reference sheet with face detail views and full-body front side back turnaround, clean layout",
    "人物面部+三视图": "combined character reference sheet with face detail views and full-body front side back turnaround, clean layout",
    "人物角色卡": "complete character card with main full-body view, face close-up, outfit details, accessory details, color and material notes",
}


PROMPT_DIR = Path(__file__).with_name("prompt_templates")
CLOTHING_REFERENCE_PROMPT_FILE = PROMPT_DIR / "服装参考图系统提示词.txt"


def load_system_prompt(prompt_type, include_clothing_reference=False):
    prompt_file = PROMPT_DIR / PROMPT_TYPE_TO_FILE[prompt_type]
    prompt = prompt_file.read_text(encoding="utf-8").strip()
    if include_clothing_reference:
        clothing_prompt = CLOTHING_REFERENCE_PROMPT_FILE.read_text(encoding="utf-8").strip()
        prompt = f"{prompt}\n\n{clothing_prompt}"
    return prompt


USER_PROMPT_TEMPLATE = """请根据以下信息生成「{prompt_type}」提示词。

角色简介/生成要求：
{character_brief}

面部参考图：
{face_reference_note}

服装参考图：
{outfit_reference_note}

统一风格要求：
{visual_style}

输出要求：
只生成当前选择的「{prompt_type}」这一种提示词，不要生成其他类型提示词。"""


FALLBACK_PROMPT_TEMPLATE = """{subject}, based on the provided face reference image and outfit reference image, keep the same identity, hairstyle, facial structure, outfit design, colors, materials, and signature accessories. {specific_requirements}. Clean professional character design sheet, white background, soft studio lighting, sharp details, consistent proportions, no complex scene, no dramatic action."""
