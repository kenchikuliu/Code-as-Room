"""
Shared syntax fixes for LLM-generated Blender Python (Stage3/4/8/9).

Root cause: ArrowCleaner removes create_direction_arrow(...) inside create_box,
leaving an empty if-block with return at the same indent as if -> SyntaxError.
"""

import re


def fix_empty_if_show_direction_before_return(code: str) -> str:
    """
    Turn invalid:
        if show_direction and ...:
        return obj
    into:
        if show_direction and ...:
            pass
        return obj
    """
    pat = re.compile(
        r"^([ \t]+)(if show_direction[^\n]*:)\n(?:[ \t]*\n)*\1return obj\s*$",
        re.MULTILINE,
    )

    def repl(m: re.Match) -> str:
        ind = m.group(1)
        if_head = m.group(2)
        return f"{ind}{if_head}\n{ind}    pass\n{ind}return obj"

    return pat.sub(repl, code)
