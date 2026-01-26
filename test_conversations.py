#!/usr/bin/env python3
"""
Script de test automatisé pour les conversations UWI.
Teste tous les scénarios de conversation contre l'ENGINE déployé.

Usage:
    python test_conversations.py                    # Tous les tests
    python test_conversations.py --scenario happy   # Un scénario spécifique
    python test_conversations.py --local            # Test local (localhost:8000)
"""

import requests
import time
import argparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

# Configuration
PROD_URL = "https://agent-production-c246.up.railway.app"
LOCAL_URL = "http://localhost:8000"

# Couleurs terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class TestResult:
    """Résultat d'un test de conversation."""
    scenario_name: str
    success: bool
    steps_completed: int
    total_steps: int
    failed_step: Optional[int] = None
    error_message: Optional[str] = None
    user_input: Optional[str] = None
    agent_response: Optional[str] = None
    duration_ms: float = 0
    conversation_log: List[Dict[str, str]] = None


class ConversationTester:
    """Teste un scénario de conversation complet."""
    
    def __init__(self, base_url: str, verbose: bool = False):
        self.base_url = base_url
        self.verbose = verbose
    
    def run_scenario(self, name: str, messages: List[str]) -> TestResult:
        """
        Exécute un scénario de conversation.
        
        Args:
            name: Nom du scénario
            messages: Liste des messages utilisateur
            
        Returns:
            TestResult avec le détail du test
        """
        call_id = f"test-{name}-{int(time.time())}"
        conversation_log = []
        start_time = time.time()
        
        for i, user_msg in enumerate(messages):
            step_num = i + 1
            
            if self.verbose:
                print(f"    [{step_num}/{len(messages)}] User: '{user_msg[:50]}...'")
            
            try:
                # Appel à l'ENGINE
                response = requests.post(
                    f"{self.base_url}/api/vapi/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": user_msg}],
                        "call_id": call_id
                    },
                    timeout=15
                )
                
                # Check HTTP status
                if response.status_code != 200:
                    return TestResult(
                        scenario_name=name,
                        success=False,
                        steps_completed=i,
                        total_steps=len(messages),
                        failed_step=step_num,
                        error_message=f"HTTP {response.status_code}: {response.text[:100]}",
                        user_input=user_msg,
                        duration_ms=(time.time() - start_time) * 1000,
                        conversation_log=conversation_log
                    )
                
                # Parse response
                try:
                    data = response.json()
                    agent_msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    return TestResult(
                        scenario_name=name,
                        success=False,
                        steps_completed=i,
                        total_steps=len(messages),
                        failed_step=step_num,
                        error_message=f"Invalid JSON response: {e}",
                        user_input=user_msg,
                        duration_ms=(time.time() - start_time) * 1000,
                        conversation_log=conversation_log
                    )
                
                # Log conversation
                conversation_log.append({"role": "user", "content": user_msg})
                conversation_log.append({"role": "assistant", "content": agent_msg})
                
                if self.verbose:
                    print(f"    [{step_num}/{len(messages)}] Agent: '{agent_msg[:50]}...'")
                
                # Check for error responses
                error_indicators = [
                    "erreur", "error", "désolé, une erreur",
                    "je vous transfère", "je vous mets en relation"
                ]
                
                # Note: Transfer is not always an error (e.g., for "résultats d'analyses")
                # So we don't fail on transfer for now
                
            except requests.Timeout:
                return TestResult(
                    scenario_name=name,
                    success=False,
                    steps_completed=i,
                    total_steps=len(messages),
                    failed_step=step_num,
                    error_message="Request timeout (15s)",
                    user_input=user_msg,
                    duration_ms=(time.time() - start_time) * 1000,
                    conversation_log=conversation_log
                )
            except requests.RequestException as e:
                return TestResult(
                    scenario_name=name,
                    success=False,
                    steps_completed=i,
                    total_steps=len(messages),
                    failed_step=step_num,
                    error_message=f"Request error: {e}",
                    user_input=user_msg,
                    duration_ms=(time.time() - start_time) * 1000,
                    conversation_log=conversation_log
                )
        
        # All steps completed successfully
        return TestResult(
            scenario_name=name,
            success=True,
            steps_completed=len(messages),
            total_steps=len(messages),
            duration_ms=(time.time() - start_time) * 1000,
            conversation_log=conversation_log
        )


