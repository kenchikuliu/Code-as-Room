"""Stage Clean Arrows - source-level cleanup of red direction arrows in the scene"""
import os
import re

from blender_code_syntax_fix import fix_empty_if_show_direction_before_return


class ArrowCleaner:
    """Source-level cleanup of direction arrows in Blender code (not runtime deletion, but direct removal from source)"""
    
    def __init__(self, output_dir: str = None, verbose: bool = True):
        self.output_dir = output_dir or "./output"
        self.verbose = verbose
        self._stats = {"default_flipped": 0, "explicit_removed": 0,
                       "arrow_func_removed": False, "arrow_calls_removed": 0}
    
    def _log(self, msg: str, level: str = "info"):
        if self.verbose:
            prefix = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "step": "📋"}.get(level, "")
            print(f"{prefix} {msg}")
    
    def clean_code(self, code: str) -> str:
        """
        Source-level arrow removal:
        1. Flip show_direction default to False in function defs
        2. Remove explicit show_direction=True from calls
        3. Remove create_direction_arrow function definition
        4. Remove calls to create_direction_arrow
        5. Remove ArrowRed material creation blocks
        """
        lines = code.split('\n')
        cleaned_lines = []
        skip_until_dedent = False
        func_indent = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # --- Step 3: Remove create_direction_arrow function definition ---
            if stripped.startswith('def create_direction_arrow('):
                self._stats["arrow_func_removed"] = True
                func_indent = len(line) - len(stripped)
                skip_until_dedent = True
                i += 1
                continue

            if skip_until_dedent:
                cur_indent = len(line) - len(line.lstrip())
                if stripped == '' or cur_indent > func_indent:
                    i += 1
                    continue
                else:
                    skip_until_dedent = False

            # --- Step 1: Flip default in function definitions ---
            if re.match(r'\s*def\s+(create_box|create_cylinder)\s*\(', line):
                full_sig = line
                while i + 1 < len(lines) and ')' not in full_sig.split('#')[0]:
                    i += 1
                    full_sig += '\n' + lines[i]
                before = full_sig
                full_sig = re.sub(r'show_direction\s*=\s*True', 'show_direction=False', full_sig)
                if full_sig != before:
                    self._stats["default_flipped"] += 1
                cleaned_lines.append(full_sig)
                i += 1
                continue

            # --- Step 4: Remove standalone calls to create_direction_arrow ---
            if 'create_direction_arrow(' in stripped:
                self._stats["arrow_calls_removed"] += 1
                i += 1
                continue

            # --- Step 2: Remove explicit show_direction=True from calls ---
            if 'show_direction=True' in line:
                line = re.sub(r',\s*show_direction\s*=\s*True', '', line)
                line = re.sub(r'show_direction\s*=\s*True\s*,\s*', '', line)
                self._stats["explicit_removed"] += 1

            # --- Step 5: Remove ArrowRed material blocks ---
            if re.match(r'\s*mat_arrow\s*=.*ArrowRed', stripped):
                i += 1
                continue

            cleaned_lines.append(line)
            i += 1

        result = '\n'.join(cleaned_lines)
        result = fix_empty_if_show_direction_before_return(result)
        self._log(
            f"Arrow cleanup stats: defaults_flipped={self._stats['default_flipped']}, "
            f"explicit_true_removed={self._stats['explicit_removed']}, "
            f"arrow_func_removed={self._stats['arrow_func_removed']}, "
            f"arrow_calls_removed={self._stats['arrow_calls_removed']}",
            "info"
        )
        return result
    
    def clean_file(self, input_path: str, output_path: str = None) -> str:
        """Clean arrows from a file"""
        if not os.path.exists(input_path):
            self._log(f"File does not exist: {input_path}", "error")
            return None

        with open(input_path, 'r', encoding='utf-8') as f:
            code = f.read()

        cleaned_code = self.clean_code(code)

        # Save
        if output_path is None:
            output_path = input_path.replace('.py', '_clean.py')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)

        self._log(f"Arrows cleaned, saved to: {output_path}", "success")
        return cleaned_code

    def run(self, stage4_code: str = None, stage4_path: str = None) -> tuple:
        """
        Run cleanup.

        Args:
            stage4_code: Code string output by Stage4.
            stage4_path: Stage4 output file path.

        Returns:
            (success, cleaned_code)
        """
        self._log("Source-level cleanup of direction arrows...", "step")

        if stage4_code:
            code = stage4_code
        elif stage4_path and os.path.exists(stage4_path):
            with open(stage4_path, 'r', encoding='utf-8') as f:
                code = f.read()
        else:
            default_path = os.path.join(self.output_dir, "stage4_output.py")
            if os.path.exists(default_path):
                with open(default_path, 'r', encoding='utf-8') as f:
                    code = f.read()
            else:
                self._log("Stage4 output file not found", "error")
                return False, None

        cleaned_code = self.clean_code(code)

        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, "stage4_clean.py")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)

        self._log(f"Saved cleaned code to: {output_path}", "success")

        return True, cleaned_code


class StageCleanArrowsRunner:
    """Stage Clean Arrows Runner - for pipeline integration"""

    def __init__(self, workspace_dir: str = None, verbose: bool = True):
        self.workspace_dir = workspace_dir or "."
        self.verbose = verbose
        self.cleaner = ArrowCleaner(
            output_dir=os.path.join(workspace_dir, "pipeline_output") if workspace_dir else "./output",
            verbose=verbose
        )

    def run(self) -> tuple:
        """Run cleanup"""
        # Default to reading from stage4 output
        stage4_path = os.path.join(
            self.workspace_dir,
            "pipeline_output",
            "stage4",
            "stage4_output.py"
        )

        return self.cleaner.run(stage4_path=stage4_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean direction arrows from Blender code")
    parser.add_argument("--input", "-i", required=True, help="Input file path")
    parser.add_argument("--output", "-o", help="Output file path")
    
    args = parser.parse_args()
    
    cleaner = ArrowCleaner()
    cleaner.clean_file(args.input, args.output)
