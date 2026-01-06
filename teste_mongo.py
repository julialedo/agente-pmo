import pymongo
from pymongo import MongoClient
import datetime
import sys

def testar_conexao_mongodb():
    """Testa a conexão com o MongoDB e cria estrutura de cursos"""
    
    print("🔗 TESTANDO CONEXÃO MONGODB")
    print("=" * 50)
    
    # SUA CONEXÃO (substitua <db_password> pela senha real)
    MONGO_URI = "mongodb+srv://julialedo_db_user:hr7vHI5EjMwuRT9X@cluster0.u0sm02b.mongodb.net/?appName=Cluster0"
    
    try:
        # 1. Testar conexão básica
        print("1. Conectando ao MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Testar conexão
        client.admin.command('ping')
        print("✅ Conexão bem-sucedida!")
        
        # 2. Listar bancos de dados disponíveis
        print("\n2. Bancos de dados disponíveis:")
        databases = client.list_database_names()
        for db_name in databases:
            print(f"   - {db_name}")
        
        # 3. Criar/Usar banco 'cursos_db'
        print("\n3. Acessando banco 'cursos_db'...")
        db = client['cursos_db']
        
        # 4. Criar coleções (se não existirem)
        print("\n4. Criando coleções...")
        
        # Coleção para categorias e subpastas
        if 'categorias' not in db.list_collection_names():
            db.create_collection('categorias')
            print("   ✅ Coleção 'categorias' criada")
        else:
            print("   ℹ️ Coleção 'categorias' já existe")
        
        # Coleção para cursos
        if 'cursos' not in db.list_collection_names():
            db.create_collection('cursos')
            print("   ✅ Coleção 'cursos' criada")
        else:
            print("   ℹ️ Coleção 'cursos' já existe")
        
        # 5. Verificar se já tem dados
        print("\n5. Verificando dados existentes...")
        
        collection_categorias = db['categorias']
        collection_cursos = db['cursos']
        
        categorias_count = collection_categorias.count_documents({})
        cursos_count = collection_cursos.count_documents({})
        
        print(f"   - Categorias/Subpastas: {categorias_count} documentos")
        print(f"   - Cursos: {cursos_count} documentos")
        
        # 6. Se estiver vazio, criar estrutura de exemplo
        if categorias_count == 0:
            print("\n6. Criando estrutura de exemplo...")
            
            # CATEGORIA: Tecnologia
            categoria_tech = {
                "_id": "tech",
                "tipo": "categoria",
                "nome": "Tecnologia",
                "descricao": "Cursos de tecnologia e inovação",
                "icone": "💻",
                "ordem": 1,
                "ativo": True,
                "data_criacao": datetime.datetime.now()
            }
            
            # SUBPASTA: Inteligência Artificial (dentro de Tech)
            subpasta_ia = {
                "_id": "inteligencia-artificial",
                "tipo": "subpasta",
                "categoria_id": "tech",
                "nome": "Inteligência Artificial",
                "descricao": "Cursos sobre IA, machine learning e deep learning",
                "icone": "🤖",
                "ordem": 1,
                "ativo": True,
                "data_criacao": datetime.datetime.now()
            }
            
            # CATEGORIA: Marketing (exemplo adicional)
            categoria_marketing = {
                "_id": "marketing",
                "tipo": "categoria",
                "nome": "Marketing",
                "descricao": "Cursos de marketing digital e estratégias",
                "icone": "📈",
                "ordem": 2,
                "ativo": True,
                "data_criacao": datetime.datetime.now()
            }
            
            # SUBPASTA: Redes Sociais (dentro de Marketing)
            subpasta_redes = {
                "_id": "redes-sociais",
                "tipo": "subpasta",
                "categoria_id": "marketing",
                "nome": "Redes Sociais",
                "descricao": "Cursos sobre gestão de redes sociais",
                "icone": "📱",
                "ordem": 1,
                "ativo": True,
                "data_criacao": datetime.datetime.now()
            }
            
            # Inserir categorias e subpastas
            collection_categorias.insert_many([
                categoria_tech,
                subpasta_ia,
                categoria_marketing,
                subpasta_redes
            ])
            
            print("   ✅ 2 categorias e 2 subpastas criadas")
            
            # CURSOS de exemplo
            curso_ia = {
                "_id": "ia-basica",
                "categoria_id": "tech",
                "subpasta_id": "inteligencia-artificial",
                "titulo": "Introdução à Inteligência Artificial",
                "descricao": "Aprenda os conceitos fundamentais de IA, machine learning e suas aplicações práticas",
                "tipo": "video",
                "link_drive": "https://drive.google.com/file/d/1sC5q5Yw6X4ABC123XYZ/view?usp=sharing",
                "duracao": "2 horas",
                "nivel": "Iniciante",
                "tags": ["IA", "Machine Learning", "Python"],
                "autor": "Equipe de IA",
                "data_publicacao": datetime.datetime.now(),
                "ativo": True
            }
            
            curso_python = {
                "_id": "python-data-science",
                "categoria_id": "tech",
                "subpasta_id": "inteligencia-artificial",
                "titulo": "Python para Data Science",
                "descricao": "Domine Python para análise de dados e machine learning",
                "tipo": "video",
                "link_drive": "https://drive.google.com/file/d/2sD6q6Yw7Y5DEF456UVW/view?usp=sharing",
                "duracao": "3 horas",
                "nivel": "Intermediário",
                "tags": ["Python", "Data Science", "Pandas", "NumPy"],
                "autor": "Equipe de Desenvolvimento",
                "data_publicacao": datetime.datetime.now(),
                "ativo": True
            }
            
            curso_instagram = {
                "_id": "instagram-marketing",
                "categoria_id": "marketing",
                "subpasta_id": "redes-sociais",
                "titulo": "Marketing no Instagram",
                "descricao": "Estratégias avançadas para crescimento no Instagram",
                "tipo": "video",
                "link_drive": "https://drive.google.com/file/d/3sE7r7Zx8Z6GHI789OPQ/view?usp=sharing",
                "duracao": "1.5 horas",
                "nivel": "Intermediário",
                "tags": ["Instagram", "Marketing", "Redes Sociais"],
                "autor": "Equipe de Marketing",
                "data_publicacao": datetime.datetime.now(),
                "ativo": True
            }
            
            # Inserir cursos
            collection_cursos.insert_many([
                curso_ia,
                curso_python,
                curso_instagram
            ])
            
            print("   ✅ 3 cursos de exemplo criados")
        else:
            print("\n6. Banco já contém dados. Pulando criação de exemplo.")
        
        # 7. Mostrar estrutura criada
        print("\n7. ESTRUTURA CRIADA:")
        print("-" * 40)
        
        # Buscar e mostrar todas as categorias
        print("\n📁 CATEGORIAS:")
        categorias = collection_categorias.find({"tipo": "categoria"}).sort("ordem", 1)
        for cat in categorias:
            print(f"  ├─ {cat['icone']} {cat['nome']} (ID: {cat['_id']})")
            
            # Buscar subpastas desta categoria
            subpastas = collection_categorias.find({
                "tipo": "subpasta",
                "categoria_id": cat["_id"]
            }).sort("ordem", 1)
            
            for sub in subpastas:
                print(f"  │  └─ {sub['icone']} {sub['nome']} (ID: {sub['_id']})")
                
                # Buscar cursos desta subpasta
                cursos = collection_cursos.find({
                    "subpasta_id": sub["_id"]
                })
                
                for curso in cursos:
                    print(f"  │     ├─ 🎓 {curso['titulo']}")
                    print(f"  │     │    ⏱️ {curso['duracao']} | 📊 {curso['nivel']}")
        
        # 8. Testar consultas
        print("\n8. TESTANDO CONSULTAS:")
        print("-" * 40)
        
        # Exemplo 1: Buscar todos os cursos de IA
        print("\n📋 Exemplo 1: Todos os cursos de IA")
        cursos_ia = collection_cursos.find({
            "subpasta_id": "inteligencia-artificial"
        })
        for curso in cursos_ia:
            print(f"  - {curso['titulo']} ({curso['duracao']})")
        
        # Exemplo 2: Buscar estrutura completa de uma categoria
        print("\n📋 Exemplo 2: Estrutura completa da categoria 'tech'")
        categoria = collection_categorias.find_one({"_id": "tech", "tipo": "categoria"})
        if categoria:
            print(f"  Categoria: {categoria['nome']}")
            
            subpastas = collection_categorias.find({
                "tipo": "subpasta",
                "categoria_id": "tech"
            })
            
            for sub in subpastas:
                print(f"  ├─ Subpasta: {sub['nome']}")
                
                cursos = collection_cursos.find({"subpasta_id": sub["_id"]})
                for curso in cursos:
                    print(f"  │  └─ Curso: {curso['titulo']}")
        
        print("\n" + "=" * 50)
        print("✅ TESTE CONCLUÍDO COM SUCESSO!")
        
        # Fechar conexão
        client.close()
        
    except pymongo.errors.ConnectionFailure as e:
        print(f"❌ ERRO DE CONEXÃO: {e}")
        print("Verifique:")
        print("1. Sua senha está correta? (hr7vHI5EjMwuRT9X)")
        print("2. Seu IP está autorizado no MongoDB Atlas?")
        print("3. Você está conectado à internet?")
    except pymongo.errors.ServerSelectionTimeoutError as e:
        print(f"❌ TIMEOUT: {e}")
        print("O servidor não respondeu em 5 segundos.")
    except Exception as e:
        print(f"❌ ERRO INESPERADO: {type(e).__name__}: {e}")

if __name__ == "__main__":
    testar_conexao_mongodb()