"""Composite-helper static expander (Stage 3 post-process).

Stage 3 currently emits some scene parts via composite helper functions
(see agent_prompt/Stage3_lab_addendum). Those helpers internally call
several `create_box(...)` primitives, but to downstream parsers
(stage5_describe / stage6_geometry / stage7_small_objects) the helper call is
opaque -- they only understand `create_box` / `create_cylinder`. Result:
the entire helper-built object disappears from describe_output.json,
DETAILED_GEOMETRY, and the small-object PlaneFinder.

Fix: at the tail of Stage 3 (after rotation correction), rewrite each
helper call into the same primitive `create_box` calls the helper body
would produce at Blender runtime. Geometry is bit-for-bit equivalent.

Adding a new helper:
1) Add an entry under SPEC with the helper's hard-coded constants.
2) Implement a `_expand_<helper_name>(positional, kwargs, indent) -> List[str]`
   that returns the lines to substitute the call with.
3) Register it in HELPER_DISPATCH below.
4) Add a unit test mirroring tests/test_composite_helpers.py.

The numeric constants in SPEC MUST match the literals in the helper body
shown in the addendum prompt; tests/test_composite_helpers.py pins this
contract.
"""

from __future__ import annotations

import ast
import math
import re
from typing import Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# SPEC: hard-coded geometric constants for each composite helper.
# Source of truth for the static expander; MUST equal the literals in
# agent_prompt/Stage3_lab_addendum (test-enforced).
# ---------------------------------------------------------------------------
SPEC: Dict[str, Dict[str, float]] = {
    "create_double_deck_bench": {
        "H_work": 0.9,
        "H_shelf": 1.4,
        "T_shelf": 0.04,
        "D_shelf": 0.30,
        "W_post": 0.05,
    },
}


# ---------------------------------------------------------------------------
# Tiny safe scalar evaluator (math constants/functions only)
# ---------------------------------------------------------------------------
_SAFE_GLOBALS = {
    "__builtins__": {},
    "math": math,
    "pi": math.pi,
}


def _safe_eval_scalar(expr: str) -> Optional[float]:
    """Evaluate `expr` to a float using a minimal math-only environment.

    Returns None on any failure (variable references, function calls outside
    `math.*`, syntax errors, division by zero, etc.) -- caller falls back to
    "leave the helper call alone" when it cannot evaluate the parameter.
    """
    expr = expr.strip()
    try:
        return float(ast.literal_eval(expr))
    except (ValueError, SyntaxError):
        pass
    try:
        return float(eval(expr, _SAFE_GLOBALS, {}))  # noqa: S307 (sandboxed)
    except Exception:
        return None


def _format_float(value: float) -> str:
    """Render a float so it round-trips losslessly while staying short.

    `repr(0.1+0.2) == '0.30000000000000004'`; we instead use `%g` with
    enough precision that all SPEC-derived values land on a clean decimal
    (0.45, 1.15, 1.38, etc.).
    """
    if value == int(value):
        return f"{int(value)}"
    return f"{value:.10g}"


def _format_tuple(values: Tuple[float, ...]) -> str:
    return "(" + ", ".join(_format_float(v) for v in values) + ")"


