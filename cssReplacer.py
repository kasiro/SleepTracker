import cssutils
from pathlib import Path
import re

# Отключаем лог
cssutils.log.setLevel(50)

# Типы правил
STYLE_RULE = 1      # .class { ... }
IMPORT_RULE = 3     # @import
KEYFRAMES_RULE = 7  # @keyframes
MEDIA_RULE = 4      # @media


def format_css_rule(rule, indent="    "):
    """Форматирует обычное CSS-правило"""
    sel = rule.selectorText.strip()
    props = [f"{indent}{p.name}: {p.value};" for p in rule.style]
    if not props:
        return f"{sel} {{}}"
    return f"{sel} {{\n" + "\n".join(props) + "\n}"


def format_at_rule(rule, indent="    "):
    """Форматирует @-правила"""
    if rule.type == IMPORT_RULE:
        return f"@import url('{rule.href}');"
    elif rule.type == KEYFRAMES_RULE:
        frames = []
        for keyframe in rule:
            style_lines = [f"{indent * 2}{p.name}: {p.value};" for p in keyframe.style]
            frame_block = f"{indent}{keyframe.keyText} {{\n" + "\n".join(style_lines) + f"\n{indent}}}"
            frames.append(frame_block)
        return f"@keyframes {rule.name} {{\n" + "\n".join(frames) + "\n}"
    elif rule.type == MEDIA_RULE:
        query = rule.media.mediaText
        inner = []
        for r in rule:
            if hasattr(r, 'selectorText'):
                inner.append(f"{indent}{format_css_rule(r, indent * 2)}")
        return f"@media {query} {{\n" + "\n".join(inner) + "\n}"
    else:
        # Резервный вывод для неизвестных @-правил
        rule_text = rule.cssText if hasattr(rule, 'cssText') else str(rule)
        if '@charset' not in rule_text:
            return rule_text
        return ''

def get_rule_key(rule):
    """Генерирует уникальный ключ для правила для сравнения"""
    if rule.type == STYLE_RULE:
        # print(rule.selectorText)
        return f"style:{rule.selectorText.strip().lower()}"                                 
    elif rule.type == IMPORT_RULE:
        return f"import:{rule.href}"
    elif rule.type == KEYFRAMES_RULE:
        # Для keyframes используем имя и содержимое
        frames_content = []
        for keyframe in rule:
            frame_props = [f"{p.name}:{p.value}" for p in keyframe.style]
            frames_content.append(f"{keyframe.keyText}:{';'.join(sorted(frame_props))}")
        return f"keyframes:{rule.name}:{':'.join(sorted(frames_content))}"
    elif rule.type == MEDIA_RULE:
        # Для media используем запрос и содержимое
        query = rule.media.mediaText
        inner_content = []
        for r in rule:
            if hasattr(r, 'selectorText'):
                props = [f"{p.name}:{p.value}" for p in r.style]
                inner_content.append(f"{r.selectorText}:{';'.join(sorted(props))}")
        return f"media:{query}:{':'.join(sorted(inner_content))}"
    else:
        # Для других правил используем CSS текст
        return f"other:{rule.cssText}"


def load_css_rules(css_text):
    """Парсит CSS и возвращает правила с уникальными ключами"""
    try:
        sheet = cssutils.parseString(css_text, encoding='utf-8')
    except Exception as e:
        print(f"❌ Ошибка парсинга CSS: {e}")
        sheet = cssutils.parseString("")  # пустой лист

    rules_dict = {}  # для всех правил с ключами
    rules_list = []  # для сохранения порядка

    for rule in sheet:
        key = get_rule_key(rule)
        rules_dict[key] = rule
        rules_list.append((key, rule))

    return rules_dict, rules_list


def merge_inline_with_external(html_file, css_file):
    try:
        html_content = Path(html_file).read_text(encoding='utf-8')
        css_content = Path(css_file).read_text(encoding='utf-8')
    except Exception as e:
        print(f"❌ Ошибка чтения файлов: {e}")
        return

    print(f"📄 HTML: {html_file}")
    print(f"🎨 CSS: {css_file}\n")

    # Извлекаем <style> из HTML
    style_match = re.search(r'<style[^>]*>(.*?)</style>', html_content, re.DOTALL | re.IGNORECASE)
    inline_css = style_match.group(1).strip() if style_match else ""

    print("🔍 Парсинг CSS...")

    # Загружаем правила
    ext_rules, ext_list = load_css_rules(css_content)
    inline_rules, inline_list = load_css_rules(inline_css)

    print(f"   ✅ Из CSS-файла: {len(ext_rules)} правил")
    print(f"   ✅ Из <style>: {len(inline_rules)} правил")

    # Объединяем: внешние приоритетны
    final_rules = ext_rules.copy()
    new_from_inline = 0

    for key, rule in inline_rules.items():
        if key not in final_rules:
            final_rules[key] = rule
            new_from_inline += 1

    print(f"   🔄 Итого: {len(final_rules)} правил (+{new_from_inline} новых)\n")

    # Формируем итоговый CSS, сохраняя порядок из внешнего файла
    lines = []
    processed_keys = set()

    # 1. Сначала добавляем все правила из внешнего CSS в оригинальном порядке
    for key, rule in ext_list:
        if key in processed_keys:
            continue
            
        if rule.type == IMPORT_RULE:
            lines.append(format_at_rule(rule))
        elif rule.type == STYLE_RULE:
            lines.append(format_css_rule(rule))
        else:
            lines.append(format_at_rule(rule, indent="    "))
        
        processed_keys.add(key)

    # 2. Добавляем новые правила из inline CSS
    # if new_from_inline > 0:
        # lines.append("")  # Пустая строка для разделения
        # lines.append("/* Правила из <style> */")
        
        for key, rule in inline_list:
            if key not in processed_keys:
                if rule.type == IMPORT_RULE:
                    lines.append(format_at_rule(rule))
                elif rule.type == STYLE_RULE:
                    lines.append(format_css_rule(rule))
                else:
                    lines.append(format_at_rule(rule, indent="    "))
                
                processed_keys.add(key)

    # Убираем возможные пустые строки в начале
    final_css = "\n".join(lines).strip()

    # Вывод
    print("=" * 60)
    print("✨ ИТОГОВЫЙ ТЕГ <style>")
    print("=" * 60)
    print(f"<style>\n{final_css}\n</style>")
    print("=" * 60)


# ========================
#   ТОЧКА ВХОДА
# ========================
if __name__ == "__main__":
    html_file = "index.html"   # ← замени на свой
    css_file = "rep.css"    # ← замени на свой
    merge_inline_with_external(html_file, css_file)
