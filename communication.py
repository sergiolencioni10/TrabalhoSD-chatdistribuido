import socket
import json
import struct
import threading
import time
from utils import serialize_message, deserialize_message, get_logger

logger = get_logger(__name__)

# Constantes para a comunicação multicast
MULTICAST_GROUP = '224.1.1.1'  # Endereço IP do grupo multicast
MULTICAST_PORT = 5007         # Porta para a comunicação multicast

class Communication:
    """Gerencia toda a comunicação de rede para um nó, incluindo TCP e UDP multicast."""
    def __init__(self, node_ip, node_port, message_handler_tcp, message_handler_udp):
        self.node_ip = node_ip
        self.node_port = node_port
        self.message_handler_tcp = message_handler_tcp  # Função para processar mensagens TCP
        self.message_handler_udp = message_handler_udp  # Função para processar mensagens UDP

        # Configuração do Socket TCP para comunicação ponto a ponto
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((self.node_ip, self.node_port))
        self.tcp_socket.listen(10) # Permite até 10 conexões pendentes
        logger.info(f"Listener TCP iniciado em {self.node_ip}:{self.node_port}")

        # Configuração do Socket UDP para descoberta de nós via multicast
        self.udp_multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.udp_multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # O bind é feito em "" para escutar em todas as interfaces de rede disponíveis
        self.udp_multicast_socket.bind(('', MULTICAST_PORT))
        # Adiciona o socket ao grupo multicast
        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        self.udp_multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        logger.info(f"Listener Multicast UDP iniciado em {MULTICAST_GROUP}:{MULTICAST_PORT}")

        self.stop_event = threading.Event() # Evento para sinalizar o encerramento das threads

    def start(self):
        """Inicia as threads de escuta para mensagens TCP e UDP."""
        threading.Thread(target=self._listen_tcp, daemon=True).start()
        threading.Thread(target=self._listen_udp_multicast, daemon=True).start()

    def _listen_tcp(self):
        """Loop principal para aceitar conexões TCP e despachar para um handler."""
        while not self.stop_event.is_set():
            try:
                self.tcp_socket.settimeout(1.0) # Timeout para permitir a verificação do stop_event
                conn, addr = self.tcp_socket.accept()
                # Cada conexão é tratada em uma nova thread para não bloquear o listener
                threading.Thread(target=self._handle_tcp_connection, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue # Ignora timeouts, que são esperados
            except Exception as e:
                if not self.stop_event.is_set():
                    logger.error(f"Erro no listener TCP: {e}")
                    break

    def _handle_tcp_connection(self, conn, addr):
        """Processa uma única conexão TCP, recebe a mensagem e a envia para o handler do nó."""
        with conn:
            try:
                data = conn.recv(4096) # Buffer de 4KB para receber dados
                if data:
                    message = deserialize_message(data.decode('utf-8'))
                    self.message_handler_tcp(message, addr)
            except Exception as e:
                logger.error(f"Erro ao tratar conexão TCP de {addr}: {e}")

    def send_tcp_message(self, target_ip, target_port, message):
        """Envia uma mensagem TCP para um destino específico."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3.0) # Timeout de 3 segundos para a conexão
                sock.connect((target_ip, target_port))
                sock.sendall(serialize_message(message).encode('utf-8'))
                logger.debug(f"Mensagem TCP enviada para {target_ip}:{target_port}: {message.get('type')}")
                return True
        except Exception as e:
            logger.warning(f"Falha ao enviar mensagem TCP para {target_ip}:{target_port}: {e}")
            return False

    def _listen_udp_multicast(self):
        """Loop principal para escutar mensagens multicast UDP."""
        while not self.stop_event.is_set():
            try:
                self.udp_multicast_socket.settimeout(1.0)
                data, addr = self.udp_multicast_socket.recvfrom(1024)
                # Ignora as próprias mensagens multicast
                if addr[0] != self.node_ip:
                    message = deserialize_message(data.decode('utf-8'))
                    self.message_handler_udp(message, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if not self.stop_event.is_set():
                    logger.error(f"Erro no listener UDP multicast: {e}")
                    break

    def send_udp_multicast(self, message):
        """Envia uma mensagem para o grupo multicast."""
        try:
            # Cria um socket temporário para enviar a mensagem multicast
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2) # TTL (Time-To-Live) da mensagem
                sock.sendto(serialize_message(message).encode('utf-8'), (MULTICAST_GROUP, MULTICAST_PORT))
                logger.debug(f"Mensagem UDP multicast enviada: {message.get('type')}")
                return True
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem UDP multicast: {e}")
            return False

    def stop(self):
        """Encerra os sockets e as threads de comunicação."""
        self.stop_event.set()
        # Fechar os sockets interrompe as chamadas de bloqueio nas threads de escuta
        self.tcp_socket.close()
        self.udp_multicast_socket.close()
        logger.info("Módulo de comunicação encerrado.")
