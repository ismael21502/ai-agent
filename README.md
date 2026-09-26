# AI Personal Assistant

## Objetivo

Desarrollar un agente de IA personal robusto que funcione correctamente en al menos el **80 %** de los casos. El agente debe:

1. Entender la instrucción del usuario.
2. Planificar qué herramientas necesita.
3. Ejecutar las acciones seleccionadas.
4. Observar los resultados y decidir si la tarea está completa, se necesita información adicional o se debe cambiar el enfoque.

## Arquitectura y tecnología

- **Orquestación:** LangGraph (`StateGraph`).
- **Modelo activo:** `ChatOllama` con `qwen3.6:35b-a3b`, `temperature=0` y `num_ctx=65536`.
- **Modelos alternativos:** `ChatOpenAI` con OpenRouter (`openrouter/free`) y Groq aparecen como ejemplos comentados.
- **Memoria y contexto:** módulos de SQLite para memoria episódica y recuperación semántica.
- **Principio de diseño:** local-first / privacy-first, aunque actualmente algunas capacidades dependen de servicios externos (ipwho.is, OpenRouter/Groq).

## Resumen de `main.py`

`main.py` configura y ejecuta directamente el grafo del agente con un trazado detallado al final.

### Componentes principales

- **Estado:** `State` contiene mensajes (`Annotated[list[AnyMessage], add_messages]`), recuerdos (`memories`) y episodio actual (`currentEpisode`).
- **Herramientas vinculadas:** `tvController`, `DuckDuckGoSearchRun`, `delegateToAI`, gestor de archivos (`listFiles`, `readFile`, `findFiles`, `overwriteFile`, `createDirectory`, `moveFile`), funciones de tiempo (`getCurrentTimeTool`, `addTime`, `substractTime`, `timeDiff`), correo (`getEmails`, `deleteEmail`, `readEmail`) y clima (`getCurrentWeather`, `getWeatherAt`, `getWeatherBetween`).
- **Modelo:** se carga `.env` y se inicializa `ChatOllama`. Las herramientas se vinculan al modelo mediante `bind_tools()`.
- **Entorno:** `getEnvironment()` obtiene la zona horaria, la ubicación aproximada mediante `ipwho.is` y la hora actual. Se inyecta como `SystemMessage` en cada iteración.
- **Nodo `agent`:** construye el contexto del sistema (entorno, recuerdos relevantes, resumen del episodio anterior) e invoca al modelo.
- **Nodo `tools`:** `ToolNode` ejecuta las herramientas solicitadas por el modelo y devuelve los resultados al agente.
- **Carga de contexto:** `loadEpisode()` comprueba la relevancia del episodio anterior para decidir si se reutiliza o se cierra (guardando sus memorias). `loadMemories()` busca recuerdos relacionados con el primer mensaje del usuario.
- **Persistencia:** `saveMessages()` guarda los mensajes en SQLite. `saveEpisode()` serializa y almacena/actualiza el episodio de conversación.
- **Enrutamiento:** `shouldContinue()` decide si el agente debe volver al nodo de herramientas (`tools`) o guardar los mensajes y finalizar (`saveMessages`).
- **Trazado detallado:** la función `print_result()` imprime estadísticas completas: tokens (input/output), tiempos de carga/procesamiento/generación, TPS, llamadas a herramientas y advertencias sobre respuestas vacías.

## Flujo de ejecución

```text
START
  → loadEpisode
  → loadMemories
  → agent
      ├─ con tool_calls → tools → agent (ciclo)
      └─ sin tool_calls → saveMessages → saveEpisode → END
```

El ciclo se repite mientras el modelo siga solicitando herramientas. Al finalizar, se guarda el episodio y se imprime el trazado.

## Herramientas disponibles

| Categoría | Herramientas |
|---|---|
| Control de dispositivos | `tvController` |
| Selección de modelo | `delegateToAI` |
| Sistema de archivos | `listFiles`, `readFile`, `findFiles`, `overwriteFile`, `createDirectory`, `moveFile` |
| Tiempo | `getCurrentTimeTool`, `addTime`, `substractTime`, `timeDiff` |
| Correo | `getEmails`, `deleteEmail`, `readEmail` |
| Clima | `getCurrentWeather`, `getWeatherAt`, `getWeatherBetween` |
| Búsqueda web | `DuckDuckGoSearchRun` |
| Ubicación | `getLocation()` (mediante `ipwho.is`) |

> **Nota:** `addMemory`, `searchMemory` y `extractMemories` se usan internamente en los nodos de carga/guardado de contexto, pero no están registrados como herramientas ejecutables por el modelo.

## Estado del proyecto

| Fase | Estado |
|---|---|
| Núcleo LangGraph y herramientas | 🟢 Funcional |
| Memoria SQLite y episodios | 🟡 Implementación parcial (persistencia operativa, recuperación semántica en mejora) |
| Capacidades locales | 🟢 Herramientas disponibles y vinculadas |
| Integraciones externas | 🟢 Implementadas (TV, correo, clima, búsqueda, ubicación IP) |
| Delegación avanzada | 🟢 `delegateToAI` operativo |

## Limitaciones actuales

- `addMemory` no está registrado en la lista de herramientas del grafo; solo se usa internamente.
- La ejecución está ligada a una solicitud concreta al final de `main.py`; no funciona todavía como una interfaz reutilizable o servidor.
- Las herramientas externas no necesariamente devuelven JSON estructurado uniforme.
- Las operaciones sensibles no tienen todavía un esquema uniforme de permisos y confirmación.
- `getLocation()` envía información a servicios externos (`ipwho.is`), lo que debe revisarse desde el punto de vista de privacidad.
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

1. Convertir `main.py` en una aplicación reutilizable (CLI o API FastAPI).
2. Completar la persistencia de memoria y episodios en SQLite.
3. Registrar `addMemory` como herramienta si se requiere ejecución directa por el agente.
4. Añadir un nodo explícito de validación y conclusión de tareas.
5. Unificar el formato de respuesta de todas las herramientas en JSON estructurado.
6. Añadir permisos y confirmaciones antes de modificar archivos, borrar correos o controlar dispositivos.
7. Evaluar una opción local para `getLocation()` y reducir dependencias externas.

---

*Última actualización: 24 de septiembre de 2026*
