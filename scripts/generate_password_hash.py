#!/usr/bin/env python3
"""
Génère un hash bcrypt pour remplir tenant_users.password_hash.
Usage: python3 scripts/generate_password_hash.py [mot_de_passe]
       python3 scripts/generate_password_hash.py "Secret#2026"
"""
import sys
import bcrypt

def main():
    pwd = (sys.argv[1] if len(sys.argv) > 1 else "Secret#2026").encode("utf-8")
    h = bcrypt.hashpw(pwd, bcrypt.gensalt()).decode()
    print(h)

if __name__ == "__main__":
    main()
