import os
from anthropic import Anthropic
import streamlit as st
import io
import google.generativeai as genai
from PIL import Image
import datetime
from pymongo import MongoClient
from bson import ObjectId
import json
from google.genai import types
import PyPDF2
from pptx import Presentation
import docx
import openai
from typing import List, Dict, Tuple
import hashlib
import pandas as pd
import re
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Text
import requests
from dotenv import load_dotenv
# Adicione estas importações após as outras importações
import networkx as nx
import matplotlib.pyplot as plt
import graphviz
from graphviz import Digraph
import tempfile
import base64
from io import BytesIO
import matplotlib.patches as patches
import numpy as np
import urllib.parse
load_dotenv()

# Configuração inicial
st.set_page_config(
    layout="wide",
    page_title="Agente PMO",
    page_icon="🤖"
)

import os
import PyPDF2
import pdfplumber
from pathlib import Path

# --- CONFIGURAÇÃO DOS MODELOS ---
# Configuração da API do Anthropic (Claude)
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
if anthropic_api_key:
    anthropic_client = Anthropic(api_key=anthropic_api_key)
else:
    st.error("ANTHROPIC_API_KEY não encontrada nas variáveis de ambiente")
    anthropic_client = None

# Configuração da API do Gemini
gemini_api_key = os.getenv("GEM_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    modelo_vision = genai.GenerativeModel("gemini-2.0-flash", generation_config={"temperature": 0.0})
    modelo_texto = genai.GenerativeModel("gemini-2.0-flash")
else:
    st.error("GEM_API_KEY não encontrada nas variáveis de ambiente")
    modelo_vision = None
    modelo_texto = None

import os
import PyPDF2
import pdfplumber
from pathlib import Path


# --- Sistema de Autenticação MELHORADO ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# Dados de usuário (em produção, isso deve vir de um banco de dados seguro)
users_db = {
    "admin": {
        "password": make_hashes("senha1234"),
        "squad": "admin",
        "nome": "Administrador"
    }
}

# Conexão MongoDB
client = MongoClient("mongodb+srv://gustavoromao3345:RqWFPNOJQfInAW1N@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true")
db = client['agentes_personalizados']
collection_agentes = db['agentes']
collection_conversas = db['conversas']
collection_usuarios = db['usuarios']  # Nova coleção para usuários
collection_playbook_logs = db['playbook_logs']  # Nova coleção para logs do playbook


try:
    client_cursos = MongoClient(
        "mongodb+srv://julialedo_db_user:hr7vHI5EjMwuRT9X@cluster0.u0sm02b.mongodb.net/cursos_db?retryWrites=true&w=majority&appName=Cluster0",
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=10000
    )
    
    # Testar conexão
    client_cursos.admin.command('ping')
    
    db_cursos = client_cursos['cursos_db']
    collection_cursos = db_cursos['cursos']
    collection_categorias = db_cursos['categorias']
    
    print("✅ Conexão com banco de cursos estabelecida!")
    
except Exception as e:
    st.error(f"❌ Erro na conexão com banco de cursos: {str(e)}")
    # Criar variáveis vazias para evitar erros
    client_cursos = None
    db_cursos = None
    collection_cursos = None
    collection_categorias = None


# --- FUNÇÕES DE CADASTRO E LOGIN ---
def criar_usuario(email, senha, nome, squad):
    """Cria um novo usuário no banco de dados"""
    try:
        # Verificar se usuário já existe
        if collection_usuarios.find_one({"email": email}):
            return False, "Usuário já existe"
        
        # Criar hash da senha
        senha_hash = make_hashes(senha)
        
        novo_usuario = {
            "email": email,
            "senha": senha_hash,
            "nome": nome,
            "squad": squad,
            "data_criacao": datetime.datetime.now(),
            "ultimo_login": None,
            "ativo": True
        }
        
        result = collection_usuarios.insert_one(novo_usuario)
        return True, "Usuário criado com sucesso"
        
    except Exception as e:
        return False, f"Erro ao criar usuário: {str(e)}"

def verificar_login(email, senha):
    """Verifica as credenciais do usuário"""
    try:
        # Primeiro verificar no banco de dados
        usuario = collection_usuarios.find_one({"email": email, "ativo": True})
        
        if usuario:
            if check_hashes(senha, usuario["senha"]):
                # Atualizar último login
                collection_usuarios.update_one(
                    {"_id": usuario["_id"]},
                    {"$set": {"ultimo_login": datetime.datetime.now()}}
                )
                return True, usuario, "Login bem-sucedido"
            else:
                return False, None, "Senha incorreta"
        
        # Fallback para usuários hardcoded (apenas para admin)
        if email in users_db:
            user_data = users_db[email]
            if check_hashes(senha, user_data["password"]):
                usuario_fallback = {
                    "email": email,
                    "nome": user_data["nome"],
                    "squad": user_data["squad"],
                    "_id": "admin"
                }
                return True, usuario_fallback, "Login bem-sucedido"
            else:
                return False, None, "Senha incorreta"
        
        return False, None, "Usuário não encontrado"
        
    except Exception as e:
        return False, None, f"Erro no login: {str(e)}"

def get_current_user():
    """Retorna o usuário atual da sessão"""
    return st.session_state.get('user', {})

def get_current_squad():
    """Retorna o squad do usuário atual"""
    user = get_current_user()
    return user.get('squad', 'unknown')

def login():
    """Formulário de login e cadastro"""
    st.title("🔒 Agente PMO - Login")
    
    tab_login, tab_cadastro = st.tabs(["Login", "Cadastro"])
    
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if email and password:
                    sucesso, usuario, mensagem = verificar_login(email, password)
                    if sucesso:
                        st.session_state.logged_in = True
                        st.session_state.user = usuario
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error(mensagem)
                else:
                    st.error("Por favor, preencha todos os campos")
    
    with tab_cadastro:
        with st.form("cadastro_form"):
            st.subheader("Criar Nova Conta")
            
            nome = st.text_input("Nome Completo")
            email = st.text_input("Email")
            squad = st.selectbox(
                "Selecione seu Squad:",
                ["Syngenta", "SME", "Enterprise"],
                help="Escolha o squad ao qual você pertence"
            )
            senha = st.text_input("Senha", type="password")
            confirmar_senha = st.text_input("Confirmar Senha", type="password")
            
            submit_cadastro = st.form_submit_button("Criar Conta")
            
            if submit_cadastro:
                if not all([nome, email, squad, senha, confirmar_senha]):
                    st.error("Por favor, preencha todos os campos")
                elif senha != confirmar_senha:
                    st.error("As senhas não coincidem")
                elif len(senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres")
                else:
                    sucesso, mensagem = criar_usuario(email, senha, nome, squad)
                    if sucesso:
                        st.success("Conta criada com sucesso! Faça login para continuar.")
                    else:
                        st.error(mensagem)


# Verificar se o usuário está logado
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()



# --- FUNÇÕES PARA CURSOS ---
def inicializar_cursos_base():
    """Inicializa a estrutura de cursos no banco de dados"""
    try:
        # Verificar se a conexão está disponível
        if not collection_categorias:
            return False, "❌ Conexão com banco de cursos não disponível"
        
        # Verificar se já existe alguma categoria
        if collection_categorias.count_documents({}) == 0:
            return True, "✅ Estrutura de cursos já existe!"
        else:
            return True, "✅ Estrutura de cursos já existe!"
            
    except Exception as e:
        return False, f"❌ Erro ao verificar cursos: {str(e)}"

def obter_categorias():
    """Retorna todas as categorias de cursos"""
    try:
        if not collection_categorias:
            return []
        return list(collection_categorias.find(
            {"tipo": "categoria", "ativo": True}
        ).sort("ordem", 1))
    except Exception as e:
        st.warning(f"Erro ao obter categorias: {str(e)}")
        return []

def obter_subpastas(categoria_id):
    """Retorna subpastas de uma categoria"""
    try:
        if not collection_categorias:
            return []
        return list(collection_categorias.find({
            "tipo": "subpasta", 
            "categoria_id": categoria_id,
            "ativo": True
        }).sort("ordem", 1))
    except Exception as e:
        st.warning(f"Erro ao obter subpastas: {str(e)}")
        return []

def obter_cursos(subpasta_id=None):
    """Retorna cursos de uma subpasta ou todos os cursos"""
    try:
        if not collection_cursos:
            return []
        
        query = {"ativo": True}
        if subpasta_id:
            query["subpasta_id"] = subpasta_id
        
        return list(collection_cursos.find(query).sort("data_publicacao", -1))
    except Exception as e:
        st.warning(f"Erro ao obter cursos: {str(e)}")
        return []

def obter_todos_cursos_formatados():
    """
    Obtém todos os cursos do banco e formata para passar para a IA
    """
    try:
        if not collection_cursos:
            return "Nenhum curso disponível no banco de dados."
        
        todos_cursos = obter_cursos()
        
        if not todos_cursos:
            return "Nenhum curso cadastrado no sistema."
        
        texto = "LISTA COMPLETA DE CURSOS DISPONÍVEIS:\n\n"
        
        for i, curso in enumerate(todos_cursos, 1):
            titulo = curso.get('titulo', 'Curso sem título')
            descricao = curso.get('descricao', 'Descrição não disponível')
            duracao = curso.get('duracao', 'Duração não informada')
            nivel = curso.get('nivel', 'Nível não informado')
            tags = ", ".join(curso.get('tags', [])) if curso.get('tags') else "Sem tags"
            link = curso.get('link_drive', 'Link não disponível')
            
            texto += f"{i}. {titulo}\n"
            texto += f"   Descrição: {descricao}\n"
            texto += f"   Nível: {nivel} | Duração: {duracao}\n"
            texto += f"   Tags: {tags}\n"
            texto += f"   Link: {link}\n\n"
        
        return texto
        
    except Exception as e:
        return f"Erro ao obter cursos: {str(e)}"

def selecionar_curso_com_ia(funcao, cargo, tasks_exemplo):
    """
    Usa o Gemini para analisar todos os cursos e selecionar o mais relevante
    """
    try:
        if not modelo_texto:
            return None
        
        # Obter todos os cursos formatados
        cursos_texto = obter_todos_cursos_formatados()
        
        prompt = f"""
        Você é um especialista em desenvolvimento de carreira e treinamento.
        
        ANALISE O PERFIL ABAIXO:
        - Função: {funcao}
        - Cargo: {cargo}
        - Tasks/Responsabilidades: {tasks_exemplo}
        
        E ESTA LISTA COMPLETA DE CURSOS DISPONÍVEIS:
        {cursos_texto}
        
        SUA TAREFA:
        1. Analise o perfil profissional
        2. Analise TODOS os cursos disponíveis
        3. Selecione o CURSO MAIS RELEVANTE para este perfil
        4. Retorne APENAS o número do curso escolhido (ex: "1", "2", "3")
        
        CRITÉRIOS DE SELEÇÃO:
        - Relevância para a função
        - Adequação ao nível do cargo
        - Aplicabilidade nas tasks mencionadas
        - Tags que correspondam ao perfil
        
        RETORNE APENAS O NÚMERO DO CURSO. Exemplo: "3"
        """
        
        response = modelo_texto.generate_content(prompt)
        numero_curso = response.text.strip()
        
        # Verificar se é um número válido
        if numero_curso.isdigit():
            # Obter cursos novamente para pegar o curso correto
            todos_cursos = obter_cursos()
            idx = int(numero_curso) - 1  # Converter para índice 0-based
            
            if 0 <= idx < len(todos_cursos):
                return todos_cursos[idx]
        
        # Se falhou, retornar o primeiro curso
        todos_cursos = obter_cursos()
        return todos_cursos[0] if todos_cursos else None
        
    except Exception as e:
        st.warning(f"⚠️ Erro ao selecionar curso com IA: {str(e)}")
        # Fallback: retornar primeiro curso
        todos_cursos = obter_cursos()
        return todos_cursos[0] if todos_cursos else None    

# --- FUNÇÕES PARA PLAYBOOK ---
def processar_playbook(agente_id, instrucao_usuario, base_conhecimento_atual, elemento_tipo="base_conhecimento"):
    """
    Processa uma instrução do playbook usando Gemini para modificar a base de conhecimento
    """
    if not modelo_playbook or not gemini_api_key:
        return None, "API do Gemini não configurada"
    
    try:
        prompt = f"""
        Você é um assistente especializado em edição de documentos de base de conhecimento.
        
        BASE DE CONHECIMENTO ATUAL:
        {base_conhecimento_atual}
        
        INSTRUÇÃO DO USUÁRIO:
        {instrucao_usuario}
        
        TAREFA:
        1. Analise a base de conhecimento atual
        2. Aplique a instrução do usuário
        3. Retorne APENAS a nova versão da base de conhecimento, sem explicações
        
        REGRAS:
        - Mantenha o estilo e formato original
        - Não adicione comentários ou explicações
        - Só retorne o texto revisado
        - Se a instrução for para remover algo, remova completamente
        - Se for para adicionar, adicione de forma coerente
        - Preserve a estrutura geral do documento
        
        NOVA BASE DE CONHECIMENTO (apenas o texto):
        """
        
        response = modelo_playbook.generate_content(prompt)
        nova_base = response.text.strip()
        
        # Registrar log da alteração
        log_entry = {
            "agente_id": agente_id,
            "usuario": get_current_user().get('email', 'unknown'),
            "squad": get_current_squad(),
            "elemento_tipo": elemento_tipo,
            "instrucao_original": instrucao_usuario,
            "base_anterior": base_conhecimento_atual,
            "base_nova": nova_base,
            "data_modificacao": datetime.datetime.now(),
            "status": "processado"
        }
        
        collection_playbook_logs.insert_one(log_entry)
        
        return nova_base, "✅ Base de conhecimento atualizada com sucesso!"
        
    except Exception as e:
        error_msg = f"❌ Erro ao processar playbook: {str(e)}"
        
        # Registrar erro no log
        log_entry = {
            "agente_id": agente_id,
            "usuario": get_current_user().get('email', 'unknown'),
            "squad": get_current_squad(),
            "elemento_tipo": elemento_tipo,
            "instrucao_original": instrucao_usuario,
            "base_anterior": base_conhecimento_atual,
            "base_nova": None,
            "data_modificacao": datetime.datetime.now(),
            "status": "erro",
            "erro": str(e)
        }
        
        collection_playbook_logs.insert_one(log_entry)
        return None, error_msg


def atualizar_elemento_agente(agente_id, elemento_tipo, novo_conteudo):
    """
    Atualiza um elemento específico do agente no banco de dados
    """
    try:
        if isinstance(agente_id, str):
            agente_id = ObjectId(agente_id)
        
        update_field = ""
        if elemento_tipo == "system_prompt":
            update_field = "system_prompt"
        elif elemento_tipo == "base_conhecimento":
            update_field = "base_conhecimento"
        elif elemento_tipo == "comments":
            update_field = "comments"
        elif elemento_tipo == "planejamento":
            update_field = "planejamento"
        else:
            return False, "Tipo de elemento inválido"
        
        result = collection_agentes.update_one(
            {"_id": agente_id},
            {
                "$set": {
                    update_field: novo_conteudo,
                    "data_atualizacao": datetime.datetime.now(),
                    "atualizado_por": get_current_user().get('email', 'unknown')
                }
            }
        )
        
        if result.modified_count > 0:
            return True, f"✅ {elemento_tipo.replace('_', ' ').title()} atualizado com sucesso!"
        else:
            return False, "❌ Nenhuma alteração foi feita"
            
    except Exception as e:
        return False, f"❌ Erro ao atualizar agente: {str(e)}"

def obter_logs_playbook(agente_id=None, limite=20):
    """
    Obtém os logs de alterações do playbook
    """
    query = {}
    if agente_id:
        if isinstance(agente_id, str):
            agente_id = ObjectId(agente_id)
        query["agente_id"] = agente_id
    
    return list(collection_playbook_logs.find(query)
                .sort("data_modificacao", -1)
                .limit(limite))

def reverter_alteracao(log_id):
    """
    Reverte uma alteração específica do playbook
    """
    try:
        log = collection_playbook_logs.find_one({"_id": ObjectId(log_id)})
        
        if not log or not log.get("base_anterior"):
            return False, "Log não encontrado ou sem base anterior"
        
        # Reverter para versão anterior
        sucesso, mensagem = atualizar_elemento_agente(
            log["agente_id"],
            log["elemento_tipo"],
            log["base_anterior"]
        )
        
        if sucesso:
            # Marcar log como revertido
            collection_playbook_logs.update_one(
                {"_id": ObjectId(log_id)},
                {"$set": {"status": "revertido", "data_reversao": datetime.datetime.now()}}
            )
            
            # Criar novo log para a reversão
            novo_log = {
                "agente_id": log["agente_id"],
                "usuario": get_current_user().get('email', 'unknown'),
                "squad": get_current_squad(),
                "elemento_tipo": log["elemento_tipo"],
                "instrucao_original": f"REVERSÃO: {log.get('instrucao_original', '')}",
                "base_anterior": log.get("base_nova", ""),
                "base_nova": log["base_anterior"],
                "data_modificacao": datetime.datetime.now(),
                "status": "reversao",
                "log_revertido_id": log_id
            }
            
            collection_playbook_logs.insert_one(novo_log)
            
            return True, "✅ Alteração revertida com sucesso!"
        else:
            return False, mensagem
            
    except Exception as e:
        return False, f"❌ Erro ao reverter alteração: {str(e)}"

# --- CONFIGURAÇÕES APÓS LOGIN ---
gemini_api_key = os.getenv("GEM_API_KEY")
if not gemini_api_key:
    st.error("GEMINI_API_KEY não encontrada nas variáveis de ambiente")
    st.stop()

genai.configure(api_key=gemini_api_key)
modelo_vision = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.1})
modelo_texto = genai.GenerativeModel("gemini-2.5-flash")
modelo_playbook = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.1}) 