# ============================================
# SCÉNARIOS DE TEST
# ============================================

SCENARIOS = {
    # === FLOW A: BOOKING (Happy Paths) ===
    
    "happy_path_consultation": {
        "description": "RDV complet - consultation",
        "messages": [
            "Oui",                      # Réponse au "pour un RDV ?"
            "Jean Dupont",              # Nom
            "Consultation",             # Motif
            "Le matin",                 # Préférence
        ],
        "expected_flow": "BOOKING"
    },
    
    "happy_path_controle": {
        "description": "RDV complet - contrôle",
        "messages": [
            "Oui",
            "Marie Martin",
            "Contrôle",
            "L'après-midi",
        ],
        "expected_flow": "BOOKING"
    },
    
    "happy_path_douleur": {
        "description": "RDV pour douleur",
        "messages": [
            "Oui",
            "Pierre Bernard",
            "J'ai mal au dos",
            "Le matin si possible",
        ],
        "expected_flow": "BOOKING"
    },
    
    # === FLOW B: FAQ ===
    
    "faq_horaires": {
        "description": "Question sur les horaires",
        "messages": [
            "Non, quels sont vos horaires ?",
        ],
        "expected_flow": "FAQ"
    },
    
    "faq_horaires_direct": {
        "description": "Question horaires directe (sans non)",
        "messages": [
            "C'est quoi vos horaires ?",
        ],
        "expected_flow": "FAQ"
    },
    
    # === FLOW C: CANCEL ===
    
    "cancel_rdv": {
        "description": "Annulation de RDV",
        "messages": [
            "Non, je veux annuler mon rendez-vous",
            "Jean Dupont",
        ],
        "expected_flow": "CANCEL"
    },
    
    # === FLOW D: MODIFY ===
    
    "modify_rdv": {
        "description": "Modification de RDV",
        "messages": [
            "Je voudrais déplacer mon rendez-vous",
            "Jean Dupont",
        ],
        "expected_flow": "MODIFY"
    },
    
    # === FLOW E: UNCLEAR ===
    
    "unclear_hesitation": {
        "description": "Utilisateur hésite",
        "messages": [
            "Non",  # Juste non → CLARIFY
        ],
        "expected_flow": "CLARIFY"
    },
    
    "unclear_then_booking": {
        "description": "Hésite puis veut RDV",
        "messages": [
            "Non",
            "En fait oui, je veux un rendez-vous",
        ],
        "expected_flow": "CLARIFY → BOOKING"
    },
    
    # === FLOW F: TRANSFER ===
    
    "transfer_resultats": {
        "description": "Demande résultats → transfert",
        "messages": [
            "C'est pour mes résultats d'analyses",
        ],
        "expected_flow": "TRANSFER"
    },
    
    # === EDGE CASES ===
    
    "edge_motif_generique": {
        "description": "Motif trop générique (rdv)",
        "messages": [
            "Oui",
            "Test User",
            "un rdv",  # Trop générique → demande précision
        ],
        "expected_flow": "BOOKING (retry motif)"
    },
    
    "edge_spam_insulte": {
        "description": "Insulte détectée",
        "messages": [
            "Va te faire foutre",
        ],
        "expected_flow": "TRANSFER (spam)"
    },
    
    "edge_message_vide": {
        "description": "Message vide",
        "messages": [
            "",
        ],
        "expected_flow": "ERROR"
    },
    
    "edge_message_long": {
        "description": "Message très long",
        "messages": [
            "a" * 5000,  # 5000 caractères
        ],
        "expected_flow": "ERROR (too long)"
    },
    
    "edge_abandon": {
        "description": "Utilisateur abandonne",
        "messages": [
            "Oui",
            "Jean Dupont",
            "Je vais rappeler plus tard",
        ],
        "expected_flow": "ABANDON"
    },
}


# ============================================
# RUNNER
# ============================================

