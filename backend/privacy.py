from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer


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

sensitive_entities = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "US_BANK_NUMBER",
    "CUSTOMER_ID",
    "TRANSACTION_ID",
]

for supported_language in ["en", "es", "pt"]:
    customer_id_recognizer = PatternRecognizer(
        supported_entity="CUSTOMER_ID",
        patterns=[
            Pattern(
                name="customer_id_pattern",
                regex=r"\bCUST[_-]?[A-Z0-9]+\b",
                score=0.85,
            )
        ],
        supported_language=supported_language,
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
        supported_language=supported_language,
    )

    analyzer.registry.add_recognizer(customer_id_recognizer)
    analyzer.registry.add_recognizer(transaction_id_recognizer)


def sanitize_text(text, language="en"):
    """Detect and replace sensitive PII before text leaves the AWS backend.

    Parameters
    ----------
    text : str
        Text that may contain sensitive information.
    language : str
        Language code used by Presidio.

    Returns
    -------
    str
        Text with sensitive entities anonymized.
    """
    if language not in {"en", "es", "pt"}:
        language = "en"

    results = analyzer.analyze(
        text=text,
        language=language,
        entities=sensitive_entities,
    )

    return anonymizer.anonymize(
        text=text,
        analyzer_results=results,
    ).text
