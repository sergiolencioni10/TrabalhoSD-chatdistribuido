import json
import logging

# Configuração básica de logging para registrar eventos do sistema.
# Define o nível de log para INFO e o formato da mensagem.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def serialize_message(data):
    """Serializa um dicionário (representando uma mensagem) para uma string JSON.
    Isso é necessário para enviar a mensagem pela rede em um formato padronizado.
    """
    return json.dumps(data)

def deserialize_message(data_string):
    """Deserializa uma string JSON (recebida da rede) de volta para um dicionário Python.
    Permite que o nó receptor processe a mensagem.
    """
    return json.loads(data_string)

def get_logger(name):
    """Retorna uma instância de logger configurada para um módulo específico.
    Ajuda a identificar a origem das mensagens de log.
    """
    return logging.getLogger(name)
