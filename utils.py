import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
import tempfile
import psutil
import ctypes
import glob

FFMPEG_DOWNLOAD_URL = "https://github.com/GyanD/codexffmpeg/releases/download/7.0.2/ffmpeg-7.0.2-essentials_build.zip"

SUPPORTED_EXTENSIONS = (
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.ts', '.m2ts', '.mts', '.vob', '.3gp', '.mpg',
    '.mpeg', '.divx', '.asf', '.ogv'
)

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(get_app_dir(), relative_path)

def get_ffmpeg_cmd():
    app_dir = get_app_dir()
    local = os.path.join(app_dir, "ffmpeg.exe")
    if os.path.exists(local):
        return local
    return "ffmpeg"

def get_ffprobe_cmd():
    app_dir = get_app_dir()
    local = os.path.join(app_dir, "ffprobe.exe")
    if os.path.exists(local):
        return local
    return "ffprobe"

def check_ffmpeg_installed():
    app_dir = get_app_dir()
    local_ffmpeg = os.path.join(app_dir, "ffmpeg.exe")
    local_ffprobe = os.path.join(app_dir, "ffprobe.exe")
    
    if os.path.exists(local_ffmpeg) and os.path.exists(local_ffprobe):
        return True

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    return bool(ffmpeg_path and ffprobe_path)

def get_optimal_ffmpeg_threads():
    total_cores = os.cpu_count() or 4
    optimal = max(2, total_cores // 2)
    return optimal

def get_free_disk_space_bytes(path):
    """
    Retorna o espaço livre em bytes na unidade de disco onde o caminho está localizado.
    """
    try:
        target_dir = os.path.dirname(os.path.abspath(path))
        if not os.path.exists(target_dir):
            target_dir = get_app_dir()
        _, _, free = shutil.disk_usage(target_dir)
        return free
    except Exception:
        return 10 * 1024 * 1024 * 1024

def cleanup_leftover_temp_files():
    """
    Remove arquivos temporários residuais (%TEMP%/thumb_frames_* e ffmpeg_log_*)
    para garantir que o disco não fique poluído com o tempo.
    """
    temp_root = tempfile.gettempdir()
    try:
        for p in glob.glob(os.path.join(temp_root, "thumb_frames_*")):
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
        for f in glob.glob(os.path.join(temp_root, "ffmpeg_log_*.txt")):
            if os.path.isfile(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
    except Exception as e:
        print(f"Aviso na limpeza de temporários: {e}")

def detect_hardware_encoder():
    ffmpeg = get_ffmpeg_cmd()
    flags = get_low_priority_creation_flags()
    
    encoders_to_test = ["h264_nvenc", "h264_qsv", "h264_amf"]
    try:
        res = subprocess.run(
            [ffmpeg, "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags
        )
        out = res.stdout.lower()
        for enc in encoders_to_test:
            if enc in out:
                return enc
    except Exception:
        pass
    return None

def refresh_windows_thumbnail_cache(file_path):
    if sys.platform == "win32":
        try:
            SHCNE_UPDATEITEM = 0x00002000
            SHCNE_ASSOCCHANGED = 0x08000000
            SHFMT_PATHW = 0x0005
            abs_path = os.path.abspath(file_path)
            ctypes.windll.shell32.SHChangeNotify(SHCNE_UPDATEITEM, SHFMT_PATHW, abs_path, None)
            ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)
        except Exception as e:
            print(f"Erro ao notificar o Windows Shell: {e}")

def download_and_extract_ffmpeg(progress_callback=None):
    app_dir = get_app_dir()
    zip_temp_path = os.path.join(tempfile.gettempdir(), "ffmpeg_download.zip")
    
    try:
        if progress_callback:
            progress_callback(10, "Conectando ao servidor para baixar o FFmpeg...")

        def _reporthook(blocknum, blocksize, totalsize):
            if totalsize > 0 and progress_callback:
                downloaded = blocknum * blocksize
                percent = int(10 + (downloaded / totalsize) * 70)
                percent = min(percent, 80)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = totalsize / (1024 * 1024)
                progress_callback(percent, f"Baixando FFmpeg: {mb_downloaded:.1f} MB de {mb_total:.1f} MB")

        urllib.request.urlretrieve(FFMPEG_DOWNLOAD_URL, zip_temp_path, reporthook=_reporthook)

        if progress_callback:
            progress_callback(85, "Extraindo arquivos do FFmpeg...")

        extracted_count = 0
        with zipfile.ZipFile(zip_temp_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                filename = os.path.basename(file_info.filename)
                if filename.lower() in ("ffmpeg.exe", "ffprobe.exe"):
                    target_path = os.path.join(app_dir, filename)
                    with zip_ref.open(file_info) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    extracted_count += 1

        if progress_callback:
            progress_callback(100, "FFmpeg instalado e configurado com sucesso!")

        return extracted_count >= 2
    except Exception as e:
        print(f"Erro ao baixar/extrair FFmpeg: {e}")
        raise e
    finally:
        if os.path.exists(zip_temp_path):
            try:
                os.remove(zip_temp_path)
            except Exception:
                pass

def get_file_dates(file_path):
    stat_info = os.stat(file_path)
    return stat_info.st_atime, stat_info.st_mtime

def restore_file_dates(file_path, atime, mtime):
    try:
        os.utime(file_path, (atime, mtime))
        return True
    except Exception as e:
        print(f"Erro ao restaurar datas em {file_path}: {e}")
        return False

def format_bytes(size_in_bytes):
    if size_in_bytes is None or size_in_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def format_seconds(seconds):
    if seconds is None or seconds < 0:
        return "00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def get_low_priority_creation_flags():
    flags = 0
    if sys.platform == "win32":
        flags = 0x00004000 | 0x08000000
    return flags

def apply_low_priority_to_current_process():
    try:
        p = psutil.Process(os.getpid())
        if sys.platform == "win32":
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
    except Exception as e:
        print(f"Não foi possível ajustar prioridade do processo: {e}")
