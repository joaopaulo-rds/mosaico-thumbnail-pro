import os
import sys
from PySide6.QtCore import Qt, QSize, Slot, QThread, Signal
from PySide6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QComboBox,
    QCheckBox, QFileDialog, QProgressBar, QGroupBox, QFrame, QMessageBox,
    QAbstractItemView, QProgressDialog
)

from utils import (
    check_ffmpeg_installed, download_and_extract_ffmpeg,
    format_bytes, format_seconds, SUPPORTED_EXTENSIONS, get_resource_path
)
from processor import WorkerThread, probe_video

DARK_STYLESHEET = """
QMainWindow {
    background-color: #181825;
}
QWidget {
    background-color: #181825;
    color: #CDD6F4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QFrame#card {
    background-color: #1E1E2E;
    border: 1px solid #313244;
    border-radius: 8px;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #45475A;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
    background-color: #1E1E2E;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #89B4FA;
}
QPushButton {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #45475A;
    border-color: #585B70;
}
QPushButton:pressed {
    background-color: #585B70;
}
QPushButton#primaryBtn {
    background-color: #89B4FA;
    color: #11111B;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #B4BEFE;
}
QPushButton#dangerBtn {
    background-color: #F38BA8;
    color: #11111B;
    border: none;
}
QPushButton#dangerBtn:hover {
    background-color: #EBA0AC;
}
QPushButton:disabled {
    background-color: #181825;
    color: #6C7086;
    border-color: #313244;
}
QTableWidget {
    background-color: #181825;
    border: 1px solid #313244;
    gridline-color: #313244;
    border-radius: 6px;
    selection-background-color: #313244;
    selection-color: #CDD6F4;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #1E1E2E;
    color: #A6ADC8;
    padding: 8px;
    border: 1px solid #313244;
    font-weight: bold;
}
QComboBox, QLineEdit {
    background-color: #313244;
    border: 1px solid #45475A;
    border-radius: 6px;
    padding: 6px 12px;
    color: #CDD6F4;
}
QComboBox:hover {
    border-color: #89B4FA;
}
QComboBox::drop-down {
    border: none;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #45475A;
    background-color: #313244;
}
QCheckBox::indicator:checked {
    background-color: #89B4FA;
    border-color: #89B4FA;
}
QProgressBar {
    border: 1px solid #45475A;
    border-radius: 6px;
    text-align: center;
    background-color: #313244;
    color: #11111B;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #A6E3A1;
    border-radius: 5px;
}
"""

