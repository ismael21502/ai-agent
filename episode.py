import ollama
import sqlite3
import json

from pydantic import BaseModel
DB = "memory.db"
class Path(BaseModel):
    path: str
    explanation: str
class Episode(BaseModel):
    topic: str
    summary: str
    relevant_paths: list[Path]
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
            model="Gemma4:e2b",
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
        # print("\n\nEl episode es relevante\n\n")
        return True

    if llmResponse == "false":
        # print("\n\nEl episode no es relevante\n\n")
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
    #Tal vez sirve poner user_message, agent_response, important paths NO FUNCIONÓ
    #TOPIC, USER REQUEST, AGENT RESPONSE, IMPORTANT FILES, SUMMARY?
#     - tool_results: successful tool results from the current interaction. These may
#   contain information that is relevant to understanding the current state of
#   the work.
    systemPrompt = """
        You are an episode state manager for an AI assistant.

Your task is to create the new episode representing the CURRENT STATE OF THE WORK.

The episode is not a conversation summary, chronological log, or changelog.
It is a compact representation of the information that should be preserved
to continue the work in a future interaction.

You will receive:

- current_episode: the previous episode, if one exists.
- user_request: the user's request from the current interaction.
- agent_response: the agent's final response from the current interaction.
- observed_paths: paths that were explicitly involved in successful tool operations
  during the current interaction.

Your task is to generate a new Episode with exactly these fields:

{
    "topic": "...",
    "summary": "...",
    "relevant_paths": [
        {
            "path": "...",
            "explanation": "..."
        }
    ]
}

Rules:

1. TOPIC

The topic represents the relatively stable subject or activity being worked on.

It should answer:
"What are we working on?"

Prefer the broader ongoing subject over the specific action of the current
interaction.

For example:
- "AI Personal Assistant" is a good topic.
- "Update README" is usually too specific.

Keep the topic concise.

2. SUMMARY

The summary must describe the STATE OF THE WORK, not the content of the
documents or information discovered during the interaction.

Do not summarize files, articles, code, or tool results unless their content
directly represents an important change to the current state of the work.

Ask yourself:

"What would another assistant need to know to continue this work in the
next interaction?"

The answer to that question is the summary.

Prefer describing:
- what is currently being worked on
- what has been accomplished
- what has been decided
- what remains relevant
- important results that affect future work

Do not describe:
- the general contents of a file
- every tool operation
- information that was merely inspected
- project details that are not relevant to continuing the current work

3. RELEVANT PATHS

Select the paths that are relevant to the CURRENT STATE OF THE WORK.

Use observed_paths as the candidates.

Do not invent paths.

Do not extract additional paths from tool results unless they are already
present in observed_paths.

Do not assume that every observed path is relevant.

A path is relevant when it is likely to be useful in a future interaction
about the current work.

For every selected path, preserve the exact "path" from observed_paths and
provide a concise explanation of why it is relevant.

Paths already present in current_episode may remain relevant even if they were
not observed during the current interaction.

When preserving an existing relevant path, keep its existing path and
explanation unless the current interaction provides a reason to update them.

4. LAST INTERACTION

Do not generate a last_interaction field.

The application will inject the current user_request and agent_response into
the episode after generation.

5. INFORMATION PRIORITY

When information conflicts, prefer the most recent valid information from the
current interaction over older information from current_episode.

Tool results are evidence that may help understand the current state, but they
should not be copied into the episode unless their information is important for
the current state.

6. OUTPUT

Return ONLY a valid JSON object matching the Episode schema.

Do not include markdown.
Do not include explanations outside the JSON object.
        """
    formatedMessages = messages
    paths = set()
    for message in formatedMessages:
        if message["role"] != "tool":
            continue
        data = json.loads(message["content"])
        if data.get("success") and data.get("path"):
            paths.add(data["path"])
    dataForNewEpisode = {
        "current_episode": {},
        "user_request": formatedMessages[0]["content"],
        "agent_response": formatedMessages[-1]["content"],
        "observed_paths": list(paths),
        # "tool_results": ""
    }
    # print(dataForNewEpisode)
    response = ollama.chat("Gemma4:e2b", messages=[
                    {"role": "system", "content": systemPrompt},
                    {"role": "user", "content": json.dumps(
                        dataForNewEpisode,
                        ensure_ascii=False
                    )}
                ],
                format=Episode.model_json_schema(),
                options={
                    "temperature": 0
                },
                think=False)
    result = Episode.model_validate_json(
        response.message.content
    )

    # messagesText = ""
    # # for message in result.messages_summary:
    # #     messagesText += f"{message.role.capitalize()}\n{message.content}\n"
    # # return 
    # newContent = f"\nTOPIC: {result.topic}\nSUMMARY: {result.summary}\nPATHS: \n{result.relevant_paths}\nUSER REQUEST: \nAGENT RESPONSE: \n"
    newContent = result.model_dump()
    newContent["last_interaction"] = {
        "user_request": formatedMessages[0]["content"],
        "agent_response": formatedMessages[-1]["content"]
    }

    #Para pruebas. Quitar en producción.
    if __name__ == "__main__":
        print("EPISODIO ACTUALIZADO: ", newContent)
        json.dumps(newContent)
        return
    if currentEpisode:
        print("\n\nGuardando un nuevo episode\n\n", newContent)
        updateEpisode(currentEpisode["id"], json.dumps(newContent))
    else:
        createEpisode(1, json.dumps(newContent))
# from message import getAllMessages [row for row in rows if row[3] != "tool"]
def getSuccessfulToolResults(messages):
    toolMessages = []
    for message in messages:
        if message["role"] != "tool":
            continue
        try:
            data = json.loads(message["content"])
        except (TypeError, json.JSONDecodeError):
            continue
        if data.get("success"):
            toolMessages.append(data)
    return toolMessages
