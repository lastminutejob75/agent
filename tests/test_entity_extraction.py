# tests/test_entity_extraction.py
"""
Tests pour l'extraction d'entités (Option 2).
Vérifie l'extraction conservatrice de noms, motifs et préférences.
"""

import pytest
from backend.entity_extraction import (
    extract_name,
    extract_motif,
    extract_pref,
    extract_entities,
    get_missing_fields,
    get_next_missing_field,
    merge_entities,
    ExtractedEntities,
)


# ============================================
# Tests extraction de nom
# ============================================

class TestExtractName:
    """Tests pour l'extraction de noms."""
    
    def test_je_suis_pattern(self):
        """Pattern 'je suis [prénom nom]'"""
        assert extract_name("je suis jean dupont") == "Jean Dupont"
        assert extract_name("Je suis Marie Martin") == "Marie Martin"
        assert extract_name("je suis pierre durand") == "Pierre Durand"
    
    def test_je_mappelle_pattern(self):
        """Pattern 'je m'appelle [prénom nom]'"""
        assert extract_name("je m'appelle jean dupont") == "Jean Dupont"
        assert extract_name("Je m'appelle Sophie Bernard") == "Sophie Bernard"
    
    def test_cest_pattern(self):
        """Pattern 'c'est [prénom nom]'"""
        assert extract_name("c'est jean dupont") == "Jean Dupont"
        assert extract_name("C'est Marie Martin") == "Marie Martin"
    
    def test_mon_nom_pattern(self):
        """Pattern 'mon nom c'est/est [prénom nom]'"""
        assert extract_name("mon nom c'est jean dupont") == "Jean Dupont"
        assert extract_name("mon nom est marie martin") == "Marie Martin"
    
    def test_a_lappareil_pattern(self):
        """Pattern '[prénom nom] à l'appareil'"""
        assert extract_name("jean dupont à l'appareil") == "Jean Dupont"
    
    def test_exclusions(self):
        """Doit exclure les faux positifs."""
        # "le docteur Martin" ne doit pas être extrait
        assert extract_name("je veux voir le docteur Martin") is None
        assert extract_name("c'est pour le médecin") is None
        assert extract_name("j'appelle pour ma mère Marie") is None
    
    def test_no_match(self):
        """Retourne None si aucun pattern ne matche."""
        assert extract_name("je veux un rendez-vous") is None
        assert extract_name("bonjour") is None
        assert extract_name("quelle sont vos horaires") is None
    
    def test_accents(self):
        """Gère les accents français."""
        assert extract_name("je suis héléne béraud") == "Héléne Béraud"
        assert extract_name("je suis françois müller") == "François Müller"


# ============================================
# Tests extraction de motif
# ============================================

class TestExtractMotif:
    """Tests pour l'extraction de motifs."""
    
    def test_douleur_simple(self):
        """Détecte le motif 'douleur'."""
        result = extract_motif("j'ai mal")
        assert result.get("type") == "douleur"
    
    def test_douleur_avec_localisation(self):
        """Détecte douleur + localisation."""
        result = extract_motif("j'ai mal au dos")
        assert result.get("type") == "douleur"
        assert result.get("detail") == "dos"
        assert result.get("full") == "douleur dos"
        
        result = extract_motif("j'ai une douleur à la tête")
        assert result.get("detail") == "tête"
    
    def test_controle(self):
        """Détecte le motif 'contrôle'."""
        result = extract_motif("pour un contrôle")
        assert result.get("type") == "contrôle"
        
        result = extract_motif("visite de suivi")
        assert result.get("type") == "contrôle"
    
    def test_renouvellement(self):
        """Détecte le motif 'renouvellement'."""
        result = extract_motif("renouveler mon ordonnance")
        assert result.get("type") == "renouvellement"
        
        result = extract_motif("j'ai besoin d'une ordonnance")
        assert result.get("type") == "renouvellement"
    
    def test_vaccination(self):
        """Détecte le motif 'vaccination'."""
        result = extract_motif("pour mes vaccins")
        assert result.get("type") == "vaccination"
        
        result = extract_motif("rappel vaccin")
        assert result.get("type") == "vaccination"
    
    def test_bilan(self):
        """Détecte le motif 'bilan'."""
        result = extract_motif("prise de sang")
        assert result.get("type") == "bilan"
        
        result = extract_motif("bilan sanguin")
        assert result.get("type") == "bilan"
    
    def test_no_match(self):
        """Retourne dict vide si aucun motif trouvé."""
        result = extract_motif("je voudrais un rendez-vous")
        assert result == {}
        
        result = extract_motif("bonjour")
        assert result == {}


# ============================================
# Tests extraction de préférence
# ============================================

