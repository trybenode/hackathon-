"""Future live-chat boundary; no runtime stub or simulated delivery."""
from typing import Protocol
from uuid import UUID


class LiveChatTransport(Protocol):
    """Reserved contract for a future independently authorized transport."""
    async def publish(self, thread_id: UUID, message_id: UUID) -> None: ...
