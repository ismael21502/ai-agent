# AI Personal Assistant

## Objetivo

Desarrollar un agente de IA personal robusto que funcione correctamente en al menos el **80 %** de los casos. El agente debe:

1. Entender la instrucción del usuario.
2. Planificar qué herramientas necesita.
3. Ejecutar las acciones seleccionadas.
4. Observar los resultados y decidir si la tarea está completa, se necesita información adicional o se debe cambiar el enfoque.

## Arquitectura y tecnología

- **Orquestación:** LangGraph (`StateGraph`).
- **Modelo activo:** `ChatOpenAI` con OpenRouter (`openrouter/free`) y `temperature=0`.
- **Modelos alternativos:** Ollama y Groq aparecen como ejemplos comentados.
- **Memoria y contexto:** módulos de SQLite para memoria y episodios de conversación.
- **Principio de diseño:** local-first / privacy-first, aunque actualmente algunas capacidades dependen de servicios externos.

## Resumen de `main.py`

`main.py` configura y ejecuta directamente el grafo del agente.

### Componentes principales

- **Estado:** `State` contiene mensajes, recuerdos y episodio actual. `AgentState` fue definido para una futura clasificación de tareas, pero no se utiliza.
- **Herramientas:** se registra un conjunto de herramientas para TV, selección de modelo, archivos, tiempo, memoria, correo, clima, búsqueda, entrada del usuario y otros servicios.
- **Modelo:** se carga `.env` y se crea `ChatOpenAI` con la clave `OPENAI_API_KEY`. Las herramientas se vinculan al modelo mediante `bind_tools()`.
- **Entorno:** `getEnvironment()` obtiene la zona horaria, la ubicación aproximada mediante `ipwho.is` y la hora actual.
- **Nodo `agent`:** construye mensajes del sistema con el entorno, recuerdos relevantes y el resumen del episodio anterior; después invoca al modelo.
- **Nodo `tools`:** `ToolNode` ejecuta las herramientas solicitadas por el modelo.
- **Carga de contexto:** `loadEpisode()` comprueba la relevancia del episodio anterior y `loadMemories()` busca recuerdos relacionados con el primer mensaje del usuario.
- **Persistencia:** `saveMessages()` guarda los mensajes mediante `addMessage()`.
- **Enrutamiento:** `shouldContinue()` decide si el agente debe volver al nodo de herramientas o guardar los mensajes y terminar.
- **Ejecución automática:** al final del archivo se invoca el grafo con la solicitud actual y se imprime un trazado detallado del agente, llamadas LLM, herramientas y estadísticas.

## Flujo de ejecución

```text
START
  → loadEpisode
  → loadMemories
  → agent
      ├─ con tool_calls → tools → agent
      └─ sin tool_calls → saveMessages → END
```

El ciclo se repite mientras el modelo siga solicitando herramientas.

## Herramientas disponibles

| Categoría | Herramientas |
|---|---|
| Control de dispositivos | `tvController` |
| Selección de modelo | `delegateToAI` |
| Sistema de archivos | `listFiles`, `readFile`, `findFiles`, `overwriteFile`, `createDirectory`, `moveFile` |
| Tiempo | `getCurrentTimeTool`, `addTime`, `substractTime`, `timeDiff` |
| Memoria | `searchMemory` |
| Correo | `getEmails`, `deleteEmail`, `readEmail` |
| Clima | `getCurrentWeather`, `getWeatherAt`, `getWeatherBetween` |
| Búsqueda web | `DuckDuckGoSearchRun` |
| Entrada del usuario | `requestUserInput` |
| Scheduler | `Scheduler` (importado, pero aún no registrado como herramienta) |
| Ubicación | `getLocation()` (mediante `ipwho.is`) |

## Estado del proyecto

| Fase | Estado |
|---|---|
| Núcleo LangGraph y herramientas | 🟡 Parcialmente completado |
| Memoria SQLite y episodios | 🟡 Implementación parcial |
| Capacidades locales | 🟡 Herramientas disponibles, integración pendiente |
| Integraciones externas | 🟡 Implementadas de forma aislada |
| Scheduler | ⏳ Importado, no activo |
| Delegación avanzada y trabajos largos | ⏳ Pendiente |

## Limitaciones actuales

- `understandTask()` y `checkTaskComplete()` contienen código placeholder y no forman parte del grafo.
- No existe todavía un nodo explícito para comprobar el cumplimiento de la tarea.
- `loadEpisode()` puede devolver `None`, mientras que el siguiente nodo espera un diccionario de estado.
- `addMemory()` está importado, pero no se registra en la lista de herramientas.
- La ejecución está ligada a una solicitud concreta al final de `main.py`; no funciona todavía como una interfaz reutilizable.
- Las herramientas externas no necesariamente devuelven JSON estructurado.
- Las operaciones sensibles no tienen todavía un esquema uniforme de permisos y confirmación.
- `getLocation()` y el modelo activo envían información a servicios externos, lo que debe revisarse desde el punto de vista de privacidad.
- Falta una capa común de validación y manejo de errores para todas las herramientas.

## Seguridad

Se debe implementar un esquema de permisos con:

- Confirmación explícita para acciones irreversibles o de alto riesgo.
- Listas blancas de archivos, cuentas, dispositivos y dominios.
- Mínimos privilegios para cada herramienta.
- Protección de claves y datos personales.
- Validación de respuestas antes de ejecutar una acción.
- Registros de auditoría para operaciones sensibles.

Las credenciales deben mantenerse en un archivo `.env` excluido del repositorio. No se debe asumir que las credenciales expuestas en `secrets.md` han sido migradas hasta comprobarlo y eliminar el archivo inseguro.

## Próximos pasos

1. Convertir `main.py` en una aplicación reutilizable y parametrizable.
2. Completar la persistencia de memoria y episodios en SQLite.
3. Registrar `addMemory` y el scheduler en el grafo.
4. Añadir un nodo explícito de validación y conclusión.
5. Unificar el formato de respuesta de todas las herramientas en JSON estructurado.
6. Añadir permisos y confirmaciones antes de modificar archivos, borrar correos o controlar dispositivos.
7. Evaluar una opción local para reducir las dependencias externas.

---

*Última actualización: 17 de septiembre de 2026*