if __name__ == "__main__":
    option = input("""1. Ver el episode actual
2. Probar `checkEpisodeRelevance()`
3. Probar `mergeEpisode()` (Recuerda desactivar updateEpisode y createEpisode)
Elige una opción: """)
    import time
    start = time.perf_counter()
    if option == "1":
        episode = getEpisode()
        print("="*20, "\n\tDATA")
        print("="*20, f"\nUSER ID: {episode["user_id"]}\nCREATED AT: {episode["created_at"]}\nUPDATED AT: {episode["updated_at"]}")
        print("="*23, "\n\tCONTENT")
        print("="*23, f"\n{episode["content"]}")
    elif option == "2":
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
        "Puedes explicarme eso?",

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
        for question in questions:
            print("Pregunta: ", question)
            print(checkEpisodeRelevance(getEpisode()["content"],question))
    elif option == "3":
        messages = [(152, 1, None, 'user', 'Revisa main.py y actualiza el README'), (153, 1, None, 'assistant', '{"content": "", "tool_calls": [{"name": "listFiles", "args": {"path": "."}, "id": "72737407-f8f7-45a1-a059-d553cda9bb60", "type": "tool_call"}]}'), (154, 1, None, 'tool', '{"success": true, "path": ".", "result": [{"name": ".git", "path": "E:/Proyectos/Automation/AI Agent/.git", "type": "directory"},{"name": ".gitignore", "path": "E:/Proyectos/Automation/AI Agent/.gitignore", "type": "file"}, {"name": "BuiltInTools", "path": "E:/Proyectos/Automation/AI Agent/BuiltInTools", "type": "directory"}, {"name": "credentials.json", "path": "E:/Proyectos/Automation/AI Agent/credentials.json", "type": "file"}, {"name": "docs", "path": "E:/Proyectos/Automation/AI Agent/docs", "type": "directory"}, {"name": "env", "path": "E:/Proyectos/Automation/AI Agent/env", "type": "directory"}, {"name": "episode.py", "path": "E:/Proyectos/Automation/AI Agent/episode.py", "type": "file"}, {"name": "Features.md", "path": "E:/Proyectos/Automation/AI Agent/Features.md", "type": "file"}, {"name": "main.py", "path": "E:/Proyectos/Automation/AI Agent/main.py", "type": "file"}, {"name": "memory.db", "path": "E:/Proyectos/Automation/AI Agent/memory.db", "type": "file"}, {"name": "message.py", "path": "E:/Proyectos/Automation/AI Agent/message.py", "type": "file"}, {"name": "MiniRoadmap.md", "path": "E:/Proyectos/Automation/AI Agent/MiniRoadmap.md", "type": "file"}, {"name": "models", "path": "E:/Proyectos/Automation/AI Agent/models", "type": "directory"}, {"name": "pruebaollama.py", "path": "E:/Proyectos/Automation/AI Agent/pruebaollama.py", "type": "file"}, {"name": "README.md", "path": "E:/Proyectos/Automation/AI Agent/README.md", "type": "file"}, {"name": "schedule.json", "path": "E:/Proyectos/Automation/AI Agent/schedule.json", "type": "file"}, {"name": "secrets.md", "path": "E:/Proyectos/Automation/AI Agent/secrets.md", "type": "file"}, {"name": "smolagents-obsolete.py", "path": "E:/Proyectos/Automation/AI Agent/smolagents-obsolete.py", "type": "file"}, {"name": "tests", "path": "E:/Proyectos/Automation/AI Agent/tests", "type": "directory"}, {"name": "token.json", "path": "E:/Proyectos/Automation/AI Agent/token.json", "type": "file"}, {"name": "__pycache__", "path": "E:/Proyectos/Automation/AI Agent/__pycache__", "type": "directory"}], "count": 21}'), (155, 1, None, 'assistant', '{"content": "", "tool_calls": [{"name": "readFile", "args": {"path": "E:/Proyectos/Automation/AI Agent/main.py"}, "id": "25d0afdd-78de-40ec-9d4e-5c4c6ff591e1", "type":"tool_call"}, {"name": "readFile", "args": {"path": "E:/Proyectos/Automation/AI Agent/README.md"}, "id": "83890258-5578-49aa-b7df-e5e2000e45be", "type": "tool_call"}]}'), (156, 1, None, 'tool', '{"success": true, "path": "E:/Proyectos/Automation/AI Agent/main.py", "result": "from typing import Annotated\\nfrom typing_extensions import TypedDict\\n\\nfrom langchain_core.messages import AnyMessage, ToolMessage\\nfrom langgraph.graph import StateGraph, START, END\\nfrom langgraph.graph.message import add_messages\\nfrom langgraph.prebuilt import ToolNode\\n\\nfrom langchain_openai import ChatOpenAI\\nfrom langchain_ollama import ChatOllama\\nfrom langchain_core.tools import tool\\nfrom langchain_core.messages import SystemMessage\\nfrom BuiltInTools.tvController import tvController\\nfrom BuiltInTools.modelSelector import delegateToAI\\nfrom BuiltInTools.Files.fileManager import listFiles, readFile, findFiles, overwriteFile, createDirectory, moveFile\\nfrom BuiltInTools.System.timeFunctions import getCurrentTime, getCurrentTimeTool, getCurrentTimezone, addTime, substractTime, timeDiff\\nfrom BuiltInTools.System.memory import addMemory, searchMemory, extractMemories\\nfrom episode import getEpisode, checkEpisodeRelevance, mergeEpisode\\nfrom BuiltInTools.Google.gmail import getEmails, deleteEmail, readEmail\\nfrom BuiltInTools.System.weather import getCurrentWeather, getWeatherBetween, getWeatherAt\\nfrom message import addMessage, serializeMessage\\nfrom dotenv import load_dotenv\\nimport time \\n\\nfrom langchain_community.tools import DuckDuckGoSearchRun\\n\\nload_dotenv()\\n\\n#TODO: Buscar un lugar mejor para esto: \\nimport requests\\ndef getLocation():\\n    try:\\n        response = requests.get(\\n            \\"https://ipwho.is/\\",\\n            timeout=3\\n        )\\n        response.raise_for_status()\\n        data = response.json()\\n        return {\\n            \\"city\\": data.get(\\"city\\"),\\n            \\"state\\": data.get(\\"region\\"),\\n            \\"country\\": data.get(\\"country\\"),\\n            # \\"latitude\\": data.get(\\"latitude\\"),\\n            # \\"longitude\\": data.get(\\"longitude\\"),\\n            \\"source\\": \\"ip\\"\\n        }\\n    except requests.RequestException:\\n        return None\\n\\nsearch = DuckDuckGoSearchRun()\\n\\n# ---------------------------------------------------------\\n# Estado\\n# ---------------------------------------------------------\\n\\nclass State(TypedDict):\\n    messages: Annotated[list[AnyMessage], add_messages]\\n    memories: list[str]\\n    currentEpisode: str\\n\\ntools = [tvController, \\n            search,\\n            delegateToAI, \\n            listFiles, readFile, findFiles, overwriteFile, createDirectory, moveFile,\\n            getCurrentTimeTool, addTime, substractTime, timeDiff,\\n            getEmails, deleteEmail, readEmail,\\n            getCurrentWeather, getWeatherAt, getWeatherBetween]\\n\\n# ---------------------------------------------------------\\n# Modelo\\n# ---------------------------------------------------------\\n\\nmodel = ChatOllama(\\n    model=\\"qwen3.6:35b-a3b\\",\\n    temperature=0,\\n    num_predict=-1,\\n    num_ctx=65536\\n)\\n\\n# nvidia/nemotron-3-ultra-550b-a55b:free\\n# openrouter/free\\n# qwen/qwen3.5-9b\\n\\n# model = ChatOpenAI(\\n#     model=\\"openrouter/free\\",\\n#     base_url=\\"https://openrouter.ai/api/v1\\",\\n#     api_key=os.getenv(\\"OPENAI_API_KEY\\"),\\n#     temperature=0\\n# )\\n\\n# model = ChatOpenAI(\\n#     model=\\"qwen/qwen3.8-27b\\",\\n#     base_url=\\"https://api.groq.com/openai/v1\\",\\n#     api_key=os.getenv(\\"GROQ_API_KEY\\"),\\n#     temperature=0\\n# )\\n\\nmodel = model.bind_tools(tools)\\n\\ndef getEnvironment():\\n    timezone = getCurrentTimezone()\\n    location = getLocation()\\n  return {\\n        \\"datetime\\": getCurrentTime(timezone),\\n        \\"timezone\\": timezone,\\n        \\"location\\": location\\n    }\\n\\n# ---------------------------------------------------------\\n# Nodo del agente\\n# ---------------------------------------------------------\\n\\ndef agent(state: State):\\n    environment = getEnvironment()\\n    if environment[\\"location\\"]:\\n        locationText = f\\"\\"\\"\\\\\\n        - City: {environment[\\"location\\"][\\"city\\"]}\\n      - State: {environment[\\"location\\"][\\"state\\"]}\\n        - Country: {environment[\\"location\\"][\\"country\\"]}\\"\\"\\"\\n    else:\\n        locationText = \\"No data available.\\"\\n    environmentText = f\\"\\"\\"\\\\\\n        Current user environment:\\n        - Date and time: {environment[\\"datetime\\"]}\\n     - Timezone: {environment[\\"timezone\\"]}\\n        - Location:\\n        {locationText}\\"\\"\\"\\n    messages = [\\n        SystemMessage(content=environmentText),\\n    ]\\n    if state[\\"memories\\"]:\\n        memoryText = \\"\\\\n\\".join(\\n            f\\"- {memory}\\"\\n            for memory in state[\\"memories\\"]\\n        )\\n        messages.append(\\n            SystemMessage(\\n                content=f\\"Relevant facts about the user:\\\\n{memoryText}\\"\\n)\\n        )\\n    if state[\\"currentEpisode\\"]:\\n        messages.append(\\n                    SystemMessage(\\n                        content=f\\"Summary of the last conversation: :\\\\n{state[\\"currentEpisode\\"][\\"content\\"]}\\"\\n                    )\\n                )\\n    messages.extend(state[\\"messages\\"])\\n    response = model.invoke(messages)\\n    # print(\\"\\\\nMensaje actual: \\", messages[:-1])\\n    return {\\n        \\"messages\\": [response]\\n    }\\n\\n# ---------------------------------------------------------\\n# Nodo de tools\\n# ---------------------------------------------------------\\n\\ntool_node = ToolNode(tools)\\n\\ndef saveMessages(state: State):\\n    for message in state[\\"messages\\"]:\\n        message_id = addMessage(\\n            user_id=1,\\n            message=message\\n        )\\n        print(\\n            f\\"Guardado: {message.__class__.__name__} \\"\\n            f\\"(id={message_id})\\"\\n        )\\n    return {}\\n\\ndef saveEpisode(state: State):\\n    messages = [\\n        message\\n        for message in state[\\"messages\\"]\\n        if not isinstance(message, ToolMessage)\\n    ]\\n    formattedMessages = [\\n        serializeMessage(message)\\n        for message in messages\\n    ]\\n\\n    llmText = \\"\\\\n\\\\n\\".join(\\n   f\\"{message[\'role\'].upper()}\\\\n{message[\'content\']}\\"\\n        for message in formattedMessages\\n    )\\n    if state[\\"currentEpisode\\"]:\\n        mergeEpisode(state[\\"currentEpisode\\"], llmText)\\n        print(f\\"Updated episode (id={state[\\"currentEpisode\\"][\'id\']})\\")\\n    else:\\n        mergeEpisode(state[\\"currentEpisode\\"], llmText)\\n        print(\\"Created new episode\\")\\n    return {}\\ndef loadMemories(state: State):\\n    print(\\"Loading memories...\\")\\n    userMessage = state[\\"messages\\"][0].content\\n    memories = searchMemory(1, userMessage)\\n    return {\\n        \\"memories\\": memories\\n    }\\n\\ndef saveMemories(currentEpisode: dict):\\n    newMemories = extractMemories(currentEpisode[\\"content\\"])\\n    for memory in newMemories:\\n        addMemory(1, memory, currentEpisode[\\"id\\"])\\n\\ndef loadEpisode(state: State):\\n    print(\\"Loading episode...\\")\\n    currentEpisode = getEpisode()\\n    userMessage = state[\\"messages\\"][0].content\\n    \\n    if checkEpisodeRelevance(currentEpisode[\\"content\\"], userMessage):\\n        #Ask LLM if episode and message are compatible\\n        return {\\n            \\"currentEpisode\\": currentEpisode\\n        }\\n    else:\\n        saveMemories(currentEpisode)\\n        return {\\n        \\"currentEpisode\\": None\\n    }\\n\\n# ---------------------------------------------------------\\n# Router\\n# ---------------------------------------------------------\\n\\ndef shouldContinue(state: State):\\n    last_message = state[\\"messages\\"][-1]\\n    if last_message.tool_calls:\\n        return \\"tools\\"\\n    # print(state[\\"messages\\"])\\n    return \\"saveMessages\\"    \\n\\n# ---------------------------------------------------------\\n# Construir grafo\\n# ---------------------------------------------------------\\n\\ngraph = StateGraph(State)\\n\\ngraph.add_node(\\"agent\\", agent)\\ngraph.add_node(\\"tools\\", tool_node)\\ngraph.add_node(\\"loadEpisode\\", loadEpisode)\\ngraph.add_node(\\"loadMemories\\", loadMemories)\\ngraph.add_node(\\"saveMessages\\", saveMessages)\\ngraph.add_node(\\"saveEpisode\\", saveEpisode)\\n\\n# graph.add_edge(START, \\"agent\\")\\ngraph.add_edge(START, \\"loadEpisode\\")\\ngraph.add_edge(\\"loadEpisode\\", \\"loadMemories\\")\\ngraph.add_edge(\\"loadMemories\\", \\"agent\\")\\ngraph.add_edge(\\"saveMessages\\", \\"saveEpisode\\")\\ngraph.add_edge(\\"saveEpisode\\", END)\\ngraph.add_conditional_edges(\\n    \\"agent\\",\\n    shouldContinue,\\n    {\\n        \\"tools\\": \\"tools\\",\\n        \\"saveMessages\\": \\"saveMessages\\"\\n    }\\n)\\n\\ngraph.add_edge(\\"tools\\", \\"agent\\")\\n\\n# ---------------------------------------------------------\\n# Compilar\\n# ---------------------------------------------------------\\n\\napp = graph.compile()\\n\\n# ---------------------------------------------------------\\n# Ejecutar\\n# ---------------------------------------------------------\\nstart = time.perf_counter()\\n\\nresult = app.invoke({\\n    \\"messages\\": [\\n        {\\n            \\"role\\": \\"user\\",\\n            \\"content\\": \\"Revisa main.py y actualiza el README\\"\\n        }\\n    ],\\n    \\"memories\\": [],\\n    # \\"task\\": \\"\\",\\n    # \\"taskComplete\\": False\\n})\\nelapsed = time.perf_counter() - start\\n\\n# print(result)\\n# print(result[\\"messages\\"][-1].content)\\ndef print_result(result):\\n    messages = result[\\"messages\\"]\\n\\n    print(\\"\\\\n\\" + \\"=\\" * 76)\\n    print(\\"                              AGENT TRACE\\")\\n    print(\\"=\\" * 76)\\n\\n    total_input_tokens = 0\\n    total_output_tokens = 0\\n    total_llm_time = 0\\n    total_tool_calls = 0\\n    llm_calls = 0\\n    empty_responses = 0\\n    tools_used = []\\n\\n    for i, message in enumerate(messages):\\n        message_type = message.__class__.__name__\\n\\n        print(f\\"\\\\n[{i}] {message_type}\\")\\n        print(\\"-\\" * 76)\\n\\n        # ---------------------------------------------------------\\n        # Human message\\n        # ---------------------------------------------------------\\n        if message_type == \\"HumanMessage\\":\\n            print(f\\"Usuario: {message.content}\\")\\n\\n        # ---------------------------------------------------------\\n        # AI message\\n        # ---------------------------------------------------------\\n        elif message_type == \\"AIMessage\\":\\n     # DEBUG\\n            # from pprint import pprint\\n\\n            # print(\\"\\\\nDEBUG - AIMessage completo:\\")\\n            # pprint(message.model_dump(), sort_dicts=False)\\n            llm_calls += 1\\n\\n            content = getattr(message, \\"content\\", \\"\\")\\n            tool_calls = getattr(message, \\"tool_calls\\", [])\\n            metadata = getattr(message, \\"response_metadata\\", {}) or {}\\n            usage = getattr(message, \\"usage_metadata\\", {}) or {}\\n\\n            # -----------------------------------------------------\\n            # Tokens\\n            # -----------------------------------------------------\\n         input_tokens = (\\n                usage.get(\\"input_tokens\\")\\n                or metadata.get(\\"prompt_eval_count\\")\\n                or 0\\n    )\\n\\n            output_tokens = (\\n                usage.get(\\"output_tokens\\")\\n                or metadata.get(\\"eval_count\\")\\n                or 0\\n            )\\n\\n            total_input_tokens += input_tokens\\n            total_output_tokens += output_tokens\\n\\n            # -----------------------------------------------------\\n            # Tiempos de Ollama\\n            # Los valores de Ollama están en nanosegundos\\n            # -----------------------------------------------------\\n            total_duration = metadata.get(\\"total_duration\\")\\n            load_duration = metadata.get(\\"load_duration\\")\\n prompt_duration = metadata.get(\\"prompt_eval_duration\\")\\n            eval_duration = metadata.get(\\"eval_duration\\")\\n\\n            def ns_to_seconds(value):\\n                if value is None:\\n                    return None\\n                return value / 1_000_000_000\\n\\n            total_s = ns_to_seconds(total_duration)\\n            load_s = ns_to_seconds(load_duration)\\n            prompt_s = ns_to_seconds(prompt_duration)\\n            eval_s = ns_to_seconds(eval_duration)\\n\\n            if total_s is not None:\\n                total_llm_time += total_s\\n\\n            # -----------------------------------------------------\\n         # TPS\\n            # -----------------------------------------------------\\n            input_tps = (\\n                input_tokens / prompt_s\\n       if input_tokens and prompt_s and prompt_s > 0\\n                else None\\n            )\\n\\n            output_tps = (\\n                output_tokens / eval_s\\n                if output_tokens and eval_s and eval_s > 0\\n                else None\\n            )\\n\\n            # -----------------------------------------------------\\n            # Mostrar estadísticas de la llamada\\n            # -----------------------------------------------------\\n            print(\\"LLM call:\\")\\n\\n            if total_s is not None:\\n                print(f\\"  Tiempo total:     {total_s:.2f} s\\")\\n\\n            if load_s is not None:\\n         print(f\\"  Carga modelo:     {load_s:.2f} s\\")\\n\\n            if prompt_s is not None:\\n                print(f\\"  Procesamiento:    {prompt_s:.2f} s\\")\\n\\n            if eval_s is not None:\\n                print(f\\"  Generación:       {eval_s:.2f} s\\")\\n\\n            if input_tokens:\\n                print(f\\"  Input tokens:     {input_tokens:,}\\")\\n\\n            if output_tokens:\\n                print(f\\"  Output tokens:    {output_tokens:,}\\")\\n\\n   if input_tps is not None:\\n                print(f\\"  Input TPS:        {input_tps:.1f}\\")\\n\\n            if output_tps is not None:\\n                print(f\\"  Output TPS:       {output_tps:.1f}\\")\\n\\n            # -----------------------------------------------------\\n            # Tool calls\\n            # -----------------------------------------------------\\n            if tool_calls:\\n                print(\\"\\\\nTool calls:\\")\\n\\n                for call in tool_calls:\\n                    name = call.get(\\"name\\", \\"unknown\\")\\n                    args = call.get(\\"args\\", {})\\n                    call_id = call.get(\\"id\\")\\n\\n                    total_tool_calls += 1\\n\\n                    if name not in tools_used:\\n                        tools_used.append(name)\\n\\n                print(f\\"  → {name}\\")\\n\\n                    if args:\\n                        for key, value in args.items():\\n                            print(f\\"      {key}: {value}\\")\\n\\n                    if call_id:\\n                        print(f\\"      id: {call_id}\\")\\n\\n            # -----------------------------------------------------\\n            # Respuesta final\\n            # -----------------------------------------------------\\n            if content:\\n                print(\\"\\\\nContenido:\\")\\n                print(content)\\n\\n            elif not tool_calls:\\n                empty_responses += 1\\n       print(\\"\\\\n⚠ ADVERTENCIA: AIMessage vacío\\")\\n                metadata = getattr(message, \\"response_metadata\\", {}) or {}\\n                print(\\"\\\\nMotivo: \\", metadata.get(\\"done_reason\\"))\\n                # Puede ser útil si Ollama/LangChain puso reasoning\\n                # en otro campo.\\n      additional_kwargs = getattr(\\n                    message,\\n                    \\"additional_kwargs\\",\\n                    {}\\n                ) or {}\\n\\n                if additional_kwargs:\\n                    print(\\"  additional_kwargs:\\")\\n                    print(f\\"    {additional_kwargs}\\")\\n\\n    # ---------------------------------------------------------\\n        # Tool message\\n        # ---------------------------------------------------------\\n   elif message_type == \\"ToolMessage\\":\\n\\n            tool_name = getattr(message, \\"name\\", \\"unknown\\")\\n            content = getattr(message, \\"content\\", \\"\\")\\n\\n            print(f\\"Tool: {tool_name}\\")\\n\\n            print(\\"Resultado:\\")\\n            print(content)\\n\\n        # ---------------------------------------------------------\\n        # Cualquier otro tipo de mensaje\\n        # ---------------------------------------------------------\\n        else:\\n            content = getattr(message, \\"content\\", \\"\\")\\n\\n            if content:\\n                print(f\\"Contenido:\\\\n{content}\\")\\n\\n    # =============================================================\\n    # RESUMEN\\n    # =============================================================\\n\\n    print(\\"\\\\n\\" + \\"=\\" * 76)\\n    print(\\"                               SUMMARY\\")\\n    print(\\"=\\" * 76)\\n\\n    print(f\\"LLM calls:          {llm_calls}\\")\\n  print(f\\"Tool calls:         {total_tool_calls}\\")\\n\\n    if tools_used:\\n        print(f\\"Tools usadas:       {\', \'.join(tools_used)}\\")\\n    else:\\n     print(\\"Tools usadas:       Ninguna\\")\\n\\n    print(f\\"Input tokens:       {total_input_tokens:,}\\")\\n    print(f\\"Output tokens:      {total_output_tokens:,}\\")\\n    print(f\\"Total tokens:       {total_input_tokens + total_output_tokens:,}\\")\\n\\n    if total_llm_time > 0:\\n        print(f\\"Tiempo LLM: {total_llm_time:.2f} s\\")\\n\\n    if empty_responses:\\n        print(f\\"Respuestas vacías:  ⚠ {empty_responses}\\")\\n\\n    print(\\"=\\" * 76)\\nprint_result(result)\\n\\n"}'), (157, 1, None, 'tool', '{"success": true, "path": "E:/Proyectos/Automation/AI Agent/README.md", "result": "# AI Personal Assistant\\n\\n## Objetivo\\n\\nDesarrollar un agente de IA personal robusto que funcione correctamente en al menos el **80 %** de los casos. El agente debe:\\n\\n1. Entender la instrucción del usuario.\\n2. Planificar qué herramientas necesita.\\n3. Ejecutar las acciones seleccionadas.\\n4. Observar los resultados y decidir si la tarea está completa, se necesita información adicional o se debe cambiar el enfoque.\\n\\n## Arquitectura y tecnología\\n\\n- **Orquestación:** LangGraph (`StateGraph`).\\n- **Modelo activo:** `ChatOpenAI` con OpenRouter (`openrouter/free`) y `temperature=0`.\\n- **Modelos alternativos:** Ollama y Groq aparecen como ejemplos comentados.\\n- **Memoria y contexto:** módulos de SQLite para memoria y episodios de conversación.\\n- **Principio de diseño:** local-first / privacy-first, aunque actualmente algunas capacidadesdependen de servicios externos.\\n\\n## Resumen de `main.py`\\n\\n`main.py` configura y ejecuta directamente el grafo del agente.\\n\\n### Componentes principales\\n\\n- **Estado:** `State` contiene mensajes, recuerdos y episodio actual. `AgentState` fue definido para una futura clasificación de tareas, pero no se utiliza.\\n- **Herramientas:** se registra un conjunto de herramientas para TV, selección de modelo, archivos, tiempo, memoria, correo, clima, búsqueda, entrada del usuario y otros servicios.\\n- **Modelo:** se carga `.env` y se crea `ChatOpenAI` con la clave `OPENAI_API_KEY`. Las herramientas se vinculan al modelo mediante `bind_tools()`.\\n- **Entorno:** `getEnvironment()` obtiene la zona horaria, la ubicación aproximada mediante `ipwho.is` y la hora actual.\\n- **Nodo `agent`:** construye mensajes del sistema con el entorno, recuerdos relevantes y el resumen del episodio anterior; después invoca al modelo.\\n- **Nodo `tools`:** `ToolNode` ejecuta las herramientas solicitadas por el modelo.\\n- **Carga de contexto:** `loadEpisode()` comprueba la relevancia del episodio anterior y `loadMemories()` busca recuerdos relacionados con elprimer mensaje del usuario.\\n- **Persistencia:** `saveMessages()` guarda los mensajes mediante `addMessage()`.\\n- **Enrutamiento:** `shouldContinue()` decide si elagente debe volver al nodo de herramientas o guardar los mensajes y terminar.\\n- **Ejecución automática:** al final del archivo se invoca el grafo con la solicitud actual y se imprime un trazado detallado del agente, llamadas LLM, herramientas y estadísticas.\\n\\n## Flujo de ejecución\\n\\n```text\\nSTART\\n  → loadEpisode\\n  → loadMemories\\n  → agent\\n      ├─ con tool_calls → tools → agent\\n      └─ sin tool_calls → saveMessages → END\\n```\\n\\nEl ciclo se repite mientras el modelo siga solicitando herramientas.\\n\\n## Herramientas disponibles\\n\\n| Categoría | Herramientas |\\n|---|---|\\n| Control de dispositivos | `tvController` |\\n| Selección de modelo | `delegateToAI` |\\n| Sistema de archivos | `listFiles`, `readFile`, `findFiles`, `overwriteFile`, `createDirectory`, `moveFile` |\\n| Tiempo | `getCurrentTimeTool`, `addTime`, `substractTime`, `timeDiff` |\\n| Memoria | `searchMemory` |\\n| Correo | `getEmails`, `deleteEmail`, `readEmail` |\\n| Clima | `getCurrentWeather`, `getWeatherAt`, `getWeatherBetween` |\\n| Búsqueda web | `DuckDuckGoSearchRun` |\\n| Entrada del usuario | `requestUserInput` |\\n| Scheduler | `Scheduler` (importado, pero aún no registrado como herramienta) |\\n| Ubicación | `getLocation()` (mediante `ipwho.is`) |\\n\\n## Estado del proyecto\\n\\n| Fase | Estado |\\n|---|---|\\n| Núcleo LangGraph y herramientas | 🟡 Parcialmente completado |\\n| Memoria SQLite y episodios | 🟡 Implementación parcial |\\n| Capacidades locales | 🟡 Herramientas disponibles, integración pendiente |\\n| Integraciones externas | 🟡 Implementadas de forma aislada |\\n| Scheduler | ⏳ Importado, no activo |\\n| Delegación avanzada y trabajos largos | ⏳ Pendiente |\\n\\n## Limitaciones actuales\\n\\n- `understandTask()` y `checkTaskComplete()` contienen código placeholder y no forman parte del grafo.\\n- No existe todavía un nodo explícito para comprobar el cumplimiento de la tarea.\\n- `loadEpisode()` puede devolver `None`, mientras que el siguiente nodo espera un diccionario de estado.\\n- `addMemory()` está importado, pero no se registra en la lista de herramientas.\\n- La ejecución está ligada a una solicitud concreta al final de `main.py`; no funciona todavía como una interfaz reutilizable.\\n- Las herramientas externas no necesariamente devuelven JSON estructurado.\\n- Las operaciones sensibles no tienen todavía un esquema uniforme de permisos y confirmación.\\n- `getLocation()` y el modelo activo envían información a servicios externos, lo que debe revisarse desde el punto de vista de privacidad.\\n- Falta una capa común de validación y manejo de errores para todas las herramientas.\\n\\n## Seguridad\\n\\nSe debe implementar un esquema de permisos con:\\n\\n- Confirmación explícita para acciones irreversibles o de alto riesgo.\\n- Listas blancas de archivos, cuentas, dispositivos y dominios.\\n- Mínimos privilegios para cada herramienta.\\n- Protección de claves y datos personales.\\n- Validación de respuestas antes de ejecutar una acción.\\n- Registros de auditoría para operaciones sensibles.\\n\\nLas credenciales deben mantenerse en un archivo `.env` excluido del repositorio. No se debe asumir que las credenciales expuestas en `secrets.md` han sido migradas hasta comprobarlo y eliminar el archivo inseguro.\\n\\n## Próximos pasos\\n\\n1. Convertir `main.py` en una aplicación reutilizable y parametrizable.\\n2. Completar la persistencia de memoria y episodios en SQLite.\\n3. Registrar `addMemory` y el scheduler en el grafo.\\n4. Añadir un nodo explícito de validación y conclusión.\\n5. Unificar el formato de respuesta de todas las herramientas en JSON estructurado.\\n6. Añadir permisos y confirmaciones antes de modificar archivos, borrar correos o controlar dispositivos.\\n7. Evaluar una opción local para reducir las dependencias externas.\\n\\n---\\n\\n*Última actualización: 17 de septiembre de 2026*\\n"}'), (158, 1, None, 'assistant', '{"content": "", "tool_calls": [{"name": "overwriteFile", "args": {"content": "# AI Personal Assistant\\n\\n## Objetivo\\n\\nDesarrollar un agente de IA personal robusto que funcione correctamente en al menos el **80 %**de los casos. El agente debe:\\n\\n1. Entender la instrucción del usuario.\\n2. Planificar qué herramientas necesita.\\n3. Ejecutar las acciones seleccionadas.\\n4. Observar los resultados y decidir si la tarea está completa, se necesita información adicional o se debe cambiar el enfoque.\\n\\n## Arquitectura y tecnología\\n\\n- **Orquestación:** LangGraph (`StateGraph`).\\n- **Modelo activo:** `ChatOllama` con `qwen3.6:35b-a3b`, `temperature=0` y `num_ctx=65536`.\\n- **Modelos alternativos:** `ChatOpenAI` con OpenRouter (`openrouter/free`) y Groq aparecen como ejemplos comentados.\\n- **Memoria y contexto:** módulos de SQLite para memoria episódica y recuperación semántica.\\n- **Principio de diseño:** local-first / privacy-first, aunque actualmente algunas capacidades dependen de servicios externos (ipwho.is, OpenRouter/Groq).\\n\\n## Resumen de `main.py`\\n\\n`main.py` configura y ejecuta directamente el grafo del agente con un trazado detallado al final.\\n\\n### Componentes principales\\n\\n- **Estado:** `State` contiene mensajes (`Annotated[list[AnyMessage], add_messages]`), recuerdos (`memories`) y episodio actual (`currentEpisode`).\\n- **Herramientas vinculadas:** `tvController`, `DuckDuckGoSearchRun`, `delegateToAI`, gestor de archivos (`listFiles`, `readFile`, `findFiles`, `overwriteFile`, `createDirectory`, `moveFile`), funciones de tiempo (`getCurrentTimeTool`, `addTime`, `substractTime`, `timeDiff`), correo (`getEmails`, `deleteEmail`, `readEmail`) y clima (`getCurrentWeather`, `getWeatherAt`, `getWeatherBetween`).\\n- **Modelo:** se carga `.env` y se inicializa `ChatOllama`. Las herramientas se vinculan al modelo mediante `bind_tools()`.\\n- **Entorno:** `getEnvironment()` obtiene la zona horaria, la ubicación aproximada mediante `ipwho.is` y la hora actual. Se inyecta como `SystemMessage` en cada iteración.\\n- **Nodo `agent`:** construye el contexto del sistema (entorno, recuerdos relevantes, resumen del episodio anterior) e invoca al modelo.\\n- **Nodo `tools`:** `ToolNode` ejecuta las herramientas solicitadas por el modelo y devuelve los resultados al agente.\\n- **Carga de contexto:** `loadEpisode()`comprueba la relevancia del episodio anterior para decidir si se reutiliza o se cierra (guardando sus memorias). `loadMemories()` busca recuerdos relacionados con elprimer mensaje del usuario.\\n- **Persistencia:** `saveMessages()` guarda los mensajes en SQLite. `saveEpisode()` serializa y almacena/actualiza el episodio de conversación.\\n- **Enrutamiento:** `shouldContinue()` decide si el agente debe volver al nodo de herramientas (`tools`) o guardar los mensajes y finalizar (`saveMessages`).\\n- **Trazado detallado:** la función `print_result()` imprime estadísticas completas: tokens (input/output), tiempos de carga/procesamiento/generación, TPS, llamadas a herramientas y advertencias sobre respuestas vacías.\\n\\n## Flujo de ejecución\\n\\n```text\\nSTART\\n  → loadEpisode\\n  → loadMemories\\n  → agent\\n      ├─con tool_calls → tools → agent (ciclo)\\n      └─ sin tool_calls → saveMessages → saveEpisode → END\\n```\\n\\nEl ciclo se repite mientras el modelo siga solicitandoherramientas. Al finalizar, se guarda el episodio y se imprime el trazado.\\n\\n## Herramientas disponibles\\n\\n| Categoría | Herramientas |\\n|---|---|\\n| Controlde dispositivos | `tvController` |\\n| Selección de modelo | `delegateToAI` |\\n| Sistema de archivos | `listFiles`, `readFile`, `findFiles`, `overwriteFile`, `createDirectory`, `moveFile` |\\n| Tiempo | `getCurrentTimeTool`, `addTime`, `substractTime`, `timeDiff` |\\n| Correo | `getEmails`, `deleteEmail`, `readEmail` |\\n| Clima| `getCurrentWeather`, `getWeatherAt`, `getWeatherBetween` |\\n| Búsqueda web | `DuckDuckGoSearchRun` |\\n| Ubicación | `getLocation()` (mediante `ipwho.is`) |\\n\\n> **Nota:** `addMemory`, `searchMemory` y `extractMemories` se usan internamente en los nodos de carga/guardado de contexto, pero no están registrados como herramientas ejecutables por el modelo.\\n\\n## Estado del proyecto\\n\\n| Fase | Estado |\\n|---|---|\\n| Núcleo LangGraph y herramientas | 🟢 Funcional |\\n| Memoria SQLite yepisodios | 🟡 Implementación parcial (persistencia operativa, recuperación semántica en mejora) |\\n| Capacidades locales | 🟢 Herramientas disponibles y vinculadas|\\n| Integraciones externas | 🟢 Implementadas (TV, correo, clima, búsqueda, ubicación IP) |\\n| Delegación avanzada | 🟢 `delegateToAI` operativo |\\n\\n## Limitaciones actuales\\n\\n- `addMemory` no está registrado en la lista de herramientas del grafo; solo se usa internamente.\\n- La ejecución está ligada a una solicitud concreta al final de `main.py`; no funciona todavía como una interfaz reutilizable o servidor.\\n- Las herramientas externas no necesariamente devuelven JSON estructurado uniforme.\\n- Las operaciones sensibles no tienen todavía un esquema uniforme de permisos y confirmación.\\n- `getLocation()` envía información a servicios externos(`ipwho.is`), lo que debe revisarse desde el punto de vista de privacidad.\\n- Falta una capa común de validación y manejo de errores para todas las herramientas.\\n\\n## Seguridad\\n\\nSe debe implementar un esquema de permisos con:\\n\\n- Confirmación explícita para acciones irreversibles o de alto riesgo.\\n- Listas blancas dearchivos, cuentas, dispositivos y dominios.\\n- Mínimos privilegios para cada herramienta.\\n- Protección de claves y datos personales.\\n- Validación de respuestas antes de ejecutar una acción.\\n- Registros de auditoría para operaciones sensibles.\\n\\nLas credenciales deben mantenerse en un archivo `.env` excluido del repositorio. No se debe asumir que las credenciales expuestas en `secrets.md` han sido migradas hasta comprobarlo y eliminar el archivo inseguro.\\n\\n## Próximos pasos\\n\\n1. Convertir `main.py` en una aplicación reutilizable (CLI o API FastAPI).\\n2. Completar la persistencia de memoria y episodios en SQLite.\\n3. Registrar `addMemory`como herramienta si se requiere ejecución directa por el agente.\\n4. Añadir un nodo explícito de validación y conclusión de tareas.\\n5. Unificar el formato de respuesta de todas las herramientas en JSON estructurado.\\n6. Añadir permisos y confirmaciones antes de modificar archivos, borrar correos o controlar dispositivos.\\n7.Evaluar una opción local para `getLocation()` y reducir dependencias externas.\\n\\n---\\n\\n*Última actualización: 24 de septiembre de 2026*\\n", "path": "E:/Proyectos/Automation/AI Agent/README.md"}, "id": "80e4a0c2-df39-49f7-9985-355fe3286187", "type": "tool_call"}]}'), (159, 1, None, 'tool', '{"success": true, "path": "E:/Proyectos/Automation/AI Agent/README.md", "result": "File written successfully."}'), (160, 1, None, 'assistant', 'He revisado `main.py` y actualizado el README con los siguientes cambios:\n\n1. **Modelo activo:** Se actualizó de `ChatOpenAI` a `ChatOllama` con `qwen3.6:35b-a3b`, incluyendo parámetros como `temperature=0` y `num_ctx=65536`.\n2. **Herramientas vinculadas:** Se listaron explícitamente las herramientas registradas en el grafo (`tvController`, `DuckDuckGoSearchRun`, `delegateToAI`, gestor de archivos, tiempo, correo y clima).\n3. **Claridad sobre memoria:** Se aclaró que `addMemory`, `searchMemory` y `extractMemories` se usan internamente en los nodos de contexto, pero no están registrados como herramientas ejecutables por el modelo.\n4. **Flujo de ejecución:** Se actualizó para reflejar el nodo `saveEpisode` antes de finalizar.\n5. **Estado del proyecto:** Se ajustaron las fases a un estado más preciso según la implementación actual.\n6. **Fecha de actualización:** Actualizada al 24 de septiembre de 2026.')]
        formatedMessages = [{'role': message[3], 'content': message[4]} for message in messages] #Formato de message.serializeMessage()
        # print(formatedMessages)
        # llmText = ""

        # for message in formatedMessages:
        #     if message["role"] == "tool":
        #         print(f"{message["role"].upper()}\n {message["content"]}\n\n")
        #     llmText += f"{message["role"].upper()}\n {message["content"]}\n\n"
    
        # paths = set()
        # for message in formatedMessages:
        #     if message["role"] != "tool":
        #         continue
        #     data = json.loads(message["content"])
        #     if data.get("success") and data.get("path"):
        #         paths.add(data["path"])
        # dataForNewEpisode = {
        #     "current_episode": {},
        #     "user_request": formatedMessages[0]["content"],
        #     "agent_response": formatedMessages[-1]["content"],
        #     "observed_paths": paths,
        #     "tool_messages": getSuccessfulToolResults(formatedMessages)
        # }
        # # print(f"LAST INTERACTION:\nUser request: \n{formatedMessages[0]["content"]}", f"\nAgent response: \n{formatedMessages[-1]["content"]}")
        # # print(f"Observed paths: \n{paths}")
        # print(dataForNewEpisode)
        
        mergeEpisode("", formatedMessages)
    else:
        print("Opción no válida")
    end = time.perf_counter()
    print(f"Tiempo total: {end - start:.2f}s")
  