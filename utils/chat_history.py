"""Chat history utilities."""
from typing import Dict, List


class ChatHistory:
    """Manages chat history for sessions."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[Dict] = []
    
    def add_message(self, role: str, content: str):
        """Add a message to the chat history."""
        self.messages.append({
            "role": role,
            "content": content
        })
    
    def get_messages(self) -> List[Dict]:
        """Get all messages in the chat history."""
        return self.messages
    
    def clear(self):
        """Clear the chat history."""
        self.messages = []
