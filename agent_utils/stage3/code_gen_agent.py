"""CodeGenAgent - code-generation Agent"""
import json
from typing import Optional, Dict, Tuple

from core import BaseAgent, ImageMixin, extract_python_from_response
from langchain_core.messages import HumanMessage, SystemMessage


class CodeGenAgent(BaseAgent, ImageMixin):
    """Code-generation Agent - generates Blender code from Stage1/2 data"""

    @property
    def system_prompt_name(self) -> str:
        return "Stage3_generate_system"

    @property
    def user_prompt_name(self) -> str:
        return "Stage3_generate_user"

    def build_messages(
        self,
        stage1_json: Dict,
        stage2_json: Dict,
        image_path: Optional[str] = None
    ):
        """Build messages - supports images"""
        system = self.get_system_prompt()
        user_text = self.build_user_prompt(
            stage1_json=json.dumps(stage1_json, ensure_ascii=False, indent=2),
            stage2_json=json.dumps(stage2_json, ensure_ascii=False, indent=2)
        )

        # Build user content
        user_content = []

        if image_path:
            user_content.append({"type": "text", "text": "Reference image:"})
            user_content.append(self.build_image_content(image_path))

        user_content.append({"type": "text", "text": user_text})

        return [
            SystemMessage(content=system),
            HumanMessage(content=user_content if image_path else user_text)
        ]

    def run(
        self,
        stage1_json: Dict,
        stage2_json: Dict,
        image_path: Optional[str] = None,
        max_retries: int = 3
    ) -> Tuple[bool, str, Dict]:
        """
        Generate Blender code.

        Returns:
            (success, code, metadata)
        """
        self._log("Generating Blender code...")

        for attempt in range(max_retries):
            try:
                messages = self.build_messages(stage1_json, stage2_json, image_path)
                response = self.llm.invoke(messages)

                # Extract code
                code = extract_python_from_response(response)

                if not code:
                    self._log(f"Attempt {attempt + 1}: No code extracted", "warning")
                    continue

                # Basic validation
                try:
                    compile(code, '<string>', 'exec')
                except SyntaxError as e:
                    self._log(f"Attempt {attempt + 1}: Syntax error - {e}", "warning")
                    continue

                # Success
                self._log(f"Code generated ({len(code)} chars)", "success")

                metadata = {
                    "lines": code.count('\n') + 1,
                    "chars": len(code),
                    "attempt": attempt + 1
                }

                return True, code, metadata

            except Exception as e:
                self._log(f"Attempt {attempt + 1}: Error - {e}", "error")

        return False, "", {"error": "Max retries exceeded"}

