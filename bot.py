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
MONGO_URI = os.getenv("MONGO_URI")
CLIENT_ID = "1470566268850409555" # Seu ID do Discord

# --- CONEXÃO MONGODB ---
# Aqui ele usa o link que você cadastrou no Render com a sua senha
client = pymongo.MongoClient(MONGO_URI)
db = client["backup_database"]
collection = db["membros"]

# --- SISTEMA WEB (FLASK) PARA O REDIRECT E O UPTIMEROBOT ---
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
        # Pega info do usuário para saber quem é
        user_headers = {'Authorization': f"Bearer {token}"}
        user_info = requests.get('https://discord.com/api/users/@me', headers=user_headers).json()
        
        # SALVA NO MONGODB (Se o ID já existir, ele só atualiza o token)
        collection.update_one(
            {"_id": user_info['id']},
            {"$set": {"access_token": token, "username": user_info['username']}},
            upsert=True
        )
        return f"✅ {user_info['username']}, você foi verificado! Seus dados foram salvos para o backup."
    
    return "Erro ao processar verificação. Tente novamente.", 400

# --- BOT DISCORD ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Comandos Slash sincronizados para {self.user}")

bot = MyBot()

@bot.tree.command(name="setup", description="Envia o botão de verificação")
@commands.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    # ATENÇÃO: Você vai gerar esse link no OAuth2 -> URL Generator do Discord
    # e depois trocar esse texto abaixo pelo seu link real.
    auth_url = "COLE_O_LINK_GERADO_NO_DISCORD_AQUI"
    
    embed = discord.Embed(
        title="🛡️ Verificação de Segurança",
        description="Clique no botão abaixo para se verificar e garantir que você não perca acesso ao servidor.",
        color=discord.Color.green()
    )
    
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Verificar", url=auth_url, style=discord.ButtonStyle.link))
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="puxar", description="Restaura os membros do banco de dados")
@commands.has_permissions(administrator=True)
async def puxar(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Iniciando restauração... Isso pode demorar.", ephemeral=True)
    
    membros = collection.find()
    sucesso = 0
    falha = 0
    
    for membro in membros:
        user_id = membro['_id']
        token = membro['access_token']
        
        url = f"https://discord.com/api/v10/guilds/{interaction.guild_id}/members/{user_id}"
        headers = {"Authorization": f"Bot {TOKEN_BOT}"}
        body = {"access_token": token}
        
        r = requests.put(url, headers=headers, json=body)
        
        if r.status_code in [201, 204]:
            sucesso += 1
        else:
            falha += 1
            
    await interaction.edit_original_response(content=f"✅ Concluído!\n👤 Sucessos: {sucesso}\n❌ Falhas: {falha}")

# --- RODAR FLASK (SITE) E BOT JUNTOS ---
def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.start()
    bot.run(TOKEN_BOT)
