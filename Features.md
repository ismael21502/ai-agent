Núcleo del agente
*Orquestador: interpreta la intención, planifica y decide qué acciones realizar.
*Sistema de tools: permite al agente interactuar con archivos, datos y servicios externos.
*Tools estructuradas: devuelven operación, estado/éxito, ruta, contenido, errores, etc., para reducir malas interpretaciones.
*Búsqueda de archivos recursiva: find() determinista, con exclusión de directorios irrelevantes como .git, node_modules, __pycache__, etc.
Memoria: almacenar información persistente del usuario y del funcionamiento del agente.
Base de datos: usar SQLite como almacenamiento local inicial del agente.
Scheduler: ejecutar/despertar al agente en una fecha u hora determinada.
**Delegación a modelos especializados: permitir que el orquestador llame a modelos más adecuados para escritura, análisis, programación, etc.
*Control de ejecución: saber cuándo continuar utilizando tools y cuándo terminar porque ya tiene suficiente información.
Confirmaciones/permisos: requerir aprobación para acciones sensibles o irreversibles.
Arquitectura local-first/privacy-first: minimizar la dependencia de servicios externos y mantener los datos bajo nuestro control.
*Darle funciones para manejar tiempo? 

Integraciones futuras
*Correo: leer, buscar, redactar y enviar emails.
Calendario: consultar y administrar eventos y citas.
Recordatorios: crear y administrar recordatorios temporales.
Domótica: controlar dispositivos y automatizaciones mediante Home Assistant.
TV/decodificador: controlar el XView mediante Google Cast/Home Assistant si resulta posible.
Ejercicio: consultar datos y generar planes de entrenamiento personalizados.
Alimentación: generar planes alimentarios y listas de compras a partir de recetas/datos nutricionales.
Gestión de compras: convertir planes o necesidades en listas de compras.
Archivos personales: buscar, leer, modificar y organizar documentos.
LinkedIn: mantenerlo como interacción manual, sin integración automática por ahora.
Servicios privados: explorar Proton/Nextcloud y alternativas a Google para correo, calendario y almacenamiento.

Flujo deseado del agente:
1. UNDERSTAND: ¿Qué quiere el usuario? ¿Qué se necesita para obtenerlo?
2. PLAN: Siguiente lote de acciones
3. EXECUTE: tool o llamada a un especialista
4. OBSERVE: observar y evaluar resultados
5.1 COMPLETE: Fin de la ejecución
5.2 NEED_INFO: Preguntar al usuario por más información -> PLAN
5.3 REPLAN -> PLAN

Ahora mismo seguiré con:
1. Delegación entre modelos (listo)
2. Scheduler básico
3. SQLite como almacenamiento
4. Memoria
5. Primera integración real