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



# print(searchMemory("Hola, podrías resumir el clima"))

if __name__ == "__main__":
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
    initDb()

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