import os
import hashlib
import logging

logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')

CHUNK_SIZE = 1024 * 256  # 256 KB por chunk


class FileManager:
    def __init__(self, shared_dir="./shared_files"):
        self.shared_dir = shared_dir
        if not os.path.exists(self.shared_dir):  # cria a pasta caso nao exista
            try:
                os.makedirs(self.shared_dir)
            except OSError as e:
                logging.error(f"Erro ao criar a pasta {self.shared_dir}: {e}")

    # ------------------------------------------------------------------
    # Listagem
    # ------------------------------------------------------------------

    def list_files(self):
        files = []
        if not os.path.exists(self.shared_dir):
            return files

        try:
            for filename in os.listdir(self.shared_dir):
                file_path = os.path.join(self.shared_dir, filename)
                if os.path.isfile(file_path):  # ignora subpastas
                    size = os.path.getsize(file_path)
                    sha = self.compute_sha256(file_path)
                    files.append({"name": filename, "size": size, "sha256": sha})
        except OSError as e:
            logging.error(f"Erro ao listar os arquivos: {e}")

        return files

    # ------------------------------------------------------------------
    # Localização
    # ------------------------------------------------------------------

    def get_file_path(self, filename):
        file_path = os.path.join(self.shared_dir, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return file_path
        return None

    # ------------------------------------------------------------------
    # Hash SHA-256
    # ------------------------------------------------------------------

    def compute_sha256(self, file_path):
        """Calcula o hash SHA-256 de um arquivo completo (via path absoluto)."""
        h = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    h.update(chunk)
        except OSError as e:
            logging.error(f"Erro ao calcular hash de {file_path}: {e}")
            return ""
        return h.hexdigest()

    def compute_sha256_by_name(self, filename):
        """Calcula o hash SHA-256 a partir do nome do arquivo na pasta compartilhada."""
        file_path = self.get_file_path(filename)
        if not file_path:
            return ""
        return self.compute_sha256(file_path)

    # ------------------------------------------------------------------
    # Leitura em chunks para streaming gRPC
    # ------------------------------------------------------------------

    def read_file_chunks(self, filename, chunk_size=CHUNK_SIZE):
        """Le o arquivo em blocos para transferencia via streaming gRPC."""
        file_path = self.get_file_path(filename)

        if not file_path:
            raise FileNotFoundError(f"O arquivo '{filename}' nao foi encontrado na pasta compartilhada.")

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


# ------------------------------------------------------------------
# Teste standalone
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("Testando o FileManager localmente...\n")
    manager = FileManager()

    # cria arquivo de teste rapido
    teste_path = os.path.join(manager.shared_dir, "teste_local.txt")
    if not os.path.exists(teste_path):
        with open(teste_path, "w") as f:
            f.write("Ola P2P!")

    lista = manager.list_files()
    print(f"Arquivos em '{manager.shared_dir}':")
    for arq in lista:
        print(f"  -> {arq['name']}  ({arq['size']} bytes)  sha256={arq['sha256'][:16]}...")
