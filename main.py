import socket
import random
import sys
from node import Node

def main():
    """Função principal para iniciar o nó e gerenciar a interação com o usuário."""
    try:
        # Lógica para tratar os argumentos IP e Porta
        # Assume IP local e porta aleatória por padrão
        my_ip = socket.gethostbyname(socket.gethostname())
        my_port = random.randint(8000, 9000)

        if len(sys.argv) == 3:
            # Se 2 argumentos: IP e Porta
            my_ip = sys.argv[1]
            my_port = int(sys.argv[2])
        elif len(sys.argv) == 2:
            # Se 1 argumento: Porta (usa IP local)
            my_port = int(sys.argv[1])

        # Solicita o nome de usuário
        username = input("Digite seu nome de usuário: ")
        
        # Cria e inicia o nó
        node = Node(my_ip, my_port, username)
        node.start()

        # Loop para interação com o usuário
        while True:
            try:
                # O prompt muda para refletir o nome do usuário e o status (Coordenador/Peer)
                prompt = f"{node.username} ({'Coord' if node.is_coordinator else 'Peer'})> "
                command = input(prompt)
                
                # Comando de chat
                if command.lower().startswith("chat "):
                    message = command.split(" ", 1)[1]
                    if node.id:
                        node.send_chat_message(message)
                    else:
                        print("Não é possível enviar mensagem, ainda não está na rede.")
                
                # Comando para listar peers
                elif command.lower() == "peers":
                    if node.id:
                        node.print_peers()
                    else:
                        print("Não está na rede.")
                
                # Comando para ver o histórico
                elif command.lower() == "history":
                    print("--- Histórico de Mensagens ---")
                    for msg in node.message_history:
                        print(msg)
                    print("-----------------------")
                
                # Comando para sair
                elif command.lower() == "exit":
                    print("Encerrando...")
                    node.stop()
                    break
                
                else:
                    print("Comando desconhecido. Comandos disponíveis: chat <msg>, peers, history, exit")
            
            except (EOFError, KeyboardInterrupt):
                print("\nEncerrando...")
                node.stop()
                break

    except Exception as e:
        print(f"Ocorreu um erro na função principal: {e}")
        # Em caso de erro, garante que o nó seja parado
        if 'node' in locals() and node:
            node.stop()

if __name__ == '__main__':
    main()
