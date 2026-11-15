import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition
from PIL import Image, ImageDraw, ImageFont

class VideoSkippedException(Exception):
    """Exceção levantada quando o usuário solicita pular o vídeo atual."""
    pass

from utils import (
    get_file_dates,
    restore_file_dates,
    format_bytes,
    format_seconds,
    get_low_priority_creation_flags,
    apply_low_priority_to_current_process,
    get_ffmpeg_cmd,
    get_ffprobe_cmd,
    get_optimal_ffmpeg_threads,
    refresh_windows_thumbnail_cache,
    get_free_disk_space_bytes,
    cleanup_leftover_temp_files
)

def probe_video(video_path):
    flags = get_low_priority_creation_flags()
    cmd = [
        get_ffprobe_cmd(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags,
            timeout=25,
            check=True
        )
        data = json.loads(result.stdout)
        
        format_info = data.get("format", {})
        duration = float(format_info.get("duration", 0))
        size = int(format_info.get("size", os.path.getsize(video_path)))
        
        tags = format_info.get("tags", {})
        comment_tag = str(tags.get("comment", "")).lower()
        encoder_tag = str(tags.get("encoder", "")).lower()
        title_tag = str(tags.get("title", "")).lower()
        
        is_already_compressed = (
            "mosaicothumbnailpro" in comment_tag or
            "mosaicothumbnailpro" in encoder_tag or
            "mosaicothumbnailpro" in title_tag
        )
        
        width = 0
        height = 0
        vcodec = "Desconhecido"
        acodec = "Nenhum"
        
        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and width == 0:
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                vcodec = stream.get("codec_name", "h264").upper()
            elif codec_type == "audio" and acodec == "Nenhum":
                acodec = stream.get("codec_name", "aac").upper()
                
        return {
            "duration": duration,
            "size": size,
            "width": width,
            "height": height,
            "vcodec": vcodec,
            "acodec": acodec,
            "is_already_compressed": is_already_compressed
        }
    except Exception as e:
        print(f"Erro no probe do vídeo {video_path}: {e}")
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
        return {
            "duration": 0,
            "size": file_size,
            "width": 1920,
            "height": 1080,
            "vcodec": "N/A",
            "acodec": "N/A",
            "is_already_compressed": False
        }

def _extract_frame_task(task_args):
    i, ts, video_path, frame_path, flags = task_args
    # Adicionado suporte a ignorar erros de gravação e regeneração de timestamps para arquivos .TS corrompidos
    cmd = [
        get_ffmpeg_cmd(),
        "-err_detect", "ignore_err",
        "-fflags", "+genpts+discardcorrupt",
        "-ss", str(ts),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-y",
        frame_path
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            timeout=30
        )
    except Exception:
        pass
    if os.path.exists(frame_path):
        return (i, frame_path, ts)
    return None

def get_unique_mosaic_path(base_dir, base_name, ext, on_conflict="overwrite"):
    """
    Gera o caminho de saída da imagem mosaico.
    Se on_conflict == 'overwrite': sempre salva como 'Nome_mosaico.ext'.
    Se on_conflict == 'number': se já existir, busca 'Nome_mosaico_1.ext', 'Nome_mosaico_2.ext', etc.
    """
    clean_ext = ext.lstrip(".").lower()
    candidate = os.path.join(base_dir, f"{base_name}_mosaico.{clean_ext}")
    if on_conflict != "number" or not os.path.exists(candidate):
        return candidate
    counter = 1
    while True:
        candidate = os.path.join(base_dir, f"{base_name}_mosaico_{counter}.{clean_ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1

def generate_mosaic(video_path, output_jpg_path, rows, cols, meta_info, progress_callback=None, cancel_checker=None, image_format="jpg", quality=95, progress_range=(0, 25)):
    total_frames = rows * cols
    duration = meta_info.get("duration", 0)
    
    if duration <= 0:
        duration = 60
        
    interval = duration / (total_frames + 1)
    timestamps = [(i + 1) * interval for i in range(total_frames)]
    
    temp_dir = tempfile.mkdtemp(prefix="thumb_frames_")
    flags = get_low_priority_creation_flags()
    
    p_start, p_end = progress_range
    p_span = max(1, p_end - p_start)
    p_extract = int(p_span * 0.7)
    p_stitch = p_span - p_extract
    
    try:
        tasks = []
        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(temp_dir, f"frame_{i:03d}.jpg")
            tasks.append((i, ts, video_path, frame_path, flags))

        frame_results = [None] * total_frames
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_idx = {executor.submit(_extract_frame_task, t): t[0] for t in tasks}
            for future in as_completed(future_to_idx):
                if cancel_checker and cancel_checker():
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise InterruptedError("Operação cancelada pelo usuário.")
                res = future.result()
                if res:
                    idx, f_path, ts = res
                    frame_results[idx] = (f_path, ts)
                completed_count += 1
                if progress_callback:
                    pct = p_start + int((completed_count / total_frames) * p_extract)
                    progress_callback(pct, f"Capturando quadros {completed_count}/{total_frames}")

        frame_files = [f for f in frame_results if f is not None]
        if not frame_files:
            raise RuntimeError("Não foi possível extrair quadros deste vídeo. Arquivo pode estar corrompido.")

        thumb_width = 380
        aspect_ratio = meta_info["height"] / meta_info["width"] if meta_info["width"] > 0 else 9 / 16
        thumb_height = int(thumb_width * aspect_ratio)
        
        padding = 12
        header_height = 135
        
        canvas_width = (cols * thumb_width) + ((cols + 1) * padding)
        canvas_height = header_height + (rows * thumb_height) + ((rows + 1) * padding)
        
        canvas = Image.new("RGB", (canvas_width, canvas_height), color=(24, 27, 34))
        draw = ImageDraw.Draw(canvas)
        
        try:
            font_title = ImageFont.truetype("arial.ttf", 29)
            font_info = ImageFont.truetype("arial.ttf", 20)
            font_time = ImageFont.truetype("arial.ttf", 17)
        except IOError:
            font_title = ImageFont.load_default()
            font_info = ImageFont.load_default()
            font_time = ImageFont.load_default()

        filename = os.path.basename(video_path)
        size_str = format_bytes(meta_info["size"])
        duration_str = format_seconds(meta_info["duration"])
        res_str = f'{meta_info["width"]}x{meta_info["height"]}'
        codecs_str = f'Vídeo: {meta_info["vcodec"]} | Áudio: {meta_info["acodec"]}'
        
        draw.rectangle([(0, 0), (canvas_width, header_height)], fill=(32, 36, 46))
        draw.line([(0, header_height), (canvas_width, header_height)], fill=(50, 56, 70), width=2)
        
        draw.text((padding, 15), f"Arquivo: {filename}", fill=(255, 255, 255), font=font_title)
        draw.text((padding, 56), f"Tamanho: {size_str}  |  Duração: {duration_str}  |  Resolução: {res_str}", fill=(180, 190, 205), font=font_info)
        draw.text((padding, 92), f"Formatos / Codecs: {codecs_str}", fill=(140, 150, 165), font=font_info)

        for idx, (f_path, ts) in enumerate(frame_files):
            if cancel_checker and cancel_checker():
                raise InterruptedError("Operação cancelada pelo usuário.")
                
            row_idx = idx // cols
            col_idx = idx % cols
            
            x = padding + col_idx * (thumb_width + padding)
            y = header_height + padding + row_idx * (thumb_height + padding)
            
            with Image.open(f_path) as img:
                img_resized = img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
                canvas.paste(img_resized, (x, y))
                
            draw.rectangle([(x, y), (x + thumb_width, y + thumb_height)], outline=(60, 66, 80), width=1)
            
            ts_text = format_seconds(ts)
            bbox = font_time.getbbox(ts_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            
            box_px = 7
            box_x1 = x + thumb_width - tw - (box_px * 2) - 6
            box_y1 = y + thumb_height - th - (box_px * 2) - 6
            box_x2 = x + thumb_width - 6
            box_y2 = y + thumb_height - 6
            
            draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill=(0, 0, 0))
            draw.text((box_x1 + box_px, box_y1 + box_px - 2), ts_text, fill=(255, 255, 255), font=font_time)
            
            if progress_callback:
                progress_pct = p_start + p_extract + int(((idx + 1) / total_frames) * p_stitch)
                progress_callback(progress_pct, f"Montando mosaico {idx+1}/{total_frames}")

        clean_fmt = str(image_format).lower().replace(".", "").strip()
        if clean_fmt == "png":
            canvas.save(output_jpg_path, "PNG", optimize=True)
        else:
            canvas.save(output_jpg_path, "JPEG", quality=quality)
        return output_jpg_path
        
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

def _clean_ffmpeg_error(raw_stderr: str) -> str:
    """Extrai apenas as linhas finais e relevantes do log do FFmpeg, removendo o cabeçalho técnico de compilação."""
    if not raw_stderr:
        return "Erro desconhecido retornado pelo motor FFmpeg."
    lines = [line.strip() for line in raw_stderr.splitlines() if line.strip()]
    meaningful = [
        l for l in lines
        if not l.startswith("ffmpeg version")
        and not l.startswith("configuration:")
        and not l.startswith("lib")
        and not l.startswith("built with")
    ]
    if meaningful:
        return "\n".join(meaningful[-10:])
    return "\n".join(lines[-10:])

def _kill_process_tree(process):
    """Mata o processo e toda a sua árvore no Windows de forma imediata e forçada."""
    if process is None:
        return
    try:
        process.kill()
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000 # CREATE_NO_WINDOW
        )
    except Exception:
        pass

def embed_cover_and_process_video(video_path, mosaic_jpg_path, meta_info=None, compress=False, progress_callback=None, cancel_checker=None, process_holder=None, target_format="mp4"):
    total_duration = meta_info.get("duration", 0) if meta_info else 0
    is_already_compressed = meta_info.get("is_already_compressed", False) if meta_info else False
    atime, mtime = get_file_dates(video_path)
    
    target_format = target_format.lower().strip()
    target_ext = f".{target_format}"
    fmt_upper = target_format.upper()
    
    dir_name, full_name = os.path.split(video_path)
    base_name, ext = os.path.splitext(full_name)
    is_target_format = ext.lower() == target_ext
    
    file_size = meta_info.get("size", os.path.getsize(video_path)) if meta_info else os.path.getsize(video_path)
    free_disk = get_free_disk_space_bytes(video_path)
    required_space = max(2 * 1024 * 1024 * 1024, int(file_size * 1.3))
    
    if free_disk < required_space:
        raise RuntimeError(
            f"Espaço insuficiente no HD ({format_bytes(free_disk)} livres). "
            f"Necessário pelo menos {format_bytes(required_space)} para processar este vídeo de forma segura."
        )
    
    temp_output = os.path.join(dir_name, f"temp_{int(time.time())}_{base_name}{target_ext}")
    final_video_path = os.path.join(dir_name, f"{base_name}{target_ext}")
    
    flags = get_low_priority_creation_flags()
    threads = get_optimal_ffmpeg_threads()
    
    stderr_log_path = os.path.join(tempfile.gettempdir(), f"ffmpeg_log_{int(time.time())}.txt")
    
    try:
        if target_format == "mkv":
            cmd = [
                get_ffmpeg_cmd(), "-y",
                "-err_detect", "ignore_err",
                "-fflags", "+genpts+discardcorrupt",
                "-progress", "pipe:1",
                "-i", video_path,
                "-attach", mosaic_jpg_path,
                "-metadata:s:t", "mimetype=image/jpeg",
                "-metadata:s:t", "filename=cover.jpg",
                "-map", "0:v:0?", "-map", "0:a?",
                "-dn",
                "-avoid_negative_ts", "make_zero",
                "-max_muxing_queue_size", "1024",
                "-metadata", "encoder=MosaicoThumbnailPro",
                "-metadata", "comment=MosaicoThumbnailPro_Compressed",
                "-threads", str(threads)
            ]
        else: # mp4 padrão
            cmd = [
                get_ffmpeg_cmd(), "-y",
                "-err_detect", "ignore_err",
                "-fflags", "+genpts+discardcorrupt",
                "-progress", "pipe:1",
                "-i", video_path,
                "-i", mosaic_jpg_path
            ]
            cmd.extend(["-map", "0:v:0?", "-map", "0:a?", "-map", "1:v:0"])
            cmd.extend(["-c:v:1", "copy", "-disposition:v:1", "attached_pic"])
            cmd.extend(["-dn"])
            cmd.extend(["-avoid_negative_ts", "make_zero", "-max_muxing_queue_size", "1024"])
            cmd.extend(["-metadata", "encoder=MosaicoThumbnailPro"])
            cmd.extend(["-metadata", "comment=MosaicoThumbnailPro_Compressed"])
            cmd.extend(["-threads", str(threads)])
        
        if is_target_format and (is_already_compressed or not compress):
            cmd.extend(["-c:v:0", "copy", "-c:a", "copy"])
            if progress_callback:
                progress_callback(30, f"Vídeo já comprimido anteriormente! Copiando para {fmt_upper} ultra-rápido...")
        else:
            crf_val = "24" if compress else "22"
            cmd.extend([
                "-c:v:0", "libx264",
                "-crf", crf_val,
                "-preset", "superfast",
                "-fps_mode", "vfr",
                "-c:a", "aac",
                "-af", "aresample=async=1"
            ])
                
        cmd.append(temp_output)
        
        with open(stderr_log_path, "w", encoding="utf-8", errors="ignore") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=log_file,
                text=True,
                creationflags=flags,
                bufsize=1
            )
            if process_holder:
                process_holder(process)
            
            out_time_us = 0
            speed_val = 1.0
            
            stdout_queue = queue.Queue()
            
            def _reader_thread(pipe, q):
                try:
                    for l in iter(pipe.readline, ''):
                        q.put(l)
                except Exception:
                    pass
                finally:
                    try:
                        pipe.close()
                    except Exception:
                        pass

            reader = threading.Thread(
                target=_reader_thread,
                args=(process.stdout, stdout_queue),
                daemon=True
            )
            reader.start()

            last_heartbeat_time = time.time()
            last_window_time = time.time()
            last_window_out_time_us = 0
            CHECK_WINDOW_SECONDS = 20 # Janela de 20s para aferir progresso real

            while True:
                if cancel_checker:
                    t_before_check = time.time()
                    check_res = cancel_checker()
                    if check_res == "cancel" or check_res is True:
                        _kill_process_tree(process)
                        raise InterruptedError("Operação cancelada pelo usuário.")
                    elif check_res == "skip":
                        _kill_process_tree(process)
                        raise VideoSkippedException("Vídeo pulado pelo usuário.")
                        
                    # Se cancel_checker demorou mais de 0.5s (ex: usuário pausou o app),
                    # reseta os relógios para não disparar o watchdog indevidamente ao despausar:
                    if time.time() - t_before_check > 0.5:
                        last_heartbeat_time = time.time()
                        last_window_time = time.time()
                        last_window_out_time_us = out_time_us
                
                ret_code = process.poll()
                
                try:
                    line = stdout_queue.get(timeout=0.5)
                except queue.Empty:
                    line = None
                    
                curr_clock = time.time()
                
                if line is not None:
                    line = line.strip()
                    last_heartbeat_time = curr_clock
                    
                    if line.startswith("out_time_us="):
                        try:
                            out_time_us = int(line.split("=")[1])
                        except ValueError:
                            pass
                    elif line.startswith("speed="):
                        speed_str = line.split("=")[1].replace("x", "").strip()
                        try:
                            speed_val = float(speed_str)
                        except ValueError:
                            pass
                    elif line.startswith("progress="):
                        curr_sec = out_time_us / 1000000.0
                        if total_duration > 0:
                            enc_ratio = min(1.0, max(0.0, curr_sec / total_duration))
                            pct = 25 + int(enc_ratio * 70)
                            
                            rem_sec = total_duration - curr_sec
                            if speed_val > 0.05:
                                item_eta = int(rem_sec / speed_val)
                            else:
                                item_eta = int(rem_sec)
                                
                            if progress_callback:
                                speed_disp = f"{speed_val:.1f}x"
                                pct_disp = int(enc_ratio * 100)
                                status_msg = "Processando Capa (Rápido)" if (is_target_format and is_already_compressed) else f"Convertendo para {fmt_upper} ({pct_disp}% - Vel. {speed_disp})"
                                progress_callback(pct, status_msg, item_eta)
                else:
                    if ret_code is not None and stdout_queue.empty():
                        break

                # === CÃO DE GUARDA DE TEMPO REAL (WATCHDOG INFALÍVEL) ===
                # 1. Se o FFmpeg parar de responder por completo (silêncio total no pipe por > 25s)
                if (curr_clock - last_heartbeat_time) > 25:
                    _kill_process_tree(process)
                    raise RuntimeError(
                        "Vídeo corrompido: FFmpeg travou e parou de responder por mais de 25s (Silêncio total). Abortado automaticamente para proteger a fila."
                    )

                # 2. Se a cada janela de 20s o vídeo avançar menos de 800ms de duração E velocidade for < 0.2x:
                if (curr_clock - last_window_time) >= CHECK_WINDOW_SECONDS:
                    video_advanced_us = out_time_us - last_window_out_time_us
                    if video_advanced_us < 800000 and speed_val < 0.2:
                        _kill_process_tree(process)
                        raise RuntimeError(
                            f"Vídeo corrompido: velocidade travada em {speed_val:.2f}x (vídeo não avança há {CHECK_WINDOW_SECONDS}s). Abortado automaticamente para proteger a fila."
                        )
                    last_window_time = curr_clock
                    last_window_out_time_us = out_time_us
            
        if process.returncode != 0:
            stderr_out = ""
            if os.path.exists(stderr_log_path):
                with open(stderr_log_path, "r", encoding="utf-8", errors="ignore") as log_file:
                    stderr_out = log_file.read()
            clean_err = _clean_ffmpeg_error(stderr_out)
            raise RuntimeError(f"Erro no FFmpeg ao converter/embutir capa:\n{clean_err}")

        if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
            raise RuntimeError(f"O arquivo temporário {fmt_upper} não foi gerado pelo FFmpeg.")

        if progress_callback:
            progress_callback(95, f"Finalizando arquivo {fmt_upper} e restaurando datas...", 1)

        if not is_target_format and os.path.exists(video_path) and os.path.abspath(video_path) != os.path.abspath(final_video_path):
            try:
                os.remove(video_path)
            except Exception as e:
                print(f"Aviso ao remover arquivo original ({video_path}): {e}")

        if os.path.exists(final_video_path):
            os.replace(temp_output, final_video_path)
        else:
            os.replace(temp_output, final_video_path)

        restore_file_dates(final_video_path, atime, mtime)
        refresh_windows_thumbnail_cache(final_video_path)
        
        if progress_callback:
            progress_callback(100, "Concluído com sucesso!", 0)

        return final_video_path
        
    finally:
        if process_holder:
            try:
                process_holder(None)
            except Exception:
                pass
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except Exception:
                pass
        if os.path.exists(stderr_log_path):
            try:
                os.remove(stderr_log_path)
            except Exception:
                pass

