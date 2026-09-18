import ollama
import sqlite3
import json
DB = "memory.db"

#TODO: Esta función es compartida, debería ponerla en algún lado específico
def getEmbedding(text: str):
    response = ollama.embed(
        model="qwen3-embedding:0.6b",
        input=text
    )
    return response["embeddings"][0]

def getLastEpisode(userId: int):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, created_at, updated_at, content, embedding
        FROM episodes
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (userId,))

    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "created_at": row[2],
        "updated_at": row[3],
        "content": row[4],
        "embedding": row[5]
    }

def getEpisode(): #TODO: Esta función parece bastante inútil
    currentEpisode = getLastEpisode(1)
    if currentEpisode is None:
        return None
    return currentEpisode

def checkEpisodeRelevance(episode: str, userMessage: str):
    prompt = f"""
    Determine whether the USER MESSAGE belongs to the CURRENT EPISODE.

    A message belongs to the episode ONLY when there is a specific
    subject, task, project, or ongoing work shared by both.

    Do NOT consider the message relevant merely because:
    - the same assistant can handle it
    - the same tools can be used
    - both involve computers or technology
    - the user is talking to the same assistant

    If the connection is weak, indirect, or only based on the assistant's
    general capabilities, return false.

    Examples:

    CURRENT EPISODE: Building a LangGraph-based AI agent.
    USER MESSAGE: "How are we implementing memory?"
    true

    CURRENT EPISODE: Building a LangGraph-based AI agent.
    USER MESSAGE: "Enciende la TV."
    false

    CURRENT EPISODE: Building a LangGraph-based AI agent.
    USER MESSAGE: "¿Qué clima hará mañana?"
    false

    CURRENT EPISODE: Building a robot with an ESP32 and MG90S servos.
    USER MESSAGE: "¿Qué servo estamos usando?"
    true

    CURRENT EPISODE: Building a robot with an ESP32 and MG90S servos.
    USER MESSAGE: "Enciende la TV."
    false

    Return ONLY:
    true
    or
    false

    CURRENT EPISODE:
    {episode}

    USER MESSAGE:
    {userMessage}
    """
    response = ollama.chat(
            model="qwen3.5:9b",
            messages=[
                {"role": "user", "content": prompt}
            ],
            think=False,
            options={
                "num_predict": 2048,
                "num_ctx": 16384
            }
        )
    llmResponse = response.message.content.strip().lower()

    if llmResponse == "true":
        print("\n\nEl episode es relevante\n\n")
        return True

    if llmResponse == "false":
        print("\n\nEl episode no es relevante\n\n")
        return False

    print(f"\n\nRespuesta inesperada del modelo: {llmResponse}\n\n")
    return False

def createEpisode(userId: int, content: str):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO episodes (user_id, content, embedding)
        VALUES (?, ?, ?)
    """, (userId, content, json.dumps(getEmbedding(content))))
    episodeId = cursor.lastrowid
    conn.commit()
    conn.close()
    return episodeId

def updateEpisode(episodeId: int, content: str):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE episodes
        SET content = ?,
            embedding = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        content,
        json.dumps(getEmbedding(content)),
        episodeId
    ))
    conn.commit()
    conn.close()

def mergeEpisode(currentEpisode: dict, messages: str):
    prompt = f"""
        Update the current episode using the new messages.
        Preserve all important information from the current episode that is still valid.
        Incorporate relevant information from the new messages.
        If the new messages contradict, correct, or supersede information in the current episode, update it accordingly.
        Do not remove information simply because it is not mentioned in the new messages.
        Do not invent information.
        The result should represent the accumulated state of the episode, not only the latest interaction.
        CURRENT EPISODE:
        {currentEpisode["content"] if currentEpisode else ""}
        NEW MESSAGES:
        {messages}
        Return only the updated episode.
        """

    response = ollama.chat(
        model="qwen3:1.7b",
        messages=[
            {"role": "user", "content": prompt}
        ],
        think=False,
        options={
            "num_predict": 2048,
            "num_ctx": 16384
        }
    )
    newContent = response.message.content.strip()
    if currentEpisode:
        print("\n\nGuardando un nuevo episode\n\n", newContent)
        updateEpisode(currentEpisode["id"], newContent)
    else:
        createEpisode(1, newContent)
# from message import getAllMessages [row for row in rows if row[3] != "tool"]
print(getEpisode()["content"])
print(checkEpisodeRelevance(getEpisode()["content"],"Hola, sabes mi nombre?"))
# saveEpisode(getEpisode(), getAllMessages())
# currentEpisode = """"""

# formatedMessages = [(message[3], message[4]) for message in messages]
# llmText = ""

# for message in formatedMessages:
#     llmText += f"{message[0].upper()}\n {message[1]}\n\n"
#     print("Message", message[0], message[1])
# print(llmText)


# checkEpisodeRelevance(getEpisode()["content"], "Hola, recuerdame en qué estamos trabajando")
# episodeModel = ChatOllama(
#     model="Gemma4:e2b",  # o tu 1.7B actual
#     temperature=0,
#     num_predict=-1,
#     num_ctx=32768
# ).bind_tools([updateEpisode])

# response = episodeModel.invoke(prompt.format(episode=currentEpisode, messages=llmText))

# print(response.tool_calls)

# response = ollama.chat(
#         model="qwen3.5:9b",
#         messages=[
#             {"role": "user", "content": prompt.format(current_episode=currentEpisode, messages=messages)}
#         ],
#         think=False,
#         options={
#             "num_predict": 16384,
#             "num_ctx": 16384
#         }
#     )

# print(response.message.content)
# print("done_reason:", response["done_reason"])
# print("eval_count:", response.get("eval_count"))
# print("content_length:", len(response["message"]["content"]))