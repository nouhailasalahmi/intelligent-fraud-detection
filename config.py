import os

try:
    from dotenv import load_dotenv
    # Charger les variables d'environnement depuis un fichier .env si présent
    load_dotenv()
except ImportError:
    pass

# ============================================
# Paramètres de génération des données
# ============================================

n_customers = int(os.getenv("N_CUSTOMERS", 1000))
n_transactions = int(os.getenv("N_TRANSACTIONS", 100000))
n_history = int(os.getenv("N_HISTORY", 50))
is_fraud_ratio = float(os.getenv("IS_FRAUD_RATIO", 0.05))


# ============================================
# Valeurs possibles pour les features catégorielles
# ============================================

Devices = ["POS Terminal", "Mobile", "Laptop"]
Payment_Methods = ["credit_card", "debit_card", "paypal", "bank_transfer"]

# Compatibilité device -> moyens de paiement réalistes
# (PayPal et virement ne passent pas sur un terminal physique)
Device_Payment_Compatibility = {
    "POS Terminal": ["credit_card", "debit_card"],
    "Mobile": ["credit_card", "debit_card", "paypal", "bank_transfer"],
    "Laptop": ["credit_card", "debit_card", "paypal", "bank_transfer"],
}

Morrocan_Cities = [
    "Casablanca", "Rabat", "Marrakech", "Fès", "Tanger",
    "Agadir", "Meknès", "Oujda", "Kénitra", "Tétouan",
    "Salé", "Nador", "Mohammédia", "El Jadida", "Béni Mellal",
    "Khouribga", "Taza", "Settat", "Larache", "Khemisset",
    "Guelmim", "Berrechid", "Ouarzazate", "Essaouira", "Safi",
    "Errachidia", "Al Hoceïma", "Ifrane", "Chefchaouen", "Dakhla",
    "Laâyoune", "Sidi Kacem", "Taroudant", "Tiznit", "Azrou"
]

Foreign_Countries = [
    "France", "Espagne", "Belgique", "Italie", "Allemagne",
    "Pays-Bas", "Suisse", "Royaume-Uni", "Portugal",
    "Émirats Arabes Unis", "Arabie Saoudite", "Qatar", "Turquie",
    "États-Unis", "Canada",
    "Tunisie", "Algérie", "Égypte", "Sénégal", "Côte d'Ivoire",
    "Chine", "Russie"
]

# Villes par pays : garantit la cohérence pays <-> ville
# ⚠️ La clé du pays d'origine doit être EXACTEMENT la valeur de customer["usual_country"]
Cities_By_Country = {
    "Maroc": Morrocan_Cities,
    "France": ["Paris", "Lyon", "Marseille", "Lille"],
    "Espagne": ["Madrid", "Barcelone", "Valence"],
    "Belgique": ["Bruxelles", "Anvers", "Liège"],
    "Italie": ["Rome", "Milan", "Naples"],
    "Allemagne": ["Berlin", "Munich", "Francfort"],
    "Pays-Bas": ["Amsterdam", "Rotterdam", "La Haye"],
    "Suisse": ["Genève", "Zurich", "Lausanne"],
    "Royaume-Uni": ["Londres", "Manchester", "Birmingham"],
    "Portugal": ["Lisbonne", "Porto", "Faro"],
    "Émirats Arabes Unis": ["Dubaï", "Abu Dhabi", "Sharjah"],
    "Arabie Saoudite": ["Riyad", "Djeddah", "La Mecque"],
    "Qatar": ["Doha", "Al Rayyan", "Al Wakrah"],
    "Turquie": ["Istanbul", "Ankara", "Izmir"],
    "États-Unis": ["New York", "Los Angeles", "Chicago", "Miami"],
    "Canada": ["Montréal", "Toronto", "Vancouver"],
    "Tunisie": ["Tunis", "Sfax", "Sousse"],
    "Algérie": ["Alger", "Oran", "Constantine"],
    "Égypte": ["Le Caire", "Alexandrie", "Louxor"],
    "Sénégal": ["Dakar", "Thiès", "Saint-Louis"],
    "Côte d'Ivoire": ["Abidjan", "Yamoussoukro", "Bouaké"],
    "Chine": ["Shanghai", "Pékin", "Shenzhen"],
    "Russie": ["Moscou", "Saint-Pétersbourg", "Kazan"],
}


# ============================================
# Distribution des montants de transaction
# ============================================

# Distribution log-normale
TARGET_MEDIAN_AMOUNT = float(os.getenv("TARGET_MEDIAN_AMOUNT", 250))   # montant "typique" attendu (médiane réelle, pas le paramètre log)
AMOUNT_SIGMA = float(os.getenv("AMOUNT_SIGMA", 0.9))                   # dispersion (plus grand = plus de gros montants rares)


# ============================================
# Configuration Kafka
# ============================================

TOPIC = os.getenv("KAFKA_TOPIC", os.getenv("TOPIC", "transactions"))
BOOTSTRAP_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVER", os.getenv("BOOTSTRAP_SERVER", "localhost:9092"))
KAFKA_AUTO_OFFSET_RESET = os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest")  # "latest" pour le temps réel, "earliest" pour rejouer


# ============================================
# Configuration PostgreSQL
# ============================================

DB_HOST = os.getenv("DB_HOST", "localhost")      
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "transactions_db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "userpassword")


# ============================================
# Configuration LLM
# ============================================

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # Options : "ollama", "openai", "mistral", "anthropic"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Adaptation automatique pour conteneurs Docker accédant à Ollama sur l'hôte Windows
if (os.path.exists("/.dockerenv") or os.getenv("IS_DOCKER") == "true") and ("localhost" in OLLAMA_BASE_URL or "127.0.0.1" in OLLAMA_BASE_URL):
    OLLAMA_BASE_URL = OLLAMA_BASE_URL.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")

USE_AGENT = os.getenv("USE_AGENT", "True").lower() in ("true", "1", "yes")
MULTI_AGENT_MODE = os.getenv("MULTI_AGENT_MODE", "True").lower() in ("true", "1", "yes")


# ============================================
# Configuration Réponses Automatisées & Conformité
# ============================================

ACTIONS_TOPIC = os.getenv("KAFKA_ACTIONS_TOPIC", os.getenv("ACTIONS_TOPIC", "fraud-actions"))

# Seuils de confiance pour déclenchement des actions
CONFIDENCE_BLOCK_THRESHOLD = float(os.getenv("CONFIDENCE_BLOCK_THRESHOLD", 0.85))
CONFIDENCE_REVIEW_THRESHOLD = float(os.getenv("CONFIDENCE_REVIEW_THRESHOLD", 0.60))

# Conformité DSP2 (Montant d'exemption SCA en EUR/MAD)
DSP2_EXEMPTION_THRESHOLD_AMOUNT = float(os.getenv("DSP2_EXEMPTION_THRESHOLD_AMOUNT", 30.0))

# Dossier des rapports SAR (Suspicious Activity Report)
REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")