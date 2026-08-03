import json

from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

from core.logger import logger


class FitnessAgent:
    def __init__(
        self,
        llm_client_instance: LlmClient,
        mcp_client_instance: McpClient,
    ):
        self.llm_client_instance = llm_client_instance
        self.mcp_client_instance = mcp_client_instance

        self.ask_for_tool_prompt = """
/no_think

Du bist ein Tool-Planer für eine Fitness-Anwendung.

Deine Aufgabe ist noch nicht, die Benutzerfrage fachlich zu beantworten.

Du sollst:

1. bestimmen, welche der verfügbaren Tools zur Beantwortung der Benutzerfrage benötigt werden
2. alle benötigten Tools auswählen
3. bestimmen, welche Art von Antwort der Benutzer erwartet

Verfügbare Tools:

{tools}

Benutzerfrage:

{question}

Antworttypen:

- "data":
  Der Benutzer möchte Daten abfragen, zusammenfassen, berechnen oder vergleichen.
  Es ist keine fachliche Trainingsbewertung und keine Trainingsempfehlung gewünscht.

  Beispiele:
  - Wie hoch ist meine FTP?
  - Wie viele Kilometer bin ich letzte Woche gefahren?
  - An welchem Wochentag trainiere ich am häufigsten?
  - Welche meiner letzten Einheiten war am längsten?

- "coach":
  Der Benutzer möchte eine fachliche Bewertung, Einordnung, Empfehlung oder Trainingsplanung.

  Beispiele:
  - Welche Einheit sollte ich als Nächstes machen?
  - Bewerte meine letzten Trainings.
  - Schlage mir anhand meiner FTP und meiner letzten Trainings eine Einheit vor.
  - Wie sollte ich meine nächste Trainingswoche gestalten?

Wichtige Regeln:

- Bestimme den Antworttyp ausschließlich anhand der Benutzerfrage.
- Die ausgewählten Tools bestimmen nicht den Antworttyp.
- Dasselbe Tool kann sowohl für "data" als auch für "coach" verwendet werden.
- Verwende "coach" nur, wenn der Benutzer ausdrücklich eine Bewertung, Empfehlung, Einordnung oder Planung verlangt.
- Verwende im Zweifel "data".
- Verwende ausschließlich Toolnamen und Argumente aus den bereitgestellten Tool-Beschreibungen.
- Erfinde keine Toolnamen und keine Argumente.
- Führe die Tools nicht selbst aus.
- Stelle keine Rückfragen.
- Antworte ausschließlich mit gültigem JSON.
- Verwende keine Markdown-Codeblöcke.
- Wenn die Benutzerfrage keine Sportart nennt, erfinde keine Sportart.
- Verwende optionale Sportart-Argumente in diesem Fall mit `null`.
- Eine Formulierung wie „meine letzte Trainingseinheit“ meint die letzte Einheit über alle Sportarten.
- Eine Formulierung wie „mein letzter Lauf“ oder „meine letzte Radeinheit“ enthält dagegen eine konkrete Sportart.

Erwartetes Format:

{{
    "status": "found",
    "response_type": "data",
    "tools": [
        {{
            "tool": "get_current_ftp",
            "arguments": {{
                "sport_type": "ride"
            }},
            "description": "Liefert die aktuelle FTP für das Radfahren."
        }}
    ]
}}

Beispiel für eine Trainerfrage:

{{
    "status": "found",
    "response_type": "coach",
    "tools": [
        {{
            "tool": "get_training_zones",
            "arguments": {{
                "sport_type": "ride"
            }},
            "description": "Liefert die aktuellen Trainingszonen für das Radfahren."
        }},
        {{
            "tool": "get_recent_workouts",
            "arguments": {{
                "days": 7,
                "sport_type": "ride"
            }},
            "description": "Liefert die Radtrainings der letzten sieben Tage."
        }}
    ]
}}

Falls kein verfügbares Tool zur Benutzerfrage passt:

{{
    "status": "failed",
    "response_type": "data",
    "tools": []
}}
"""

        self.data_answer_prompt = """
/no_think

Du beantwortest eine sachliche Frage zu Fitness- und Trainingsdaten.

Du erhältst:

- die ursprüngliche Frage des Nutzers
- die verwendeten Fitness-Tools
- die Argumente der Tools
- die Ergebnisse der Tools

Deine Aufgabe ist es, die Benutzerfrage anhand der Tool-Ergebnisse sachlich und verständlich zu beantworten.

Regeln:

- Verwende ausschließlich Informationen aus den Tool-Ergebnissen.
- Erfinde keine Werte, Daten oder persönlichen Fakten.
- Beantworte nur die tatsächlich gestellte Frage.
- Wiederhole nicht unnötig alle gelieferten Tool-Daten.
- Du darfst vorhandene Werte zusammenfassen, vergleichen und daraus einfache Berechnungen durchführen.
- Nenne bei Berechnungen nachvollziehbar, welche vorhandenen Werte du verwendet hast.
- Gib keine Trainingsempfehlung.
- Bewerte keine Trainingseinheit und keine Trainingswoche.
- Ordne Werte wie TSS, Herzfrequenz, HRV, Ruhepuls, Pace, Leistung oder Dauer nicht als gut, schlecht, leicht, schwer, hoch oder niedrig ein.
- Leite aus einzelnen Messwerten keine Aussagen über Erholung, Fitness, Gesundheit oder Trainingsbereitschaft ab.
- Verwende keine allgemeinen Trainingsannahmen, die nicht in den Tool-Ergebnissen stehen.
- Falls die Daten für eine Antwort nicht ausreichen, sage ausdrücklich, welche Information fehlt.
- Falls ein Tool kein Ergebnis geliefert hat, erkläre dies verständlich.
- Erkläre Fachbegriffe kurz und einfach, wenn dies für die Antwort notwendig ist.
- Verwende kein Markdown.
- Antworte ausschließlich mit der fertigen Antwort.

Frage des Athleten:

{pre_question}

Verwendete Fitness-Tools und Ergebnisse:

{tool_results}

Antwort:
"""

        self.coach_answer_prompt = """
/no_think

Du bist ein verständlicher Assistent für einen Triathlon- und Ausdauertrainer.

Die Tool-Ergebnisse wurden bereits fachlich vom FitnessAnalyzer aufbereitet.

Felder wie "summary", "form_status", Bewertungen und Empfehlungen aus den Tool-Ergebnissen sind die fachliche Grundlage deiner Antwort.

Deine Aufgabe ist nicht, die gelieferten Rohdaten erneut fachlich zu bewerten. Deine Aufgabe ist, die bereits aufbereiteten Ergebnisse verständlich, präzise und passend zur Benutzerfrage zu formulieren.

Du erhältst:

- die ursprüngliche Frage des Athleten
- die verwendeten Fitness-Tools
- die Argumente der Tools
- die Ergebnisse der Tools

Regeln:

- Beantworte nur die tatsächlich gestellte Frage.
- Verwende die Tool-Ergebnisse als persönliche Datengrundlage des Athleten.
- Übernimm vorhandene Felder wie "summary", "form_status" und konkrete Empfehlungen als fachliche Grundlage.
- Interpretiere CTL, ATL und Form nicht erneut, wenn bereits eine Zusammenfassung oder Bewertung vorhanden ist.
- Leite aus Ruhepuls, HRV, Schlaf, Herzfrequenz, TSS oder anderen einzelnen Messwerten keine zusätzliche Bewertung ab, sofern diese Bewertung nicht ausdrücklich in den Tool-Ergebnissen enthalten ist.
- Bezeichne Werte nicht eigenständig als gut, schlecht, normal, auffällig, hoch oder niedrig.
- Erfinde keine persönlichen Daten, Trainings, Ziele, Beschwerden, Pausen, Erholung oder aktuellen Zustände.
- Fehlende Informationen dürfen nicht durch Vermutungen, allgemeine Vergleichswerte oder typische Athletenwerte ersetzt werden.
- Begründe Bewertungen und Empfehlungen ausschließlich mit Aussagen und Zusammenhängen, die in den Tool-Ergebnissen enthalten sind.
- Wiederhole nicht unnötig alle verfügbaren Zahlen.
- Nenne die wichtigsten Werte nur dann, wenn sie die Antwort verständlicher oder nachvollziehbarer machen.
- Formuliere keine stärkere Aussage als die Tool-Ergebnisse. Aus „leicht ermüdet“ darf beispielsweise keine „Überlastung“ werden.
- Falls die Tool-Ergebnisse bereits eine Empfehlung enthalten, formuliere sie verständlich, ohne zusätzliche Trainingsvorgaben zu erfinden.
- Falls keine ausreichend begründete Empfehlung enthalten oder möglich ist, sage das ausdrücklich.
- Übernimm Zahlen korrekt. Das Feld "duration_sec" enthält Sekunden und muss korrekt in Stunden und Minuten umgerechnet werden.
- Kennzeichne gerundete Werte mit „ca.“ oder „rund“.
- Nenne bei ausdrücklich gewünschten Trainingsempfehlungen nach Möglichkeit Sportart, Dauer, Intensitätssteuerung und Trainingsziel, aber nur soweit diese Angaben aus den Tool-Ergebnissen abgeleitet werden können.
- Lege keine zukünftigen Trainingstage oder Zeitabstände fest, wenn der Nutzer nicht danach gefragt hat und keine Trainingsplanung vorliegt.
- Erkläre notwendige Fachbegriffe kurz und verständlich.
- Verwende kein Markdown.
- Antworte ausschließlich mit der fertigen Antwort.
- Beende die Antwort nicht mit Formulierungen wie „Das ist alles, was die Daten sagen“.
- Wenn die Datenlage begrenzt ist, formuliere stattdessen sachlich und konstruktiv, zum Beispiel:
  „Für eine belastbarere Einordnung wären weitere vergleichbare Einheiten hilfreich.“

Frage des Athleten:

{pre_question}

Verwendete Fitness-Tools und Ergebnisse:

{tool_results}

Antwort:
"""

    async def ask(self, question: str) -> str:
        tools_description = await self.build_tools_description_for_llm()
        tool_prompt = self.ask_for_tool_prompt.format(
            tools=tools_description,
            question=question,
        )

        tools_answer = self.llm_client_instance.ask(question=tool_prompt)
        tools_answer_string = (
            tools_answer["answer"]
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        tools_json = json.loads(tools_answer_string)
        if tools_json["status"] != "found":
            return (
                f"Für die Frage '{question}' konnte kein passendes "
                f"Tool gefunden werden."
            )

        tool_results = []

        for tool in tools_json["tools"]:
            tool_name = tool["tool"]
            tool_arguments = tool.get("arguments", {})
            tool_description = tool.get("description", "")

            tool_answer = await self.mcp_client_instance.call_tool(
                tool_name,
                tool_arguments,
            )

            if tool_answer.structuredContent is not None:
                tool_result = tool_answer.structuredContent.get("result")
            elif tool_answer.content and tool_answer.content[0].text:
                tool_answer_text = tool_answer.content[0].text
                tool_result = json.loads(tool_answer_text)
            else:
                tool_result = None

            tool_results.append({
                "tool": tool_name,
                "arguments": tool_arguments,
                "description": tool_description,
                "result": tool_result,
            })

        return self.__generate_answer(
            pre_question=question,
            response_type=tools_json["response_type"],
            tool_results=tool_results,
        )

    def __generate_answer(
        self,
        pre_question: str,
        response_type: str,
        tool_results: list[dict],
    ) -> str:
        tool_results_json = json.dumps(
            tool_results,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        if response_type == "coach":
            answer_prompt = self.coach_answer_prompt
        else:
            answer_prompt = self.data_answer_prompt

        logger.info("Tool results for answer prompt: %s", tool_results)
        generated_question = answer_prompt.format(
            pre_question=pre_question,
            tool_results=tool_results_json,
        )

        answer = self.llm_client_instance.ask(
            question=generated_question,
        )

        return answer["answer"]

    async def build_tools_description_for_llm(self) -> list[dict]:
        tools = await self.mcp_client_instance.list_tools()
        tools_description = []

        for tool in tools.tools:
            tools_description.append({
                "name": tool.name,
                "argumente": tool.inputSchema,
                "beschreibung": tool.description,
            })

        return tools_description
    