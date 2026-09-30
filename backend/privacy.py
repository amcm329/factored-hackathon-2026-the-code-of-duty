from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine


nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [
        {"lang_code": "en", "model_name": "en_core_web_sm"},
        {"lang_code": "es", "model_name": "es_core_news_sm"},
        {"lang_code": "pt", "model_name": "pt_core_news_sm"},
    ],
}

provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(
    nlp_engine=nlp_engine,
    supported_languages=["en", "es", "pt"],
)

anonymizer = AnonymizerEngine()

customer_id_recognizer = PatternRecognizer(
    supported_entity="CUSTOMER_ID",
    patterns=[
        Pattern(
            name="customer_id_pattern",
            regex=r"\bCUST[_-]?[A-Z0-9]+\b",
            score=0.85,
        )
    ],
    supported_language="en",
)

transaction_id_recognizer = PatternRecognizer(
    supported_entity="TRANSACTION_ID",
    patterns=[
        Pattern(
            name="transaction_id_pattern",
            regex=r"\b(?:TX|TXN)[_-]?[A-Z0-9]+\b",
            score=0.85,
        )
    ],
    supported_language="en",
)

analyzer.registry.add_recognizer(customer_id_recognizer)
analyzer.registry.add_recognizer(transaction_id_recognizer)


def sanitize_text(text, language="en"):
    """Detect and replace PII before text leaves the AWS backend."""

    if language not in {"en", "es", "pt"}:
        language = "en"

    results = analyzer.analyze(
        text=text,
        language=language,
    )

    return anonymizer.anonymize(
        text=text,
        analyzer_results=results,
    ).text


def create_alias_map(records, id_field, prefix):
    """Create short-lived aliases for structured database identifiers."""

    alias_map = {}
    safe_records = []

    for index, record in enumerate(records, start=1):
        alias = f"{prefix}_{index}"
        real_id = record[id_field]
        alias_map[alias] = real_id

        safe_record = {
            key: value
            for key, value in record.items()
            if key != id_field
        }
        safe_record["reference"] = alias
        safe_records.append(safe_record)

    return safe_records, alias_map