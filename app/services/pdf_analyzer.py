import json
import re
import time
import logging
import tempfile
import os
import unicodedata
from datetime import datetime, timezone

from google import genai
from google.genai import types as genai_types

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ANALYSIS_PROMPT = """
Analiza este documento legal mexicano y extrae la siguiente información en formato JSON:

1. **title**: Título breve del documento (máximo 100 caracteres)
   Ejemplo: "Reglamento de Tránsito Jalisco"

2. **description**: Descripción concisa del contenido (1-2 oraciones)
   Ejemplo: "Regulación de tránsito terrestre, derechos de conductores, tabulador de infracciones"

3. **type_name**: Tipo de documento. Valores permitidos:
   - "Constitución Política del Estado"
   - "Ley de Movilidad y Transporte"
   - "Reglamento de Tránsito"
   - "Reglamento de Corralón"
   - "Reglamento de Guardianes Viales"
   - "Gaceta Municipal"
   - "Otro" (si no encaja en las categorías anteriores)

4. **level**: Nivel del documento
   - "estatal" (aplica a todo el estado)
   - "municipal" (aplica a municipios específicos)

5. **municipalities**: Si el nivel es "municipal", lista de nombres de los municipios a los que aplica. Si es "estatal", devuelve una lista vacía [].
   Ejemplo: ["Guadalajara", "Zapopan"]

6. **confidence**: Nivel de confianza en la detección (0-100)

Responde ÚNICAMENTE con el JSON, sin texto adicional:
{
    "title": "...",
    "description": "...",
    "type_name": "...",
    "level": "estatal",
    "municipalities": [],
    "confidence": 85
}
"""


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    return text

def fuzzy_match_municipalities(extracted: list[str], state: str) -> list[str]:
    if not extracted or not state:
        return extracted
        
    try:
        catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "municipalities.json")
        with open(catalog_path, "r") as f:
            catalog = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load municipalities catalog: {e}")
        return extracted
        
    norm_state = normalize_text(state.replace("_", " "))
    state_municipalities = []
    for k, v in catalog.items():
        if normalize_text(k) == norm_state:
            state_municipalities = v
            break
            
    if not state_municipalities:
        return extracted
        
    matched = []
    for ext in extracted:
        norm_ext = normalize_text(ext)
        best_match = ext
        for m in state_municipalities:
            if normalize_text(m) == norm_ext:
                best_match = m
                break
        matched.append(best_match)
        
    return matched

def analyze_pdf(pdf_content: bytes, filename: str, state: str = None) -> dict:
    """
    Analiza un PDF usando Gemini y extrae metadatos.
    Retorna: {title, description, type_name, level, municipalities, confidence}
    """
    tmp_path = None
    try:
        logger.info(f"Analyzing PDF: {filename} ({len(pdf_content)} bytes)")
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = tmp_file.name

        uploaded_file = client.files.upload(file=tmp_path)
        logger.info(f"Uploaded to Gemini: {uploaded_file.name}, state: {uploaded_file.state}")

        for i in range(30):
            if uploaded_file.state == "ACTIVE":
                logger.info(f"Gemini file active after {i*2}s")
                break
            if uploaded_file.state == "FAILED":
                raise Exception(f"Gemini file processing failed: {uploaded_file.name}")
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state != "ACTIVE":
            raise Exception(f"Gemini file not active after timeout: {uploaded_file.state}")

        model_name = "gemini-2.5-flash-lite" if settings.ENVIRONMENT in ["DEV", "LOCAL"] else "gemini-2.5-flash"

        response = client.models.generate_content(
            model=model_name,
            contents=[
                genai_types.Content(
                    parts=[
                        genai_types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type=uploaded_file.mime_type,
                        ),
                        genai_types.Part.from_text(text=ANALYSIS_PROMPT),
                    ]
                )
            ],
        )

        client.files.delete(name=uploaded_file.name)

        raw_text = response.text
        if not raw_text:
            logger.warning(f"Gemini returned empty response for {filename}")
            return _fallback_analysis(filename)

        raw_text = raw_text.strip()
        logger.info(f"Gemini response: {raw_text[:200]}...")

        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        result = json.loads(raw_text)

        required_keys = {"title", "description", "type_name", "level", "confidence"}
        if not required_keys.issubset(result.keys()):
            raise Exception(f"Missing keys in Gemini response: {result.keys()}")

        if "municipalities" not in result or not isinstance(result["municipalities"], list):
            result["municipalities"] = []
            
        if state and result["level"] == "municipal" and result["municipalities"]:
            result["municipalities"] = fuzzy_match_municipalities(result["municipalities"], state)

        logger.info(f"Gemini analysis complete: confidence={result.get('confidence', 0)}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Error parsing Gemini JSON for {filename}: {e}")
        return _fallback_analysis(filename)
    except Exception as e:
        logger.error(f"Error analyzing PDF with Gemini for {filename}: {type(e).__name__}: {e}")
        return _fallback_analysis(filename)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _fallback_analysis(filename: str) -> dict:
    """Fallback cuando Gemini no puede analizar el PDF."""
    clean_name = filename.replace(".pdf", "").replace("_", " ").replace("-", " ")
    return {
        "title": clean_name.title(),
        "description": "",
        "type_name": "Otro",
        "level": "estatal",
        "municipalities": [],
        "confidence": 0,
    }


def generate_type_id(name: str, state: str) -> str:
    """Genera ID del tipo desde el nombre"""
    normalized = name.lower().strip()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized)
    return f"{normalized}_{state}"


def log_gemini_correction(filename: str, gemini_result: dict, corrections: dict):
    """Registra cuando el admin corrige la detección de Gemini."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "gemini_detected": gemini_result,
        "admin_corrections": corrections,
        "confidence": gemini_result.get("confidence", 0),
    }

    try:
        import os
        os.makedirs("logs", exist_ok=True)
        with open("logs/gemini_corrections.jsonl", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.warning(f"Error logging Gemini correction: {e}")
