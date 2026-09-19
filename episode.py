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
    You are an episode membership classifier for an AI agent.

    Your task is to determine whether the USER MESSAGE is a continuation
    of the specific work or subject represented by the CURRENT EPISODE.

    Return ONLY:
    true
    or
    false

    A message is relevant (true) ONLY when the user is explicitly
    continuing, modifying, asking about, or resuming the specific work
    or subject of the episode.

    A message is irrelevant (false) when it is an independent request,
    even if it could be useful to the project, could be performed by the
    same assistant, or uses one of the assistant's tools.

    IMPORTANT:
    Do NOT infer a connection that the user did not express.
    Do NOT assume that information is related to the episode merely
    because it could potentially be useful for the project.

    For example:

    CURRENT EPISODE:
    The user is developing a local AI agent using LangGraph and Python.

    USER MESSAGE:
    "Busca en Google información sobre Python"

    OUTPUT:
    false

    The message asks for general information about Python. The user did
    not connect the request to the AI agent.

    CURRENT EPISODE:
    The user is developing a local AI agent using LangGraph and Python.

    USER MESSAGE:
    "Busca en Google información sobre Python para mejorar nuestro agente"

    OUTPUT:
    true

    The user explicitly connects the request to the agent project.

    CURRENT EPISODE:
    The user is developing a local AI agent using LangGraph.

    USER MESSAGE:
    "Enciende la TV"

    OUTPUT:
    false

    Using a capability of the assistant is not a continuation of the
    episode.

    CURRENT EPISODE:
    The user is developing a local AI agent using LangGraph.

    USER MESSAGE:
    "Quiero agregar una herramienta para controlar la TV al agente"

    OUTPUT:
    true

    The user is explicitly modifying the agent project.

    CURRENT EPISODE:
    The user is developing a local AI agent using LangGraph.

    USER MESSAGE:
    "Cuál es el framework que estamos usando?"

    OUTPUT:
    true

    The user is asking about the specific project described in the episode.

    CURRENT EPISODE:
    The user is developing a local AI agent using LangGraph.

    USER MESSAGE:
    "Qué clima hará mañana?"

    OUTPUT:
    false

    The request is independent of the project.

    CLASSIFICATION RULE:

    Ask:
    "Is the user actually continuing the specific work or subject of
    this episode?"

    Do NOT ask:
    "Could this request somehow be related to, useful for, or performed
    by the project?"

    If the connection requires inventing or assuming a purpose that is
    not present in the USER MESSAGE, return false.

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
        An episode summarizes the relevant information, decisions, and context accumulated throughout the interactions in the episode.
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

questions = [
    # Claramente irrelevantes
    "Hola, sabes mi nombre?",
    "Buenos días",
    "Qué hora es?",
    "Qué clima hará mañana?",
    "Enciende la TV",
    "Apaga la televisión",
    "Pon Netflix",
    "Revisa mis correos de hoy y resumelos",
    "Busca en Google información sobre Python",
    "Revisa el archivo pruebaWhisper.py",

    # Claramente relevantes
    "Cuál es el framework del agente?",
    "Deberíamos continuar creando un archivo Memories.py",
    "Qué modelo estamos usando actualmente para el agente?",
    "Cómo estamos almacenando las memorias?",
    "Qué base de datos estamos utilizando?",
    "Qué herramientas tiene actualmente el agente?",
    "Cómo funciona el flujo de LangGraph?",
    "Quiero modificar el sistema de memoria del agente",
    "Deberíamos mejorar el reranker de memorias",
    "Cómo estamos generando los embeddings de las memorias?",

    # Casos frontera
    "Establece un recordatorio para las 11:00AM que diga 'Alimentar a los gatos'",
    "Crea una tarea para alimentar a los gatos",
    "Quiero agregar una herramienta de recordatorios al agente",
    "Quiero agregar una herramienta para controlar la TV al agente",
    "Cómo podríamos hacer que el agente controle la TV?",
    "Qué modelo pequeño podríamos usar para el agente?",
    "Busca información sobre modelos pequeños para agentes de IA",
    "Quiero instalar otro modelo de Ollama",
    "Podemos mejorar la velocidad del agente?",
    "Quiero hacer que el agente sea capaz de usar más herramientas",
]
# for question in questions:
#     print("Pregunta: ", question)
#     print(checkEpisodeRelevance(getEpisode()["content"],question))
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