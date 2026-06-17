import os
import hashlib
import grpc
import logging
import time

from generated import p2pshare_pb2
from generated import p2pshare_pb2_grpc

logger = logging.getLogger("p2pshare.client")

DEFAULT_TIMEOUT = 10      # segundos por tentativa
DEFAULT_RETRIES = 3       # numero de tentativas antes de desistir
RETRY_DELAY    = 1.5      # segundos de espera entre tentativas


class PeerClient:
    def __init__(self, timeout_seconds=DEFAULT_TIMEOUT, max_retries=DEFAULT_RETRIES):
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Utilitarios internos
    # ------------------------------------------------------------------

    def _get_stub(self, address, port):
        """Cria o canal e o stub. O canal DEVE ser fechado pelo chamador."""
        channel = grpc.insecure_channel(f'{address}:{port}')
        stub = p2pshare_pb2_grpc.PeerServiceStub(channel)
        return channel, stub

    def _call_with_retry(self, func, peer_label, *args, **kwargs):
        """
        Executa func(*args, **kwargs) com até self.max_retries tentativas.
        Retorna o resultado ou None em caso de falha persistente.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"[RETRY] {peer_label} — sucesso na tentativa {attempt}")
                return result
            except grpc.RpcError as e:
                code = e.code()
                # erros definitivos: nao vale tentar de novo
                if code in (grpc.StatusCode.NOT_FOUND, grpc.StatusCode.INVALID_ARGUMENT,
                            grpc.StatusCode.PERMISSION_DENIED, grpc.StatusCode.UNIMPLEMENTED):
                    logger.warning(f"[CLIENT] {peer_label} — erro definitivo ({code.name}): {e.details()}")
                    raise  # propaga para o chamador tratar
                if attempt < self.max_retries:
                    logger.warning(
                        f"[RETRY] {peer_label} — tentativa {attempt}/{self.max_retries} falhou "
                        f"({code.name}). Aguardando {RETRY_DELAY}s..."
                    )
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"[CLIENT] {peer_label} — todas as {self.max_retries} tentativas falharam: {e.details()}")
                    return None
        return None

    # ------------------------------------------------------------------
    # Gossip: sync de lista de peers
    # ------------------------------------------------------------------

    def sync_with_peer(self, peer_info_self, known_peers, target_address, target_port):
        """Manda nossa lista de peers e recebe a lista de quem nos conhece."""
        label = f"{target_address}:{target_port} (sync)"
        channel, stub = self._get_stub(target_address, target_port)

        def _call():
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

        try:
            result = self._call_with_retry(_call, label)
            return result if result is not None else []
        except grpc.RpcError:
            return []
        finally:
            channel.close()

    # ------------------------------------------------------------------
    # Lista de arquivos de um peer remoto
    # ------------------------------------------------------------------

    def get_file_list(self, address, port):
        label = f"{address}:{port} (get_file_list)"
        channel, stub = self._get_stub(address, port)

        def _call():
            response = stub.GetFileList(p2pshare_pb2.Empty(), timeout=self.timeout)
            return [{'name': f.name, 'size': f.size, 'sha256': f.sha256} for f in response.files]

        try:
            result = self._call_with_retry(_call, label)
            if result is None:
                logger.warning(f"[CLIENT] get_file_list falhou para {label}")
                return []
            return result
        except grpc.RpcError:
            return []
        finally:
            channel.close()

    # ------------------------------------------------------------------
    # Lista de peers de um peer remoto
    # ------------------------------------------------------------------

    def get_peer_list(self, address, port):
        label = f"{address}:{port} (get_peer_list)"
        channel, stub = self._get_stub(address, port)

        def _call():
            response = stub.GetPeerList(p2pshare_pb2.Empty(), timeout=self.timeout)
            return [{'id': p.id, 'address': p.address, 'port': p.port} for p in response.peers]

        try:
            result = self._call_with_retry(_call, label)
            if result is None:
                return []
            return result
        except grpc.RpcError:
            return []
        finally:
            channel.close()

    # ------------------------------------------------------------------
    # Download com verificacao de integridade SHA-256
    # ------------------------------------------------------------------

    def download_file(self, address, port, filename, destination_folder):
        label = f"{address}:{port} (download '{filename}')"
        channel, stub = self._get_stub(address, port)
        dest_path = os.path.join(destination_folder, filename)

        try:
            os.makedirs(destination_folder, exist_ok=True)
            request = p2pshare_pb2.DownloadRequest(filename=filename)

            logger.info(f"[DOWNLOAD] Iniciando download de '{filename}' de {address}:{port}")
            stream = stub.DownloadFile(request, timeout=self.timeout)

            hasher = hashlib.sha256()
            total = 0
            received_hash = ""

            with open(dest_path, 'wb') as f:
                for chunk in stream:
                    f.write(chunk.data)
                    hasher.update(chunk.data)
                    total += len(chunk.data)
                    print(f"  Baixando... {total:,} bytes recebidos", end='\r')
                    if chunk.sha256:  # ultimo chunk traz o hash do servidor
                        received_hash = chunk.sha256

            local_hash = hasher.hexdigest()
            print()  # quebra de linha apos o progresso

            # ----------------------------------------------------------
            # Verificacao de integridade
            # ----------------------------------------------------------
            if received_hash and local_hash != received_hash:
                logger.error(
                    f"[INTEGRITY] FALHA em '{filename}'! "
                    f"Esperado={received_hash[:16]}... Calculado={local_hash[:16]}..."
                )
                print(f"  [ERRO] Integridade comprometida — arquivo removido.")
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                return False

            if received_hash:
                logger.info(f"[INTEGRITY] '{filename}' OK — sha256={local_hash[:16]}...")
                print(f"  [OK] Integridade verificada (SHA-256 conferido).")

            print(f"  Download concluido: '{filename}' ({total:,} bytes)")
            logger.info(f"[DOWNLOAD] '{filename}' concluido — {total} bytes")
            return True

        except grpc.RpcError as e:
            print()
            if e.code() == grpc.StatusCode.NOT_FOUND:
                print(f"  Arquivo '{filename}' nao encontrado no peer {address}:{port}.")
                logger.warning(f"[DOWNLOAD] NOT_FOUND: '{filename}' em {address}:{port}")
            else:
                logger.error(f"[DOWNLOAD] RpcError ao baixar '{filename}' de {label}: {e.details()}")
                print(f"  Erro ao baixar '{filename}' de {address}:{port} — {e.details()}")

            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

        except Exception as e:
            print()
            logger.error(f"[DOWNLOAD] Erro inesperado no download de '{filename}': {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

        finally:
            channel.close()
