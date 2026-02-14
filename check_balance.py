import re


def check_balance(filename):
    with open(filename, "r") as f:
        content = f.read()

    # Extract template
    start_tag = "<template>"
    end_tag = "</template>"

    start_idx = content.find(start_tag)
    end_idx = content.rfind(end_tag)

    if start_idx == -1 or end_idx == -1:
        print("Template not found")
        return

    template_content = content[start_idx + len(start_tag) : end_idx]
    lines = template_content.split("\n")

    stack = []
    # Simple regex for opening and closing tags.
    # Ignores self-closing like <br/> <input /> <img /> or void elements.
    # Also ignores comments.

    void_elements = set(
        [
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        ]
    )

    tag_pattern = re.compile(r"</?([a-zA-Z0-9-]+)(?:\s[^>]*)?/?>")

    offset_line = content[:start_idx].count("\n") + 1

    for i, line in enumerate(lines):
        line_num = offset_line + i + 1
        pos = 0
        while pos < len(line):
            match = tag_pattern.search(line, pos)
            if not match:
                break

            tag_str = match.group(0)
            tag_name = match.group(1).lower()
            pos = match.end()

            # Check for self-closing slash
            is_self_closing = tag_str.endswith("/>")
            is_closing = tag_str.startswith("</")

            if is_self_closing:
                continue

            if tag_name in void_elements:
                continue

            if is_closing:
                if not stack:
                    print(
                        f"Error at line {line_num}: Unexpected closing tag </{tag_name}> (Stack empty)"
                    )
                    return

                last_tag, last_line = stack.pop()
                if last_tag != tag_name:
                    print(
                        f"Error at line {line_num}: Expected closing tag </{last_tag}> (opened at {last_line}), found </{tag_name}>"
                    )
                    # Put it back to maybe continue? No, usually fatal.
                    return
            else:
                # Opening tag
                # Check if it's not a void element
                stack.append((tag_name, line_num))

    if stack:
        print("Error: Unclosed tags at end of file:")
        for tag, line in stack:
            print(f"  <{tag}> opened at line {line}")
    else:
        print("No nesting errors found.")


check_balance("ui/src/components/SettingsPage.vue")