# Configuração da API do Perplexity
perp_api_key = os.getenv("PERP_API_KEY")
if not perp_api_key:
    st.error("PERP_API_KEY não encontrada nas variáveis de ambiente")

# --- Configuração de Autenticação de Administrador ---
def check_admin_password():
    """Retorna True para usuários admin sem verificação de senha."""
    return st.session_state.user.get('squad') == "admin"

def gerar_resposta_modelo(prompt: str, modelo_escolhido: str = "Gemini", contexto_agente: str = None) -> str:
    """
    Gera resposta usando Gemini ou Claude baseado na escolha do usuário
    """
    try:
        if modelo_escolhido == "Gemini" and modelo_texto:
            if contexto_agente:
                prompt_completo = f"{contexto_agente}\n\n{prompt}"
            else:
                prompt_completo = prompt
            
            resposta = modelo_texto.generate_content(prompt_completo)
            return resposta.text
            
        elif modelo_escolhido == "Claude" and anthropic_client:
            if contexto_agente:
                system_prompt = contexto_agente
            else:
                system_prompt = "Você é um assistente útil."
            
            message = anthropic_client.messages.create(
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
                model="claude-haiku-4-5-20251001",
                system=system_prompt
            )
            return message.content[0].text
            
        else:
            return f"❌ Modelo {modelo_escolhido} não disponível. Verifique as configurações da API."
            
    except Exception as e:
        return f"❌ Erro ao gerar resposta com {modelo_escolhido}: {str(e)}"

# --- FUNÇÕES CRUD PARA AGENTES (MODIFICADAS PARA SQUADS) ---
def criar_agente(nome, system_prompt, base_conhecimento, comments, planejamento, categoria, squad_permitido, agente_mae_id=None, herdar_elementos=None):
    """Cria um novo agente no MongoDB com squad permitido"""
    agente = {
        "nome": nome,
        "system_prompt": system_prompt,
        "base_conhecimento": base_conhecimento,
        "comments": comments,
        "planejamento": planejamento,
        "categoria": categoria,
        "squad_permitido": squad_permitido,  # Novo campo
        "agente_mae_id": agente_mae_id,
        "herdar_elementos": herdar_elementos or [],
        "data_criacao": datetime.datetime.now(),
        "ativo": True,
        "criado_por": get_current_user().get('email', 'unknown'),
        "criado_por_squad": get_current_squad()  # Novo campo
    }
    result = collection_agentes.insert_one(agente)
    return result.inserted_id

def listar_agentes():
    """Retorna todos os agentes ativos que o usuário atual pode ver"""
    current_squad = get_current_squad()
    
    # Admin vê todos os agentes
    if current_squad == "admin":
        return list(collection_agentes.find({"ativo": True}).sort("data_criacao", -1))
    
    # Usuários normais veem apenas agentes do seu squad ou squad "Todos"
    return list(collection_agentes.find({
        "ativo": True,
        "$or": [
            {"squad_permitido": current_squad},
            {"squad_permitido": "Todos"},
            {"criado_por_squad": current_squad}  # Usuário pode ver seus próprios agentes
        ]
    }).sort("data_criacao", -1))

def listar_agentes_para_heranca(agente_atual_id=None):
    """Retorna todos os agentes ativos que podem ser usados como mãe (com filtro de squad)"""
    current_squad = get_current_squad()
    
    query = {"ativo": True}
    
    # Filtro por squad
    if current_squad != "admin":
        query["$or"] = [
            {"squad_permitido": current_squad},
            {"squad_permitido": "Todos"},
            {"criado_por_squad": current_squad}
        ]
    
    if agente_atual_id:
        # Excluir o próprio agente da lista de opções para evitar auto-herança
        if isinstance(agente_atual_id, str):
            agente_atual_id = ObjectId(agente_atual_id)
        query["_id"] = {"$ne": agente_atual_id}
    
    return list(collection_agentes.find(query).sort("data_criacao", -1))

def obter_agente(agente_id):
    """Obtém um agente específico pelo ID com verificação de permissão por squad"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    
    agente = collection_agentes.find_one({"_id": agente_id})
    
    # Verificar permissão baseada no squad
    if agente and agente.get('ativo', True):
        current_squad = get_current_squad()
        
        # Admin pode ver tudo
        if current_squad == "admin":
            return agente
        
        # Usuários normais só podem ver agentes do seu squad ou "Todos"
        squad_permitido = agente.get('squad_permitido')
        criado_por_squad = agente.get('criado_por_squad')
        
        if squad_permitido == current_squad or squad_permitido == "Todos" or criado_por_squad == current_squad:
            return agente
    
    return None

def atualizar_agente(agente_id, nome, system_prompt, base_conhecimento, comments, planejamento, categoria, squad_permitido, agente_mae_id=None, herdar_elementos=None):
    """Atualiza um agente existente com verificação de permissão"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    
    # Verificar se o usuário tem permissão para editar este agente
    agente_existente = obter_agente(agente_id)
    if not agente_existente:
        raise PermissionError("Agente não encontrado ou sem permissão de edição")
    
    return collection_agentes.update_one(
        {"_id": agente_id},
        {
            "$set": {
                "nome": nome,
                "system_prompt": system_prompt,
                "base_conhecimento": base_conhecimento,
                "comments": comments,
                "planejamento": planejamento,
                "categoria": categoria,
                "squad_permitido": squad_permitido,  # Novo campo
                "agente_mae_id": agente_mae_id,
                "herdar_elementos": herdar_elementos or [],
                "data_atualizacao": datetime.datetime.now()
            }
        }
    )

def desativar_agente(agente_id):
    """Desativa um agente (soft delete) com verificação de permissão"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    
    # Verificar se o usuário tem permissão para desativar este agente
    agente_existente = obter_agente(agente_id)
    if not agente_existente:
        raise PermissionError("Agente não encontrado ou sem permissão para desativar")
    
    return collection_agentes.update_one(
        {"_id": agente_id},
        {"$set": {"ativo": False, "data_desativacao": datetime.datetime.now()}}
    )

def obter_agente_com_heranca(agente_id):
    """Obtém um agente com os elementos herdados aplicados"""
    agente = obter_agente(agente_id)
    if not agente or not agente.get('agente_mae_id'):
        return agente
    
    agente_mae = obter_agente(agente['agente_mae_id'])
    if not agente_mae:
        return agente
    
    elementos_herdar = agente.get('herdar_elementos', [])
    agente_completo = agente.copy()
    
    for elemento in elementos_herdar:
        if elemento == 'system_prompt' and not agente_completo.get('system_prompt'):
            agente_completo['system_prompt'] = agente_mae.get('system_prompt', '')
        elif elemento == 'base_conhecimento' and not agente_completo.get('base_conhecimento'):
            agente_completo['base_conhecimento'] = agente_mae.get('base_conhecimento', '')
        elif elemento == 'comments' and not agente_completo.get('comments'):
            agente_completo['comments'] = agente_mae.get('comments', '')
        elif elemento == 'planejamento' and not agente_completo.get('planejamento'):
            agente_completo['planejamento'] = agente_mae.get('planejamento', '')
    
    return agente_completo

def salvar_conversa(agente_id, mensagens, segmentos_utilizados=None):
    """Salva uma conversa no histórico"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    conversa = {
        "agente_id": agente_id,
        "mensagens": mensagens,
        "segmentos_utilizados": segmentos_utilizados,
        "data_criacao": datetime.datetime.now()
    }
    return collection_conversas.insert_one(conversa)

def obter_conversas(agente_id, limite=10):
    """Obtém o histórico de conversas de um agente"""
    if isinstance(agente_id, str):
        agente_id = ObjectId(agente_id)
    return list(collection_conversas.find(
        {"agente_id": agente_id}
    ).sort("data_criacao", -1).limit(limite))

# --- Função para construir contexto com segmentos selecionados ---
def construir_contexto(agente, segmentos_selecionados, historico_mensagens=None):
    """Constrói o contexto com base nos segmentos selecionados"""
    contexto = ""
    
    if "system_prompt" in segmentos_selecionados and agente.get('system_prompt'):
        contexto += f"### INSTRUÇÕES DO SISTEMA ###\n{agente['system_prompt']}\n\n"
    
    if "base_conhecimento" in segmentos_selecionados and agente.get('base_conhecimento'):
        contexto += f"### BASE DE CONHECIMENTO ###\n{agente['base_conhecimento']}\n\n"
    
    if "comments" in segmentos_selecionados and agente.get('comments'):
        contexto += f"### COMENTÁRIOS DO CLIENTE ###\n{agente['comments']}\n\n"
    
    if "planejamento" in segmentos_selecionados and agente.get('planejamento'):
        contexto += f"### PLANEJAMENTO ###\n{agente['planejamento']}\n\n"
    
    # Adicionar histórico se fornecido
    if historico_mensagens:
        contexto += "### HISTÓRICO DA CONVERSA ###\n"
        for msg in historico_mensagens:
            contexto += f"{msg['role']}: {msg['content']}\n"
        contexto += "\n"
    
    contexto += "### RESPOSTA ATUAL ###\nassistant:"
    
    return contexto

# --- MODIFICAÇÃO: SELECTBOX PARA SELEÇÃO DE AGENTE ---
def selecionar_agente_interface():
    """Interface para seleção de agente usando selectbox"""
    st.title("🤖 Agente PMO")
    
    # Carregar agentes disponíveis
    agentes = listar_agentes()
    
    if not agentes:
        st.error("❌ Nenhum agente disponível. Crie um agente primeiro na aba de Gerenciamento.")
        return None
    
    # Preparar opções para o selectbox
    opcoes_agentes = []
    for agente in agentes:
        agente_completo = obter_agente_com_heranca(agente['_id'])
        if agente_completo:  # Só adiciona se tiver permissão
            descricao = f"{agente['nome']} - {agente.get('categoria', 'Social')}"
            if agente.get('agente_mae_id'):
                descricao += " 🔗"
            # Adicionar indicador de squad
            squad_permitido = agente.get('squad_permitido', 'Todos')
            descricao += f" 👥{squad_permitido}"
            opcoes_agentes.append((descricao, agente_completo))
    
    if opcoes_agentes:
        # Selectbox para seleção de agente
        agente_selecionado_desc = st.selectbox(
            "Selecione uma base de conhecimento para usar o sistema:",
            options=[op[0] for op in opcoes_agentes],
            index=0,
            key="selectbox_agente_principal"
        )
        
        # Encontrar o agente completo correspondente
        agente_completo = None
        for desc, agente in opcoes_agentes:
            if desc == agente_selecionado_desc:
                agente_completo = agente
                break
        
        if agente_completo and st.button("✅ Confirmar Seleção", key="confirmar_agente"):
            st.session_state.agente_selecionado = agente_completo
            st.session_state.messages = []
            st.session_state.segmentos_selecionados = ["system_prompt", "base_conhecimento", "comments", "planejamento"]
            st.success(f"✅ Agente '{agente_completo['nome']}' selecionado!")
            st.rerun()
        
        return agente_completo
    else:
        st.info("Nenhum agente disponível com as permissões atuais.")
        return None

# --- Verificar se o agente já foi selecionado ---
if "agente_selecionado" not in st.session_state:
    st.session_state.agente_selecionado = None

# Se não há agente selecionado, mostrar interface de seleção
if not st.session_state.agente_selecionado:
    selecionar_agente_interface()
    st.stop()

# --- INTERFACE PRINCIPAL (apenas se agente estiver selecionado) ---
agente_selecionado = st.session_state.agente_selecionado

def is_syn_agent(agent_name):
    """Verifica se o agente é da baseado no nome"""
    return agent_name and any(keyword in agent_name.upper() for keyword in ['SYN'])

PRODUCT_DESCRIPTIONS = {
    "FORTENZA": "Tratamento de sementes inseticida, focado no Cerrado e posicionado para controle do complexo de lagartas e outras pragas iniciais. Comunicação focada no mercado 'on farm' (tratamento feito na fazenda).",
    "ALADE": "Fungicida para controle de doenças em soja, frequentemente posicionado em programa com Mitrion para controle de podridões de vagens e grãos.",
    "VERDAVIS": "Inseticida e acaricida composto por PLINAZOLIN® technology (nova molécula, novo grupo químico, modo de ação inédito) + lambda-cialotrina. KBFs: + mais choque, + mais espectro e + mais dias de controle.",
    "ENGEO PLENO S": "Inseticida de tradição, referência no controle de percevejos. Mote: 'Nunca foi sorte. Sempre foi Engeo Pleno S'.",
    "MEGAFOL": "Bioativador da Syn Biologicals. Origem 100% natural (extratos vegetais e de algas Ascophyllum nodosum). Desenvolvido para garantir que a planta alcance todo seu potencial produtivo.",
    "MIRAVIS DUO": "Fungicida da família Miravis. Traz ADEPIDYN technology (novo ingrediente ativo, novo grupo químico). Focado no controle de manchas foliares.",
    "AVICTA COMPLETO": "Oferta comercial de tratamento industrial de sementes (TSI). Composto por inseticida, fungicida e nematicida.",
    "MITRION": "Fungicida para controle de doenças em soja, frequentemente posicionado em programa com Alade.",
    "AXIAL": "Herbicida para trigo. Composto por um novo ingrediente ativo. Foco no controle do azevém.",
    "CERTANO": "Bionematicida e biofungicida. Composto pela bactéria Bacillus velezensis. Controla nematoides e fungos de solo.",
    "MANEJO LIMPO": "Programa da Syn para manejo integrado de plantas daninhas.",
    "ELESTAL NEO": "Fungicida para controle de doenças em soja e algodão.",
    "FRONDEO": "Inseticida para cana-de-açúcar com foco no controle da broca da cana.",
    "FORTENZA ELITE": "Oferta comercial de TSI. Solução robusta contre pragas, doenças e nematoides do Cerrado.",
    "REVERB": "Produto para manejo de doenças em soja e milho com ação prolongada ou de espectro amplo.",
    "YIELDON": "Produto focado em maximizar a produtividade das lavouras.",
    "ORONDIS FLEXI": "Fungicida com flexibilidade de uso para controle de requeima, míldios e manchas.",
    "RIZOLIQ LLI": "Inoculante ou produto para tratamento de sementes que atua na rizosfera.",
    "ARVATICO": "Fungicida ou inseticida com ação específica para controle de doenças foliares ou pragas.",
    "VERDADERO": "Produto relacionado à saúde do solo ou nutrição vegetal.",
    "MIRAVIS": "Fungicida da família Miravis para controle de doenças.",
    "MIRAVIS PRO": "Fungicida premium da família Miravis para controle avançado de doenças.",
    "INSTIVO": "Lagarticida posicionado como especialista no controle de lagartas do gênero Spodoptera.",
    "CYPRESS": "Fungicida posicionado para últimas aplicações na soja, consolidando o manejo de doenças.",
    "CALARIS": "Herbicida composto por atrazina + mesotriona para controle de plantas daninhas no milho.",
    "SPONTA": "Inseticida para algodão com PLINAZOLIN® technology para controle de bicudo e outras pragas.",
    "INFLUX": "Inseticida lagarticida premium para controle de todas as lagartas, especialmente helicoverpa.",
    "JOINER": "Inseticida acaricida com tecnologia PLINAZOLIN para culturas hortifrúti.",
    "DUAL GOLD": "Herbicida para manejo de plantas daninhas.",
}

