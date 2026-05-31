from backend.callback_reason import parse_vocal_callback_reason


def test_parse_vocal_callback_reason_rdv():
    code, detail = parse_vocal_callback_reason("J'ai une question sur mon rendez-vous de mardi")
    assert code == "question_rdv"
    assert "mardi" in detail


def test_parse_vocal_callback_reason_admin():
    code, _ = parse_vocal_callback_reason("C'est pour une question administrative")
    assert code == "admin"


def test_parse_vocal_callback_reason_ordonnance():
    code, _ = parse_vocal_callback_reason("Ordonnance a renouveler")
    assert code == "ordonnance"


def test_parse_vocal_callback_reason_other_default():
    code, detail = parse_vocal_callback_reason("autre")
    assert code == "other"
    assert detail == ""
