from backend.database import create_dispute_case


def open_dispute(customer_id, transaction_id, reason, escalation_probability, requires_human_review):
    """Persist the final dispute decision.

    Parameters:
        customer_id: Authenticated customer ID.
        transaction_id: Customer transaction being disputed.
        reason: Sanitized dispute reason.
        escalation_probability: Logistic Regression probability.
        requires_human_review: Model escalation decision.

    Returns:
        dict: Persisted dispute row.
    """

    return create_dispute_case(
        customer_id=customer_id,
        transaction_id=transaction_id,
        reason=reason,
        escalation_probability=escalation_probability,
        requires_human_review=requires_human_review,
    )
