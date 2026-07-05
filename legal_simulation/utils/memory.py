# legal_simulation/utils/memory.py
import math
from dataclasses import dataclass

@dataclass
class MemoryItem:
    content: str        # e.g., "Turn 5: I coughed blood. Health dropped to 45."
    turn_created: int
    date_created: str   # e.g., "[2025-02-15]" - Human-readable date
    importance: float   # 0.0 to 1.0 (High for health crises, low for mundane)

class AgentMemory:
    def __init__(self, decay_rate=0.1):
        self.memories = []
        self.decay_rate = decay_rate

    def add(self, content: str, turn: int, date_str: str, importance: float = 0.5, event_type: str = "general"):
        """
        Add a memory to the agent's memory store.

        Args:
            content: The memory content
            turn: The turn number when this memory was created
            date_str: Human-readable date string (e.g., "[2025-02-15]")
            importance: Importance score (0.0 to 1.0)
            event_type: Category of the event (e.g., "health_crisis", "legal", "financial")
        """
        # Format content with event type prefix
        formatted_content = f"[{event_type}]: {content}"
        self.memories.append(MemoryItem(formatted_content, turn, date_str, importance))

    def retrieve(self, current_turn: int, top_k: int = 5) -> str:
        """
        Returns top_k memories sorted by: importance * exp(-decay * time_gap)
        """
        scored_memories = []
        for mem in self.memories:
            time_gap = current_turn - mem.turn_created
            # Time decay formula
            score = mem.importance * math.exp(-self.decay_rate * time_gap)
            scored_memories.append((score, mem))

        # Sort descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # Format for Prompt - Use date_str instead of turn number for human readability
        result = [f"{m.date_created} (Turn {m.turn_created}) {m.content}" for _, m in scored_memories[:top_k]]
        return "\n".join(result)

    def retrieve_recent(self, k: int = 5) -> str:
        """
        Returns the most recent k memories regardless of importance (Sliding Window).
        Used to ensure agents focus on current events rather than past traumas.

        Args:
            k: Number of most recent memories to retrieve

        Returns:
            Formatted string with recent memories
        """
        # Get last k elements
        recent_memories = self.memories[-k:] if k > 0 else []

        # Format for Prompt - Use date_str for human readability
        result = [f"{m.date_created} (Turn {m.turn_created}) {m.content}" for m in recent_memories]

        if not result:
            return "No recent memories."

        return "\n".join(result)

