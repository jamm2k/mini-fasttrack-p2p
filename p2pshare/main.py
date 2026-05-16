import argparse
import sys
import time

from peer.file_manager import FileManager
from peer.peer_manager import PeerManager
from peer.client import PeerClient
from peer.protocol_handler import ProtocolHandler
from peer.server import start_server


def parse_args():
    parser = argparse.ArgumentParser(description="p2pshare -- compartilhamento de arquivos P2P via gRPC")
    parser.add_argument("--id",        required=True,          help="Identificador unico deste peer")
    parser.add_argument("--port",      required=True, type=int, help="Porta em que este peer vai escutar")
    parser.add_argument("--address",   default="127.0.0.1",     help="Endereco IP deste peer (padrao: 127.0.0.1)")
    parser.add_argument("--bootstrap", default=None,            help="Endereco do peer de entrada (ex: 127.0.0.1:50051)")
    parser.add_argument("--shared",    default="./shared_files", help="Pasta de arquivos compartilhados")
    return parser.parse_args()


def ask_peer_address():
    #solicita o endereço e porta de um peer ao usuario
    try:
        address = input("Endereco do peer: ").strip()
        port    = int(input("Porta do peer: ").strip())
        return address, port
    except ValueError:
        print("Porta invalida.")
        return None, None


def menu_listar_peers(handler):
    peers = handler.list_known_peers()
    if not peers:
        print("Nenhum peer conhecido ainda.")
        return
    print(f"\n{len(peers)} peer(s) conhecido(s):")
    for p in peers:
        print(f"  -> {p['id']}  {p['address']}:{p['port']}")


def menu_listar_meus_arquivos(file_manager):
    files = file_manager.list_files()
    if not files:
        print("Nenhum arquivo na pasta compartilhada.")
        return
    print(f"\n{len(files)} arquivo(s) compartilhado(s):")
    for f in files:
        print(f"  -> {f['name']}  ({f['size']} bytes)")


def menu_ver_arquivos_peer(handler):
    address, port = ask_peer_address()
    if not address:
        return
    files = handler.list_remote_files(address, port)
    if not files:
        print("Nenhum arquivo encontrado ou peer inacessivel.")
        return
    print(f"\n{len(files)} arquivo(s) disponivel(is):")
    for f in files:
        print(f"  -> {f['name']}  ({f['size']} bytes)")


def menu_baixar_arquivo(handler):
    address, port = ask_peer_address()
    if not address:
        return
    filename = input("Nome do arquivo: ").strip()
    if not filename:
        print("Nome invalido.")
        return
    handler.download_from_peer(address, port, filename)


def menu_refresh(handler):
    print("Atualizando lista de peers...")
    handler.refresh_peers()
    print("Feito.")


def main():
    args = parse_args()

    print(f"\nIniciando peer '{args.id}' em {args.address}:{args.port}...")

    #instancia os componentes principais
    file_manager    = FileManager(args.shared)
    peer_manager    = PeerManager(args.id, args.address, args.port)
    client          = PeerClient()
    handler         = ProtocolHandler(peer_manager, file_manager, client)

    #sobe o servidor gRPC em background
    start_server(peer_manager, file_manager, args.port)
    time.sleep(0.5) #aguarda o servidor subir antes de qualquer chamada de rede

    #se tiver bootstrap, tenta entrar na rede
    if args.bootstrap:
        try:
            host, port_str = args.bootstrap.split(":")
            print(f"Conectando ao bootstrap {host}:{port_str}...")
            handler.bootstrap(host, int(port_str))
            print(f"Sync concluido. {peer_manager.peer_count} peer(s) encontrado(s).")
        except ValueError:
            print("Formato de bootstrap invalido. Use endereco:porta (ex: 127.0.0.1:50051)")

    print("\n=== p2pshare ===")

    while True:
        print("\n[1] Listar peers conhecidos")
        print("[2] Listar meus arquivos")
        print("[3] Ver arquivos de um peer")
        print("[4] Baixar arquivo de um peer")
        print("[5] Atualizar lista de peers (refresh)")
        print("[0] Sair")

        try:
            opcao = input("\nEscolha: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando...")
            sys.exit(0)

        if opcao == "1":
            menu_listar_peers(handler)
        elif opcao == "2":
            menu_listar_meus_arquivos(file_manager)
        elif opcao == "3":
            menu_ver_arquivos_peer(handler)
        elif opcao == "4":
            menu_baixar_arquivo(handler)
        elif opcao == "5":
            menu_refresh(handler)
        elif opcao == "0":
            print("Encerrando...")
            sys.exit(0)
        else:
            print("Opcao invalida.")


if __name__ == "__main__":
    main()
