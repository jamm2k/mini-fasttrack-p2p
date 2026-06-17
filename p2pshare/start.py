"""
start.py -- abre dois terminais Windows para teste rapido do p2pshare.
Execute a partir da pasta p2pshare/:  python start.py
"""
import os
import sys
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON   = sys.executable

PEER1_CMD = (
    f'"{PYTHON}" main.py --id peer1 --port 50051 --address 127.0.0.1 --shared ./shared_files'
)
PEER2_CMD = (
    f'"{PYTHON}" main.py --id peer2 --port 50052 --address 127.0.0.1 --bootstrap 127.0.0.1:50051 --shared ./shared_peer2'
)

def abrir_terminal(titulo, comando):
    #abre um novo terminal cmd com titulo e comando proprios
    subprocess.Popen(
        f'start "{titulo}" cmd /k cd /d "{BASE_DIR}" && {comando}',
        shell=True,
        cwd=BASE_DIR,
    )

print("Abrindo terminais para peer1 e peer2...")

abrir_terminal("p2pshare -- peer1 (porta 50051)", PEER1_CMD)
time.sleep(2) #aguarda peer1 subir antes de peer2 tentar bootstrap

abrir_terminal("p2pshare -- peer2 (porta 50052)", PEER2_CMD)

print("Terminais abertos!")
print("peer1 escutando na porta 50051")
print("peer2 vai fazer bootstrap com peer1 na porta 50051")
print("\nColoque arquivos em 'shared_files/' para peer1 compartilhar.")
