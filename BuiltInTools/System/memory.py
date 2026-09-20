import ollama
import math
import sqlite3
import json
from langchain_core.tools import tool
from sentence_transformers import CrossEncoder

# Init Database

import os
import sqlite3

DB = "memory.db"
reranker = CrossEncoder(
    "Qwen/Qwen3-Reranker-0.6B",
    prompts={
        "memory": "Determine whether the document contains information relevant to the user's query."
    },
    default_prompt_name="memory"
)

def initDb():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    conn.executescript("""
        CREATE TABLE episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            content TEXT NOT NULL,
            embedding BLOB
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            episode_id INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            role TEXT NOT NULL,
            content TEXT,
            FOREIGN KEY (episode_id) REFERENCES episodes(id)
        );
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            source_episode_id INTEGER,
            FOREIGN KEY (source_episode_id) REFERENCES episodes(id)
        );
        CREATE INDEX idx_episodes_user_id
        ON episodes(user_id);

        CREATE INDEX idx_messages_user_id
        ON messages(user_id);

        CREATE INDEX idx_messages_episode_id
        ON messages(episode_id);

        CREATE INDEX idx_memories_user_id
        ON memories(user_id);
    """)
    conn.commit()
    conn.close()

def cosineSimilarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    normA = math.sqrt(sum(x * x for x in a))
    normB = math.sqrt(sum(y * y for y in b))

    if normA == 0 or normB == 0:
        return 0

    return dot / (normA * normB)

def getEmbedding(text: str):
    response = ollama.embed(
        model="qwen3-embedding:0.6b",
        input=text
    )
    return response["embeddings"][0]

def addMemory(user_id: int, content: str, source_episode_id: int | None = None):
    embedding = getEmbedding(content)
    conn = sqlite3.connect(DB)
    conn.execute(
        """
        INSERT INTO memories
        (user_id, content, embedding, source_episode_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            content,
            json.dumps(embedding),
            source_episode_id
        )
    )
    conn.commit()
    conn.close()

def getTopEmbeddings(user_id: int, query: str, topK: int = 5):
    queryEmbedding = getEmbedding(query)
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """
        SELECT id, content, embedding
        FROM memories
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        id_, content, embedding = row
        memoryEmbedding = json.loads(embedding)
        similarity = cosineSimilarity(
            queryEmbedding,
            memoryEmbedding
        )
        results.append({
            "id": id_,
            "value": content,
            "score": similarity
        })
    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )
    return results[:topK]

def searchMemory(user_id: int, query: str, topK: int = 3, embTopK: int = 15):
    embTop = getTopEmbeddings(
        user_id,
        query,
        embTopK
    )
    documents = [
        memory["value"]
        for memory in embTop
    ]
    print("EmbTopK:\n", documents)
    scores = reranker.predict([
        (query, document)
        for document in documents
    ])
    sortedDocuments = sorted(
        zip(embTop, scores),
        key=lambda x: x[1],
        reverse=True
    )
    # print("Selected documents:")
    for memory, score in sortedDocuments[:topK]:
        print(score, memory["value"])
    return [
        memory["value"]
        for memory, score in sortedDocuments[:topK]
    ]

def extractMemories(episode: str) -> list[str]:
    prompt = f"""You are a memory extraction system.

    Your task is to extract durable information from an episode that should be
    preserved after the episode is no longer available.

    WHAT IS A MEMORY?

    A memory is a short, concise, self-contained statement about the user,
    the user's projects, decisions, preferences, work environment, or other
    durable information that may be useful in a future interaction.

    A memory must stand on its own.

    SELF-CONTAINED REQUIREMENT:

    Imagine that someone reads the memory months later without having access
    to the original episode. They must be able to understand:
    - who or what the memory refers to,
    - what the relevant fact is,
    - and why the information could be useful.

    Do not use vague subjects such as:
    - "the project"
    - "the system"
    - "the agent"
    - "it"
    - "this"
    - "the user"
    when the subject can be stated explicitly.

    Prefer:
    "The user's AI personal assistant uses LangGraph for agent orchestration."

    Instead of:
    "Uses LangGraph for orchestration."

    Prefer:
    "The user's AI personal assistant stores episodes and memories in SQLite."

    Instead of:
    "Uses SQLite for memory and conversation episodes."

    WHAT SHOULD BE REMEMBERED:

    Extract information about:
    - The user's persistent preferences or ways of working.
    - The user's projects and their important characteristics.
    - Important technical or architectural decisions.
    - Important project goals or requirements that are likely to remain relevant.
    - The user's work environment, configurations, or resources.
    - Important file or project paths.
    - Other durable information that could meaningfully help future interactions.

    WHAT SHOULD NOT BE REMEMBERED:

    Do NOT extract:
    - Questions asked during the episode.
    - Temporary tasks or TODO items.
    - Problems currently being debugged.
    - Implementation steps that have not become durable decisions.
    - Explanations or reasoning from the episode.
    - Temporary project status.
    - Facts that are only useful for understanding the current episode.
    - Trivial details.
    - Predictions or assumptions.
    - Information that is already implied by another memory.

    For example, these are NOT memories:
    "Need to implement memory persistence."
    "Need to add validation nodes."
    "Project is in early development."
    "Main.py needs to be converted into a reusable application."

    These describe temporary work or the current state of an episode.

    These ARE memories:
    "The user's AI personal assistant uses LangGraph for agent orchestration."
    "The user's AI personal assistant stores episodes and memories in SQLite."
    "The user prefers local-first architectures for privacy and data control."

    IMPORTANT:

    Do not summarize the episode.

    Do not turn every fact from the episode into a memory.

    Extract only information that deserves to survive after the episode is forgotten.

    Each memory should ideally contain 10-15 words, while preserving clarity
    and completeness.

    Return ONLY a list of memory strings.

    If the episode contains no durable information worth preserving, return [].
    
    Input text: 
    {episode}"""
    response = ollama.chat("qwen3.5:2b", messages=[
                {"role": "user", "content": prompt}
            ],
            think=False)
    print(response.message.content)


