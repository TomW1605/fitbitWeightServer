import secrets
from typing import Optional

import requests
import datetime
import base64
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.requests import Request


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env')

    client_id: SecretStr
    client_secret: SecretStr

    authorization_url: str = Field(default='https://www.fitbit.com/oauth2/authorize')
    token_url: str = Field(default='https://www.fitbit.com/oauth2/token')
    weight_log_url: str = Field(default='https://api.fitbit.com/1/user/-/body/log/weight.json')

    base_url: str = Field(default='https://localhost:5000/')
    redirect_url: Optional[str] = None


config = Settings()

if config.base_url.endswith('/'):
    config.base_url = config.base_url[:-1]

if config.redirect_url is None:
    config.redirect_url = config.base_url + '/callback'

app = FastAPI(root_path="/"+config.base_url.split('/', 3)[-1])
# if config.base_url.count('/') > 2:
#     app.config['SCRIPT_NAME'] = config.base_url.split('/', 3)[-1]
#     app.config['APPLICATION_ROOT'] = config.base_url.split('/', 3)[-1]

# Dictionary to store user keys and Fitbit access tokens
user_keys = {}

@app.get("/")
async def home():
    return RedirectResponse(url=f"{config.base_url}/login")

@app.get("/login")
async def login():
    # Generate a unique key for the user
    user_key = secrets.token_urlsafe(16)

    # Store the user key temporarily
    session_key = secrets.token_urlsafe(16)
    user_keys[session_key] = {'access_token': None}

    authorization_redirect_url = f"{config.authorization_url}?client_id={config.client_id.get_secret_value()}&redirect_uri={config.redirect_url}&response_type=code&scope=weight&state={session_key}"
    return RedirectResponse(url=authorization_redirect_url)

@app.get("/callback")
async def callback(request: Request):
    authorization_code = request.query_params.get('code')
    session_key = request.query_params.get('state')

    data = {
        'client_id': config.client_id.get_secret_value(),
        'code': authorization_code,
        'grant_type': 'authorization_code',
        'redirect_uri': config.redirect_url,
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + base64.b64encode(f"{config.client_id.get_secret_value()}:{config.client_secret.get_secret_value()}".encode()).decode()
    }

    response = requests.post(config.token_url, headers=headers, data=data)

    print(response.json())

    if response.status_code == 200:
        access_token = response.json()['access_token']
        user_keys[session_key]['access_token'] = access_token
        return f"Logged in! Your user key is: {session_key}"
    else:
        return response.json()
        # raise HTTPException(status_code=400, detail='Error getting access token')

@app.post("/add_weight")
async def add_weight(request: Request):
    form_data = await request.form()
    user_key = form_data.get('user_key')
    weight = float(form_data.get('weight'))

    # Check if the user key exists and has an associated access token
    if user_key in user_keys and user_keys[user_key]['access_token']:
        access_token = user_keys[user_key]['access_token']

        weight_data = {
            'date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'weight': weight,
        }

        headers = {
            'Authorization': 'Bearer ' + access_token,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.post(config.weight_log_url, headers=headers, data=weight_data)

        if response.status_code == 201:
            return 'Weight data added successfully!'
        else:
            raise HTTPException(status_code=400, detail='Error adding weight data')
    else:
        raise HTTPException(status_code=401, detail='Unauthorized')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
