# Integração com Clientes Torrent

## Novas Funcionalidades

O aplicativo agora suporta integração direta com clientes torrent externos. Quando você clicar no botão "📥 Baixar/Abrir Torrent" em um item que contém links .torrent ou magnet links, o sistema irá:

1. **Detectar automaticamente** clientes torrent instalados no sistema
2. **Abrir o cliente** com o link do torrent
3. **Mostrar confirmação** de que o cliente foi aberto com sucesso

## Clientes Suportados

O sistema detecta automaticamente os seguintes clientes torrent:

### Clientes Principais
- **qBittorrent** - Cliente gratuito e open-source com interface moderna
- **uTorrent / µTorrent** - Cliente leve e amplamente usado
- **BitTorrent** - Cliente oficial do protocolo BitTorrent

### Clientes Adicionais
- **Deluge** - Cliente com suporte a plugins, leve e extensível
- **Tixati** - Cliente avançado com visualizações gráficas
- **WebTorrent Desktop** - Cliente moderno baseado em web
- **Transmission** - Cliente minimalista (se instalado)

## Como Funciona

### Para Links .torrent e Magnet Links
1. Clique no botão "📥 Baixar/Abrir Torrent" na janela de edição
2. O sistema detecta automaticamente se é um link torrent
3. Procura por clientes torrent instalados no sistema
4. Abre o primeiro cliente encontrado com o link
5. Mostra uma mensagem de confirmação

### Para Arquivos Normais
1. O comportamento permanece o mesmo
2. Permite selecionar pasta de destino
3. Faz o download interno com barra de progresso

## Instalação de Clientes Torrent

### qBittorrent (Recomendado)
- **Download**: https://www.qbittorrent.org/download.php
- **Instalação**: Execute o instalador e siga as instruções
- **Vantagens**: Gratuito, open-source, sem anúncios

### uTorrent
- **Download**: https://www.utorrent.com/
- **Instalação**: Execute o instalador
- **Observação**: Versão gratuita contém anúncios

### BitTorrent
- **Download**: https://www.bittorrent.com/
- **Instalação**: Execute o instalador
- **Observação**: Muito similar ao uTorrent

## Funcionalidades Adicionais

### Copiar Link para Área de Transferência
Se nenhum cliente torrent for encontrado:
1. O sistema mostra uma mensagem de aviso
2. Oferece a opção de copiar o link para a área de transferência
3. Permite colar o link manualmente em qualquer cliente

### Dependências
- `pyperclip` - Para copiar links para a área de transferência
- `subprocess` - Para executar clientes externos

## Configuração

### Instalar Dependências
```bash
pip install -r requirements.txt
```

### Verificar Clientes Instalados
Execute o script de teste:
```bash
python test_torrent_client.py
```

## Solução de Problemas

### Cliente Não Detectado
1. Verifique se o cliente está instalado
2. Execute o script de teste para verificar detecção
3. Se necessário, reinstale o cliente torrent

### Erro ao Abrir Cliente
1. Verifique se o cliente está funcionando
2. Tente abrir o cliente manualmente
3. Verifique se há atualizações disponíveis

### Link Não Funciona
1. Verifique se o link está correto
2. Teste o link em um navegador
3. Verifique se o arquivo .torrent ainda está disponível

## Exemplos de Uso

### Link Magnet
```
magnet:?xt=urn:btih:1234567890abcdef...
```

### Arquivo .torrent
```
https://exemplo.com/arquivo.torrent
```

### Arquivo Normal
```
https://exemplo.com/arquivo.zip
```

## Notas Técnicas

- O sistema detecta links torrent verificando se começam com `magnet:` ou terminam com `.torrent`
- A detecção de clientes é feita verificando caminhos comuns de instalação
- Se nenhum cliente for encontrado, o sistema oferece copiar o link
- O comportamento para arquivos normais permanece inalterado 