def extract_product_info(text: str) -> Tuple[str, str, str]:
    """Extrai informações do produto do texto da célula"""
    if not text or not text.strip():
        return None, None, None
    
    text = str(text).strip()
    
    # Remover emojis e marcadores
    clean_text = re.sub(r'[🔵🟠🟢🔴🟣🔃📲]', '', text).strip()
    
    # Padrões para extração
    patterns = {
        'product': r'\b([A-Z][A-Za-z\s]+(?:PRO|S|NEO|LLI|ELITE|COMPLETO|DUO|FLEXI|PLENO|XTRA)?)\b',
        'culture': r'\b(soja|milho|algodão|cana|trigo|HF|café|citrus|batata|melão|uva|tomate|multi)\b',
        'action': r'\b(depoimento|resultados|série|reforço|controle|lançamento|importância|jornada|conceito|vídeo|ação|diferenciais|awareness|problemática|glossário|manejo|aplicação|posicionamento)\b'
    }
    
    product_match = re.search(patterns['product'], clean_text, re.IGNORECASE)
    culture_match = re.search(patterns['culture'], clean_text, re.IGNORECASE)
    action_match = re.search(patterns['action'], clean_text, re.IGNORECASE)
    
    product = product_match.group(1).strip().upper() if product_match else None
    culture = culture_match.group(0).lower() if culture_match else "multi"
    action = action_match.group(0).lower() if action_match else "conscientização"
    
    return product, culture, action

def generate_context(content, product_name, culture, action, data_input, formato_principal):
    """Gera o texto de contexto discursivo usando LLM"""
    if not gemini_api_key:
        return "API key do Gemini não configurada. Contexto não disponível."
    
    # Determinar mês em português
    meses = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }
    mes = meses[data_input.month]
    
    prompt = f"""
    Como redator especializado em agronegócio da Syn, elabore um texto contextual discursivo de 3-4 parágrafos para uma pauta de conteúdo.

    Informações da pauta:
    - Produto: {product_name}
    - Cultura: {culture}
    - Ação/tema: {action}
    - Mês de publicação: {mes}
    - Formato principal: {formato_principal}
    - Conteúdo original: {content}

    Descrição do produto: {PRODUCT_DESCRIPTIONS.get(product_name, 'Produto agrícola')}

    Instruções:
    - Escreva em formato discursivo e fluido, com 3-4 parágrafos bem estruturados
    - Mantenha tom técnico mas acessível, adequado para produtores rurais
    - Contextualize a importância do tema para a cultura e época do ano
    - Explique por que este conteúdo é relevante neste momento
    - Inclua considerações sobre o público-alvo e objetivos da comunicação
    - Não repita literalmente a descrição do produto, mas a incorpore naturalmente no texto
    - Use linguagem persuasiva mas factual, baseada em dados técnicos

    Formato: Texto corrido em português brasileiro
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar contexto: {str(e)}"

def generate_platform_strategy(product_name, culture, action, content):
    """Gera estratégia por plataforma usando Gemini"""
    if not gemini_api_key:
        return "API key do Gemini não configurada. Estratégias por plataforma não disponíveis."
    
    prompt = f"""
    Como especialista em mídias sociais para o agronegócio, crie uma estratégia de conteúdo detalhada:

    PRODUTO: {product_name}
    CULTURA: {culture}
    AÇÃO: {action}
    CONTEÚDO ORIGINAL: {content}
    DESCRIÇÃO DO PRODUTO: {PRODUCT_DESCRIPTIONS.get(product_name, 'Produto agrícola')}

    FORNECER ESTRATÉGIA PARA:
    - Instagram (Feed, Reels, Stories)
    - Facebook 
    - LinkedIn
    - WhatsApp Business
    - YouTube
    - Portal Mais Agro (blog)

    INCLUIR PARA CADA PLATAFORMA:
    1. Tipo de conteúdo recomendado
    2. Formato ideal (vídeo, carrossel, estático, etc.)
    3. Tom de voz apropriado
    4. CTA específico
    5. Melhores práticas

    Formato: Texto claro com seções bem definidas
    """
    
    try:
        response = modelo_texto.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar estratégia: {str(e)}"

def generate_briefing(content, product_name, culture, action, data_input, formato_principal):
    """Gera um briefing completo em formato de texto puro"""
    description = PRODUCT_DESCRIPTIONS.get(product_name, "Descrição do produto não disponível.")
    context = generate_context(content, product_name, culture, action, data_input, formato_principal)
    platform_strategy = generate_platform_strategy(product_name, culture, action, content)
    
    briefing = f"""
BRIEFING DE CONTEÚDO - {product_name} - {culture.upper()} - {action.upper()}

CONTEXTO E OBJETIVO
{context}

DESCRIÇÃO DO PRODUTO
{description}

ESTRATÉGIA POR PLATAFORMA
{platform_strategy}

FORMATOS SUGERIDOS
- Instagram: Reels + Stories + Feed post
- Facebook: Carrossel + Link post
- LinkedIn: Artigo + Post informativo
- WhatsApp: Card informativo + Link
- YouTube: Shorts + Vídeo explicativo
- Portal Mais Agro: Blog post + Webstories

CONTATOS E OBSERVAÇões
- Validar com especialista técnico
- Checar disponibilidade de imagens/vídeos
- Incluir CTA para portal Mais Agro
- Seguir guidelines de marca
- Revisar compliance regulatório

DATA PREVISTA: {data_input.strftime('%d/%m/%Y')}
FORMATO PRINCIPAL: {formato_principal}
"""
    return briefing

# --- FUNÇÕES PARA TRILHA DE CONHECIMENTO (COM FLUXOGRAMA) ---
def generate_knowledge_flowchart(nome, equipe, funcao, cargo, tasks_exemplo, modelo="gemini"):
    """Gera uma trilha de conhecimento como FLUXOGRAMA profissional"""
    if not gemini_api_key:
        return None, None, "❌ API key do Gemini não configurada."
    
    try:
        # === USAR IA PARA SELECIONAR CURSO ===
        curso_recomendado = selecionar_curso_com_ia(funcao, cargo, tasks_exemplo)
        
        # Formatar informações do curso para o prompt
        info_curso = ""
        if curso_recomendado:
            titulo = curso_recomendado.get('titulo', 'Curso')
            descricao = curso_recomendado.get('descricao', 'Descrição não disponível')
            duracao = curso_recomendado.get('duracao', 'Duração não informada')
            nivel = curso_recomendado.get('nivel', 'Nível não informado')
            link = curso_recomendado.get('link_drive', '')
            
            info_curso = f"""
            
            CURSO RECOMENDADO (SELECIONADO PELA IA BASEADO NO PERFIL):
            
            Título: {titulo}
            Descrição: {descricao}
            Nível: {nivel}
            Duração: {duracao}
            Link de acesso: {link}
            
            INSTRUÇÃO: No final da descrição da trilha, adicione uma seção "🎯 Curso Recomendado" 
            explicando por que este curso é importante para o perfil do colaborador e como ele 
            complementa a trilha de conhecimento. Use as informações acima.
            """
        
        prompt = f"""
        Você é um especialista em Desenvolvimento Organizacional e Design Instrucional.
        Crie uma TRILHA DE CONHECIMENTO como FLUXOGRAMA para:
        
        NOME: {nome}
        EQUIPE: {equipe}
        FUNÇÃO: {funcao}
        CARGO: {cargo}
        EXEMPLO DE TASKS: {tasks_exemplo}
        
        {info_curso}
        
        ### ESTRUTURA DO FLUXOGRAMA:
        1. INÍCIO: Ponto de partida
        2. FUNDAMENTOS: 2-3 módulos básicos
        3. NÚCLEO: 3-4 módulos principais da função
        4. APLICAÇÃO: 2-3 módulos práticos
        5. PROJETOS: 1-2 projetos reais
        6. AVALIAÇÃO: Checkpoints e provas
        7. CERTIFICAÇÃO: Finalização
        
        ### FORMATO DE SAÍDA (JSON):
        {{
            "trilha_info": {{
                "titulo": "Trilha de {funcao}",
                "objetivo": "Texto do objetivo",
                "duracao": "X semanas",
                "publico_alvo": "{cargo}",
                "pre_requisitos": ["item1", "item2"]
            }},
            "fluxograma": {{
                "niveis": [
                    {{
                        "nome": "FUNDAMENTOS",
                        "posicao": 1,
                        "modulos": [
                            {{
                                "id": "F1",
                                "titulo": "Introdução a {funcao}",
                                "tipo": "teoria",
                                "duracao": "2h",
                                "descricao": "Descrição detalhada",
                                "recursos": ["link1", "link2"]
                            }}
                        ]
                    }}
                ]
            }},
            "conexoes": [
                {{
                    "de": "F1",
                    "para": "F2",
                    "tipo": "obrigatoria"
                }}
            ],
            "checkpoints": [
                {{
                    "id": "CP1",
                    "posicao": "apos FUNDAMENTOS",
                    "tipo": "prova",
                    "peso": "20%"
                }}
            ],
            "texto_descritivo": "Texto explicativo em markdown..."
        }}
        
        ### REGRAS IMPORTANTES:
        - Máximo 12 módulos
        - Organize em 4-5 níveis verticais
        - Inclua decisões (sim/não) para diferentes caminhos
        - Adicione loops de feedback
        - Seja prático e realista
        - {f"NO FINAL do texto_descritivo, ADICIONE uma seção '🎯 Curso Recomendado' com o curso acima" if curso_recomendado else ""}
        """
        
        if modelo == "gemini":
            response = modelo_texto.generate_content(prompt)
            response_text = response.text
        else:
            message = anthropic_client.messages.create(
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
                model="claude-haiku-4-5-20241022",
                system="Você é um especialista em design instrucional. Retorne JSON válido."
            )
            response_text = message.content[0].text
        
        # Extrair JSON
        import json
        import re
        
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                texto_descritivo = data.get("texto_descritivo", response_text)
                
                # Se não tem curso na descrição e temos curso recomendado, adicionar
                if curso_recomendado and "Curso Recomendado" not in texto_descritivo:
                    titulo = curso_recomendado.get('titulo', 'Curso')
                    descricao = curso_recomendado.get('descricao', '')
                    duracao = curso_recomendado.get('duracao', '')
                    nivel = curso_recomendado.get('nivel', '')
                    link = curso_recomendado.get('link_drive', '')
                    
                    curso_section = f"""
                    
## 🎯 Curso Recomendado

Para complementar sua trilha como **{funcao} ({cargo})**, recomendamos o curso:

**{titulo}**

{descricao}

📊 **Nível:** {nivel}
⏱️ **Duração:** {duracao}

**Por que este curso é importante para você?**
- Desenvolvido especificamente para profissionais da área de {funcao.split()[0].lower() if funcao.split() else 'sua área'}
- Complementa diretamente as habilidades necessárias para suas tasks: {tasks_exemplo[:100]}...
- Oferece conhecimentos práticos que você pode aplicar imediatamente no trabalho

