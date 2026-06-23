# p2pshare

Um sistema de compartilhamento de arquivos ponto-a-ponto feito em Python, usando gRPC como camada de comunicação. Cada nó da rede age ao mesmo tempo como cliente e servidor — sem coordenador central, sem broker, sem nada no meio.

O projeto é uma espécie de mini-FastTrack: peers descobrem uns aos outros via gossip e trocam arquivos diretamente, com verificação de integridade por SHA-256.

---

## Como funciona

### Arquitetura

Não existe um servidor central. Cada peer que entra na rede:

1. Sobe um servidor gRPC na porta configurada
2. Se conecta a um peer de entrada (bootstrap) e troca listas de peers conhecidos
3. Propaga esse conhecimento para os demais (gossip de um nível)
4. A partir daí, pode listar e baixar arquivos de qualquer peer conhecido

```
peer1 (porta 50051)          peer2 (porta 50052)
┌─────────────────┐          ┌─────────────────┐
│  gRPC Server    │◄────────►│  gRPC Server    │
│  FileManager    │          │  FileManager    │
│  PeerManager    │          │  PeerManager    │
└─────────────────┘          └─────────────────┘
```

### Transferência de arquivos

O download acontece via streaming gRPC em chunks de 256 KB. O último chunk traz o hash SHA-256 do arquivo — calculado pelo servidor antes de enviar. O cliente recalcula o hash localmente e compara: se não bater, o arquivo é descartado.

### Descoberta de peers (gossip)

Quando um peer entra na rede via bootstrap, ele envia sua lista de peers conhecidos e recebe a lista do outro lado. Depois propaga para cada peer recém-descoberto, garantindo que o conhecimento se espalhe rapidamente mesmo em redes maiores.

---

## Estrutura do projeto

```
Mini_FastTrack/
└── p2pshare/
    ├── main.py               # Ponto de entrada; CLI interativa
    ├── start.py              # Atalho para abrir dois peers em terminais separados (Windows)
    ├── requirements.txt
    ├── proto/
    │   └── p2pshare.proto    # Definição dos serviços e mensagens gRPC
    ├── generated/            # Código gerado pelo protoc (não editar manualmente)
    ├── peer/
    │   ├── server.py         # Servidor gRPC (RegisterAndSync, GetFileList, DownloadFile...)
    │   ├── client.py         # Cliente gRPC com retry e timeout configuráveis
    │   ├── file_manager.py   # Leitura de arquivos em chunks e cálculo de SHA-256
    │   ├── peer_manager.py   # Gerencia a lista de peers conhecidos
    │   └── protocol_handler.py  # Orquestra bootstrap, refresh e downloads
    ├── shared_files/         # Pasta padrão de arquivos compartilhados pelo peer1
    ├── shared_peer2/         # Pasta de arquivos do peer2 (nos testes locais)
    ├── downloads/            # Arquivos baixados de outros peers
    └── logs/                 # Logs por peer (peer1.log, peer2.log, ...)
```

---

## Instalação

```bash
cd p2pshare
pip install -r requirements.txt
```

Se precisar regenerar o código gRPC a partir do `.proto`:

```bash
python -m grpc_tools.protoc \
  -I./proto \
  --python_out=./generated \
  --grpc_python_out=./generated \
  proto/p2pshare.proto
```

---

## Executando

### Opção 1 — dois terminais na mão

**Terminal 1 (peer1):**
```bash
cd p2pshare
python main.py --id peer1 --port 50051 --shared ./shared_files
```

**Terminal 2 (peer2, entrando pela rede do peer1):**
```bash
cd p2pshare
python main.py --id peer2 --port 50052 --bootstrap 127.0.0.1:50051 --shared ./shared_peer2
```

### Opção 2 — script de teste rápido (Windows)

Abre os dois terminais automaticamente:

```bash
cd p2pshare
python start.py
```

### Argumentos disponíveis

| Argumento     | Descrição                                              | Padrão          |
|---------------|--------------------------------------------------------|-----------------|
| `--id`        | Identificador único do peer (obrigatório)              | —               |
| `--port`      | Porta em que este peer vai escutar (obrigatório)       | —               |
| `--address`   | IP deste peer                                          | `127.0.0.1`     |
| `--bootstrap` | Endereço de entrada na rede (`host:porta`)             | —               |
| `--shared`    | Pasta com os arquivos a compartilhar                   | `./shared_files`|
| `--log-dir`   | Pasta onde os logs serão gravados                      | `./logs`        |

---

## Menu interativo

Depois de iniciar, cada peer apresenta um menu no terminal:

```
[1] Listar peers conhecidos
[2] Listar meus arquivos (com hash SHA-256)
[3] Ver arquivos de um peer (com hash SHA-256)
[4] Baixar arquivo de um peer (com verificação de integridade)
[5] Atualizar lista de peers (refresh)
[0] Sair
```

---

## Detalhes de implementação

### Retry e timeout

O `PeerClient` tenta cada operação até **3 vezes** com **1.5s** de espera entre tentativas. Erros definitivos como `NOT_FOUND` ou `PERMISSION_DENIED` não são retentados — falham imediatamente.

### Verificação de integridade

No download, o servidor calcula o SHA-256 antes de iniciar o stream e inclui o hash no último chunk. O cliente acumula os dados, recalcula o hash ao final e compara. Se divergir, o arquivo parcial é removido do disco.

### Refresh de peers

A opção `[5]` percorre todos os peers conhecidos e tenta buscar a lista de cada um. Peers que não respondem após `max_failures` tentativas são removidos da lista local.

### Logs

Cada peer grava um arquivo de log separado em `logs/<peer-id>.log`, com data/hora, nível e módulo de origem. O log do gRPC interno é silenciado para não poluir a saída.

---

## Dependências

- [`grpcio`](https://grpc.io/docs/languages/python/) — runtime gRPC
- [`grpcio-tools`](https://pypi.org/project/grpcio-tools/) — compilador protoc integrado ao Python
- [`grpcio-reflection`](https://pypi.org/project/grpcio-reflection/) — suporte a reflexão do servidor (opcional, para ferramentas como grpcurl)
