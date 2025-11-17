import time
import hmac
import base64
import hashlib
import json
import os
from flask import Flask, request, abort
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import requests
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

APPS = {
    "app_a": {
        "CLIENT_ID": 'ABpiC27UvCiXPjumk5T54cZWy4rxjkvc1rgxGpDx6uyfzndQeY',
        "CLIENT_SECRET": 'amnhCOVk017cvhE9pkK1WSxD07Lj5AHVLoP4695m',
        "WEBHOOK_VERIFICATION_TOKEN": 'a8d34ea3-6986-4c2a-81be-ccd9e3c052b5',
        "POWER_AUTOMATE_URL": "https://prod-113.westus.logic.azure.com:443/workflows/c55f68d9f1374b9285645d9e6e31ca8c/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=Y9uDfvLhBlo-4KFqndYPp4tt7OX7ZAyvEr3yH2FJhhA"
    },
    "app_b": {
        "CLIENT_ID": 'ABuIIPvX74z4HLYw4z3F4qZ1t7ndjVPF3l464QhS0YinYOa972',
        "CLIENT_SECRET": '0MUUP41ETTs3peH5zZqtHj5xzAztjsMj2wdRO6ia',
        "WEBHOOK_VERIFICATION_TOKEN": '9d8013d7-683d-4ecf-a705-7bcfa3afae67',
        "POWER_AUTOMATE_URL": "https://prod-53.westus.logic.azure.com:443/workflows/12949052ccd34d338e348eb2c8b656e9/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=t0JxROYwoiAQAoTuHi3ZH-2_2JTPrqweKsiL2dGY2PQ"
    },

     "app_c": {
        "CLIENT_ID": 'ABFWZPp7l3WLsID0ZTEKNhD2YIjuUWtwW0CJkpdSjzWxTDsSbH',
        "CLIENT_SECRET": 'QsFzKamxvFvTkvZnYscxm9CniaKHG5dDqJOQ9t2G',
        "WEBHOOK_VERIFICATION_TOKEN": 'bdcbda82-774f-4186-bd72-9f743e2a8f5e',
        "POWER_AUTOMATE_URL": "https://prod-118.westus.logic.azure.com:443/workflows/01bb71c83893400dbd790f10e6e76aa2/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=V4jcUC9_jdrlumGJHfIqSxNm6HZlAo36ZLdx_bndJgI"
    }
}

ENVIRONMENT = 'production'
RENDER_DOMAIN = 'https://quickbooks-webhook.onrender.com'


@app.route('/')
def index():
    return '✅ Servidor Flask activo en Render', 200


@app.route('/<app_id>/callback')
def callback(app_id):
    if app_id not in APPS:
        return '❌ App ID no reconocida', 400

    code = request.args.get('code')
    realm_id = request.args.get('realmId')
    if not code:
        return '❌ Código no recibido', 400

    cfg = APPS[app_id]
    redirect_uri = f'{RENDER_DOMAIN}/{app_id}/callback'

    auth_client = AuthClient(
        client_id=cfg["CLIENT_ID"],
        client_secret=cfg["CLIENT_SECRET"],
        redirect_uri=redirect_uri,
        environment=ENVIRONMENT
    )

    try:
        auth_client.get_bearer_token(code)
        access_token = auth_client.access_token
        refresh_token = auth_client.refresh_token

        supabase.table("tokens").upsert({
            "app_id": app_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "realm_id": realm_id
        }).execute()

        print(f"✅ Tokens guardados en Supabase para {app_id}")
        return f'✅ Tokens guardados en Supabase para {app_id}', 200

    except Exception as e:
        print(f"❌ Error en {app_id}:", str(e))
        return '❌ Error al obtener token', 500


@app.route('/<app_id>/webhook', methods=['POST'])
def webhook(app_id):
    if app_id not in APPS:
        return '❌ App ID no reconocida', 400

    raw_body = request.get_data()
    sig_header = request.headers.get('intuit-signature')
    cfg = APPS[app_id]

    computed_sig = base64.b64encode(hmac.new(
        cfg["WEBHOOK_VERIFICATION_TOKEN"].encode('utf-8'),
        raw_body,
        hashlib.sha256
    ).digest()).decode()

    if sig_header != computed_sig:
        print(f"❌ Firma inválida en {app_id}")
        abort(401)

    payload = request.json
    print(f"✅ Webhook recibido para {app_id}: {payload}")

    try:
        response = requests.post(cfg["POWER_AUTOMATE_URL"], json=payload)
        print(f"📤 Enviado a Power Automate {app_id}: {response.status_code}")
        print(f"📦 Respuesta de Power Automate: {response.text}")
        if response.status_code >= 400:
            print(f"⚠️ Power Automate respondió con error para {app_id}")
    except Exception as e:
        print(f"❌ Error al hacer POST a Power Automate para {app_id}:", str(e))

    return 'OK', 200


@app.route('/<app_id>/get-token')
def get_token(app_id):
    try:
        response = supabase.table("tokens").select("*").eq("app_id", app_id).execute()
        data = response.data
        if not data:
            return f"❌ No hay tokens en Supabase para {app_id}", 404
        tokens = data[0]
        return tokens.get("access_token", ""), 200
    except Exception as e:
        return f"❌ Error al leer token desde Supabase para {app_id}: {str(e)}", 500


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


@app.route('/refresh-tokens', methods=['GET'])
def refresh_tokens_endpoint():
    try:
        refresh_tokens_once()
        return '🔄 Proceso de renovación ejecutado', 200
    except Exception as e:
        return f'❌ Error al renovar tokens: {str(e)}', 500


@app.route('/auth-urls')
def auth_urls():
    html = "<h2>🔗 Enlaces de autorización:</h2>"
    for app_id, cfg in APPS.items():
        redirect_uri = f'{RENDER_DOMAIN}/{app_id}/callback'
        auth_client = AuthClient(
            client_id=cfg["CLIENT_ID"],
            client_secret=cfg["CLIENT_SECRET"],
            redirect_uri=redirect_uri,
            environment=ENVIRONMENT
        )
        auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])
        html += f"<p><strong>{app_id}:</strong> <a href='{auth_url}' target='_blank'>{auth_url}</a></p>"
    return html


if __name__ == '__main__':
    print("🚀 Iniciando servidor Flask en Render...")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
