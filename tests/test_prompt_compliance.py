# tests/test_prompt_compliance.py
"""
Tests de non-régression du comportement / wording.
Ces tests protègent le PRD + System Prompt.
Ne pas modifier ces tests sans modifier PRD/SYSTEM_PROMPT.
"""

import pytest
from backend import prompts


def test_empty_message_exact_wording():
    assert prompts.MSG_EMPTY_MESSAGE == "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?"


def test_too_long_exact_wording():
    assert prompts.MSG_TOO_LONG == "Votre message est trop long. Pouvez-vous résumer ?"


def test_french_only_exact_wording():
    assert prompts.MSG_FRENCH_ONLY == "Je ne parle actuellement que français."


def test_session_expired_exact_wording():
    assert prompts.MSG_SESSION_EXPIRED == "Votre session a expiré. Puis-je vous aider ?"


def test_transfer_exact_wording():
    assert prompts.MSG_TRANSFER == "Je vous mets en relation avec un conseiller. Ne quittez pas, s'il vous plaît."


def test_already_transferred_exact_wording():
    assert prompts.MSG_ALREADY_TRANSFERRED == "Vous avez été transféré à un humain. Quelqu'un va vous répondre sous peu."


def test_contact_invalid_exact_wording():
    assert prompts.MSG_CONTACT_INVALID == "Le format du contact est invalide. Merci de fournir un email ou un numéro de téléphone valide."


def test_contact_invalid_transfer_exact_wording():
    assert prompts.MSG_CONTACT_INVALID_TRANSFER == "Le format du contact est invalide. Je vous mets en relation avec un humain pour vous aider."


def test_aide_motif_exact_wording():
    expected = (
        "Pour continuer, indiquez le motif du rendez-vous "
        "(ex : consultation, contrôle, douleur, devis). Répondez en 1 courte phrase."
    )
    assert prompts.MSG_AIDE_MOTIF == expected


def test_conversation_closed_exact_wording():
    expected = (
        "C'est terminé pour cette demande. "
        "Si vous avez un nouveau besoin, ouvrez une nouvelle conversation ou parlez à un humain."
    )
    assert prompts.MSG_CONVERSATION_CLOSED == expected


def test_no_match_faq_exact_wording():
    business = "Cabinet Dupont"
    expected = (
        "Je ne suis pas certain de pouvoir répondre précisément.\n"
        "Puis-je vous mettre en relation avec Cabinet Dupont ?"
    )
    assert prompts.msg_no_match_faq(business) == expected


def test_faq_format_includes_source_and_exact_structure():
    answer = "Nos horaires sont de 9h à 18h du lundi au vendredi."
    faq_id = "FAQ_HORAIRES"
    out = prompts.format_faq_response(answer, faq_id)
    assert out == "Nos horaires sont de 9h à 18h du lundi au vendredi.\n\nSource : FAQ_HORAIRES"
    assert "\n\nSource : " in out


def test_qualif_questions_are_closed_and_ordered():
    assert prompts.QUALIF_QUESTIONS_ORDER == ["name", "motif", "pref", "contact"]
    assert prompts.QUALIF_QUESTIONS["name"] == "Quel est votre nom et prénom ?"
    assert prompts.QUALIF_QUESTIONS["motif"] == "Pour quel sujet ? (ex : renouvellement, douleur, bilan, visiteur médical)"
    assert prompts.QUALIF_QUESTIONS["pref"] == "Quel créneau préférez-vous ? (ex : lundi matin, mardi après-midi)"
    assert prompts.QUALIF_QUESTIONS["contact"] == "Quel est votre moyen de contact ? (email ou téléphone)"


def test_booking_confirm_instruction_exact():
    assert prompts.MSG_CONFIRM_INSTRUCTION == "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer."


def test_slot_proposal_format_is_deterministic():
    slots = [
        prompts.SlotDisplay(idx=1, label="Mardi 15/01 - 10:00", slot_id=101),
        prompts.SlotDisplay(idx=2, label="Mardi 15/01 - 14:00", slot_id=102),
        prompts.SlotDisplay(idx=3, label="Mardi 15/01 - 16:00", slot_id=103),
    ]
    out = prompts.format_slot_proposal(slots)
    expected = (
        "Créneaux disponibles :\n"
        "1. Mardi 15/01 - 10:00\n"
        "2. Mardi 15/01 - 14:00\n"
        "3. Mardi 15/01 - 16:00\n"
        "\n"
        "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer."
    )
    assert out == expected


def test_booking_confirmed_format_is_exact():
    out = prompts.format_booking_confirmed("Mardi 15/01 - 14:00")
    expected = (
        "Parfait ! Votre rendez-vous est confirmé.\n"
        "\n"
        "📅 Date et heure : Mardi 15/01 - 14:00\n"
        "\n"
        "À bientôt !"
    )
    assert out == expected


def test_booking_confirmed_with_name_and_motif():
    out = prompts.format_booking_confirmed("Mardi 15/01 - 14:00", name="Jean Dupont", motif="Consultation")
    assert "Parfait ! Votre rendez-vous est confirmé." in out
    assert "📅 Date et heure : Mardi 15/01 - 14:00" in out
    assert "👤 Nom : Jean Dupont" in out
    assert "📋 Motif : Consultation" in out
    assert "À bientôt !" in out


