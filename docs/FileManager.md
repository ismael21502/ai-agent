# Documentación del FileManager

Este documento describe las funciones y operaciones disponibles en el módulo `fileManager.py`.

## Función Principal: `fileManager`

```python
@tool
def fileManager(operation: str, path: str, content: str = "", query: str = "") -> dict:
```

Administra archivos y directorios proporcionando operaciones básicas de sistema de archivos.

### Parámetros

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `operation` | `str` | Operación a realizar: `list`, `read`, `write`, `find` o `mkdir` |
| `path` | `str` | Ruta relativa al archivo o directorio |
| `content` | `str` | Contenido que se escribirá cuando `operation` sea `write` (opcional, default: "") |
| `query` | `str` | Consulta utilizada cuando `operation` es `find` (opcional, default: "") |

### Operaciones Disponibles

#### 1. `list` - Listar contenido de directorio
Lista los archivos y carpetas de un directorio especificado.

**Parámetros:**
- `operation`: "list"
- `path`: Ruta del directorio a listar

**Resultado exitoso:**
```json
{
  "success": true,
  "operation": "list",
  "path": "/ruta/del/directorio",
  "result": [
    {
      "name": "archivo.txt",
      "path": "/ruta/completa/archivo.txt",
      "type": "file"
    },
    {
      "name": "carpeta",
      "path": "/ruta/completa/carpeta",
      "type": "directory"
    }
  ]
}
```

#### 2. `read` - Leer archivo
Lee el contenido completo de un archivo de texto.

**Parámetros:**
- `operation`: "read"
- `path`: Ruta del archivo a leer

**Resultado exitoso:**
```json
{
  "success": true,
  "operation": "read",
  "path": "/ruta/del/archivo.txt",
  "result": "Contenido del archivo..."
}
```

#### 3. `write` - Escribir archivo
Sobreescribe un archivo existente o crea uno nuevo con el contenido especificado.

**Parámetros:**
- `operation`: "write"
- `path`: Ruta del archivo a escribir
- `content`: Contenido a escribir en el archivo

**Resultado exitoso:**
```json
{
  "success": true,
  "operation": "write",
  "path": "/ruta/del/archivo.txt",
  "result": "File written successfully."
}
```

#### 4. `find` - Buscar archivos
Búsqueda recursiva de archivos que coincidan con el nombre especificado.

**Parámetros:**
- `operation`: "find"
- `path`: Directorio raíz donde iniciar la búsqueda
- `query`: Nombre del archivo a buscar

**Resultado exitoso:**
```json
{
  "success": true,
  "operation": "find",
  "path": "/directorio/raiz",
  "result": {
    "query": "archivo.txt",
    "results": [
      {
        "name": "archivo.txt",
        "path": "/directorio/raiz/subcarpeta/archivo.txt",
        "type": "file"
      }
    ],
    "count": 1,
    "truncated": false
  }
}
```

**Nota:** La búsqueda está limitada a `MAX_FIND_RESULTS` (20) resultados e ignora directorios comunes como `.git`, `__pycache__`, `node_modules`, etc.

#### 5. `mkdir` - Crear directorio
Crea una nueva carpeta en la ruta especificada, incluyendo directorios padre si es necesario.

**Parámetros:**
- `operation`: "mkdir"
- `path`: Ruta del directorio a crear

**Resultado exitoso:**
```json
{
  "success": true,
  "operation": "mkdir",
  "path": "/ruta/nueva/carpeta",
  "result": "Directory created successfully."
}
```

### Estructura de Respuesta

Todas las operaciones devuelven un diccionario con la siguiente estructura:

**Éxito:**
```json
{
  "success": true,
  "operation": "nombre_operacion",
  "path": "ruta_utilizada",
  "result": "resultado_especifico_de_la_operacion"
}
```

**Error:**
```json
{
  "success": false,
  "operation": "nombre_operacion",
  "path": "ruta_utilizada",
  "error": {
    "type": "tipo_error",
    "message": "mensaje_descriptivo",
    "suggestion": "sugerencia_para_resolver"
  }
}
```

### Tipos de Error

| Tipo | Descripción | Sugerencia típica |
|------|-------------|-------------------|
| `path_not_found` | Archivo o directorio no encontrado | Use find cuando la ubicación del archivo sea desconocida, o list cuando conozca el directorio |
| `permission_denied` | Permiso denegado | Verifique si la ruta es accesible |
| `is_a_directory` | La ruta es un directorio, no un archivo | Use list para inspeccionar el contenido del directorio |
| `not_a_directory` | La ruta no es un directorio | Use list para inspeccionar la estructura del directorio |
| `decode_error` | Error de decodificación (archivo binario o codificación diferente) | El archivo puede ser binario o usar una codificación de texto diferente |
| `os_error` | Error del sistema operativo | Verifique la ruta e intente de nuevo |
| `unknown_error` | Error no clasificado | Verifique la ruta e intente de nuevo |

### Constantes Importantes

- `MAX_FIND_RESULTS = 20`: Límite máximo de resultados en búsquedas `find`
- `IGNORED_DIRS`: Conjunto de directorios ignorados durante búsquedas recursivas (`.git`, `__pycache__`, `node_modules`, `venv`, `env`, etc.)

### Ejemplos de Uso

```python
# Listar directorio actual
fileManager("list", ".")

# Leer un archivo
fileManager("read", "docs/ejemplo.md")

# Escribir un archivo
fileManager("write", "nuevo_archivo.txt", "Hola mundo")

# Buscar un archivo
fileManager("find", ".", query="config.json")

# Crear directorio
fileManager("mkdir", "nueva/carpeta/anidada")
```

---
*Documentación generada automáticamente desde `BuiltInTools/fileManager.py`*