import os
import discord
from discord import app_commands
from discord.ext import commands
import pymongo
from flask import Flask, request
import threading
import requests

# --- CONFIGURAÇÕES DE AMBIENTE (O RENDER VAI LER DA ABA ENVIRONMENT) ---
TOKEN_BOT = os.getenv("TOKEN_BOT")
CLIENT_SECRET = os.getenv("C3PsFkCtLdNG470dSlNpIEUixIW6086s")
MONGO_URI = os.getenv("mongodb+srv://narutozaborges4021_db_user:eY0V6zFNn7cu38Jc@orache.aiw4pne.mongodb.net/?appName=Orache")
CLIENT_ID = "1470566268850409555" # Seu ID do Discord

# --- CONEXÃO MONGODB ---
client = pymongo.MongoClient(MONGO_URI)
db = client["backup_database"]
collection = db["membros"]

# --- SISTEMA WEB (FLASK) ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot Online - Sistema de Backup Ativo", 200

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "Erro: Código de autorização não encontrado.", 400
    
    # Define a redirect_uri automaticamente baseada no seu link do Render
    redirect_uri = f"https://{request.host}/callback"
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post('https://discord.com/api/v10/oauth2/token', data=data, headers=headers)
    res = r.json()
    
    if 'access_token' in res:
        token = res['access_token']
        user_headers = {'Authorization': f"Bearer {token}"}
        user_info = requests.get('https://discord.com/api/users/@me', headers=user_headers).json()
        
        collection.update_one(
            {"_id": user_info['id']},
            {"$set": {"access_token": token, "username": user_info['username']}},
            upsert=True
        )
        return f"✅ {user_info['username']}, verificado com sucesso!"
    
    return "Erro na verificação.", 400

# --- BOT DISCORD ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Comandos Slash sincronizados para {self.user}")

bot = MyBot()

@bot.tree.command(name="setup", description="Envia o botão de verificação")
@commands.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    # ATENÇÃO: Substitua pelo seu link gerado no Discord Developer Portal
    auth_url = "COLE_O_SEU_LINK_OAUTH2_AQUI"
    
    embed = discord.Embed(
        title="🛡️ Verificação de Segurança",
        description="Clique no botão abaixo para se verificar e garantir seu backup.",
        color=discord.Color.blue()
    )
    
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Verificar", url=auth_url, style=discord.ButtonStyle.link))
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="puxar", description="Restaura os membros")
@commands.has_permissions(administrator=True)
async def puxar(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Restaurando membros...", ephemeral=True)
    membros = collection.find()
    sucesso, falha = 0, 0
    
    for membro in membros:
        url = f"https://discord.com/api/v10/guilds/{interaction.guild_id}/members/{membro['_id']}"
        headers = {"Authorization": f"Bot {TOKEN_BOT}"}
        r = requests.put(url, headers=headers, json={"access_token": membro['access_token']})
        if r.status_code in [201, 204]: sucesso += 1
        else: falha += 1
            
    await interaction.edit_original_response(content=f"✅ Sucessos: {sucesso} | ❌ Falhas: {falha}")

# --- FUNÇÃO PARA RODAR O FLASK NA PORTA DO RENDER ---
def run_flask():
    # O Render exige ler a porta da variável de ambiente 'PORT'
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.setDaemon(True) # Garante que a thread feche se o bot fechar
    t.start()
    bot.run(TOKEN_BOT)