{f"🔗 **Acesse o curso aqui:** [{link}]({link})" if link else "📚 Disponível na nossa biblioteca de cursos"}
"""
                    data["texto_descritivo"] = texto_descritivo + curso_section
                    texto_descritivo = data["texto_descritivo"]
                
                # Gerar fluxograma visual
                flowchart_image = create_flowchart_diagram(data, nome, funcao)
                
                return data, flowchart_image, texto_descritivo
            except Exception as json_error:
                st.warning(f"⚠️ Erro no JSON: {str(json_error)}")
                # Criar fluxograma genérico
                texto_descritivo = response_text
                if curso_recomendado:
                    # Adicionar curso mesmo sem JSON
                    titulo = curso_recomendado.get('titulo', 'Curso')
                    descricao = curso_recomendado.get('descricao', '')
                    link = curso_recomendado.get('link_drive', '')
                    
                    texto_descritivo += f"\n\n## 🎯 Curso Recomendado\n\n"
                    texto_descritivo += f"**{titulo}**\n\n"
                    texto_descritivo += f"{descricao}\n\n"
                    if link:
                        texto_descritivo += f"🔗 Acesse: {link}"
                
                flowchart_image = create_generic_flowchart(nome, funcao, tasks_exemplo)
                return None, flowchart_image, texto_descritivo
        else:
            texto_descritivo = response_text
            if curso_recomendado:
                # Adicionar curso mesmo sem JSON
                titulo = curso_recomendado.get('titulo', 'Curso')
                descricao = curso_recomendado.get('descricao', '')
                link = curso_recomendado.get('link_drive', '')
                
                texto_descritivo += f"\n\n## 🎯 Curso Recomendado\n\n"
                texto_descritivo += f"**{titulo}**\n\n"
                texto_descritivo += f"{descricao}\n\n"
                if link:
                    texto_descritivo += f"🔗 Acesse: {link}"
            
            flowchart_image = create_generic_flowchart(nome, funcao, tasks_exemplo)
            return None, flowchart_image, texto_descritivo
            
    except Exception as e:
        return None, None, f"❌ Erro ao gerar fluxograma: {str(e)}"




def create_flowchart_diagram(data, nome, funcao):
    """Cria um fluxograma visual profissional a partir dos dados"""
    try:
        # Configurar figura
        fig, ax = plt.subplots(figsize=(14, 10))
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 12)
        ax.axis('off')
        
        # Cores para diferentes tipos
        color_map = {
            'teoria': '#4A90E2',      # Azul para teoria
            'pratica': '#50C878',     # Verde para prática
            'projeto': '#FFD700',     # Amarelo para projeto
            'prova': '#FF6B6B',       # Vermelho para prova
            'decisao': '#9B59B6',     # Roxo para decisão
            'inicio': '#2ECC71',      # Verde claro para início
            'fim': '#E74C3C'          # Vermelho para fim
        }
        
        # Posicionamento dos níveis
        niveis = data.get("fluxograma", {}).get("niveis", [])
        
        modules_by_level = {}
        y_positions = {}
        
        # Organizar módulos por nível
        for i, nivel in enumerate(niveis):
            level_name = nivel.get("nome", f"Nível {i+1}")
            modules = nivel.get("modulos", [])
            
            # Posição Y para este nível (mais alto = mais no topo)
            y_base = 10 - (i * 2.2)
            modules_by_level[level_name] = {
                'modules': modules,
                'y': y_base
            }
        
        # Desenhar módulos
        module_positions = {}  # Para guardar posições dos módulos
        module_by_id = {}      # Para mapear ID -> dados do módulo
        
        for level_name, level_data in modules_by_level.items():
            modules = level_data['modules']
            y = level_data['y']
            
            # Número de módulos neste nível
            num_modules = len(modules)
            
            # Calcular espaçamento horizontal
            if num_modules > 0:
                spacing = 8.0 / (num_modules + 1)
                
                for j, modulo in enumerate(modules):
                    x = 1 + (j + 1) * spacing
                    module_id = modulo.get("id", f"M{j}")
                    title = modulo.get("titulo", "Módulo")
                    tipo = modulo.get("tipo", "teoria")
                    
                    # Guardar posição para conexões
                    module_positions[module_id] = (x, y)
                    module_by_id[module_id] = {
                        'x': x,
                        'y': y,
                        'tipo': tipo,
                        'nivel': level_name
                    }
                    
                    # Cor baseada no tipo
                    color = color_map.get(tipo, '#4A90E2')
                    
                    # Desenhar caixa do módulo
                    if tipo == 'decisao':
                        # Losango para decisões
                        diamond = patches.RegularPolygon(
                            (x, y), 4, radius=0.5,
                            orientation=np.pi/4,
                            facecolor=color, alpha=0.8,
                            edgecolor='black', linewidth=2
                        )
                        ax.add_patch(diamond)
                        # Texto dentro do losango
                        ax.text(x, y, f"{module_id}\n{title[:15]}", 
                               ha='center', va='center', fontsize=8, fontweight='bold')
                    else:
                        # Retângulo para outros módulos
                        rect = patches.FancyBboxPatch(
                            (x-0.6, y-0.3), 1.2, 0.6,
                            boxstyle="round,pad=0.1",
                            facecolor=color, alpha=0.8,
                            edgecolor='black', linewidth=2
                        )
                        ax.add_patch(rect)
                        # Texto dentro do retângulo
                        ax.text(x, y, f"{module_id}\n{title[:20]}", 
                               ha='center', va='center', fontsize=8, fontweight='bold')
                    
                    # Adicionar ícone baseado no tipo
                    icon = get_icon_for_type(tipo)
                    ax.text(x, y+0.4, icon, ha='center', va='center', fontsize=12)
        
        # Desenhar conexões - ORDEM CORRIGIDA
        # Primeiro organizar conexões por nível para evitar sobreposição
        conexoes = data.get("conexoes", [])
        
        # Agrupar conexões por nível de origem
        conexoes_ordenadas = []
        for conexao in conexoes:
            de = conexao.get("de")
            para = conexao.get("para")
            
            if de in module_by_id and para in module_by_id:
                nivel_de = module_by_id[de]['nivel']
                nivel_para = module_by_id[para]['nivel']
                
                # Calcular "distância" entre níveis
                niveis_list = list(modules_by_level.keys())
                if nivel_de in niveis_list and nivel_para in niveis_list:
                    indice_de = niveis_list.index(nivel_de)
                    indice_para = niveis_list.index(nivel_para)
                    distancia = abs(indice_para - indice_de)
                    
                    conexoes_ordenadas.append({
                        'conexao': conexao,
                        'distancia': distancia,
                        'nivel_de': indice_de,
                        'nivel_para': indice_para
                    })
        
        # Ordenar conexões: primeiro as mais curtas, depois as mais longas
        conexoes_ordenadas.sort(key=lambda x: x['distancia'])
        
        # Desenhar conexões ordenadas
        for item in conexoes_ordenadas:
            conexao = item['conexao']
            de = conexao.get("de")
            para = conexao.get("para")
            tipo = conexao.get("tipo", "obrigatoria")
            
            if de in module_positions and para in module_positions:
                x1, y1 = module_positions[de]
                x2, y2 = module_positions[para]
                
                # CORREÇÃO: Ajustar pontos de conexão baseado no tipo de módulo
                if module_by_id[de]['tipo'] == 'decisao':
                    # Para losangos, conectar das laterais
                    if x2 > x1:  # Módulo destino à direita
                        x1 += 0.5
                    else:  # Módulo destino à esquerda
                        x1 -= 0.5
                else:
                    # Para retângulos, conectar da base
                    y1 -= 0.3
                
                if module_by_id[para]['tipo'] == 'decisao':
                    # Para losangos, conectar nas laterais
                    if x2 > x1:  # Vindo da esquerda
                        x2 -= 0.5
                    else:  # Vindo da direita
                        x2 += 0.5
                else:
                    # Para retângulos, conectar no topo
                    y2 += 0.3
                
                # Estilo da seta baseado no tipo
                if tipo == 'opcional':
                    linestyle = 'dashed'
                    color = 'gray'
                    arrowstyle = '-|>'
                elif tipo == 'feedback':
                    linestyle = 'dotted'
                    color = 'orange'
                    arrowstyle = '<|-|>'
                else:
                    linestyle = 'solid'
                    color = 'black'
                    arrowstyle = '->'
                
                # Calcular curvatura baseado na distância horizontal
                dx = abs(x2 - x1)
                rad = 0.2 if dx < 2 else 0.3
                
                # Desenhar linha com seta
                ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                          arrowprops=dict(arrowstyle=arrowstyle,
                                        color=color,
                                        linestyle=linestyle,
                                        linewidth=1.5,
                                        connectionstyle=f"arc3,rad={rad}"))
        
        # Adicionar título
        titulo = data.get("trilha_info", {}).get("titulo", f"Trilha de {funcao}")
        ax.text(5, 11.5, titulo, ha='center', va='center', 
               fontsize=16, fontweight='bold', color='#2C3E50')
        
        # Adicionar informações do colaborador
        info_text = f"Colaborador: {nome} | Cargo: {funcao}"
        ax.text(5, 11.0, info_text, ha='center', va='center', 
               fontsize=10, color='#34495E')
        
        # Adicionar legenda
        legend_x = 0.5
        legend_y = 0.5
        legend_elements = [
            patches.Patch(facecolor=color_map['teoria'], label='Teoria/Aula', alpha=0.8),
            patches.Patch(facecolor=color_map['pratica'], label='Prática', alpha=0.8),
            patches.Patch(facecolor=color_map['projeto'], label='Projeto', alpha=0.8),
            patches.Patch(facecolor=color_map['prova'], label='Avaliação', alpha=0.8),
            patches.Patch(facecolor=color_map['decisao'], label='Decisão', alpha=0.8),
        ]
        
        ax.legend(handles=legend_elements, loc='lower left', 
                 bbox_to_anchor=(0.02, 0.02), fontsize=9)
        
        # Adicionar níveis como rótulos na esquerda
        for i, (level_name, level_data) in enumerate(modules_by_level.items()):
            y = level_data['y']
            ax.text(0.3, y, level_name, ha='right', va='center',
                   fontsize=10, fontweight='bold', color='#2C3E50',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))
        
        plt.tight_layout()
        
        # Salvar em buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', pad_inches=0.5)
        buf.seek(0)
        plt.close()
        
        return buf
        
    except Exception as e:
        st.error(f"Erro ao criar fluxograma: {str(e)}")
        # Em caso de erro, criar fluxograma genérico
        return create_generic_flowchart(nome, funcao, "")






def get_icon_for_type(tipo):
    """Retorna emoji baseado no tipo de módulo"""
    icons = {
        'teoria': '📚',
        'pratica': '🔧',
        'projeto': '🎯',
        'prova': '📝',
        'decisao': '🤔',
        'inicio': '🚀',
        'fim': '🏆',
        'feedback': '🔄'
    }
    return icons.get(tipo, '📌')

def save_flowchart_to_db(nome, equipe, funcao, cargo, tasks, data_fluxograma, flowchart_image, texto_descritivo):
    """Salva o fluxograma no MongoDB"""
    try:
        # Converter imagem para base64 para salvar no MongoDB
        flowchart_base64 = None
        if flowchart_image:
            flowchart_image.seek(0)
            flowchart_base64 = base64.b64encode(flowchart_image.read()).decode('utf-8')
        
        trilha_doc = {
            "nome_colaborador": nome,
            "equipe": equipe,
            "funcao": funcao,
            "cargo": cargo,
            "tasks_exemplo": tasks,
            "data_fluxograma": data_fluxograma,
            "fluxograma_imagem": flowchart_base64,
            "texto_descritivo": texto_descritivo,
            "criado_por": get_current_user().get('email', 'unknown'),
            "squad": get_current_squad(),
            "data_criacao": datetime.datetime.now(),
            "tipo": "fluxograma",
            "status": "ativo"
        }
        
        # Criar uma coleção específica para trilhas
        collection_trilhas = db['trilhas_conhecimento']
        result = collection_trilhas.insert_one(trilha_doc)
        
        return True, f"✅ Fluxograma salvo com ID: {result.inserted_id}"
        
    except Exception as e:
        return False, f"❌ Erro ao salvar fluxograma: {str(e)}"

def get_knowledge_paths(limit=10):
    """Obtém trilhas/fluxogramas de conhecimento salvas"""
    try:
        collection_trilhas = db['trilhas_conhecimento']
        return list(collection_trilhas.find(
            {"status": "ativo", "squad": get_current_squad()}
        ).sort("data_criacao", -1).limit(limit))
    except:
        # Se a coleção não existir, criar
        try:
            db.create_collection('trilhas_conhecimento')
            return []
        except:
            return []



def gerar_resposta_especialista_curso(pergunta, curso_selecionado, historico_conversa=None):
    """
    Gera resposta como especialista do curso usando Gemini
    """
    try:
        if not modelo_texto or not curso_selecionado:
            return "❌ Configuração não disponível"
        
        # Extrair informações do curso
        titulo = curso_selecionado.get('titulo', 'Curso')
        descricao = curso_selecionado.get('descricao', 'Descrição não disponível')
        nivel = curso_selecionado.get('nivel', 'Nível não informado')
        tags = curso_selecionado.get('tags', [])
        
        # Construir contexto do especialista
        contexto_especialista = f"""
        Você é um especialista no curso: "{titulo}"
        
        INFORMAÇÕES DO CURSO:
        - Título: {titulo}
        - Descrição: {descricao}
        - Nível: {nivel}
        - Tags/Áreas: {', '.join(tags) if tags else 'Não especificado'}
        
        SUA PERSONALIDADE:
        - Especialista com profundo conhecimento no assunto
        - Professor paciente e didático
        - Explica conceitos complexos de forma simples
        - Dá exemplos práticos e aplicações reais
        - Incentiva o aprendizado contínuo
        
        REGRAS:
        1. Responda APENAS sobre o assunto do curso
        2. Se a pergunta não for sobre o curso, explique educadamente que só pode falar sobre esse tópico
        3. Use analogias e exemplos para facilitar o entendimento
        4. Relacione o conteúdo com aplicações práticas
        5. Sugira exercícios ou práticas quando apropriado
        
        HISTÓRICO DA CONVERSA:
        {historico_conversa if historico_conversa else 'Primeira pergunta'}
        """
        
        # Montar prompt completo
        prompt_completo = f"{contexto_especialista}\n\nPERGUNTA DO ALUNO: {pergunta}\n\nRESPOSTA DO ESPECIALISTA:"
        
        # Gerar resposta
        response = modelo_texto.generate_content(prompt_completo)
        return response.text
        
    except Exception as e:
        return f"❌ Erro ao gerar resposta: {str(e)}"


# --- Interface Principal ---
st.sidebar.title(f"🤖 Bem-vindo, {get_current_user().get('nome', 'Usuário')}!")
st.sidebar.info(f"**Squad:** {get_current_squad()}")
st.sidebar.info(f"**Agente selecionado:** {agente_selecionado['nome']}")

# Botão de logout na sidebar
if st.sidebar.button("🚪 Sair", key="logout_btn"):
    for key in ["logged_in", "user", "admin_password_correct", "admin_user", "agente_selecionado"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# Botão para trocar agente
if st.sidebar.button("🔄 Trocar Agente", key="trocar_agente_global"):
    st.session_state.agente_selecionado = None
    st.session_state.messages = []
    st.rerun()

# --- SELECTBOX PARA TROCAR AGENTE ACIMA DAS ABAS ---
st.title("🤖 Agente PMO")

# Carregar agentes disponíveis
agentes = listar_agentes()

if agentes:
    # Preparar opções para o selectbox
    opcoes_agentes = []
    for agente in agentes:
        agente_completo = obter_agente_com_heranca(agente['_id'])
        if agente_completo:  # Só adiciona se tiver permissão
            descricao = f"{agente['nome']} - {agente.get('categoria', 'Social')}"
            if agente.get('agente_mae_id'):
                descricao += " 🔗"
            # Adicionar indicador de squad
            squad_permitido = agente.get('squad_permitido', 'Todos')
            descricao += f" 👥{squad_permitido}"
            opcoes_agentes.append((descricao, agente_completo))
    
    if opcoes_agentes:
        # Encontrar o índice atual
        indice_atual = 0
        for i, (desc, agente) in enumerate(opcoes_agentes):
            if agente['_id'] == st.session_state.agente_selecionado['_id']:
                indice_atual = i
                break
        
        # Selectbox para trocar agente
        col1, col2 = st.columns([3, 1])
        with col1:
            novo_agente_desc = st.selectbox(
                "Selecionar Agente:",
                options=[op[0] for op in opcoes_agentes],
                index=indice_atual,
                key="selectbox_trocar_agente"
            )
        with col2:
            if st.button("🔄 Trocar", key="botao_trocar_agente"):
                # Encontrar o agente completo correspondente
                for desc, agente in opcoes_agentes:
                    if desc == novo_agente_desc:
                        st.session_state.agente_selecionado = agente
                        st.session_state.messages = []
                        st.success(f"✅ Agente alterado para '{agente['nome']}'!")
                        st.rerun()
                        break
    else:
        st.info("Nenhum agente disponível com as permissões atuais.")

# Menu de abas - DETERMINAR QUAIS ABAS MOSTRAR
abas_base = [
    "💬 Chat", 
    "⚙️ Gerenciar Agentes",
    "📚 Playbook",
    "🧠 Trilha de Conhecimento" , 
    "🎓 Cursos e Capacitações"
]

if is_syn_agent(agente_selecionado['nome']):
    abas_base.append("📋 Briefing")

# Criar abas dinamicamente
tabs = st.tabs(abas_base)

# Mapear abas para suas respectivas funcionalidades
tab_mapping = {}
for i, aba in enumerate(abas_base):
    tab_mapping[aba] = tabs[i]

# --- ABA: CHAT ---
with tab_mapping["💬 Chat"]:
    st.header("💬 Chat com Agente")
    
    # Inicializar session_state se não existir
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'segmentos_selecionados' not in st.session_state:
        st.session_state.segmentos_selecionados = []
    if 'show_historico' not in st.session_state:
        st.session_state.show_historico = False
    if 'modelo_chat' not in st.session_state:
        st.session_state.modelo_chat = "Gemini"
    
    agente = st.session_state.agente_selecionado
    st.subheader(f"Conversando com: {agente['nome']}")
    
    # Seletor de modelo na sidebar do chat
    st.sidebar.subheader("🤖 Configurações do Modelo")
    modelo_chat = st.sidebar.selectbox(
        "Escolha o modelo:",
        ["Gemini", "Claude"],
        key="modelo_chat_selector",
        index=0 if st.session_state.modelo_chat == "Gemini" else 1
    )
    st.session_state.modelo_chat = modelo_chat
    
    # Status dos modelos
    if modelo_chat == "Gemini" and not gemini_api_key:
        st.sidebar.error("❌ Gemini não disponível")
    elif modelo_chat == "Claude" and not anthropic_api_key:
        st.sidebar.error("❌ Claude não disponível")
    else:
        st.sidebar.success(f"✅ {modelo_chat} ativo")
    
    # Controles de navegação no topo
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("📚 Carregar Histórico", key="carregar_historico"):
            st.session_state.show_historico = not st.session_state.show_historico
            st.rerun()
    
    with col2:
        if st.button("🔄 Limpar Chat", key="limpar_chat"):
            st.session_state.messages = []
            if hasattr(st.session_state, 'historico_contexto'):
                st.session_state.historico_contexto = []
            st.success("Chat limpo!")
            st.rerun()
    
    with col3:
        if st.button("🔁 Trocar Agente", key="trocar_agente_chat"):
            st.session_state.agente_selecionado = None
            st.session_state.messages = []
            st.session_state.historico_contexto = []
            st.rerun()
    
    # Mostrar se há histórico carregado
    if hasattr(st.session_state, 'historico_contexto') and st.session_state.historico_contexto:
        st.info(f"📖 Usando histórico anterior com {len(st.session_state.historico_contexto)} mensagens como contexto")
    
    # Modal para seleção de histórico
    if st.session_state.show_historico:
        with st.expander("📚 Selecionar Histórico de Conversa", expanded=True):
            conversas_anteriores = obter_conversas(agente['_id'])
            
            if conversas_anteriores:
                for i, conversa in enumerate(conversas_anteriores[:10]):  # Últimas 10 conversas
                    col_hist1, col_hist2, col_hist3 = st.columns([3, 1, 1])
                    
                    with col_hist1:
                        # CORREÇÃO: Usar get() para evitar KeyError
                        data_display = conversa.get('data_formatada', conversa.get('data', 'Data desconhecida'))
                        mensagens_count = len(conversa.get('mensagens', []))
                        st.write(f"**{data_display}** - {mensagens_count} mensagens")
                    
                    with col_hist2:
                        if st.button("👀 Visualizar", key=f"ver_{i}"):
                            st.session_state.conversa_visualizada = conversa.get('mensagens', [])
                    
                    with col_hist3:
                        if st.button("📥 Usar", key=f"usar_{i}"):
                            st.session_state.messages = conversa.get('mensagens', [])
                            st.session_state.historico_contexto = conversa.get('mensagens', [])
                            st.session_state.show_historico = False
                            st.success(f"✅ Histórico carregado: {len(conversa.get('mensagens', []))} mensagens")
                            st.rerun()
                
                # Visualizar conversa selecionada
                if hasattr(st.session_state, 'conversa_visualizada'):
                    st.subheader("👀 Visualização do Histórico")
                    for msg in st.session_state.conversa_visualizada[-6:]:  # Últimas 6 mensagens
                        with st.chat_message(msg.get("role", "user")):
                            st.markdown(msg.get("content", ""))
                    
                    if st.button("Fechar Visualização", key="fechar_visualizacao"):
                        st.session_state.conversa_visualizada = None
                        st.rerun()
            else:
                st.info("Nenhuma conversa anterior encontrada")
    
    # Mostrar informações de herança se aplicável
    if 'agente_mae_id' in agente and agente['agente_mae_id']:
        agente_original = obter_agente(agente['_id'])
        if agente_original and agente_original.get('herdar_elementos'):
            st.info(f"🔗 Este agente herda {len(agente_original['herdar_elementos'])} elementos do agente mãe")
    
    # Controles de segmentos na sidebar do chat
    st.sidebar.subheader("🔧 Configurações do Agente")
    st.sidebar.write("Selecione quais bases de conhecimento usar:")
    
    segmentos_disponiveis = {
        "Prompt do Sistema": "system_prompt",
        "Brand Guidelines": "base_conhecimento", 
        "Comentários do Cliente": "comments",
        "Planejamento": "planejamento"
    }
    
    segmentos_selecionados = []
    for nome, chave in segmentos_disponiveis.items():
        if st.sidebar.checkbox(nome, value=chave in st.session_state.segmentos_selecionados, key=f"seg_{chave}"):
            segmentos_selecionados.append(chave)
    
    st.session_state.segmentos_selecionados = segmentos_selecionados
    
    # Exibir status dos segmentos
    if segmentos_selecionados:
        st.sidebar.success(f"✅ Usando {len(segmentos_selecionados)} segmento(s)")
    else:
        st.sidebar.warning("⚠️ Nenhum segmento selecionado")
    
    # Indicador de posição na conversa
    if len(st.session_state.messages) > 4:
        st.caption(f"📄 Conversa com {len(st.session_state.messages)} mensagens")
    
    # CORREÇÃO: Exibir histórico de mensagens DENTRO do contexto correto
    # Verificar se messages existe e é iterável
    if hasattr(st.session_state, 'messages') and st.session_state.messages:
        for message in st.session_state.messages:
            # Verificar se message é um dicionário e tem a chave 'role'
            if isinstance(message, dict) and "role" in message:
                with st.chat_message(message["role"]):
                    st.markdown(message.get("content", ""))
            else:
                # Se a estrutura não for a esperada, pular esta mensagem
                continue
    else:
        # Se não houver mensagens, mostrar estado vazio
        st.info("💬 Inicie uma conversa digitando uma mensagem abaixo!")
    
    # Input do usuário
    if prompt := st.chat_input("Digite sua mensagem..."):
        # Adicionar mensagem do usuário ao histórico
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Construir contexto com segmentos selecionados
        contexto = construir_contexto(
            agente, 
            st.session_state.segmentos_selecionados, 
            st.session_state.messages
        )
        
        # Gerar resposta
        with st.chat_message("assistant"):
            with st.spinner('Pensando...'):
                try:
                    resposta = gerar_resposta_modelo(
                        contexto, 
                        st.session_state.modelo_chat,
                        contexto
                    )
                    st.markdown(resposta)
                    
                    # Adicionar ao histórico
                    st.session_state.messages.append({"role": "assistant", "content": resposta})
                    
                    # Salvar conversa com segmentos utilizados
                    salvar_conversa(
                        agente['_id'], 
                        st.session_state.messages,
                        st.session_state.segmentos_selecionados
                    )
                    
                except Exception as e:
                    st.error(f"Erro ao gerar resposta: {str(e)}")

# --- ABA: GERENCIAMENTO DE AGENTES (MODIFICADA PARA SQUADS) ---
with tab_mapping["⚙️ Gerenciar Agentes"]:
    st.header("Gerenciamento de Agentes")
    
    # Verificar autenticação apenas para gerenciamento
    current_user = get_current_user()
    current_squad = get_current_squad()
    
    if current_squad not in ["admin", "Syngenta", "SME", "Enterprise"]:
        st.warning("Acesso restrito a usuários autorizados")
    else:
        # Para admin, verificar senha adicional
        if current_squad == "admin":
            if not check_admin_password():
                st.warning("Digite a senha de administrador")
            else:
                st.write(f'Bem-vindo administrador!')
        else:
            st.write(f'Bem-vindo {current_user.get("nome", "Usuário")} do squad {current_squad}!')
            
        # Subabas para gerenciamento
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["Criar Agente", "Editar Agente", "Gerenciar Agentes"])
        
        with sub_tab1:
            st.subheader("Criar Novo Agente")
            
            with st.form("form_criar_agente"):
                nome_agente = st.text_input("Nome do Agente:")
                
                # Seleção de categoria - AGORA COM MONITORAMENTO
                categoria = st.selectbox(
                    "Categoria:",
                    ["Social", "SEO", "Conteúdo", "Monitoramento"],
                    help="Organize o agente por área de atuação"
                )
                
                # NOVO: Seleção de squad permitido
                squad_permitido = st.selectbox(
                    "Squad Permitido:",
                    ["Todos", "Syngenta", "SME", "Enterprise"],
                    help="Selecione qual squad pode ver e usar este agente"
                )
                
                # Configurações específicas para agentes de monitoramento
                if categoria == "Monitoramento":
                    st.info("🔍 **Agente de Monitoramento**: Este agente será usado apenas na aba de Monitoramento de Redes e terá uma estrutura simplificada.")
                    
                    # Para monitoramento, apenas base de conhecimento
                    base_conhecimento = st.text_area(
                        "Base de Conhecimento para Monitoramento:", 
                        height=300,
                        placeholder="""Cole aqui a base de conhecimento específica para monitoramento de redes sociais.