class WorkerThread(QThread):
    item_started = Signal(str)
    item_progress = Signal(str, int, str, int, int, int, int)
    item_finished = Signal(str, bool, str)
    queue_completed = Signal(dict)
    
    def __init__(self, queue_items, settings, parent=None):
        super().__init__(parent)
        self.queue_items = queue_items
        self.settings = settings
        self.is_paused = False
        self.is_cancelled = False
        self.is_skipped = False
        self.current_process = None
        self.mutex = QMutex()
        self.pause_condition = QWaitCondition()

    def set_current_process(self, proc):
        self.mutex.lock()
        self.current_process = proc
        self.mutex.unlock()

    def pause(self):
        self.mutex.lock()
        self.is_paused = True
        self.mutex.unlock()

    def resume(self):
        self.mutex.lock()
        self.is_paused = False
        self.pause_condition.wakeAll()
        self.mutex.unlock()

    def cancel(self):
        self.mutex.lock()
        self.is_cancelled = True
        proc = self.current_process
        if self.is_paused:
            self.is_paused = False
            self.pause_condition.wakeAll()
        self.mutex.unlock()
        if proc:
            _kill_process_tree(proc)

    def skip_current(self):
        self.mutex.lock()
        self.is_skipped = True
        proc = self.current_process
        if self.is_paused:
            self.is_paused = False
            self.pause_condition.wakeAll()
        self.mutex.unlock()
        if proc:
            _kill_process_tree(proc)

    def check_pause_or_cancel(self):
        self.mutex.lock()
        while self.is_paused:
            self.pause_condition.wait(self.mutex)
        cancelled = self.is_cancelled
        skipped = self.is_skipped
        self.mutex.unlock()
        if cancelled:
            return "cancel"
        if skipped:
            return "skip"
        return "continue"

    def run(self):
        apply_low_priority_to_current_process()
        cleanup_leftover_temp_files()
        
        mode = self.settings.get("mode", "mp4").lower()
        rows = self.settings.get("rows", 6)
        cols = self.settings.get("cols", 4)
        compress = self.settings.get("compress", True)
        save_mosaic_separately = self.settings.get("save_mosaic", False)
        custom_mosaic_dir = self.settings.get("mosaic_dir", None)
        image_fmt = self.settings.get("image_format", "jpg").lower()
        on_conflict = self.settings.get("on_conflict", "overwrite").lower()
        quality = self.settings.get("quality", 95)
        
        total_items = len(self.queue_items)
        completed_times = []
        
        queue_start_time = time.time()
        total_initial_bytes = 0
        total_final_bytes = 0
        success_count = 0
        error_count = 0
        error_list = []
        
        for idx_item, item in enumerate(self.queue_items):
            video_path = item["path"]
            item_num = idx_item + 1
            
            self.mutex.lock()
            self.is_skipped = False
            self.current_process = None
            self.mutex.unlock()
            
            chk_status = self.check_pause_or_cancel()
            if chk_status == "cancel":
                break
            elif chk_status == "skip":
                self.item_finished.emit(video_path, False, "⏭️ Pulado")
                continue
                
            item_start_time = time.time()
            self.item_started.emit(video_path)
            
            default_avg = 4 if mode == "mosaic_only" else 30
            avg_time = (sum(completed_times) / len(completed_times)) if completed_times else default_avg
            items_remaining = total_items - idx_item
            est_item_eta = int(avg_time)
            est_queue_eta = int(avg_time * items_remaining)
            
            self.item_progress.emit(video_path, 2, "Iniciando análise...", est_item_eta, est_queue_eta, item_num, total_items)
            
            mosaic_target_path = None
            try:
                meta_info = probe_video(video_path)
                initial_size = meta_info.get("size", os.path.getsize(video_path))
                
                chk_status = self.check_pause_or_cancel()
                if chk_status == "cancel":
                    break
                elif chk_status == "skip":
                    self.item_finished.emit(video_path, False, "⏭️ Pulado")
                    continue
                    
                dir_name, full_name = os.path.split(video_path)
                base_name, _ = os.path.splitext(full_name)
                
                if custom_mosaic_dir and os.path.exists(custom_mosaic_dir):
                    target_dir = custom_mosaic_dir
                else:
                    target_dir = dir_name

                def progress_cb(pct, status, override_item_eta=None):
                    elapsed_so_far = time.time() - item_start_time
                    if override_item_eta is not None:
                        calc_item_eta = override_item_eta
                    elif pct > 5:
                        calc_item_eta = max(1, int((elapsed_so_far / (pct / 100.0)) - elapsed_so_far))
                    else:
                        calc_item_eta = est_item_eta
                        
                    calc_queue_eta = calc_item_eta + int(avg_time * (items_remaining - 1))
                    self.item_progress.emit(video_path, pct, status, calc_item_eta, calc_queue_eta, item_num, total_items)

                # ==============================================================
                # MODO 1: APENAS IMAGEM MOSAICO (SEM CONVERTER VÍDEO)
                # ==============================================================
                if mode == "mosaic_only":
                    mosaic_target_path = get_unique_mosaic_path(target_dir, base_name, image_fmt, on_conflict)
                    
                    generate_mosaic(
                        video_path=video_path,
                        output_jpg_path=mosaic_target_path,
                        rows=rows,
                        cols=cols,
                        meta_info=meta_info,
                        progress_callback=progress_cb,
                        cancel_checker=lambda: self.check_pause_or_cancel() != "continue",
                        image_format=image_fmt,
                        quality=quality,
                        progress_range=(5, 95)
                    )
                    
                    progress_cb(100, "Mosaico gerado com sucesso!", 0)
                    success_count += 1
                    item_duration = time.time() - item_start_time
                    completed_times.append(item_duration)
                    self.item_finished.emit(mosaic_target_path, True, "Mosaico gerado com sucesso")
                    continue

                # ==============================================================
                # MODO 2: CONVERSÃO DE VÍDEO (MP4 OU MKV) COM CAPA EMBUTIDA
                # ==============================================================
                mosaic_target_path = os.path.join(target_dir, f"{base_name}_mosaico.jpg")
                
                generate_mosaic(
                    video_path=video_path,
                    output_jpg_path=mosaic_target_path,
                    rows=rows,
                    cols=cols,
                    meta_info=meta_info,
                    progress_callback=progress_cb,
                    cancel_checker=lambda: self.check_pause_or_cancel() != "continue",
                    image_format="jpg",
                    quality=92,
                    progress_range=(0, 25)
                )
                
                chk_status = self.check_pause_or_cancel()
                if chk_status == "cancel":
                    break
                elif chk_status == "skip":
                    if not save_mosaic_separately and mosaic_target_path and os.path.exists(mosaic_target_path):
                        try:
                            os.remove(mosaic_target_path)
                        except Exception:
                            pass
                    self.item_finished.emit(video_path, False, "⏭️ Pulado")
                    continue
                    
                target_fmt = "mkv" if mode == "mkv" else "mp4"
                final_video_path = embed_cover_and_process_video(
                    video_path=video_path,
                    mosaic_jpg_path=mosaic_target_path,
                    meta_info=meta_info,
                    compress=compress,
                    progress_callback=progress_cb,
                    cancel_checker=self.check_pause_or_cancel,
                    process_holder=self.set_current_process,
                    target_format=target_fmt
                )
                
                if not save_mosaic_separately and mosaic_target_path and os.path.exists(mosaic_target_path):
                    try:
                        os.remove(mosaic_target_path)
                    except Exception:
                        pass
                        
                final_size = os.path.getsize(final_video_path) if os.path.exists(final_video_path) else initial_size
                total_initial_bytes += initial_size
                total_final_bytes += final_size
                success_count += 1
                
                item_duration = time.time() - item_start_time
                completed_times.append(item_duration)
                
                self.item_finished.emit(final_video_path, True, f"Concluído com sucesso ({target_fmt.upper()})")
                
            except InterruptedError:
                self.item_finished.emit(video_path, False, "Cancelado")
                break
            except VideoSkippedException:
                if not save_mosaic_separately and mosaic_target_path and os.path.exists(mosaic_target_path):
                    try:
                        os.remove(mosaic_target_path)
                    except Exception:
                        pass
                self.item_finished.emit(video_path, False, "⏭️ Pulado")
                continue
            except Exception as e:
                error_count += 1
                error_list.append((os.path.basename(video_path), str(e)))
                self.item_finished.emit(video_path, False, str(e))
                
        summary_data = {
            "mode": mode,
            "total_items": total_items,
            "success_count": success_count,
            "error_count": error_count,
            "total_elapsed_sec": int(time.time() - queue_start_time),
            "total_initial_bytes": total_initial_bytes,
            "total_final_bytes": total_final_bytes,
            "error_list": error_list
        }
        
        self.queue_completed.emit(summary_data)
