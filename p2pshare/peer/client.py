import os
import grpc
import logging

from generated import p2pshare_pb2
from generated import p2pshare_pb2_grpc

logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')


class PeerClient:
    def __init__(self, timeout_seconds=10):
        self.timeout = timeout_seconds

    def _get_stub(self, address, port):
        #cria o canal e o stub — o canal precisa ser fechado pelo chamador
        channel = grpc.insecure_channel(f'{address}:{port}')
        stub = p2pshare_pb2_grpc.PeerServiceStub(channel)
        return channel, stub

    def sync_with_peer(self, peer_info_self, known_peers, target_address, target_port):
        #manda nossa lista de peers e recebe a lista de quem nos conhece
        channel, stub = self._get_stub(target_address, target_port)
        try:
            sender = p2pshare_pb2.PeerInfo(
                id=peer_info_self['id'],
                address=peer_info_self['address'],
                port=peer_info_self['port']
            )
            peers_msg = [
                p2pshare_pb2.PeerInfo(id=p['id'], address=p['address'], port=p['port'])
                for p in known_peers
            ]
            request = p2pshare_pb2.SyncRequest(sender=sender, known_peers=peers_msg)
            response = stub.RegisterAndSync(request, timeout=self.timeout)

            return [{'id': p.id, 'address': p.address, 'port': p.port} for p in response.known_peers]
        except grpc.RpcError as e:
            logging.error(f"Falha ao sincronizar com {target_address}:{target_port} — {e.details()}")
            return []
        finally:
            channel.close()

    def get_file_list(self, address, port):
        channel, stub = self._get_stub(address, port)
        try:
            response = stub.GetFileList(p2pshare_pb2.Empty(), timeout=self.timeout)
            return [{'name': f.name, 'size': f.size} for f in response.files]
        except grpc.RpcError as e:
            logging.error(f"Erro ao obter lista de arquivos de {address}:{port} — {e.details()}")
            return []
        finally:
            channel.close()

    def get_peer_list(self, address, port):
        channel, stub = self._get_stub(address, port)
        try:
            response = stub.GetPeerList(p2pshare_pb2.Empty(), timeout=self.timeout)
            return [{'id': p.id, 'address': p.address, 'port': p.port} for p in response.peers]
        except grpc.RpcError as e:
            logging.error(f"Erro ao obter lista de peers de {address}:{port} — {e.details()}")
            return []
        finally:
            channel.close()

    def download_file(self, address, port, filename, destination_folder):
        channel, stub = self._get_stub(address, port)
        dest_path = os.path.join(destination_folder, filename)

        try:
            os.makedirs(destination_folder, exist_ok=True)
            request = p2pshare_pb2.DownloadRequest(filename=filename)
            stream = stub.DownloadFile(request, timeout=self.timeout)

            total = 0
            with open(dest_path, 'wb') as f:
                for chunk in stream:
                    f.write(chunk.data)
                    total += len(chunk.data)
                    print(f"Baixando... {total} bytes recebidos", end='\r')

            print(f"\nDownload concluido: '{filename}' ({total} bytes)")
            return True

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                print(f"Arquivo '{filename}' nao encontrado no peer {address}:{port}.")
            else:
                print(f"Erro ao baixar '{filename}' de {address}:{port} — {e.details()}")

            #remove arquivo incompleto se chegou a ser criado
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

        except Exception as e:
            logging.error(f"Erro inesperado no download de '{filename}': {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

        finally:
            channel.close()
