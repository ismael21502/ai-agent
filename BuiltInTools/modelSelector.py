import ollama
# from smolagents import tool
from langchain_core.tools import tool

@tool
def delegateToAI(role: str, prompt: str) -> str: #Cambiar el return a dict con info?
    """
    Allows to delegate a task to a specific AI model based on the role provided. 
    The function allows to send a prompt to the selected model and returns the generated message.

    Args:
        role: A string indicating the role of the AI model to delegate the task to. Possible values are: 
        - writer: Expert writer for creative or large texts (poems, stories, essays, etc.) 
        - coder: Expert coder for programming tasks
        prompt: Prompt string to send to the selected AI model.
    
    Returns:
        A string containing the generated message from the selected AI model.
    """
    ROLES = {
        "writer": {
            "model": "qwen3:1.7b",
            "think": False,
        },
        "coder": {
            "model": "qwen3:1.7b",
            "think": False,
        }
    }
    selectedRole = ROLES[role]
    response = ollama.chat(
        model=selectedRole["model"],
        messages=[
            {"role": "user", "content": prompt}
        ],
        think=selectedRole["think"]
    )
    prompt_tps = (
    response["prompt_eval_count"] /
        (response["prompt_eval_duration"] / 1e9)
    )

    eval_tps = (
        response["eval_count"] /
        (response["eval_duration"] / 1e9)
    )

    print(f"Prompt: {prompt_tps:.2f} tok/s")
    print(f"Generation: {eval_tps:.2f} tok/s")

    return response.message.content