PERSONALIDADE: Especialista técnico do agronegócio com habilidade social - "Especialista que fala como gente"

TOM DE VOZ:
- Técnico, confiável e seguro, mas acessível
- Evita exageros e promessas vazias
- Sempre embasado em fatos e ciência
- Frases curtas e diretas, mais simpáticas
- Toque de leveza e ironia pontual quando o contexto permite

PRODUTOS SYN:
- Fortenza: Tratamento de sementes inseticida para Cerrado
- Verdatis: Inseticida com tecnologia PLINAZOLIN
- Megafol: Bioativador natural
- Miravis Duo: Fungicida para controle de manchas foliares

DIRETRIZES:
- NÃO inventar informações técnicas
- Sempre basear respostas em fatos
- Manter tom profissional mas acessível
- Adaptar resposta ao tipo de pergunta""",
                        help="Esta base será usada exclusivamente para monitoramento de redes sociais"
                    )
                    
                    # Campos específicos ocultos para monitoramento
                    system_prompt = ""
                    comments = ""
                    planejamento = ""
                    criar_como_filho = False
                    agente_mae_id = None
                    herdar_elementos = []
                    
                else:
                    # Para outras categorias, manter estrutura original
                    criar_como_filho = st.checkbox("Criar como agente filho (herdar elementos)")
                    
                    agente_mae_id = None
                    herdar_elementos = []
                    
                    if criar_como_filho:
                        # Listar TODOS os agentes disponíveis para herança (exceto monitoramento)
                        agentes_mae = listar_agentes_para_heranca()
                        agentes_mae = [agente for agente in agentes_mae if agente.get('categoria') != 'Monitoramento']
                        
                        if agentes_mae:
                            agente_mae_options = {f"{agente['nome']} ({agente.get('categoria', 'Social')})": agente['_id'] for agente in agentes_mae}
                            agente_mae_selecionado = st.selectbox(
                                "Agente Mãe:",
                                list(agente_mae_options.keys()),
                                help="Selecione o agente do qual este agente irá herdar elementos"
                            )
                            agente_mae_id = agente_mae_options[agente_mae_selecionado]
                            
                            st.subheader("Elementos para Herdar")
                            herdar_elementos = st.multiselect(
                                "Selecione os elementos a herdar do agente mãe:",
                                ["system_prompt", "base_conhecimento", "comments", "planejamento"],
                                help="Estes elementos serão herdados do agente mãe se não preenchidos abaixo"
                            )
                        else:
                            st.info("Nenhum agente disponível para herança. Crie primeiro um agente mãe.")
                    
                    system_prompt = st.text_area("Prompt de Sistema:", height=150, 
                                                placeholder="Ex: Você é um assistente especializado em...",
                                                help="Deixe vazio se for herdar do agente mãe")
                    base_conhecimento = st.text_area("Brand Guidelines:", height=200,
                                                   placeholder="Cole aqui informações, diretrizes, dados...",
                                                   help="Deixe vazio se for herdar do agente mãe")
                    comments = st.text_area("Comentários do cliente:", height=200,
                                                   placeholder="Cole aqui os comentários de ajuste do cliente (Se houver)",
                                                   help="Deixe vazio se for herdar do agente mãe")
                    planejamento = st.text_area("Planejamento:", height=200,
                                               placeholder="Estratégias, planejamentos, cronogramas...",
                                               help="Deixe vazio se for herdar do agente mãe")
                
                submitted = st.form_submit_button("Criar Agente")
                if submitted:
                    if nome_agente:
                        agente_id = criar_agente(
                            nome_agente, 
                            system_prompt, 
                            base_conhecimento, 
                            comments, 
                            planejamento,
                            categoria,
                            squad_permitido,  # Novo campo
                            agente_mae_id if criar_como_filho else None,
                            herdar_elementos if criar_como_filho else []
                        )
                        st.success(f"Agente '{nome_agente}' criado com sucesso na categoria {categoria} para o squad {squad_permitido}!")
                    else:
                        st.error("Nome é obrigatório!")
        
        with sub_tab2:
            st.subheader("Editar Agente Existente")
            
            agentes = listar_agentes()
            if agentes:
                agente_options = {agente['nome']: agente for agente in agentes}
                agente_selecionado_nome = st.selectbox("Selecione o agente para editar:", 
                                                     list(agente_options.keys()))
                
                if agente_selecionado_nome:
                    agente = agente_options[agente_selecionado_nome]
                    
                    with st.form("form_editar_agente"):
                        novo_nome = st.text_input("Nome do Agente:", value=agente['nome'])
                        
                        # Categoria - AGORA COM MONITORAMENTO
                        categorias_disponiveis = ["Social", "SEO", "Conteúdo", "Monitoramento"]
                        if agente.get('categoria') in categorias_disponiveis:
                            index_categoria = categorias_disponiveis.index(agente.get('categoria', 'Social'))
                        else:
                            index_categoria = 0
                            
                        nova_categoria = st.selectbox(
                            "Categoria:",
                            categorias_disponiveis,
                            index=index_categoria,
                            help="Organize o agente por área de atuação"
                        )
                        
                        # NOVO: Squad permitido
                        squads_disponiveis = ["Todos", "Syngenta", "SME", "Enterprise"]
                        squad_atual = agente.get('squad_permitido', 'Todos')
                        if squad_atual in squads_disponiveis:
                            index_squad = squads_disponiveis.index(squad_atual)
                        else:
                            index_squad = 0
                            
                        novo_squad_permitido = st.selectbox(
                            "Squad Permitido:",
                            squads_disponiveis,
                            index=index_squad,
                            help="Selecione qual squad pode ver e usar este agente"
                        )
                        
                        # Interface diferente para agentes de monitoramento
                        if nova_categoria == "Monitoramento":
                            st.info("🔍 **Agente de Monitoramento**: Este agente será usado apenas na aba de Monitoramento de Redes.")
                            
                            # Para monitoramento, apenas base de conhecimento
                            nova_base = st.text_area(
                                "Base de Conhecimento para Monitoramento:", 
                                value=agente.get('base_conhecimento', ''),
                                height=300,
                                help="Esta base será usada exclusivamente para monitoramento de redes sociais"
                            )
                            
                            # Campos específicos ocultos para monitoramento
                            novo_prompt = ""
                            nova_comment = ""
                            novo_planejamento = ""
                            agente_mae_id = None
                            herdar_elementos = []
                            
                            # Remover herança se existir
                            if agente.get('agente_mae_id'):
                                st.warning("⚠️ Agentes de monitoramento não suportam herança. A herança será removida.")
                            
                        else:
                            # Para outras categorias, manter estrutura original
                            
                            # Informações de herança (apenas se não for monitoramento)
                            if agente.get('agente_mae_id'):
                                agente_mae = obter_agente(agente['agente_mae_id'])
                                if agente_mae:
                                    st.info(f"🔗 Este agente é filho de: {agente_mae['nome']}")
                                    st.write(f"Elementos herdados: {', '.join(agente.get('herdar_elementos', []))}")
                            
                            # Opção para tornar independente
                            if agente.get('agente_mae_id'):
                                tornar_independente = st.checkbox("Tornar agente independente (remover herança)")
                                if tornar_independente:
                                    agente_mae_id = None
                                    herdar_elementos = []
                                else:
                                    agente_mae_id = agente.get('agente_mae_id')
                                    herdar_elementos = agente.get('herdar_elementos', [])
                            else:
                                agente_mae_id = None
                                herdar_elementos = []
                                # Opção para adicionar herança
                                adicionar_heranca = st.checkbox("Adicionar herança de agente mãe")
                                if adicionar_heranca:
                                    # Listar TODOS os agentes disponíveis para herança (excluindo o próprio e monitoramento)
                                    agentes_mae = listar_agentes_para_heranca(agente['_id'])
                                    agentes_mae = [agente_mae for agente_mae in agentes_mae if agente_mae.get('categoria') != 'Monitoramento']
                                    
                                    if agentes_mae:
                                        agente_mae_options = {f"{agente_mae['nome']} ({agente_mae.get('categoria', 'Social')})": agente_mae['_id'] for agente_mae in agentes_mae}
                                        if agente_mae_options:
                                            agente_mae_selecionado = st.selectbox(
                                                "Agente Mãe:",
                                                list(agente_mae_options.keys()),
                                                help="Selecione o agente do qual este agente irá herdar elementos"
                                            )
                                            agente_mae_id = agente_mae_options[agente_mae_selecionado]
                                            herdar_elementos = st.multiselect(
                                                "Elementos para herdar:",
                                                ["system_prompt", "base_conhecimento", "comments", "planejamento"],
                                                default=herdar_elementos
                                            )
                                        else:
                                            st.info("Nenhum agente disponível para herança.")
                                    else:
                                        st.info("Nenhum agente disponível para herança.")
                            
                            novo_prompt = st.text_area("Prompt de Sistema:", value=agente['system_prompt'], height=150)
                            nova_base = st.text_area("Brand Guidelines:", value=agente.get('base_conhecimento', ''), height=200)
                            nova_comment = st.text_area("Comentários:", value=agente.get('comments', ''), height=200)
                            novo_planejamento = st.text_area("Planejamento:", value=agente.get('planejamento', ''), height=200)
                        
                        submitted = st.form_submit_button("Atualizar Agente")
                        if submitted:
                            if novo_nome:
                                atualizar_agente(
                                    agente['_id'], 
                                    novo_nome, 
                                    novo_prompt, 
                                    nova_base, 
                                    nova_comment, 
                                    novo_planejamento,
                                    nova_categoria,
                                    novo_squad_permitido,  # Novo campo
                                    agente_mae_id,
                                    herdar_elementos
                                )
                                st.success(f"Agente '{novo_nome}' atualizado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Nome é obrigatório!")
            else:
                st.info("Nenhum agente criado ainda.")
        
        with sub_tab3:
            st.subheader("Gerenciar Agentes")
            
            # Mostrar informações do usuário atual
            current_squad = get_current_squad()
            if current_squad == "admin":
                st.info("👑 Modo Administrador: Visualizando todos os agentes do sistema")
            else:
                st.info(f"👤 Visualizando agentes do squad {current_squad} e squad 'Todos'")
            
            # Filtros por categoria - AGORA COM MONITORAMENTO
            categorias = ["Todos", "Social", "SEO", "Conteúdo", "Monitoramento"]
            categoria_filtro = st.selectbox("Filtrar por categoria:", categorias)
            
            agentes = listar_agentes()
            
            # Aplicar filtro
            if categoria_filtro != "Todos":
                agentes = [agente for agente in agentes if agente.get('categoria') == categoria_filtro]
            
            if agentes:
                for i, agente in enumerate(agentes):
                    with st.expander(f"{agente['nome']} - {agente.get('categoria', 'Social')} - Squad: {agente.get('squad_permitido', 'Todos')} - Criado em {agente['data_criacao'].strftime('%d/%m/%Y')}"):
                        
                        # Mostrar proprietário se for admin
                        owner_info = ""
                        if current_squad == "admin" and agente.get('criado_por'):
                            owner_info = f" | 👤 {agente['criado_por']}"
                            st.write(f"**Proprietário:** {agente['criado_por']}")
                            st.write(f"**Squad do Criador:** {agente.get('criado_por_squad', 'N/A')}")
                        
                        # Mostrar informações específicas por categoria
                        if agente.get('categoria') == 'Monitoramento':
                            st.info("🔍 **Agente de Monitoramento** - Usado apenas na aba de Monitoramento de Redes")
                            
                            if agente.get('base_conhecimento'):
                                st.write(f"**Base de Conhecimento:** {agente['base_conhecimento'][:200]}...")
                            else:
                                st.warning("⚠️ Base de conhecimento não configurada")
                            
                            # Agentes de monitoramento não mostram outros campos
                            st.write("**System Prompt:** (Não utilizado em monitoramento)")
                            st.write("**Comentários:** (Não utilizado em monitoramento)")
                            st.write("**Planejamento:** (Não utilizado em monitoramento)")
                            
                        else:
                            # Para outras categorias, mostrar estrutura completa
                            if agente.get('agente_mae_id'):
                                agente_mae = obter_agente(agente['agente_mae_id'])
                                if agente_mae:
                                    st.write(f"**🔗 Herda de:** {agente_mae['nome']}")
                                    st.write(f"**Elementos herdados:** {', '.join(agente.get('herdar_elementos', []))}")
                            
                            st.write(f"**Prompt de Sistema:** {agente['system_prompt'][:100]}..." if agente['system_prompt'] else "**Prompt de Sistema:** (herdado ou vazio)")
                            if agente.get('base_conhecimento'):
                                st.write(f"**Brand Guidelines:** {agente['base_conhecimento'][:200]}...")
                            if agente.get('comments'):
                                st.write(f"**Comentários do cliente:** {agente['comments'][:200]}...")
                            if agente.get('planejamento'):
                                st.write(f"**Planejamento:** {agente['planejamento'][:200]}...")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Selecionar para Chat", key=f"select_{i}"):
                                agente_completo = obter_agente_com_heranca(agente['_id'])
                                st.session_state.agente_selecionado = agente_completo
                                st.session_state.messages = []
                                st.success(f"Agente '{agente['nome']}' selecionado!")
                                st.rerun()
                        with col2:
                            if st.button("Desativar", key=f"delete_{i}"):
                                desativar_agente(agente['_id'])
                                st.success(f"Agente '{agente['nome']}' desativado!")
                                st.rerun()
            else:
                st.info("Nenhum agente encontrado para esta categoria.")


# --- NOVA ABA: PLAYBOOK ---
with tab_mapping["📚 Playbook"]:
    st.header("📚 Playbook - Gerenciamento Inteligente de Base de Conhecimento")
    st.markdown("Modifique a base de conhecimento dos agentes usando instruções em linguagem natural.")
    
    # Seleção de agente para playbook
    agentes_playbook = listar_agentes()
    
    if not agentes_playbook:
        st.warning("❌ Nenhum agente disponível para edição.")
    else:
        # Preparar opções para selectbox
        opcoes_agentes_playbook = []
        for agente in agentes_playbook:
            descricao = f"{agente['nome']} - {agente.get('categoria', 'Social')}"
            if agente.get('agente_mae_id'):
                descricao += " 🔗"
            opcoes_agentes_playbook.append((descricao, agente))
        
        agente_selecionado_desc = st.selectbox(
            "Selecione o agente para editar:",
            options=[op[0] for op in opcoes_agentes_playbook],
            key="selectbox_playbook_agente"
        )
        
        # Encontrar agente selecionado
        agente_playbook = None
        for desc, agente in opcoes_agentes_playbook:
            if desc == agente_selecionado_desc:
                agente_playbook = agente
                break
        
        if agente_playbook:
            st.subheader(f"📝 Editando: {agente_playbook['nome']}")
            
            # Abas para diferentes elementos
            playbook_tab1, playbook_tab2, playbook_tab3 = st.tabs(["🔄 Editar Base", "📋 Histórico", "⚡ Exemplos"])
            
            with playbook_tab1:
                st.markdown("### Instrução para Modificação")
                
                # Seleção do elemento a modificar
                elemento_tipo = st.selectbox(
                    "Elemento a modificar:",
                    ["base_conhecimento", "system_prompt", "comments", "planejamento"],
                    format_func=lambda x: {
                        "base_conhecimento": "Brand Guidelines",
                        "system_prompt": "Prompt do Sistema",
                        "comments": "Comentários do Cliente",
                        "planejamento": "Planejamento"
                    }[x]
                )
                
                # Mostrar conteúdo atual
                conteudo_atual = agente_playbook.get(elemento_tipo, "")
                
                with st.expander("📄 Ver conteúdo atual", expanded=False):
                    if conteudo_atual:
                        st.text_area(f"Conteúdo atual ({elemento_tipo}):", 
                                   conteudo_atual, 
                                   height=200,
                                   disabled=True)
                    else:
                        st.info("Este elemento está vazio ou herdado.")
                
                # Formulário para instrução
                with st.form("form_playbook"):
                    instrucao = st.text_area(
                        "Digite sua instrução:",
                        height=150,
                        placeholder="Exemplo: Remova todas as referências à cor preta. Altere 'tom técnico' para 'tom acessível'. Adicione uma seção sobre novas diretrizes de marca.",
                        help="Descreva em linguagem natural o que deve ser alterado na base de conhecimento."
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        preview = st.form_submit_button("👁️ Visualizar Alterações", type="secondary")
                    with col_btn2:
                        aplicar = st.form_submit_button("✅ Aplicar Alterações", type="primary")
                    
                    if preview or aplicar:
                        if not instrucao:
                            st.error("Por favor, digite uma instrução.")
                        elif not conteudo_atual:
                            st.error("Não há conteúdo para modificar neste elemento.")
                        else:
                            with st.spinner("Processando com Gemini..."):
                                novo_conteudo, mensagem = processar_playbook(
                                    agente_playbook['_id'],
                                    instrucao,
                                    conteudo_atual,
                                    elemento_tipo
                                )
                                
                                if novo_conteudo:
                                    # Mostrar diferenças
                                    st.subheader("🔍 Comparação")
                                    
                                    col_diff1, col_diff2 = st.columns(2)
                                    with col_diff1:
                                        st.markdown("**Antes:**")
                                        st.text_area("Conteúdo anterior:", conteudo_atual, height=300, disabled=True)
                                    
                                    with col_diff2:
                                        st.markdown("**Depois:**")
                                        st.text_area("Novo conteúdo:", novo_conteudo, height=300, disabled=True)
                                    
                                    # Aplicar se solicitado
                                    if aplicar:
                                        sucesso, msg_atualizacao = atualizar_elemento_agente(
                                            agente_playbook['_id'],
                                            elemento_tipo,
                                            novo_conteudo
                                        )
                                        
                                        if sucesso:
                                            st.success("✅ Alteração aplicada com sucesso!")
                                            st.balloons()
                                            
                                            # Atualizar agente na sessão se for o mesmo
                                            if (st.session_state.agente_selecionado and 
                                                st.session_state.agente_selecionado['_id'] == agente_playbook['_id']):
                                                st.session_state.agente_selecionado = obter_agente_com_heranca(agente_playbook['_id'])
                                        else:
                                            st.error(msg_atualizacao)
                                else:
                                    st.error(mensagem)
            
            with playbook_tab2:
                st.markdown("### 📜 Histórico de Alterações")
                
                logs = obter_logs_playbook(agente_playbook['_id'], limite=15)
                
                if logs:
                    for i, log in enumerate(logs):
                        with st.expander(f"{log['data_modificacao'].strftime('%d/%m/%Y %H:%M')} - {log['usuario']} - {log['elemento_tipo']} - {log['status']}", 
                                       expanded=False):
                            
                            col_log1, col_log2, col_log3 = st.columns([2, 1, 1])
                            
                            with col_log1:
                                st.write(f"**Instrução:** {log.get('instrucao_original', 'N/A')}")
                                st.write(f"**Status:** {log.get('status', 'N/A')}")
                                if log.get('erro'):
                                    st.error(f"Erro: {log['erro']}")
                            
                            with col_log2:
                                if st.button("📄 Ver Detalhes", key=f"ver_log_{i}"):
                                    st.session_state.log_detalhe = log
                            
                            with col_log3:
                                if (log.get('status') == 'processado' and 
                                    log.get('base_anterior') and 
                                    log.get('base_nova')):
                                    if st.button("↩️ Reverter", key=f"reverter_{i}"):
                                        with st.spinner("Revertendo..."):
                                            sucesso, msg = reverter_alteracao(str(log['_id']))
                                            if sucesso:
                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)
                    
                    # Modal de detalhes do log
                    if 'log_detalhe' in st.session_state and st.session_state.log_detalhe:
                        st.subheader("📋 Detalhes da Alteração")
                        log = st.session_state.log_detalhe
                        
                        col_det1, col_det2 = st.columns(2)
                        with col_det1:
                            st.markdown("**Antes:**")
                            if log.get('base_anterior'):
                                st.text_area("Conteúdo anterior:", log['base_anterior'], height=200, disabled=True)
                        
                        with col_det2:
                            st.markdown("**Depois:**")
                            if log.get('base_nova'):
                                st.text_area("Novo conteúdo:", log['base_nova'], height=200, disabled=True)
                        
                        if st.button("Fechar Detalhes"):
                            st.session_state.log_detalhe = None
                            st.rerun()
                
                else:
                    st.info("Nenhuma alteração registrada para este agente.")
            
            with playbook_tab3:
                st.markdown("### ⚡ Exemplos de Instruções")
                
                st.info("""
                **Instruções para remover conteúdo:**
                - "Remova todas as referências à cor preta"
                - "Exclua a seção sobre políticas antigas"
                - "Retire menções ao produto descontinuado XYZ"
                
                **Instruções para adicionar conteúdo:**
                - "Adicione uma seção sobre novas diretrizes de sustentabilidade"
                - "Inclua informações sobre o produto Fortenza Elite"
                - "Adicione exemplos de tom de voz para redes sociais"
                
                **Instruções para modificar conteúdo:**
                - "Altere 'tom técnico' para 'tom acessível' em todo o documento"
                - "Substitua 'cliente' por 'parceiro' onde aparecer"
                - "Atualize os valores da missão da empresa"
                
                **Instruções para reorganizar:**
                - "Reorganize as seções por ordem de importância"
                - "Mova a parte sobre compliance para o início"
                - "Agrupe todas as informações sobre produtos SYN"
                """)
                
                st.markdown("### 💡 Dicas")
                st.success("""
                1. **Seja específico**: Quanto mais detalhada a instrução, melhor o resultado
                2. **Mantenha o contexto**: O Gemini preserva o estilo original
                3. **Revise sempre**: Confira as alterações antes de aplicar
                4. **Use o histórico**: Todas as alterações são registradas e podem ser revertidas
                """)

# --- NOVA ABA: TRILHA DE CONHECIMENTO (COM FLUXOGRAMA) ---
with tab_mapping["🧠 Trilha de Conhecimento"]:
    st.header("🧠 Gerador de Trilha de Conhecimento")
    st.markdown("Crie trilhas personalizadas de aprendizado com **fluxogramas visuais**")
    
    # Abas dentro da trilha de conhecimento
    trilha_tab1, trilha_tab2 = st.tabs(["🔄 Gerar Novo Fluxograma", "📚 Fluxogramas Salvos"])
    
    with trilha_tab1:
        st.subheader("Informações do Colaborador")
        
        # Exemplo rápido para testar
        with st.expander("💡 Exemplo Rápido para Testar", expanded=False):
            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                if st.button("👨‍💻 Exemplo Desenvolvedor"):
                    st.session_state.exemplo_preenchido = {
                        "nome": "Carlos Silva",
                        "equipe": "Desenvolvimento Frontend",
                        "funcao": "Desenvolvedor React",
                        "cargo": "Pleno",
                        "tasks": """- Desenvolvimento de componentes React
