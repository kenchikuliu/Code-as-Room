"""CodeValidator - code validation utility"""
import math
import re
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Validation result"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class CodeValidator:
    """Code validator"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def _log(self, msg: str, level: str = "info"):
        if self.verbose:
            prefix = {"info": "[i]", "success": "[OK]", "warning": "[!]", "error": "[X]"}.get(level, "")
            print(f"  {prefix} {msg}")

    def validate(self, code: str) -> ValidationResult:
        """
        Validate the code.

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # 1. Python syntax check
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            errors.append(f"Syntax error (line {e.lineno}): {e.msg}")
            return ValidationResult(False, errors, warnings)

        # 2. Check required functions
        if 'def run_layout_engine' not in code and 'def main' not in code:
            warnings.append("Missing main function: run_layout_engine or main")

        if 'def clear_scene' not in code:
            warnings.append("Missing clear_scene function")

        if 'def create_material' not in code:
            warnings.append("Missing create_material function")

        if 'def create_box' not in code:
            warnings.append("Missing create_box function")

        # 3. Check material usage
        create_calls = re.findall(r'create_box\([^)]+\)|create_cylinder\([^)]+\)', code)
        missing_material = 0
        for call in create_calls:
            if 'material=' not in call:
                missing_material += 1

        if missing_material > 0:
            warnings.append(f"{missing_material} objects missing material parameter")

        # 4. Check imports
        if 'import bpy' not in code:
            warnings.append("Missing 'import bpy'")

        # 5. Parenthesis balance check (per line)
        for line_num, line in enumerate(code.split('\n'), 1):
            if line.strip().startswith('#'):
                continue

            open_count = line.count('(')
            close_count = line.count(')')

            # Allow multi-line statements
            if abs(open_count - close_count) > 3:
                warnings.append(f"Line {line_num}: Possible parentheses imbalance")

        # 6. CRITICAL: dimensions order check (X must be >= Y)
        dim_warnings = self.check_dimensions_order(code)
        if dim_warnings:
            # Dimensions errors are treated as serious warnings
            for w in dim_warnings:
                warnings.append(w)
            self._log(f"Found {len(dim_warnings)} dimensions order violations!", "warning")

        # 7. CRITICAL: composite-furniture adjacency check (the two pieces of an L-desk / sectional sofa must be contiguous)
        comp_warnings = self.check_composite_adjacency(code)
        if comp_warnings:
            for w in comp_warnings:
                warnings.append(w)
            self._log(
                f"Found {len(comp_warnings)} broken composite-furniture pair(s)!",
                "warning",
            )
        
        is_valid = len(errors) == 0
        
        if self.verbose:
            if is_valid:
                self._log(f"Validation passed ({len(warnings)} warnings)", "success")
            else:
                self._log(f"Validation failed: {errors[0]}", "error")
        
        return ValidationResult(is_valid, errors, warnings)
    
    def quick_check(self, code: str) -> Tuple[bool, str]:
        """Quick syntax check"""
        try:
            compile(code, '<string>', 'exec')
            return True, "OK"
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    def check_dimensions_order(self, code: str) -> List[str]:
        """
        Check the dimensions order in every create_box call.

        Rule: for rectangular objects, dimensions[0] (X) must be >= dimensions[1] (Y)
        i.e. X = width/long-side (larger), Y = thickness/depth (smaller)

        Returns:
            List of warning messages for violations
        """
        warnings = []

        # Match create_box calls, extract name and dimensions
        # Format: create_box("name", (loc), (dim_x, dim_y, dim_z), ...)
        # Use a more precise regex to match the two parenthesis groups
        pattern = r'create_box\s*\(\s*["\']([^"\']+)["\']\s*,\s*\([^)]+\)\s*,\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)'

        for match in re.finditer(pattern, code):
            name = match.group(1)
            dim_x = float(match.group(2))
            dim_y = float(match.group(3))
            dim_z = float(match.group(4))

            # Skip square / near-square objects (X and Y differ by less than 10%)
            if abs(dim_x - dim_y) > 0.1 * max(dim_x, dim_y):
                # Detect X < Y (rule violation)
                if dim_x < dim_y:
                    # Skip some special object names (their orientation can be defined freely)
                    skip_keywords = ['lamp', 'light', 'pillar', 'column', 'pole', 'post',
                                     'cylinder', 'vase', 'plant', 'tree', 'toiletry',
                                     'nib', 'wall_', 'floor', 'ceiling', 'door', 'window',
                                     'curtain', 'rug', 'carpet', 'mat', 'runner']
                    if not any(kw in name.lower() for kw in skip_keywords):
                        warnings.append(
                            f"DIMENSIONS ERROR: '{name}' has X={dim_x} < Y={dim_y}. "
                            f"Should be ({dim_y}, {dim_x}, {dim_z}) - swap X and Y!"
                        )

        return warnings
    
    # ------------------------------------------------------------------
    # Composite-furniture adjacency check (L-shaped desks, sectional sofas)
    # ------------------------------------------------------------------
    # Composite "main / return" pairs we know about. The first token must be a
    # substring of one box's name (case-insensitive) and the second token must
    # be a substring of another box's name from the SAME prefix family. We
    # match by shared prefix so e.g. "Desk_Main"+"Desk_Return" pair up but
    # "Desk_Main"+"Small_Desk_Return" do not.
    _COMPOSITE_PAIR_TOKENS: Tuple[Tuple[str, str], ...] = (
        ("main", "return"),
        ("main", "chaise"),
        ("main", "lounger"),
        ("desk", "return"),
        ("sofa", "chaise"),
        ("sofa", "lounger"),
        ("sofa", "daybed"),
        ("counter", "return"),
        ("counter_main", "counter_return"),
    )

    # Tolerances for a "well-connected" composite pair.
    _COMPOSITE_GAP_OK_M = 0.05      # gap up to this is fine (touching)
    _COMPOSITE_GAP_WARN_M = 0.30    # gap above this is reported as broken

    @staticmethod
    def _aabb_after_yaw(loc: Tuple[float, float],
                        dim: Tuple[float, float],
                        yaw_rad: float) -> Tuple[float, float, float, float]:
        """Return (x_min, x_max, y_min, y_max) of an axis-aligned bbox in WORLD
        space for a box centered at `loc` with `dim` rotated by `yaw_rad` about
        Z. Conservative (uses corner extrema), correct for arbitrary yaw.
        """
        cx, cy = loc
        dx, dy = dim
        c, s = math.cos(yaw_rad), math.sin(yaw_rad)
        xs, ys = [], []
        for sx in (-dx / 2.0, dx / 2.0):
            for sy in (-dy / 2.0, dy / 2.0):
                xs.append(cx + sx * c - sy * s)
                ys.append(cy + sx * s + sy * c)
        return min(xs), max(xs), min(ys), max(ys)

    @staticmethod
    def _common_prefix_token(name_a: str, name_b: str) -> Optional[str]:
        """If `name_a` and `name_b` share a leading underscore-delimited
        token (case-insensitive), return it. Otherwise None."""
        ta = name_a.lower().split("_", 1)[0]
        tb = name_b.lower().split("_", 1)[0]
        if ta and ta == tb:
            return ta
        return None

    @staticmethod
    def _safe_eval_numeric(expr: str,
                           env: Optional[Dict[str, float]] = None) -> Optional[float]:
        """Evaluate a small numeric expression with `math.*` and a constant
        env. Returns None if the expression contains anything we cannot
        confidently evaluate. Used to resolve tuple-element expressions like
        ``-SCENE_W/2 + 0.35`` where SCENE_W comes from a top-level constant.
        """
        if expr is None:
            return None
        s = expr.strip()
        if not s:
            return None
        # Whitelist tokens: digits, dot, e, +, -, *, /, parens, math.*, names.
        if not re.fullmatch(r"[\w\s.\-+*/()]+", s):
            return None
        try:
            return float(eval(s, {"__builtins__": {}, "math": math}, env or {}))
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _collect_constants(code: str) -> Dict[str, float]:
        """Find top-level numeric constants like ``SCENE_W = 6.5``."""
        env: Dict[str, float] = {}
        pat = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*([-\d.eE+]+)\s*$",
                         re.MULTILINE)
        for m in pat.finditer(code):
            try:
                env[m.group(1)] = float(m.group(2))
            except ValueError:
                continue
        return env

    @staticmethod
    def _collect_tuple_vars(code: str,
                            env: Dict[str, float]
                            ) -> Dict[str, Tuple[float, float, float]]:
        """Find assignments like `desk_main_loc = (x, y, z)` and resolve them
        to numeric 3-tuples. Tuples with non-numeric elements are skipped.
        """
        out: Dict[str, Tuple[float, float, float]] = {}
        pat = re.compile(
            r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(\s*([^)]+?)\s*\)\s*$",
            re.MULTILINE,
        )
        for m in pat.finditer(code):
            name = m.group(1)
            inner = m.group(2)
            parts = [p.strip() for p in inner.split(",")]
            if len(parts) != 3:
                continue
            vals: List[float] = []
            for p in parts:
                v = CodeValidator._safe_eval_numeric(p, env)
                if v is None:
                    break
                vals.append(v)
            if len(vals) == 3:
                out[name] = (vals[0], vals[1], vals[2])
        return out

    def _parse_create_calls(self, code: str) -> List[Dict[str, object]]:
        """Extract a structured record per `create_box(...)` call.

        Returns a list of dicts:
            {name, loc:(x,y), dim:(dx,dy), yaw}
        Resolves both literal tuples AND variable references (since real
        Stage 3 output frequently uses `desk_main_loc` style helper vars).
        Calls we cannot fully resolve statically are skipped.
        """
        env = self._collect_constants(code)
        tup_vars = self._collect_tuple_vars(code, env)

        # Two-form regex: literal tuples OR identifier-as-tuple.
        # Group structure:
        #   1: name
        #   2: loc literal x   (or empty)
        #   3: loc literal y
        #   4: loc literal z
        #   5: loc identifier  (or empty)
        #   6: dim literal x   (or empty)
        #   7: dim literal y
        #   8: dim literal z
        #   9: dim identifier  (or empty)
        #   10: tail
        tuple_lit = r"\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)"
        ident = r"([A-Za-z_][A-Za-z0-9_]*)"
        pattern = re.compile(
            rf"""
            create_box\s*\(\s*
                ["']([^"']+)["']\s*,\s*                 # 1: name
                (?:{tuple_lit}|{ident})\s*,\s*          # 2-4: loc lit OR 5: loc id
                (?:{tuple_lit}|{ident})                 # 6-8: dim lit OR 9: dim id
                ([^)]*)                                 # 10: tail
            \)
            """,
            re.VERBOSE,
        )
        # Rotation may be `rotation=(rx, ry, math.radians(N))` or with floats.
        # We only want the Z component. Try math.radians(...) first, then float.
        rot_z_pat_rad = re.compile(
            r"rotation\s*=\s*\(\s*[^,]+,\s*[^,]+,\s*math\.radians\(\s*([-\d.eE+]+)\s*\)\s*\)"
        )
        rot_z_pat_pi = re.compile(
            r"rotation\s*=\s*\(\s*[^,]+,\s*[^,]+,\s*math\.pi\s*([*/]\s*[-\d.eE+]+)?\s*\)"
        )
        rot_z_pat_num = re.compile(
            r"rotation\s*=\s*\(\s*[^,]+,\s*[^,]+,\s*([-\d.eE+]+)\s*\)"
        )

        out: List[Dict[str, object]] = []
        for m in pattern.finditer(code):
            name = m.group(1)
            tail = m.group(10) or ""

            # Resolve loc — either literal (groups 2,3,4) or identifier (5).
            loc_lit_x, loc_lit_y, loc_lit_z = m.group(2), m.group(3), m.group(4)
            loc_ident = m.group(5)
            if loc_lit_x is not None:
                try:
                    lx, ly = float(loc_lit_x), float(loc_lit_y)
                except (TypeError, ValueError):
                    continue
            elif loc_ident is not None and loc_ident in tup_vars:
                lx, ly, _ = tup_vars[loc_ident]
            else:
                continue  # unresolvable loc → skip

            # Resolve dim — literal (6,7,8) or identifier (9).
            dim_lit_x, dim_lit_y, dim_lit_z = m.group(6), m.group(7), m.group(8)
            dim_ident = m.group(9)
            if dim_lit_x is not None:
                try:
                    dx, dy = float(dim_lit_x), float(dim_lit_y)
                except (TypeError, ValueError):
                    continue
            elif dim_ident is not None and dim_ident in tup_vars:
                dx, dy, _ = tup_vars[dim_ident]
            else:
                continue

            yaw = 0.0
            mr = rot_z_pat_rad.search(tail)
            if mr:
                try:
                    yaw = math.radians(float(mr.group(1)))
                except ValueError:
                    yaw = 0.0
            else:
                mp = rot_z_pat_pi.search(tail)
                if mp:
                    expr = mp.group(1)
                    yaw = math.pi
                    if expr:
                        op_num = expr.strip()
                        op = op_num[0]
                        try:
                            num = float(op_num[1:].strip())
                            yaw = math.pi * num if op == "*" else math.pi / num
                        except ValueError:
                            yaw = math.pi
                else:
                    mn = rot_z_pat_num.search(tail)
                    if mn:
                        try:
                            yaw = float(mn.group(1))
                        except ValueError:
                            yaw = 0.0
            out.append({
                "name": name,
                "loc": (lx, ly),
                "dim": (dx, dy),
                "yaw": yaw,
            })
        return out

    def check_composite_adjacency(self, code: str) -> List[str]:
        """Detect broken L-shaped / sectional composites.

        Heuristic: scan all box pairs for tokens like (main, return) /
        (sofa, chaise) sharing a common prefix family ("Desk_Main" +
        "Desk_Return"). For each match, check that the two boxes' AABBs
        meet within ``_COMPOSITE_GAP_OK_M``. If they sit further than
        ``_COMPOSITE_GAP_WARN_M`` apart in BOTH axes (i.e. they don't even
        share an extended edge), report the pair as broken.
        """
        boxes = self._parse_create_calls(code)
        if len(boxes) < 2:
            return []

        warnings: List[str] = []
        seen_pairs: set = set()
        for i, a in enumerate(boxes):
            na = str(a["name"]).lower()
            for b in boxes[i + 1:]:
                nb = str(b["name"]).lower()
                pair_key = tuple(sorted((a["name"], b["name"])))
                if pair_key in seen_pairs:
                    continue
                # Must share an underscore-prefix family.
                prefix = self._common_prefix_token(a["name"], b["name"])
                if prefix is None:
                    continue
                # One name must contain a "main/return" token from a known pair.
                matched = False
                for tok_a, tok_b in self._COMPOSITE_PAIR_TOKENS:
                    if (tok_a in na and tok_b in nb) or (tok_a in nb and tok_b in na):
                        matched = True
                        break
                if not matched:
                    continue
                seen_pairs.add(pair_key)

                # Compute world AABBs.
                ax_min, ax_max, ay_min, ay_max = self._aabb_after_yaw(
                    a["loc"], a["dim"], a["yaw"])  # type: ignore[arg-type]
                bx_min, bx_max, by_min, by_max = self._aabb_after_yaw(
                    b["loc"], b["dim"], b["yaw"])  # type: ignore[arg-type]
                gap_x = max(0.0, max(ax_min, bx_min) - min(ax_max, bx_max))
                gap_y = max(0.0, max(ay_min, by_min) - min(ay_max, by_max))

                # A well-connected L requires adjacency on BOTH axes — the
                # pieces should either overlap or touch in each direction.
                # If EITHER axis has a gap > warn threshold, the L is broken
                # (the two pieces stand far apart in the scene).
                worst_gap = max(gap_x, gap_y)
                if worst_gap > self._COMPOSITE_GAP_WARN_M:
                    warnings.append(
                        f"⚠️ COMPOSITE BROKEN: '{a['name']}' and '{b['name']}' "
                        f"share prefix '{prefix}' (likely an L-shape / sectional) "
                        f"but their footprints are separated by "
                        f"({gap_x:.2f}m in X, {gap_y:.2f}m in Y). They must "
                        f"meet edge-to-edge at a 90° corner. See "
                        f"'Composite / Multi-Piece Furniture' rules."
                    )

        return warnings

    def count_objects(self, code: str) -> int:
        """Count the number of created objects"""
        boxes = len(re.findall(r'create_box\(', code))
        cylinders = len(re.findall(r'create_cylinder\(', code))
        return boxes + cylinders

    def extract_object_names(self, code: str) -> List[str]:
        """Extract all object names"""
        names = []

        # Match create_box("name", ...) or create_cylinder("name", ...)
        pattern = r'create_(?:box|cylinder)\s*\(\s*["\']([^"\']+)["\']'
        matches = re.findall(pattern, code)
        
        return matches




