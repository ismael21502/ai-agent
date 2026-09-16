from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from BuiltInTools.tvController import tvController
from BuiltInTools.modelSelector import delegateToAI
from BuiltInTools.Files.fileManager import listFiles, readFile, findFiles, overwriteFile, createDirectory, moveFile
from BuiltInTools.System.timeFunctions import getCurrentTime, getCurrentTimeTool, getCurrentTimezone, addTime, substractTime, timeDiff
from BuiltInTools.System.memory import addMemory, searchMemory
from BuiltInTools.Google.gmail import getEmails, deleteEmail, readEmail
from BuiltInTools.System.weather import getCurrentWeather, getWeatherBetween, getWeatherAt

from dotenv import load_dotenv
import os

from datetime import datetime, timezone
from BuiltInTools.scheduler import Scheduler

import time 

from langchain_community.tools import DuckDuckGoSearchRun

load_dotenv()

#TODO: Buscar un lugar mejor para esto: 
import requests
def getLocation():
    try:
        response = requests.get(
            "https://ipwho.is/",
            timeout=3
        )
        response.raise_for_status()
        data = response.json()
        return {
            "city": data.get("city"),
            "state": data.get("region"),
            "country": data.get("country"),
            # "latitude": data.get("latitude"),
            # "longitude": data.get("longitude"),
            "source": "ip"
        }
    except requests.RequestException:
        return None

search = DuckDuckGoSearchRun()

# ---------------------------------------------------------
# Estado
# ---------------------------------------------------------

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    memories: list[str]

@tool
def requestUserInput(question: str):    
    """Request input from the user.
    Use this tool to ask the user for information or clarification. The agent will wait for the user's response before proceeding.
    Args:
        question (str): The question to ask the user.
    Returns:
        dict: A dictionary containing the user's response.
    """
    response = input(f"{question} ")
    return {
        "success": True,
        "response": response
    }
tools = [tvController, 
            # scheduleTask,
            search,
            delegateToAI, 
            listFiles, readFile, findFiles, overwriteFile, createDirectory, moveFile,
            getCurrentTimeTool, addTime, substractTime, timeDiff,
            addMemory,
            getEmails, deleteEmail, readEmail,
            getCurrentWeather, getWeatherAt, getWeatherBetween,
            requestUserInput]

# ---------------------------------------------------------
# Modelo
# ---------------------------------------------------------

# model = ChatOllama(
#     model="qwen3.5:9b",
#     temperature=0,
#     num_predict=-1,
#     num_ctx=32768
# )

# nvidia/nemotron-3-ultra-550b-a55b:free
# openrouter/free
# qwen/qwen3.5-9b

model = ChatOpenAI(
    model="openrouter/free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
)

# model = ChatOpenAI(
#     model="qwen/qwen3.8-27b",
#     base_url="https://api.groq.com/openai/v1",
#     api_key=os.getenv("GROQ_API_KEY"),
#     temperature=0
# )

model = model.bind_tools(tools)

def getEnvironment():
    timezone = getCurrentTimezone()
    location = getLocation()
    return {
        "datetime": getCurrentTime(timezone),
        "timezone": timezone,
        "location": location
    }

# ---------------------------------------------------------
# Nodo del agente
# ---------------------------------------------------------
class AgentState(TypedDict):
    messages: list
    memories: list
    task: str
    isTaskComplete: bool

#TODO: Este será un nodo para que el agente entienda la task. Pero aún no me parece necesario. Podría usar un modelo 2b o 1b
def understandTask(state: AgentState):
    task = ...
    return {
        "task": task
    }
#TODO: En este caso, este nodo sí es más necesario. También usará un modelo IA para analizar si la tarea fue completada, pero tal vez tenga que hacerlo el modelo principal.
def checkTaskComplete(state: AgentState):
    isComplete = ...
    return {
        "isTaskComplete": isComplete
    }
