import sys
import os
import json
import hashlib
import subprocess
from datetime import datetime
import requests
import threading
import time
import zipfile
try:
    import libtorrent as lt
    TORRENT_AVAILABLE = True
except ImportError:
    TORRENT_AVAILABLE = False
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QProgressBar, QInputDialog, QDialog, QTextEdit, QSplashScreen,
    QFrame, QGridLayout, QMenu, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QThread, QUrl
from PyQt5.QtGui import QPalette, QColor, QIcon, QPixmap, QFont, QPainter, QDesktopServices
from PIL import Image
from io import BytesIO
import csv

# Desabilitar aviso de depreciação
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

class MergeFilesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unir Arquivos JSON")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        # Label
        layout.addWidget(QLabel("Selecione os arquivos JSON para unir:"))

        # Lista de arquivos
        self.file_list_widget = QListWidget()
        layout.addWidget(self.file_list_widget)

        # Botões de ação para a lista
        list_button_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("Adicionar Arquivos")
        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_remove_file = QPushButton("Remover Selecionado")
        self.btn_remove_file.clicked.connect(self.remove_selected_file)
        list_button_layout.addWidget(self.btn_add_files)
        list_button_layout.addWidget(self.btn_remove_file)
        list_button_layout.addStretch()
        layout.addLayout(list_button_layout)

        # Botão de unir
        self.btn_merge = QPushButton("Unir Arquivos")
        self.btn_merge.clicked.connect(self.merge_files)
        self.btn_merge.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(self.btn_merge)
        
        self.merged_data = None

    def add_files(self):
        caminhos, _ = QFileDialog.getOpenFileNames(self, 'Selecione os arquivos JSON', '', 'Arquivos JSON (*.json);;Todos os arquivos (*)')
        if caminhos:
            for caminho in caminhos:
                # Evitar adicionar o mesmo caminho duas vezes
                if not self.file_list_widget.findItems(caminho, Qt.MatchExactly):
                    self.file_list_widget.addItem(caminho)

    def remove_selected_file(self):
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.file_list_widget.takeItem(self.file_list_widget.row(item))

    def merge_files(self):
        if self.file_list_widget.count() < 2:
            QMessageBox.warning(self, "Aviso", "Você precisa selecionar pelo menos dois arquivos para unir.")
            return

        all_downloads = []
        all_titles = set()
        
        base_data = None # Para usar o 'name' e outras chaves do primeiro arquivo

        # Ler todos os arquivos
        try:
            for i in range(self.file_list_widget.count()):
                path = self.file_list_widget.item(i).text()
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if i == 0:
                    base_data = data.copy()
                    # Remove 'downloads' para preenchê-lo depois
                    if 'downloads' in base_data:
                        del base_data['downloads']

                downloads = data.get('downloads', [])
                for download in downloads:
                    title = download.get('title')
                    if title and title not in all_titles:
                        all_downloads.append(download)
                        all_titles.add(title)

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler o arquivo {path}:\n{e}")
            return
            
        # Salvar o novo arquivo
        save_path, _ = QFileDialog.getSaveFileName(self, 'Salvar arquivo JSON unido', '', 'Arquivos JSON (*.json);;Todos os arquivos (*)')
        if not save_path:
            return

        if base_data is None:
            base_data = {}
            
        base_data['downloads'] = all_downloads

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(base_data, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "Sucesso", f"Arquivos unidos com sucesso em:\n{save_path}")
            self.merged_data = base_data
            self.accept() # Fecha a janela de diálogo

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar o arquivo unido:\n{e}")

class TorrentDownloader(QThread):
    progress_updated = pyqtSignal(int, int, int, int, int, int, int)
    download_finished = pyqtSignal(bool, str)
    
    def __init__(self, torrent_url, save_path):
        super().__init__()
        self.torrent_url = torrent_url
        self.save_path = save_path
        self.session = None
        self.torrent_handle = None
        self.running = True
        
    def run(self):
        if not TORRENT_AVAILABLE:
            self.download_finished.emit(False, "libtorrent não está disponível")
            return
            
        try:
            # Configurar sessão do libtorrent
            self.session = lt.session({'listen_interfaces': '0.0.0.0:6881'})
            
            # Adicionar torrent
            params = lt.parse_magnet_uri(self.torrent_url)
            params.save_path = self.save_path
            self.torrent_handle = self.session.add_torrent(params)
            
            # Aguardar metadados
            while not self.torrent_handle.has_metadata() and self.running:
                time.sleep(0.1)
                self.session.post_torrent_updates()
                
            if not self.running:
                self.session.remove_torrent(self.torrent_handle)
                return
                
            # Agora que temos metadados, podemos obter o tamanho
            torrent_file = self.torrent_handle.torrent_file()
            total_size = torrent_file.total_size() if torrent_file else 0

            # Monitorar progresso
            while self.running:
                status = self.torrent_handle.status()
                
                # Se o download acabou ou está semeando, paramos de monitorar
                if status.state == lt.torrent_status.seeding or status.state == lt.torrent_status.finished:
                    break

                progress = int(status.progress * 100)
                
                self.progress_updated.emit(
                    progress,
                    status.download_rate,
                    status.upload_rate,
                    status.num_peers,
                    status.num_seeds,
                    status.total_done,
                    total_size
                )
                
                time.sleep(1)
                self.session.post_torrent_updates()

            if self.running:
                self.download_finished.emit(True, "Download concluído!")
            else:
                self.download_finished.emit(False, "Download cancelado.")

            self.session.remove_torrent(self.torrent_handle)

        except Exception as e:
            self.download_finished.emit(False, f"Erro: {str(e)}")
            
    def stop(self):
        self.running = False

class FileDownloader(QThread):
    progress_updated = pyqtSignal(int, int, int, int)
    download_finished = pyqtSignal(bool, str)
    
    def __init__(self, file_url, save_path):
        super().__init__()
        self.file_url = file_url
        self.save_path = save_path
        self.running = True
        
    def run(self):
        try:
            self.start_time = time.time()
            response = requests.get(self.file_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self.running:
                        self.download_finished.emit(False, "Download cancelado.")
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        elapsed_time = time.time() - self.start_time
                        speed = downloaded / elapsed_time if elapsed_time > 0 else 0
                        
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress, downloaded, total_size, int(speed))
                        else:
                            self.progress_updated.emit(0, downloaded, 0, int(speed))
                            
            self.download_finished.emit(True, "Download concluído!")
            
        except Exception as e:
            self.download_finished.emit(False, f"Erro: {str(e)}")
            
    def stop(self):
        self.running = False

class JsonEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SuperBase editor e gerenciardo')
        self.resize(800, 600)
        self.setWindowState(Qt.WindowMaximized)
        self.dados = None
        self.arquivo_atual = None
        self.todos_downloads = []
        self.filtered_downloads = []
        self.current_page = 1
        self.items_per_page = 400
        self.tema_escuro = True
        self.is_downloading = False  # Flag para controlar downloads
        self.link_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'link')
        if not os.path.exists(self.link_dir):
            os.makedirs(self.link_dir)

        # Inicializa a interface
        self.init_ui()
        
        # Aplica o tema após um pequeno delay para garantir que todos os widgets foram criados
        QTimer.singleShot(100, self.aplicar_tema)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Menu
        menubar = self.menuBar()

        # Menu Arquivo (reorganizado)
        menu_arquivo = menubar.addMenu('Arquivo')
        menu_arquivo.addAction('📝 Nova Lista', self.criar_nova_lista)
        menu_arquivo.addAction('📂 Abrir JSON', self.abrir_arquivo)
        menu_arquivo.addAction('🌐 Abrir de URL', self.abrir_de_url)
        menu_arquivo.addAction('💾 Salvar', self.salvar_arquivo)
        menu_arquivo.addAction('💾 Salvar Como...', self.salvar_como)
        menu_arquivo.addSeparator()
        menu_arquivo.addAction('🔄 Unir Arquivos JSON', self.unir_arquivos)

        # Novo Menu Exportar
        menu_exportar = menu_arquivo.addMenu('📤 Exportar')
        menu_exportar.addAction('Exportar JSON (com estrelas)', self.salvar_como)
        menu_exportar.addAction('Exportar JSON (sem estrelas)', self.exportar_json_sem_estrelas)
        
        menu_arquivo.addSeparator()
        menu_arquivo.addAction('🚪 Sair', self.close)

        menu_sobre = menubar.addMenu('Sobre')
        acao_sobre = menu_sobre.addAction('Sobre o Software')
        acao_sobre.triggered.connect(self.mostrar_sobre)
        
        menu_comunidade = menubar.addMenu('Comunidade')
        acao_atualizar = menu_comunidade.addAction('Atualizar lista da comunidade')
        acao_atualizar.triggered.connect(self.atualizar_lista_comunidade)

        # Topo: nome e botões de tema
        top_layout = QHBoxLayout()
        self.label_name = QLabel('(sem nome)')
        self.label_name.setStyleSheet('font-weight: bold; font-size: 16px;')
        top_layout.addWidget(self.label_name)
        self.btn_editar_nome = QPushButton('Editar Nome')
        self.btn_editar_nome.clicked.connect(self.editar_nome)
        self.btn_editar_nome.setEnabled(False)
        top_layout.addWidget(self.btn_editar_nome)
        top_layout.addStretch()
        self.btn_tema = QPushButton('🌙')
        self.btn_tema.setFixedWidth(40)
        self.btn_tema.clicked.connect(self.alternar_tema)
        top_layout.addWidget(self.btn_tema)
        layout.addLayout(top_layout)

        # Botões principais (agora logo abaixo do topo)
        btn_layout = QHBoxLayout()
        self.btn_nova_lista = QPushButton('📝 Nova Lista')
        self.btn_nova_lista.clicked.connect(self.criar_nova_lista)
        btn_layout.addWidget(self.btn_nova_lista)
        self.btn_adicionar_item = QPushButton('➕ Adicionar Item')
        self.btn_adicionar_item.clicked.connect(self.adicionar_item)
        self.btn_adicionar_item.setEnabled(False)
        btn_layout.addWidget(self.btn_adicionar_item)
        self.btn_abrir = QPushButton('Abrir JSON')
        self.btn_abrir.clicked.connect(self.abrir_arquivo)
        btn_layout.addWidget(self.btn_abrir)
        self.btn_abrir_url = QPushButton('Abrir de URL')
        self.btn_abrir_url.clicked.connect(self.abrir_de_url)
        btn_layout.addWidget(self.btn_abrir_url)
        self.btn_unir = QPushButton('Unir JSON')
        self.btn_unir.clicked.connect(self.unir_arquivos)
        btn_layout.addWidget(self.btn_unir)
        self.btn_excluir = QPushButton('Excluir Selecionado')
        self.btn_excluir.clicked.connect(self.excluir_selecionado)
        self.btn_excluir.setEnabled(False)
        btn_layout.addWidget(self.btn_excluir)
        self.btn_salvar = QPushButton('Salvar')
        self.btn_salvar.clicked.connect(self.salvar_arquivo)
        self.btn_salvar.setEnabled(False)
        btn_layout.addWidget(self.btn_salvar)
        layout.addLayout(btn_layout)

        # Botões de seleção
        selection_layout = QHBoxLayout()
        self.btn_selecionar_todos = QPushButton('☑️ Selecionar Todos')
        self.btn_selecionar_todos.clicked.connect(self.selecionar_todos)
        self.btn_selecionar_todos.setEnabled(False)
        selection_layout.addWidget(self.btn_selecionar_todos)
        self.btn_desmarcar_todos = QPushButton('☐ Desmarcar Todos')
        self.btn_desmarcar_todos.clicked.connect(self.desmarcar_todos)
        self.btn_desmarcar_todos.setEnabled(False)
        selection_layout.addWidget(self.btn_desmarcar_todos)
        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # Busca
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel('Buscar:'))
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Digite o termo e pressione Enter ou clique em Buscar")
        self.search_entry.textChanged.connect(self.verificar_busca_limpa)
        self.search_entry.returnPressed.connect(self.iniciar_busca)
        search_layout.addWidget(self.search_entry)
        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.iniciar_busca)
        search_layout.addWidget(self.btn_buscar)
        layout.addLayout(search_layout)

        # Controles de Paginação
        self.pagination_widget = QWidget()
        pagination_layout = QHBoxLayout(self.pagination_widget)
        self.btn_anterior = QPushButton("<< Anterior")
        self.btn_anterior.clicked.connect(self.pagina_anterior)
        self.page_label = QLabel("Página 1 / 1")
        self.btn_proxima = QPushButton("Próximo >>")
        self.btn_proxima.clicked.connect(self.proxima_pagina)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.btn_anterior)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.btn_proxima)
        pagination_layout.addStretch()
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pagination_widget)

        # Lista e contador
        self.label_contador = QLabel('Total de itens: 0')
        layout.addWidget(self.label_contador)
        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(self.abrir_popup_edicao)
        self.lista.setSelectionMode(QListWidget.ExtendedSelection)
        self.lista.setAlternatingRowColors(True)
        self.lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self.mostrar_menu_contexto)
        self.lista.setStyleSheet("""
            QListWidget {
                background-color: #181c20;
                border: 1px solid #222;
                border-radius: 4px;
                padding: 5px;
                color: #fff;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                margin: 2px 0;
                border-radius: 4px;
                color: #fff;
                background: transparent;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: #fff;
            }
            QListWidget::item:alternate {
                background-color: #23272b;
                color: #fff;
            }
            QListWidget::item:hover {
                background-color: #222;
                color: #fff;
            }
            QListWidget::item:focus {
                border: none;
                outline: none;
            }
        """)
        layout.addWidget(self.lista)

        # Seção de Progresso de Download (inicialmente oculta)
        self.download_progress_frame = QFrame()
        self.download_progress_frame.setFrameStyle(QFrame.StyledPanel)
        download_layout = QGridLayout(self.download_progress_frame)
        
        self.download_title_label = QLabel("Download em andamento...")
        self.download_title_label.setStyleSheet("font-weight: bold;")
        self.download_progress_bar = QProgressBar()
        self.download_stats_label = QLabel("")
        self.download_torrent_stats_label = QLabel("")
        self.download_cancel_button = QPushButton("Cancelar Download")
        self.download_cancel_button.clicked.connect(self.cancelar_download)

        download_layout.addWidget(self.download_title_label, 0, 0, 1, 2)
        download_layout.addWidget(self.download_progress_bar, 1, 0, 1, 2)
        download_layout.addWidget(self.download_stats_label, 2, 0, 1, 2)
        download_layout.addWidget(self.download_torrent_stats_label, 3, 0, 1, 2)
        download_layout.addWidget(self.download_cancel_button, 4, 0, 1, 2)
        
        layout.addWidget(self.download_progress_frame)
        self.download_progress_frame.setVisible(False)

        # Barra de progresso (para outras operações)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

    def alternar_tema(self):
        self.tema_escuro = not self.tema_escuro
        self.aplicar_tema()
        self.btn_tema.setText('☀️' if self.tema_escuro else '🌙')

    def aplicar_tema(self):
        # Paleta base escura
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor('#171a21'))  # Fundo Steam
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor('#23262e'))
        palette.setColor(QPalette.AlternateBase, QColor('#1b1e25'))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor('#23262e'))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor('#66c0f4'))  # Azul Steam
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)

        # QSS para estilo Steam
        qss = """
        QWidget {
            background-color: #171a21;
            color: #c7d5e0;
            font-family: 'Segoe UI', 'Arial', sans-serif;
            font-size: 13px;
        }
        QDialog, QMessageBox {
            background-color: #23262e;
        }
        /* Garante que o texto dentro de dialogos não tenha fundo próprio */
        QDialog QLabel, QMessageBox QLabel {
            background-color: transparent;
            color: #c7d5e0;
        }
        QLabel#label_name {
            color: #66c0f4;
            font-size: 18px;
            font-weight: bold;
        }
        QLineEdit, QTextEdit {
            background: #23262e;
            color: #c7d5e0;
            border: 1px solid #2a475e;
            border-radius: 6px;
            padding: 4px;
        }
        QLineEdit:focus, QTextEdit:focus {
            border: 1.5px solid #66c0f4;
        }
        QPushButton {
            background-color: #23262e;
            color: #c7d5e0;
            border: 1.5px solid #2a475e;
            border-radius: 8px;
            padding: 6px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #66c0f4;
            color: #23262e;
            border: 1.5px solid #66c0f4;
        }
        QPushButton:pressed {
            background-color: #2a475e;
        }
        QListWidget {
            background: #23262e;
            color: #c7d5e0;
            border: 1px solid #2a475e;
            border-radius: 6px;
        }
        QProgressBar {
            background: #23262e;
            color: #23262e;
            border: 1px solid #2a475e;
            border-radius: 6px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #66c0f4;
            border-radius: 6px;
        }
        QMessageBox {
            background: #23262e;
            color: #c7d5e0;
        }
        """
        self.setStyleSheet(qss)
        self.label_name.setObjectName('label_name')
        self.lista.setStyleSheet('QListWidget { background: #23262e; color: #c7d5e0; }')
        self.search_entry.setStyleSheet('background: #23262e; color: #c7d5e0;')

    def editar_nome(self):
        if self.dados is None:
            return
        nome_atual = self.dados.get('name', '')
        novo_nome, ok = QInputDialog.getText(self, 'Editar Nome', 'Digite o novo nome:', text=nome_atual)
        if ok and novo_nome.strip():
            self.dados['name'] = novo_nome.strip()
            self.label_name.setText(self.dados['name'])

    def abrir_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, 'Abrir arquivo JSON', '', 'Arquivos JSON (*.json);;Todos os arquivos (*)')
        if not caminho:
            QMessageBox.information(self, 'Informação', 'Nenhum arquivo foi selecionado.')
            return
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                self.dados = json.load(f)
            self.arquivo_atual = caminho
            self.label_name.setText(self.dados.get('name', '(sem nome)'))
            self.btn_editar_nome.setEnabled(True)
            self.btn_adicionar_item.setEnabled(True)
            self.btn_excluir.setEnabled(True)
            self.atualizar_lista()
            self.btn_salvar.setEnabled(True)
            num_downloads = len(self.dados.get('downloads', []))
            QMessageBox.information(self, 'Sucesso', f"Arquivo '{caminho}' carregado com sucesso!\nEncontrados {num_downloads} downloads.")
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao abrir arquivo:\n{e}')

    def atualizar_lista(self):
        self.todos_downloads = self.dados.get('downloads', []) if self.dados else []
        self.search_entry.setText("")  # Limpa a busca ao carregar
        self.filtrar_lista() # A filtragem inicial irá configurar a paginação
        
        # Habilitar/desabilitar botões de seleção baseado na presença de dados
        has_data = len(self.todos_downloads) > 0
        self.btn_selecionar_todos.setEnabled(has_data)
        self.btn_desmarcar_todos.setEnabled(has_data)

    def mostrar_pagina_atual(self, is_search_result=False):
        self.lista.clear()

        if is_search_result:
            items_to_display = self.filtered_downloads
            self.pagination_widget.setVisible(False)
        else:
            self.pagination_widget.setVisible(True)
            start_index = (self.current_page - 1) * self.items_per_page
            end_index = start_index + self.items_per_page
            items_to_display = self.filtered_downloads[start_index:end_index]
            
        total_pages = (len(self.filtered_downloads) + self.items_per_page - 1) // self.items_per_page or 1
        self.page_label.setText(f"Página {self.current_page} / {total_pages}")
        self.btn_anterior.setEnabled(self.current_page > 1)
        self.btn_proxima.setEnabled(self.current_page < total_pages)

        for idx, item in enumerate(items_to_display):
            titulo = item.get('title', 'Sem título')
            uris = item.get('uris', [])
            file_size = item.get('fileSize', '')

            # Criar widget container
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(12)

            # Caixa de seleção
            checkbox = QCheckBox()
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #c7d5e0;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 2px solid #555;
                    border-radius: 3px;
                    background-color: #23262e;
                }
                QCheckBox::indicator:checked {
                    background-color: #66c0f4;
                    border-color: #66c0f4;
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
                }
                QCheckBox::indicator:unchecked:hover {
                    border-color: #66c0f4;
                }
            """)
            checkbox.stateChanged.connect(self.verificar_selecao)
            layout.addWidget(checkbox, 0)  # No stretch

            # Label para o título e tamanho
            size_text = f' [{file_size}]' if file_size else ""
            titulo_label = QLabel(f"{titulo}{size_text}")
            titulo_label.setStyleSheet("color: #c7d5e0; font-weight: bold;")
            titulo_label.setWordWrap(True)
            layout.addWidget(titulo_label, 1)  # Stretch factor 1

            # Botão para link/torrent
            if not uris:
                link_btn = QPushButton("[Sem Link]")
                link_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #555555;
                        color: #999999;
                        border: none;
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #666666;
                    }
                """)
                link_btn.setEnabled(False)
            elif any(u.startswith('magnet:') or u.endswith('.torrent') for u in uris):
                link_btn = QPushButton("🔗 Torrent")
                link_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        border: none;
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #2ecc71;
                    }
                    QPushButton:pressed {
                        background-color: #229954;
                    }
                """)
                # Conectar o botão para abrir o torrent
                link_btn.clicked.connect(lambda checked, item_data=item: self.mostrar_opcoes_link(item_data))
            else:
                link_btn = QPushButton("📥 Link")
                link_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: none;
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                    QPushButton:pressed {
                        background-color: #a93226;
                    }
                """)
                # Conectar o botão para baixar o arquivo
                link_btn.clicked.connect(lambda checked, item_data=item: self.mostrar_opcoes_link(item_data))

            # Botão de editar
            edit_btn = QPushButton("✏️ Editar")
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #21618c;
                }
            """)
            edit_btn.clicked.connect(lambda checked, item_data=item: self.abrir_popup_edicao_direto(item_data))

            layout.addWidget(link_btn, 0)  # No stretch
            layout.addWidget(edit_btn, 0)  # No stretch

            # Exibir estrelas de avaliação se existir
            rating = item.get('rating', 0)
            if rating > 0:
                rating_label = QLabel()
                rating_text = "★" * rating + "☆" * (5 - rating)
                rating_label.setText(rating_text)
                rating_label.setStyleSheet("""
                    QLabel {
                        color: #ffd700;
                        font-size: 18px;
                        font-weight: bold;
                        padding: 5px;
                    }
                """)
                layout.addWidget(rating_label, 0)  # No stretch

            # Criar o item da lista
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item)
            
            # Alternância de cor de fundo (zebra striping)
            if idx % 2 == 0:
                list_item.setBackground(QColor('#23262e'))
            else:
                list_item.setBackground(QColor('#1b1e25'))
            
            self.lista.addItem(list_item)
            self.lista.setItemWidget(list_item, container)
            
            # Ajustar altura do item
            container.adjustSize()
            list_item.setSizeHint(container.sizeHint())
            
            # Adicionar separador visual (exceto para o último item)
            if idx < len(items_to_display) - 1:
                separator_item = QListWidgetItem()
                separator_item.setFlags(Qt.NoItemFlags)  # Item não selecionável
                separator_item.setBackground(QColor('#2c3e50'))
                separator_item.setSizeHint(QSize(0, 2))  # Altura de 2 pixels
                self.lista.addItem(separator_item)
        
        self.label_contador.setText(f'Total de itens: {len(self.todos_downloads)} | Mostrando: {len(self.filtered_downloads)}')
        
        # Verificar seleção após atualizar a lista
        self.verificar_selecao()

    def mostrar_opcoes_link(self, item_data):
        """Mostra uma janela de diálogo com opções para copiar links ou baixar"""
        uris = item_data.get('uris', [])
        titulo = item_data.get('title', 'Item')
        
        if not uris:
            QMessageBox.information(self, 'Sem Links', 'Este item não possui links disponíveis.')
            return
        
        # Criar janela de diálogo
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Opções para: {titulo}")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(300)
        layout = QVBoxLayout(dialog)
        
        # Título
        titulo_label = QLabel(f"<b>{titulo}</b>")
        titulo_label.setStyleSheet("color: #c7d5e0; font-size: 14px; padding: 10px;")
        layout.addWidget(titulo_label)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Seção de links
        links_label = QLabel("Links disponíveis:")
        links_label.setStyleSheet("color: #c7d5e0; font-weight: bold; margin-top: 10px;")
        layout.addWidget(links_label)
        
        # Lista de links com botões
        for i, uri in enumerate(uris):
            # Container para cada link
            link_container = QWidget()
            link_layout = QHBoxLayout(link_container)
            link_layout.setContentsMargins(5, 5, 5, 5)
            
            # Ícone baseado no tipo de link
            if uri.startswith('magnet:') or uri.endswith('.torrent'):
                icon_label = QLabel("🔗")
                link_type = "Torrent"
                color = "#27ae60"
            else:
                icon_label = QLabel("📥")
                link_type = "Link"
                color = "#e74c3c"
            
            icon_label.setStyleSheet("font-size: 16px; margin-right: 5px;")
            link_layout.addWidget(icon_label)
            
            # Número do link
            num_label = QLabel(f"Link {i+1} ({link_type}):")
            num_label.setStyleSheet(f"color: {color}; font-weight: bold; min-width: 80px;")
            link_layout.addWidget(num_label)
            
            # URL truncada
            url_display = uri[:50] + "..." if len(uri) > 50 else uri
            url_label = QLabel(url_display)
            url_label.setStyleSheet("color: #95a5a6; font-family: monospace; background: #2c3e50; padding: 3px; border-radius: 3px;")
            url_label.setWordWrap(True)
            link_layout.addWidget(url_label, 1)
            
            # Botão copiar
            btn_copiar = QPushButton("📋 Copiar")
            btn_copiar.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {color.replace('7', '8')};
                }}
            """)
            btn_copiar.clicked.connect(lambda checked, url=uri: self.copiar_link(url))
            link_layout.addWidget(btn_copiar)
            
            # Botão de ação direta
            if uri.startswith('magnet:') or uri.endswith('.torrent'):
                btn_acao = QPushButton("🔗 Abrir Torrent")
                btn_acao.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;
                        color: white;
                        border: none;
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                """)
                btn_acao.clicked.connect(lambda checked, url=uri, title=titulo: self.abrir_cliente_torrent(url, title))
            else:
                btn_acao = QPushButton("🌐 Abrir no Navegador")
                btn_acao.setStyleSheet("""
                    QPushButton {
                        background-color: #f39c12;
                        color: white;
                        border: none;
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #e67e22;
                    }
                """)
                btn_acao.clicked.connect(lambda checked, url=uri: self.abrir_no_navegador(url))
            
            link_layout.addWidget(btn_acao)
            
            layout.addWidget(link_container)
        
        # Botões de ação geral
        separator2 = QFrame()
        separator2.setFrameStyle(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)
        
        # Informação sobre quantidade de links
        if len(uris) > 1:
            info_label = QLabel(f"📊 Total de {len(uris)} links disponíveis")
            info_label.setStyleSheet("color: #95a5a6; font-style: italic; padding: 5px;")
            layout.addWidget(info_label)
        
        # Botões inferiores
        btn_layout = QHBoxLayout()
        
        # Copiar todos os links
        if len(uris) > 1:
            btn_copiar_todos = QPushButton("📋 Copiar Todos os Links")
            btn_copiar_todos.setStyleSheet("""
                QPushButton {
                    background-color: #9b59b6;
                    color: white;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #8e44ad;
                }
            """)
            btn_copiar_todos.clicked.connect(lambda: self.copiar_todos_links(uris))
            btn_layout.addWidget(btn_copiar_todos)
        
        # Botão fechar
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet("""
            QPushButton {
                background-color: #7f8c8d;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #95a5a6;
            }
        """)
        btn_fechar.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_fechar)
        
        layout.addLayout(btn_layout)
        
        dialog.exec_()
    
    def copiar_link(self, url):
        """Copia um link específico para a área de transferência"""
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(url)
                QMessageBox.information(self, 'Link Copiado', f'Link copiado para a área de transferência:\n{url[:50]}...')
            except Exception as e:
                QMessageBox.warning(self, 'Erro ao Copiar', f'Não foi possível copiar o link: {str(e)}')
        else:
            QMessageBox.warning(self, 'Erro', 'Funcionalidade de copiar não disponível. Instale pyperclip.')
    
    def copiar_todos_links(self, uris):
        """Copia todos os links para a área de transferência"""
        if CLIPBOARD_AVAILABLE:
            try:
                todos_links = '\n'.join(uris)
                pyperclip.copy(todos_links)
                QMessageBox.information(self, 'Links Copiados', f'{len(uris)} links copiados para a área de transferência.')
            except Exception as e:
                QMessageBox.warning(self, 'Erro ao Copiar', f'Não foi possível copiar os links: {str(e)}')
        else:
            QMessageBox.warning(self, 'Erro', 'Funcionalidade de copiar não disponível. Instale pyperclip.')
    
    def baixar_arquivo_direto(self, url):
        """Inicia download direto de um arquivo"""
        # Selecionar pasta de destino
        save_dir = QFileDialog.getExistingDirectory(
            self, 'Selecionar pasta de destino'
        )
        if not save_dir:
            return
            
        filename = os.path.basename(url.split('?')[0])
        if not filename:
            filename = "download"

        self.download_title_label.setText(f"Baixando: {filename}")
        self.download_file(url, save_dir)

    def filtrar_lista(self):
        termo = self.search_entry.text().lower()
        
        if termo:
            # Busca em todos os itens, desliga paginação
            self.filtered_downloads = [
                item for item in self.todos_downloads 
                if termo in item.get('title', 'Sem título').lower()
            ]
            self.mostrar_pagina_atual(is_search_result=True)
        else:
            # Sem busca, reativa paginação
            self.filtered_downloads = self.todos_downloads
            self.current_page = 1
            self.mostrar_pagina_atual()

    def abrir_popup_edicao(self, item):
        item_data = item.data(Qt.UserRole) # Pega o item diretamente
        if not item_data:
            return

        # Cria a janela de edição
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Editando: {item_data.get('title', '')}")
        dialog.setMinimumWidth(600)
        layout = QVBoxLayout(dialog)

        # Campos de edição
        campos = {}

        # Title
        layout.addWidget(QLabel("title:"))
        entry_title = QLineEdit()
        entry_title.setText(item_data.get('title', ''))
        layout.addWidget(entry_title)
        campos['title'] = entry_title

        # URIs (lista multiline)
        layout.addWidget(QLabel("uris (uma URI por linha):"))
        text_uris = QTextEdit()
        text_uris.setPlainText('\n'.join(item_data.get('uris', [])))
        text_uris.setMaximumHeight(100)
        layout.addWidget(text_uris)
        campos['uris'] = text_uris

        # uploadDate
        layout.addWidget(QLabel("uploadDate:"))
        entry_uploadDate = QLineEdit()
        entry_uploadDate.setText(item_data.get('uploadDate', ''))
        layout.addWidget(entry_uploadDate)
        campos['uploadDate'] = entry_uploadDate

        # fileSize
        layout.addWidget(QLabel("fileSize:"))
        entry_fileSize = QLineEdit()
        entry_fileSize.setText(item_data.get('fileSize', ''))
        layout.addWidget(entry_fileSize)
        campos['fileSize'] = entry_fileSize

        # repackLinkSource (opcional)
        layout.addWidget(QLabel("repackLinkSource (opcional):"))
        entry_repack = QLineEdit()
        entry_repack.setText(item_data.get('repackLinkSource', ''))
        layout.addWidget(entry_repack)
        campos['repackLinkSource'] = entry_repack

        # Nota (1-5 estrelas)
        layout.addWidget(QLabel("Nota (1-5 estrelas):"))
        nota_layout = QHBoxLayout()

        estrelas = []
        rating_atual = item_data.get('rating', 0)
        # Usar um dicionário para contornar o problema de escopo do lambda
        nota_selecionada = {'value': rating_atual}

        def atualizar_estrelas(idx, b_estrelas):
            nota_selecionada['value'] = idx + 1
            for i, btn in enumerate(b_estrelas):
                if i <= idx:
                    btn.setText("★")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: transparent;
                            border: none;
                            font-size: 26px;
                            color: #ffd700;
                        }
                    """)
                else:
                    btn.setText("☆")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: transparent;
                            border: none;
                            font-size: 26px;
                            color: #888;
                        }
                        QPushButton:hover {
                            color: #ffd700;
                        }
                    """)
        
        for i in range(5):
            estrela_btn = QPushButton("☆")
            estrela_btn.setFixedSize(35, 35)
            # Usamos uma função anônima para capturar o valor de 'i' corretamente
            estrela_btn.clicked.connect(lambda checked, idx=i, b=estrelas: atualizar_estrelas(idx, b))
            estrelas.append(estrela_btn)
            nota_layout.addWidget(estrela_btn)
        
        # Define o estado inicial das estrelas
        if rating_atual > 0:
            atualizar_estrelas(rating_atual - 1, estrelas)
        else:
            atualizar_estrelas(-1, estrelas)

        nota_layout.addStretch()
        layout.addLayout(nota_layout)
        campos['estrelas'] = estrelas
        campos['nota_atual'] = nota_selecionada['value']  # Carregar nota atual

        # Botões
        btn_layout = QHBoxLayout()
        btn_salvar = QPushButton('Salvar')
        btn_cancelar = QPushButton('Cancelar')
        btn_layout.addWidget(btn_salvar)
        btn_layout.addWidget(btn_cancelar)
        layout.addLayout(btn_layout)

        def salvar_edicao():
            item_data['title'] = campos['title'].text().strip()
            uris_novo = campos['uris'].toPlainText().strip()
            item_data['uris'] = [u.strip() for u in uris_novo.splitlines() if u.strip()]
            item_data['uploadDate'] = campos['uploadDate'].text().strip()
            item_data['fileSize'] = campos['fileSize'].text().strip()
            repack_val = campos['repackLinkSource'].text().strip()
            if repack_val:
                item_data['repackLinkSource'] = repack_val
            elif 'repackLinkSource' in item_data:
                del item_data['repackLinkSource']
            
            # Salvar nota se selecionada
            nova_nota = nota_selecionada['value']
            if nova_nota > 0:
                item_data['rating'] = nova_nota
            elif 'rating' in item_data:
                del item_data['rating']

            self.filtrar_lista() # Atualiza a lista respeitando a busca/paginação
            
            # Salva as alterações no arquivo atual
            self.salvar_arquivo_atual()
            
            dialog.accept()

        btn_salvar.clicked.connect(salvar_edicao)
        btn_cancelar.clicked.connect(dialog.reject)

        dialog.exec_()

    def abrir_popup_edicao_direto(self, item_data):
        """Abre a janela de edição diretamente com os dados do item"""
        if not item_data:
            return

        # Cria a janela de edição
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Editando: {item_data.get('title', '')}")
        dialog.setMinimumWidth(600)
        layout = QVBoxLayout(dialog)

        # Campos de edição
        campos = {}

        # Title
        layout.addWidget(QLabel("title:"))
        entry_title = QLineEdit()
        entry_title.setText(item_data.get('title', ''))
        layout.addWidget(entry_title)
        campos['title'] = entry_title

        # URIs (lista multiline)
        layout.addWidget(QLabel("uris (uma URI por linha):"))
        text_uris = QTextEdit()
        text_uris.setPlainText('\n'.join(item_data.get('uris', [])))
        text_uris.setMaximumHeight(100)
        layout.addWidget(text_uris)
        campos['uris'] = text_uris

        # uploadDate
        layout.addWidget(QLabel("uploadDate:"))
        entry_uploadDate = QLineEdit()
        entry_uploadDate.setText(item_data.get('uploadDate', ''))
        layout.addWidget(entry_uploadDate)
        campos['uploadDate'] = entry_uploadDate

        # fileSize
        layout.addWidget(QLabel("fileSize:"))
        entry_fileSize = QLineEdit()
        entry_fileSize.setText(item_data.get('fileSize', ''))
        layout.addWidget(entry_fileSize)
        campos['fileSize'] = entry_fileSize

        # repackLinkSource (opcional)
        layout.addWidget(QLabel("repackLinkSource (opcional):"))
        entry_repack = QLineEdit()
        entry_repack.setText(item_data.get('repackLinkSource', ''))
        layout.addWidget(entry_repack)
        campos['repackLinkSource'] = entry_repack

        # Nota (1-5 estrelas)
        layout.addWidget(QLabel("Nota (1-5 estrelas):"))
        nota_layout = QHBoxLayout()

        estrelas = []
        rating_atual = item_data.get('rating', 0)
        # Usar um dicionário para contornar o problema de escopo do lambda
        nota_selecionada = {'value': rating_atual}

        def atualizar_estrelas(idx, b_estrelas):
            nota_selecionada['value'] = idx + 1
            for i, btn in enumerate(b_estrelas):
                if i <= idx:
                    btn.setText("★")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: transparent;
                            border: none;
                            font-size: 26px;
                            color: #ffd700;
                        }
                    """)
                else:
                    btn.setText("☆")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: transparent;
                            border: none;
                            font-size: 26px;
                            color: #888;
                        }
                        QPushButton:hover {
                            color: #ffd700;
                        }
                    """)
        
        for i in range(5):
            estrela_btn = QPushButton("☆")
            estrela_btn.setFixedSize(35, 35)
            # Usamos uma função anônima para capturar o valor de 'i' corretamente
            estrela_btn.clicked.connect(lambda checked, idx=i, b=estrelas: atualizar_estrelas(idx, b))
            estrelas.append(estrela_btn)
            nota_layout.addWidget(estrela_btn)
        
        # Define o estado inicial das estrelas
        if rating_atual > 0:
            atualizar_estrelas(rating_atual - 1, estrelas)
        else:
            atualizar_estrelas(-1, estrelas)

        nota_layout.addStretch()
        layout.addLayout(nota_layout)
        campos['estrelas'] = estrelas
        campos['nota_atual'] = nota_selecionada['value']  # Carregar nota atual

        # Botões
        btn_layout = QHBoxLayout()
        btn_salvar = QPushButton('Salvar')
        btn_cancelar = QPushButton('Cancelar')
        btn_layout.addWidget(btn_salvar)
        btn_layout.addWidget(btn_cancelar)
        layout.addLayout(btn_layout)

        def salvar_edicao():
            item_data['title'] = campos['title'].text().strip()
            uris_novo = campos['uris'].toPlainText().strip()
            item_data['uris'] = [u.strip() for u in uris_novo.splitlines() if u.strip()]
            item_data['uploadDate'] = campos['uploadDate'].text().strip()
            item_data['fileSize'] = campos['fileSize'].text().strip()
            repack_val = campos['repackLinkSource'].text().strip()
            if repack_val:
                item_data['repackLinkSource'] = repack_val
            elif 'repackLinkSource' in item_data:
                del item_data['repackLinkSource']
            
            # Salvar nota se selecionada
            nova_nota = nota_selecionada['value']
            if nova_nota > 0:
                item_data['rating'] = nova_nota
            elif 'rating' in item_data:
                del item_data['rating']

            self.filtrar_lista() # Atualiza a lista respeitando a busca/paginação
            
            # Salva as alterações no arquivo atual
            self.salvar_arquivo_atual()
            
            dialog.accept()

        btn_salvar.clicked.connect(salvar_edicao)
        btn_cancelar.clicked.connect(dialog.reject)

        dialog.exec_()

    def iniciar_download(self, item_data):
        """Inicia o processo de download do item selecionado"""
        if self.is_downloading:
            QMessageBox.warning(self, 'Aviso', 'Um download já está em andamento.')
            return

        uris = item_data.get('uris', [])
        if not uris:
            QMessageBox.warning(self, 'Aviso', 'Nenhuma URI disponível para download.')
            return
            
        # Se há múltiplas URIs, deixar o usuário escolher
        if len(uris) > 1:
            uri, ok = QInputDialog.getItem(
                self, 'Selecionar URI', 
                'Escolha a URI para download:', 
                uris, 0, False
            )
            if not ok:
                return
        else:
            uri = uris[0]
            
        # Verificar se é torrent ou arquivo normal
        is_torrent = uri.startswith('magnet:') or uri.endswith('.torrent')
        
        if is_torrent:
            # Para torrents, abrir cliente externo
            self.abrir_cliente_torrent(uri, item_data.get('title', 'Torrent'))
        else:
            # Para arquivos normais, continuar com o download interno
            # Selecionar pasta de destino
            save_dir = QFileDialog.getExistingDirectory(
                self, 'Selecionar pasta de destino'
            )
            if not save_dir:
                return
                
            filename = os.path.basename(uri.split('?')[0])
            if not filename:
                filename = "download"

            self.download_title_label.setText(f"Baixando: {filename}")
            self.download_file(uri, save_dir)
            
    def abrir_cliente_torrent(self, torrent_url, title):
        """Abre um cliente torrent externo com o link fornecido"""
        # Lista de clientes torrent comuns no Windows
        clientes_torrent = [
            # qBittorrent
            {
                'nome': 'qBittorrent',
                'comandos': [
                    r'C:\Program Files\qBittorrent\qbittorrent.exe',
                    r'C:\Program Files (x86)\qBittorrent\qbittorrent.exe',
                    'qbittorrent'
                ],
                'args': ['{}']
            },
            # uTorrent
            {
                'nome': 'uTorrent',
                'comandos': [
                    r'C:\Users\{}\AppData\Roaming\uTorrent\uTorrent.exe'.format(os.getenv('USERNAME')),
                    r'C:\Program Files\uTorrent\uTorrent.exe',
                    r'C:\Program Files (x86)\uTorrent\uTorrent.exe',
                    'utorrent'
                ],
                'args': ['{}']
            },
            # BitTorrent
            {
                'nome': 'BitTorrent',
                'comandos': [
                    r'C:\Program Files\BitTorrent\BitTorrent.exe',
                    r'C:\Program Files (x86)\BitTorrent\BitTorrent.exe',
                    'bittorrent'
                ],
                'args': ['{}']
            },
            # Deluge
            {
                'nome': 'Deluge',
                'comandos': [
                    r'C:\Program Files\Deluge\deluge.exe',
                    r'C:\Program Files (x86)\Deluge\deluge.exe',
                    'deluge'
                ],
                'args': ['{}']
            },
            # Tixati
            {
                'nome': 'Tixati',
                'comandos': [
                    r'C:\Program Files\Tixati\tixati.exe',
                    r'C:\Program Files (x86)\Tixati\tixati.exe',
                    'tixati'
                ],
                'args': ['{}']
            },
            # WebTorrent Desktop
            {
                'nome': 'WebTorrent Desktop',
                'comandos': [
                    r'C:\Users\{}\AppData\Local\Programs\webtorrent\WebTorrent.exe'.format(os.getenv('USERNAME')),
                    r'C:\Program Files\WebTorrent\WebTorrent.exe',
                    'webtorrent'
                ],
                'args': ['{}']
            },
            # Transmission (se instalado via chocolatey ou similar)
            {
                'nome': 'Transmission',
                'comandos': [
                    r'C:\Program Files\Transmission\transmission-qt.exe',
                    'transmission-qt'
                ],
                'args': ['{}']
            }
        ]
        
        # Tentar abrir com cada cliente
        for cliente in clientes_torrent:
            for comando in cliente['comandos']:
                try:
                    # Expandir variáveis de ambiente no caminho
                    comando_expandido = os.path.expandvars(comando)
                    
                    # Verificar se o executável existe
                    if os.path.exists(comando_expandido) or comando == cliente['comandos'][-1]:  # Último é o comando genérico
                        # Construir argumentos
                        args = []
                        for arg_template in cliente['args']:
                            args.append(arg_template.format(torrent_url))
                        
                        # Tentar executar
                        if comando == cliente['comandos'][-1]:  # Comando genérico
                            subprocess.Popen([comando] + args, shell=True)
                        else:
                            subprocess.Popen([comando_expandido] + args)
                        
                        return
                        
                except Exception as e:
                    continue
        
        # Se nenhum cliente foi encontrado, mostrar mensagem de erro
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Cliente Torrent Não Encontrado')
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setText(
            'Nenhum cliente torrent foi encontrado no sistema.\n\n'
            'Clientes suportados:\n'
            '• qBittorrent\n'
            '• uTorrent\n'
            '• BitTorrent\n'
            '• Deluge\n'
            '• Tixati\n'
            '• WebTorrent Desktop\n'
            '• Transmission\n\n'
            'Por favor, instale um desses clientes ou copie o link manualmente.'
        )
        
        # Adicionar botão para copiar link se pyperclip estiver disponível
        if CLIPBOARD_AVAILABLE:
            copy_button = msg_box.addButton("Copiar Link", QMessageBox.ActionRole)
            msg_box.addButton("OK", QMessageBox.Ok)
        else:
            msg_box.addButton("OK", QMessageBox.Ok)
        
        msg_box.exec_()
        
        # Se o botão de copiar foi clicado
        if CLIPBOARD_AVAILABLE and msg_box.clickedButton() == copy_button:
            try:
                pyperclip.copy(torrent_url)
                QMessageBox.information(
                    self, 'Link Copiado', 
                    f'Link copiado para a área de transferência:\n{torrent_url}'
                )
            except Exception as e:
                QMessageBox.warning(
                    self, 'Erro ao Copiar', 
                    f'Não foi possível copiar o link: {str(e)}'
                )

    def download_file(self, file_url, save_dir):
        """Inicia download de arquivo normal"""
        # Extrair nome do arquivo da URL
        filename = os.path.basename(file_url.split('?')[0])
        if not filename:
            filename = "download"
        save_path = os.path.join(save_dir, filename)
        
        self.is_downloading = True
        self.download_progress_frame.setVisible(True)
        self.download_cancel_button.setEnabled(True)
        
        # Criar e configurar downloader
        self.file_downloader = FileDownloader(file_url, save_path)
        self.file_downloader.progress_updated.connect(
            self.atualizar_progresso_arquivo
        )
        self.file_downloader.download_finished.connect(
            lambda success, msg: self.finalizar_download(success, msg, is_torrent=False)
        )
        
        self.file_downloader.start()
        
    def atualizar_progresso_arquivo(self, progress, downloaded, total_size, speed):
        """Atualiza a interface de progresso para arquivos normais"""
        self.download_progress_bar.setValue(progress)
        
        # Formata as strings de informação
        if total_size > 0:
            size_str = f"{downloaded / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB"
        else:
            size_str = f"{downloaded / (1024*1024):.2f} MB"
            
        speed_str = f"{speed / 1024:.1f} KB/s"
        
        eta_str = "N/A"
        if speed > 0 and total_size > 0 and downloaded < total_size:
            try:
                eta = (total_size - downloaded) / speed
                eta_str = time.strftime('%H:%M:%S', time.gmtime(eta))
            except (ValueError, OSError):
                eta_str = "Calculando..."

        stats_str = f"{size_str} | Velocidade: {speed_str} | ETA: {eta_str}"
        self.download_stats_label.setText(stats_str)
        self.download_torrent_stats_label.setText("")
        
    def finalizar_download(self, success, message, is_torrent=False):
        """Finaliza o download e restaura a interface"""
        self.is_downloading = False
        self.download_progress_frame.setVisible(False)
        self.download_cancel_button.setEnabled(False)
        
        if success:
            QMessageBox.information(self, 'Sucesso', f'Download concluído!\n{message}')
        else:
            if "cancelado" not in message.lower():
                QMessageBox.critical(self, 'Erro', f'Erro no download:\n{message}')
            
        # Parar o downloader
        if is_torrent and hasattr(self, 'torrent_downloader'):
            self.torrent_downloader.stop()
        elif not is_torrent and hasattr(self, 'file_downloader'):
            self.file_downloader.stop()

    def atualizar_progresso(self, valor, texto=""):
        """Atualiza a barra de progresso e o texto"""
        self.progress_bar.setValue(int(valor))
        self.progress_bar.setFormat(texto)
        QApplication.processEvents()

    def baixar_e_salvar_json(self, url):
        """Baixa um JSON de uma URL e salva localmente"""
        try:
            # Gera um nome de arquivo único baseado na URL
            url_hash = hashlib.md5(url.encode()).hexdigest()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{url_hash}_{timestamp}.json"
            filepath = os.path.join(self.link_dir, filename)

            # Verifica se já existe uma versão recente (menos de 1 hora)
            for existing_file in os.listdir(self.link_dir):
                if existing_file.startswith(url_hash):
                    existing_path = os.path.join(self.link_dir, existing_file)
                    file_time = os.path.getmtime(existing_path)
                    if (datetime.now().timestamp() - file_time) < 3600:  # 1 hora
                        print(f"Usando arquivo em cache: {existing_path}")
                        self.atualizar_progresso(100, "Usando arquivo em cache")
                        with open(existing_path, 'r', encoding='utf-8') as f:
                            return json.load(f)

            # Se não encontrou em cache, baixa e salva
            print(f"Baixando JSON da URL: {url}")
            self.atualizar_progresso(0, "Iniciando download...")
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Calcula o tamanho total do arquivo
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024  # 1 Kibibyte
            downloaded = 0
            
            # Baixa o arquivo em chunks
            data = bytearray()
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    data.extend(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        progresso = (downloaded / total_size) * 100
                        self.atualizar_progresso(
                            progresso,
                            f"Baixando: {downloaded}/{total_size} bytes"
                        )
            
            # Processa o JSON
            self.atualizar_progresso(90, "Processando JSON...")
            dados = json.loads(data.decode('utf-8'))
            
            # Salva o arquivo
            self.atualizar_progresso(95, "Salvando arquivo...")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)

            print(f"Arquivo salvo em: {filepath}")
            self.atualizar_progresso(100, "Download concluído!")
            return dados

        except Exception as e:
            self.atualizar_progresso(0, "Erro no download")
            raise Exception(f"Erro ao baixar/salvar JSON: {str(e)}")

    def abrir_de_url(self):
        url, ok = QInputDialog.getText(self, 'Abrir de URL', 'Digite a URL do arquivo JSON:')
        if not ok or not url:
            return
            
        try:
            self.dados = self.baixar_e_salvar_json(url)
            print(f"Conteúdo baixado: {self.dados}")  # Debug
            
            
            self.arquivo_atual = None  # Não temos arquivo local
            self.label_name.setText(self.dados.get('name', '(sem nome)'))
            self.btn_editar_nome.setEnabled(True)
            self.btn_adicionar_item.setEnabled(True)
            self.btn_excluir.setEnabled(True)
            self.atualizar_lista()
            self.btn_salvar.setEnabled(False)  # Desabilita salvar pois não temos arquivo local
            
            # Mostrar quantidade de downloads encontrados
            num_downloads = len(self.dados.get('downloads', []))
            QMessageBox.information(self, 'Sucesso', 
                              f"JSON baixado com sucesso!\n"
                              f"Encontrados {num_downloads} downloads.")
                              
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f"Erro ao processar URL:\n{e}")

    def salvar_arquivo(self):
        # Esta função agora vai agir como "Salvar" ou "Salvar Como" dependendo do contexto.
        if self.arquivo_atual:
            self.salvar_arquivo_atual()
        else:
            self.salvar_como()

    def salvar_arquivo_atual(self):
        """Salva as alterações no arquivo JSON atualmente aberto."""
        if not self.arquivo_atual:
            # Se nenhum arquivo estiver aberto (ex: dados da URL), usa "salvar_como"
            self.salvar_como()
            return

        if not self.dados:
            QMessageBox.warning(self, 'Aviso', 'Nenhum dado para salvar.')
            return

        try:
            with open(self.arquivo_atual, 'w', encoding='utf-8') as f:
                json.dump(self.dados, f, indent=4, ensure_ascii=False)
            
            self.statusBar().showMessage(f"Arquivo salvo: {os.path.basename(self.arquivo_atual)}", 3000)
            self.btn_salvar.setEnabled(False) # Desabilita o botão após salvar
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao salvar arquivo:\n{e}')

    def salvar_como(self):
        if not self.dados:
            QMessageBox.warning(self, 'Aviso', 'Não há dados para salvar.')
            return

        caminho, _ = QFileDialog.getSaveFileName(self, 'Salvar como...', '', 'Arquivos JSON (*.json);;Todos os arquivos (*)')
        if caminho:
            try:
                with open(caminho, 'w', encoding='utf-8') as f:
                    json.dump(self.dados, f, indent=4, ensure_ascii=False)
                self.arquivo_atual = caminho
                self.setWindowTitle(f'SuperBase editor e gerenciador - {os.path.basename(caminho)}')
                QMessageBox.information(self, 'Sucesso', f'Arquivo salvo em:\n{caminho}')
            except Exception as e:
                QMessageBox.critical(self, 'Erro', f'Falha ao salvar arquivo:\n{e}')

    def exportar_json_sem_estrelas(self):
        """Exporta a lista atual para um novo arquivo JSON sem os dados de avaliação."""
        if not self.dados:
            QMessageBox.warning(self, 'Aviso', 'Não há dados para exportar.')
            return

        # Cria uma cópia profunda dos dados para não alterar a sessão atual
        dados_para_exportar = json.loads(json.dumps(self.dados))

        # Remove a chave 'rating' de cada item na lista de downloads
        if 'downloads' in dados_para_exportar:
            for item in dados_para_exportar['downloads']:
                if 'rating' in item:
                    del item['rating']
        
        caminho, _ = QFileDialog.getSaveFileName(self, 'Exportar como (sem estrelas)...', '', 'Arquivos JSON (*.json);;Todos os arquivos (*)')
        if caminho:
            try:
                with open(caminho, 'w', encoding='utf-8') as f:
                    json.dump(dados_para_exportar, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, 'Sucesso', f'Arquivo exportado (sem estrelas) em:\n{caminho}')
            except Exception as e:
                QMessageBox.critical(self, 'Erro', f'Falha ao exportar arquivo:\n{e}')

    def excluir_selecionado(self):
        # Coletar itens selecionados através das caixas de seleção
        selected_items = []
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.flags() & Qt.ItemIsSelectable:  # Ignorar separadores
                widget = self.lista.itemWidget(item)
                if widget:
                    # Encontrar a caixa de seleção no widget
                    for child in widget.findChildren(QCheckBox):
                        if child.isChecked():
                            selected_items.append(item)
                            break
        
        if not selected_items:
            QMessageBox.warning(self, 'Aviso', 'Selecione pelo menos um item para excluir.')
            return
            
        reply = QMessageBox.question(
            self, 'Confirmar Exclusão',
            f"Tem certeza que deseja excluir {len(selected_items)} item(ns) selecionado(s)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Pega os dados dos itens a serem removidos
            items_to_remove = {id(item.data(Qt.UserRole)) for item in selected_items}

            # Filtra a lista de downloads principal, mantendo os que não foram selecionados
            self.dados['downloads'] = [
                d for d in self.dados['downloads'] if id(d) not in items_to_remove
            ]
            
            # Atualiza a lista na interface
            self.atualizar_lista()
            
            QMessageBox.information(self, 'Sucesso', 'Itens excluídos com sucesso!')
            
            # Habilita o botão de salvar após a exclusão
            self.btn_salvar.setEnabled(True)

    def unir_arquivos(self):
        dialog = MergeFilesDialog(self)
        dialog.exec_()
        if dialog.merged_data:
            self.dados = dialog.merged_data
            self.atualizar_lista()
            QMessageBox.information(self, 'Sucesso', 'Arquivos unidos com sucesso!')
            self.btn_salvar.setEnabled(True)

    def mostrar_sobre(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Sobre')
        msg_box.setText(
            'Editor JSON - Downloads (PyQt5)\n' +
            'Versão: 1.2.1\n' +
            'Desenvolvedor: Prietto'
        )
        msg_box.setInformativeText("Gostaria de visitar o perfil do desenvolvedor?")
        
        msg_box.setStandardButtons(QMessageBox.Ok)
        github_button = msg_box.addButton("Visitar ", QMessageBox.ActionRole)

        msg_box.exec_()

        if msg_box.clickedButton() == github_button:
            self.abrir_link_desenvolvedor()

    def abrir_link_desenvolvedor(self):
        QDesktopServices.openUrl(QUrl("https://www.instagram.com/prietto_polar/?igsh=MXgycXg5eThzNmprZw%3D%3D#"))

    def atualizar_lista_comunidade(self):
        # Caixa de diálogo de aviso
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Aviso de Responsabilidade")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setText(
            "Aviso: Ao utilizar esta base de dados da comunidade, você reconhece que o uso é de sua total responsabilidade."
        )
        msg_box.setInformativeText("Certifique-se de revisar as informações antes de aplicá-las.\nDeseja continuar e fazer o download?")
        
        download_button = msg_box.addButton("Download", QMessageBox.AcceptRole)
        msg_box.addButton("Cancelar", QMessageBox.RejectRole)
        
        msg_box.exec_()

        if msg_box.clickedButton() != download_button:
            return # O usuário cancelou

        url = 'https://drive.google.com/uc?export=download'
        file_id = '1NXO_XnSl7Z9fEtQDejKhe0VbneQY7PC6' # ID do arquivo ZIP
        
        try:
            # Usar uma sessão para lidar com cookies do Google Drive
            session = requests.Session()
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

            # Primeira requisição para obter o token de confirmação
            response = session.get(url, params={'id': file_id}, stream=True, headers=headers)
            
            token = None
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    token = value
                    break

            # Se um token foi encontrado, fazer uma segunda requisição com ele
            if token:
                params = {'id': file_id, 'confirm': token}
                response = session.get(url, params=params, stream=True, headers=headers)
            
            response.raise_for_status()

            # Configurar barra de progresso para porcentagem
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            QApplication.processEvents()

            # Salvar o arquivo ZIP temporariamente
            zip_path = os.path.join(self.link_dir, 'superbase.zip')
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            self.progress_bar.setValue(int(progress))
                            self.progress_bar.setFormat(f"Baixando: {int(progress)}%")
                            QApplication.processEvents()
            
            self.progress_bar.setFormat("Extraindo arquivo...")
            QApplication.processEvents()
            
            # Extrair o arquivo ZIP
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Listar arquivos no ZIP
                json_files = [f for f in zf.namelist() if f.endswith('.json')]
                if not json_files:
                    raise Exception("Nenhum arquivo JSON encontrado no arquivo baixado.")
                
                # Extrair o primeiro arquivo JSON encontrado
                json_filename = json_files[0]
                zf.extract(json_filename, self.link_dir)
                json_path = os.path.join(self.link_dir, json_filename)
            
            self.progress_bar.setFormat("Carregando dados...")
            QApplication.processEvents()
            
            # Carregar o arquivo JSON extraído
            with open(json_path, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            # Limpar arquivos temporários
            try:
                os.remove(zip_path)
                os.remove(json_path)
            except:
                pass
            
            # Atualizar a interface
            self.dados = dados
            self.todos_downloads = dados.get('downloads', [])
            self.label_name.setText(dados.get('name', '(sem nome)'))
            self.btn_editar_nome.setEnabled(True)
            self.btn_adicionar_item.setEnabled(True)
            self.btn_excluir.setEnabled(True)
            self.atualizar_lista()
            
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Lista da comunidade atualizada!")
            
            QMessageBox.information(self, 'Sucesso', 'Lista da comunidade atualizada com sucesso!')
            self.btn_salvar.setEnabled(True)
            
            # Limpar a mensagem de progresso após 3 segundos
            QTimer.singleShot(3000, lambda: self.progress_bar.setFormat(""))
            
        except Exception as e:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("")
            QMessageBox.critical(self, 'Erro', f'Erro ao baixar/extrair lista da comunidade:\n{e}')

    def cancelar_download(self):
        if not self.is_downloading:
            return
        
        reply = QMessageBox.question(
            self, 'Cancelar Download',
            "Tem certeza que deseja cancelar o download em andamento?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if hasattr(self, 'torrent_downloader') and self.torrent_downloader.isRunning():
                self.torrent_downloader.stop()
            if hasattr(self, 'file_downloader') and self.file_downloader.isRunning():
                self.file_downloader.stop()
            
            self.finalizar_download(False, "Download cancelado pelo usuário.")
            QMessageBox.information(self, "Cancelado", "O download foi cancelado.")

    def proxima_pagina(self):
        total_pages = (len(self.filtered_downloads) + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.mostrar_pagina_atual()

    def pagina_anterior(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.mostrar_pagina_atual()

    def iniciar_busca(self):
        """Inicia a busca manual e atualiza a barra de progresso."""
        termo = self.search_entry.text()
        if not termo.strip():
            self.filtrar_lista()
            self.progress_bar.setFormat("")
            self.progress_bar.setValue(0)
            return

        self.progress_bar.setRange(0, 0)  # Modo indeterminado
        self.progress_bar.setFormat("Buscando...")
        QApplication.processEvents()

        self.filtrar_lista()

        num_resultados = len(self.filtered_downloads)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(f"Encontrados {num_resultados} resultados")
        
        QTimer.singleShot(4000, lambda: self.progress_bar.setFormat("") if self.progress_bar.value() == 100 else None)

    def verificar_busca_limpa(self, texto):
        """Reseta a lista se o campo de busca for limpo."""
        if not texto:
            self.filtrar_lista()
            self.progress_bar.setFormat("")
            self.progress_bar.setValue(0)

    def criar_nova_lista(self):
        """Cria uma nova lista do zero"""
        # Pedir nome para a nova lista
        nome_lista, ok = QInputDialog.getText(
            self, 'Nova Lista', 
            'Digite o nome para sua nova lista:',
            text='Minha Lista de Downloads'
        )
        
        if not ok or not nome_lista.strip():
            return
        
        # Criar estrutura básica da nova lista
        self.dados = {
            'name': nome_lista.strip(),
            'downloads': []
        }
        
        # Limpar arquivo atual (nova lista)
        self.arquivo_atual = None
        
        # Atualizar interface
        self.label_name.setText(self.dados['name'])
        self.btn_editar_nome.setEnabled(True)
        self.btn_adicionar_item.setEnabled(True)
        self.btn_excluir.setEnabled(True)
        self.atualizar_lista()
        self.btn_salvar.setEnabled(True)
        
        # Mostrar mensagem de sucesso
        QMessageBox.information(
            self, 'Nova Lista Criada', 
            f'Lista "{nome_lista}" criada com sucesso!\n\n'
            'Para adicionar itens:\n'
            '• Clique com o botão direito na lista\n'
            '• Ou use o menu "Adicionar Item"'
        )
        
        # Atualizar título da janela
        self.setWindowTitle(f'SuperBase editor e gerenciador - Nova Lista')
    
    def adicionar_item(self):
        """Adiciona um novo item à lista"""
        if not self.dados:
            QMessageBox.warning(self, 'Aviso', 'Crie ou abra uma lista primeiro.')
            return
        
        # Criar janela de adição de item
        dialog = QDialog(self)
        dialog.setWindowTitle("Adicionar Novo Item")
        dialog.setMinimumWidth(600)
        layout = QVBoxLayout(dialog)

        # Campos do item
        campos = {}

        # Title
        layout.addWidget(QLabel("Título:"))
        entry_title = QLineEdit()
        entry_title.setPlaceholderText("Digite o título do item...")
        layout.addWidget(entry_title)
        campos['title'] = entry_title

        # URIs (lista multiline)
        layout.addWidget(QLabel("Links (um por linha):"))
        text_uris = QTextEdit()
        text_uris.setPlaceholderText("magnet:?xt=urn:btih:...\nhttps://exemplo.com/arquivo.zip")
        text_uris.setMaximumHeight(100)
        layout.addWidget(text_uris)
        campos['uris'] = text_uris

        # uploadDate
        layout.addWidget(QLabel("Data de Upload (opcional):"))
        entry_uploadDate = QLineEdit()
        entry_uploadDate.setPlaceholderText("2024-01-01")
        layout.addWidget(entry_uploadDate)
        campos['uploadDate'] = entry_uploadDate

        # fileSize
        layout.addWidget(QLabel("Tamanho do Arquivo (opcional):"))
        entry_fileSize = QLineEdit()
        entry_fileSize.setPlaceholderText("1.5 GB")
        layout.addWidget(entry_fileSize)
        campos['fileSize'] = entry_fileSize

        # repackLinkSource (opcional)
        layout.addWidget(QLabel("repackLinkSource (opcional):"))
        entry_repack = QLineEdit()
        entry_repack.setPlaceholderText("https://exemplo.com/repack")
        layout.addWidget(entry_repack)
        campos['repackLinkSource'] = entry_repack

        # Nota (1-5 estrelas)
        layout.addWidget(QLabel("Nota (1-5 estrelas):"))
        nota_layout = QHBoxLayout()

        estrelas = []
        for i in range(5):
            estrela_btn = QPushButton("☆")
            estrela_btn.setFixedSize(30, 30)
            estrela_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    font-size: 20px;
                    color: #666;
                }
                QPushButton:hover {
                    color: #ffd700;
                }
            """)
            estrela_btn.clicked.connect(lambda checked, idx=i: self.selecionar_estrela(estrelas, idx))
            estrelas.append(estrela_btn)
            nota_layout.addWidget(estrela_btn)
        
        nota_layout.addStretch()
        layout.addLayout(nota_layout)
        campos['estrelas'] = estrelas
        campos['nota_atual'] = 0  # Variável para armazenar a nota selecionada

        # Botões
        btn_layout = QHBoxLayout()
        btn_adicionar = QPushButton('➕ Adicionar Item')
        btn_cancelar = QPushButton('Cancelar')
        btn_layout.addWidget(btn_adicionar)
        btn_layout.addWidget(btn_cancelar)
        layout.addLayout(btn_layout)

        def adicionar_item():
            # Validar campos obrigatórios
            titulo = campos['title'].text().strip()
            uris_texto = campos['uris'].toPlainText().strip()
            
            if not titulo:
                QMessageBox.warning(dialog, 'Campo Obrigatório', 'O título é obrigatório.')
                return
            
            if not uris_texto:
                QMessageBox.warning(dialog, 'Campo Obrigatório', 'Pelo menos um link é obrigatório.')
                return
            
            # Criar novo item
            novo_item = {
                'title': titulo,
                'uris': [u.strip() for u in uris_texto.splitlines() if u.strip()],
                'uploadDate': campos['uploadDate'].text().strip(),
                'fileSize': campos['fileSize'].text().strip()
            }
            
            # Adicionar repackLinkSource se fornecido
            repack_val = campos['repackLinkSource'].text().strip()
            if repack_val:
                novo_item['repackLinkSource'] = repack_val
            
            # Adicionar nota se selecionada
            if nota_selecionada['value'] > 0:
                novo_item['rating'] = nota_selecionada['value']

            # Adicionar à lista
            self.dados['downloads'].append(novo_item)
            
            # Atualizar interface
            self.atualizar_lista()
            self.btn_salvar.setEnabled(True)
            
            dialog.accept()
            QMessageBox.information(self, 'Sucesso', f'Item "{titulo}" adicionado com sucesso!')

        btn_adicionar.clicked.connect(adicionar_item)
        btn_cancelar.clicked.connect(dialog.reject)

        dialog.exec_()

    def abrir_no_navegador(self, url):
        """Abre um link no navegador padrão do sistema"""
        try:
            QDesktopServices.openUrl(QUrl(url))
            QMessageBox.information(
                self, 'Navegador Aberto', 
                f'Link aberto no navegador:\n{url[:50]}...'
            )
        except Exception as e:
            QMessageBox.warning(
                self, 'Erro ao Abrir Navegador', 
                f'Não foi possível abrir o link no navegador:\n{str(e)}'
            )

    def mostrar_menu_contexto(self, pos):
        """Mostra menu de contexto na lista"""
        menu = QMenu()
        
        # Adicionar item (sempre disponível se há uma lista)
        if self.dados:
            menu.addAction("➕ Adicionar Item", self.adicionar_item)
            menu.addSeparator()
        
        # Opções para item selecionado
        item = self.lista.itemAt(pos)
        if item:
            item_data = item.data(Qt.UserRole)
            if item_data:
                menu.addAction("✏️ Editar", lambda: self.abrir_popup_edicao(item))
                menu.addAction("🗑️ Excluir", lambda: self.excluir_selecionado())
                menu.addSeparator()
                menu.addAction("📋 Copiar Links", lambda: self.mostrar_opcoes_link(item_data))
        
        # Mostrar menu apenas se há opções
        if menu.actions():
            menu.exec_(self.lista.mapToGlobal(pos))

    def verificar_selecao(self):
        """Verifica se há itens selecionados e atualiza o estado dos botões"""
        has_selected = False
        all_selected = True
        total_items = 0
        
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.flags() & Qt.ItemIsSelectable:  # Ignorar separadores
                total_items += 1
                widget = self.lista.itemWidget(item)
                if widget:
                    for child in widget.findChildren(QCheckBox):
                        if child.isChecked():
                            has_selected = True
                        else:
                            all_selected = False
                        break
        
        # Atualizar estado dos botões
        if total_items > 0:
            self.btn_selecionar_todos.setEnabled(not all_selected)
            self.btn_desmarcar_todos.setEnabled(has_selected)
        else:
            self.btn_selecionar_todos.setEnabled(False)
            self.btn_desmarcar_todos.setEnabled(False)

    def selecionar_todos(self):
        """Marca todas as caixas de seleção"""
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.flags() & Qt.ItemIsSelectable:  # Ignorar separadores
                widget = self.lista.itemWidget(item)
                if widget:
                    for child in widget.findChildren(QCheckBox):
                        child.setChecked(True)
        self.verificar_selecao()

    def desmarcar_todos(self):
        """Desmarca todas as caixas de seleção"""
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.flags() & Qt.ItemIsSelectable:  # Ignorar separadores
                widget = self.lista.itemWidget(item)
                if widget:
                    for child in widget.findChildren(QCheckBox):
                        child.setChecked(False)
        self.verificar_selecao()

    def selecionar_estrela(self, estrelas, idx):
        """Atualiza a seleção de estrelas"""
        for i, estrela in enumerate(estrelas):
            if i <= idx:
                estrela.setText("★")
                estrela.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        font-size: 20px;
                        color: #ffd700;
                    }
                    QPushButton:hover {
                        color: #ffed4e;
                    }
                """)
            else:
                estrela.setText("☆")
                estrela.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        font-size: 20px;
                        color: #666;
                    }
                    QPushButton:hover {
                        color: #ffd700;
                    }
                """)
        # Armazenar a nota selecionada (1-5)
        self.nota_atual = idx + 1

