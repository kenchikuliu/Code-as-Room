"""CodePatcher - code-patching utility"""
import re
from typing import Dict, List, Tuple, Optional


class CodePatcher:
    """Code-patching utility - rule-based code modification"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def _log(self, msg: str, level: str = "info"):
        if self.verbose:
            prefix = {"info": "[i]", "success": "[OK]", "warning": "[!]", "error": "[X]"}.get(level, "")
            print(f"  {prefix} {msg}")

    def apply_corrections(self, code: str, corrections: List[Dict]) -> Tuple[str, int]:
        """
        Apply a list of corrections.

        Returns:
            (patched_code, applied_count)
        """
        lines = code.split('\n')
        applied = 0

        for correction in corrections:
            obj_id = correction.get("object_id", "")
            obj_label = correction.get("object_label", "")
            corr = correction.get("correction", {})
            action = corr.get("action")

            search_names = [n for n in [obj_id, obj_label] if n]

            if action in ["relocate", "move"]:
                success = self._apply_relocate(lines, search_names, corr)
                if success:
                    applied += 1

            elif action == "rotate":
                success = self._apply_rotate(lines, search_names, corr)
                if success:
                    applied += 1

            elif action == "delete":
                success = self._apply_delete(lines, search_names)
                if success:
                    applied += 1

        patched_code = '\n'.join(lines)
        return patched_code, applied

    def _apply_relocate(self, lines: List[str], names: List[str], corr: Dict) -> bool:
        """Apply a position correction"""
        new_x = corr.get("new_x")
        new_y = corr.get("new_y")
        new_z = corr.get("new_z")

        if new_x is None or new_y is None:
            return False

        for name in names:
            for i, line in enumerate(lines):
                if self._line_matches_object(line, name):
                    # Find the location argument
                    loc_match = re.search(
                        r'\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)',
                        line
                    )
                    if loc_match:
                        old_z = float(loc_match.group(3))
                        nz = new_z if new_z is not None else old_z

                        old_loc = loc_match.group(0)
                        new_loc = f"({new_x:.2f}, {new_y:.2f}, {nz:.2f})"

                        lines[i] = line.replace(old_loc, new_loc, 1)
                        self._log(f"Relocated {name}: {old_loc} -> {new_loc}", "success")
                        return True

        self._log(f"Could not find object: {names}", "warning")
        return False

    def _apply_rotate(self, lines: List[str], names: List[str], corr: Dict) -> bool:
        """Apply a rotation correction"""
        new_rot = corr.get("new_rotation", 0)

        for name in names:
            for i, line in enumerate(lines):
                if self._line_matches_object(line, name):
                    if 'rotation=' in line:
                        # Modify existing rotation
                        rot_match = re.search(r'rotation\s*=\s*\([^)]+\)', line)
                        if rot_match:
                            new_rot_str = f"rotation=(0, 0, {new_rot})"
                            lines[i] = line[:rot_match.start()] + new_rot_str + line[rot_match.end():]
                            self._log(f"Rotated {name}: {new_rot} deg", "success")
                            return True
                    else:
                        # Insert before the last ')'
                        last_paren = line.rfind(')')
                        if last_paren > 0:
                            lines[i] = line[:last_paren] + f", rotation=(0, 0, {new_rot})" + line[last_paren:]
                            self._log(f"Added rotation to {name}: {new_rot} deg", "success")
                            return True

        return False

    def _apply_delete(self, lines: List[str], names: List[str]) -> bool:
        """Apply a delete correction"""
        for name in names:
            for i, line in enumerate(lines):
                if self._line_matches_object(line, name):
                    lines[i] = f"    # DELETED: {line.strip()}"
                    self._log(f"Deleted {name}", "success")
                    return True
        return False

    def _line_matches_object(self, line: str, name: str) -> bool:
        """Check whether a line matches an object"""
        if f'"{name}"' not in line and f"'{name}'" not in line:
            return False
        return 'create_box' in line or 'create_cylinder' in line

    def fix_parentheses(self, code: str) -> str:
        """Fix parenthesis-mismatch issues"""
        lines = code.split('\n')
        fixed_lines = []

        for line in lines:
            if line.strip().startswith('#'):
                fixed_lines.append(line)
                continue

            open_count = line.count('(')
            close_count = line.count(')')

            if open_count > close_count:
                line = line.rstrip() + ')' * (open_count - close_count)
            elif close_count > open_count:
                diff = close_count - open_count
                temp = line.rstrip()
                while diff > 0 and temp.endswith(')'):
                    temp = temp[:-1]
                    diff -= 1
                line = temp

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)

    def ensure_materials(self, code: str) -> str:
        """Make sure every object has a material"""
        lines = code.split('\n')

        for i, line in enumerate(lines):
            if ('create_box' in line or 'create_cylinder' in line) and 'material=' not in line:
                # Try to add a default material
                if 'collection=' in line:
                    # Add material before collection=
                    lines[i] = line.replace('collection=', 'material=mat_wood, collection=')
                else:
                    # Insert before the last ')'
                    last_paren = line.rfind(')')
                    if last_paren > 0:
                        lines[i] = line[:last_paren] + ', material=mat_wood' + line[last_paren:]

                self._log(f"Added material to line {i + 1}", "info")

        return '\n'.join(lines)




