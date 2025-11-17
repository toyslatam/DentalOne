# refresh_logic.py

import os
from intuitlib.client import AuthClient
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_API_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

APPS = {
    "app_a": {
        "CLIENT_ID": os.environ["APP_A_CLIENT_ID"],
        "CLIENT_SECRET": os.environ["APP_A_CLIENT_SECRET"],
    },
    "app_b": {
        "CLIENT_ID": os.environ["APP_B_CLIENT_ID"],
        "CLIENT_SECRET": os.environ["APP_B_CLIENT_SECRET"],
    },


    "app_c": {
        "CLIENT_ID": os.environ["APP_C_CLIENT_ID"],
        "CLIENT_SECRET": os.environ["APP_C_CLIENT_SECRET"],
    }
}

RENDER_DOMAIN = os.environ.get("RENDER_DOMAIN", "https://quickbooks-webhook.onrender.com")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

def refresh_tokens_once():
    print("🚀 Ejecutando renovación manual de tokens")
    for app_id, cfg in APPS.items():
        try:
            response = supabase.table("tokens").select("*").eq("app_id", app_id).execute()
            data = response.data
            if not data:
                print(f"⛔ No hay tokens guardados en Supabase para {app_id}")
                continue

            tokens = data[0]
            refresh_token = tokens.get("refresh_token")
            realm_id = tokens.get("realm_id")

            if not refresh_token:
                print(f"⛔ No refresh_token disponible para {app_id}")
                continue

            redirect_uri = f'{RENDER_DOMAIN}/{app_id}/callback'
            auth_client = AuthClient(
                client_id=cfg["CLIENT_ID"],
                client_secret=cfg["CLIENT_SECRET"],
                redirect_uri=redirect_uri,
                environment=ENVIRONMENT
            )

            auth_client.refresh(refresh_token)

            new_tokens = {
                "app_id": app_id,
                "access_token": auth_client.access_token,
                "refresh_token": auth_client.refresh_token,
                "realm_id": realm_id
            }

            supabase.table("tokens").upsert(new_tokens).execute()
            print(f"✅ Tokens actualizados en Supabase para {app_id}")

        except Exception as e:
            print(f"❌ Error renovando tokens para {app_id}:", str(e))