# ---------------------------------------------------------------------------
# Call extraction (multi-line aware)
# ---------------------------------------------------------------------------
def _find_call_span(code: str, start: int) -> Optional[Tuple[int, int]]:
    """Given that code[start:start+len(name)] is a helper name followed by
    optional whitespace and '(', return (open_paren_idx, close_paren_idx_exclusive)
    spanning the matched parentheses, or None if unbalanced."""
    paren_start = code.find("(", start)
    if paren_start < 0:
        return None
    depth = 0
    in_str: Optional[str] = None
    i = paren_start
    while i < len(code):
        ch = code[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in ("'", '"'):
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return (paren_start, i + 1)
        i += 1
    return None


def _split_top_level_args(s: str) -> List[str]:
    """Split a comma-separated arg list by top-level commas only."""
    args: List[str] = []
    buf: List[str] = []
    depth_paren = 0
    depth_bracket = 0
    in_str: Optional[str] = None
    for ch in s:
        if in_str:
            buf.append(ch)
            if ch == "\\":
                # naive escape pass-through: next char will be appended too
                # but we don't need to look ahead for our use case.
                pass
            elif ch == in_str:
                in_str = None
            continue
        if ch in ("'", '"'):
            in_str = ch
            buf.append(ch)
            continue
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
        elif ch == "," and depth_paren == 0 and depth_bracket == 0:
            args.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        args.append(tail)
    return args


def _split_positional_kwargs(args: List[str]) -> Tuple[List[str], Dict[str, str]]:
    positional: List[str] = []
    kwargs: Dict[str, str] = {}
    seen_kw = False
    for a in args:
        m = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", a, re.DOTALL)
        if m and not _looks_like_comparison(a):
            seen_kw = True
            kwargs[m.group(1)] = m.group(2).strip()
        else:
            if seen_kw:
                # Stage 3 emits well-formed calls; if positional appears
                # after a kwarg something is wrong -- bail out by treating
                # this arg as positional anyway and let the test suite
                # catch the resulting numeric drift.
                positional.append(a.strip())
            else:
                positional.append(a.strip())
    return positional, kwargs


def _looks_like_comparison(arg: str) -> bool:
    """`x == y` / `x != y` accidentally match the kwarg regex above."""
    return any(op in arg for op in ("==", "!=", "<=", ">=", "=>"))


def _line_indent_at(code: str, idx: int) -> str:
    line_start = code.rfind("\n", 0, idx) + 1
    line_prefix = code[line_start:idx]
    leading = re.match(r"^[ \t]*", line_prefix)
    return leading.group(0) if leading else ""


def _is_def_site(code: str, idx: int) -> bool:
    """Return True when the helper-name token at `idx` is the function's
    name inside a `def helper_name(...)` definition (rather than a call
    site). Stage 3 emits the helper definition verbatim near the top of
    every generated script so Blender can execute the helper at runtime --
    we must NEVER expand the definition itself.
    """
    line_start = code.rfind("\n", 0, idx) + 1
    prefix = code[line_start:idx]
    return bool(re.match(r"^\s*def\s+$", prefix))


# ---------------------------------------------------------------------------
# create_double_deck_bench expansion
# ---------------------------------------------------------------------------
def _expand_double_deck_bench(
    positional: List[str], kwargs: Dict[str, str], indent: str
) -> Optional[List[str]]:
    """Mirror the helper body in agent_prompt/Stage3_lab_addendum.

    Returns 4 lines:
        worktop  (CENTER z = 0.45,            mat_top,   show_direction default)
        post_L   (CENTER z = 1.15, local x<0, mat_frame, show_direction=False)
        post_R   (CENTER z = 1.15, local x>0, mat_frame, show_direction=False)
        upper_shelf (CENTER z = 1.38,         mat_top,   show_direction=False)

    Returns None if any required parameter cannot be evaluated to a number;
    the caller then leaves the helper call untouched.
    """
    if len(positional) < 5:
        return None

    name_lit = positional[0].strip()
    name_match = re.match(r'^["\']([^"\']+)["\']$', name_lit)
    if not name_match:
        return None
    name = name_match.group(1)

    cx = _safe_eval_scalar(positional[1])
    cy = _safe_eval_scalar(positional[2])
    L = _safe_eval_scalar(positional[3])
    D = _safe_eval_scalar(positional[4])
    if any(v is None for v in (cx, cy, L, D)):
        return None

    spec = SPEC["create_double_deck_bench"]
    H_work = spec["H_work"]
    H_shelf = spec["H_shelf"]
    T_shelf = spec["T_shelf"]
    D_shelf = spec["D_shelf"]
    W_post = spec["W_post"]
    H_post = H_shelf - H_work

    # Yaw -> needed to project local post offsets into world space.
    rotation_str = kwargs.get("rotation", "(0, 0, 0)").strip()
    yaw = _extract_yaw(rotation_str)
    if yaw is None:
        return None

    mat_top = kwargs.get("mat_top", "None")
    mat_frame = kwargs.get("mat_frame", "None")
    collection = kwargs.get("collection", "None")

    # Local post offsets (in bench-local frame): along ±x at the short ends.
    local_post_dx = L / 2.0 - W_post / 2.0
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)

    def _world_post_xy(local_x: float) -> Tuple[float, float]:
        wx = cos_y * local_x  # local_y is 0
        wy = sin_y * local_x
        return (cx + wx, cy + wy)

    post_l_xy = _world_post_xy(-local_post_dx)
    post_r_xy = _world_post_xy(+local_post_dx)
    post_z = H_work + H_post / 2.0          # = 1.15
    shelf_z = H_shelf - T_shelf / 2.0       # = 1.38
    worktop_z = H_work / 2.0                # = 0.45

    # Each emitted line keeps the original `rotation` source string verbatim
    # so a later reader (or stage5_describe's parser) can still recognize the
    # symbolic form `(0, 0, math.pi/2)` even though we already used a numeric
    # yaw to compute post offsets. This keeps human-readable code intact and
    # ensures all 4 parts share a single rotation source -- they rotate as a
    # rigid body (addendum B.5).
    def _emit_box(
        suffix: str,
        loc: Tuple[float, float, float],
        dim: Tuple[float, float, float],
        material: str,
        show_direction: Optional[bool],
    ) -> str:
        parts = [
            f'"{name}_{suffix}"',
            _format_tuple(loc),
            _format_tuple(dim),
            f"rotation={rotation_str}",
            f"material={material}",
            f"collection={collection}",
        ]
        if show_direction is False:
            parts.append("show_direction=False")
        return f"{indent}create_box({', '.join(parts)})"

    return [
        _emit_box(
            "worktop",
            (cx, cy, worktop_z),
            (L, D, H_work),
            mat_top,
            show_direction=None,  # use helper default (True)
        ),
        _emit_box(
            "post_L",
            (post_l_xy[0], post_l_xy[1], post_z),
            (W_post, W_post, H_post),
            mat_frame,
            show_direction=False,
        ),
        _emit_box(
            "post_R",
            (post_r_xy[0], post_r_xy[1], post_z),
            (W_post, W_post, H_post),
            mat_frame,
            show_direction=False,
        ),
        _emit_box(
            "upper_shelf",
            (cx, cy, shelf_z),
            (L, D_shelf, T_shelf),
            mat_top,
            show_direction=False,
        ),
    ]


