"""
Script de teste local: sobe dois peers em subprocessos e valida
as operacoes basicas do sistema p2pshare.
Execute a partir da pasta p2pshare/:  python test_local.py
"""
import os
import sys
import time
import subprocess
import tempfile

PYTHON   = sys.executable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PEER1_PORT    = 50051
PEER2_PORT    = 50052
SHARED_PEER1  = os.path.join(BASE_DIR, "shared_files")
TEST_FILENAME = "arquivo_teste.txt"
TEST_FILE     = os.path.join(SHARED_PEER1, TEST_FILENAME)
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")


def ok(msg):
    print(f"  [OK]  {msg}")

def fail(msg):
    print(f"  [FAIL] {msg}")

def titulo(msg):
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")


def garantir_arquivo_teste():
    os.makedirs(SHARED_PEER1, exist_ok=True)
    with open(TEST_FILE, "w", encoding="utf-8") as f:
        f.write("Conteudo de teste do p2pshare.\n" * 100)
    ok(f"Arquivo de teste criado: {TEST_FILE}")


def subir_peer1():
    cmd = [
        PYTHON, "main.py",
        "--id",      "peer1",
        "--port",    str(PEER1_PORT),
        "--address", "127.0.0.1",
        "--shared",  SHARED_PEER1,
    ]
    #stdin em PIPE para que o processo nao consuma o terminal interativo
    proc = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc


def testar_bootstrap():
    titulo("Teste 1: bootstrap do peer2 com peer1")
    cmd = [
        PYTHON, "main.py",
        "--id",        "peer2",
        "--port",      str(PEER2_PORT),
        "--address",   "127.0.0.1",
        "--bootstrap", f"127.0.0.1:{PEER1_PORT}",
        "--shared",    os.path.join(BASE_DIR, "shared_peer2"),
    ]
    #manda "0" (sair) logo apos o bootstrap para encerrar o processo
    proc = subprocess.run(
        cmd,
        cwd=BASE_DIR,
        input=b"0\n",
        capture_output=True,
        timeout=15,
    )
    saida = proc.stdout.decode(errors="replace")
    if "peer encontrado" in saida.lower() or "sync concluido" in saida.lower():
        ok("Bootstrap e sync realizados com sucesso")
    else:
        fail("Bootstrap nao reportou peers encontrados")
        print("    stdout:", saida[:300])
        print("    stderr:", proc.stderr.decode(errors="replace")[:300])


def testar_lista_arquivos():
    titulo("Teste 2: peer2 lista arquivos de peer1")
    #envia opcao 3 (ver arquivos de um peer), depois endereco/porta e 0 (sair)
    entrada = f"3\n127.0.0.1\n{PEER1_PORT}\n0\n".encode()
    cmd = [
        PYTHON, "main.py",
        "--id",        "peer2",
        "--port",      str(PEER2_PORT),
        "--address",   "127.0.0.1",
        "--bootstrap", f"127.0.0.1:{PEER1_PORT}",
        "--shared",    os.path.join(BASE_DIR, "shared_peer2"),
    ]
    proc = subprocess.run(
        cmd,
        cwd=BASE_DIR,
        input=entrada,
        capture_output=True,
        timeout=15,
    )
    saida = proc.stdout.decode(errors="replace")
    if TEST_FILENAME in saida:
        ok(f"Arquivo '{TEST_FILENAME}' encontrado na listagem remota")
    else:
        fail(f"Arquivo '{TEST_FILENAME}' nao apareceu na listagem")
        print("    stdout:", saida[:400])


def testar_download():
    titulo("Teste 3: peer2 baixa arquivo de peer1")
    #opcao 4 (baixar), depois endereco/porta/nome do arquivo e 0 (sair)
    entrada = f"4\n127.0.0.1\n{PEER1_PORT}\n{TEST_FILENAME}\n0\n".encode()
    cmd = [
        PYTHON, "main.py",
        "--id",        "peer2",
        "--port",      str(PEER2_PORT),
        "--address",   "127.0.0.1",
        "--bootstrap", f"127.0.0.1:{PEER1_PORT}",
        "--shared",    os.path.join(BASE_DIR, "shared_peer2"),
    ]
    proc = subprocess.run(
        cmd,
        cwd=BASE_DIR,
        input=entrada,
        capture_output=True,
        timeout=20,
    )
    saida = proc.stdout.decode(errors="replace")
    dest  = os.path.join(DOWNLOADS_DIR, TEST_FILENAME)
    if os.path.exists(dest):
        ok(f"Arquivo baixado com sucesso em: {dest}")
    elif "concluido" in saida.lower():
        ok("Download reportado como concluido (arquivo pode estar em pasta diferente)")
    else:
        fail("Download falhou ou arquivo nao foi criado")
        print("    stdout:", saida[:400])
        print("    stderr:", proc.stderr.decode(errors="replace")[:200])


def main():
    print("\np2pshare -- Teste de integracao local")
    print("Certifique-se de rodar a partir da pasta p2pshare/\n")

    garantir_arquivo_teste()

    titulo("Subindo peer1 em background...")
    peer1 = subir_peer1()
    time.sleep(2) #aguarda o servidor gRPC do peer1 subir

    if peer1.poll() is not None:
        fail("peer1 encerrou antes do esperado")
        print(peer1.stderr.read().decode(errors="replace"))
        sys.exit(1)
    ok("peer1 rodando")

    try:
        testar_bootstrap()
        testar_lista_arquivos()
        testar_download()
    finally:
        peer1.terminate()
        peer1.wait(timeout=5)
        print("\npeer1 encerrado.")

    print("\n=== Testes concluidos ===\n")


if __name__ == "__main__":
    main()
