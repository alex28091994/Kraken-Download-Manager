import sys
from PyQt5.QtWidgets import (QApplication, QSplashScreen, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QProgressBar, QFrame)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QFont, QPainter, QColor

class SplashScreen(QSplashScreen):
    def __init__(self):
        # Criar um pixmap com o design da splash screen
        pixmap = QPixmap(1200, 700)
        pixmap.fill(QColor('#051821'))  # Fundo escuro
        
        # Desenhar o design da splash screen
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Lado esquerdo (escuro)
        left_rect = painter.viewport()
        left_rect.setWidth(600)
        
        # Logo (círculo laranja)
        painter.setBrush(QColor('#FF8C00'))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(50, 50, 80, 80)
        
        # Nome do app
        painter.setPen(QColor('#FF8C00'))
        font = QFont('Segoe UI', 36, QFont.Bold)
        painter.setFont(font)
        painter.drawText(50, 180, "SuperBase")
        
        # Copyright e versão
        font.setPointSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor('#666666'))
        painter.drawText(50, 600, "© 2025 Todos os direitos reservados a Dev Prieto.")
        painter.drawText(50, 620, "Versão 1.5.1")
        
        # Lado direito (claro)
        painter.fillRect(600, 0, 600, 700, QColor('#FFFFFF'))
        
        # Título
        painter.setPen(QColor('#333333'))
        font.setPointSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(650, 200, "Bem-vindo ao SuperBase")
        
        # Subtítulo
        font.setPointSize(16)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor('#666666'))
        painter.drawText(650, 240, " Gerenciamento de Downloads ")
        
        # Barra de progresso (esboço)
        painter.setPen(QColor('#E0E0E0'))
        painter.setBrush(QColor('#F5F5F5'))
        painter.drawRoundedRect(650, 350, 500, 20, 10, 10)
        
        # Status inicial
        font.setPointSize(12)
        painter.setFont(font)
        painter.setPen(QColor('#666666'))
        painter.drawText(650, 390, "Inicializando...")
        
        painter.end()
        
        super().__init__(pixmap)
        self.setWindowFlag(Qt.FramelessWindowHint)
        
        # Variáveis para controle de progresso
        self.progress_value = 0
        self.status_text = "Inicializando..."
        
    def update_progress(self, value, status):
        self.progress_value = value
        self.status_text = status

        # Criar um novo pixmap limpo
        pixmap = QPixmap(1200, 700)
        pixmap.fill(QColor('#051821'))  # Fundo escuro
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Lado esquerdo (escuro)
        left_rect = painter.viewport()
        left_rect.setWidth(600)

        # Logo (círculo laranja)
        painter.setBrush(QColor('#FF8C00'))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(50, 50, 80, 80)

        # Nome do app
        painter.setPen(QColor('#FF8C00'))
        font = QFont('Segoe UI', 36, QFont.Bold)
        painter.setFont(font)
        painter.drawText(50, 180, "SuperBase")

        # Copyright e versão
        font.setPointSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor('#666666'))
        painter.drawText(50, 600, "© 2025 Todos os direitos reservados a Dev Prieto.")
        painter.drawText(50, 620, "Versão 1.2.1")

        # Lado direito (claro)
        painter.fillRect(600, 0, 600, 700, QColor('#FFFFFF'))

        # Título
        painter.setPen(QColor('#333333'))
        font.setPointSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(650, 200, "Bem-vindo ao SuperBase")

        # Subtítulo
        font.setPointSize(16)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor('#666666'))
        painter.drawText(650, 240, "Gerenciamento de Downloads")

        # Barra de progresso (fundo)
        painter.setPen(QColor('#E0E0E0'))
        painter.setBrush(QColor('#F5F5F5'))
        painter.drawRoundedRect(650, 350, 500, 20, 10, 10)

        # Barra de progresso (preenchimento)
        if value > 0:
            progress_width = int((value / 100) * 500)
            painter.setPen(QColor('#FF8C00'))
            painter.setBrush(QColor('#FF8C00'))
            painter.drawRoundedRect(650, 350, progress_width, 20, 10, 10)

        # Status
        font.setPointSize(12)
        painter.setFont(font)
        painter.setPen(QColor('#666666'))
        painter.drawText(650, 390, status)

        painter.end()
        self.setPixmap(pixmap)
        QApplication.processEvents()

# Exemplo de uso
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Criar splash screen
    splash = SplashScreen()
    splash.show()
    
    # Simular carregamento
    import time
    
    for i in range(101):
        if i < 30:
            status = "Carregando módulos..."
        elif i < 60:
            status = "Conectando ao banco de dados..."
        elif i < 90:
            status = "Inicializando interface..."
        else:
            status = "Pronto!"
        
        splash.update_progress(i, status)
        time.sleep(0.05)  # Simular tempo de carregamento
    
    # Fechar splash após 1 segundo
    QTimer.singleShot(1000, splash.close)
    
    sys.exit(app.exec_()) 
