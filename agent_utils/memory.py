"""Agent Memory system"""
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime


@dataclass
class MemoryEntry:
    """A single memory entry"""
    id: str
    stage: str  # "stage1", "stage2", "stage3", etc.
    type: str  # "result", "interaction", "validation", "fix"
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class Memory:
    """Agent Memory manager.

    Features:
    1. Stores results from multiple stages.
    2. Supports queries by stage / type / tags.
    3. Auto-persists to JSON Lines.
    4. Provides summary and statistics.
    """

    def __init__(self, workspace_dir: str = ".", memory_file: str = "agent_memory.jsonl"):
        self.workspace_dir = Path(workspace_dir)
        self.memory_file = self.workspace_dir / memory_file
        self.entries: List[MemoryEntry] = []
        self._load()

    def _load(self):
        """Load existing memory"""
        if self.memory_file.exists():
            with open(self.memory_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        self.entries.append(MemoryEntry.from_dict(data))

    def _save(self):
        """Persist memory"""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def add(self, stage: str, type: str, content: Any,
            metadata: Optional[Dict] = None, tags: Optional[List[str]] = None) -> MemoryEntry:
        """Add a memory entry"""
        entry = MemoryEntry(
            id=f"{stage}_{type}_{int(time.time() * 1000)}",
            stage=stage,
            type=type,
            content=content,
            metadata=metadata or {},
            tags=tags or []
        )
        self.entries.append(entry)
        self._save()
        return entry

    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get an entry by ID"""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def get_by_stage(self, stage: str, type: Optional[str] = None) -> List[MemoryEntry]:
        """Query by stage (optional type filter)"""
        results = [e for e in self.entries if e.stage == stage]
        if type:
            results = [e for e in results if e.type == type]
        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def get_latest(self, stage: str, type: str) -> Optional[MemoryEntry]:
        """Get the most recent entry"""
        results = self.get_by_stage(stage, type)
        return results[0] if results else None

    def search(self, query: str = None, stage: Optional[str] = None,
               type: Optional[str] = None, tags: Optional[List[str]] = None) -> List[MemoryEntry]:
        """Search memory"""
        results = self.entries

        if stage:
            results = [e for e in results if e.stage == stage]
        if type:
            results = [e for e in results if e.type == type]
        if tags:
            results = [e for e in results if any(tag in e.tags for tag in tags)]
        if query:
            query_lower = query.lower()
            results = [e for e in results if query_lower in json.dumps(e.content, ensure_ascii=False).lower()]

        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def get_stage_chain(self, stages: List[str]) -> Dict[str, Optional[MemoryEntry]]:
        """Get the most recent results across multiple stages (used for stage-to-stage handoff)"""
        return {stage: self.get_latest(stage, "result") for stage in stages}

    def get_stage_overview(self, stage: str) -> Optional[Dict[str, Any]]:
        """Get a stage overview (title + summary + metadata, no full content)"""
        latest = self.get_latest(stage, "result")
        if not latest:
            return None

        return {
            "id": latest.id,
            "stage": latest.stage,
            "timestamp": latest.timestamp,
            "title": latest.metadata.get("title", "Untitled"),
            "summary": latest.metadata.get("summary", "No summary"),
            "success": latest.metadata.get("success", False),
            "tags": latest.tags
        }

    def list_all_stages(self) -> Dict[str, Dict[str, Any]]:
        """List all completed stages and their overviews"""
        stages = {}
        for entry in self.entries:
            if entry.type == "result" and entry.stage not in stages:
                overview = self.get_stage_overview(entry.stage)
                if overview:
                    stages[entry.stage] = overview
        return dict(sorted(stages.items()))

    def summary(self) -> Dict[str, Any]:
        """Generate summary statistics"""
        by_stage = {}
        by_type = {}

        for entry in self.entries:
            by_stage[entry.stage] = by_stage.get(entry.stage, 0) + 1
            by_type[entry.type] = by_type.get(entry.type, 0) + 1

        return {
            "total_entries": len(self.entries),
            "by_stage": by_stage,
            "by_type": by_type,
            "oldest": datetime.fromtimestamp(self.entries[0].timestamp).isoformat() if self.entries else None,
            "latest": datetime.fromtimestamp(self.entries[-1].timestamp).isoformat() if self.entries else None
        }

    def clear(self, stage: Optional[str] = None):
        """Clear memory (optionally by stage)"""
        if stage:
            self.entries = [e for e in self.entries if e.stage != stage]
        else:
            self.entries = []
        self._save()

    def export_stage_result(self, stage: str, output_path: Optional[str] = None) -> Optional[Dict]:
        """Export a stage result as a standalone JSON file"""
        latest = self.get_latest(stage, "result")
        if not latest:
            return None

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(latest.content, f, ensure_ascii=False, indent=2)

        return latest.content

    def get_context_for_stage(self, current_stage: str, max_history: int = 3) -> Dict[str, Any]:
        """Build context for the current stage (previous stage results + recent history)"""
        context = {
            "current_stage": current_stage,
            "previous_stages": {},
            "recent_interactions": []
        }

        # Fetch previous stage results
        stage_num = int(current_stage.replace("stage", ""))
        for i in range(1, stage_num):
            prev_stage = f"stage{i}"
            latest = self.get_latest(prev_stage, "result")
            if latest:
                context["previous_stages"][prev_stage] = {
                    "id": latest.id,
                    "timestamp": latest.timestamp,
                    "summary": latest.metadata.get("summary", "N/A")
                }

        # Fetch recent interactions
        recent = [e for e in self.entries if e.type == "interaction"][-max_history:]
        context["recent_interactions"] = [
            {"stage": e.stage, "timestamp": e.timestamp, "content": e.content}
            for e in recent
        ]

        return context

    def get_stage_title(self, stage: str) -> Optional[str]:
        """Get the stage title (one-line title)"""
        latest = self.get_latest(stage, "result")
        if not latest:
            return None
        return latest.metadata.get("title", "Untitled")

    def get_stage_summary(self, stage: str) -> Optional[str]:
        """Get the stage summary (short text description)"""
        latest = self.get_latest(stage, "result")
        if not latest:
            return None
        return latest.metadata.get("summary", "No summary available")

    def get_stage_structured_data(self, stage: str) -> Optional[Dict]:
        """Get the stage's structured_data (detailed structured data)"""
        latest = self.get_latest(stage, "result")
        if not latest:
            return None
        return latest.metadata.get("structured_data")

    def query_by_semantic_tags(self, semantic_query: str, stage: Optional[str] = None) -> List[MemoryEntry]:
        """Query by semantic tags (e.g. "kitchen", "living_room", "sofa").

        Args:
            semantic_query: Semantic keyword (auto-matched against tags).
            stage: Optional stage filter.

        Returns:
            Matching memory entries.
        """
        query_normalized = semantic_query.lower().replace(" ", "_")
        results = self.entries

        if stage:
            results = [e for e in results if e.stage == stage]

        # Match tags (supports partial matching)
        matched = []
        for entry in results:
            for tag in entry.tags:
                if query_normalized in tag or tag in query_normalized:
                    matched.append(entry)
                    break

        return sorted(matched, key=lambda x: x.timestamp, reverse=True)


class MemoryAwareAgent:
    """Memory-aware Agent base class (Mixin)"""

    def __init__(self, *args, memory: Optional[Memory] = None, workspace_dir: str = ".", **kwargs):
        super().__init__(*args, **kwargs)
        self.memory = memory or Memory(workspace_dir=workspace_dir)

    def save_result(self, stage: str, result: Dict, metadata: Optional[Dict] = None):
        """Save a stage result to memory"""
        summary = self._generate_summary(result)
        full_metadata = metadata or {}
        full_metadata["summary"] = summary

        self.memory.add(
            stage=stage,
            type="result",
            content=result,
            metadata=full_metadata,
            tags=["success"]
        )

    def save_interaction(self, stage: str, interaction: Dict):
        """Save an interaction record"""
        self.memory.add(
            stage=stage,
            type="interaction",
            content=interaction,
            tags=["interaction"]
        )

    def load_previous_results(self, stages: List[str]) -> Dict[str, Optional[Dict]]:
        """Load previous stage results"""
        results = {}
        for stage in stages:
            entry = self.memory.get_latest(stage, "result")
            results[stage] = entry.content if entry else None
        return results

    def _generate_summary(self, result: Dict) -> str:
        """Generate a result summary (subclasses may override)"""
        if isinstance(result, dict):
            keys = list(result.keys())[:3]
            return f"Keys: {', '.join(keys)}"
        return str(result)[:100]