def test_all_prompts_are_strings_and_non_empty():
    for s in [
        prompts.MSG_EMPTY_MESSAGE,
        prompts.MSG_TOO_LONG,
        prompts.MSG_FRENCH_ONLY,
        prompts.MSG_SESSION_EXPIRED,
        prompts.MSG_TRANSFER,
        prompts.MSG_ALREADY_TRANSFERRED,
        prompts.MSG_CONTACT_INVALID,
        prompts.MSG_CONTACT_INVALID_TRANSFER,
        prompts.MSG_CONFIRM_INSTRUCTION,
        prompts.MSG_AIDE_MOTIF,
        prompts.MSG_CONVERSATION_CLOSED,
    ]:
        assert isinstance(s, str)
        assert len(s) > 0


def test_no_prompts_exceed_150_chars():
    assert len(prompts.MSG_EMPTY_MESSAGE) < 150
    assert len(prompts.MSG_TOO_LONG) < 150
    assert len(prompts.MSG_FRENCH_ONLY) < 150
    assert len(prompts.MSG_SESSION_EXPIRED) < 150
    assert len(prompts.MSG_TRANSFER) < 150
    # MSG_AIDE_MOTIF peut dépasser 150 chars car il donne des exemples
    # Vérification qu'il reste raisonnable (< 200)
    assert len(prompts.MSG_AIDE_MOTIF) < 200


def test_qualif_questions_format_constraints():
    for key, q in prompts.QUALIF_QUESTIONS.items():
        # Les questions doivent contenir un '?' (pas forcément à la fin si exemples)
        assert "?" in q, f"{key}: doit contenir '?'"
        assert len(q) < 120, f"{key}: trop long (>120 chars)"
        # Les questions commencent par 'Quel' ou 'Pour'
        assert q.startswith("Quel") or q.startswith("Pour"), f"{key}: doit commencer par 'Quel' ou 'Pour'"


def test_faq_response_never_empty():
    try:
        out = prompts.format_faq_response("", "FAQ_TEST")
        assert False, "format_faq_response doit refuser answer vide"
    except ValueError:
        assert True


def test_booking_confirmed_includes_slot_label():
    slot = "Mardi 15/01 - 14:00"
    out = prompts.format_booking_confirmed(slot)
    assert slot in out


# ----------------------------
# Tests pour les prompts vocaux (V1)
# ----------------------------

def test_vocal_qualif_questions_are_short():
    """Les questions vocales doivent être courtes pour le TTS (motif désactivé = vide)."""
    for key, q in prompts.QUALIF_QUESTIONS_VOCAL.items():
        if not q:
            continue  # motif désactivé en vocal
        assert len(q) < 80, f"{key}: trop long pour le vocal (>80 chars)"
        assert "?" in q, f"{key}: doit contenir '?'"


def test_vocal_faq_response_no_source():
    """En mode vocal, pas de 'Source: XXX' (pas naturel)."""
    answer = "Nos horaires sont de 9h à 18h."
    faq_id = "FAQ_HORAIRES"
    out = prompts.format_faq_response(answer, faq_id, channel="vocal")
    assert "Source" not in out
    assert out == answer


def test_vocal_slot_proposal_is_natural():
    """Le format vocal doit être naturel pour le TTS (un/deux/trois)."""
    slots = [
        prompts.SlotDisplay(idx=1, label="Mardi 10h", slot_id=101),
        prompts.SlotDisplay(idx=2, label="Mardi 14h", slot_id=102),
        prompts.SlotDisplay(idx=3, label="Mardi 16h", slot_id=103),
    ]
    out = prompts.format_slot_proposal(slots, channel="vocal")
    out_lower = out.lower()
    assert "un" in out_lower and "deux" in out_lower and "trois" in out_lower
    assert "mardi 10h" in out_lower and "mardi 14h" in out_lower
    assert "Créneaux disponibles" not in out
    assert "oui 1" not in out_lower


def test_vocal_booking_confirmed_no_emoji():
    """En mode vocal, pas d'emoji."""
    slot = "Mardi 14h"
    out = prompts.format_booking_confirmed(slot, channel="vocal")
    assert "📅" not in out
    assert "👤" not in out
    assert slot in out


def test_get_message_adapts_to_channel():
    """get_message retourne le bon message selon le canal."""
    # Vocal
    vocal_transfer = prompts.get_message("transfer", channel="vocal")
    assert "mets en relation" in vocal_transfer.lower() or "conseiller" in vocal_transfer.lower()
    
    # Web
    web_transfer = prompts.get_message("transfer", channel="web")
    assert "relation" in web_transfer.lower()


def test_get_qualif_question_adapts_to_channel():
    """get_qualif_question retourne la bonne question selon le canal."""
    # Vocal - demande nom
    vocal_name = prompts.get_qualif_question("name", channel="vocal")
    assert "nom" in vocal_name.lower()
    
    # Web - plus formel
    web_name = prompts.get_qualif_question("name", channel="web")
    assert "nom et prénom" in web_name.lower()


def test_msg_no_match_faq_adapts_to_channel():
    """msg_no_match_faq retourne le bon message selon le canal."""
    # Vocal
    vocal = prompts.msg_no_match_faq("Cabinet Durand", channel="vocal")
    assert "certain" in vocal.lower() or "mets en relation" in vocal.lower()
    
    # Web - plus formel
    web = prompts.msg_no_match_faq("Cabinet Durand", channel="web")
    assert "certain" in web.lower()
