import ollama
import math
import sqlite3
import json
from langchain_core.tools import tool
from sentence_transformers import CrossEncoder
from pydantic import BaseModel

import os
import sqlite3
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "Qwen3-Reranker-0.6B"

# TODO: Ahora la estructura de lo que genera el LLM es: {entity: str, memories: list[str]}.
# Para permitir múltiples entities podría cambiar a {entity_1: list[str], entity_2: list[str], ...}
DB = "memory.db"
reranker = CrossEncoder(
    str(MODEL_PATH),
    # "Qwen/Qwen3-Reranker-0.6B",
    prompts={
        "memory": "Determine whether the document contains information relevant to the user's query."
    },
    default_prompt_name="memory"
)
class MemoryExtraction(BaseModel):
    entity: str
    memories: list[str]
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
    Extract durable information from the provided episode.
    Return:
    - one entity that the memories belong to;
    - a list of durable factual statements about that entity.
    The entity must be derived only from the provided episode.
    The entity is the subject described by the extracted memories.
    It is not the document, file, message, or source containing those memories.
    The entity must identify the specific system, project, person, object, or concept
    to which the memories belong. Avoid vague entities.
    Only extract information that represents a stable characteristic, decision,
    preference, requirement, architecture, or other durable knowledge.
    Do not extract the current status of implementation, completion, bugs,
    missing features, pending work, temporary dependencies, or other transient
    project state.
    Each memory must:
    - be understandable when combined with the entity;
    - express one clear factual statement;
    - be supported by information in the episode;
    - contain only the information necessary to state the fact clearly;
    - be concise, between 10 and 20 words.
    The memory itself does not need to repeat the entity.
    Only use information contained in the provided episode.
    Do not use previous conversations, other projects, examples, or outside knowledge.
    Do not extract:
    - temporary implementation state;
    - TODOs or pending work;
    - current bugs or transient problems;
    - explanations, reasoning, or conclusions that are only relevant to the episode;
    - information that is unlikely to remain useful.
    Do not summarize the episode.
    Do not create multiple memories expressing substantially the same fact.
    If the episode contains no durable information worth remembering, return an empty
    memories list.
    Episode:
    {episode}"""
    response = ollama.chat("qwen3.5:2b", messages=[
                {"role": "user", "content": prompt}
            ],
            format=MemoryExtraction.model_json_schema(),
            options={
                "temperature": 0
            },
            think=False)
    result = MemoryExtraction.model_validate_json(
        response.message.content
    )
    newMemories = [f"{result.entity}: {memory}" for memory in result.memories]
    return newMemories

# print(searchMemory("Hola, podrías resumir el clima"))

if __name__ == "__main__":
    # memories = print(extractMemories("""{
    # "Temperaturas: "
    # " - Mínima: ~16.5°C (al amanecer, alrededor de las 6 AM) "
    # " - Máxima: ~29.0°C (a las 4 PM) "

    # "Condiciones generales: "
    # " - Precipitación: No se esperan lluvias (0 mm), con una probabilidad muy baja de lluvia (0-4%). "
    # " - Humedad: Varía entre un 26% y un 98%, siendo más alta durante la noche y el amanecer. "
    # " - Nubes: La cobertura nubosa fluctuará, con cielos mayormente despejados por la mañana y nublado en algunas horas de la tarde/noche. "
    # " - Viento: Velocidades moderadas entre 1.1 y 10.3 km/h. "

    # "En resumen: Será un día soleado y cálido durante el día, con temperaturas agradables para la noche. No hay riesgo de lluvia."
    # }"""))

    conn = sqlite3.connect(DB)

    # 1. Execute the query and fetch all matching rows
    rows = conn.execute(""" SELECT * FROM memories """).fetchall()

    # 2. Iterate through and print each row
    for row in rows:
        print(f"User_ID: {row[1]}, Episode_ID: {row[6]}, Content: {row[2]}")

    conn.close()