class TestExtractPref:
    """Tests pour l'extraction de préférences horaires."""
    
    def test_matin(self):
        """Détecte 'matin'."""
        assert extract_pref("plutôt le matin") == "matin"
        assert extract_pref("le matin si possible") == "matin"
    
    def test_apres_midi(self):
        """Détecte 'après-midi'."""
        assert extract_pref("l'après-midi") == "après-midi"
        assert extract_pref("cet après midi") == "après-midi"
    
    def test_jour_seul(self):
        """Détecte un jour seul."""
        assert extract_pref("lundi") == "lundi"
        assert extract_pref("plutôt mardi") == "mardi"
    
    def test_jour_et_moment(self):
        """Détecte jour + moment."""
        assert extract_pref("lundi matin") == "lundi matin"
        assert extract_pref("mardi après-midi") == "mardi après-midi"
    
    def test_no_match(self):
        """Retourne None si aucune préférence trouvée."""
        assert extract_pref("je suis flexible") is None
        assert extract_pref("n'importe quand") is None


# ============================================
# Tests extraction complète
# ============================================

class TestExtractEntities:
    """Tests pour l'extraction complète."""
    
    def test_message_complet(self):
        """Extrait tout d'un message complet."""
        msg = "je suis jean dupont, je voudrais un rdv pour un contrôle, plutôt mardi matin"
        entities = extract_entities(msg)
        
        assert entities.name == "Jean Dupont"
        assert entities.motif == "contrôle"
        assert entities.pref == "mardi matin"
        assert entities.has_any() is True
        assert entities.confidence > 0
    
    def test_message_partiel(self):
        """Extrait ce qui est disponible."""
        msg = "je suis marie martin, j'ai mal au dos"
        entities = extract_entities(msg)
        
        assert entities.name == "Marie Martin"
        assert entities.motif == "douleur dos"
        assert entities.pref is None
    
    def test_message_sans_info(self):
        """Retourne entités vides si rien trouvé."""
        msg = "je voudrais un rendez-vous svp"
        entities = extract_entities(msg)
        
        assert entities.name is None
        assert entities.motif is None
        assert entities.pref is None
        assert entities.has_any() is False
    
    def test_to_dict(self):
        """Conversion en dict."""
        entities = ExtractedEntities(name="Jean Dupont", motif="contrôle")
        d = entities.to_dict()
        
        assert d["name"] == "Jean Dupont"
        assert d["motif"] == "contrôle"
        assert d["pref"] is None


# ============================================
# Tests utilitaires
# ============================================

class TestGetMissingFields:
    """Tests pour get_missing_fields (défaut: skip_motif=True → name, pref, contact)."""
    
    def test_all_missing(self):
        """Tous les champs manquent (ordre par défaut: name, pref, contact)."""
        context = {}
        missing = get_missing_fields(context)
        assert missing == ["name", "pref", "contact"]
    
    def test_some_filled(self):
        """Certains champs remplis."""
        context = {"name": "Jean Dupont", "pref": "matin"}
        missing = get_missing_fields(context)
        assert missing == ["contact"]
    
    def test_all_filled(self):
        """Tous les champs remplis (name, pref, contact)."""
        context = {
            "name": "Jean Dupont",
            "pref": "matin",
            "contact": "0612345678",
        }
        missing = get_missing_fields(context)
        assert missing == []


class TestGetNextMissingField:
    """Tests pour get_next_missing_field (défaut: skip_motif=True)."""
    
    def test_first_missing(self):
        """Retourne le premier champ manquant (name → pref → contact)."""
        assert get_next_missing_field({}) == "name"
        assert get_next_missing_field({"name": "Jean"}) == "pref"
        assert get_next_missing_field({"name": "Jean", "pref": "matin"}) == "contact"
    
    def test_none_missing(self):
        """Retourne None si tout est rempli."""
        context = {
            "name": "Jean",
            "pref": "matin",
            "contact": "email@test.com",
        }
        assert get_next_missing_field(context) is None


class TestMergeEntities:
    """Tests pour merge_entities."""
    
    def test_merge_empty(self):
        """Merge avec contexte vide."""
        existing = {}
        extracted = ExtractedEntities(name="Jean Dupont", motif="contrôle")
        
        result = merge_entities(existing, extracted)
        
        assert result["name"] == "Jean Dupont"
        assert result["motif"] == "contrôle"
        assert result.get("name_extracted") is True
    
    def test_existing_priority(self):
        """Les valeurs existantes ont priorité."""
        existing = {"name": "Pierre Martin"}
        extracted = ExtractedEntities(name="Jean Dupont", motif="contrôle")
        
        result = merge_entities(existing, extracted)
        
        # Le nom existant est conservé
        assert result["name"] == "Pierre Martin"
        # Le motif extrait est ajouté
        assert result["motif"] == "contrôle"
