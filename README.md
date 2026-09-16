#AI personal assistant

Objetivo:
El agente debe funcionar al menos el 80% de las veces. 
Debe recibir una instrucción, decidir qué hacer y qué herramientas necesita, para luego utilizarlas, analizar su resultado y llegar a una conclusión.

Utilizaré ollama, tools propias hechas con python y smolagents.

Herramientas: 
El agente necesitará herramientas para:
CRUD de archivos, búscar en internet para investigar, interactuar con otras aplicaciones (reloj, calendario, etc.). Tal vez posteriormente podría intentar integrar aider u otros agentes similares.

Las herramientas deben devolver información estructurada en json. Debo encontrar la forma de combinar mi estructura propia con lo que pueda devolver una tool no hecha por mí mismo.

El agente debe comprobar el resultado de sus acciones para comprender si cumplió el objetivo o si por el contrario aún debe hacer más cosas o cambiar de enfoque.

Implementar un sistema de memoria utilizando sqlite, sql o alguna otra base de datos

Seguridad: 
Añadir permisos específicos para evitar que una alucinación del agente, un hackeo o un uso indebido terminen filtrando mis datos personales, inutilizando mi PC o haciendo compras en internet sin autorización.

