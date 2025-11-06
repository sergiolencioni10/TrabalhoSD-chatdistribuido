import socket
import threading
import time
import random
from communication import Communication
from election import Election
from utils import get_logger

logger = get_logger(__name__)

class Node:
    """Representa um nó na rede de chat distribuído. Atua como cliente e servidor (P2P)."""
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username # Nome de usuário do nó
        self.id = None # ID único atribuído pelo coordenador
        self.peers = {} # Dicionário de peers conhecidos (ID -> {ip, port, username})
        self.coordinator_id = None
        self.is_coordinator = False
        self.message_history = []
        self.stop_event = threading.Event()
        # Inicializa o módulo de comunicação, passando os handlers de mensagem
        self.communication = Communication(self.host, self.port, self.handle_tcp_message, self.handle_udp_message)
        self.election = Election(self) # Inicializa o módulo de eleição
        self.last_heartbeat_time = time.time() # Timestamp do último heartbeat recebido

    def start(self):
        """Inicia o nó, a comunicação e os processos de monitoramento."""
        self.communication.start()
        logger.info(f"Nó iniciado em {self.host}:{self.port}")
        self.join_network()
        # Inicia o monitoramento do coordenador em uma thread separada
        threading.Thread(target=self.monitor_coordinator, daemon=True).start()
        # Se for o coordenador inicial, começa a enviar heartbeats
        if self.is_coordinator:
            threading.Thread(target=self.send_heartbeats, daemon=True).start()

    def stop(self):
        """Encerra o nó e os módulos de comunicação."""
        self.stop_event.set()
        self.communication.stop()
        logger.info("Nó encerrado.")

    def join_network(self):
        """Tenta entrar na rede enviando uma requisição multicast."""
        join_message = {
            "type": "JOIN_REQUEST",
            "sender_ip": self.host,
            "sender_port": self.port,
            "username": self.username # Inclui o nome de usuário na requisição de entrada
        }
        self.communication.send_udp_multicast(join_message)
        logger.info("Enviado JOIN_REQUEST via multicast.")

        # Espera por uma resposta. Se não houver, assume que é o primeiro nó e se torna coordenador.
        time.sleep(5)
        if self.id is None:
            logger.info("Nenhum coordenador encontrado. Tornando-se o primeiro nó e coordenador.")
            self.id = 1
            self.is_coordinator = True
            self.coordinator_id = self.id
            # Adiciona a si mesmo à lista de peers
            self.peers[self.id] = {"ip": self.host, "port": self.port, "username": self.username}

    def handle_tcp_message(self, message, addr):
        """Processa mensagens recebidas via TCP (ponto a ponto)."""
        msg_type = message.get("type")
        logger.debug(f"Mensagem TCP recebida do tipo {msg_type} de {addr}")
        if msg_type == "JOIN_ACK":
            self.handle_join_ack(message)
        elif msg_type == "NEW_PEER":
            self.handle_new_peer(message)
        elif msg_type == "PEER_LIST":
            self.handle_peer_list(message)
        elif msg_type == "CHAT_MESSAGE":
            self.handle_chat_message(message)
        # Mensagens de eleição
        elif msg_type == "ELECTION":
            self.election.handle_election_message(message)
        elif msg_type == "ANSWER":
            self.election.handle_answer_message(message)
        elif msg_type == "COORDINATOR":
            self.election.handle_coordinator_message(message)
        # Heartbeat
        elif msg_type == "HEARTBEAT":
            self.last_heartbeat_time = time.time()
            logger.debug(f"Heartbeat recebido do coordenador {self.coordinator_id}")
        elif msg_type == "NODE_LEAVE":
            self.handle_node_leave(message)

    def handle_udp_message(self, message, addr):
        """Processa mensagens recebidas via UDP multicast (descoberta)."""
        msg_type = message.get("type")
        # Apenas o coordenador responde a requisições de entrada
        if msg_type == "JOIN_REQUEST" and self.is_coordinator:
            self.handle_join_request(message)

    def handle_join_request(self, message):
        """Trata a requisição de entrada de um novo nó (apenas coordenador)."""
        if not self.is_coordinator:
            return
        new_peer_ip = message["sender_ip"]
        new_peer_port = message["sender_port"]
        new_peer_username = message["username"] # Obtém o nome de usuário do novo nó
        new_peer_id = max(self.peers.keys()) + 1 # Atribui o próximo ID disponível
        # Adiciona o novo peer à lista
        self.peers[new_peer_id] = {"ip": new_peer_ip, "port": new_peer_port, "username": new_peer_username}
        logger.info(f"Novo peer {new_peer_id} ({new_peer_username}) em {new_peer_ip}:{new_peer_port} entrou.")

        # Envia JOIN_ACK para o novo peer com seu ID e a lista completa de peers
        join_ack_message = {
            "type": "JOIN_ACK",
            "id": new_peer_id,
            "coordinator_id": self.id,
            "peers": self.peers
        }
        self.communication.send_tcp_message(new_peer_ip, new_peer_port, join_ack_message)

        # Informa outros peers sobre o novo peer
        new_peer_message = {
            "type": "NEW_PEER",
            "id": new_peer_id,
            "ip": new_peer_ip,
            "port": new_peer_port,
            "username": new_peer_username # Inclui o nome de usuário na mensagem de novo peer
        }
        for pid, pinfo in self.peers.items():
            if pid != new_peer_id and pid != self.id:
                self.communication.send_tcp_message(pinfo["ip"], pinfo["port"], new_peer_message)

    def handle_join_ack(self, message):
        """Trata a confirmação de entrada na rede (JOIN_ACK)."""
        self.id = message["id"]
        self.coordinator_id = message["coordinator_id"]
        # Atualiza a lista de peers com a lista completa enviada pelo coordenador
        self.peers = {int(k): v for k, v in message["peers"].items()}
        logger.info(f"Entrou na rede com ID {self.id}. Coordenador é {self.coordinator_id}")

    def handle_new_peer(self, message):
        """Trata a notificação de um novo peer na rede."""
        peer_id = message["id"]
        peer_ip = message["ip"]
        peer_port = message["port"]
        peer_username = message["username"] # Obtém o nome de usuário do novo peer
        self.peers[peer_id] = {"ip": peer_ip, "port": peer_port, "username": peer_username}
        logger.info(f"Novo peer {peer_id} ({peer_username}) adicionado à lista.")

    def handle_peer_list(self, message):
        """Trata a atualização completa da lista de peers."""
        self.peers = {int(k): v for k, v in message["peers"].items()}
        logger.info("Lista de peers atualizada.")

    def handle_chat_message(self, message):
        """Trata uma mensagem de chat recebida."""
        sender_username = message["username"] # Usa o nome de usuário para exibição
        chat_text = message["text"]
        display_message = f"{sender_username}: {chat_text}"
        self.message_history.append(display_message)
        print(f"\n{display_message}")

    def send_chat_message(self, text):
        """Envia uma mensagem de chat para todos os peers."""
        message = {
            "type": "CHAT_MESSAGE",
            "sender_id": self.id,
            "username": self.username, # Inclui o nome de usuário na mensagem de chat
            "text": text
        }
        self.message_history.append(f"{self.username} (You): {text}")
        # Envia a mensagem para todos os peers, exceto para si mesmo
        for pid, pinfo in self.peers.items():
            if pid != self.id:
                self.communication.send_tcp_message(pinfo["ip"], pinfo["port"], message)

    def set_coordinator(self, coordinator_id):
        """Define o novo coordenador da rede."""
        self.coordinator_id = coordinator_id
        self.is_coordinator = (self.id == coordinator_id)
        if self.is_coordinator:
            logger.info("Eu sou o novo coordenador.")
            # Se for o novo coordenador, inicia o envio de heartbeats
            threading.Thread(target=self.send_heartbeats, daemon=True).start()
        else:
            logger.info(f"Novo coordenador é {coordinator_id}")

    def send_heartbeats(self):
        """Envia heartbeats periodicamente para monitorar a saúde dos peers (apenas coordenador)."""
        while self.is_coordinator and not self.stop_event.is_set():
            heartbeat_message = {"type": "HEARTBEAT", "sender_id": self.id}
            peers_to_remove = []
            # Tenta enviar heartbeat para todos os peers
            for pid, pinfo in self.peers.items():
                if pid != self.id:
                    if not self.communication.send_tcp_message(pinfo["ip"], pinfo["port"], heartbeat_message):
                        logger.warning(f"Peer {pid} não está respondendo. Marcando para remoção.")
                        peers_to_remove.append(pid)
            
            # Remove os peers que falharam
            if peers_to_remove:
                for pid in peers_to_remove:
                    self.remove_peer(pid)

            time.sleep(5) # Envia heartbeat a cada 5 segundos

    def monitor_coordinator(self):
        """Monitora o heartbeat do coordenador atual (apenas peers)."""
        while not self.stop_event.is_set():
            if not self.is_coordinator and self.coordinator_id is not None:
                # Se o tempo desde o último heartbeat for maior que 15 segundos (3x o intervalo de envio)
                if time.time() - self.last_heartbeat_time > 15:
                    logger.warning(f"Coordenador {self.coordinator_id} falhou. Iniciando eleição.")
                    # Remove o coordenador falho da lista de peers
                    self.remove_peer(self.coordinator_id)
                    # Inicia o algoritmo de eleição
                    self.election.start_election()
                    self.last_heartbeat_time = time.time() # Reseta o timer para evitar re-eleição imediata
            time.sleep(5)

    def remove_peer(self, peer_id):
        """Remove um peer da lista e notifica a rede (apenas coordenador)."""
        if peer_id in self.peers:
            del self.peers[peer_id]
            logger.info(f"Peer {peer_id} removido.")
            if self.is_coordinator:
                # Anuncia a saída do nó para os peers restantes
                leave_message = {"type": "NODE_LEAVE", "id": peer_id}
                for pid, pinfo in self.peers.items():
                    if pid != self.id:
                        self.communication.send_tcp_message(pinfo["ip"], pinfo["port"], leave_message)

    def handle_node_leave(self, message):
        """Trata a notificação de saída de um nó."""
        peer_id = message["id"]
        if peer_id in self.peers:
            del self.peers[peer_id]
            logger.info(f"Peer {peer_id} saiu da rede.")

    def print_peers(self):
        """Imprime a lista de peers conectados."""
        print("Peers conectados:")
        for pid, pinfo in self.peers.items():
            print(f"  - ID: {pid}, Usuário: {pinfo['username']}, Endereço: {pinfo['ip']}:{pinfo['port']}")

# O bloco if __name__ == '__main__': foi removido para ser tratado em main.py
