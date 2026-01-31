#!/usr/bin/env python3
"""
Test direct de chargement Google Calendar depuis Railway
"""
import requests

BASE_URL = "https://agent-googleserviceaccountbase64.up.railway.app"

print("="*60)
print("TEST GOOGLE CALENDAR SUR RAILWAY")
print("="*60)

# Test 1: Variables présentes ?
print("\n1. Variables d'environnement")
r = requests.get(f"{BASE_URL}/debug/env-vars")
data = r.json()
print(f"   google_keys: {data.get('google_keys', [])}")
print(f"   GOOGLE_SERVICE_ACCOUNT_BASE64 present: {data.get('google_values_present', {}).get('GOOGLE_SERVICE_ACCOUNT_BASE64', False)}")

# Test 2: Health
print("\n2. Health check")
r = requests.get(f"{BASE_URL}/health")
data = r.json()
print(f"   service_account_file: {data.get('service_account_file')}")
print(f"   file_exists: {data.get('file_exists')}")
print(f"   calendar_id_set: {data.get('calendar_id_set')}")

# Test 3: Test calendar endpoint
print("\n3. Test calendar")
r = requests.get(f"{BASE_URL}/api/vapi/test-calendar")
data = r.json()
print(f"   env_var_present: {data.get('env_var_present')}")
print(f"   env_var_length: {data.get('env_var_length')}")
print(f"   file_exists: {data.get('file_exists')}")
print(f"   slots_available: {data.get('slots_available')}")

print("\n" + "="*60)
if data.get('file_exists'):
    print("✅ GOOGLE CALENDAR CONNECTÉ !")
else:
    print("❌ GOOGLE CALENDAR PAS CONNECTÉ")
    print("Cause probable: startup event n'a pas appelé load_google_credentials()")
print("="*60)