# print(searchMemory("Hola, podrías resumir el clima"))

if __name__ == "__main__":
    memories = extractMemories("""{
  "content": "El resumen actualizado del contenido de `Readme.md` es el siguiente:

---

## 📄 Resumen de Readme.md

### **Objetivo del Proyecto**
Desarrollar un agente de IA personal robusto que funcione correctamente en al menos el **80 %** de los casos, capaz de:
1. Entender instrucciones del usuario
2. Planificar herramientas necesarias
3. Ejecutar acciones
4. Observar resultados y decidir siguientes pasos

### **Arquitectura Técnica**
- **Orquestación:** LangGraph (`StateGraph`)
- **Modelo activo:** `ChatOpenAI` con OpenRouter (`openrouter/free`, `temperature=0`)
- **Memoria:** SQLite para memoria y episodios de conversación
- **Principio:** Local-first / privacy-first (aunque depende de servicios externos)

### **Componentes Principales**
| Componente | Descripción |
|------------|-------------|
| **Estado** | Contiene mensajes, recuerdos y episodio actual |
| **Herramientas** | TV, archivos, tiempo, memoria, correo, clima, búsqueda web, etc. |
| **Modelo** | Carga `.env` con `OPENAI_API_KEY`, vincula herramientas vía `bind_tools()` |
| **Entorno** | Obtiene zona horaria, ubicación (ipwho.is) y hora actual |
| **Nodos** | `agent` (LLM), `tools` (ejecución), `shouldContinue` (decisión de flujo) |

### **Flujo de Ejecución**
```
START → loadEpisode → loadMemories → agent
    ├─ con tool_calls → tools → agent
    └─ sin tool_calls → saveMessages → END
```

### **Herramientas Disponibles**
- 📺 Control: `tvController`
- 🤖 IA: `delegateToAI`
- 📁 Archivos: `listFiles`, `readFile`, `findFiles`, `overwriteFile`, `createDirectory`, `moveFile`
- ⏰ Tiempo: `getCurrentTimeTool`, `addTime`, `substractTime`, `timeDiff`
- 💾 Memoria: `searchMemory`
- 📧 Correo: `getEmails`, `deleteEmail`, `readEmail`
- 🌤️ Clima: `getCurrentWeather`, `getWeatherAt`, `getWeatherBetween`
- 🔍 Búsqueda: `DuckDuckGoSearchRun`
- 📅 Scheduler: Importado pero no activo

### **Estado del Proyecto**
| Fase | Estado |
|------|--------|
| Núcleo LangGraph y herramientas | 🟡 Parcialmente completado |
| Memoria SQLite y episodios | 🟡 Implementación parcial |
| Capacidades locales | 🟡 Herramientas disponibles, integración pendiente |
| Integraciones externas | 🟡 Implementadas de forma aislada |
| Scheduler | ⏳ Importado, no activo |
| Delegación avanzada | ⏳ Pendiente |

### **Limitaciones Actuales**
- Código placeholder en `understandTask()` y `checkTaskComplete()`
- No existe nodo explícito para comprobar cumplimiento de tarea
- `loadEpisode()` puede devolver `None` (incompatible con el siguiente nodo)
- `addMemory()` importado pero no registrado
- Ejecución ligada a solicitud concreta en `main.py` (no reutilizable)
- Herramientas externas no devuelven JSON estructurado uniformemente
- Operaciones sensibles sin esquema uniforme de permisos/confirmación
- Dependencias externas (ubicación, modelo activo) con implicaciones de privacidad
- Falta capa común de validación y manejo de errores

### **Seguridad**
Necesita implementar:
- Confirmación explícita para acciones irreversibles/alto riesgo
- Listas blancas de archivos, cuentas, dispositivos y dominios
- Mínimos privilegios por herramienta
- Protección de claves y datos personales
- Validación de respuestas antes de ejecutar acciones
- Registros de auditoría para operaciones sensibles

### **Próximos Pasos**
1. Convertir `main.py` en aplicación reutilizable y parametrizable
2. Completar persistencia de memoria y episodios en SQLite
3. Registrar `addMemory` y el scheduler en el grafo
4. Añadir nodo explícito de validación y conclusión
5. Unificar formato de respuesta JSON estructurado para todas las herramientas
6. Añadir permisos y confirmaciones antes de modificar archivos, borrar correos o controlar dispositivos
7. Evaluar opción local para reducir dependencias externas

---

*Última actualización: 17 de septiembre de 2026*""")
    # print(cosineSimilarity(getEmbedding("Busca recetas de cocina en internet"), getEmbedding("Me gustaría preparar la número 5")))
    # print(getTopEmbeddings("Hola"))
    # print(searchMemory("¿Qué herramientas utilizo para mi agente?"))
    # memories = [
    #     # Proyectos
    #     "El usuario desarrolla un agente de IA utilizando LangGraph.",
    #     "El usuario utiliza Python para desarrollar agentes de IA.",
    #     "El usuario utiliza Ollama para ejecutar modelos de IA localmente.",
    #     "El proyecto Modular Robot GUI and firmware se encuentra en E:/Proyectos/Modular Robot.",
    #     "El proyecto Boat Rental Management System es una aplicación web para gestionar el alquiler de embarcaciones.",
    #     "El usuario utiliza React para desarrollar interfaces web.",

    #     # Hardware y robótica
    #     "El usuario utiliza un Ryzen 5 Pro 4650G en su computadora principal.",
    #     "El usuario utiliza 16 GB de memoria RAM DDR4.",
    #     "El usuario utiliza una GPU RTX 5060 para ejecutar modelos de IA localmente.",
    #     "El usuario utiliza un ESP32 para controlar proyectos de robótica.",
    #     "El robot del usuario utiliza servomotores MG90S.",
    #     "El usuario utiliza Windows como sistema operativo principal.",

    #     # Conocimientos
    #     "El usuario tiene conocimientos de Python.",
    #     "El usuario tiene conocimientos de C y C++.",
    #     "El usuario tiene conocimientos de JavaScript.",
    #     "El usuario tiene conocimientos de React.",
    #     "El usuario tiene conocimientos básicos de MATLAB.",
    #     "El usuario está aprendiendo SQL para trabajar con bases de datos.",

    #     # Preferencias y arquitectura de IA
    #     "El usuario prefiere modelos de IA locales para mantener la privacidad de sus datos.",
    #     "El usuario prefiere utilizar herramientas estructuradas en lugar de prompts excesivamente restrictivos.",
    #     "El usuario prefiere arquitecturas de agentes con un modelo principal y modelos especializados.",
    #     "El usuario utiliza modelos pequeños para tareas de clasificación y extracción.",
    #     "El usuario utiliza modelos más grandes para razonamiento y ejecución de herramientas.",

    #     # Desarrollo y trabajo
    #     "El usuario estudia Ingeniería en Robótica.",
    #     "El usuario busca oportunidades laborales relacionadas con tecnología.",
    #     "El usuario ha desarrollado una aplicación de gestión para un negocio de alquiler de embarcaciones.",
    #     "El usuario utiliza FastAPI para desarrollar APIs.",
    #     "El usuario utiliza Tailwind CSS para desarrollar interfaces web.",

    #     # Otros
    #     "El usuario reside en Guadalajara, Jalisco, México.",
    #     "El usuario utiliza español como idioma principal.",
    #     "El usuario utiliza Gmail para gestionar su correo electrónico.",
    #     "El usuario utiliza un decodificador XView para consumir televisión.",
    #     "El usuario utiliza Google Cast para controlar dispositivos multimedia.",
    # ]

    # for memory in memories:
    #     addMemory(1, memory)
    # initDb()

    # addMemory(
    #     1,
    #     "El usuario reside en Guadalajara, Jalisco, México."
    # )

    # addMemory(
    #     1,
    #     "El agente de IA utiliza Ollama para ejecutar modelos locales."
    # )

    # addMemory(
    #     1,
    #     "El usuario cuenta con una PC AM4, 32gb de RAM DDR4, SSD SATA 256gb y Ryzen 5 4650g."
    # )

    # addMemory(
    #     1,
    #     "El usuario tiene conocimientos avanzados de ReactJS."
    # )

    # print("Memorias agregadas correctamente.")

    # conn = sqlite3.connect(DB)

    # # 1. Execute the query and fetch all matching rows
    # rows = conn.execute(""" SELECT * FROM memories """).fetchall()

    # # 2. Iterate through and print each row
    # for row in rows:
    #     print(row)

    # conn.close()