class FFmpegDownloaderThread(QThread):
    progress_signal = Signal(int, str)
    finished_signal = Signal(bool, str)

    def run(self):
        try:
            def cb(pct, msg):
                self.progress_signal.emit(pct, msg)

            success = download_and_extract_ffmpeg(progress_callback=cb)
            if success:
                self.finished_signal.emit(True, "FFmpeg instalado e configurado com sucesso!")
            else:
                self.finished_signal.emit(False, "Não foi possível extrair os executáveis do FFmpeg.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mosaico Thumbnail Pro - Gerador & Conversor (.MP4)")
        self.resize(1150, 740)
        self.setMinimumSize(950, 620)
        
        self.setStyleSheet(DARK_STYLESHEET)
        self.setAcceptDrops(True)
        
        icon_path = get_resource_path("icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.queue = []
        self.worker = None
        self.downloader_thread = None
        self.is_paused = False
        
        self.init_ui()
        self.check_ffmpeg()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(18, 18, 18, 18)
        
        top_card = QFrame()
        top_card.setObjectName("card")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(15, 12, 15, 12)
        
        title_label = QLabel("🎬 MOSAICO THUMBNAIL PRO")
        title_font = QFont("Segoe UI", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #89B4FA;")
        
        sub_label = QLabel("Gere mosaicos de miniaturas, converta vídeos para MP4 e embuta capas automaticamente.")
        sub_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")
        
        title_vbox = QVBoxLayout()
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(sub_label)
        
        top_layout.addLayout(title_vbox)
        top_layout.addStretch()
        
        layout.addWidget(top_card)

        settings_group = QGroupBox("⚙️ Configurações e Desempenho (25-30% CPU / GPU Turbo)")
        settings_layout = QHBoxLayout(settings_group)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(20)
        
        grid_lbl = QLabel("Grade do Mosaico:")
        self.grid_combo = QComboBox()
        self.grid_combo.addItems([
            "6 x 4 (24 miniaturas - Padrão)",
            "4 x 4 (16 miniaturas)",
            "5 x 4 (20 miniaturas)",
            "6 x 5 (30 miniaturas)",
            "6 x 6 (36 miniaturas)",
            "5 x 5 (25 miniaturas)",
            "3 x 3 (9 miniaturas)",
            "2 x 2 (4 miniaturas)"
        ])
        self.grid_combo.setCurrentIndex(0)
        
        grid_hbox = QHBoxLayout()
        grid_hbox.addWidget(grid_lbl)
        grid_hbox.addWidget(self.grid_combo)
        settings_layout.addLayout(grid_hbox)

        self.compress_cb = QCheckBox("Compressão Adicional (H.264 CRF 24)")
        self.compress_cb.setChecked(True)
        self.compress_cb.setToolTip("Compacta o arquivo reduzindo tamanho. Se desativado, converte mantendo taxa original.")
        settings_layout.addWidget(self.compress_cb)

        self.save_jpg_cb = QCheckBox("Salvar Imagem Mosaico (.jpg)")
        self.save_jpg_cb.setChecked(False)
        self.save_jpg_cb.setToolTip("Salva a imagem do mosaico junto ao vídeo além de embuti-la como capa.")
        settings_layout.addWidget(self.save_jpg_cb)

        self.output_dir_btn = QPushButton("Pasta do Mosaico: (Mesma do vídeo)")
        self.output_dir_btn.clicked.connect(self.select_output_directory)
        self.custom_mosaic_dir = None
        settings_layout.addWidget(self.output_dir_btn)

        layout.addWidget(settings_group)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.add_files_btn = QPushButton("📁 Adicionar Arquivos")
        self.add_files_btn.clicked.connect(self.add_files_dialog)
        
        self.add_folder_btn = QPushButton("📂 Adicionar Pasta")
        self.add_folder_btn.clicked.connect(self.add_folder_dialog)

        self.start_btn = QPushButton("▶️ Iniciar Fila")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.clicked.connect(self.start_queue)

        self.pause_btn = QPushButton("⏸️ Pausar")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause)

        self.cancel_btn = QPushButton("🛑 Cancelar")
        self.cancel_btn.setObjectName("dangerBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_queue)

        self.clear_btn = QPushButton("🧹 Limpar Fila")
        self.clear_btn.clicked.connect(self.clear_queue)

        btn_layout.addWidget(self.add_files_btn)
        btn_layout.addWidget(self.add_folder_btn)
        btn_layout.addSpacing(15)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Status / ETA", "Nome do Arquivo", "Duração", "Resolução", "Tamanho", "Progresso"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 180)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        layout.addWidget(self.table)

        bottom_card = QFrame()
        bottom_card.setObjectName("card")
        bottom_layout = QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(12, 10, 12, 10)

        self.status_label = QLabel("Arraste e solte vídeos (.ts, .mp4, .mkv, .avi, etc) para começar.")
        self.status_label.setStyleSheet("color: #A6ADC8; font-weight: 500;")

        self.overall_progress = QProgressBar()
        self.overall_progress.setValue(0)
        self.overall_progress.setFixedHeight(14)
        self.overall_progress.setTextVisible(False)

        bottom_layout.addWidget(self.status_label)
        bottom_layout.addWidget(self.overall_progress)

        layout.addWidget(bottom_card)

    def check_ffmpeg(self):
        if not check_ffmpeg_installed():
            reply = QMessageBox.question(
                self,
                "FFmpeg Não Encontrado",
                "O motor de vídeo FFmpeg não foi encontrado no seu computador.\n\n"
                "Deseja que o aplicativo BAIXE E INSTALE O FFMPEG AUTOMATICAMENTE agora?\n"
                "(É rápido e totalmente automático!)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.start_ffmpeg_auto_download()

    def start_ffmpeg_auto_download(self):
        self.progress_dialog = QProgressDialog("Iniciando download do FFmpeg...", "Cancelar", 0, 100, self)
        self.progress_dialog.setWindowTitle("Instalador Automático do FFmpeg")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setMinimumDuration(0)

        self.downloader_thread = FFmpegDownloaderThread()
        self.downloader_thread.progress_signal.connect(self.on_download_progress)
        self.downloader_thread.finished_signal.connect(self.on_download_finished)
        self.downloader_thread.start()

    @Slot(int, str)
    def on_download_progress(self, pct, msg):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setValue(pct)
            self.progress_dialog.setLabelText(msg)
        self.status_label.setText(f"[FFmpeg Auto-Setup] {msg}")

    @Slot(bool, str)
    def on_download_finished(self, success, msg):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            
        if success:
            QMessageBox.information(
                self,
                "FFmpeg Instalado!",
                "O FFmpeg foi baixado e configurado com sucesso na pasta do aplicativo!\n\n"
                "Agora o aplicativo está 100% pronto para uso."
            )
            self.status_label.setText("FFmpeg pronto para uso. Adicione seus vídeos para começar.")
        else:
            QMessageBox.critical(
                self,
                "Erro no Download",
                f"Não foi possível baixar o FFmpeg automaticamente:\n{msg}\n\n"
                "Verifique sua conexão com a internet ou coloque o ffmpeg.exe manualmente na pasta do app."
            )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]
        self.process_added_paths(paths)

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar Vídeos",
            "",
            "Todos os Vídeos Suportados (*.ts *.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m2ts *.mts *.vob *.3gp *.mpg *.mpeg *.m4v);;Arquivos de Vídeo TS (*.ts *.m2ts *.mts);;Arquivos MP4 (*.mp4);;Todos os Arquivos (*.*)"
        )
        if files:
            self.process_added_paths(files)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta com Vídeos")
        if folder:
            self.process_added_paths([folder])

    def select_output_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Salvar Imagens Mosaico")
        if folder:
            self.custom_mosaic_dir = folder
            self.output_dir_btn.setText(f"Pasta do Mosaico: {os.path.basename(folder)}")
        else:
            self.custom_mosaic_dir = None
            self.output_dir_btn.setText("Pasta do Mosaico: (Mesma do vídeo)")

    def process_added_paths(self, paths):
        added_count = 0
        for p in paths:
            if os.path.isfile(p):
                if p.lower().endswith(SUPPORTED_EXTENSIONS):
                    self.add_video_to_table(p)
                    added_count += 1
            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith(SUPPORTED_EXTENSIONS):
                            full_p = os.path.join(root, f)
                            self.add_video_to_table(full_p)
                            added_count += 1
                            
        self.status_label.setText(f"{added_count} vídeo(s) adicionado(s) à fila.")

    def add_video_to_table(self, video_path):
        for item in self.queue:
            if item["path"] == video_path:
                return

        row = self.table.rowCount()
        self.table.insertRow(row)

        status_item = QTableWidgetItem("⏳ Pendente")
        status_item.setForeground(QColor("#F9E2AF"))
        self.table.setItem(row, 0, status_item)

        name_item = QTableWidgetItem(os.path.basename(video_path))
        name_item.setToolTip(video_path)
        self.table.setItem(row, 1, name_item)

        meta = probe_video(video_path)
        
        dur_item = QTableWidgetItem(format_seconds(meta["duration"]))
        self.table.setItem(row, 2, dur_item)

        res_item = QTableWidgetItem(f'{meta["width"]}x{meta["height"]}')
        self.table.setItem(row, 3, res_item)

        size_item = QTableWidgetItem(format_bytes(meta["size"]))
        self.table.setItem(row, 4, size_item)

        pbar = QProgressBar()
        pbar.setValue(0)
        pbar.setFixedHeight(18)
        pbar.setTextVisible(True)
        pbar.setStyleSheet("QProgressBar { color: #11111B; font-weight: bold; }")
        self.table.setCellWidget(row, 5, pbar)

        self.queue.append({
            "path": video_path,
            "status": "Pendente",
            "row": row
        })

    def get_grid_dimensions(self):
        text = self.grid_combo.currentText()
        try:
            grid_part = text.split("(")[0].strip()
            parts = grid_part.split("x")
            rows = int(parts[0].strip())
            cols = int(parts[1].strip())
            return rows, cols
        except Exception:
            return 6, 4

    def start_queue(self):
        if not check_ffmpeg_installed():
            self.check_ffmpeg()
            return

        pending_items = [item for item in self.queue if item["status"] in ("Pendente", "Erro", "Cancelado")]
        if not pending_items:
            QMessageBox.information(self, "Fila Vazia", "Não há vídeos pendentes para processar na fila.")
            return

        settings = {
            "rows": self.get_grid_dimensions()[0],
            "cols": self.get_grid_dimensions()[1],
            "compress": self.compress_cb.isChecked(),
            "save_mosaic": self.save_jpg_cb.isChecked(),
            "mosaic_dir": self.custom_mosaic_dir
        }

        self.worker = WorkerThread(pending_items, settings)
        self.worker.item_started.connect(self.on_item_started)
        self.worker.item_progress.connect(self.on_item_progress)
        self.worker.item_finished.connect(self.on_item_finished)
        self.worker.queue_completed.connect(self.on_queue_completed)

        self.worker.start()

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.add_files_btn.setEnabled(False)
        self.add_folder_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.status_label.setText("Processando fila de vídeos em segundo plano...")

    def toggle_pause(self):
        if not self.worker:
            return
        if self.is_paused:
            self.worker.resume()
            self.is_paused = False
            self.pause_btn.setText("⏸️ Pausar")
            self.status_label.setText("Processamento retomado.")
        else:
            self.worker.pause()
            self.is_paused = True
            self.pause_btn.setText("▶️ Retomar")
            self.status_label.setText("Processamento pausado.")

    def cancel_queue(self):
        if self.worker:
            self.status_label.setText("Cancelando operação...")
            self.worker.cancel()

    def clear_queue(self):
        self.table.setRowCount(0)
        self.queue.clear()
        self.overall_progress.setValue(0)
        self.status_label.setText("Fila limpa com sucesso.")

    @Slot(str)
    def on_item_started(self, file_path):
        for item in self.queue:
            if item["path"] == file_path:
                item["status"] = "Processando"
                row = item["row"]
                status_item = self.table.item(row, 0)
                status_item.setText("🔄 Processando...")
                status_item.setForeground(QColor("#89B4FA"))
                break

    @Slot(str, int, str, int, int, int, int)
    def on_item_progress(self, file_path, pct, status_text, item_eta_sec, total_queue_eta_sec, item_index, total_items):
        for item in self.queue:
            if item["path"] == file_path:
                row = item["row"]
                pbar = self.table.cellWidget(row, 5)
                if pbar:
                    pbar.setValue(pct)
                    
                status_item = self.table.item(row, 0)
                item_eta_str = format_seconds(item_eta_sec)
                status_item.setText(f"🔄 Processando ({item_eta_str})")
                
                queue_eta_str = format_seconds(total_queue_eta_sec)
                filename = os.path.basename(file_path)
                disp_name = filename if len(filename) <= 30 else filename[:27] + "..."
                
                # PRIMEIRO: Contador da Fila ("📊 Vídeos: 1/20") no início da Barra de Status
                self.status_label.setText(
                    f"📊 Vídeos: {item_index}/{total_items}  |  ⏱️ Restante do Vídeo: {item_eta_str}  |  ⏳ Restante da Fila: {queue_eta_str}  |  [{disp_name}] {status_text}"
                )
                break

    @Slot(str, bool, str)
    def on_item_finished(self, file_path, success, message):
        for item in self.queue:
            if item["path"] == file_path or os.path.splitext(item["path"])[0] == os.path.splitext(file_path)[0]:
                row = item["row"]
                status_item = self.table.item(row, 0)
                pbar = self.table.cellWidget(row, 5)
                
                if success:
                    item["status"] = "Concluído"
                    status_item.setText("✅ Concluído")
                    status_item.setForeground(QColor("#A6E3A1"))
                    if pbar:
                        pbar.setValue(100)
                else:
                    item["status"] = "Erro" if message != "Cancelado" else "Cancelado"
                    status_item.setText("❌ Erro" if message != "Cancelado" else "🛑 Cancelado")
                    status_item.setForeground(QColor("#F38BA8") if message != "Cancelado" else QColor("#FAB387"))
                    status_item.setToolTip(message)
                break
                
        completed_count = sum(1 for i in self.queue if i["status"] in ("Concluído", "Erro", "Cancelado"))
        total = len(self.queue)
        if total > 0:
            self.overall_progress.setValue(int((completed_count / total) * 100))

    @Slot(dict)
    def on_queue_completed(self, summary_data):
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸️ Pausar")
        self.cancel_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.is_paused = False
        
        total_items = summary_data.get("total_items", 0)
        success_count = summary_data.get("success_count", 0)
        error_count = summary_data.get("error_count", 0)
        elapsed_sec = summary_data.get("total_elapsed_sec", 0)
        init_bytes = summary_data.get("total_initial_bytes", 0)
        final_bytes = summary_data.get("total_final_bytes", 0)
        
        self.status_label.setText(f"Processamento concluído! ({success_count}/{total_items} vídeos processados com sucesso)")
        
        elapsed_str = format_seconds(elapsed_sec)
        diff_bytes = init_bytes - final_bytes
        
        if init_bytes > 0 and final_bytes > 0:
            if diff_bytes > 0:
                pct_saved = (diff_bytes / init_bytes) * 100
                space_info = f"🎉 Economia Total de Espaço: {format_bytes(diff_bytes)} ({pct_saved:.1f}% de redução de tamanho)"
            elif diff_bytes < 0:
                inc_bytes = abs(diff_bytes)
                pct_inc = (inc_bytes / init_bytes) * 100
                space_info = f"📈 Aumento Total no Tamanho: {format_bytes(inc_bytes)} (+{pct_inc:.1f}% devido à conversão para MP4)"
            else:
                space_info = "⚡ Tamanho Total Mantido (sem alteração de peso)"
        else:
            space_info = "Sem dados de tamanho acumulados."
            
        error_details = ""
        if error_count > 0 and summary_data.get("error_list"):
            error_details = "\n\n⚠️ Vídeos que apresentaram erro:\n"
            for err_file, err_msg in summary_data["error_list"][:5]:
                error_details += f" • {err_file}: {err_msg}\n"
            if len(summary_data["error_list"]) > 5:
                error_details += f" ... e mais {len(summary_data['error_list']) - 5} erro(s)."

        msg = (
            f"✅ Processamento da Fila Concluído!\n\n"
            f"📊 Estatísticas Detalhadas do Lote:\n"
            f"--------------------------------------------------\n"
            f"• Total de Vídeos na Lista: {total_items}\n"
            f"• Concluídos com Sucesso: {success_count} vídeo(s)\n"
            f"• Vídeos com Erro / Falha: {error_count}\n"
            f"• Tempo Total Decorrido: {elapsed_str}\n\n"
            f"💾 Comparativo de Espaço em Disco:\n"
            f"• Tamanho Total Inicial: {format_bytes(init_bytes)}\n"
            f"• Tamanho Total Final: {format_bytes(final_bytes)}\n"
            f"• {space_info}"
            f"{error_details}"
        )
        
        QMessageBox.information(
            self,
            "Resumo Geral da Fila",
            msg
        )