def _extract_yaw(rotation_expr: str) -> Optional[float]:
    """Pull the third component out of a `(rx, ry, rz)` tuple expression."""
    expr = rotation_expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1]
    parts = _split_top_level_args(expr)
    if len(parts) < 3:
        return None
    return _safe_eval_scalar(parts[2])


# ---------------------------------------------------------------------------
# Public dispatch + entry point
# ---------------------------------------------------------------------------
HelperExpander = Callable[[List[str], Dict[str, str], str], Optional[List[str]]]

HELPER_DISPATCH: Dict[str, HelperExpander] = {
    "create_double_deck_bench": _expand_double_deck_bench,
}


def expand_composite_helpers(code: str) -> str:
    """Statically expand every known composite-helper call in `code`.

    Behavior contract:
      * Function definitions (`def helper_name(...):`) are NEVER touched --
        Stage 3 emits the helper body in every script for Blender runtime
        execution and downstream tooling (e.g. `bpy --python` smoke tests)
        still need to see it.
      * A call whose positional args cannot be evaluated to literal floats
        is left in place (caller can grep for the surviving helper name).
      * Idempotent: running this twice yields the same result as once,
        because emitted lines contain only `create_box` (no helper names).
    """
    if not any(name + "(" in code for name in HELPER_DISPATCH):
        return code

    # 1) Collect every call site (skipping `def helper_name(...)`).
    sites: List[Tuple[str, HelperExpander, int]] = []
    for helper_name, expander in HELPER_DISPATCH.items():
        for m in re.finditer(rf"\b{re.escape(helper_name)}\s*\(", code):
            if _is_def_site(code, m.start()):
                continue
            sites.append((helper_name, expander, m.start()))

    if not sites:
        return code

    # 2) Apply replacements right-to-left so saved indices stay valid:
    #    earlier (smaller index) substrings are unaffected by edits made
    #    further to the right.
    sites.sort(key=lambda s: s[2])
    result = code
    for helper_name, expander, start in reversed(sites):
        span = _find_call_span(result, start)
        if span is None:
            continue
        paren_open, paren_close = span
        inner = result[paren_open + 1:paren_close - 1]
        args = _split_top_level_args(inner)
        positional, kwargs = _split_positional_kwargs(args)
        indent = _line_indent_at(result, start)
        new_lines = expander(positional, kwargs, indent)
        if new_lines is None:
            # Cannot statically expand -- leave call alone. (Caller can
            # grep for the surviving helper name.)
            continue
        replacement = "\n".join(new_lines)

        line_start = result.rfind("\n", 0, start) + 1
        prefix_on_line = result[line_start:start]
        if prefix_on_line.strip() == "":
            # Common case: helper occupies its own line. Drop the line and
            # substitute the emitted block, preserving leading indent.
            result = result[:line_start] + replacement + result[paren_close:]
        else:
            # Helper call appears mid-line (rare); keep the prefix and
            # splice in the emitted lines starting at the helper-name token.
            result = result[:start] + replacement.lstrip() + result[paren_close:]

    return result
