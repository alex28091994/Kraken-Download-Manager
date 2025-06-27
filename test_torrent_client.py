#!/usr/bin/env python3
"""
Script de teste para verificar a detecção de clientes torrent
"""

import os
import subprocess

def test_torrent_clients():
    """Testa a detecção de clientes torrent"""
    
    # Lista de clientes torrent para testar
    clientes_torrent = [
        # qBittorrent
        {
            'nome': 'qBittorrent',
            'comandos': [
                r'C:\Program Files\qBittorrent\qbittorrent.exe',
                r'C:\Program Files (x86)\qBittorrent\qbittorrent.exe',
                'qbittorrent'
            ]
        },
        # uTorrent
        {
            'nome': 'uTorrent',
            'comandos': [
                r'C:\Users\{}\AppData\Roaming\uTorrent\uTorrent.exe'.format(os.getenv('USERNAME')),
                r'C:\Program Files\uTorrent\uTorrent.exe',
                r'C:\Program Files (x86)\uTorrent\uTorrent.exe',
                'utorrent'
            ]
        },
        # BitTorrent
        {
            'nome': 'BitTorrent',
            'comandos': [
                r'C:\Program Files\BitTorrent\BitTorrent.exe',
                r'C:\Program Files (x86)\BitTorrent\BitTorrent.exe',
                'bittorrent'
            ]
        },
        # Deluge
        {
            'nome': 'Deluge',
            'comandos': [
                r'C:\Program Files\Deluge\deluge.exe',
                r'C:\Program Files (x86)\Deluge\deluge.exe',
                'deluge'
            ]
        },
        # Tixati
        {
            'nome': 'Tixati',
            'comandos': [
                r'C:\Program Files\Tixati\tixati.exe',
                r'C:\Program Files (x86)\Tixati\tixati.exe',
                'tixati'
            ]
        },
        # WebTorrent Desktop
        {
            'nome': 'WebTorrent Desktop',
            'comandos': [
                r'C:\Users\{}\AppData\Local\Programs\webtorrent\WebTorrent.exe'.format(os.getenv('USERNAME')),
                r'C:\Program Files\WebTorrent\WebTorrent.exe',
                'webtorrent'
            ]
        },
        # Transmission
        {
            'nome': 'Transmission',
            'comandos': [
                r'C:\Program Files\Transmission\transmission-qt.exe',
                'transmission-qt'
            ]
        }
    ]
    
    print("=== Teste de Detecção de Clientes Torrent ===\n")
    
    clientes_encontrados = []
    
    for cliente in clientes_torrent:
        print(f"Verificando {cliente['nome']}...")
        encontrado = False
        
        for comando in cliente['comandos']:
            try:
                comando_expandido = os.path.expandvars(comando)
                if os.path.exists(comando_expandido):
                    print(f"  ✓ Encontrado: {comando_expandido}")
                    encontrado = True
                    clientes_encontrados.append({
                        'nome': cliente['nome'],
                        'caminho': comando_expandido
                    })
                    break
                elif comando == cliente['comandos'][-1]:  # Último comando (genérico)
                    print(f"  ? Comando genérico disponível: {comando}")
                    encontrado = True
                    clientes_encontrados.append({
                        'nome': cliente['nome'],
                        'caminho': comando
                    })
            except Exception as e:
                print(f"  ✗ Erro ao verificar {comando}: {e}")
        
        if not encontrado:
            print(f"  ✗ Não encontrado")
        
        print()
    
    print("=== Resumo ===")
    if clientes_encontrados:
        print(f"Clientes encontrados: {len(clientes_encontrados)}")
        for cliente in clientes_encontrados:
            print(f"• {cliente['nome']}: {cliente['caminho']}")
    else:
        print("Nenhum cliente torrent foi encontrado no sistema.")
        print("\nClientes suportados:")
        for cliente in clientes_torrent:
            print(f"• {cliente['nome']}")

if __name__ == "__main__":
    test_torrent_clients() 