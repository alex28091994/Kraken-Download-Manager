# SuperBase - Editor e Gerenciador de Downloads

Um aplicativo simples e eficiente para gerenciar suas listas de downloads e torrents.

## 🚀 Funcionalidades Principais

### 📁 Gerenciamento de Arquivos JSON
- **Abrir arquivos JSON** com listas de downloads
- **Editar informações** dos itens (título, links, tamanho, etc.)
- **Salvar alterações** automaticamente
- **Unir múltiplos arquivos** em um só

### 🔍 Busca e Organização
- **Busca rápida** por título dos downloads
- **Paginação** para listas grandes (400 itens por página)
- **Filtros** em tempo real

### 📥 Download Inteligente
- **Detecção automática** de links torrent (.torrent e magnet)
- **Integração com clientes torrent** (qBittorrent, uTorrent, BitTorrent, etc.)
- **Download direto** para arquivos normais
- **Barra de progresso** em tempo real

## 🎯 Como Usar

### 1. Abrir um Arquivo
- Clique em **"Abrir Arquivo"** ou **"Abrir de URL"**
- Selecione um arquivo JSON ou cole uma URL

### 2. Editar Downloads
- **Duplo-clique** em qualquer item da lista
- Modifique os campos desejados
- Clique em **"Salvar"** para gravar as alterações

### 3. Baixar Conteúdo
- Na janela de edição, clique em **"📥 Baixar/Abrir Torrent"**
- Para torrents: abre automaticamente seu cliente torrent
- Para arquivos normais: escolha a pasta de destino

### 4. Buscar Downloads
- Use a **barra de busca** no topo
- Digite parte do título do que procura
- A lista filtra automaticamente

## 🎨 Interface

- **Tema escuro** por padrão (estilo Steam)
- **Interface responsiva** e intuitiva
- **Atalhos visuais** para ações principais

## 📋 Clientes Torrent Suportados

O app detecta automaticamente:
- ✅ **qBittorrent** (recomendado)
- ✅ **uTorrent**
- ✅ **BitTorrent**
- ✅ **Deluge**
- ✅ **Tixati**
- ✅ **WebTorrent Desktop**
- ✅ **Transmission**

## 🛠️ Instalação

1. **Instale o Python** (versão 3.7 ou superior)
2. **Baixe os arquivos** do projeto
3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Execute o aplicativo:**
   ```bash
   python 4.py
   ```

## 📦 Dependências

- PyQt5 (interface gráfica)
- requests (downloads)
- Pillow (imagens)
- pyperclip (área de transferência)

## 🔧 Dicas de Uso

### Para Torrents
- O app abre automaticamente seu cliente torrent
- Se nenhum cliente for encontrado, copia o link para a área de transferência

### Para Arquivos Normais
- Escolha a pasta de destino
- Acompanhe o progresso na barra
- Cancelamento disponível a qualquer momento

### Organização
- Use a busca para encontrar downloads específicos
- Edite informações para manter a lista organizada
- Una arquivos para criar listas maiores

## 🆘 Solução de Problemas

### Cliente Torrent Não Abre
1. Verifique se está instalado
2. Teste abrindo manualmente
3. Use o botão "Copiar Link" se necessário

### Arquivo Não Salva
1. Verifique permissões da pasta
2. Certifique-se de que o arquivo não está aberto em outro programa

### Erro de Download
1. Verifique sua conexão com a internet
2. Confirme se o link ainda está ativo
3. Tente novamente

## 📞 Suporte

- **Desenvolvedor:** Prietto
- **Instagram:** [@prietto_polar](https://www.instagram.com/prietto_polar/)

---

**Versão:** 1.2.1  
**Última atualização:** 2024 