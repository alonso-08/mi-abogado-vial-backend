import json
import pytest
from app.services import rag
from google import genai
from app.config import get_settings

settings = get_settings()
client = genai.Client(api_key=settings.GEMINI_API_KEY)

SCENARIOS = [
    {
        "name": "Multa_Copiloto",
        "question": "Me acaban de detener en Jalisco porque mi copiloto venía usando su celular y el oficial dice que es motivo de multa. ¿Es cierto eso? Dime qué artículo dice la verdad y de cuánto es la multa.",
        "expected_behavior": "La IA debe aclarar que la ley penaliza al conductor por usar el teléfono, no al copiloto. Debe indicar que la multa no procede para el copiloto."
    },
    {
        "name": "Grua_Linea_Amarilla",
        "question": "Dejé mi carro estacionado afuera de mi casa, pero la llanta trasera pisaba la línea amarilla de la esquina por unos centímetros. Llegó la grúa y se lo quieren llevar. Estoy presente y tengo mis llaves. ¿Tienen derecho a llevárselo o solo deben multarme?",
        "expected_behavior": "La IA debe explicar que si el conductor está presente y dispuesto a mover el vehículo antes de que se inicie el arrastre, solo procede la multa y no el remolque."
    },
    {
        "name": "Licencia_Digital",
        "question": "El tránsito de Jalisco me paró por ir a exceso de velocidad. No traía mi licencia física, pero se la mostré digital en mi celular a través de la app oficial del Estado. El oficial dice que no es válida y quiere retenerme el vehículo si no llegamos a un 'arreglo'. ¿Qué hago?",
        "expected_behavior": "La IA debe validar que la licencia digital estatal es legalmente válida. Además, debe aconsejar no ceder ante extorsiones y explicar el procedimiento correcto para recibir la infracción por velocidad."
    }
]

@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_rag_scenarios(scenario):
    # 1. Obtener la respuesta de nuestro RAG directamente (sin pasar por la web HTTP)
    chain = rag.get_qa_chain("transito", "jalisco", None)
    
    # Simular una consulta del usuario
    answer = chain.invoke(
        {"question": scenario["question"]},
        config={"configurable": {"session_id": f"test_{scenario['name']}"}}
    )
    
    # Extraer el texto final
    response_text = answer.content if hasattr(answer, "content") else str(answer)

    # 2. Usar Gemini como Juez (LLM-as-a-judge) para evaluar a nuestro propio sistema
    prompt = f"""
    Eres un juez experto en derecho de tránsito mexicano.
    Un usuario hizo esta pregunta a un asistente legal de IA: "{scenario['question']}"
    
    La IA del sistema respondió lo siguiente: 
    "{response_text}"
    
    El comportamiento esperado era: 
    {scenario['expected_behavior']}
    
    Evalúa la respuesta de la IA del 1 al 10 basándote en qué tan bien cumplió con el comportamiento esperado, precisión y utilidad.
    Devuelve estrictamente un JSON con este formato y nada más:
    {{"score": 8, "reasoning": "Explicación breve de por qué le diste esa calificación"}}
    """
    
    eval_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    # 3. Extraer y parsear la calificacion del juez
    result_text = eval_response.text.strip()
    if result_text.startswith("```json"):
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        
    try:
        evaluation = json.loads(result_text)
        score = evaluation.get("score", 0)
        reasoning = evaluation.get("reasoning", "")
    except Exception as e:
        pytest.fail(f"Fallo al parsear la evaluación del juez: {e}\nTexto crudo: {result_text}")
        
    # Imprimir los resultados en consola para poder leerlos
    print(f"\n--- Escenario: {scenario['name']} ---")
    print(f"Pregunta: {scenario['question']}")
    print(f"Respuesta de Mi Abogado Vial:\n{response_text}")
    print(f"\n👉 CALIFICACIÓN DEL JUEZ: {score}/10")
    print(f"👉 Razón: {reasoning}")
    print("----------------------------------\n")
    
    # La prueba pasa automáticamente si la IA saca al menos 7/10
    assert score >= 7, f"La IA reprobó el escenario. Calificación: {score}/10. Razón: {reasoning}"
