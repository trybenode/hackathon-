"""Development/test-only live transport; never wired into application services."""
from uuid import UUID


class RecordingLiveChat:
    def __init__(self) -> None:
        self.messages: list[tuple[UUID, UUID]] = []

    async def publish(self, thread_id: UUID, message_id: UUID) -> None:
        self.messages.append((thread_id, message_id))
