# P2P Share

Um sistema P2P de compartilhamento de arquivos em Python utilizando gRPC.

## Arquitetura

Nesta rede P2P, cada nó (peer) age tanto como **cliente** quanto como **servidor**. Não há um servidor central dedicado para gerenciar a rede ou o compartilhamento de arquivos.

- **Descoberta de Peers (Gossip):**
  A descoberta de novos peers na rede é feita utilizando um protocolo de gossip. Cada peer mantém uma lista de peers conhecidos. Quando um peer se conecta a outro, eles trocam essas listas, propagando o conhecimento de rede de forma descentralizada.
  
- **Transferência de Arquivos:**
  O download de arquivos ocorre diretamente (ponto-a-ponto) entre os peers. Um peer solicita e baixa partes ou o arquivo completo diretamente do peer que o possui.

## Como Executar

(Instruções serão adicionadas conforme a implementação for realizada).
