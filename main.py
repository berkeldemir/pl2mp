import sys
import os
import glob
import re
import time
import subprocess
import requests
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TYER, TCON, TRCK
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QListWidget, QLabel, 
                             QStackedWidget, QFrame, QComboBox, QAbstractItemView, 
                             QMessageBox, QFileDialog, QScrollArea, QGridLayout, QListWidgetItem)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRectF
from PySide6.QtGui import QPixmap, QImage, QIcon, QPainter, QPen, QColor, QFont

try:
    from style import STYLE_SHEET
except ImportError:
    STYLE_SHEET = ""

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
ICON_BACK = os.path.join(ASSETS_DIR, "back.png")
ICON_BROWSE = os.path.join(ASSETS_DIR, "browse.png")
ICON_ADD = os.path.join(ASSETS_DIR, "add.png")

VERSION = "1.0.0"
GITHUB_USER = "berkeldemir"
GITHUB_REPO = "pl2mp"

def check_and_update():
    # Arkadaşının bilgisayarında kodların durduğu klasör
    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(sys.executable)
        # PyInstaller klasör yapısında kaynak kodların çalıştığı yer
        base_dir = os.path.abspath(os.path.join(current_dir, "..", "Resources"))
    else:
        return

    # Sürüm kontrolünü yine GitHub API'den hafif bir text olarak yapıyoruz
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data["tag_name"].replace("v", "")
            
            if latest_version > VERSION:
                # GitHub'daki ana branch'indeki (main/master) güncel kodların ham (raw) linkleri
                raw_base_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main"
                
                # Güncellenecek dosyaların listesi (Yeni dosya eklersen buraya yazman yeterli)
                files_to_update = ["main.py", "style.py"]
                
                for file_name in files_to_update:
                    file_url = f"{raw_base_url}/{file_name}"
                    file_response = requests.get(file_url, timeout=5)
                    if file_response.status_code == 200:
                        # Eski kod dosyasının üzerine yenisini yazıyoruz
                        with open(os.path.join(base_dir, file_name), "w", encoding="utf-8") as f:
                            f.write(file_response.text)
                
                print("Uygulama başarıyla güncellendi. Lütfen yeniden başlatın.")
                sys.exit(0)
    except Exception as e:
        print(f"Güncelleme atlandı: {e}")

# --- MİNİMALİST DAİRESEL (PIE) WIDGET ---
class CircularProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.setFixedSize(24, 24) # Çok daha minik ve zarif

    def setValue(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = QRectF(2, 2, self.width()-4, self.height()-4)
        
        # Arka Plan Dairesi (Koyu Gri)
        painter.setBrush(QColor("#2A2A2A"))
        painter.setPen(Qt.NoPen) # Kenarlık yok
        painter.drawEllipse(rect)

        # İçi Dolu Pie Chart (Dümdüz Beyaz)
        if self.value > 0:
            painter.setBrush(QColor("#FFFFFF"))
            start_angle = 90 * 16
            span_angle = -int((self.value / 100.0) * 360 * 16)
            painter.drawPie(rect, start_angle, span_angle)

# --- WORKER SINIFLARI ---

class DownloadWorker(QThread):
    progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, metadata):
        super().__init__()
        self.metadata = metadata
        self.is_paused = False
        self.is_cancelled = False

    def run(self):
        try:
            target_dir = self.metadata['target_dir']
            artist = self.metadata['artist']
            album = self.metadata['album']
            cover_url = self.metadata['cover_url']
            songs = self.metadata['songs']

            safe_artist = re.sub(r'[\\/*?:"<>|]', "", artist)
            safe_album = re.sub(r'[\\/*?:"<>|]', "", album)
            album_path = os.path.join(target_dir, safe_artist, safe_album)
            os.makedirs(album_path, exist_ok=True)

            cover_path = os.path.join(album_path, "cover.jpg")
            if cover_url and cover_url.startswith("http"):
                self.progress.emit(2, "Fetching Cover...")
                try:
                    resp = requests.get(cover_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    if resp.status_code == 200:
                        img = QImage()
                        if img.loadFromData(resp.content):
                            img = img.scaled(600, 600, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            img.save(cover_path, "JPG", 100)
                except: pass

            total_songs = len(songs)
            for index, song in enumerate(songs, start=1):
                if self.is_cancelled: break
                while self.is_paused and not self.is_cancelled: time.sleep(0.5)

                track_num = f"{index:02d}"
                safe_title = re.sub(r'[\\/*?:"<>|]', "", song['title'])
                file_name = f"{safe_title}.mp3"
                out_path = os.path.join(album_path, file_name)

                base_prog = 2 + int(((index - 1) / total_songs) * 98)
                self.progress.emit(base_prog, f"[{index}/{total_songs}] {safe_title[:25]}")

                def progress_hook(d):
                    if self.is_cancelled: raise ValueError("CANCELLED")
                    while self.is_paused and not self.is_cancelled: time.sleep(0.5)

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(album_path, f"{safe_title}.%(ext)s"),
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                    'quiet': True, 'noprogress': True, 'no_warnings': True, 'cookiefile': 'cookies.txt',
                    'sleep_interval_requests': 2, 'extractor_args': {'youtube': ['player_client=default']},
                    'progress_hooks': [progress_hook]
                }

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([song['url']])
                except ValueError as ve:
                    if str(ve) == "CANCELLED" or self.is_cancelled: break
                except Exception as e:
                    if self.is_cancelled: break

                if self.is_cancelled: break

                self.progress.emit(base_prog + int(98 / total_songs / 2), f"Tagging: {safe_title[:15]}")
                self.apply_metadata(out_path, song['title'], track_num, cover_path, total_songs)

            if self.is_cancelled: self.error.emit("Cancelled.")
            else:
                self.progress.emit(100, "Done!")
                self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

    def apply_metadata(self, file_path, title, track_num, cover_path, total_songs):
        try:
            audio = MP3(file_path, ID3=ID3)
            if audio.tags is None: audio.add_tags()
            tags = audio.tags
            tags.add(TIT2(encoding=3, text=title))
            tags.add(TPE1(encoding=3, text=self.metadata['artist']))
            tags.add(TALB(encoding=3, text=self.metadata['album']))
            tags.add(TYER(encoding=3, text=self.metadata['year']))
            tags.add(TCON(encoding=3, text=self.metadata['genre']))
            tags.add(TRCK(encoding=3, text=f"{track_num}/{total_songs}"))
            if os.path.exists(cover_path):
                with open(cover_path, 'rb') as img:
                    tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc=u'', data=img.read()))
            audio.save(v2_version=3)
        except: pass