def agent(state: State):
    environment = getEnvironment()
    if environment["location"]:
        locationText = f"""\
        - City: {environment["location"]["city"]}
        - State: {environment["location"]["state"]}
        - Country: {environment["location"]["country"]}"""
    else:
        locationText = "No data available."
    environmentText = f"""\
        Current user environment:
        - Date and time: {environment["datetime"]}
        - Timezone: {environment["timezone"]}
        - Location:
        {locationText}"""
    messages = [
        SystemMessage(content=environmentText),
    ]
    if state["memories"]:
        memoryText = "\n".join(
            f"- {memory}"
            for memory in state["memories"]
        )
        messages.append(
            SystemMessage(
                content=f"Relevant facts about the user:\n{memoryText}"
            )
        )
    messages.extend(state["messages"])
    response = model.invoke(messages)
    print(messages)
    return {
        "messages": [response]
    }

# ---------------------------------------------------------
# Nodo de tools
# ---------------------------------------------------------

tool_node = ToolNode(tools)

def loadMemories(state: State):
    user_message = state["messages"][0].content
    memories = searchMemory(user_message)
    return {
        "memories": memories
    }

# ---------------------------------------------------------
# Router
# ---------------------------------------------------------

def shouldContinue(state: State):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


# ---------------------------------------------------------
# Construir grafo
# ---------------------------------------------------------

graph = StateGraph(State)

graph.add_node("agent", agent)
graph.add_node("tools", tool_node)
graph.add_node("loadMemories", loadMemories)

# graph.add_edge(START, "agent")
graph.add_edge(START, "loadMemories")
graph.add_edge("loadMemories", "agent")

graph.add_conditional_edges(
    "agent",
    shouldContinue,
    {
        "tools": "tools",
        END: END
    }
)


graph.add_edge("tools", "agent")

# ---------------------------------------------------------
# Compilar
# ---------------------------------------------------------

app = graph.compile()

# ---------------------------------------------------------
# Ejecutar
# ---------------------------------------------------------
start = time.perf_counter()

result = app.invoke({
    "messages": [
        {
            "role": "user",
            "content": "Revisa y haz un resumen del clima de mañana, por favor"
        }
    ],
    "memories": [],
    # "task": "",
    # "taskComplete": False
})
elapsed = time.perf_counter() - start

