import json
import sqlite3

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
)

DB = "memory.db"

def serializeMessage(message):
    """
    Converts a LangChain message into the format used by the messages table.
    Returns:
        dict: {
            "role": str,
            "content": str
        }
    """

    # ---------------------------------------------------------
    # Human message
    # ---------------------------------------------------------
    if isinstance(message, HumanMessage):
        return {
            "role": "user",
            "content": message.content
        }
    # ---------------------------------------------------------
    # AI message
    # ---------------------------------------------------------
    if isinstance(message, AIMessage):
        tool_calls = getattr(message, "tool_calls", []) or []
        # Normal assistant response
        if not tool_calls:
            return {
                "role": "assistant",
                "content": message.content
            }
        # Assistant response containing tool calls
        return {
            "role": "assistant",
            "content": json.dumps(
                {
                    "content": message.content,
                    "tool_calls": tool_calls
                },
                ensure_ascii=False
            )
        }

    # ---------------------------------------------------------
    # Tool message
    # ---------------------------------------------------------
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "content": message.content
        }
    raise ValueError(
        f"Unsupported message type: {type(message).__name__}"
    )


def addMessage(
    user_id: int,
    message,
    episode_id: int | None = None
):
    """
    Saves a LangChain message into the messages table.
    Returns:
        int: ID of the inserted message.
    """
    serialized = serializeMessage(message)
    conn = sqlite3.connect(DB)
    cursor = conn.execute(
        """
        INSERT INTO messages
        (user_id, episode_id, role, content)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            episode_id,
            serialized["role"],
            serialized["content"]
        )
    )
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id
def getAllMessages():
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """
        SELECT id, user_id, episode_id, role, content
        FROM messages
        ORDER BY id
        """
    ).fetchall()
    conn.close()
    return rows
    

def clearMessages():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'messages';")
    conn.commit()
    conn.close()
# print(getAllMessages())