import os
import sys
from PySide6.QtCore import Qt, QSize, Slot, QThread, Signal
from PySide6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QComboBox,
    QCheckBox, QFileDialog, QProgressBar, QGroupBox, QFrame, QMessageBox,
    QAbstractItemView, QProgressDialog, QTabWidget, QSpinBox
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
QPushButton#skipBtn {
    background-color: #FAB387;
    color: #11111B;
    border: none;
}
QPushButton#skipBtn:hover {
    background-color: #F9E2AF;
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
QSpinBox {
    background-color: #313244;
    border: 1px solid #45475A;
    border-radius: 6px;
    padding: 5px 8px;
    color: #CDD6F4;
    font-weight: bold;
}
QSpinBox:hover {
    border-color: #89B4FA;
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
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #181825;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #1E1E2E;
    color: #A6ADC8;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: bold;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background-color: #181825;
    color: #89B4FA;
    border-color: #45475A;
    border-bottom: 2px solid #89B4FA;
}
QTabBar::tab:hover:!selected {
    background-color: #313244;
    color: #CDD6F4;
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


class QueueTabWidget(QWidget):
    """Aba individual com fila própria e ciclo de processamento independente."""
    def __init__(self, mode="mp4", main_window=None, parent=None):
        super().__init__(parent)
        self.mode = mode # "mp4", "mkv", or "mosaic_only"
        self.main_window = main_window
        self.queue = []
        self.worker = None
        self.is_paused = False
        self.custom_mosaic_dir = None
        
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. Configurações Específicas do Modo
        if self.mode == "mp4":
            settings_group = QGroupBox("⚙️ Configurações de Conversão para MP4 (H.264 / AAC + Capa Embutida)")
        elif self.mode == "mkv":
            settings_group = QGroupBox("⚙️ Configurações de Conversão para MKV (Matroska / AAC + Capa Embutida)")
        else:
            settings_group = QGroupBox("⚙️ Configurações da Folha de Mosaico (Gera apenas a imagem - Sem alterar os vídeos)")
            
        settings_layout = QHBoxLayout(settings_group)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(15)

        # Controles de Grade
        grid_lbl = QLabel("Grade:")
        self.grid_combo = QComboBox()
        self.grid_combo.addItems([
            "6 x 4 (24 miniaturas - Padrão)",
            "4 x 4 (16 miniaturas)",
            "5 x 4 (20 miniaturas)",
            "6 x 5 (30 miniaturas)",
            "6 x 6 (36 miniaturas)",
            "5 x 5 (25 miniaturas)",
            "3 x 3 (9 miniaturas)",
            "2 x 2 (4 miniaturas)",
            "Personalizada (Definir ao lado)"
        ])
        self.grid_combo.setCurrentIndex(0)
        self.grid_combo.currentTextChanged.connect(self.on_grid_preset_changed)

        grid_hbox = QHBoxLayout()
        grid_hbox.addWidget(grid_lbl)
        grid_hbox.addWidget(self.grid_combo)
        settings_layout.addLayout(grid_hbox)

        # Se for o modo de apenas mosaico, expõe spinboxes de Linhas e Colunas
        if self.mode == "mosaic_only":
            col_lbl = QLabel("Colunas:")
            self.cols_spin = QSpinBox()
            self.cols_spin.setRange(1, 10)
            self.cols_spin.setValue(4)
            self.cols_spin.setToolTip("Número de colunas de miniaturas (1 a 10)")
            self.cols_spin.valueChanged.connect(self.on_spin_changed)

            row_lbl = QLabel("Linhas:")
            self.rows_spin = QSpinBox()
            self.rows_spin.setRange(1, 15)
            self.rows_spin.setValue(6)
            self.rows_spin.setToolTip("Número de linhas de miniaturas (1 a 15)")
            self.rows_spin.valueChanged.connect(self.on_spin_changed)

            spin_hbox = QHBoxLayout()
            spin_hbox.addWidget(col_lbl)
            spin_hbox.addWidget(self.cols_spin)
            spin_hbox.addWidget(row_lbl)
            spin_hbox.addWidget(self.rows_spin)
            settings_layout.addLayout(spin_hbox)

            # Formato da imagem (JPEG / PNG)
            fmt_lbl = QLabel("Formato:")
            self.img_fmt_combo = QComboBox()
            self.img_fmt_combo.addItems([
                "JPEG (.jpg) - Recomendado",
                "PNG (.png) - Sem Perdas"
            ])
            self.img_fmt_combo.setToolTip("Escolha o formato de arquivo para a imagem mosaico gerada.")
            fmt_hbox = QHBoxLayout()
            fmt_hbox.addWidget(fmt_lbl)
            fmt_hbox.addWidget(self.img_fmt_combo)
            settings_layout.addLayout(fmt_hbox)

            # Opção de conflito de arquivo (Sobrescrever / Numerar)
            conflict_lbl = QLabel("Se existir:")
            self.conflict_combo = QComboBox()
            self.conflict_combo.addItems([
                "Sobrescrever (Padrão)",
                "Numerar (_1, _2...)"
            ])
            self.conflict_combo.setToolTip("Define se sobrescreve a imagem anterior ou cria cópia com numeração caso já exista.")
            conflict_hbox = QHBoxLayout()
            conflict_hbox.addWidget(conflict_lbl)
            conflict_hbox.addWidget(self.conflict_combo)
            settings_layout.addLayout(conflict_hbox)

        else:
            # Configurações para conversão (MP4 e MKV)
            self.compress_cb = QCheckBox("Compressão Adicional (CRF 24)")
            self.compress_cb.setChecked(True)
            self.compress_cb.setToolTip("Aplica compactação inteligente reduzindo o tamanho em disco mantendo excelente qualidade visual.")
            settings_layout.addWidget(self.compress_cb)

            self.save_jpg_cb = QCheckBox("Salvar Imagem Mosaico (.jpg)")
            self.save_jpg_cb.setChecked(False)
            self.save_jpg_cb.setToolTip("Salva uma cópia da imagem do mosaico junto ao vídeo na pasta, além de embutir no arquivo.")
            settings_layout.addWidget(self.save_jpg_cb)

        # Botão de Pasta de Saída
        pasta_btn_text = "Pasta da Imagem: (Mesma do vídeo)" if self.mode == "mosaic_only" else "Pasta do Mosaico: (Mesma do vídeo)"
        self.output_dir_btn = QPushButton(pasta_btn_text)
        self.output_dir_btn.clicked.connect(self.select_output_directory)
        settings_layout.addWidget(self.output_dir_btn)

        layout.addWidget(settings_group)

        # 2. Barra de Botões de Ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.add_files_btn = QPushButton("📁 Adicionar Arquivos")
        self.add_files_btn.clicked.connect(self.add_files_dialog)
        
        self.add_folder_btn = QPushButton("📂 Adicionar Pasta")
        self.add_folder_btn.clicked.connect(self.add_folder_dialog)

        if self.mode == "mp4":
            start_text = "▶️ Iniciar Fila (MP4)"
        elif self.mode == "mkv":
            start_text = "▶️ Iniciar Fila (MKV)"
        else:
            start_text = "🖼️ Gerar Mosaicos"

        self.start_btn = QPushButton(start_text)
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.clicked.connect(self.start_queue)

        self.pause_btn = QPushButton("⏸️ Pausar")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause)

        self.skip_btn = QPushButton("⏭️ Pular Vídeo")
        self.skip_btn.setObjectName("skipBtn")
        self.skip_btn.setEnabled(False)
        self.skip_btn.setToolTip("Pula imediatamente o vídeo atual que estiver travado ou demorando e avança para o próximo da fila.")
        self.skip_btn.clicked.connect(self.skip_current_video)

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
        btn_layout.addWidget(self.skip_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        # 3. Tabela de Vídeos da Fila
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

        # 4. Cartão Inferior com Barra de Status e Progresso Geral
        bottom_card = QFrame()
        bottom_card.setObjectName("card")
        bottom_layout = QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(12, 10, 12, 10)

        default_status = "Arraste e solte vídeos (.ts, .mp4, .mkv, .avi, etc) para começar."
        self.status_label = QLabel(default_status)
        self.status_label.setStyleSheet("color: #A6ADC8; font-weight: 500;")

        self.overall_progress = QProgressBar()
        self.overall_progress.setValue(0)
        self.overall_progress.setFixedHeight(14)
        self.overall_progress.setTextVisible(False)

        bottom_layout.addWidget(self.status_label)
        bottom_layout.addWidget(self.overall_progress)
        layout.addWidget(bottom_card)

    def on_grid_preset_changed(self, text):
        if "x" in text and hasattr(self, 'rows_spin') and hasattr(self, 'cols_spin'):
            try:
                parts = text.split("(")[0].strip().split("x")
                r = int(parts[0].strip())
                c = int(parts[1].strip())
                self.rows_spin.blockSignals(True)
                self.cols_spin.blockSignals(True)
                self.rows_spin.setValue(r)
                self.cols_spin.setValue(c)
                self.rows_spin.blockSignals(False)
                self.cols_spin.blockSignals(False)
            except Exception:
                pass

    def on_spin_changed(self):
        if hasattr(self, 'rows_spin') and hasattr(self, 'cols_spin'):
            r = self.rows_spin.value()
            c = self.cols_spin.value()
            found = False
            for i in range(self.grid_combo.count()):
                txt = self.grid_combo.itemText(i)
                if txt.startswith(f"{r} x {c}") or txt.startswith(f"{r}x{c}"):
                    self.grid_combo.blockSignals(True)
                    self.grid_combo.setCurrentIndex(i)
                    self.grid_combo.blockSignals(False)
                    found = True
                    break
            if not found:
                for i in range(self.grid_combo.count()):
                    if "Personalizada" in self.grid_combo.itemText(i):
                        self.grid_combo.blockSignals(True)
                        self.grid_combo.setCurrentIndex(i)
                        self.grid_combo.blockSignals(False)
                        break

    def get_grid_dimensions(self):
        if self.mode == "mosaic_only" and hasattr(self, 'rows_spin') and hasattr(self, 'cols_spin'):
            return self.rows_spin.value(), self.cols_spin.value()
        text = self.grid_combo.currentText()
        try:
            grid_part = text.split("(")[0].strip()
            parts = grid_part.split("x")
            rows = int(parts[0].strip())
            cols = int(parts[1].strip())
            return rows, cols
        except Exception:
            return 6, 4

    def select_output_directory(self):
        dir_selected = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino")
        if dir_selected:
            self.custom_mosaic_dir = dir_selected
            disp = dir_selected if len(dir_selected) <= 35 else "..." + dir_selected[-32:]
            self.output_dir_btn.setText(f"Pasta: {disp}")
        else:
            self.custom_mosaic_dir = None
            pasta_txt = "Pasta da Imagem: (Mesma do vídeo)" if self.mode == "mosaic_only" else "Pasta do Mosaico: (Mesma do vídeo)"
            self.output_dir_btn.setText(pasta_txt)

    def add_files_dialog(self):
        ext_filter = "Vídeos (*" + " *".join(SUPPORTED_EXTENSIONS) + ")"
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Vídeos", "", ext_filter)
        if files:
            for f in files:
                self.add_video_file(f)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta com Vídeos")
        if folder:
            for root, _, files in os.walk(folder):
                for f in sorted(files):
                    if f.lower().endswith(SUPPORTED_EXTENSIONS):
                        self.add_video_file(os.path.join(root, f))

    def add_video_file(self, video_path):
        video_path = os.path.abspath(video_path)
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

    def start_queue(self):
        if not check_ffmpeg_installed():
            if self.main_window:
                self.main_window.check_ffmpeg()
            return

        pending_items = [item for item in self.queue if item["status"] in ("Pendente", "Erro", "Cancelado", "Pulado")]
        if not pending_items:
            QMessageBox.information(self, "Fila Vazia", "Não há vídeos pendentes para processar nesta fila.")
            return

        rows, cols = self.get_grid_dimensions()

        if self.mode == "mosaic_only":
            img_format = "png" if "png" in self.img_fmt_combo.currentText().lower() else "jpg"
            on_conflict = "number" if "numerar" in self.conflict_combo.currentText().lower() else "overwrite"
            settings = {
                "mode": "mosaic_only",
                "rows": rows,
                "cols": cols,
                "image_format": img_format,
                "on_conflict": on_conflict,
                "mosaic_dir": self.custom_mosaic_dir,
                "quality": 95
            }
        else:
            settings = {
                "mode": self.mode,
                "rows": rows,
                "cols": cols,
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
        self.skip_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.add_files_btn.setEnabled(False)
        self.add_folder_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.status_label.setText("Processando fila em segundo plano...")

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

    def skip_current_video(self):
        if self.worker:
            self.status_label.setText("⏭️ Pulando vídeo atual e avançando para o próximo...")
            self.worker.skip_current()

    def cancel_queue(self):
        if self.worker:
            self.status_label.setText("Cancelando operação...")
            self.skip_btn.setEnabled(False)
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
                elif "Pulado" in message:
                    item["status"] = "Pulado"
                    status_item.setText("⏭️ Pulado")
                    status_item.setForeground(QColor("#FAB387"))
                    status_item.setToolTip("Vídeo pulado pelo usuário")
                else:
                    item["status"] = "Erro" if message != "Cancelado" else "Cancelado"
                    status_item.setText("❌ Erro" if message != "Cancelado" else "🛑 Cancelado")
                    status_item.setForeground(QColor("#F38BA8") if message != "Cancelado" else QColor("#FAB387"))
                    status_item.setToolTip(message)
                break
                
        completed_count = sum(1 for i in self.queue if i["status"] in ("Concluído", "Erro", "Cancelado", "Pulado"))
        total = len(self.queue)
        if total > 0:
            self.overall_progress.setValue(int((completed_count / total) * 100))

    @Slot(dict)
    def on_queue_completed(self, summary_data):
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸️ Pausar")
        self.skip_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.is_paused = False
        
        mode = summary_data.get("mode", self.mode)
        total_items = summary_data.get("total_items", 0)
        success_count = summary_data.get("success_count", 0)
        error_count = summary_data.get("error_count", 0)
        elapsed_sec = summary_data.get("total_elapsed_sec", 0)
        init_bytes = summary_data.get("total_initial_bytes", 0)
        final_bytes = summary_data.get("total_final_bytes", 0)
        error_list = summary_data.get("error_list", [])
        
        elapsed_str = format_seconds(elapsed_sec)
        
        if mode == "mosaic_only":
            self.status_label.setText(f"Mosaicos concluídos! ({success_count}/{total_items} imagens geradas com sucesso)")
            
            report_lines = [
                "🖼️ Geração de Imagens Mosaico Concluída!\n",
                f"• Total de Vídeos Selecionados: {total_items}",
                f"• Mosaicos Gerados com Sucesso: {success_count}",
                f"• Vídeos com Erro / Falha: {error_count}",
                f"• Tempo Total Decorrido: {elapsed_str}\n"
            ]
        else:
            fmt_name = mode.upper()
            self.status_label.setText(f"Processamento concluído! ({success_count}/{total_items} vídeos convertidos para {fmt_name})")
            
            diff_bytes = init_bytes - final_bytes
            if init_bytes > 0 and final_bytes > 0:
                if diff_bytes > 0:
                    pct_saved = (diff_bytes / init_bytes) * 100
                    space_info = f"🎉 Economia Total de Espaço: {format_bytes(diff_bytes)} ({pct_saved:.1f}% de redução de tamanho)"
                elif diff_bytes < 0:
                    inc_bytes = abs(diff_bytes)
                    pct_inc = (inc_bytes / init_bytes) * 100
                    space_info = f"📈 Aumento Total no Tamanho: {format_bytes(inc_bytes)} (+{pct_inc:.1f}% devido à conversão para {fmt_name})"
                else:
                    space_info = "⚖️ Tamanho em disco permaneceu praticamente idêntico."
            else:
                space_info = "⚖️ Estatísticas de tamanho indisponíveis."

            report_lines = [
                f"🎬 Processamento da Fila ({fmt_name}) Concluído!\n",
                f"• Total de Vídeos na Lista: {total_items}",
                f"• Concluídos com Sucesso: {success_count} vídeo(s)",
                f"• Vídeos com Erro / Falha: {error_count}",
                f"• Tempo Total Decorrido: {elapsed_str}\n",
                "💽 Comparativo de Espaço em Disco:",
                f"• Tamanho Total Inicial: {format_bytes(init_bytes)}",
                f"• Tamanho Total Final: {format_bytes(final_bytes)}",
                f"• {space_info}\n"
            ]

        if error_list:
            report_lines.append("⚠️ Itens com Erro ou Pulados:")
            for err_file, err_reason in error_list:
                clean_reason = err_reason if len(err_reason) <= 120 else err_reason[:117] + "..."
                report_lines.append(f"  • {err_file}: {clean_reason}")

        full_message = "\n".join(report_lines)
        QMessageBox.information(self, "Resumo Geral da Fila", full_message)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                if file_path.lower().endswith(SUPPORTED_EXTENSIONS):
                    self.add_video_file(file_path)
            elif os.path.isdir(file_path):
                for root, _, files in os.walk(file_path):
                    for f in sorted(files):
                        if f.lower().endswith(SUPPORTED_EXTENSIONS):
                            self.add_video_file(os.path.join(root, f))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mosaico Thumbnail Pro - Conversor MP4/MKV & Gerador de Mosaicos")
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)
        
        self.setStyleSheet(DARK_STYLESHEET)
        
        icon_path = get_resource_path("icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.init_ui()
        self.check_ffmpeg()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 12, 15, 12)
        main_layout.setSpacing(10)

        # Cabeçalho Superior Elegante
        top_card = QFrame()
        top_card.setObjectName("card")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(15, 10, 15, 10)
        
        title_label = QLabel("🎬 MOSAICO THUMBNAIL PRO")
        title_font = QFont("Segoe UI", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #89B4FA;")
        
        sub_label = QLabel("Gere mosaicos de miniaturas, converta vídeos para MP4/MKV com capa embutida ou crie folhas de contato em alta resolução.")
        sub_label.setStyleSheet("color: #A6ADC8; font-size: 12px;")
        
        title_vbox = QVBoxLayout()
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(sub_label)
        
        top_layout.addLayout(title_vbox)
        top_layout.addStretch()
        main_layout.addWidget(top_card)

        # Abas Principais (Estilo oCam / Ferramentas Profissionais)
        self.tab_widget = QTabWidget()
        
        self.tab_mp4 = QueueTabWidget(mode="mp4", main_window=self)
        self.tab_mkv = QueueTabWidget(mode="mkv", main_window=self)
        self.tab_mosaic = QueueTabWidget(mode="mosaic_only", main_window=self)

        self.tab_widget.addTab(self.tab_mp4, "🎬 Converter para MP4")
        self.tab_widget.addTab(self.tab_mkv, "🎞️ Converter para MKV")
        self.tab_widget.addTab(self.tab_mosaic, "🖼️ Apenas Imagem Mosaico")

        main_layout.addWidget(self.tab_widget)

    def check_ffmpeg(self):
        if not check_ffmpeg_installed():
            reply = QMessageBox.question(
                self,
                "Motor FFmpeg Necessário",
                "O FFmpeg e FFprobe não foram encontrados na pasta do aplicativo.\n\n"
                "Deseja fazer o download automático agora (cerca de 30MB)?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.download_ffmpeg()

    def download_ffmpeg(self):
        progress = QProgressDialog("Baixando e configurando motor FFmpeg portátil...", "Cancelar", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.show()

        self.dl_thread = FFmpegDownloaderThread()
        self.dl_thread.progress_signal.connect(lambda p, m: (progress.setValue(p), progress.setLabelText(m)))
        
        def on_finished(success, msg):
            progress.close()
            if success:
                QMessageBox.information(self, "Sucesso", msg)
            else:
                QMessageBox.critical(self, "Falha no Download", f"Erro: {msg}\nBaixe o FFmpeg manualmente e coloque ffmpeg.exe e ffprobe.exe na pasta do aplicativo.")

        self.dl_thread.finished_signal.connect(on_finished)
        self.dl_thread.start()

    def closeEvent(self, event):
        # Verifica se alguma das 3 abas está processando
        busy_tabs = []
        if self.tab_mp4.worker and self.tab_mp4.worker.isRunning():
            busy_tabs.append("MP4")
        if self.tab_mkv.worker and self.tab_mkv.worker.isRunning():
            busy_tabs.append("MKV")
        if self.tab_mosaic.worker and self.tab_mosaic.worker.isRunning():
            busy_tabs.append("Apenas Mosaico")

        if busy_tabs:
            reply = QMessageBox.question(
                self,
                "Operação em Andamento",
                f"Há processamentos em andamento nas abas: {', '.join(busy_tabs)}.\n\nDeseja realmente interromper e fechar o aplicativo?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                for tab in (self.tab_mp4, self.tab_mkv, self.tab_mosaic):
                    if tab.worker and tab.worker.isRunning():
                        tab.worker.cancel()
                        tab.worker.wait(2000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
