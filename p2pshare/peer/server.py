import grpc
import logging
from concurrent import futures

from generated import p2pshare_pb2
from generated import p2pshare_pb2_grpc

logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')


class PeerServer(p2pshare_pb2_grpc.PeerServiceServicer):
    def __init__(self, peer_manager, file_manager):
        self.peer_manager = peer_manager
        self.file_manager = file_manager

    def RegisterAndSync(self, request, context):
        #adiciona o proprio solicitante antes de fazer o merge
        sender = request.sender
        self.peer_manager.add_peer({
            'id': sender.id,
            'address': sender.address,
            'port': sender.port
        })

        #incorpora a lista de peers que o solicitante conhece
        received = [{'id': p.id, 'address': p.address, 'port': p.port} for p in request.known_peers]
        self.peer_manager.merge_peer_lists(received)

        #monta a resposta com os peers que conhecemos localmente
        local_peers = self.peer_manager.get_peers()
        peer_infos = [
            p2pshare_pb2.PeerInfo(id=p['id'], address=p['address'], port=p['port'])
            for p in local_peers
        ]
        return p2pshare_pb2.SyncResponse(known_peers=peer_infos)

    def GetPeerList(self, request, context):
        peers = self.peer_manager.get_peers()
        peer_infos = [
            p2pshare_pb2.PeerInfo(id=p['id'], address=p['address'], port=p['port'])
            for p in peers
        ]
        return p2pshare_pb2.PeerListResponse(peers=peer_infos)

    def GetFileList(self, request, context):
        files = self.file_manager.list_files()
        file_infos = [
            p2pshare_pb2.FileInfo(name=f['name'], size=f['size'])
            for f in files
        ]
        return p2pshare_pb2.FileListResponse(files=file_infos)

    def DownloadFile(self, request, context):
        file_path = self.file_manager.get_file_path(request.filename)

        if not file_path: #arquivo nao encontrado na pasta compartilhada
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Arquivo '{request.filename}' nao encontrado.")
            return

        try:
            sequence = 0
            for chunk in self.file_manager.read_file_chunks(request.filename):
                yield p2pshare_pb2.FileChunk(data=chunk, sequence=sequence)
                sequence += 1
        except Exception as e:
            logging.error(f"Erro durante o streaming de '{request.filename}': {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Erro interno durante a leitura do arquivo.")


def start_server(peer_manager, file_manager, port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    p2pshare_pb2_grpc.add_PeerServiceServicer_to_server(
        PeerServer(peer_manager, file_manager), server
    )

    server.add_insecure_port(f'[::]:{port}')
    server.start()

    #thread daemon: encerra junto com o processo principal sem precisar de stop() manual
    import threading
    t = threading.Thread(target=server.wait_for_termination, daemon=True)
    t.start()

    return server
