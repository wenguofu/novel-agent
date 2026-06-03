"""Fixture for repository signature scanner tests."""
from typing import Optional, List, Dict


class Repository:
    def get_novel(self, novel_name: str) -> Optional[Dict]:
        """Look up a novel by name."""
        return None

    def list_chapters(self, novel_name: str, volume: Optional[str] = None) -> List[Dict]:
        """List all chapters, optionally filtered by volume."""
        return []

    def upsert_outline(self, novel_name: str, volume: str, content: str, word_count: int = 0) -> Dict:
        """Create or update a volume outline."""
        return {}
