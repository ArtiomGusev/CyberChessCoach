from rag.contracts.validate_output import validate_output


def run_mode_2(
    *,
    llm,
    prompt: str,
    case_type: str,
) -> str:
    response = llm.generate(prompt)

    validate_output(
        response,
        case_type=case_type,
    )

    return response
