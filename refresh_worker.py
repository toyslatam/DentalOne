# refresh_worker.py

from refresh_logic import refresh_tokens_once

if __name__ == "__main__":
    print("🔄 Worker de tokens iniciado...")
    refresh_tokens_once()
