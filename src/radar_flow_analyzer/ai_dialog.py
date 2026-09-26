from __future__ import annotations

from collections.abc import Callable
from html import escape

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .ai import AiClient, AiError, PROVIDERS, environment_key


class ModelLoader(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def run(self) -> None:
        try:
            models = AiClient("ollama", timeout_seconds=5).list_ollama_models()
            if not self.isInterruptionRequested():
                self.loaded.emit(models)
        except AiError as error:
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))


class ChatWorker(QThread):
    chunk_received = Signal(str)
    failed = Signal(str)

    def __init__(self, provider: str, model: str, api_key: str, question: str, context: str) -> None:
        super().__init__()
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.question = question
        self.context = context

    def run(self) -> None:
        try:
            for chunk in AiClient(self.provider, self.api_key).stream_chat(self.model, self.question, self.context):
                if self.isInterruptionRequested():
                    return
                self.chunk_received.emit(chunk)
        except AiError as error:
            self.failed.emit(str(error))


class AiDialog(QDialog):
    def __init__(self, context_provider: Callable[[], str], parent=None) -> None:
        super().__init__(parent)
        self.context_provider = context_provider
        self._automatic_context = context_provider()
        self._session_context = self._automatic_context
        self.model_loader: ModelLoader | None = None
        self.chat_worker: ChatWorker | None = None
        self.setWindowTitle("问 AI")
        self.resize(780, 720)
        self.setMinimumSize(620, 540)
        self._build_ui()
        self._provider_changed()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("提供商"))
        self.provider_combo = QComboBox()
        for provider, spec in PROVIDERS.items():
            self.provider_combo.addItem(str(spec["label"]), provider)
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        provider_row.addWidget(self.provider_combo)
        provider_row.addWidget(QLabel("模型"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        provider_row.addWidget(self.model_combo, 1)
        self.refresh_button = QPushButton("刷新本地模型")
        self.refresh_button.clicked.connect(self._load_ollama_models)
        provider_row.addWidget(self.refresh_button)
        layout.addLayout(provider_row)

        key_row = QHBoxLayout()
        self.key_label = QLabel("API Key")
        key_row.addWidget(self.key_label)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("优先读取环境变量；这里输入只在当前对话框有效")
        key_row.addWidget(self.key_edit, 1)
        layout.addLayout(key_row)

        self.provider_note = QLabel()
        self.provider_note.setWordWrap(True)
        layout.addWidget(self.provider_note)

        self.cloud_confirm = QCheckBox("我确认将当前上下文发送至云端模型服务")
        self.cloud_confirm.setChecked(False)
        layout.addWidget(self.cloud_confirm)

        context_row = QHBoxLayout()
        self.context_button = QPushButton("上下文详情")
        self.context_button.clicked.connect(self._show_context)
        context_row.addWidget(self.context_button)
        context_row.addStretch()
        layout.addLayout(context_row)

        preset_row = QHBoxLayout()
        for title, question in (
            ("解释当前页面", "请解释当前页面的内容、关键概念、数据来源和结论边界。"),
            ("检查数据链", "请检查当前页面的数据链路是否闭环：输入是什么、输出是什么、哪些结论可验证。"),
            ("下一步建议", "基于当前页面，建议下一步应补充哪些真实数据或验证步骤？"),
        ):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, value=question: self.question_edit.setPlainText(value))
            preset_row.addWidget(button)
        layout.addLayout(preset_row)

        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setPlaceholderText("选择提供商和模型后，提出关于当前雷达数据链页面的问题。")
        layout.addWidget(self.conversation, 1)

        self.question_edit = QTextEdit()
        self.question_edit.setPlaceholderText("请输入问题……")
        self.question_edit.setFixedHeight(88)
        layout.addWidget(self.question_edit)

        action_row = QHBoxLayout()
        self.status_label = QLabel("就绪")
        action_row.addWidget(self.status_label, 1)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self.conversation.clear)
        action_row.addWidget(clear_button)
        self.stop_button = QPushButton("停止生成")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)
        action_row.addWidget(self.stop_button)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self._send)
        action_row.addWidget(self.send_button)
        layout.addLayout(action_row)

        warning = QLabel("云端提供商会接收“上下文详情”中的内容。AI 回答可能不准确，请以实际数据、参数和可验证结果为准。")
        warning.setWordWrap(True)
        warning.setObjectName("aiWarning")
        layout.addWidget(warning)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setStyleSheet(
            "QDialog { background: #f5f1e7; } "
            "QTextEdit, QLineEdit, QComboBox { background: #fffdf7; border: 1px solid #ded8c8; border-radius: 8px; padding: 5px; } "
            "QPushButton { background: #16856f; color: white; border: none; border-radius: 8px; padding: 6px 12px; } "
            "QPushButton:hover { background: #126b5a; } "
            "QLabel#aiWarning { color: #76513a; background:#fff4df; padding:7px; border:1px solid #e7cfa6; border-radius:8px; }"
        )

    def _provider_changed(self) -> None:
        provider = self.provider_combo.currentData()
        if provider != "ollama" and self.model_loader is not None and self.model_loader.isRunning():
            self.model_loader.requestInterruption()
        self.model_combo.clear()
        is_ollama = provider == "ollama"
        self.refresh_button.setVisible(is_ollama)
        self.key_label.setVisible(not is_ollama)
        self.key_edit.setVisible(not is_ollama)
        self.cloud_confirm.setVisible(not is_ollama)
        self.send_button.setEnabled(not is_ollama)
        if is_ollama:
            self.provider_note.setText("本地请求仅发送到 http://localhost:11434。")
            self._load_ollama_models()
            return

        for model in PROVIDERS[provider]["models"]:
            self.model_combo.addItem(str(model), str(model))
        key = environment_key(provider)
        self.key_edit.setText(key)
        key_status = "已从环境变量读取" if key else "未设置"
        self.provider_note.setText(
            f"云端请求发送至 {PROVIDERS[provider]['url']}；API Key 环境变量："
            f"{PROVIDERS[provider]['env']}（{key_status}）。"
        )

    def _load_ollama_models(self) -> None:
        if self.model_loader is not None and self.model_loader.isRunning():
            return
        self.model_combo.clear()
        self.model_combo.addItem("正在读取本地模型……", "")
        self.send_button.setEnabled(False)
        self.model_loader = ModelLoader(self)
        self.model_loader.loaded.connect(self._models_loaded)
        self.model_loader.failed.connect(self._models_failed)
        self.model_loader.start()

    def _models_loaded(self, models: list[str]) -> None:
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(model, model)
        self.send_button.setEnabled(bool(models))
        self.status_label.setText(f"已读取 {len(models)} 个本地模型" if models else "Ollama 中没有已安装模型")

    def _models_failed(self, message: str) -> None:
        self.model_combo.clear()
        self.model_combo.addItem("请手动输入模型名", "")
        self.model_combo.setEditText("qwen2.5:1.5b")
        self.send_button.setEnabled(True)
        self.status_label.setText(message)

    def _context(self) -> str:
        return self._session_context

    def _show_context(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑本次发送给 AI 的上下文")
        dialog.resize(720, 540)
        layout = QVBoxLayout(dialog)
        note = QLabel("修改仅对当前问 AI 对话框有效，关闭后不会保存。")
        layout.addWidget(note)
        text = QTextEdit()
        text.setPlainText(self._context())
        layout.addWidget(text)

        action_row = QHBoxLayout()
        restore_button = QPushButton("恢复自动上下文")
        action_row.addWidget(restore_button)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(text.clear)
        action_row.addWidget(clear_button)
        action_row.addStretch()
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(dialog.reject)
        action_row.addWidget(cancel_button)
        apply_button = QPushButton("应用本次修改")
        action_row.addWidget(apply_button)
        layout.addLayout(action_row)

        def restore_context() -> None:
            self._automatic_context = self.context_provider()
            text.setPlainText(self._automatic_context)

        def apply_context() -> None:
            self._session_context = text.toPlainText()
            modified = self._session_context != self._automatic_context
            self.context_button.setText("上下文详情（已修改）" if modified else "上下文详情")
            self.cloud_confirm.setChecked(False)
            dialog.accept()

        restore_button.clicked.connect(restore_context)
        apply_button.clicked.connect(apply_context)
        dialog.exec()

    def _send(self) -> None:
        question = self.question_edit.toPlainText().strip()
        model = self._selected_model()
        provider = self.provider_combo.currentData()
        if not question or not model:
            self.status_label.setText("请选择模型并输入问题")
            return
        if provider != "ollama" and not self.cloud_confirm.isChecked():
            self.status_label.setText("请先确认将当前上下文发送至云端服务")
            return

        self.conversation.append(f"<p><b>你：</b>{escape(question)}</p><p><b>AI：</b></p>")
        self.question_edit.clear()
        self.send_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText(f"{model} 正在生成……")
        self.chat_worker = ChatWorker(provider, model, self.key_edit.text(), question, self._context())
        self.chat_worker.chunk_received.connect(self._append)
        self.chat_worker.failed.connect(lambda message: self.conversation.append(f"<p><b>请求失败：</b>{escape(message)}</p>"))
        self.chat_worker.finished.connect(self._finished)
        self.chat_worker.start()

    def _selected_model(self) -> str:
        text = self.model_combo.currentText().strip()
        index = self.model_combo.currentIndex()
        if index >= 0 and text == self.model_combo.itemText(index):
            model_data = self.model_combo.itemData(index)
            if model_data:
                return str(model_data).strip()
        return text

    def _append(self, chunk: str) -> None:
        cursor = self.conversation.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.conversation.setTextCursor(cursor)
        self.conversation.ensureCursorVisible()

    def _stop(self) -> None:
        if self.chat_worker is not None:
            self.chat_worker.requestInterruption()

    def _finished(self) -> None:
        self.conversation.append("<br>")
        self.send_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("就绪")

    def closeEvent(self, event) -> None:
        if self.chat_worker is not None and self.chat_worker.isRunning():
            self.chat_worker.requestInterruption()
            self.chat_worker.wait(2000)
        if self.model_loader is not None and self.model_loader.isRunning():
            self.model_loader.requestInterruption()
            self.model_loader.wait(5500)
        super().closeEvent(event)
