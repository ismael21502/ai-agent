# from smolagents import tool
from langchain_core.tools import tool
from pathlib import Path
    
@tool
def tvController(operation: str) -> dict:
    """Controla la TV mediante API
        Args:
            operation: Operación a realizar: turn_on, turn_off.
        Returns:
            Un diccionario con el resultado de la operación.
            Incluye:
                success: Indica si la operación fue exitosa.
                operation: Operación realizada.
                result: Resultado de la operación cuando es exitosa.
                error: Descripción del error si la operación falla."""
    if operation == "turn_on":
        print("Turning on")
        return {
            "success": True,
            "operation": operation,
            "path": None,
            "result": "TV turned on"
        }
    elif operation == "turn_off":
        return {
            "success": True,
            "operation": operation,
            "path": None,
            "result": "TV turned off"
        }