if __name__ == '__main__':
    from PyQt5.QtWidgets import QSplashScreen
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont
    from splash_screen import SplashScreen

    app = QApplication(sys.argv)

    # Criar e mostrar a nova splash screen
    splash = SplashScreen()
    splash.show()
    
    # Simular carregamento com textos personalizados para o app de downloads
    def simulate_loading():
        splash.update_progress(10, "Inicializando sistema...")
        QTimer.singleShot(200, lambda: splash.update_progress(25, "Carregando módulos de download..."))
        QTimer.singleShot(400, lambda: splash.update_progress(40, "Configurando interface..."))
        QTimer.singleShot(600, lambda: splash.update_progress(60, "Preparando gerenciador de arquivos..."))
        QTimer.singleShot(800, lambda: splash.update_progress(80, "Inicializando sistema de busca..."))
        QTimer.singleShot(1000, lambda: splash.update_progress(90, "Carregando tema escuro..."))
        QTimer.singleShot(1200, lambda: splash.update_progress(100, "Pronto!"))

    # Iniciar simulação de carregamento
    simulate_loading()

    def start_main():
        try:
            global main_window
            main_window = JsonEditorApp()
            main_window.show()
        except Exception as e:
            import traceback
            print('Erro ao iniciar a janela principal:', e)
            print(traceback.format_exc())
    
    # Fechar splash e abrir janela principal após 2.5 segundos
    QTimer.singleShot(2500, splash.close)
    QTimer.singleShot(2500, start_main)

    sys.exit(app.exec_())
