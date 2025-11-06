# Trabalho Final de Sistemas Distribuídos: Chat Distribuído Tolerante a Falhas

Este projeto implementa um sistema de chat distribuído **Peer-to-Peer (P2P)** em Python, focado em demonstrar conceitos chave de Sistemas Distribuídos, como comunicação assíncrona, descoberta de serviços e tolerância a falhas através da eleição de coordenador.

## 1. Arquitetura e Comunicação

O sistema opera em uma arquitetura P2P, onde cada nó é capaz de atuar como cliente e servidor.

| Componente | Protocolo | Função |
| :--- | :--- | :--- |
| **Comunicação Ponto a Ponto** | TCP | Utilizado para o envio de mensagens de chat, *heartbeats* e mensagens de controle (JOIN_ACK, ELECTION, ANSWER, COORDINATOR). Garante a entrega confiável das mensagens. |
| **Descoberta de Nós** | UDP Multicast | Utilizado para que novos nós enviem uma requisição `JOIN_REQUEST` para o grupo multicast, permitindo que o Coordenador ativo descubra e registre o novo participante. |

## 2. Funcionalidades Chave

### 2.1. Eleição de Coordenador (Tolerância a Falhas)

O sistema implementa o **Algoritmo do Bully** para garantir que a rede possa se recuperar da falha do nó Coordenador.

*   **Coordenador:** Um nó é designado como Coordenador, responsável por atribuir IDs únicos, manter a lista de peers e enviar *heartbeats* periódicos.
*   **Monitoramento:** Cada nó monitora o Coordenador através de *heartbeats* (mensagens TCP periódicas).
*   **Início da Eleição:** Se um nó não receber o *heartbeat* do Coordenador por um período de tempo, ele assume que o Coordenador falhou e inicia uma eleição, enviando mensagens `ELECTION` para todos os nós com ID maior.
*   **Regra do Bully:** O nó com o **maior ID** que responder à eleição se torna o novo Coordenador. Se nenhum nó de ID maior responder, o nó que iniciou a eleição se declara o novo Coordenador.

### 2.2. Identificação de Usuário

Cada nó é identificado por um **nome de usuário** (além do ID único e endereço IP:Porta), que é incluído em todas as mensagens de controle e chat. Isso garante que a comunicação seja exibida de forma clara para o usuário final (ex: `[Nome de Usuário]: <mensagem>`).

## 3. Estrutura do Código

O projeto é modularizado em Python, com comentários nas principais seções para facilitar a compreensão:

| Arquivo | Descrição |
| :--- | :--- |
| `main.py` | Ponto de entrada. Trata a inicialização do nó, a solicitação do nome de usuário e o loop de interação com o usuário (comandos `chat`, `peers`, `history`, `exit`). |
| `node.py` | **Classe principal do nó.** Contém a lógica de estado (ID, peers, coordenador), o gerenciamento de threads e os *handlers* para todos os tipos de mensagens recebidas. |
| `communication.py` | Gerencia a camada de rede. Contém a lógica de sockets TCP (ponto a ponto) e UDP Multicast (descoberta), além dos *listeners* em threads separadas. |
| `election.py` | Implementa a lógica do **Algoritmo do Bully**, incluindo o início da eleição, o tratamento das mensagens `ELECTION`, `ANSWER` e `COORDINATOR`, e o *timeout* da eleição. |
| `utils.py` | Funções utilitárias para serialização/deserialização de mensagens (JSON) e configuração de *logging*. |

---
