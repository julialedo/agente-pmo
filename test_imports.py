try:
    import networkx as nx
    import matplotlib
    import graphviz
    print('✅ Todas as bibliotecas importadas com sucesso!')
except ImportError as e:
    print(f'❌ Erro ao importar: {e}')
