import threading
import time
from utils import get_logger

logger = get_logger(__name__)

class Election:
    """Implementa o algoritmo de eleição do Bully para escolher um novo coordenador.
    O nó com o maior ID ativo na rede se torna o coordenador.
    """
    def __init__(self, node):
        self.node = node  # Referência ao objeto Node principal
        self.election_in_progress = False  # Flag para evitar múltiplas eleições simultâneas
        self.answered = False  # Flag para saber se um nó de ID maior respondeu

    def start_election(self):
        """Inicia o processo de eleição."""
        if self.election_in_progress:
            logger.info(f"Nó {self.node.id}: Eleição já em andamento.")
            return

        logger.info(f"Nó {self.node.id}: Iniciando eleição.")
        self.election_in_progress = True
        self.answered = False

        # Filtra apenas os peers com ID maior que o nó atual
        higher_peers = {pid: pinfo for pid, pinfo in self.node.peers.items() if pid > self.node.id}

        if not higher_peers:
            # Se não houver peers com ID maior, o nó atual se declara coordenador
            logger.info(f"Nó {self.node.id}: Nenhum peer com ID maior. Declarando-me coordenador.")
            self.declare_coordinator()
            return

        # Envia mensagens ELECTION para todos os peers com ID maior
        election_message = {
            "type": "ELECTION",
            "sender_id": self.node.id
        }
        sent_to_any = False
        for pid, pinfo in higher_peers.items():
            if self.node.communication.send_tcp_message(pinfo["ip"], pinfo["port"], election_message):
                logger.info(f"Nó {self.node.id}: Enviou ELECTION para {pid}")
                sent_to_any = True

        if not sent_to_any:
            # Se não conseguir enviar para ninguém, assume que é o maior ID ativo
            logger.warning(f"Nó {self.node.id}: Não foi possível alcançar nenhum peer com ID maior. Declarando-me coordenador.")
            self.declare_coordinator()
            return

        # Inicia um timer para esperar por mensagens ANSWER
        threading.Timer(5, self._election_timeout).start()

    def _election_timeout(self):
        """Função chamada se o timer de eleição expirar sem receber um ANSWER."""
        if not self.answered:
            logger.info(f"Nó {self.node.id}: Timeout da eleição. Nenhum ANSWER recebido. Declarando-me coordenador.")
            self.declare_coordinator()
        self.election_in_progress = False

    def handle_election_message(self, message):
        """Trata a recepção de uma mensagem ELECTION."""
        sender_id = message["sender_id"]
        logger.info(f"Nó {self.node.id}: Recebeu ELECTION de {sender_id}")

        # Se o nó atual tiver ID maior, ele responde com ANSWER
        if self.node.id > sender_id:
            answer_message = {
                "type": "ANSWER",
                "sender_id": self.node.id
            }
            sender_info = self.node.peers.get(sender_id)
            if sender_info:
                self.node.communication.send_tcp_message(sender_info["ip"], sender_info["port"], answer_message)
                logger.info(f"Nó {self.node.id}: Enviou ANSWER para {sender_id}")

        # Inicia sua própria eleição, a menos que já esteja em andamento
        if not self.election_in_progress:
            self.start_election()

    def handle_answer_message(self, message):
        """Trata a recepção de uma mensagem ANSWER."""
        sender_id = message["sender_id"]
        logger.info(f"Nó {self.node.id}: Recebeu ANSWER de {sender_id}. Um nó de ID maior está ativo.")
        self.answered = True
        # O nó atual espera pela mensagem COORDINATOR do vencedor

    def declare_coordinator(self):
        """Declara o nó atual como o novo coordenador e notifica os outros peers."""
        self.node.set_coordinator(self.node.id)
        logger.info(f"Nó {self.node.id}: Eu sou o novo coordenador!")

        coordinator_message = {
            "type": "COORDINATOR",
            "coordinator_id": self.node.id
        }
        # Informa todos os outros peers sobre o novo coordenador
        for pid, pinfo in self.node.peers.items():
            if pid != self.node.id:
                self.node.communication.send_tcp_message(pinfo["ip"], pinfo["port"], coordinator_message)
                logger.info(f"Nó {self.node.id}: Enviou mensagem COORDINATOR para {pid}")
        self.election_in_progress = False

    def handle_coordinator_message(self, message):
        """Trata a recepção de uma mensagem COORDINATOR."""
        coordinator_id = message["coordinator_id"]
        logger.info(f"Nó {self.node.id}: Recebeu mensagem COORDINATOR. Novo coordenador é {coordinator_id}")
        self.node.set_coordinator(coordinator_id)
        self.election_in_progress = False
