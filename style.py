STYLE_SHEET = """
QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: -apple-system, "Helvetica Neue", Helvetica, "Roboto", Arial, sans-serif;
}

QLabel { background: transparent; }

#page_title {
    font-size: 22px;
    font-weight: 800;
    color: #FFFFFF;
    background: transparent;
}

#main_logo {
    font-size: 70px;
    color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #BB86FC, stop:1 #03DAC6);
    font-weight: bold;
    background: transparent;
}

#path_label {
    font-size: 11px; color: #03DAC6; background-color: #1A1A1A;
    padding: 10px; border-radius: 8px; border: 1px solid #2A2A2A;
}

#browse_card {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #1A237E, stop:1 #283593);
    border-radius: 25px;
}

#add_card {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #4A148C, stop:1 #6A1B9A);
    border-radius: 25px;
}

.card_title { font-size: 26px; font-weight: 900; color: #FFFFFF; background: transparent; }
.card_desc { font-size: 13px; color: rgba(255, 255, 255, 0.8); background: transparent; }

QPushButton {
    background-color: #BB86FC; color: #000; border-radius: 12px;
    padding: 12px; font-weight: bold; border: none;
}
QPushButton:hover { background-color: #D7B4FF; }

#back_btn { background-color: transparent; border: none; }
#back_btn:hover { background-color: rgba(255, 255, 255, 0.1); border-radius: 22px; }

QLineEdit, QComboBox {
    background-color: #1E1E1E; border: 1px solid #2A2A2A; border-radius: 8px;
    padding: 12px; color: #FFFFFF; font-size: 13px;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #BB86FC; }

QListWidget { background-color: #1A1A1A; border-radius: 15px; border: 1px solid #2A2A2A; outline: none; }
QListWidget::item { background-color: #242424; margin: 5px; padding: 15px; border-radius: 10px; }
QListWidget::item:selected { background-color: #3700B3; color: white; }

QListWidget::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 2px solid #555; background-color: #1A1A1A; margin-right: 8px;
}
QListWidget::indicator:checked { background-color: #BB86FC; border: 2px solid #BB86FC; }
QListWidget::indicator:hover { border: 2px solid #BB86FC; }

#preview_card { background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #1E1E1E, stop:1 #252525); border-radius: 20px; border: 1px solid #333333; }
#preview_title { font-size: 18px; font-weight: 800; color: #FFFFFF; }
#preview_sub { font-size: 13px; color: #BBBBBB; }
#preview_album { font-size: 11px; color: #777777; font-style: italic; }
#preview_genre { font-size: 9px; color: #BB86FC; background-color: #2D1B4D; padding: 4px 10px; border-radius: 6px; font-weight: bold; }

#album_card { background-color: #1E1E1E; border-radius: 15px; border: 1px solid #2A2A2A; }
#album_card:hover { border: 1px solid #BB86FC; }
#album_title { font-size: 14px; font-weight: bold; color: #FFFFFF; }
#album_artist { font-size: 11px; color: #AAAAAA; }

QScrollBar:vertical { border: none; background: #121212; width: 10px; }
QScrollBar::handle:vertical { background: #333; min-height: 30px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #BB86FC; }

/* --- MİNİMALİST KUYRUK (QUEUE) STİLLERİ --- */
#queue_panel {
    background-color: #0F0F0F;
    border-bottom: 1px solid #2A2A2A;
}
#queue_scroll { background-color: transparent; border: none; }
#download_row {
    background-color: #1A1A1A;
    border-radius: 6px;
    border: 1px solid #2A2A2A;
    margin-bottom: 0px;
}
.queue_btn_compact {
    padding: 0px;
    border-radius: 4px;
    font-size: 12px;
}

/* --- ULTRA-MİNİMALİST KAYDIRMA ÇUBUĞU --- */
QScrollBar:vertical { 
    border: none; 
    background: transparent; /* Arka planı tamamen görünmez yapar */
    width: 6px; /* İncecik, zarif bir genişlik */
    margin: 0px; 
}
QScrollBar::handle:vertical { 
    background: #333333; 
    min-height: 40px; 
    border-radius: 3px; 
}
QScrollBar::handle:vertical:hover { 
    background: #BB86FC; /* Üzerine gelince neon mor parlar */
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px; /* Üstteki ve alttaki o çirkin ok butonlarını tamamen yok eder */
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none; /* Çubuğun arkasında kalan izi gizler */
}
"""