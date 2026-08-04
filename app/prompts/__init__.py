from app.prompts.transito import TRANSITO_PROMPT
from app.prompts.preventivo import PREVENTIVO_PROMPT


def get_prompt(official_type: str, state: str) -> str:
    if official_type == "transito":
        return TRANSITO_PROMPT.format(state=state)
    elif official_type == "preventivo":
        return PREVENTIVO_PROMPT.format(state=state)
    else:
        raise ValueError(f"Tipo de oficial no valido: {official_type}")


__all__ = ["get_prompt", "TRANSITO_PROMPT", "PREVENTIVO_PROMPT"]
