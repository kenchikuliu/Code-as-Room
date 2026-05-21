"""FixAgent - code-fix Agent"""
import json
from typing import Optional, Dict, Tuple

from core import BaseAgent, extract_python_from_response
from langchain_core.messages import HumanMessage, SystemMessage


class FixAgent(BaseAgent):
    """Fix Agent - fixes code based on analysis results"""

    @property
    def system_prompt_name(self) -> str:
        return "Stage3_fix_system"

    @property
    def user_prompt_name(self) -> str:
        return "Stage3_fix_user"

    def build_messages(
        self,
        code: str,
        analysis: Dict,
        errors: str = ""
    ):
        """Build messages"""
        system = self.get_system_prompt()
        user_text = self.build_user_prompt(
            code=code,
            analysis=json.dumps(analysis, ensure_ascii=False, indent=2),
            errors=errors or "None"
        )

        return [
            SystemMessage(content=system),
            HumanMessage(content=user_text)
        ]

    def run(
        self,
        code: str,
        analysis: Dict,
        errors: str = "",
        max_retries: int = 2
    ) -> Tuple[bool, str]:
        """
        Fix code.

        Returns:
            (success, fixed_code)
        """
        self._log("Fixing code based on analysis...")

        for attempt in range(max_retries):
            try:
                messages = self.build_messages(code, analysis, errors)
                response = self.llm.invoke(messages)

                # Extract code
                fixed_code = extract_python_from_response(response)

                if not fixed_code:
                    self._log(f"Attempt {attempt + 1}: No code extracted", "warning")
                    continue

                # Validate syntax
                try:
                    compile(fixed_code, '<string>', 'exec')
                except SyntaxError as e:
                    self._log(f"Attempt {attempt + 1}: Syntax error - {e}", "warning")
                    # Pass error info into the next attempt
                    errors = f"Previous fix had syntax error: {e}"
                    continue

                # Check whether anything actually changed
                if fixed_code == code:
                    self._log("No changes made to code", "warning")
                    return True, code

                self._log(f"Code fixed ({len(fixed_code)} chars)", "success")
                return True, fixed_code

            except Exception as e:
                self._log(f"Attempt {attempt + 1}: Error - {e}", "error")

        # Fix failed; return original code
        self._log("Fix failed, returning original code", "warning")
        return False, code