class ImageLoader(QThread):
    loaded = Signal(QPixmap)
    error = Signal()
    def __init__(self, url):
        super().__init__()
        self.url = url
    def run(self):
        try:
            resp = requests.get(self.url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            img = QImage()
            if img.loadFromData(resp.content): self.loaded.emit(QPixmap.fromImage(img))
            else: self.error.emit()
        except: self.error.emit()

class FetchWorker(QThread):
    finished = Signal(list, dict) 
    error = Signal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url

    def get_itunes_cover(self, artist, album):
        try:
            query = f"{artist} {album}".strip().replace(" ", "+")
            url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=1"
            r = requests.get(url, timeout=5).json()
            if r.get('resultCount', 0) > 0: return r['results'][0]['artworkUrl100'].replace('100x100bb', '600x600bb')
        except: pass
        return ""

    def run(self):
        try:
            ydl_opts_flat = {
                'extract_flat': True, 'quiet': True, 'no_warnings': True,
                'cookiefile': 'cookies.txt', 'extractor_args': {'youtube': ['player_client=android,web']}
            }
            with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if not info or 'entries' not in info:
                    self.error.emit("Oynatma listesi bilgisi çekilemedi.")
                    return

                entries = [{'title': e.get('title'), 'url': e.get('url')} for e in info.get('entries', []) if e]
                raw_album = info.get('title') or 'Unknown Album'
                clean_album = re.sub(r'^(Album|EP|Single)\s*-\s*', '', str(raw_album), flags=re.IGNORECASE).strip()
                raw_artist = info.get('uploader') or info.get('channel') or 'Unknown Artist'
                clean_artist = str(raw_artist).replace(' - Topic', '').strip()

            year = ""
            genre = "Pop"
            if entries:
                ydl_opts_deep = {'quiet': True, 'no_warnings': True, 'cookiefile': 'cookies.txt', 'extractor_args': {'youtube': ['player_client=default']}}
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_deep) as ydl_deep:
                        first_track = ydl_deep.extract_info(entries[0]['url'], download=False)
                        if not clean_artist or clean_artist.lower() in ["various artists", "unknown artist"]:
                            temp_art = first_track.get('artist') or first_track.get('uploader') or clean_artist
                            clean_artist = str(temp_art).replace(' - Topic', '').strip()
                        temp_year = first_track.get('release_year') or first_track.get('upload_date', '    ')[:4]
                        year = str(temp_year)
                        found_genre = first_track.get('genre') or ['Pop']
                        if isinstance(found_genre, list) and found_genre: genre = str(found_genre[0])
                        else: genre = str(found_genre)
                except: pass

            cover_url = self.get_itunes_cover(clean_artist, clean_album)
            if not cover_url:
                thumbs = info.get('thumbnails') or []
                if thumbs: cover_url = thumbs[-1].get('url', '')

            safe_genres = ["Alternative", "Blues", "Classical", "Country", "Dance", "Electronic", "Hip-Hop", "Indie", "Jazz", "J-Pop", "K-Pop", "Lo-Fi", "Metal", "New Age", "Pop", "R&B", "Reggae", "Rock", "Soul", "Soundtrack", "Techno"]
            matched_genre = "Pop"
            for sg in safe_genres:
                if sg.lower() in genre.lower():
                    matched_genre = sg
                    break

            meta = {
                'album': clean_album, 'artist': clean_artist, 'year': year.strip(),
                'genre': matched_genre, 'cover_url': cover_url
            }
            self.finished.emit(entries, meta)
        except Exception as e: self.error.emit(str(e))

