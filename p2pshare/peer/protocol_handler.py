import os
import logging

logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')


class ProtocolHandler:
    def __init__(self, peer_manager, file_manager, client):
        self.peer_manager = peer_manager
        self.file_manager = file_manager
        self.client = client

    def bootstrap(self, bootstrap_address, bootstrap_port):
        #tenta entrar na rede pelo peer inicial e recebe a lista dele
        self_info = self.peer_manager.get_self_info()
        known = self.peer_manager.get_peers()

        received = self.client.sync_with_peer(
            self_info, known, bootstrap_address, bootstrap_port
        )

        if not received:
            logging.error(f"Bootstrap falhou com {bootstrap_address}:{bootstrap_port}, continuando sem peers iniciais.")
            return

        self.peer_manager.merge_peer_lists(received)

        #propaga para os peers recém-descobertos (1 nivel de gossip)
        for peer in received:
            if peer['address'] == bootstrap_address and peer['port'] == bootstrap_port:
                continue #ja sincronizou com esse
            extra = self.client.sync_with_peer(
                self_info, self.peer_manager.get_peers(),
                peer['address'], peer['port']
            )
            if extra:
                self.peer_manager.merge_peer_lists(extra)

    def refresh_peers(self, max_failures=2):
        #percorre todos os peers conhecidos e tenta atualizar a lista de cada um
        failure_count = {}

        for peer in self.peer_manager.get_peers():
            pid = peer['id']
            updated = self.client.get_peer_list(peer['address'], peer['port'])

            if updated is None or updated == []:
                failure_count[pid] = failure_count.get(pid, 0) + 1
                if failure_count[pid] >= max_failures:
                    self.peer_manager.remove_peer(pid)
                    logging.error(f"Peer {pid} marcado como inativo apos {max_failures} falhas.")
            else:
                self.peer_manager.merge_peer_lists(updated)

    def list_remote_files(self, address, port):
        return self.client.get_file_list(address, port)

    def download_from_peer(self, address, port, filename, destination_folder="./downloads"):
        #cria a pasta de destino caso nao exista
        if not os.path.exists(destination_folder):
            try:
                os.makedirs(destination_folder)
            except OSError as e:
                logging.error(f"Erro ao criar pasta de destino '{destination_folder}': {e}")
                return False

        return self.client.download_file(address, port, filename, destination_folder)

    def list_known_peers(self):
        return self.peer_manager.get_peers()
