"""AnalyzeAgent - image-comparison analysis Agent"""
import json
from typing import Optional, Dict, Tuple, List

from core import BaseAgent, ImageMixin, extract_json_from_response
from langchain_core.messages import HumanMessage, SystemMessage


class AnalyzeAgent(BaseAgent, ImageMixin):
    """Analyze Agent - compares the original image with the rendered image and identifies differences"""

    @property
    def system_prompt_name(self) -> str:
        return "Stage3_analyze_system"

    @property
    def user_prompt_name(self) -> str:
        return "Stage3_analyze_user"

    def build_messages(
        self,
        original_image: str,
        rendered_image: str,
        code: str,
        stage2_json: Dict
    ):
        """Build messages - includes two images"""
        system = self.get_system_prompt()

        user_text = self.build_user_prompt(
            code=code[:4000] + "..." if len(code) > 4000 else code,
            stage2_json=json.dumps(stage2_json, ensure_ascii=False, indent=2)[:3000]
        )

        # Build user content with images
        user_content = [
            {"type": "text", "text": "Image 1 - Original (Target):"},
            self.build_image_content(original_image),
            {"type": "text", "text": "Image 2 - Rendered (Current):"},
            self.build_image_content(rendered_image),
            {"type": "text", "text": user_text}
        ]

        return [
            SystemMessage(content=system),
            HumanMessage(content=user_content)
        ]

    def run(
        self,
        original_image: str,
        rendered_image: str,
        code: str,
        stage2_json: Dict
    ) -> Tuple[bool, Dict]:
        """
        Analyze the differences between two images.

        Returns:
            (success, analysis_result)
        """
        self._log("Analyzing layout differences...")

        try:
            messages = self.build_messages(
                original_image, rendered_image, code, stage2_json
            )
            response = self.llm.invoke(messages)

            # Parse JSON
            json_str = extract_json_from_response(response)
            result = json.loads(json_str)

            # Extract key information
            score = result.get("overall_assessment", {}).get("layout_match_score", 0)
            corrections = result.get("object_corrections", [])
            critical = [c for c in corrections if c.get("severity") == "critical"]

            self._log(f"Match score: {score:.0%}", "success")
            if critical:
                self._log(f"Found {len(critical)} critical issues", "warning")

            return True, result

        except json.JSONDecodeError as e:
            self._log(f"Failed to parse analysis JSON: {e}", "error")
            return False, {"error": str(e)}
        except Exception as e:
            self._log(f"Analysis failed: {e}", "error")
            return False, {"error": str(e)}

    def get_corrections(self, analysis: Dict) -> List[Dict]:
        """Get correction list"""
        return analysis.get("object_corrections", [])

    def get_score(self, analysis: Dict) -> float:
        """Get match score"""
        return analysis.get("overall_assessment", {}).get("layout_match_score", 0)

    def has_critical_issues(self, analysis: Dict) -> bool:
        """Check whether there are critical issues"""
        corrections = self.get_corrections(analysis)
        return any(c.get("severity") == "critical" for c in corrections)