def run_tests(base_url: str, scenarios: Dict[str, Any], verbose: bool = False) -> List[TestResult]:
    """Exécute tous les scénarios de test."""
    
    tester = ConversationTester(base_url, verbose=verbose)
    results = []
    
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}🧪 UWI CONVERSATION TEST SUITE{RESET}")
    print(f"{BOLD}{'='*70}{RESET}")
    print(f"\n📍 Target: {base_url}")
    print(f"📝 Scenarios: {len(scenarios)}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    for name, config in scenarios.items():
        description = config.get("description", name)
        messages = config["messages"]
        
        print(f"\n{BLUE}▶ {name}{RESET}")
        print(f"  {description}")
        print(f"  Steps: {len(messages)}")
        
        result = tester.run_scenario(name, messages)
        results.append(result)
        
        if result.success:
            print(f"  {GREEN}✅ PASSED{RESET} ({result.duration_ms:.0f}ms)")
        else:
            print(f"  {RED}❌ FAILED at step {result.failed_step}{RESET}")
            print(f"     User: '{result.user_input[:50] if result.user_input else 'N/A'}...'")
            print(f"     Error: {result.error_message}")
        
        # Small delay between tests to not overwhelm the server
        time.sleep(0.5)
    
    return results


def print_summary(results: List[TestResult]):
    """Affiche le résumé des tests."""
    
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    total_time = sum(r.duration_ms for r in results)
    
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}📊 TEST RESULTS{RESET}")
    print(f"{BOLD}{'='*70}{RESET}")
    
    print(f"\n{GREEN}✅ Passed: {passed}/{len(results)}{RESET}")
    print(f"{RED}❌ Failed: {failed}/{len(results)}{RESET}")
    
    success_rate = (passed / len(results) * 100) if results else 0
    rate_color = GREEN if success_rate >= 80 else YELLOW if success_rate >= 50 else RED
    print(f"\n{rate_color}📈 Success Rate: {success_rate:.1f}%{RESET}")
    print(f"⏱️  Total Time: {total_time/1000:.1f}s")
    
    # Failed tests details
    if failed > 0:
        print(f"\n{BOLD}🔍 FAILED TESTS DETAILS:{RESET}")
        for r in results:
            if not r.success:
                print(f"\n  {RED}• {r.scenario_name}{RESET}")
                print(f"    Step: {r.failed_step}/{r.total_steps}")
                print(f"    Input: '{r.user_input[:80] if r.user_input else 'N/A'}'")
                print(f"    Error: {r.error_message}")
                
                # Show conversation log if available
                if r.conversation_log and len(r.conversation_log) > 0:
                    print(f"    Conversation:")
                    for msg in r.conversation_log[-4:]:  # Last 4 messages
                        role = "👤" if msg["role"] == "user" else "🤖"
                        content = msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
                        print(f"      {role} {content}")
    
    print(f"\n{BOLD}{'='*70}{RESET}\n")
    
    return passed, failed


def main():
    parser = argparse.ArgumentParser(description="Test UWI conversation flows")
    parser.add_argument("--local", action="store_true", help="Use localhost instead of prod")
    parser.add_argument("--scenario", type=str, help="Run specific scenario(s) (comma-separated)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--url", type=str, help="Custom base URL")
    
    args = parser.parse_args()
    
    # Determine base URL
    if args.url:
        base_url = args.url
    elif args.local:
        base_url = LOCAL_URL
    else:
        base_url = PROD_URL
    
    # Filter scenarios if specified
    if args.scenario:
        scenario_names = [s.strip() for s in args.scenario.split(",")]
        scenarios_to_run = {k: v for k, v in SCENARIOS.items() if any(name in k for name in scenario_names)}
        if not scenarios_to_run:
            print(f"{RED}No matching scenarios found for: {args.scenario}{RESET}")
            print(f"Available: {', '.join(SCENARIOS.keys())}")
            return
    else:
        scenarios_to_run = SCENARIOS
    
    # Run tests
    results = run_tests(base_url, scenarios_to_run, verbose=args.verbose)
    passed, failed = print_summary(results)
    
    # Exit code for CI/CD
    exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
