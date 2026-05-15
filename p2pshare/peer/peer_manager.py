import threading

class PeerManager:
    def __init__(self, peer_id, address, port):
        self.peer_id = peer_id
        self.address = address
        self.port = port
        self.peers = {} 
        self.lock = threading.Lock() #usado pra proteger o acesso concorrente a lista
        
    def add_peer(self, peer_info):
        if peer_info.get('id') == self.peer_id: #ignora se for o proprio
            return
            
        with self.lock:
            self.peers[peer_info['id']] = {
                'id': peer_info.get('id'),
                'address': peer_info.get('address'),
                'port': peer_info.get('port'),
                'active': True #se atualizou ou eh novo, ta ativo
            }
            
    def add_peers(self, peer_list):
        for peer in peer_list:
            self.add_peer(peer)
            
    def remove_peer(self, peer_id): #remove da lista marcando inativo
        with self.lock:
            if peer_id in self.peers:
                self.peers[peer_id]['active'] = False
                
    def get_peers(self):
        with self.lock:
            #retorna todos que estao ativos
            return [p for p in self.peers.values() if p.get('active', True)]
            
    def get_self_info(self):
        return {
            'id': self.peer_id,
            'address': self.address,
            'port': self.port
        }
        
    def merge_peer_lists(self, received_list): #faz o merge com o que recebeu da rede
        self.add_peers(received_list)
        
    @property
    def peer_count(self):
        with self.lock:
            ativos = [p for p in self.peers.values() if p.get('active', True)]
            return len(ativos)

if __name__ == "__main__":
    print("Testando o PeerManager...\n")
    pm = PeerManager("peer_01", "127.0.0.1", 5001)
    
    #adicionando alguns peers de teste
    pm.add_peer({'id': 'peer_02', 'address': '127.0.0.1', 'port': 5002})
    pm.add_peer({'id': 'peer_03', 'address': '127.0.0.1', 'port': 5003})
    
    print(f"Meus dados: {pm.get_self_info()}")
    print(f"Total conhecidos: {pm.peer_count}")
    print(f"Lista atual: {pm.get_peers()}")
    
    pm.remove_peer('peer_02')
    print(f"\nDepois de remover o peer_02:")
    print(f"Total: {pm.peer_count}")
    print(f"Lista: {pm.get_peers()}")
