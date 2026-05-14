import os
import logging

logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')

class FileManager:
    def __init__(self, shared_dir="./shared_files"):
        self.shared_dir = shared_dir
        if not os.path.exists(self.shared_dir):  #cria a pasta caso n exista
            try:
                os.makedirs(self.shared_dir)
            except OSError as e:
                logging.error(f"Erro ao criar a pasta {self.shared_dir}: {e}")
                
    def list_files(self):
        files = []
        if not os.path.exists(self.shared_dir):
            return files
            
        try:
            for filename in os.listdir(self.shared_dir):
                file_path = os.path.join(self.shared_dir, filename)
                if os.path.isfile(file_path): #ignora subpastas
                    size = os.path.getsize(file_path)
                    files.append({"name": filename, "size": size})
        except OSError as e:
            logging.error(f"Erro ao listar os arquivos: {e}")
            
        return files

    def get_file_path(self, filename):
        file_path = os.path.join(self.shared_dir, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return file_path
        return None

    def read_file_chunks(self, filename, chunk_size=1024*256): #lê o arquivo em blocos para transferencia
        file_path = self.get_file_path(filename)
        
        if not file_path:
            raise FileNotFoundError(f"O arquivo {filename} não foi encontrado na pasta compartilhada.")
            
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except OSError as e:
            logging.error(f"Erro de leitura no arquivo {filename}: {e}")
            raise

if __name__ == "__main__":
    print("Testando o FileManager localmente...\n")
    manager = FileManager()
    
    #cria arquivo de teste rápido para ter o que listar se estiver vazio
    teste_path = os.path.join(manager.shared_dir, "teste_local.txt")
    if not os.path.exists(teste_path):
        with open(teste_path, "w") as f:
            f.write("Olá P2P!")
            
    lista = manager.list_files()
    print(f"Arquivos em '{manager.shared_dir}':")
    for arq in lista:
        print(f" -> {arq['name']} ({arq['size']} bytes)")
