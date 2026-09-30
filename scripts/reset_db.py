"""
Script utilitaire pour réinitialiser la base de données PostgreSQL.
Vide toutes les tables et recrée les contraintes d'unicité.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import create_tables, clear_all_tables


def main():
    try:
        print("Connexion et initialisation du schéma...")
        create_tables()
        print("Vidage des tables en cours (TRUNCATE CASCADE)...")
        clear_all_tables()
        print("Opération terminée avec succès : la base est prête et 100% propre.")
    except Exception as e:
        print(f"Erreur lors de la réinitialisation de la base : {e}")
        print("Vérifiez que le conteneur PostgreSQL est bien démarré (docker compose up -d data_base).")


if __name__ == "__main__":
    main()
