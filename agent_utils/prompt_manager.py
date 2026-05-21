"""Prompt manager - centralizes prompt files for all stages"""
import os
from typing import Dict, Optional


class PromptManager:
    """Centrally manages the Agent's prompt files"""

    def __init__(self, prompt_dir: Optional[str] = None):
        """
        Args:
            prompt_dir: Root directory of prompt files. Defaults to agent_prompt/.
        """
        if prompt_dir is None:
            # Default to the agent_prompt directory two levels above this file
            prompt_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "agent_prompt"
            )
        self.prompt_dir = prompt_dir
        self._cache: Dict[str, str] = {}

    def _load_file(self, filename: str) -> str:
        """Load a prompt file"""
        file_path = os.path.join(self.prompt_dir, filename)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file does not exist: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def get(self, prompt_name: str, use_cache: bool = True) -> str:
        """
        Get prompt content.

        Args:
            prompt_name: prompt filename (without path)
            use_cache: whether to use cache

        Returns:
            prompt content
        """
        if use_cache and prompt_name in self._cache:
            return self._cache[prompt_name]

        content = self._load_file(prompt_name)

        if use_cache:
            self._cache[prompt_name] = content

        return content

    def format(self, prompt_name: str, **kwargs) -> str:
        """
        Get a prompt and format it (supports {variable} placeholders).

        Args:
            prompt_name: prompt filename
            **kwargs: format arguments

        Returns:
            formatted prompt
        """
        template = self.get(prompt_name)
        return template.format(**kwargs)

    def clear_cache(self):
        """Clear cache"""
        self._cache.clear()

    def list_prompts(self) -> list:
        """List all available prompt files"""
        if not os.path.exists(self.prompt_dir):
            return []
        return [f for f in os.listdir(self.prompt_dir) if os.path.isfile(os.path.join(self.prompt_dir, f))]