- Integração com APIs REST
- Otimização de performance
- Code review com equipe júnior
- Testes unitários e integração"""
                    }
                    st.success("Exemplo carregado! Os campos foram preenchidos automaticamente.")
                    
            with col_ex2:
                if st.button("📊 Exemplo Analista"):
                    st.session_state.exemplo_preenchido = {
                        "nome": "Ana Santos",
                        "equipe": "Análise de Dados",
                        "funcao": "Analista de BI",
                        "cargo": "Sênior",
                        "tasks": """- Modelagem de dados
- Criação de dashboards
- Análise de métricas
- Relatórios executivos
- Treinamento de equipe"""
                    }
                    st.success("Exemplo carregado! Os campos foram preenchidos automaticamente.")
        
        with st.form("form_fluxograma_conhecimento"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Preencher com exemplo se existir
                nome_val = ""
                equipe_val = ""
                if 'exemplo_preenchido' in st.session_state:
                    nome_val = st.session_state.exemplo_preenchido["nome"]
                    equipe_val = st.session_state.exemplo_preenchido["equipe"]
                
                nome = st.text_input("Nome do Colaborador:", 
                                    value=nome_val,
                                    placeholder="João Silva")
                equipe = st.text_input("Equipe/Squad:", 
                                      value=equipe_val,
                                      placeholder="Marketing Digital")
                
            with col2:
                # Preencher com exemplo se existir
                funcao_val = ""
                cargo_val = ""
                if 'exemplo_preenchido' in st.session_state:
                    funcao_val = st.session_state.exemplo_preenchido["funcao"]
                    cargo_val = st.session_state.exemplo_preenchido["cargo"]
                
                funcao = st.text_input("Função Principal:", 
                                      value=funcao_val,
                                      placeholder="Analista de Mídias Sociais")
                cargo = st.text_input("Cargo/Hierarquia:", 
                                     value=cargo_val,
                                     placeholder="Analista Júnior")
            
            # Preencher tasks com exemplo se existir
            tasks_val = ""
            if 'exemplo_preenchido' in st.session_state:
                tasks_val = st.session_state.exemplo_preenchido["tasks"]
            
            tasks_exemplo = st.text_area(
                "Exemplos de Tasks/Responsabilidades:",
                value=tasks_val,
                height=150,
                placeholder="Ex: Criar conteúdo para Instagram, analisar métricas de engajamento, responder comentários, criar relatórios semanais...",
                help="Descreva as principais atividades do colaborador"
            )
            
            modelo_ai = st.selectbox(
                "Modelo de IA para gerar:",
                ["Gemini", "Claude"],
                help="Escolha qual modelo de IA usar para gerar o fluxograma"
            )
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                preview_btn = st.form_submit_button("👁️ Pré-visualizar", type="secondary")
            with col_btn2:
                gerar_btn = st.form_submit_button("🎯 Gerar Fluxograma", type="primary")
            with col_btn3:
                salvar_btn = st.form_submit_button("💾 Gerar e Salvar", type="primary")
        
        # Processar ações dos botões
        if preview_btn or gerar_btn or salvar_btn:
            if not all([nome, equipe, funcao, cargo, tasks_exemplo]):
                st.error("❌ Por favor, preencha todos os campos!")
            else:
                with st.spinner("🧠 Gerando fluxograma de conhecimento..."):
                    data_fluxograma, flowchart_image, texto_descritivo = generate_knowledge_flowchart(
                        nome=nome,
                        equipe=equipe,
                        funcao=funcao,
                        cargo=cargo,
                        tasks_exemplo=tasks_exemplo,
                        modelo=modelo_ai.lower()
                    )
                    
                    if flowchart_image and texto_descritivo and not texto_descritivo.startswith("❌"):
                        st.success("✅ Fluxograma gerado com sucesso!")
                        
                        # Colunas para exibir fluxograma e texto
                        col_fluxo, col_texto = st.columns([2, 1])
                        
                        with col_fluxo:
                            st.subheader("📊 Fluxograma da Trilha de Conhecimento")
                            st.image(flowchart_image, use_container_width=True)
                            
                            # Botões de download
                            col_dl1, col_dl2 = st.columns(2)
                            with col_dl1:
                                flowchart_image.seek(0)
                                st.download_button(
                                    label="📥 Baixar Fluxograma (PNG)",
                                    data=flowchart_image,
                                    file_name=f"fluxograma_{nome}_{datetime.datetime.now().strftime('%Y%m%d')}.png",
                                    mime="image/png"
                                )
                            with col_dl2:
                                if data_fluxograma:
                                    st.download_button(
                                        label="📊 Baixar Dados (JSON)",
                                        data=json.dumps(data_fluxograma, indent=2, ensure_ascii=False),
                                        file_name=f"dados_fluxograma_{nome}.json",
                                        mime="application/json"
                                    )
                        
                        with col_texto:
                            st.subheader("📝 Descrição da Trilha")
                            with st.expander("Ver descrição completa", expanded=True):
                                st.markdown(texto_descritivo)
                        
                        # Mostrar dados estruturados se disponíveis
                        if data_fluxograma:
                            with st.expander("🔍 Dados Estruturados", expanded=False):
                                st.json(data_fluxograma)
                        
                        # Salvar se solicitado
                        if salvar_btn:
                            sucesso, mensagem = save_flowchart_to_db(
                                nome, equipe, funcao, cargo, tasks_exemplo, 
                                data_fluxograma, flowchart_image, texto_descritivo
                            )
                            if sucesso:
                                st.success(mensagem)
                            else:
                                st.error(mensagem)
                    else:
                        st.error(texto_descritivo)
    
    with trilha_tab2:
        st.subheader("📚 Fluxogramas Salvos")
        
        # Carregar fluxogramas salvos
        fluxogramas_salvos = get_knowledge_paths(limit=20)
        
        if fluxogramas_salvos:
            for i, fluxograma in enumerate(fluxogramas_salvos):
                with st.expander(f"{fluxograma.get('nome_colaborador', 'N/A')} - {fluxograma.get('equipe', 'N/A')} - {fluxograma.get('data_criacao', 'N/A').strftime('%d/%m/%Y')}", 
                               expanded=False):
                    
                    col_fs1, col_fs2, col_fs3 = st.columns([3, 1, 1])
                    
                    with col_fs1:
                        st.write(f"**Cargo:** {fluxograma.get('cargo', 'N/A')}")
                        st.write(f"**Função:** {fluxograma.get('funcao', 'N/A')}")
                        st.write(f"**Criado por:** {fluxograma.get('criado_por', 'N/A')}")
                    
                    with col_fs2:
                        if st.button("👀 Ver", key=f"ver_fluxograma_{i}"):
                            st.session_state.fluxograma_selecionado = fluxograma
                    
                    with col_fs3:
                        if st.button("📥 Exportar", key=f"export_fluxograma_{i}"):
                            # Criar arquivo para download
                            if fluxograma.get('fluxograma_imagem'):
                                # Decodificar imagem base64
                                img_data = base64.b64decode(fluxograma['fluxograma_imagem'])
                                st.download_button(
                                    label="Baixar Fluxograma",
                                    data=img_data,
                                    file_name=f"fluxograma_{fluxograma.get('nome_colaborador', 'fluxograma')}.png",
                                    mime="image/png",
                                    key=f"download_img_{i}"
                                )
            
            # Modal para visualizar fluxograma selecionado
            if 'fluxograma_selecionado' in st.session_state and st.session_state.fluxograma_selecionado:
                st.subheader("📋 Fluxograma de Conhecimento Detalhado")
                fluxograma = st.session_state.fluxograma_selecionado
                
                col_det1, col_det2 = st.columns([2, 1])
                
                with col_det1:
                    st.write(f"**Colaborador:** {fluxograma.get('nome_colaborador', 'N/A')}")
                    st.write(f"**Equipe:** {fluxograma.get('equipe', 'N/A')}")
                    st.write(f"**Cargo:** {fluxograma.get('cargo', 'N/A')}")
                    st.write(f"**Função:** {fluxograma.get('funcao', 'N/A')}")
                    
                    # Mostrar imagem do fluxograma se existir
                    if fluxograma.get('fluxograma_imagem'):
                        st.subheader("📊 Fluxograma da Trilha")
                        img_data = base64.b64decode(fluxograma['fluxograma_imagem'])
                        img = BytesIO(img_data)
                        st.image(img, use_container_width=True)
                
                with col_det2:
                    with st.expander("📝 Tasks/Responsabilidades", expanded=False):
                        st.write(fluxograma.get('tasks_exemplo', 'N/A'))
                    
                    with st.expander("📋 Metadados", expanded=False):
                        st.write(f"**Data de Criação:** {fluxograma.get('data_criacao', 'N/A').strftime('%d/%m/%Y %H:%M')}")
                        st.write(f"**Squad:** {fluxograma.get('squad', 'N/A')}")
                        st.write(f"**Tipo:** {fluxograma.get('tipo', 'fluxograma')}")
                
                if fluxograma.get('texto_descritivo'):
                    with st.expander("📄 Descrição da Trilha", expanded=True):
                        st.markdown(fluxograma['texto_descritivo'])
                
                col_btn_close, _ = st.columns([1, 3])
                with col_btn_close:
                    if st.button("Fechar Visualização"):
                        st.session_state.fluxograma_selecionado = None
                        st.rerun()
        
        else:
            st.info("📭 Nenhum fluxograma de conhecimento salvo ainda.")




# --- NOVA ABA: CURSOS E CAPACITAÇÕES ---
with tab_mapping["🎓 Cursos e Capacitações"]:
    st.header("🎓 Biblioteca de Cursos")
    
    # Verificar se a conexão está disponível
    if 'collection_cursos' not in globals() or collection_cursos is None:
        st.error("⚠️ Conexão com banco de cursos não disponível no momento.")
        st.info("Por favor, verifique a conexão com o MongoDB.")
        
        # Botão para tentar reconectar
        if st.button("🔄 Tentar Reconectar"):
            try:
                # Tentar nova conexão
                client_cursos = MongoClient(
                    "mongodb+srv://julialedo_db_user:hr7vHI5EjMwuRT9X@cluster0.u0sm02b.mongodb.net/cursos_db?retryWrites=true&w=majority&appName=Cluster0",
                    tls=True,
                    tlsAllowInvalidCertificates=True,
                    serverSelectionTimeoutMS=10000
                )
                db_cursos = client_cursos['cursos_db']
                collection_cursos = db_cursos['cursos']
                collection_categorias = db_cursos['categorias']
                st.success("✅ Reconectado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Falha na reconexão: {str(e)}")
        
        st.stop()
    
    st.markdown("Cursos organizados em pastas: **Categoria → Subpasta → Cursos**")
    
    # Abas simples
    tab_explorar, tab_buscar, tab_admin, tab_chat = st.tabs(["📁 Explorar Pastas", "🔍 Buscar Cursos", "⚙️ Admin", "🤖 Chat com Especialista"])
    
    with tab_explorar:
        # Botão para admin verificar estrutura
        if get_current_squad() == "admin":
            col_admin1, col_admin2 = st.columns([1, 3])
            with col_admin1:
                if st.button("📊 Verificar Banco", type="secondary", use_container_width=True, key="verificar_banco"):
                    try:
                        total_categorias = collection_categorias.count_documents({})
                        total_cursos = collection_cursos.count_documents({})
                        
                        categorias = collection_categorias.count_documents({"tipo": "categoria"})
                        subpastas = collection_categorias.count_documents({"tipo": "subpasta"})
                        
                        st.success(f"""
                        **📊 Estatísticas do Banco:**
                        - Total documentos em 'categorias': {total_categorias}
                        - Categorias: {categorias}
                        - Subpastas: {subpastas}
                        - Cursos: {total_cursos}
                        """)
                    except Exception as e:
                        st.error(f"Erro ao verificar banco: {str(e)}")
        
        st.divider()
        
        # Obter categorias
        categorias = obter_categorias()
        
        if not categorias:
            st.info("📭 Nenhuma pasta de cursos encontrada.")
            st.info("Para criar a estrutura inicial, execute o script de teste.")
            
            # Mostrar botão para criar estrutura se for admin
            if get_current_squad() == "admin":
                if st.button("🚀 Criar Estrutura de Exemplo", type="primary", key="criar_estrutura"):
                    with st.spinner("Criando estrutura..."):
                        sucesso, mensagem = inicializar_cursos_base()
                        if sucesso:
                            st.success(mensagem)
                            st.rerun()
                        else:
                            st.error(mensagem)
        else:
            # Se categoria selecionada, mostrar seu conteúdo
            if 'categoria_selecionada' in st.session_state:
                categoria_id = st.session_state.categoria_selecionada
                categoria = next((c for c in categorias if c['_id'] == categoria_id), None)
                
                if categoria:
                    # Cabeçalho com botão voltar
                    col_voltar, col_titulo = st.columns([1, 5])
                    with col_voltar:
                        if st.button("← Voltar", use_container_width=True, key="voltar_categorias"):
                            del st.session_state.categoria_selecionada
                            st.rerun()
                    with col_titulo:
                        st.subheader(f"{categoria.get('icone', '📁')} {categoria['nome']}")
                        st.caption(categoria.get('descricao', ''))
                    
                    # Obter subpastas desta categoria
                    subpastas = obter_subpastas(categoria_id)
                    
                    if subpastas:
                        for subpasta in subpastas:
                            with st.expander(f"{subpasta.get('icone', '📂')} **{subpasta['nome']}**", expanded=True):
                                st.write(subpasta.get('descricao', ''))
                                
                                # Obter cursos desta subpasta
                                cursos = obter_cursos(subpasta['_id'])
                                
                                if cursos:
                                    st.write(f"**{len(cursos)} cursos disponíveis:**")
                                    for curso in cursos:
                                        # Card do curso
                                        with st.container(border=True):
                                            col_info, col_acao = st.columns([3, 1])
                                            
                                            with col_info:
                                                st.markdown(f"**{curso['titulo']}**")
                                                st.caption(curso.get('descricao', '')[:120] + "...")
                                                
                                                # Metadados
                                                col_meta1, col_meta2, col_meta3 = st.columns(3)
                                                with col_meta1:
                                                    st.caption(f"⏱️ {curso.get('duracao', 'N/A')}")
                                                with col_meta2:
                                                    st.caption(f"📊 {curso.get('nivel', 'N/A')}")
                                                with col_meta3:
                                                    if curso.get('tags'):
                                                        st.caption(f"🏷️ {curso['tags'][0]}")
                                            
                                            with col_acao:
                                                if curso.get('link_drive'):
                                                    st.link_button(
                                                        "▶️ Assistir",
                                                        curso['link_drive'],
                                                        use_container_width=True,
                                                        help="Abrir vídeo no Google Drive"
                                                    )
                                                else:
                                                    st.info("Em breve")
                                        
                                        # Espaço entre cursos
                                        st.write("")
                                else:
                                    st.info("Nenhum curso disponível nesta pasta.")
                    else:
                        st.info("Nenhuma subpasta encontrada.")
            else:
                # Mostrar todas as categorias
                st.write("### Selecione uma categoria:")
                
                cols = st.columns(min(len(categorias), 3))
                
                for idx, categoria in enumerate(categorias):
                    with cols[idx % 3]:
                        # Card da categoria
                        with st.container(border=True):
                            st.markdown(f"## {categoria.get('icone', '📁')}")
                            st.markdown(f"**{categoria['nome']}**")
                            st.caption(categoria.get('descricao', '')[:60] + "...")
                            
                            # Botão para abrir categoria
                            if st.button("Abrir", key=f"abrir_{categoria['_id']}", use_container_width=True):
                                st.session_state.categoria_selecionada = categoria['_id']
                                st.rerun()
    
    with tab_buscar:
        st.subheader("Buscar por Palavra-chave")
        
        # Campo de busca
        busca = st.text_input("O que você quer aprender?",
                            placeholder="Digite palavras como: Python, IA, Machine Learning...",
                            key="campo_busca_cursos")
        
        col_busca1, col_busca2 = st.columns([3, 1])
        with col_busca2:
            buscar_btn = st.button("🔍 Buscar", type="primary", use_container_width=True, key="btn_buscar_cursos")
        
        # Inicializar session state para busca
        if 'resultados_busca_cursos' not in st.session_state:
            st.session_state.resultados_busca_cursos = None
        if 'ultima_busca_cursos' not in st.session_state:
            st.session_state.ultima_busca_cursos = ""
        
        if buscar_btn or (st.session_state.ultima_busca_cursos and st.session_state.ultima_busca_cursos == busca):
            if busca.strip():
                st.session_state.ultima_busca_cursos = busca
                
                # Busca simples em título e descrição
                resultados = []
                todos_cursos = obter_cursos()
                
                for curso in todos_cursos:
                    if (busca.lower() in curso.get('titulo', '').lower() or 
                        busca.lower() in curso.get('descricao', '').lower() or
                        any(busca.lower() in tag.lower() for tag in curso.get('tags', []))):
                        resultados.append(curso)
                
                st.session_state.resultados_busca_cursos = resultados
                
                if resultados:
                    st.success(f"🎯 Encontrados {len(resultados)} cursos:")
                    
                    for curso in resultados:
                        with st.container(border=True):
                            col_res1, col_res2 = st.columns([3, 1])
                            
                            with col_res1:
                                st.markdown(f"**{curso['titulo']}**")
                                st.caption(curso.get('descricao', ''))
                                
                                # Informações rápidas
                                col_info1, col_info2, col_info3 = st.columns(3)
                                with col_info1:
                                    st.caption(f"📊 {curso.get('nivel', '')}")
                                with col_info2:
                                    st.caption(f"⏱️ {curso.get('duracao', '')}")
                                with col_info3:
                                    if curso.get('tags'):
                                        st.caption(f"🏷️ {curso['tags'][0]}")
                            
                            with col_res2:
                                if curso.get('link_drive'):
                                    st.link_button(
                                        "▶️ Assistir",
                                        curso['link_drive'],
                                        use_container_width=True,
                                        help="Abrir vídeo no Google Drive"
                                    )
                                else:
                                    st.info("Em breve", help="Link não disponível")
                        
                        st.write("")
                else:
                    st.info("😕 Nenhum curso encontrado. Tente outras palavras-chave.")
                    
                    # Sugestões de busca
                    st.info("💡 **Sugestões:** Python, IA, Machine Learning, Data Science, Marketing, Instagram")
            else:
                st.warning("⚠️ Digite algo para buscar.")
        elif st.session_state.resultados_busca_cursos:
            # Mostrar resultados anteriores
            resultados = st.session_state.resultados_busca_cursos
            if resultados:
                st.info(f"📚 Mostrando {len(resultados)} cursos da busca anterior")
                
                for curso in resultados:
                    with st.container(border=True):
                        col_res1, col_res2 = st.columns([3, 1])
                        
                        with col_res1:
                            st.markdown(f"**{curso['titulo']}**")
                            st.caption(curso.get('descricao', ''))
                            
                            col_info1, col_info2, col_info3 = st.columns(3)
                            with col_info1:
                                st.caption(f"📊 {curso.get('nivel', '')}")
                            with col_info2:
                                st.caption(f"⏱️ {curso.get('duracao', '')}")
                            with col_info3:
                                if curso.get('tags'):
                                    st.caption(f"🏷️ {curso['tags'][0]}")
                        
                        with col_res2:
                            if curso.get('link_drive'):
                                st.link_button(
                                    "▶️ Assistir",
                                    curso['link_drive'],
                                    use_container_width=True,
                                    help="Abrir vídeo no Google Drive"
                                )
        
        # Se não há busca ativa, mostrar alguns cursos aleatórios
        if not st.session_state.get('ultima_busca_cursos'):
            st.divider()
            st.subheader("📚 Cursos em Destaque")
            
            todos_cursos = obter_cursos()
            if todos_cursos:
                # Mostrar até 3 cursos
                cursos_destaque = todos_cursos[:3]
                
                for curso in cursos_destaque:
                    with st.container(border=True):
                        col_dest1, col_dest2 = st.columns([3, 1])
                        
                        with col_dest1:
                            st.markdown(f"**{curso['titulo']}**")
                            st.caption(curso.get('descricao', '')[:100] + "...")
                            
                            col_meta1, col_meta2 = st.columns(2)
                            with col_meta1:
                                st.caption(f"⏱️ {curso.get('duracao', '')}")
                            with col_meta2:
                                st.caption(f"📊 {curso.get('nivel', '')}")
                        
                        with col_dest2:
                            if curso.get('link_drive'):
                                st.link_button(
                                    "▶️ Assistir",
                                    curso['link_drive'],
                                    use_container_width=True,
                                    help="Abrir vídeo no Google Drive"
                                )
    
    with tab_admin:
        st.subheader("⚙️ Configurações de Administrador")
        
        if get_current_squad() != "admin":
            st.warning("⚠️ Acesso restrito a administradores.")
            st.stop()
        
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        
        with col_stats1:
            try:
                total_categorias = collection_categorias.count_documents({})
                st.metric("📁 Categorias/Subpastas", total_categorias)
            except:
                st.metric("📁 Categorias/Subpastas", "N/A")
        
        with col_stats2:
            try:
                total_cursos = collection_cursos.count_documents({})
                st.metric("🎓 Cursos", total_cursos)
            except:
                st.metric("🎓 Cursos", "N/A")
        
        with col_stats3:
            try:
                categorias_count = collection_categorias.count_documents({"tipo": "categoria"})
                st.metric("📂 Categorias", categorias_count)
            except:
                st.metric("📂 Categorias", "N/A")
        
        st.divider()
        
        # Botões de administração
        col_admin_btn1, col_admin_btn2, col_admin_btn3 = st.columns(3)
        
        with col_admin_btn1:
            if st.button("🔄 Recriar Estrutura", type="secondary", use_container_width=True, key="recriar_estrutura"):
                try:
                    # Limpar coleções
                    collection_categorias.delete_many({})
                    collection_cursos.delete_many({})
                    
                    # Executar script de criação (simplificado)
                    from datetime import datetime
                    
                    # Criar estrutura básica
                    categoria_tech = {
                        "_id": "tech",
                        "tipo": "categoria",
                        "nome": "Tecnologia",
                        "descricao": "Cursos de tecnologia e inovação",
                        "icone": "💻",
                        "ordem": 1,
                        "ativo": True,
                        "data_criacao": datetime.now()
                    }
                    
                    subpasta_ia = {
                        "_id": "inteligencia-artificial",
                        "tipo": "subpasta",
                        "categoria_id": "tech",
                        "nome": "Inteligência Artificial",
                        "descricao": "Cursos sobre IA, machine learning e deep learning",
                        "icone": "🤖",
                        "ordem": 1,
                        "ativo": True,
                        "data_criacao": datetime.now()
                    }
                    
                    collection_categorias.insert_many([categoria_tech, subpasta_ia])
                    
                    # Criar curso exemplo
                    curso_ia = {
                        "_id": "ia-basica",
                        "categoria_id": "tech",
                        "subpasta_id": "inteligencia-artificial",
                        "titulo": "Introdução à Inteligência Artificial",
                        "descricao": "Aprenda os conceitos fundamentais de IA",
                        "tipo": "video",
                        "link_drive": "https://drive.google.com/file/d/1sC5q5Yw6X4ABC123XYZ/view?usp=sharing",
                        "duracao": "2 horas",
                        "nivel": "Iniciante",
                        "tags": ["IA", "Machine Learning", "Python"],
                        "autor": "Equipe de IA",
                        "data_publicacao": datetime.now(),
                        "ativo": True
                    }
                    
                    collection_cursos.insert_one(curso_ia)
                    
                    st.success("✅ Estrutura recriada com sucesso!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao recriar estrutura: {str(e)}")
        
        with col_admin_btn2:
            if st.button("🗑️ Limpar Banco", type="secondary", use_container_width=True, key="limpar_banco"):
                if st.checkbox("⚠️ Confirmar exclusão de TODOS os dados de cursos?", key="confirmar_limpeza"):
                    try:
                        collection_categorias.delete_many({})
                        collection_cursos.delete_many({})
                        st.success("✅ Banco limpo com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro ao limpar banco: {str(e)}")
        
        with col_admin_btn3:
            if st.button("📋 Ver Dados Brutos", type="secondary", use_container_width=True, key="ver_dados_brutos"):
                try:
                    with st.expander("📁 Dados da Coleção 'categorias'", expanded=False):
                        categorias_raw = list(collection_categorias.find({}))
                        if categorias_raw:
                            for cat in categorias_raw:
                                st.json({
                                    "_id": str(cat.get("_id")),
                                    "tipo": cat.get("tipo"),
                                    "nome": cat.get("nome"),
                                    "categoria_id": cat.get("categoria_id"),
                                    "ativo": cat.get("ativo")
                                })
                        else:
                            st.info("Nenhum dado encontrado")
                    
                    with st.expander("🎓 Dados da Coleção 'cursos'", expanded=False):
                        cursos_raw = list(collection_cursos.find({}))
                        if cursos_raw:
                            for curso in cursos_raw:
                                st.json({
                                    "_id": str(curso.get("_id")),
                                    "titulo": curso.get("titulo"),
                                    "categoria_id": curso.get("categoria_id"),
                                    "subpasta_id": curso.get("subpasta_id"),
                                    "ativo": curso.get("ativo")
                                })
                        else:
                            st.info("Nenhum dado encontrado")
                            
                except Exception as e:
                    st.error(f"❌ Erro ao obter dados brutos: {str(e)}")



    with tab_chat:
        st.subheader("🤖 Chat com Especialista do Curso")
        st.markdown("Selecione um curso e converse com um especialista no assunto!")
        
        # Inicializar session state para o chat do curso
        if 'chat_curso_messages' not in st.session_state:
            st.session_state.chat_curso_messages = []
        
        if 'curso_selecionado_chat' not in st.session_state:
            st.session_state.curso_selecionado_chat = None
        
        # Layout em duas colunas
        col_curso, col_chat = st.columns([1, 2])
        
        with col_curso:
            st.markdown("#### 📚 Selecione um Curso")
            
            # Campo de busca rápida
            busca_curso = st.text_input("🔍 Buscar curso:", 
                                       placeholder="Digite palavras-chave...",
                                       key="busca_curso_chat_especialista")
            
            # Obter cursos
            todos_cursos = obter_cursos()
            
            if not todos_cursos:
                st.info("Nenhum curso disponível no momento.")
            else:
                # Filtrar por busca se houver
                cursos_filtrados = todos_cursos
                if busca_curso:
                    cursos_filtrados = [
                        curso for curso in todos_cursos
                        if busca_curso.lower() in curso.get('titulo', '').lower() or
                        busca_curso.lower() in curso.get('descricao', '').lower() or
                        (curso.get('tags') and any(busca_curso.lower() in tag.lower() for tag in curso.get('tags', [])))
                    ]
                
                if not cursos_filtrados:
                    st.info("Nenhum curso encontrado. Tente outros termos.")
                else:
                    # Lista de cursos para seleção
                    for curso in cursos_filtrados[:8]:  # Limitar a 8 resultados
                        titulo = curso.get('titulo', 'Curso sem título')
                        descricao = curso.get('descricao', '')[:80] + "..."
                        nivel = curso.get('nivel', '')
                        
                        # Card do curso
                        with st.container(border=True):
                            st.markdown(f"**{titulo}**")
                            st.caption(descricao)
                            st.caption(f"📊 {nivel}")
                            
                            if st.button("💬 Conversar", key=f"chat_curso_{curso.get('_id')}", 
                                        use_container_width=True):
                                st.session_state.curso_selecionado_chat = curso
                                st.session_state.chat_curso_messages = []  # Limpar conversa anterior
                                st.success(f"✅ Especialista de '{titulo}' pronto!")
                                st.rerun()
            
            # Mostrar curso selecionado atual
            if st.session_state.curso_selecionado_chat:
                st.divider()
                st.markdown("#### 📖 Curso Selecionado")
                curso = st.session_state.curso_selecionado_chat
                st.markdown(f"**{curso.get('titulo')}**")
                st.caption(curso.get('descricao', '')[:120] + "...")
                
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.caption(f"📊 {curso.get('nivel', '')}")
                with col_info2:
                    st.caption(f"⏱️ {curso.get('duracao', '')}")
                
                if curso.get('link_drive'):
                    st.link_button("▶️ Assistir Curso", curso['link_drive'], 
                                  use_container_width=True)
                
                # Botão para limpar seleção
                if st.button("🗑️ Trocar Curso", type="secondary", use_container_width=True):
                    st.session_state.curso_selecionado_chat = None
                    st.session_state.chat_curso_messages = []
                    st.rerun()
        
        with col_chat:
            st.markdown("#### 💬 Conversa com o Especialista")
            
            # Verificar se há curso selecionado
            if not st.session_state.curso_selecionado_chat:
                st.info("👈 Selecione um curso para começar a conversar!")
                st.markdown("""
                ### 💡 Como funciona:
                1. **Selecione um curso** da lista à esquerda
                2. **Faça perguntas** sobre o conteúdo do curso

                """)
            else:
                curso = st.session_state.curso_selecionado_chat
                st.markdown(f"**Especialista em:** {curso.get('titulo')}")
                
                # Área do chat
                chat_container = st.container(height=350, border=True)
                
                with chat_container:
                    # Exibir histórico da conversa
                    for message in st.session_state.chat_curso_messages:
                        if message["role"] == "user":
                            with st.chat_message("user"):
                                st.markdown(message["content"])
                        else:
                            with st.chat_message("assistant"):
                                st.markdown(message["content"])
                
                # Input para nova pergunta
                pergunta = st.chat_input(f"Pergunte sobre {curso.get('titulo')}...")
                
                if pergunta:
                    # Adicionar pergunta ao histórico
                    st.session_state.chat_curso_messages.append({
                        "role": "user", 
                        "content": pergunta
                    })
                    
                    # Exibir pergunta
                    with chat_container:
                        with st.chat_message("user"):
                            st.markdown(pergunta)
                    
                    # Gerar resposta
                    with st.spinner(f"Especialista pensando..."):
                        # Formatar histórico para contexto
                        historico_formatado = ""
                        for msg in st.session_state.chat_curso_messages[-4:]:  # Últimas 4 mensagens
                            role = "Aluno" if msg["role"] == "user" else "Especialista"
                            historico_formatado += f"{role}: {msg['content']}\n"
                        
                        # Usar a função que já criamos
                        resposta = gerar_resposta_especialista_curso(
                            pergunta,
                            curso,
                            historico_formatado
                        )
                        
                        # Adicionar resposta ao histórico
                        st.session_state.chat_curso_messages.append({
                            "role": "assistant", 
                            "content": resposta
                        })
                        
                        # Exibir resposta
                        with chat_container:
                            with st.chat_message("assistant"):
                                st.markdown(resposta)
                
                # Botões de controle
                col_ctrl1, col_ctrl2 = st.columns(2)
                with col_ctrl1:
                    if st.button("🗑️ Limpar Chat", use_container_width=True):
                        st.session_state.chat_curso_messages = []
                        st.rerun()
                with col_ctrl2:
                    if st.button("📥 Exportar Conversa", use_container_width=True):
                        # Criar texto da conversa para exportar
                        texto_conversa = f"Chat com Especialista - {curso.get('titulo')}\n"
                        texto_conversa += f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                        texto_conversa += "=" * 50 + "\n\n"
                        
                        for msg in st.session_state.chat_curso_messages:
                            role = "Aluno" if msg["role"] == "user" else "Especialista"
                            texto_conversa += f"{role}: {msg['content']}\n\n"
                        
                        # Botão de download
                        st.download_button(
                            label="📄 Baixar Conversa",
                            data=texto_conversa,
                            file_name=f"chat_{curso.get('titulo', 'curso').replace(' ', '_')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )