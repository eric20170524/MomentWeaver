import base64
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QToolBar, QPushButton, QLabel, QTabWidget, 
    QTextEdit, QLineEdit, QComboBox, QDialog, QFormLayout, 
    QProgressBar, QMessageBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from smart_asset_kit.core.config import load_config, save_config, SAKConfig
from smart_asset_kit.gui.worker import GenWorker

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 基础配置 (Settings)")
        self.setMinimumWidth(400)
        self.cfg = load_config()

        layout = QFormLayout()
        
        self.provider_cb = QComboBox()
        self.provider_cb.addItems(["xai", "gemini", "minimax"])
        self.provider_cb.setCurrentText(self.cfg.provider)

        self.xai_key_edit = QLineEdit(self.cfg.xai_api_key)
        self.xai_key_edit.setEchoMode(QLineEdit.Password)
        self.xai_key_edit.setPlaceholderText("填写 Grok (xAI) 的 API Key")
        
        self.gemini_key_edit = QLineEdit(self.cfg.gemini_api_key)
        self.gemini_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_key_edit.setPlaceholderText("填写 Google Gemini 的 API Key")
        
        self.eleven_key_edit = QLineEdit(self.cfg.eleven_api_key)
        self.eleven_key_edit.setEchoMode(QLineEdit.Password)
        self.eleven_key_edit.setPlaceholderText("填写 ElevenLabs 的 API Key")

        self.minimax_key_edit = QLineEdit(self.cfg.minimax_api_key)
        self.minimax_key_edit.setEchoMode(QLineEdit.Password)
        self.minimax_key_edit.setPlaceholderText("填写 MiniMax 的 API Key")
        
        layout.addRow("默认 Provider:", self.provider_cb)
        layout.addRow("Grok API Key:", self.xai_key_edit)
        layout.addRow("Gemini API Key:", self.gemini_key_edit)
        layout.addRow("ElevenLabs API Key:", self.eleven_key_edit)
        layout.addRow("MiniMax API Key:", self.minimax_key_edit)

        # Provider specific settings tabs
        self.config_tabs = QTabWidget()
        
        # XAI Tab
        xai_tab = QWidget()
        xai_layout = QFormLayout(xai_tab)
        self.xai_img_edit = QLineEdit(self.cfg.xai_image_model)
        self.xai_vid_edit = QLineEdit(self.cfg.xai_video_model)
        self.xai_aud_edit = QLineEdit(self.cfg.xai_audio_model)
        xai_layout.addRow("Image Model:", self.xai_img_edit)
        xai_layout.addRow("Video Model:", self.xai_vid_edit)
        xai_layout.addRow("Audio Model:", self.xai_aud_edit)
        self.config_tabs.addTab(xai_tab, "XAI Models")
        
        # Gemini Tab
        gemini_tab = QWidget()
        gemini_layout = QFormLayout(gemini_tab)
        self.gemini_img_edit = QLineEdit(self.cfg.gemini_image_model)
        self.gemini_vid_edit = QLineEdit(self.cfg.gemini_video_model)
        self.gemini_aud_edit = QLineEdit(self.cfg.gemini_audio_model)
        gemini_layout.addRow("Image Model:", self.gemini_img_edit)
        gemini_layout.addRow("Video Model:", self.gemini_vid_edit)
        gemini_layout.addRow("Audio Model:", self.gemini_aud_edit)
        self.config_tabs.addTab(gemini_tab, "Gemini Models")

        # MiniMax Tab
        minimax_tab = QWidget()
        minimax_layout = QFormLayout(minimax_tab)
        self.minimax_aud_edit = QLineEdit(self.cfg.minimax_audio_model)
        minimax_layout.addRow("Audio Model:", self.minimax_aud_edit)
        self.config_tabs.addTab(minimax_tab, "MiniMax Models")

        layout.addRow(self.config_tabs)
 
        save_btn = QPushButton("💾 保存配置")
        save_btn.clicked.connect(self.save_and_close)
        layout.addRow(save_btn)
 
        self.setLayout(layout)
 
    def save_and_close(self):
        self.cfg.provider = self.provider_cb.currentText()
        self.cfg.xai_api_key = self.xai_key_edit.text()
        self.cfg.gemini_api_key = self.gemini_key_edit.text()
        self.cfg.eleven_api_key = self.eleven_key_edit.text()
        self.cfg.minimax_api_key = self.minimax_key_edit.text()
        
        self.cfg.xai_image_model = self.xai_img_edit.text()
        self.cfg.xai_video_model = self.xai_vid_edit.text()
        self.cfg.xai_audio_model = self.xai_aud_edit.text()
        
        self.cfg.gemini_image_model = self.gemini_img_edit.text()
        self.cfg.gemini_video_model = self.gemini_vid_edit.text()
        self.cfg.gemini_audio_model = self.gemini_aud_edit.text()
        self.cfg.minimax_audio_model = self.minimax_aud_edit.text()
        save_config(self.cfg)
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Asset Kit - GUI")
        self.resize(800, 650)
        self.is_preview_mode = False
        self.asset_search_results_data = []
        self.init_ui()

    def init_ui(self):
        # macOS Safe: Use QToolBar instead of MenuBar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        settings_action = QAction("⚙️ 基础配置", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        
        # Image Tab
        self.img_tab = QWidget()
        img_layout = QVBoxLayout(self.img_tab)
        self.img_prompt = QTextEdit()
        self.img_prompt.setPlaceholderText("输入图像生成 Prompt...")
        self.img_prompt.setMaximumHeight(80)
        
        img_opts_layout = QHBoxLayout()
        self.img_seamless_chk = QCheckBox("无缝贴图 (Seamless)")
        self.img_pbr_chk = QCheckBox("PBR 基础图 (Normal/Roughness)")
        self.img_remove_bg_chk = QCheckBox("特效增强: 黑底去背 (VFX Alpha Extract)")
        img_opts_layout.addWidget(self.img_seamless_chk)
        img_opts_layout.addWidget(self.img_pbr_chk)
        img_opts_layout.addWidget(self.img_remove_bg_chk)
        img_opts_layout.addStretch()
        
        self.img_btn = QPushButton("🚀 生成图像")
        self.img_btn.clicked.connect(lambda: self.run_generation("image"))
        self.img_preview = QLabel("预览区域 (仅显示 Albedo/原图)")
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setMinimumHeight(300)
        self.img_preview.setStyleSheet("border: 1px solid #ccc;")
        
        img_layout.addWidget(QLabel("Prompt:"))
        img_layout.addWidget(self.img_prompt)
        img_layout.addLayout(img_opts_layout)
        img_layout.addWidget(self.img_btn)
        img_layout.addWidget(self.img_preview)
        
        self.tabs.addTab(self.img_tab, "🖼️ Image")

        # Video Tab
        self.vid_tab = QWidget()
        vid_layout = QVBoxLayout(self.vid_tab)
        self.vid_prompt = QTextEdit()
        self.vid_prompt.setPlaceholderText("输入视频生成 Prompt...")
        self.vid_btn = QPushButton("🚀 生成视频")
        self.vid_btn.clicked.connect(lambda: self.run_generation("video"))
        vid_layout.addWidget(QLabel("Prompt:"))
        vid_layout.addWidget(self.vid_prompt)
        vid_layout.addWidget(self.vid_btn)
        self.tabs.addTab(self.vid_tab, "🎥 Video")

        # 2D Asset Search Tab
        self.asset_tab = QWidget()
        asset_layout = QVBoxLayout(self.asset_tab)

        asset_ctrl_layout = QHBoxLayout()
        self.asset_target_cb = QComboBox()
        self.asset_target_cb.addItem("精灵动画 / Sprites", "sprites")
        self.asset_target_cb.addItem("角色包 / Characters", "characters")
        self.asset_target_cb.addItem("地图图块 / Tilesets", "tilesets")
        self.asset_target_cb.addItem("像素艺术 / Pixel Art", "pixel-art")
        self.asset_target_cb.addItem("UI / HUD", "ui")
        self.asset_target_cb.addItem("道具 / Props", "props")
        self.asset_target_cb.addItem("特效 / VFX", "vfx")

        self.asset_source_cb = QComboBox()
        self.asset_source_cb.addItem("全部来源", "all")
        self.asset_source_cb.addItem("OpenGameArt", "opengameart")
        self.asset_source_cb.addItem("Kenney", "kenney")
        self.asset_source_cb.addItem("itch.io Free 2D", "itch")
        self.asset_source_cb.addItem("GameArt2D", "gameart2d")
        self.asset_source_cb.addItem("CraftPix", "craftpix")
        self.asset_source_cb.addItem("Lospec", "lospec")
        self.asset_source_cb.addItem("SpriteLib", "spritelib")

        asset_ctrl_layout.addWidget(QLabel("素材类型:"))
        asset_ctrl_layout.addWidget(self.asset_target_cb)
        asset_ctrl_layout.addWidget(QLabel("来源:"))
        asset_ctrl_layout.addWidget(self.asset_source_cb)
        
        self.asset_deep_cb = QCheckBox("深度搜索 (Scrape & Score)")
        self.asset_deep_cb.setChecked(False)
        asset_ctrl_layout.addWidget(self.asset_deep_cb)
        
        asset_ctrl_layout.addStretch()

        self.asset_prompt = QTextEdit()
        self.asset_prompt.setPlaceholderText("输入 2D 游戏素材需求，例如：三国街机主角像素风角色精灵动画，或 forest tileset...")
        self.asset_prompt.setMaximumHeight(110)
        self.asset_btn = QPushButton("🔍 搜索 2D 素材")
        self.asset_btn.clicked.connect(lambda: self.run_generation("asset_search"))

        asset_layout.addLayout(asset_ctrl_layout)
        asset_layout.addWidget(QLabel("素材需求:"))
        asset_layout.addWidget(self.asset_prompt)
        asset_layout.addWidget(self.asset_btn)

        # Results table
        self.asset_results_table = QTableWidget()
        self.asset_results_table.setColumnCount(8)
        self.asset_results_table.setHorizontalHeaderLabels([
            "Rank",
            "Score",
            "Top3",
            "来源 (Source)",
            "分类 (Category)",
            "链接 (URL)",
            "授权许可 (License)",
            "适用方向 (Focus)",
        ])
        self.asset_results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.asset_results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.asset_results_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.asset_results_table.doubleClicked.connect(self.on_asset_row_double_clicked)
        self.asset_results_table.itemSelectionChanged.connect(self.on_asset_selection_changed)
        
        # Results action buttons
        asset_btn_layout = QHBoxLayout()
        self.asset_open_btn = QPushButton("🌐 浏览器打开")
        self.asset_open_btn.setEnabled(False)
        self.asset_open_btn.clicked.connect(self.on_open_asset_clicked)
        
        self.asset_copy_btn = QPushButton("📋 复制链接")
        self.asset_copy_btn.setEnabled(False)
        self.asset_copy_btn.clicked.connect(self.on_copy_asset_clicked)
        
        self.asset_notes_btn = QPushButton("💡 授权与下载指南")
        self.asset_notes_btn.setEnabled(False)
        self.asset_notes_btn.clicked.connect(self.on_asset_notes_clicked)

        self.asset_download_btn = QPushButton("⬇️ 下载选中")
        self.asset_download_btn.setEnabled(False)
        self.asset_download_btn.clicked.connect(self.on_download_asset_clicked)

        self.asset_download_top_btn = QPushButton("⬇️ 下载推荐 Top3")
        self.asset_download_top_btn.setEnabled(False)
        self.asset_download_top_btn.clicked.connect(self.on_download_top_assets_clicked)
        
        asset_btn_layout.addWidget(self.asset_open_btn)
        asset_btn_layout.addWidget(self.asset_copy_btn)
        asset_btn_layout.addWidget(self.asset_notes_btn)
        asset_btn_layout.addWidget(self.asset_download_btn)
        asset_btn_layout.addWidget(self.asset_download_top_btn)
        asset_btn_layout.addStretch()
        
        asset_layout.addWidget(QLabel("搜索候选结果 (选择行以进行操作或双击打开):"))
        asset_layout.addWidget(self.asset_results_table)
        asset_layout.addLayout(asset_btn_layout)

        self.tabs.addTab(self.asset_tab, "🔎 Assets")

        # Audio Tab
        self.aud_tab = QWidget()
        aud_layout = QVBoxLayout(self.aud_tab)
        
        # Audio Preset Control Bar
        aud_preset_layout = QHBoxLayout()
        self.aud_preset_cb = QComboBox()
        self.presets = {
            "--- 快速填入预设台词 ---": None,
            "魅姬 (TTS) - 诱惑: 主人……请尽情享用我吧……": {"type": "角色配音 (TTS)", "voice": "【性感/诱惑】成熟御姐音 (推荐魅姬)", "text": "主人……请尽情享用我吧……"},
            "魅姬 (TTS) - 爽快: 嗯……这股灵力好舒服。": {"type": "角色配音 (TTS)", "voice": "【性感/诱惑】成熟御姐音 (推荐魅姬)", "text": "嗯……这股灵力好舒服。"},
            "魅姬 (TTS) - 走火: 啊！这股属性冲撞了我的经脉！": {"type": "角色配音 (TTS)", "voice": "【性感/诱惑】成熟御姐音 (推荐魅姬)", "text": "啊！这股属性冲撞了我的经脉！"},
            "楚薰儿 (TTS) - 爽快: 正中心脉……": {"type": "角色配音 (TTS)", "voice": "【甜美/娇柔】台湾软妹音 (推荐楚薰儿)", "text": "正中心脉……"},
            "楚薰儿 (TTS) - 走火: 走岔了，好难受……": {"type": "角色配音 (TTS)", "voice": "【清冷/孤傲】高冷仙子音", "text": "走岔了，好难受……"},
            "雨馨 (TTS) - 爽快: 就是那里……": {"type": "角色配音 (TTS)", "voice": "【低沉/霸气】冷艳魔女音 (推荐雨馨)", "text": "就是那里……"},
            "雨馨 (TTS) - 走火: 灵力逆流了……": {"type": "角色配音 (TTS)", "voice": "【低沉/霸气】冷艳魔女音 (推荐雨馨)", "text": "灵力逆流了……"},
            "【ElevenLabs】 魅姬 - 诱惑": {"type": "角色配音 (ElevenLabs)", "voice": "【Eleven】性感/成熟 (Rachel)", "text": "主人……请尽情享用我吧……"},
            "【ElevenLabs】 楚薰儿 - 爽快": {"type": "角色配音 (ElevenLabs)", "voice": "【Eleven】甜美/软妹 (Bella)", "text": "嗯……这股灵力好舒服。"},
            "【ElevenLabs】 环境音 (BGM/SFX)": {"type": "环境音效 (ElevenLabs)", "text": "Quiet ancient chinese guzheng playing with flowing water ambient sound"},
            "【MiniMax】 魅姬 - 诱惑": {"type": "角色配音 (MiniMax)", "voice": "【MiniMax】御姐音色 (Yujie)", "text": "主人……请尽情享用我吧……"},
            "【MiniMax】 楚薰儿 - 爽快": {"type": "角色配音 (MiniMax)", "voice": "【MiniMax】甜美女性 (Tianmei)", "text": "嗯……这股灵力好舒服。"},
            "【MiniMax】 音乐生成 (BGM/SFX)": {"type": "环境配乐 (MiniMax BGM)", "text": "Chinese fantasy style, bamboo forest wind, slow Guzheng, zen atmosphere"},
            "Apple Say (Meijia 甜美音) - 诱惑: 主人": {"type": "角色配音 (Apple Say)", "voice": "【台湾/甜美】Meijia", "text": "主人……请尽情享用我吧……"},
            "Apple Say (Flo 温柔音) - 爽快": {"type": "角色配音 (Apple Say)", "voice": "【大陆/温柔】Flo", "text": "嗯……这股灵力好舒服。"},
            "Apple Say (Shelley 沉稳音) - 走火": {"type": "角色配音 (Apple Say)", "voice": "【大陆/沉稳】Shelley", "text": "啊！这股属性冲撞了我的经脉！"},
            "环境音 (BGM) - 宁静古筝": {"type": "环境配乐 (BGM)", "text": "宁静的中国风古筝与流水，适合修仙打坐"}
        }
        self.aud_preset_cb.addItems(list(self.presets.keys()))
        self.aud_preset_cb.currentTextChanged.connect(self.on_preset_changed)
        
        aud_preset_layout.addWidget(QLabel("实战预设:"))
        aud_preset_layout.addWidget(self.aud_preset_cb)
        aud_preset_layout.addStretch()
        aud_layout.addLayout(aud_preset_layout)
 
        # Audio Control Bar
        aud_ctrl_layout = QHBoxLayout()
        self.aud_type_cb = QComboBox()
        self.aud_type_cb.addItems(["角色配音 (Apple Say)", "角色配音 (TTS)", "角色配音 (ElevenLabs)", "角色配音 (MiniMax)", "环境配乐 (BGM)", "环境配乐 (MiniMax BGM)", "环境音效 (MiniMax SFX)", "环境音效 (ElevenLabs)", "开源素材检索 (Pixabay BGM)", "开源素材检索 (Pixabay SFX)"])
        self.aud_type_cb.currentTextChanged.connect(self.on_aud_type_changed)
        
        self.aud_voice_cb = QComboBox()
        
        self.aud_preview_btn = QPushButton("🔊 试听")
        self.aud_preview_btn.clicked.connect(self.preview_voice)
        self.aud_preview_btn.setToolTip("快速试听当前选择的音色")
        
        self.aud_seamless_chk = QCheckBox("启用无缝循环 (Seamless Loop)")
        self.aud_seamless_chk.setVisible(False)
        
        aud_ctrl_layout.addWidget(QLabel("生成类型:"))
        aud_ctrl_layout.addWidget(self.aud_type_cb)
        aud_ctrl_layout.addWidget(QLabel("配音音色:"))
        aud_ctrl_layout.addWidget(self.aud_voice_cb)
        aud_ctrl_layout.addWidget(self.aud_preview_btn)
        aud_ctrl_layout.addWidget(self.aud_seamless_chk)
        aud_ctrl_layout.addStretch()
        
        aud_layout.addLayout(aud_ctrl_layout)

        self.aud_prompt = QTextEdit()
        self.aud_prompt.setPlaceholderText("输入音频/TTS Prompt... (如果是 TTS，请输入要朗读的文本)")
        self.aud_btn = QPushButton("🚀 生成音频")
        self.aud_btn.clicked.connect(lambda: self.run_generation("audio"))
        aud_layout.addWidget(QLabel("Prompt/Text:"))
        aud_layout.addWidget(self.aud_prompt)
        aud_layout.addWidget(self.aud_btn)
        self.tabs.addTab(self.aud_tab, "🎵 Audio")

        main_layout.addWidget(self.tabs)

        # Output Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        main_layout.addWidget(QLabel("日志输出:"))
        main_layout.addWidget(self.log_output)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0) # Indeterminate
        main_layout.addWidget(self.progress)
        
        # Trigger default population
        self.on_aud_type_changed(self.aud_type_cb.currentText())

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def on_preset_changed(self, text):
        preset = self.presets.get(text)
        if preset:
            self.aud_type_cb.setCurrentText(preset["type"])
            if "voice" in preset:
                self.aud_voice_cb.setCurrentText(preset["voice"])
            self.aud_prompt.setText(preset["text"])

    def preview_voice(self):
        aud_type = self.aud_type_cb.currentText()
        voice = self.aud_voice_cb.currentText()
        text = "您好，这是我的声音试听。"

        if "Apple Say" in aud_type:
            # Extract actual voice name (e.g., "【台湾/甜美】Meijia" -> "Meijia")
            real_voice = voice.split("】")[-1].strip() if "】" in voice else voice
            import subprocess
            subprocess.Popen(["say", "-v", real_voice, text])
            self.log(f"🔊 正在本地试听 Apple Say 音色: {real_voice}...")
        elif "TTS" in aud_type:
            self.is_preview_mode = True
            self.log(f"🔊 正在为您拉取大模型音色试听，请稍候...")
            self.set_ui_enabled(False)
            self.progress.setVisible(True)
            self.current_task_type = "audio"
            
            # 使用临时 worker，避免覆盖 self.worker 导致其他问题
            self.worker = GenWorker("audio", text, aud_type="tts", voice=voice)
            self.worker.finished_task.connect(self.on_generation_finished)
            self.worker.error_task.connect(self.on_generation_error)
            self.worker.start()
        elif "MiniMax" in aud_type:
            self.is_preview_mode = True
            self.log(f"🔊 正在为您拉取 MiniMax 音色试听，请稍候...")
            self.set_ui_enabled(False)
            self.progress.setVisible(True)
            self.current_task_type = "audio"
            
            self.worker = GenWorker("audio", text, aud_type="minimax_tts", voice=voice)
            self.worker.finished_task.connect(self.on_generation_finished)
            self.worker.error_task.connect(self.on_generation_error)
            self.worker.start()

    def on_aud_type_changed(self, text):
        self.aud_voice_cb.clear()
        if "Apple Say" in text:
            self.aud_voice_cb.addItems([
                "【台湾/甜美】Meijia",
                "【大陆/温柔】Flo",
                "【大陆/沉稳】Shelley",
                "【大陆/清脆】Eddy"
            ])
            self.aud_voice_cb.setVisible(True)
            self.aud_preview_btn.setVisible(True)
            self.aud_seamless_chk.setVisible(False)
            self.aud_prompt.setPlaceholderText("输入角色配音 (Apple Say) 要朗读的文本内容...")
            self.aud_btn.setText("🚀 生成音频")
        elif "TTS" in text and "ElevenLabs" not in text and "MiniMax" not in text:
            self.aud_voice_cb.addItems([
                "【性感/诱惑】成熟御姐音 (推荐魅姬)",
                "【甜美/娇柔】台湾软妹音 (推荐楚薰儿)",
                "【清冷/孤傲】高冷仙子音",
                "【低沉/霸气】冷艳魔女音 (推荐雨馨)"
            ])
            self.aud_voice_cb.setVisible(True)
            self.aud_preview_btn.setVisible(True)
            self.aud_seamless_chk.setVisible(False)
            self.aud_prompt.setPlaceholderText("输入角色配音 (TTS) 要朗读的文本内容...")
            self.aud_btn.setText("🚀 生成音频")
        elif "ElevenLabs" in text and "配音" in text:
            self.aud_voice_cb.addItems([
                "【Eleven】性感/成熟 (Rachel)",
                "【Eleven】甜美/软妹 (Bella)",
                "【Eleven】高冷/御姐 (Charlotte)",
                "【Eleven】男声/磁性 (Drew)"
            ])
            self.aud_voice_cb.setVisible(True)
            self.aud_preview_btn.setVisible(True)
            self.aud_seamless_chk.setVisible(False)
            self.aud_prompt.setPlaceholderText("输入角色配音 (ElevenLabs) 要朗读的文本内容...")
            self.aud_btn.setText("🚀 生成音频")
        elif "MiniMax" in text and "配音" in text:
            self.aud_voice_cb.addItems([
                "【MiniMax】青涩青年 (Qingse)",
                "【MiniMax】精英青年 (Jingying)",
                "【MiniMax】少女音色 (Shaonv)",
                "【MiniMax】御姐音色 (Yujie)",
                "【MiniMax】甜美女性 (Tianmei)"
            ])
            self.aud_voice_cb.setVisible(True)
            self.aud_preview_btn.setVisible(True)
            self.aud_seamless_chk.setVisible(False)
            self.aud_prompt.setPlaceholderText("输入角色配音 (MiniMax) 要朗读的文本内容...")
            self.aud_btn.setText("🚀 生成音频")
        elif "MiniMax" in text and "BGM" in text:
            self.aud_voice_cb.setVisible(False)
            self.aud_preview_btn.setVisible(False)
            self.aud_seamless_chk.setVisible(True)
            self.aud_prompt.setPlaceholderText("输入想要生成的背景音乐 Prompt (如: Chinese fantasy style, bamboo forest wind)...")
            self.aud_btn.setText("🚀 生成音频")
        elif "MiniMax" in text and "SFX" in text:
            self.aud_voice_cb.setVisible(False)
            self.aud_preview_btn.setVisible(False)
            self.aud_seamless_chk.setVisible(True)
            self.aud_prompt.setPlaceholderText("输入想要生成的环境音效 Prompt (如: Sword clashing sound effects)...")
            self.aud_btn.setText("🚀 生成音频")
        elif "ElevenLabs" in text and "环境音效" in text:
            self.aud_voice_cb.setVisible(False)
            self.aud_preview_btn.setVisible(False)
            self.aud_seamless_chk.setVisible(True)
            self.aud_prompt.setPlaceholderText("输入想要生成的环境音 (如: Ancient chinese guzheng with flowing water)...")
            self.aud_btn.setText("🚀 生成音频")
        elif "Pixabay" in text:
            self.aud_voice_cb.setVisible(False)
            self.aud_preview_btn.setVisible(False)
            self.aud_seamless_chk.setVisible(False) # 浏览器检索无需预选此项
            self.aud_prompt.setPlaceholderText("输入想要寻找的免版税音频 (中文即可，如: 宁静的竹林风声，古风竹笛)... 工具将自动提纯关键词并唤起浏览器。")
            self.aud_btn.setText("🔍 智能检索 (浏览器)")
        else:
            self.aud_voice_cb.setVisible(False)
            self.aud_preview_btn.setVisible(False)
            self.aud_seamless_chk.setVisible(True)
            self.aud_prompt.setPlaceholderText("输入环境配乐 (BGM) 的 Prompt (例如：宁静的中国风古筝环境音)...")
            self.aud_btn.setText("🚀 生成音频")

    def run_generation(self, task_type):
        prompt = ""
        kwargs = {}
        if task_type == "image":
            prompt = self.img_prompt.toPlainText().strip()
            kwargs["seamless"] = self.img_seamless_chk.isChecked()
            kwargs["pbr"] = self.img_pbr_chk.isChecked()
            kwargs["remove_bg"] = self.img_remove_bg_chk.isChecked()
        elif task_type == "video":
            prompt = self.vid_prompt.toPlainText().strip()
        elif task_type == "asset_search":
            prompt = self.asset_prompt.toPlainText().strip()
            kwargs["target"] = self.asset_target_cb.currentData()
            kwargs["source"] = self.asset_source_cb.currentData()
            kwargs["deep"] = self.asset_deep_cb.isChecked()
        elif task_type == "audio":
            prompt = self.aud_prompt.toPlainText().strip()
            aud_type = self.aud_type_cb.currentText()
            if "Apple Say" in aud_type:
                kwargs["aud_type"] = "apple_say"
                kwargs["voice"] = self.aud_voice_cb.currentText()
            elif "TTS" in aud_type and "ElevenLabs" not in aud_type and "MiniMax" not in aud_type:
                kwargs["aud_type"] = "tts"
                kwargs["voice"] = self.aud_voice_cb.currentText()
            elif "ElevenLabs" in aud_type and "配音" in aud_type:
                kwargs["aud_type"] = "eleven_tts"
                kwargs["voice"] = self.aud_voice_cb.currentText()
            elif "ElevenLabs" in aud_type and "环境" in aud_type:
                kwargs["aud_type"] = "eleven_sfx"
                kwargs["seamless"] = self.aud_seamless_chk.isChecked()
            elif "MiniMax" in aud_type and "配音" in aud_type:
                kwargs["aud_type"] = "minimax_tts"
                kwargs["voice"] = self.aud_voice_cb.currentText()
            elif "MiniMax" in aud_type and "BGM" in aud_type:
                kwargs["aud_type"] = "minimax_bgm"
                kwargs["seamless"] = self.aud_seamless_chk.isChecked()
            elif "MiniMax" in aud_type and "SFX" in aud_type:
                kwargs["aud_type"] = "minimax_sfx"
                kwargs["seamless"] = self.aud_seamless_chk.isChecked()
            elif "Pixabay" in aud_type:
                import urllib.parse
                import webbrowser
                # 将中文用底层的 APIClient 做一波中英翻译
                self.log("🔍 正在翻译关键词并唤起 Pixabay...")
                
                # We do translation asynchronously using a simple prompt
                # But to avoid freezing GUI, we should technically use the worker.
                kwargs["aud_type"] = "pixabay"
                kwargs["pixabay_target"] = "music" if "BGM" in aud_type else "sound-effects"
            else:
                kwargs["aud_type"] = "bgm"
                kwargs["seamless"] = self.aud_seamless_chk.isChecked()

        if not prompt:
            QMessageBox.warning(self, "警告", "Prompt/Text 不能为空！")
            return

        if task_type == "asset_search":
            self.log("开始搜索 2D 素材... 请稍候。")
        else:
            self.log(f"开始生成 {task_type}... 请稍候。")
        self.set_ui_enabled(False)
        self.progress.setVisible(True)
        self.current_task_type = task_type
        self.is_preview_mode = False # Reset preview mode on normal generation

        self.worker = GenWorker(task_type, prompt, **kwargs)
        self.worker.finished_task.connect(self.on_generation_finished)
        self.worker.error_task.connect(self.on_generation_error)
        self.worker.start()

    def on_generation_finished(self, results):
        self.set_ui_enabled(True)
        self.progress.setVisible(False)
        if self.current_task_type == "asset_search":
            self.log(f"搜索完成，共返回 {len(results)} 个候选入口。")
            self.asset_results_table.setRowCount(0)
            self.asset_search_results_data = []
            self.asset_open_btn.setEnabled(False)
            self.asset_copy_btn.setEnabled(False)
            self.asset_notes_btn.setEnabled(False)
            self.asset_download_btn.setEnabled(False)
            self.asset_download_top_btn.setEnabled(False)
        else:
            self.log(f"生成成功，共返回 {len(results)} 个结果。")
        
        import os
        import time

        for idx, res in enumerate(results):
            if res.startswith("data:image"):
                b64_data = res.split("base64,")[1] if "base64," in res else res
                
                pbr_type = "albedo"
                if "pbr_type=normal" in res: pbr_type = "normal"
                elif "pbr_type=roughness" in res: pbr_type = "roughness"
                
                out_dir = os.path.abspath(os.path.join(os.getcwd(), "output", "images"))
                os.makedirs(out_dir, exist_ok=True)
                filepath = os.path.join(out_dir, f"img_{int(time.time())}_{idx}_{pbr_type}.png")
                
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                self.log(f"✅ 图像保存至: {filepath}")
                
                # Only show the main Albedo image in the preview box
                if pbr_type == "albedo":
                    pixmap = QPixmap()
                    pixmap.loadFromData(base64.b64decode(b64_data))
                    self.img_preview.setPixmap(pixmap.scaled(self.img_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            elif res.startswith("action:scraped_asset:"):
                parts = res.split("|")
                url = parts[0].replace("action:scraped_asset:", "")
                data = {}
                for part in parts[1:]:
                    if ":" in part:
                        key, value = part.split(":", 1)
                        data[key] = value
                
                import urllib.parse
                title = urllib.parse.unquote(data.get("title", ""))
                source = urllib.parse.unquote(data.get("source", ""))
                desc = urllib.parse.unquote(data.get("desc", ""))
                license_hint = urllib.parse.unquote(data.get("license", ""))
                score = data.get("score", "0.0")
                reason = urllib.parse.unquote(data.get("reason", ""))
                preview = urllib.parse.unquote(data.get("preview", ""))
                downloads = urllib.parse.unquote(data.get("downloads", ""))
                
                target = self.asset_target_cb.currentText().split("/")[-1].strip()
                
                self.asset_search_results_data.append({
                    "url": url,
                    "source": source,
                    "target": target,
                    "title": title,
                    "desc": desc,
                    "license": license_hint,
                    "score": score,
                    "reason": reason,
                    "preview": preview,
                    "downloads": downloads,
                    "kind": "scraped_asset"
                })
                
                row = self.asset_results_table.rowCount()
                self.asset_results_table.insertRow(row)
                self.asset_results_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                self.asset_results_table.setItem(row, 1, QTableWidgetItem(f"{float(score):.1f}/10.0"))
                self.asset_results_table.setItem(row, 2, QTableWidgetItem("推荐" if row < 3 else ""))
                self.asset_results_table.setItem(row, 3, QTableWidgetItem(source))
                self.asset_results_table.setItem(row, 4, QTableWidgetItem(title))
                self.asset_results_table.setItem(row, 5, QTableWidgetItem(url))
                self.asset_results_table.setItem(row, 6, QTableWidgetItem(license_hint))
                self.asset_results_table.setItem(row, 7, QTableWidgetItem(reason))
                
                self.asset_download_btn.setEnabled(True)
                self.asset_download_top_btn.setEnabled(True)
            elif res.startswith("action:open_url"):
                parts = res.split("|")
                url = parts[0].replace("action:open_url:", "")
                data = {}
                for part in parts[1:]:
                    if ":" in part:
                        key, value = part.split(":", 1)
                        data[key] = value
                kw = data.get("keyword", "")
                
                import webbrowser
                should_open = data.get("open", "1") != "0"
                if should_open:
                    webbrowser.open(url)

                if data.get("kind") == "asset_search":
                    self.log(f"✅ 已提取 2D 素材搜索关键词: '{kw}'")
                    self.log(f"🔗 {data.get('source', 'asset')} ({data.get('target', '2d')}):")
                    self.log(url)
                    self.log(f"📜 授权提示: {data.get('license', '请查看素材页授权')}")
                    self.log(f"🎯 适用方向: {data.get('focus', '2D game assets')}")
                    self.log(f"💡 {data.get('notes', '下载前请确认来源、作者和授权。')}")
                    
                    source = data.get("source", "asset")
                    target = data.get("target", "2d")
                    license_hint = data.get("license", "请查看素材页授权")
                    focus = data.get("focus", "2D game assets")
                    notes = data.get("notes", "下载前请确认来源、作者和授权。")
                    rank = int(data.get("rank", idx + 1))
                    score = int(data.get("score", 0))
                    recommended = data.get("recommended", "0") == "1"
                    score_reasons = [reason.strip() for reason in data.get("reasons", "").split(";") if reason.strip()]
                    
                    self.asset_search_results_data.append({
                        "url": url,
                        "source": source,
                        "target": target,
                        "license": license_hint,
                        "focus": focus,
                        "notes": notes,
                        "keywords": kw,
                        "rank": rank,
                        "score": score,
                        "recommended": recommended,
                        "score_reasons": score_reasons,
                    })
                    
                    row = self.asset_results_table.rowCount()
                    self.asset_results_table.insertRow(row)
                    self.asset_results_table.setItem(row, 0, QTableWidgetItem(str(rank)))
                    self.asset_results_table.setItem(row, 1, QTableWidgetItem(f"{score}/100"))
                    self.asset_results_table.setItem(row, 2, QTableWidgetItem("推荐" if recommended else ""))
                    self.asset_results_table.setItem(row, 3, QTableWidgetItem(source))
                    self.asset_results_table.setItem(row, 4, QTableWidgetItem(target))
                    self.asset_results_table.setItem(row, 5, QTableWidgetItem(url))
                    self.asset_results_table.setItem(row, 6, QTableWidgetItem(license_hint))
                    self.asset_results_table.setItem(row, 7, QTableWidgetItem(focus))
                    self.asset_download_top_btn.setEnabled(True)
                else:
                    self.log(f"✅ 已为您提取英文搜索关键词: '{kw}'")
                    self.log(f"🔗 已成功在默认浏览器中打开 Pixabay 免版税素材库:")
                    self.log(url)
                    self.log("💡 提示：在网页端试听并点击 Download 获取 MP3/WAV 后，你可以手动在本地代码中放入游戏目录。")
            elif res.startswith("data:audio") or self.current_task_type == "audio":
                try:
                    if res.startswith(("http://", "https://")):
                        import requests
                        self.log(f"📥 正在下载生成的音乐/音频: {res}...")
                        audio_resp = requests.get(res)
                        audio_resp.raise_for_status()
                        audio_bytes = audio_resp.content
                    else:
                        b64_data = res.split(",")[1] if "," in res else res
                        audio_bytes = base64.b64decode(b64_data)
                    
                    # Ensure output directory exists
                    out_dir = os.path.abspath(os.path.join(os.getcwd(), "output", "audio"))
                    os.makedirs(out_dir, exist_ok=True)
                    
                    # Convert raw PCM to MP3 if it's L16 (like from Gemini TTS)
                    if not res.startswith(("http://", "https://")) and ("audio/L16" in res or "audio/pcm" in res):
                        from pydub import AudioSegment
                        import tempfile
                        
                        # Gemini returns 24000Hz, 1 channel, 16-bit PCM by default
                        aud = AudioSegment(data=audio_bytes, sample_width=2, frame_rate=24000, channels=1)
                        filepath = os.path.join(out_dir, f"audio_{int(time.time())}.mp3")
                        aud.export(filepath, format="mp3", bitrate="192k")
                    else:
                        filepath = os.path.join(out_dir, f"audio_{int(time.time())}.mp3")
                        with open(filepath, "wb") as f:
                            f.write(audio_bytes)
                            
                    if self.is_preview_mode:
                        import subprocess
                        subprocess.Popen(["afplay", filepath])
                        self.log(f"▶️ 正在播放下载的音色试听...")
                        self.is_preview_mode = False
                    else:
                        self.log(f"✅ 音频已自动保存至:\n{filepath}\n(可复制到游戏目录对应的角色 voice/ 文件夹中并改名)")
                except Exception as e:
                    self.log(f"❌ 音频保存失败: {e}")
                    self.is_preview_mode = False

    def on_generation_error(self, error_msg):
        self.set_ui_enabled(True)
        self.progress.setVisible(False)
        self.is_preview_mode = False
        self.log(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", str(error_msg))

    def set_ui_enabled(self, enabled):
        self.tabs.setEnabled(enabled)

    def log(self, msg):
        self.log_output.append(msg)

    def on_asset_selection_changed(self):
        selected_rows = self.asset_results_table.selectedItems()
        has_selection = len(selected_rows) > 0
        self.asset_open_btn.setEnabled(has_selection)
        self.asset_copy_btn.setEnabled(has_selection)
        self.asset_notes_btn.setEnabled(has_selection)
        self.asset_download_btn.setEnabled(has_selection)

    def on_asset_row_double_clicked(self, index):
        row = index.row()
        if hasattr(self, "asset_search_results_data") and row < len(self.asset_search_results_data):
            url = self.asset_search_results_data[row]["url"]
            import webbrowser
            webbrowser.open(url)
            self.log(f"🌐 浏览器打开: {url}")

    def on_open_asset_clicked(self):
        row = self.asset_results_table.currentRow()
        if hasattr(self, "asset_search_results_data") and 0 <= row < len(self.asset_search_results_data):
            url = self.asset_search_results_data[row]["url"]
            import webbrowser
            webbrowser.open(url)
            self.log(f"🌐 浏览器打开: {url}")

    def on_copy_asset_clicked(self):
        row = self.asset_results_table.currentRow()
        if hasattr(self, "asset_search_results_data") and 0 <= row < len(self.asset_search_results_data):
            url = self.asset_search_results_data[row]["url"]
            from PySide6.QtGui import QGuiApplication
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(url)
            self.log(f"📋 复制链接成功: {url}")
            QMessageBox.information(self, "提示", "链接已成功复制到剪贴板！")

    def on_asset_notes_clicked(self):
        row = self.asset_results_table.currentRow()
        if hasattr(self, "asset_search_results_data") and 0 <= row < len(self.asset_search_results_data):
            item = self.asset_search_results_data[row]
            source = item["source"]
            license_hint = item["license"]
            
            if item.get("kind") == "scraped_asset":
                title = item["title"]
                desc = item["desc"]
                reason = item["reason"]
                info_text = (
                    f"【素材标题】: {title}\n"
                    f"【素材来源】: {source}\n"
                    f"【授权许可】: {license_hint}\n\n"
                    f"【素材描述】:\n{desc}\n\n"
                    f"【推荐理由】:\n{reason}\n\n"
                    f"提示：如果该素材有下载地址，您可以直接在下方点击“一键下载到本地”进行自动获取并解压。"
                )
            else:
                notes = item["notes"]
                info_text = (
                    f"【素材来源】: {source}\n"
                    f"【授权许可】: {license_hint}\n\n"
                    f"【下载与使用指南】:\n{notes}\n\n"
                    f"提示：点击“浏览器打开”后，请在对应的素材网站中下载资源包（通常为 ZIP/RAR/PNG），"
                    f"并解压至项目推荐目录，如 `output/images/` 下对应的分类目录中。"
                )
            QMessageBox.information(self, f"{source} 授权与下载指南", info_text)

    def _asset_result_from_item(self, item):
        from smart_asset_kit.core.asset_search import AssetSearchResult

        return AssetSearchResult(
            source=item["source"],
            target=item["target"],
            keywords=item["keywords"],
            url=item["url"],
            license_hint=item["license"],
            focus=item["focus"],
            notes=item["notes"],
            score=item["score"],
            rank=item["rank"],
            recommended=item["recommended"],
            score_reasons=item["score_reasons"],
        )

    def _asset_download_dir(self):
        import os
        return os.path.abspath(os.path.join(os.getcwd(), "output", "images", "asset-downloads"))

    def _safe_asset_dir_name(self, item, idx=None):
        import re

        safe_title = re.sub(r"[^a-zA-Z0-9._-]+", "-", item.get("title", "asset").lower()).strip("-._") or "asset"
        prefix = f"{idx:02d}-" if idx is not None else ""
        return f"{prefix}{item.get('source', 'asset')}-{safe_title}"

    def on_download_asset_clicked(self):
        row = self.asset_results_table.currentRow()
        if hasattr(self, "asset_search_results_data") and 0 <= row < len(self.asset_search_results_data):
            item = self.asset_search_results_data[row]
            if item.get("kind") == "scraped_asset":
                if not item.get("downloads"):
                    self.log("ℹ️ 该素材没有直接文件链接，将保存 manifest 和来源快捷方式。")
                    
                import os
                dest_dir = os.path.join(self._asset_download_dir(), self._safe_asset_dir_name(item))
                self.log(f"📥 开始下载素材 '{item['title']}' 到: {dest_dir}...")
                self.set_ui_enabled(False)
                self.progress.setVisible(True)
                
                from smart_asset_kit.gui.worker import DownloadWorker
                self.download_worker = DownloadWorker(item, dest_dir)
                self.download_worker.finished_download.connect(self.on_download_finished)
                self.download_worker.error_download.connect(self.on_download_error)
                self.download_worker.start()
            else:
                from smart_asset_kit.core.asset_search import download_asset_result

                result = self._asset_result_from_item(self.asset_search_results_data[row])
                download = download_asset_result(result, out_dir=self._asset_download_dir())
                self.log(f"⬇️ {download.source} {download.status}: {download.saved_path}")
                self.log(f"🧾 Manifest: {download.manifest_path}")
                self.log(download.message)
                QMessageBox.information(self, "下载结果", f"{download.status}\n{download.saved_path}\n\n{download.message}")

    def on_download_finished(self, files):
        self.set_ui_enabled(True)
        self.progress.setVisible(False)
        self.log(f"✅ 素材下载并解压成功！共获取 {len(files)} 个文件/目录。")
        for f in files:
            self.log(f" - {f}")
        QMessageBox.information(self, "成功", f"素材已成功下载并提取到本地！\n共 {len(files)} 个文件/目录。")

    def on_download_error(self, error_msg):
        self.set_ui_enabled(True)
        self.progress.setVisible(False)
        self.log(f"❌ 下载失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"下载过程中发生错误: {error_msg}")

    def on_download_top_assets_clicked(self):
        if not hasattr(self, "asset_search_results_data") or not self.asset_search_results_data:
            return

        first_item = self.asset_search_results_data[0]
        if first_item.get("kind") == "scraped_asset":
            from smart_asset_kit.gui.worker import DownloadWorker

            top_items = self.asset_search_results_data[:3]
            self.log(f"📥 开始一键下载/留档推荐 Top{len(top_items)} 到: {self._asset_download_dir()}...")
            self.set_ui_enabled(False)
            self.progress.setVisible(True)
            self.download_worker = DownloadWorker(top_items, self._asset_download_dir())
            self.download_worker.finished_download.connect(self.on_download_finished)
            self.download_worker.error_download.connect(self.on_download_error)
            self.download_worker.start()
        else:
            from smart_asset_kit.core.asset_search import download_asset_result

            top_items = [
                item for item in self.asset_search_results_data
                if item.get("recommended")
            ][:3]
            if not top_items:
                top_items = self.asset_search_results_data[:3]

            summaries = []
            for item in top_items:
                result = self._asset_result_from_item(item)
                download = download_asset_result(result, out_dir=self._asset_download_dir())
                summaries.append(f"{download.source}: {download.status} -> {download.saved_path}")
                self.log(f"⬇️ {download.source} {download.status}: {download.saved_path}")
                self.log(f"🧾 Manifest: {download.manifest_path}")
                self.log(download.message)

            QMessageBox.information(self, "推荐 Top3 下载结果", "\n".join(summaries))