# --- MİNİMALİST 2-SATIR KUYRUK ROW ---
class DownloadRowWidget(QFrame):
    def __init__(self, metadata, parent_queue):
        super().__init__()
        self.metadata = metadata
        self.parent_queue = parent_queue
        self.setObjectName("download_row")
        
        # Ekstrem kompakt kenar boşlukları
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(10)

        # 1. Minik Pie Chart
        self.progress_circle = CircularProgress()
        main_layout.addWidget(self.progress_circle)

        # 2. Metinler (Aradaki boşluk sıfırlandı)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.setAlignment(Qt.AlignVCenter)
        
        self.title_lbl = QLabel(f"{metadata['artist']} - {metadata['album']}")
        self.title_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #E0E0E0;")
        
        self.status_lbl = QLabel("Initializing...")
        self.status_lbl.setStyleSheet("font-size: 10px; color: #888888;")
        
        text_layout.addWidget(self.title_lbl)
        text_layout.addWidget(self.status_lbl)
        main_layout.addLayout(text_layout)
        main_layout.addStretch()

        # 3. Çok Minik Kare Butonlar
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setProperty("class", "queue_btn_compact")
        self.pause_btn.setFixedSize(24, 24)
        self.pause_btn.setStyleSheet("background-color: #3700B3; color: white;")
        self.pause_btn.clicked.connect(self.toggle_pause)

        self.cancel_btn = QPushButton("⏹")
        self.cancel_btn.setProperty("class", "queue_btn_compact")
        self.cancel_btn.setFixedSize(24, 24)
        self.cancel_btn.setStyleSheet("background-color: #CF6679; color: black;")
        self.cancel_btn.clicked.connect(self.cancel_download)

        self.remove_btn = QPushButton("✖")
        self.remove_btn.setProperty("class", "queue_btn_compact")
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.setStyleSheet("background-color: transparent; color: #888;")
        self.remove_btn.setVisible(False)
        self.remove_btn.clicked.connect(self.remove_row)

        main_layout.addWidget(self.pause_btn)
        main_layout.addWidget(self.cancel_btn)
        main_layout.addWidget(self.remove_btn)

        # Worker'ı Başlat
        self.worker = DownloadWorker(metadata)
        self.worker.progress.connect(self.update_ui)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def toggle_pause(self):
        if self.worker.is_paused:
            self.worker.is_paused = False
            self.pause_btn.setText("⏸")
            self.pause_btn.setStyleSheet("background-color: #3700B3; color: white;")
            self.status_lbl.setText("Resuming...")
        else:
            self.worker.is_paused = True
            self.pause_btn.setText("▶")
            self.pause_btn.setStyleSheet("background-color: #BB86FC; color: black;")
            self.status_lbl.setText("Paused.")

    def cancel_download(self):
        self.worker.is_cancelled = True
        self.worker.is_paused = False
        self.status_lbl.setText("Cancelling...")
        self.status_lbl.setStyleSheet("color: #CF6679;")
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

    def remove_row(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.is_cancelled = True
            self.worker.is_paused = False
        self.setParent(None)
        self.deleteLater()
        self.parent_queue.check_queue_empty()

    def update_ui(self, percent, text):
        self.progress_circle.setValue(percent)
        self.status_lbl.setText(text)

    def on_finished(self):
        self.status_lbl.setText("Complete!")
        self.status_lbl.setStyleSheet("color: #03DAC6;")
        self.progress_circle.setValue(100)
        self.pause_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.remove_btn.setVisible(True)

    def on_error(self, msg):
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet("color: #CF6679;")
        self.pause_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.remove_btn.setVisible(True)

# --- ANA UYGULAMA ---

class Pl2Mp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PL2MP")
        self.setFixedSize(600, 850)
        self.setStyleSheet(STYLE_SHEET)
        
        self.target_dir = ""
        self.raw_entries = [] 
        self.final_metadata = {}
        
        self.base_layout = QVBoxLayout(self)
        self.base_layout.setContentsMargins(0, 0, 0, 0)
        self.base_layout.setSpacing(0)

        # ÜST PANEL: DİNAMİK VE MİNİMALİST KUYRUK
        self.queue_panel = QWidget()
        self.queue_panel.setObjectName("queue_panel")
        self.queue_panel.setVisible(False)
        
        queue_layout = QVBoxLayout(self.queue_panel)
        queue_layout.setContentsMargins(10, 5, 10, 5) # Panel çevresindeki boşluk
        
        self.queue_scroll = QScrollArea()
        self.queue_scroll.setObjectName("queue_scroll")
        self.queue_scroll.setWidgetResizable(True)
        self.queue_scroll.setMaximumHeight(150) # Maksimum yüksekliği kıstık
        
        self.q_container = QWidget()
        self.q_container.setStyleSheet("background: transparent;")
        self.q_vbox = QVBoxLayout(self.q_container)
        self.q_vbox.setAlignment(Qt.AlignTop)
        self.q_vbox.setSpacing(2) # Satırlar arası boşluk sadece 2px
        self.queue_scroll.setWidget(self.q_container)
        
        queue_layout.addWidget(self.queue_scroll)
        self.base_layout.addWidget(self.queue_panel)
        
        # ALT PANEL: SAYFALAR
        self.stack = QStackedWidget()
        self.base_layout.addWidget(self.stack, stretch=1)

        self.unplug_timer = QTimer()
        self.unplug_timer.timeout.connect(self.check_directory_integrity)
        self.unplug_timer.start(2000)
        
        self.init_pages()

    def check_queue_empty(self):
        if self.q_vbox.count() == 0:
            self.queue_panel.setVisible(False)

    def create_nav_bar(self, layout, title_text, target_index):
        nav_container = QWidget()
        nav_container.setFixedHeight(70)
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(15, 10, 15, 10)
        
        back_btn = QPushButton()
        back_btn.setObjectName("back_btn"); back_btn.setFixedSize(44, 44)
        if os.path.exists(ICON_BACK):
            back_btn.setIcon(QIcon(ICON_BACK)); back_btn.setIconSize(QSize(22, 22))
        else: back_btn.setText("←")
        back_btn.setCursor(Qt.PointingHandCursor)
        
        if target_index == 0: back_btn.clicked.connect(self.reset_and_go_home)
        else: back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(target_index))
            
        title_lbl = QLabel(title_text); title_lbl.setObjectName("page_title")
        nav_layout.addWidget(back_btn); nav_layout.addSpacing(15)
        nav_layout.addWidget(title_lbl); nav_layout.addStretch()
        layout.addWidget(nav_container)

    def reset_and_go_home(self):
        self.target_dir = ""
        self.raw_entries = []
        self.final_metadata = {}
        self.stack.setCurrentIndex(0)

    def init_pages(self):
        self.stack.addWidget(self.create_dir_page())     # 0
        self.stack.addWidget(self.create_link_page())    # 1
        self.stack.addWidget(self.create_loading_page()) # 2
        self.stack.addWidget(self.create_sort_page())    # 3
        self.stack.addWidget(self.create_meta_page())    # 4
        self.stack.addWidget(self.create_browse_page())  # 5

    def create_dir_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignCenter)
        logo = QLabel("PL2MP"); logo.setObjectName("main_logo")
        desc = QLabel("Playlist to Music Player"); desc.setAlignment(Qt.AlignCenter)
        btn = QPushButton("Choose a directory"); btn.setFixedWidth(300); btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.select_directory)
        layout.addWidget(logo, alignment=Qt.AlignCenter); layout.addWidget(desc)
        layout.addSpacing(30); layout.addWidget(btn, alignment=Qt.AlignCenter)
        return page

    def create_link_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.create_nav_bar(layout, "Library Manager", 0)
        
        content = QVBoxLayout(); content.setSpacing(25); content.setContentsMargins(25, 10, 25, 30)

        browse_card = QFrame(); browse_card.setObjectName("browse_card")
        b_lay = QVBoxLayout(browse_card); b_lay.setContentsMargins(25, 25, 25, 25)
        b_top = QHBoxLayout()
        b_title = QLabel("Browse"); b_title.setProperty("class", "card_title")
        b_icon = QLabel()
        if os.path.exists(ICON_BROWSE): b_icon.setPixmap(QPixmap(ICON_BROWSE).scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        b_top.addWidget(b_title); b_top.addStretch(); b_top.addWidget(b_icon)
        b_desc = QLabel("Check your current library."); b_desc.setProperty("class", "card_desc")
        b_btn = QPushButton("OPEN LIBRARY"); b_btn.setStyleSheet("background-color: #FFFFFF; color: #1A237E;"); b_btn.setCursor(Qt.PointingHandCursor)
        b_btn.clicked.connect(self.open_browse_page) 
        b_lay.addLayout(b_top); b_lay.addWidget(b_desc); b_lay.addSpacing(25); b_lay.addWidget(b_btn)
        
        add_card = QFrame(); add_card.setObjectName("add_card")
        a_lay = QVBoxLayout(add_card); a_lay.setContentsMargins(25, 25, 25, 25)
        a_top = QHBoxLayout()
        a_title = QLabel("Add"); a_title.setProperty("class", "card_title")
        a_icon = QLabel()
        if os.path.exists(ICON_ADD): a_icon.setPixmap(QPixmap(ICON_ADD).scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        a_top.addWidget(a_title); a_top.addStretch(); a_top.addWidget(a_icon)
        a_desc = QLabel("Download and tag new playlists."); a_desc.setProperty("class", "card_desc")
        a_btn = QPushButton("PASTE AND GO"); a_btn.setStyleSheet("background-color: #03DAC6; color: #000;"); a_btn.setCursor(Qt.PointingHandCursor)
        a_btn.clicked.connect(self.handle_paste_go)
        a_lay.addLayout(a_top); a_lay.addWidget(a_desc); a_lay.addSpacing(25); a_lay.addWidget(a_btn)

        content.addWidget(browse_card); content.addWidget(add_card)
        layout.addLayout(content)
        return page

    def create_loading_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(QLabel("Fetching content..."))
        return page

    def create_sort_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.create_nav_bar(layout, "Sort & Format", 1)
        
        content = QVBoxLayout(); content.setContentsMargins(25, 5, 25, 25); content.setSpacing(15)
        
        btn_layout = QHBoxLayout()
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setCursor(Qt.PointingHandCursor)
        sel_all_btn.setStyleSheet("background-color: #2D1B4D; color: #BB86FC; border-radius: 8px; padding: 8px;")
        sel_all_btn.clicked.connect(self.select_all_items)

        unsel_all_btn = QPushButton("Unselect All")
        unsel_all_btn.setCursor(Qt.PointingHandCursor)
        unsel_all_btn.setStyleSheet("background-color: #333333; color: #AAAAAA; border-radius: 8px; padding: 8px;")
        unsel_all_btn.clicked.connect(self.unselect_all_items)

        btn_layout.addWidget(sel_all_btn)
        btn_layout.addWidget(unsel_all_btn)
        btn_layout.addStretch()
        content.addLayout(btn_layout)

        self.list_widget = QListWidget(); self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        
        nav = QHBoxLayout(); nav.setSpacing(15)
        nav.addWidget(QLabel("Format:"))
        self.name_format = QComboBox()
        self.name_format.addItems([" Artist - Music Name ", " Music Name ", " Music Name - Artist "])
        self.name_format.currentTextChanged.connect(self.refresh_list_preview)
        
        btn = QPushButton(" NEXT → "); btn.setFixedWidth(120); btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.go_to_metadata)
        
        nav.addWidget(self.name_format); nav.addStretch(); nav.addWidget(btn)
        content.addWidget(self.list_widget); content.addLayout(nav); layout.addLayout(content)
        return page

    def create_meta_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.create_nav_bar(layout, "Metadata Edit", 3)
        
        content = QVBoxLayout(); content.setContentsMargins(35, 10, 35, 30); content.setSpacing(15)
        
        self.preview_card = QFrame(); self.preview_card.setObjectName("preview_card"); self.preview_card.setFixedHeight(170)
        p_lay = QHBoxLayout(self.preview_card); p_lay.setContentsMargins(20, 15, 20, 15); p_lay.setSpacing(20)
        self.prev_img = QLabel("Cover"); self.prev_img.setFixedSize(130, 130); self.prev_img.setStyleSheet("background-color: #121212; border-radius: 12px;")
        self.prev_img.setAlignment(Qt.AlignCenter)
        
        i_lay = QVBoxLayout(); i_lay.setSpacing(6)
        g_c = QHBoxLayout(); self.prev_genre = QLabel("GENRE"); self.prev_genre.setObjectName("preview_genre")
        g_c.addWidget(self.prev_genre); g_c.addStretch()
        self.prev_title = QLabel("Song"); self.prev_title.setObjectName("preview_title"); self.prev_title.setWordWrap(True)
        self.prev_artist = QLabel("Artist"); self.prev_artist.setObjectName("preview_sub")
        self.prev_album = QLabel("Album"); self.prev_album.setObjectName("preview_album")
        i_lay.addLayout(g_c); i_lay.addWidget(self.prev_title); i_lay.addWidget(self.prev_artist); i_lay.addWidget(self.prev_album); i_lay.addStretch()
        p_lay.addWidget(self.prev_img); p_lay.addLayout(i_lay); content.addWidget(self.preview_card)
        
        content.addSpacing(10)
        
        sony_genres = sorted(["Alternative", "Blues", "Classical", "Country", "Dance", "Electronic", "Hip-Hop", "Indie", "Jazz", "J-Pop", "K-Pop", "Lo-Fi", "Metal", "New Age", "Pop", "R&B", "Reggae", "Rock", "Soul", "Soundtrack", "Techno"])

        self.cover_in = QLineEdit(); self.cover_in.setPlaceholderText("Album Cover URL...")
        self.cover_in.textChanged.connect(self.start_async_image_load)
        self.album_in = QLineEdit(); self.album_in.setPlaceholderText("Album Name...")
        self.album_in.textChanged.connect(self.update_preview)
        self.artist_in = QLineEdit(); self.artist_in.setPlaceholderText("Artist Name...")
        self.artist_in.textChanged.connect(self.update_preview)
        self.year_in = QLineEdit(); self.year_in.setPlaceholderText("Release Year (e.g., 2026)...")
        self.year_in.textChanged.connect(self.update_preview)
        self.genre_combo = QComboBox(); self.genre_combo.addItems(sony_genres); self.genre_combo.currentTextChanged.connect(self.update_preview)
        
        form_layout = QVBoxLayout(); form_layout.setSpacing(12)
        form_layout.addWidget(QLabel("Cover URL:")); form_layout.addWidget(self.cover_in)
        form_layout.addWidget(QLabel("Album Name:")); form_layout.addWidget(self.album_in)
        form_layout.addWidget(QLabel("Artist:")); form_layout.addWidget(self.artist_in)
        
        row_layout = QHBoxLayout(); row_layout.setSpacing(20)
        col1 = QVBoxLayout(); col1.addWidget(QLabel("Year:")); col1.addWidget(self.year_in)
        col2 = QVBoxLayout(); col2.addWidget(QLabel("Genre:")); col2.addWidget(self.genre_combo)
        row_layout.addLayout(col1, stretch=1); row_layout.addLayout(col2, stretch=1)
        
        form_layout.addLayout(row_layout)
        content.addLayout(form_layout)
        
        content.addStretch()
        btn = QPushButton("ADD TO QUEUE"); btn.setCursor(Qt.PointingHandCursor); btn.setMinimumHeight(50)
        btn.clicked.connect(self.finalize_process)
        content.addWidget(btn); layout.addLayout(content)
        return page

    def create_browse_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.create_nav_bar(layout, "My Library", 1) 
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(20, 10, 20, 20)
        self.grid_layout.setSpacing(20)
        
        self.scroll_area.setWidget(self.grid_container)
        layout.addWidget(self.scroll_area)
        return page

    # --- LOGIC ---

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path: self.target_dir = path; self.stack.setCurrentIndex(1)

    def check_directory_integrity(self):
        if self.target_dir and not os.path.exists(self.target_dir):
            self.unplug_timer.stop(); QMessageBox.warning(self, "Error", "Path lost!"); self.reset_and_go_home(); self.unplug_timer.start(2000)

    def parse_song_title(self, raw, fmt):
        clean = re.sub(r'\[.*?\]|\(.*?\)|\b(Official|Audio|Video|Lyrics|Music Video)\b', '', raw, flags=re.IGNORECASE).strip()
        if "-" in clean:
            pts = clean.split("-", 1)
            if " Artist - Music Name " in fmt: return pts[1].strip()
            if " Music Name - Artist " in fmt: return pts[0].strip()
        return clean

    def refresh_list_preview(self):
        fmt = self.name_format.currentText(); self.list_widget.clear()
        for entry in self.raw_entries:
            parsed = self.parse_song_title(entry['title'], fmt)
            item = QListWidgetItem(parsed)
            item.setData(Qt.UserRole, entry['url']) 
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked) 
            self.list_widget.addItem(item)

    def select_all_items(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Checked)

    def unselect_all_items(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Unchecked)

    def update_preview(self):
        art = self.artist_in.text() or "Artist"; alb = self.album_in.text() or "Album"
        if self.list_widget.count() > 0:
            first_item = self.list_widget.item(0).text()
            self.prev_title.setText(first_item[:30] + "..." if len(first_item) > 30 else first_item)
        self.prev_artist.setText(art); self.prev_album.setText(alb)
        if hasattr(self, 'genre_combo'): self.prev_genre.setText(self.genre_combo.currentText().upper())

    def start_async_image_load(self):
        url = self.cover_in.text().strip()
        if url.startswith("http"):
            self.img_worker = ImageLoader(url); self.img_worker.loaded.connect(self.set_preview_image); self.img_worker.start()

    def set_preview_image(self, pixmap):
        self.prev_img.setText("")
        self.prev_img.setPixmap(pixmap.scaled(self.prev_img.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def handle_paste_go(self):
        url = QApplication.clipboard().text().strip()
        if url.startswith("http"):
            self.stack.setCurrentIndex(2)
            self.fw = FetchWorker(url)
            self.fw.finished.connect(self.on_fetch_done)
            self.fw.error.connect(self.on_fetch_error)
            self.fw.start()
        else: QMessageBox.warning(self, "Error", "No valid link found in clipboard!")

    def on_fetch_error(self, err_msg):
        QMessageBox.critical(self, "Fetch Error", f"Veri çekilirken bir sorun oluştu.\n\nDetay: {err_msg}")
        self.stack.setCurrentIndex(1)

    def open_browse_page(self):
        self.load_library()
        self.stack.setCurrentIndex(5) 

    def load_library(self):
        for i in reversed(range(self.grid_layout.count())): 
            w = self.grid_layout.itemAt(i).widget()
            if w: w.setParent(None)
        if not os.path.exists(self.target_dir): return
        row, col = 0, 0
        albums_found = False
        for artist in os.listdir(self.target_dir):
            ap = os.path.join(self.target_dir, artist)
            if os.path.isdir(ap):
                for album in os.listdir(ap):
                    alp = os.path.join(ap, album)
                    if os.path.isdir(alp):
                        albums_found = True
                        card = self.create_album_card(artist, album, alp)
                        self.grid_layout.addWidget(card, row, col)
                        col += 1
                        if col > 1: col = 0; row += 1
        if not albums_found:
            empty_lbl = QLabel("Library is empty.\nPaste a link to add new albums!")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #666; font-size: 16px;")
            self.grid_layout.addWidget(empty_lbl, 0, 0, 1, 2)
        self.grid_layout.setRowStretch(row + 1, 1)

    def create_album_card(self, artist, album, album_path):
        card = QFrame(); card.setObjectName("album_card"); card.setFixedSize(260, 320)
        cl = QVBoxLayout(card); cl.setContentsMargins(15, 15, 15, 15); cl.setSpacing(10)
        cv = QLabel(); cv.setFixedSize(230, 230); cv.setStyleSheet("background-color: #121212; border-radius: 10px;"); cv.setAlignment(Qt.AlignCenter)
        imgs = glob.glob(os.path.join(album_path, "*.jpg")) + glob.glob(os.path.join(album_path, "*.png"))
        if imgs: cv.setPixmap(QPixmap(imgs[0]).scaled(230, 230, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else: cv.setText("No Cover"); cv.setStyleSheet("background-color: #333; color: #666; border-radius: 10px; font-weight: bold;")
        tl = QLabel(album); tl.setObjectName("album_title")
        if len(album) > 25: tl.setText(album[:22] + "...")
        al = QLabel(artist); al.setObjectName("album_artist")
        if len(artist) > 30: al.setText(artist[:27] + "...")
        cl.addWidget(cv); cl.addWidget(tl); cl.addWidget(al); cl.addStretch()
        return card

    def on_fetch_done(self, entries, meta):
        self.raw_entries = entries
        
        if meta.get('album'):
            self.album_in.setText(meta['album'])
            
        if meta.get('artist'):
            self.artist_in.setText(meta['artist'])
            
        if meta.get('year'):
            self.year_in.setText(str(meta['year']))
            
        if meta.get('genre'):
            index = self.genre_combo.findText(meta['genre'], Qt.MatchContains)
            if index >= 0:
                self.genre_combo.setCurrentIndex(index)
            
        if meta.get('cover_url'):
            self.cover_in.setText(meta['cover_url'])
            
        self.refresh_list_preview()
        self.stack.setCurrentIndex(3)

    def go_to_metadata(self):
        self.update_preview()
        self.stack.setCurrentIndex(4)

    def finalize_process(self):
        songs_to_download = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                songs_to_download.append({
                    "title": item.text(),
                    "url": item.data(Qt.UserRole)
                })

        if not songs_to_download:
            QMessageBox.warning(self, "Uyarı", "Lütfen indirmek için en az bir şarkı seçin!")
            return

        self.final_metadata = {
            "target_dir": self.target_dir,
            "songs": songs_to_download,
            "cover_url": self.cover_in.text(),
            "album": self.album_in.text(),
            "artist": self.artist_in.text(),
            "year": self.year_in.text(),
            "genre": self.genre_combo.currentText()
        }
        
        self.queue_panel.setVisible(True)
        row_widget = DownloadRowWidget(self.final_metadata, self)
        self.q_vbox.insertWidget(0, row_widget)
        
        self.raw_entries = []
        self.cover_in.clear()
        self.album_in.clear()
        self.artist_in.clear()
        self.year_in.clear()
        self.stack.setCurrentIndex(1)

    def closeEvent(self, event):
        active_workers = []
        
        # Kuyruktaki satırları tek tek gezip çalışan bir işlem var mı diye bakıyoruz
        for i in range(self.q_vbox.count()):
            widget = self.q_vbox.itemAt(i).widget()
            if hasattr(widget, 'worker') and widget.worker.isRunning():
                active_workers.append(widget.worker)

        # Eğer devam eden bir işlem varsa özel uyarı kutusunu göster
        if active_workers:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Aktif İndirmeler Var")
            msg_box.setText("Şu anda devam eden indirmeler var.\nUygulamayı kapatırsanız işlemler iptal edilecek.\n\nNe yapmak istersiniz?")
            
            # Kutu arka planı ve yazı rengi (Uygulamanın geneliyle uyumlu)
            msg_box.setStyleSheet("QMessageBox { background-color: #1E1E1E; } QLabel { color: #E0E0E0; font-size: 13px; }")

            # 1. Güvenli Buton (Keep) - Gri
            keep_btn = QPushButton("Keep")
            keep_btn.setCursor(Qt.PointingHandCursor)
            keep_btn.setStyleSheet("""
                QPushButton { background-color: #333333; color: #E0E0E0; padding: 8px 24px; border-radius: 6px; font-weight: bold; }
                QPushButton:hover { background-color: #444444; }
            """)
            
            # 2. Yıkıcı Buton (Quit) - Kırmızı
            quit_btn = QPushButton("Quit")
            quit_btn.setCursor(Qt.PointingHandCursor)
            quit_btn.setStyleSheet("""
                QPushButton { background-color: #CF6679; color: #000000; padding: 8px 24px; border-radius: 6px; font-weight: bold; }
                QPushButton:hover { background-color: #FF7597; }
            """)

            # Butonları kutuya ekle
            msg_box.addButton(keep_btn, QMessageBox.RejectRole)
            msg_box.addButton(quit_btn, QMessageBox.AcceptRole)

            # Uyarı kutusunu çalıştır ve kullanıcının seçimini bekle
            msg_box.exec()

            # Kullanıcı kırmızı "Quit" butonuna bastıysa iptal et ve kapat
            if msg_box.clickedButton() == quit_btn:
                for worker in active_workers:
                    worker.is_cancelled = True
                    worker.is_paused = False
                    worker.quit()
                    worker.wait(1000)
                event.accept()
            # Kullanıcı gri "Keep" butonuna bastıysa (veya çarpıdan kapattıysa) iptal etme, uygulamada kal
            else:
                event.ignore()
        else:
            # Hiçbir işlem yoksa doğrudan kapat
            event.accept()

if __name__ == "__main__":
    check_and_update()
    app = QApplication(sys.argv); window = Pl2Mp(); window.show(); sys.exit(app.exec())