# print(result)
# print(result["messages"][-1].content)
def print_result(result):
    messages = result["messages"]

    print("\n" + "=" * 76)
    print("                              AGENT TRACE")
    print("=" * 76)

    total_input_tokens = 0
    total_output_tokens = 0
    total_llm_time = 0
    total_tool_calls = 0
    llm_calls = 0
    empty_responses = 0
    tools_used = []

    for i, message in enumerate(messages):
        message_type = message.__class__.__name__

        print(f"\n[{i}] {message_type}")
        print("-" * 76)

        # ---------------------------------------------------------
        # Human message
        # ---------------------------------------------------------
        if message_type == "HumanMessage":
            print(f"Usuario: {message.content}")

        # ---------------------------------------------------------
        # AI message
        # ---------------------------------------------------------
        elif message_type == "AIMessage":
            # DEBUG
            # from pprint import pprint

            # print("\nDEBUG - AIMessage completo:")
            # pprint(message.model_dump(), sort_dicts=False)
            llm_calls += 1

            content = getattr(message, "content", "")
            tool_calls = getattr(message, "tool_calls", [])
            metadata = getattr(message, "response_metadata", {}) or {}
            usage = getattr(message, "usage_metadata", {}) or {}

            # -----------------------------------------------------
            # Tokens
            # -----------------------------------------------------
            input_tokens = (
                usage.get("input_tokens")
                or metadata.get("prompt_eval_count")
                or 0
            )

            output_tokens = (
                usage.get("output_tokens")
                or metadata.get("eval_count")
                or 0
            )

            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            # -----------------------------------------------------
            # Tiempos de Ollama
            # Los valores de Ollama están en nanosegundos
            # -----------------------------------------------------
            total_duration = metadata.get("total_duration")
            load_duration = metadata.get("load_duration")
            prompt_duration = metadata.get("prompt_eval_duration")
            eval_duration = metadata.get("eval_duration")

            def ns_to_seconds(value):
                if value is None:
                    return None
                return value / 1_000_000_000

            total_s = ns_to_seconds(total_duration)
            load_s = ns_to_seconds(load_duration)
            prompt_s = ns_to_seconds(prompt_duration)
            eval_s = ns_to_seconds(eval_duration)

            if total_s is not None:
                total_llm_time += total_s

            # -----------------------------------------------------
            # TPS
            # -----------------------------------------------------
            input_tps = (
                input_tokens / prompt_s
                if input_tokens and prompt_s and prompt_s > 0
                else None
            )

            output_tps = (
                output_tokens / eval_s
                if output_tokens and eval_s and eval_s > 0
                else None
            )

            # -----------------------------------------------------
            # Mostrar estadísticas de la llamada
            # -----------------------------------------------------
            print("LLM call:")

            if total_s is not None:
                print(f"  Tiempo total:     {total_s:.2f} s")

            if load_s is not None:
                print(f"  Carga modelo:     {load_s:.2f} s")

            if prompt_s is not None:
                print(f"  Procesamiento:    {prompt_s:.2f} s")

            if eval_s is not None:
                print(f"  Generación:       {eval_s:.2f} s")

            if input_tokens:
                print(f"  Input tokens:     {input_tokens:,}")

            if output_tokens:
                print(f"  Output tokens:    {output_tokens:,}")

            if input_tps is not None:
                print(f"  Input TPS:        {input_tps:.1f}")

            if output_tps is not None:
                print(f"  Output TPS:       {output_tps:.1f}")

            # -----------------------------------------------------
            # Tool calls
            # -----------------------------------------------------
            if tool_calls:
                print("\nTool calls:")

                for call in tool_calls:
                    name = call.get("name", "unknown")
                    args = call.get("args", {})
                    call_id = call.get("id")

                    total_tool_calls += 1

                    if name not in tools_used:
                        tools_used.append(name)

                    print(f"  → {name}")

                    if args:
                        for key, value in args.items():
                            print(f"      {key}: {value}")

                    if call_id:
                        print(f"      id: {call_id}")

            # -----------------------------------------------------
            # Respuesta final
            # -----------------------------------------------------
            if content:
                print("\nContenido:")
                print(content)

            elif not tool_calls:
                empty_responses += 1
                print("\n⚠ ADVERTENCIA: AIMessage vacío")
                metadata = getattr(message, "response_metadata", {}) or {}
                print("\nMotivo: ", metadata.get("done_reason"))
                # Puede ser útil si Ollama/LangChain puso reasoning
                # en otro campo.
                additional_kwargs = getattr(
                    message,
                    "additional_kwargs",
                    {}
                ) or {}

                if additional_kwargs:
                    print("  additional_kwargs:")
                    print(f"    {additional_kwargs}")

        # ---------------------------------------------------------
        # Tool message
        # ---------------------------------------------------------
        elif message_type == "ToolMessage":

            tool_name = getattr(message, "name", "unknown")
            content = getattr(message, "content", "")

            print(f"Tool: {tool_name}")

            print("Resultado:")
            print(content)

        # ---------------------------------------------------------
        # Cualquier otro tipo de mensaje
        # ---------------------------------------------------------
        else:
            content = getattr(message, "content", "")

            if content:
                print(f"Contenido:\n{content}")

    # =============================================================
    # RESUMEN
    # =============================================================

    print("\n" + "=" * 76)
    print("                               SUMMARY")
    print("=" * 76)

    print(f"LLM calls:          {llm_calls}")
    print(f"Tool calls:         {total_tool_calls}")

    if tools_used:
        print(f"Tools usadas:       {', '.join(tools_used)}")
    else:
        print("Tools usadas:       Ninguna")

    print(f"Input tokens:       {total_input_tokens:,}")
    print(f"Output tokens:      {total_output_tokens:,}")
    print(f"Total tokens:       {total_input_tokens + total_output_tokens:,}")

    if total_llm_time > 0:
        print(f"Tiempo LLM:         {total_llm_time:.2f} s")

    if empty_responses:
        print(f"Respuestas vacías:  ⚠ {empty_responses}")

    print("=" * 76)
print_result(result)