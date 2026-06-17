import grpc
import logging
from concurrent import futures

from generated import p2pshare_pb2
from generated import p2pshare_pb2_grpc

logger = logging.getLogger("p2pshare.server")


class PeerServer(p2pshare_pb2_grpc.PeerServiceServicer):
    def __init__(self, peer_manager, file_manager):
        self.peer_manager = peer_manager
        self.file_manager = file_manager

    # ------------------------------------------------------------------
    # Gossip: troca de listas de peers
    # ------------------------------------------------------------------

    def RegisterAndSync(self, request, context):
        #adiciona o proprio solicitante antes de fazer o merge
        sender = request.sender
        peer_addr = f"{sender.address}:{sender.port}"
        logger.info(f"[SYNC] Recebendo sync de {sender.id} ({peer_addr})")

        self.peer_manager.add_peer({
            'id': sender.id,
            'address': sender.address,
            'port': sender.port
        })

        # incorpora a lista de peers que o solicitante conhece
        received = [{'id': p.id, 'address': p.address, 'port': p.port} for p in request.known_peers]
        self.peer_manager.merge_peer_lists(received)
        logger.info(f"[SYNC] Merge concluido — {self.peer_manager.peer_count} peer(s) conhecidos agora")

        # monta a resposta com os peers que conhecemos localmente
        local_peers = self.peer_manager.get_peers()
        peer_infos = [
            p2pshare_pb2.PeerInfo(id=p['id'], address=p['address'], port=p['port'])
            for p in local_peers
        ]
        return p2pshare_pb2.SyncResponse(known_peers=peer_infos)

    # ------------------------------------------------------------------
    # Lista de peers
    # ------------------------------------------------------------------

    def GetPeerList(self, request, context):
        requester = context.peer()
        logger.info(f"[PEERS] Lista de peers solicitada por {requester}")
        peers = self.peer_manager.get_peers()
        peer_infos = [
            p2pshare_pb2.PeerInfo(id=p['id'], address=p['address'], port=p['port'])
            for p in peers
        ]
        return p2pshare_pb2.PeerListResponse(peers=peer_infos)

    # ------------------------------------------------------------------
    # Lista de arquivos (com hash SHA-256)
    # ------------------------------------------------------------------

    def GetFileList(self, request, context):
        requester = context.peer()
        logger.info(f"[FILES] Lista de arquivos solicitada por {requester}")
        files = self.file_manager.list_files()
        file_infos = [
            p2pshare_pb2.FileInfo(name=f['name'], size=f['size'], sha256=f.get('sha256', ''))
            for f in files
        ]
        return p2pshare_pb2.FileListResponse(files=file_infos)

    # ------------------------------------------------------------------
    # Download (streaming com hash no ultimo chunk)
    # ------------------------------------------------------------------

    def DownloadFile(self, request, context):
        requester = context.peer()
        filename = request.filename
        logger.info(f"[DOWNLOAD] '{filename}' solicitado por {requester}")

        file_path = self.file_manager.get_file_path(filename)

        if not file_path:
            logger.warning(f"[DOWNLOAD] Arquivo '{filename}' nao encontrado na pasta compartilhada")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Arquivo '{filename}' nao encontrado.")
            return

        # calcula o hash antes de transmitir (para enviar no ultimo chunk)
        sha256 = self.file_manager.compute_sha256(file_path)

        try:
            sequence = 0
            chunks = list(self.file_manager.read_file_chunks(filename))
            total_chunks = len(chunks)

            for i, chunk_data in enumerate(chunks):
                is_last = (i == total_chunks - 1)
                yield p2pshare_pb2.FileChunk(
                    data=chunk_data,
                    sequence=sequence,
                    sha256=sha256 if is_last else ""  # hash so no ultimo chunk
                )
                sequence += 1

            total_bytes = sum(len(c) for c in chunks)
            logger.info(f"[DOWNLOAD] '{filename}' enviado com sucesso — {total_bytes} bytes, {sequence} chunks, sha256={sha256[:16]}...")

        except Exception as e:
            logger.error(f"[DOWNLOAD] Erro durante o streaming de '{filename}': {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Erro interno durante a leitura do arquivo.")


# ------------------------------------------------------------------
# Inicializacao do servidor gRPC
# ------------------------------------------------------------------

def start_server(peer_manager, file_manager, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    p2pshare_pb2_grpc.add_PeerServiceServicer_to_server(
        PeerServer(peer_manager, file_manager), server
    )

    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"[SERVER] gRPC server iniciado na porta {port}")

    # thread daemon: encerra junto com o processo principal sem precisar de stop() manual
    import threading
    t = threading.Thread(target=server.wait_for_termination, daemon=True)
    t.start()

    return server
