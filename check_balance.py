import re


def _extract_template(content):
    start_tag = "<template>"
    end_tag = "</template>"
    start_idx = content.find(start_tag)
    end_idx = content.rfind(end_tag)
    if start_idx == -1 or end_idx == -1:
        return None, 0
    
    template = content[start_idx + len(start_tag) : end_idx]
    offset = content[:start_idx].count("\n") + 1
    return template, offset


def _handle_tag(tag_str, tag_name, line_num, stack, void_elements):
    is_self_closing = tag_str.endswith("/>")
    is_closing = tag_str.startswith("</")

    if is_self_closing or tag_name in void_elements:
        return True

    if is_closing:
        if not stack:
            print(f"Error at line {line_num}: Unexpected closing tag </{tag_name}> (Stack empty)")
            return False

        last_tag, last_line = stack.pop()
        if last_tag != tag_name:
            print(f"Error at line {line_num}: Expected closing tag </{last_tag}> (opened at {last_line}), found </{tag_name}>")
            return False
    else:
        stack.append((tag_name, line_num))
    return True


def check_balance(filename):
    with open(filename, "r") as f:
        content = f.read()

    template_content, offset_line = _extract_template(content)
    if template_content is None:
        print("Template not found")
        return

    void_elements = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    tag_pattern = re.compile(r"</?([a-zA-Z0-9-]+)(?:\s[^>]*)?/?>")
    stack = []

    for i, line in enumerate(template_content.split("\n")):
        line_num = offset_line + i + 1
        pos = 0
        while pos < len(line):
            match = tag_pattern.search(line, pos)
            if not match:
                break
            if not _handle_tag(match.group(0), match.group(1).lower(), line_num, stack, void_elements):
                return
            pos = match.end()

    if stack:
        print("Error: Unclosed tags at end of file:")
        for tag, line in stack:
            print(f"  <{tag}> opened at line {line}")
    else:
        print("No nesting errors found.")


check_balance("ui/src/components/SettingsPage.vue")
