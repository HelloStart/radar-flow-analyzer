from __future__ import annotations

import cmath
import html
import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .ai import PROVIDERS, environment_key
from .ai_dialog import ChatWorker, ModelLoader
from .domain import load_catalog

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_PATH = ROOT / "knowledge" / "catalog.yaml"
DATA_PATH = ROOT / "knowledge" / "data"


class LinePlotWidget(QWidget):
    def __init__(self, title: str, x_label: str) -> None:
        super().__init__()
        self._title = title
        self._x_label = x_label
        self._x_values: list[float] = []
        self._y_values: list[float] = []
        self._comparison_y_values: list[float] = []
        self._comparison_label = ""
        self._selected_label = ""
        self._peak_label = ""
        self.setMinimumHeight(280)

    def set_data(
        self,
        x_values: list[float],
        y_values: list[float],
        peak_label: str,
        comparison_y_values: list[float] | None = None,
        selected_label: str = "当前窗",
        comparison_label: str = "不加窗 Rect",
    ) -> None:
        self._x_values = x_values
        self._y_values = y_values
        self._comparison_y_values = comparison_y_values or []
        self._selected_label = selected_label
        self._comparison_label = comparison_label
        self._peak_label = peak_label
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#fffdf7"))

        margin_left = 58
        margin_top = 42
        margin_right = 24
        margin_bottom = 46
        plot_rect = QRectF(
            margin_left,
            margin_top,
            self.width() - margin_left - margin_right,
            self.height() - margin_top - margin_bottom,
        )

        painter.setPen(QPen(QColor("#24352f"), 1))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        painter.setFont(title_font)
        painter.drawText(12, 24, self._title)

        painter.setFont(QFont())
        painter.setPen(QPen(QColor("#ded8c8"), 1))
        painter.drawRect(plot_rect)
        for idx in range(1, 5):
            y = plot_rect.top() + plot_rect.height() * idx / 5
            painter.drawLine(QPointF(plot_rect.left(), y), QPointF(plot_rect.right(), y))

        painter.setPen(QPen(QColor("#756f63"), 1))
        painter.drawText(8, int(plot_rect.top()) + 4, "0 dB")
        painter.drawText(8, int(plot_rect.bottom()), "-80 dB")
        painter.drawText(int(plot_rect.center().x()) - 40, self.height() - 14, self._x_label)
        painter.setPen(QPen(QColor("#b7ae9f"), 2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(plot_rect.right() - 178, 19), QPointF(plot_rect.right() - 138, 19))
        painter.setPen(QPen(QColor("#6d675d"), 1))
        painter.drawText(int(plot_rect.right()) - 132, 24, self._comparison_label)
        painter.setPen(QPen(QColor("#16856f"), 2))
        painter.drawLine(QPointF(plot_rect.right() - 178, 35), QPointF(plot_rect.right() - 138, 35))
        painter.setPen(QPen(QColor("#126b5a"), 1))
        painter.drawText(int(plot_rect.right()) - 132, 40, self._selected_label)

        if not self._x_values or not self._y_values:
            return

        x_min = min(self._x_values)
        x_max = max(self._x_values)
        y_min = -80.0
        y_max = 0.0

        def map_point(x_value: float, y_value: float) -> QPointF:
            x_span = x_max - x_min if x_max != x_min else 1.0
            x = plot_rect.left() + (x_value - x_min) / x_span * plot_rect.width()
            y_clamped = max(y_min, min(y_max, y_value))
            y = plot_rect.bottom() - (y_clamped - y_min) / (y_max - y_min) * plot_rect.height()
            return QPointF(x, y)

        if self._comparison_y_values:
            painter.setPen(QPen(QColor("#b7ae9f"), 2, Qt.PenStyle.DashLine))
            comparison_points = [
                map_point(x_value, y_value)
                for x_value, y_value in zip(self._x_values, self._comparison_y_values)
            ]
            for start, end in zip(comparison_points, comparison_points[1:]):
                painter.drawLine(start, end)

        painter.setPen(QPen(QColor("#16856f"), 2))
        points = [map_point(x_value, y_value) for x_value, y_value in zip(self._x_values, self._y_values)]
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)

        peak_index = max(range(len(self._y_values)), key=self._y_values.__getitem__)
        peak = points[peak_index]
        painter.setPen(QPen(QColor("#c4562b"), 1))
        painter.drawLine(QPointF(peak.x(), plot_rect.top()), QPointF(peak.x(), plot_rect.bottom()))
        painter.setPen(QPen(QColor("#8d3c1f"), 1))
        painter.drawText(int(peak.x()) + 6, int(plot_rect.top()) + 18, self._peak_label)


class RadarFlowAnalyzerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Radar Flow Analyzer")
        self.resize(1280, 820)
        self.setStyleSheet(
            """
            QMainWindow { background: #f5f1e7; }
            QWidget { color: #24352f; }
            QListWidget { background: #fffdf7; border: 1px solid #ded8c8; border-radius: 10px; }
            QListWidget::item { padding: 10px 12px; border-radius: 8px; }
            QListWidget::item:selected { background: #d8eadf; color: #17372f; }
            QTextBrowser { background: #fffdf7; border: 1px solid #ded8c8; border-radius: 10px; }
            QLineEdit { background: #fffdf7; border: 1px solid #cfc6b5; border-radius: 8px; padding: 6px 8px; }
            QComboBox { background: #fffdf7; border: 1px solid #cfc6b5; border-radius: 8px; padding: 5px 8px; }
            QPushButton { background: #16856f; color: white; border: none; border-radius: 8px; padding: 6px 12px; }
            QPushButton:hover { background: #126b5a; }
            QFrame { border-radius: 12px; }
            """
        )
        self.catalog = load_catalog(KNOWLEDGE_PATH)
        self._ai_output = QTextBrowser()
        self._ai_input = QLineEdit()
        self._ai_input.setPlaceholderText("在任意页面中提问,例如:Range FFT 是怎么得到距离的?")
        self._ai_input.returnPressed.connect(self._send_ai_question)
        self._ai_provider_combo = QComboBox()
        self._ai_model_combo = QComboBox()
        self._ai_key_label = QLabel("API Key")
        self._ai_key_input = QLineEdit()
        self._ai_cloud_confirm = QCheckBox("确认将当前上下文发送至云端模型")
        self._ai_status = QLabel("就绪")
        self._ai_context_button = QPushButton("查看上下文")
        self._ai_refresh_button = QPushButton("刷新本地模型")
        self._ai_send_button = QPushButton("发送")
        self._ai_stop_button = QPushButton("停止")
        self._ai_context_override: str | None = None
        self._ai_model_loader: ModelLoader | None = None
        self._ai_chat_worker: ChatWorker | None = None
        self._outline_nav = QListWidget()
        self._content_browser = QTextBrowser()
        self._content_stack = QStackedWidget()
        self._window_demo: QWidget | None = None
        self._range_window_combo: QComboBox | None = None
        self._doppler_window_combo: QComboBox | None = None
        self._range_plot: LinePlotWidget | None = None
        self._doppler_plot: LinePlotWidget | None = None
        self._window_summary = QLabel()
        self._current_chapter = "工具总览"
        self._current_section = ""
        self._chapters = ["工具总览", "应用主线：从 I/Q 到 Presence", "数据处理流程", "可控数据演示", "真实数据分析"]
        self._expanded_chapter: str | None = "工具总览"
        self._chapter_sections = {
            "工具总览": ["雷达应用要解决的问题", "从物理信号到产品状态", "工具内容与阅读方式"],
            "应用主线：从 I/Q 到 Presence": [
                "从24GHz电磁波到IQ数据",
                "从IQ变化到人体运动",
                "怎样从雷达信号中找到人体线索",
                "FMCW雷达怎样看见距离和速度",
                "从目标与特征到有人无人",
            ],
            "数据处理流程": ["概览", "雷达参考参数", "完整 I/Q 数据", "可调参数观察", "ADC/IQ", "Range FFT", "Doppler / R-D", "Candidate / Feature", "Presence"],
            "可控数据演示": ["演示数据来源", "非整数 bin 峰值估计", "强背景下的弱动态目标", "逐帧证据到 Presence 状态"],
            "真实数据分析": ["真实流程入口", "从 ADC/IQ 开始（TBD）", "从 Doppler FFT 开始（TBD）", "从 Energy 开始（TBD）"],
        }
        self._chapter_map = {
            "工具总览": "<h2>工具总览</h2><p>这是工具的总入口，用来解释雷达应用如何从 I/Q 观测逐步形成有人/无人判定。</p><p>阅读时先看应用问题，再看数据链路，最后进入可控流程和真实数据入口；重点不是只看最终状态，而是确认每一层保留了什么证据、丢失了什么信息。</p>",
            "应用主线：从 I/Q 到 Presence": "<h2>应用主线：从 I/Q 到 Presence</h2><p>这里用于建立本工具需要的应用基础：从 24 GHz 电磁波、I/Q 数据、人体运动线索，到 FMCW 距离速度和 Presence 前的目标特征。</p><p>这个入口强调应用主线，不展开成完整雷达理论教材。</p>",
            "数据处理流程": "<h2>数据处理流程</h2><p>本章先看完整输入数据，再沿着 ADC/IQ → Range FFT → Doppler FFT → Range-Doppler → Candidate / Feature → Presence 的顺序展开。</p><p>原始输入、矩阵变化、坐标换算和候选结果都会在本章中逐层展示。</p>",
            "可控数据演示": "<h2>可控数据演示</h2><p>这里放可控教学场景，用来观察非整数 bin、强背景下的弱动态目标、候选路线和逐帧 Presence 状态。</p><p>每个演示都会说明输入数据、处理步骤和结论边界。</p>",
            "真实数据分析": "<h2>真实数据分析</h2><p>这里用于放真实采集、真实安装环境和真实模组接口案例。分析会先判断实际拿到的数据层，再选择从 ADC/IQ、Doppler FFT 后结果或 Energy 特征进入。</p>",
        }
        self._section_map = {
            "雷达应用要解决的问题": """
                <h2>雷达应用要解决的问题</h2>
                <p>先从一个生活中的问题开始：房间里有人吗？设备没有眼睛，也不需要人佩戴标签，它要通过传感器观察环境发生了什么变化。</p>

                <h3>1. 雷达靠什么看见目标</h3>
                <p>雷达的基本方法是主动发射一段自己知道的电磁波，再接收目标和环境反射回来的波。发射波和回波之间的差异，就包含了目标留下的线索。</p>
                <table width='100%' cellspacing='8' cellpadding='10'>
                    <tr>
                        <td bgcolor='#eef7f1' width='27%' align='center'><b>发射</b><br>已知电磁波</td>
                        <td align='center' width='6%'>→</td>
                        <td bgcolor='#fff4df' width='27%' align='center'><b>反射</b><br>目标改变回波</td>
                        <td align='center' width='6%'>→</td>
                        <td bgcolor='#fff8d8' width='27%' align='center'><b>接收</b><br>比较差异</td>
                    </tr>
                </table>
                <p>这里的“看到”不是摄像机意义上的成像，而是测量回波的幅度、相位、延迟和频率变化。墙壁、家具、风扇和人体都会反射电磁波，所以雷达首先看到的是“环境中的反射变化”，还不是“人”。</p>

                <h3>2. 人体为什么会留下线索</h3>
                <p>人体移动时，雷达到人体再返回的路径会改变；路径改变会带来相位变化和多普勒变化。人体的行走、转身、挥手、呼吸和微小晃动，都可能让回波发生变化。</p>
                <p>因此，雷达真正测量的是：</p>
                <ul>
                    <li>回波是否变强或变弱；</li>
                    <li>相位是否随时间旋转；</li>
                    <li>变化发生在哪个距离和速度范围；</li>
                    <li>变化是否持续、重复或符合某种运动过程。</li>
                </ul>

                <h3>3. 从“有反射”到“有人”还差什么</h3>
                <p>一次强反射不能直接证明有人，因为它可能来自墙面或金属物体；一次运动也不能直接证明是人，因为风扇、窗帘、宠物和机械设备也会运动。</p>
                <p>所以应用需要逐层增加证据：</p>
                <p style='text-align:center;'><b>回波变化 → 距离/速度证据 → 候选/特征 → 跨帧状态 → 有人/无人</b></p>
                <p>这就是本工具的核心问题：不是只展示最终状态，而是解释状态之前每一层证据是怎样形成的。</p>

                <h3>4. 本节结论</h3>
                <p><b>雷达通过发射、反射和接收来观察环境变化；“有人”不是直接测量值，而是后续处理根据多层证据作出的应用判断。</b></p>
            """,
            "从物理信号到产品状态": """
                <h2>从物理信号到产品状态</h2>
                <p>有了“雷达靠反射观察环境”的基本概念，下一步要说明：一段高速电磁波怎样变成程序可以处理的数据，又怎样一步步变成产品状态。</p>

                <h3>1. 物理世界到数字输入</h3>
                <table width='100%' cellspacing='8' cellpadding='10'>
                    <tr>
                        <td bgcolor='#eef7f1' align='center'><b>电磁波</b><br>发射与回波</td>
                        <td align='center'>→</td>
                        <td bgcolor='#edf7ef' align='center'><b>模拟接收</b><br>放大、混频、滤波</td>
                        <td align='center'>→</td>
                        <td bgcolor='#fff4df' align='center'><b>ADC/IQ</b><br>复数数字样本</td>
                    </tr>
                </table>
                <p>MCU 通常不会直接采样 24 GHz 载波。接收机先把回波与参考信号混频，保留较慢的差异，再由 ADC 采样成 I/Q 数字。I 和 Q 组合成一个复数，保存回波的幅度和相位信息。</p>

                <h3>2. 数字输入到距离和速度</h3>
                <table width='100%' cellspacing='8' cellpadding='10'>
                    <tr>
                        <td bgcolor='#fbf7ee' align='center'><b>ADC/IQ</b><br>时间序列</td>
                        <td align='center'>→</td>
                        <td bgcolor='#eef7f1' align='center'><b>Range FFT</b><br>距离证据</td>
                        <td align='center'>→</td>
                        <td bgcolor='#fff4df' align='center'><b>Doppler FFT</b><br>速度证据</td>
                    </tr>
                </table>
                <p>在 FMCW 雷达中，一个 Chirp 内的快时间拍频携带距离信息，所以沿快时间做 Range FFT；多个 Chirp 之间的相位变化携带速度信息，所以沿慢时间做 Doppler FFT。</p>
                <p>两个 FFT 不是孤立操作，而是把同一帧 ADC/IQ 数据沿两个不同时间尺度观察：</p>
                <ul>
                    <li>快时间：一个 Chirp 内的采样，回答目标大约有多远；</li>
                    <li>慢时间：多个 Chirp 的序列，回答目标是否有径向速度、速度是多少。</li>
                </ul>

                <h3>3. 证据到产品状态</h3>
                <p>Range-Doppler 图中的亮点只是某个距离-速度单元能量较强。后续还要判断它是不是候选目标，或者把距离门中的运动/微动压缩成特征，再进行跨帧确认。</p>
                <p style='text-align:center;'><b>ADC/IQ → Range FFT → Doppler FFT → Range-Doppler → Candidate/Feature → Presence</b></p>
                <p>Presence 通常不是单帧结果，而是经过连续确认、滞回、Hold Time 和状态机后的产品输出。这样可以避免一帧噪声直接触发，也能保护短暂安静的真实目标。</p>

                <h3>4. 本节结论</h3>
                <p><b>同一条数据路径逐层改变语义：I/Q 是信号，Range 是距离，Doppler 是速度，Candidate/Feature 是局部证据，Presence 是跨帧产品状态。</b></p>
            """,
            "工具内容与阅读方式": """
                <h2>工具内容与阅读方式</h2>
                <p>这个工具不是把整篇专业教材搬进界面，而是用可追溯的数据和图，把一条雷达应用链路讲清楚。</p>

                <h3>1. 先建立概念</h3>
                <p>“应用主线”用于从零开始理解雷达：目标为什么会反射，回波怎样变成 I/Q，人体运动怎样影响相位，以及为什么最终的有人/无人是推断结果。</p>

                <h3>2. 再看可控处理闭环</h3>
                <p>“数据处理流程”使用工具自己的完整 CSV 输入，展示矩阵如何从 ADC/IQ 变成 Range FFT、Doppler FFT、Range-Doppler 和候选结果。每一步都尽量回答：</p>
                <ul>
                    <li>输入数据是什么；</li>
                    <li>处理改变了哪个轴或哪个数据结构；</li>
                    <li>输出能证明什么；</li>
                    <li>输出不能证明什么。</li>
                </ul>

                <h3>3. 再观察困难场景</h3>
                <p>“可控数据演示”把常见困难拆开：非整数 bin 会产生泄漏，强背景可能压住弱动态目标，单帧证据还需要状态机才能变成稳定 Presence。</p>

                <h3>4. 最后进入真实数据</h3>
                <p>“真实数据分析”不假设模组一定开放 ADC/IQ。它先根据实际接口选择入口：从 ADC/IQ、Doppler FFT 后数据，或 Energy/Presence 特征开始，并明确当前能验证到哪一层。</p>

                <h3>5. 工具和完整文本的关系</h3>
                <p>页面内容是便于阅读和操作的精简说明；完整数据、图片和参数保存在工具自己的 knowledge 目录中。需要更完整的公式推导、背景解释或长篇论证时，应回到配套文本材料。</p>
            """,
            "从24GHz电磁波到IQ数据": """
                <h2>从 24 GHz 电磁波到 I/Q 数据</h2>
                <p>本节回答一个基础问题:房间中的 24 GHz 电磁波,怎样经过发射、传播、反射、接收和数字化,最终变成 MCU 可以读取的两串 I/Q 数字。</p>
                <p><i>限于篇幅,详细内容以文本提供。</i></p>

                <h3>1. 这一节要建立的主线</h3>
                <p>雷达并不是直接输出"有人"或"无人"。它主动发出一段已知电磁波,再观察返回的波发生了什么变化。人体、墙壁、家具、噪声和硬件误差都会一起影响最终数据。</p>
                <p><b>主链路:</b>波与频率 → 载波与波形控制 → 天线发射 → 传播与反射 → 接收与混频 → I/Q 与 ADC。</p>
                <p style='text-align:center;'><img src='images/chapter01/15_full_signal_chain.png' width='760'></p>

                <h3>2. 为什么是 24 GHz</h3>
                <p>24 GHz 属于常见的短距雷达与存在检测频段。它的自由空间波长约为 12.5 mm,因此毫米级的径向位移也会带来明显相位变化,这给呼吸、身体微动和运动检测提供了物理基础。</p>
                <ul>
                    <li>频率越高,波长越短,天线和阵列通常可以做得更紧凑。</li>
                    <li>相同路径变化会带来更大的相位变化。</li>
                    <li>但频率更高不等于一定测得更远,传播损耗、材料吸收、天线增益、法规和接收机能力都要一起考虑。</li>
                </ul>
                <p style='text-align:center;'><img src='images/chapter01/06_frequency_spectrum_map.png' width='720'></p>

                <h3>3. 回波为什么会包含人体线索</h3>
                <p>人体组织含有大量水分,会反射、散射和吸收一部分 24 GHz 电磁波。人体的行走、转身、挥手、呼吸和微小晃动,都会改变回波的幅度、相位或频率。</p>
                <p>对于单站雷达,目标沿雷达方向移动时,往返路径变化会改变回波相位:</p>
                <p style='text-align:center;'><b>Δφ = 4πΔR / λ</b></p>
                <p>24 GHz 下 λ 约为 12.5 mm,所以很小的径向位移也可能在 I/Q 平面上留下可观察变化。</p>

                <h3>4. 接收机怎样得到 I/Q</h3>
                <p>回到接收天线的信号仍在 24 GHz 附近,普通 MCU 无法直接采样这种高速变化。接收链路会先经过低噪声放大、正交混频、低通滤波,再送入 ADC。</p>
                <p>正交混频把同一个回波分别与 0° 和 90° 的本振参考比较,得到 I 路和 Q 路。这样可以同时保留合成回波的幅度和相位。</p>
                <p style='text-align:center;'><img src='images/chapter01/04_iq_representation.png' width='700'></p>
                <ul>
                    <li><b>I</b>:In-phase,同相分量。</li>
                    <li><b>Q</b>:Quadrature,正交分量。</li>
                    <li><b>I + jQ</b>:把两路真实测量值组织成一个复数,便于后续 FFT 和相位分析。</li>
                </ul>

                <h3>5. ADC 之后的数据应该怎样看</h3>
                <p>ADC 输出的是离散数字,例如 I: 102, 105, 101... 和 Q: -12, -8, -3...。这些数字必须结合采样率、位宽、增益、满量程、通道排列和帧结构才能解释。</p>
                <p>没有人时,I/Q 也不会是全零,因为墙壁和家具会形成静态杂波,接收机也会引入噪声、直流偏置、I/Q 失配和量化误差。</p>
                <p style='text-align:center;'><img src='images/chapter01/05_iq_imperfections.png' width='700'></p>

                <h3>6. 本节结论</h3>
                <p><b>雷达直接测量的是电磁回波及其变化;"有人"是后续算法根据这些物理线索作出的推断。</b></p>
                <p>到这里还没有进入距离、速度和 FFT。下一步要问的是:在这些不完美的 I/Q 数字中,哪些变化来自人体,哪些来自房间,哪些只是噪声。</p>
            """,
            "从IQ变化到人体运动": """
                <h2>从 I/Q 变化到人体运动</h2>
                <p>上一节说明了 24 GHz 电磁波怎样变成数字 I/Q。本节继续向前走一步:嵌入式程序看到的只是连续到来的 I/Q 样本,但这些样本的变化可以重新连接到真实世界中的靠近、远离、横向运动和呼吸微动。</p>
                <p><i>限于篇幅,详细内容以文本提供。</i></p>

                <h3>1. 从一对 I/Q 到一条轨迹</h3>
                <p>一对 I/Q 数字可以看成 I/Q 平面上的一个点。点到原点的距离表示合成回波振幅,点的角度表示相位。</p>
                <p style='text-align:center;'><b>A = sqrt(I² + Q²),φ = atan2(Q, I)</b></p>
                <p>ADC 连续采样后,一组 I/Q 点按时间连接起来,就形成 I/Q 轨迹。轨迹不仅描述信号强弱,也描述相位变化方向、变化速度、运动节奏和噪声抖动。</p>
                <p style='text-align:center;'><img src='images/chapter02/01_core_iq_trajectories.png' width='760'></p>

                <h3>2. 人体运动怎样改变 I/Q</h3>
                <p>雷达最直接敏感的是径向运动,也就是目标沿雷达视线方向靠近或远离。目标移动会改变往返路径长度,路径变化会改变回波相位。</p>
                <ul>
                    <li><b>靠近雷达:</b>路径缩短,相位沿一个方向连续变化。</li>
                    <li><b>远离雷达:</b>路径增加,相位通常沿相反方向变化。</li>
                    <li><b>横向运动:</b>径向分量较小,I/Q 变化可能弱于正面靠近或远离。</li>
                    <li><b>呼吸微动:</b>不会持续绕圈,而更可能在有限角度范围内缓慢往复。</li>
                </ul>
                <p style='text-align:center;'><img src='images/chapter02/02_radial_motion_geometry.png' width='740'></p>

                <h3>3. 相位变化和多普勒的关系</h3>
                <p>相位描述回波相对于参考信号在某一时刻的位置,多普勒频率描述相位随时间变化得多快。二者不是割裂的两种现象。</p>
                <p style='text-align:center;'><b>f<sub>d</sub> = 1/(2π) · dφ(t)/dt</b></p>
                <p>匀速径向运动会产生相对稳定的相位旋转;非匀速动作、转身、坐下和呼吸则会形成更复杂的时间过程。</p>

                <h3>4. 为什么真实 I/Q 不像理想圆</h3>
                <p>理想单目标会让 I/Q 点沿圆周运动,但真实数据通常会偏移、拉伸、倾斜或抖动。主要原因包括直流偏置、I/Q 增益不平衡、正交误差、多径叠加和随机噪声。</p>
                <p>当相位通过 ±180° 边界时,atan2 输出还会发生相位折叠。程序需要通过相位展开把"显示跳变"恢复为相对连续的变化,但这依赖采样率、信噪比和相邻样本变化足够小。</p>
                <p style='text-align:center;'><img src='images/chapter02/03_phase_wrapping.png' width='720'></p>
                <p style='text-align:center;'><img src='images/chapter02/04_iq_distortions.png' width='760'></p>

                <h3>5. 采集链路也会制造假象</h3>
                <p>I/Q 数据还可能受到 ADC 量化、饱和、丢样和时间戳异常影响。分析原始数据前,需要检查采样率、I/Q 配对、帧序号、时间间隔、满量程值和重复数据块。</p>
                <p style='text-align:center;'><img src='images/chapter02/05_acquisition_artifacts.png' width='760'></p>

                <h3>6. 人体和风扇为什么不能只靠单帧区分</h3>
                <p>人和风扇都会让回波变化。雷达首先看到的是"反射体运动",不会天然知道这是人体。真正有用的是一段时间内的变化过程:持续多久、相位是否连续、速度是否稳定、是否从明显运动逐渐转为人体微动。</p>
                <p style='text-align:center;'><img src='images/chapter02/06_human_fan_comparison.png' width='760'></p>

                <h3>7. 本节结论</h3>
                <p><b>目标运动改变传播路径和散射状态,回波的振幅与相位随之变化;接收机把这些变化保存为连续的 I/Q 样本。</b></p>
                <p>到这里仍然没有直接判断"有人"。下一步要做的是从原始 I/Q 中提取稳定、可比较的特征,逐步走向滤波、频域分析、运动能量和微动特征。</p>
            """,
            "怎样从雷达信号中找到人体线索": """
                <h2>怎样从雷达信号中找到人体线索</h2>
                <p>本节把原始 I/Q 进一步整理成可比较的特征。程序不能只看某个瞬时 I 或 Q 数值,而要先检查数据质量,再通过去偏置、观察窗口、滤波、时域统计和频域分析,描述运动强弱、变化速度和周期规律。</p>
                <p><i>限于篇幅,详细内容以文本提供。</i></p>

                <h3>本节核心思想</h3>
                <p><b>原始 I/Q 不是结论,它只是带有噪声、偏置和环境叠加的观测;特征的作用,是把一段时间内的变化压缩成可以比较、可以进入状态判断的证据。</b></p>
                <p>因此本节不是为了找到一个"人体专属数值",而是建立一条可解释的处理顺序:先确认数据可信,再说明每一步保留了什么、削弱了什么、可能误删了什么。</p>

                <h3>1. 为什么不能直接用原始 I/Q 判断</h3>
                <p>I/Q 是合成回波在两个正交轴上的投影。即使回波很强,某些相位下 I 或 Q 也可能接近零;墙壁、家具和风扇也可能形成强回波或持续变化。</p>
                <p>所以真正有用的问题是:一段时间内变化了多少、变化是否持续、变化快慢如何、是否存在稳定周期。</p>

                <h3>2. 先检查数据质量</h3>
                <p>后续算法建立在可靠采集之上。需要确认 I/Q 是否正确配对、时间戳是否连续、帧序号是否缺失、ADC 是否饱和、数据是否长期重复或停住。</p>
                <p>如果采集链已经错位、削顶或丢样,滤波和 FFT 只会把错误变得更难看清。</p>

                <h3>3. 去偏置、窗口和滤波</h3>
                <p>真实 I/Q 往往包含直流偏置、静态杂波和缓慢漂移。去均值可以把轨迹中心移回原点附近,但窗口太短或基线更新太快,可能把人体缓慢变化一起删掉。</p>
                <p>观察窗口决定看多长时间;窗口越长,低频周期越清楚,但响应越慢。滤波则按变化速度选择保留内容:低通看慢变化,高通突出运动,带通关注指定频段。</p>
                <p style='text-align:center;'><img src='images/chapter03/01_dc_offset_correction.png' width='730'></p>
                <p style='text-align:center;'><img src='images/chapter03/02_observation_windows.png' width='730'></p>
                <p style='text-align:center;'><img src='images/chapter03/03_filter_effects.png' width='730'></p>

                <h3>4. 从时域到频域提取线索</h3>
                <p>时域特征包括变化范围、RMS、能量、方差、差分、过零和峰值间隔。它们能描述一段信号的强弱、波动和变化速度,但不能单独证明变化来自人体。</p>
                <p>频域把问题换成"这段变化包含哪些频率"。FFT 可以看到呼吸样低频、机械周期、动作能量和噪声底,但每张频谱都必须说明输入是什么、窗口多长、是否去偏置和滤波。</p>
                <p style='text-align:center;'><img src='images/chapter03/04_time_frequency_views.png' width='730'></p>
                <p style='text-align:center;'><img src='images/chapter03/05_window_leakage.png' width='730'></p>

                <h3>5. 从运动到微动</h3>
                <p>明显运动通常带来较大能量和快速变化;静坐或睡眠时,人体证据可能退化为弱微动。风扇等机械运动也会产生周期峰,因此不能只看"频谱里有周期"。</p>
                <p>更可靠的特征应结合运动出现、减弱、停留和微动持续的过程。</p>
                <p style='text-align:center;'><img src='images/chapter03/06_scenario_spectra.png' width='730'></p>
                <p style='text-align:center;'><img src='images/chapter03/07_motion_micro_motion_transition.png' width='730'></p>

                <h3>6. 本节结论</h3>
                <p><b>特征不是凭空生成的标签,而是从可靠 I/Q 数据中提取出来的可比较描述。</b></p>
                <p>到这里,我们已经能描述运动强弱、周期和微动线索。下一步要让 FMCW 把这些变化放入距离和速度两个维度。</p>
            """,
            "FMCW雷达怎样看见距离和速度": """
                <h2>FMCW 雷达怎样看见距离和速度</h2>
                <p>本节解释 FMCW 怎样把房间中混在一起的回波拆成距离和速度两个维度。一个 Chirp 内的采样用于区分距离,多个 Chirp 之间的相位变化用于区分速度。</p>
                <p><i>限于篇幅,详细内容以文本提供。</i></p>

                <h3>本节核心思想</h3>
                <p><b>距离不是直接量到"飞行时间",而是由 Chirp 的传播延迟变成拍频;速度不是从单个距离峰直接看出来,而是由同一距离 bin 在多个 Chirp 之间的相位变化得到。</b></p>
                <p>所以 FMCW 的关键不是"做两次 FFT"这个动作本身,而是先让距离信息进入快时间拍频,再让速度信息进入慢时间相位变化。</p>

                <h3>1. 为什么固定频率 CW 不够</h3>
                <p>固定频率 CW 可以看到回波在变,因此适合发现运动;但它缺少明确的距离标签。墙壁、人体、风扇和门外行人的回波都会叠加成同一条基带 I/Q 序列,系统很难判断变化发生在沙发、门口还是墙外。</p>
                <p>原因在于单频相位每隔 2π 就重复。只观察一个固定频率上的相位,不能唯一知道回波多走了几个完整波长,也就难以把不同距离的回波分开。</p>

                <h3>2. Chirp 怎样把距离变成拍频</h3>
                <p>FMCW 让发射频率在一个 Chirp 内按已知斜率变化:</p>
                <p style='text-align:center;'><b>f<sub>tx</sub>(t) = f<sub>0</sub> + S t</b></p>
                <p>目标距离为 R 时,回波需要先走到目标再返回雷达,传播延迟近似为:</p>
                <p style='text-align:center;'><b>Ï" = 2R / c</b></p>
                <p>接收回波相当于较早时刻发出的 Chirp。因为当前发射频率已经沿斜坡继续向前走,所以"延迟了一段时间"会表现为"当前发射频率和回波频率之间有差值"。这个差值就是拍频:</p>
                <p style='text-align:center;'><b>f<sub>b</sub> = SÏ" = 2SR / c</b></p>
                <p>于是距离可以从拍频反推:</p>
                <p style='text-align:center;'><b>R = c f<sub>b</sub> / (2S)</b></p>
                <p>直觉上:目标越远,回波延迟越大;延迟越大,在斜坡上错开的频率越多;混频后留下的拍频也越高。</p>
                <p style='text-align:center;'><img src='images/chapter04/01_chirp_delay_beat_zoom.png' width='760'></p>

                <h3>3. Range FFT 为什么能分开不同距离</h3>
                <p>一个 Chirp 内,ADC 采到的是混频后的基带 I/Q。若房间里有多个距离不同的反射体,它们会产生多个拍频分量;在时域曲线上,这些分量叠在一起不容易直接分开。</p>
                <p>Range FFT 沿一个 Chirp 内的快时间采样执行,用来把不同拍频分量分到不同频率 bin,再通过 <b>R = c f<sub>b</sub> / (2S)</b> 映射成距离 bin。</p>
                <p>这一层输出的不是最终目标,而是"哪个距离附近有较强回波"。Range bin 也不是无限薄的点,它有宽度;两个目标太近时会重叠,强目标旁瓣也可能遮住弱目标。</p>
                <p>Range FFT 的复数结果还保留相位。后续要测速度时,正是观察同一个距离 bin 在多个 Chirp 中的相位怎样变化;如果这里提前只保留幅度,速度信息会被削弱或丢掉。</p>
                <p style='text-align:center;'><img src='images/chapter04/02_range_fft_separation.png' width='760'></p>

                <h3>4. 速度为什么来自多个 Chirp</h3>
                <p>一个 Chirp 可以形成距离维,但还不足以稳定分离速度。运动目标在相邻 Chirp 之间可能还落在同一个 Range bin 内,但它沿径向移动了一点点,往返路径已经改变,Range FFT 峰值的复数相位也会跟着转动。</p>
                <p>目标径向速度为 v<sub>r</sub>,相邻同类 Chirp 间隔为 T<sub>r</sub> 时,相邻 Chirp 间的径向位移近似为:</p>
                <p style='text-align:center;'><b>ΔR = v<sub>r</sub> T<sub>r</sub></b></p>
                <p>对应跨 Chirp 相位变化为:</p>
                <p style='text-align:center;'><b>Δφ = 4π v<sub>r</sub> T<sub>r</sub> / λ</b></p>
                <p>反过来,速度可以由相位变化得到:</p>
                <p style='text-align:center;'><b>v<sub>r</sub> = λ Δφ / (4π T<sub>r</sub>)</b></p>
                <p>也可以先理解为多普勒频率:</p>
                <p style='text-align:center;'><b>f<sub>d</sub> = 2v<sub>r</sub> / λ,Δφ = 2π f<sub>d</sub> T<sub>r</sub></b></p>
                <p>直觉上:Range FFT 峰值像一个复数指针;目标运动时,这个指针在一串 Chirp 中持续旋转。旋转方向表示靠近或远离的符号约定,旋转速度对应径向速度大小。</p>

                <h3>5. Doppler FFT 为什么能分开同距不同速目标</h3>
                <p>如果某个 Range bin 里只有一个目标,比较相邻 Chirp 的相位差就能得到速度估计。但真实场景中,同一距离附近可能同时有走动的人和风扇叶片,它们落在相同 Range bin,却具有不同速度分量。</p>
                <p>因此需要收集多个 Chirp,对同一 Range bin 的慢时间复数序列做 Doppler FFT。它的作用与 Range FFT 类似:Range FFT 分开一个 Chirp 内的不同拍频,Doppler FFT 分开同一距离 bin 中的不同相位旋转速度。</p>
                <p style='text-align:center;'><img src='images/chapter04/03_fast_slow_time_matrix.png' width='760'></p>

                <h3>6. 快时间、慢时间和 Range-Doppler Map</h3>
                <p>一帧 FMCW 数据可以看成二维矩阵:行是 Chirp 编号,列是每个 Chirp 内的 ADC sample。</p>
                <ul>
                    <li><b>快时间:</b>一个 Chirp 内的 ADC sample 轴,用来观察拍频,因此得到距离。</li>
                    <li><b>慢时间:</b>多个 Chirp 的编号轴,用来观察同一距离 bin 的相位演变,因此得到速度。</li>
                </ul>
                <p>第一次 FFT 沿快时间做,得到 Range bin;第二次 FFT 沿慢时间做,得到 Doppler bin。二者组合后就是 Range-Doppler Map。</p>
                <p>Range-Doppler 图中的亮点表示某个距离-速度单元能量较强,但它仍只是候选证据,不等于"人体"标签。</p>
                <p style='text-align:center;'><img src='images/chapter04/04_range_doppler_map.png' width='760'></p>

                <h3>7. 参数取舍</h3>
                <p>有效带宽影响距离分辨率,Chirp 重复间隔影响无模糊速度,采样率和 IF 带宽限制最大可测距离,Chirp 数量影响 Doppler 分辨率和响应延迟。</p>
                <p>这些参数不是越大越好,而是在距离、速度、功耗、内存、实时性和场景范围之间折中。对 Presence 来说,能否把门口、沙发、床等区域合理分开,往往比追求很远最大距离更重要。</p>
                <p style='text-align:center;'><img src='images/chapter04/05_parameter_tradeoffs.png' width='740'></p>

                <h3>8. 本节结论</h3>
                <p><b>FMCW 的距离来自"延迟 → 拍频 → Range bin",速度来自"径向位移 → 跨 Chirp 相位变化 → Doppler bin"。</b></p>
                <p>理解这个因果关系后,Range-Doppler Map 才不是一张孤立热力图,而是从物理传播、Chirp 参数和二维 FFT 共同得到的可解释证据。</p>
            """,
            "从目标与特征到有人无人": """
                <h2>从目标与特征到有人/无人</h2>
                <p>本节从 Range-Doppler Map 上的亮点出发,解释它怎样经过候选检测、目标或特征证据、瞬时判断、时间确认和状态机,最终变成稳定的有人/无人输出。</p>
                <p><i>限于篇幅,详细内容以文本提供。</i></p>

                <h3>本节核心思想</h3>
                <p><b>Presence 不是信号处理链中某一个中间结果的直接翻译,而是把候选、特征、时间连续性和产品策略组合后的状态决策。</b></p>
                <p>所以本节要区分三层问题:雷达看到了什么能量,算法把它整理成什么证据,产品最终什么时候宣布有人或无人。</p>

                <h3>1. 亮点只是候选,不是人体</h3>
                <p>Range-Doppler Map 中的能量可能来自人体,也可能来自风扇、门、宠物、墙面旁瓣、多径或噪声起伏。检测阶段只是在说某个单元值得关注。</p>
                <p>固定门限简单但脆弱;换设备、换安装位置、换房间背景后,数值尺度和背景分布都会改变。</p>
                <p style='text-align:center;'><img src='images/chapter05/01_fixed_adaptive_thresholds.png' width='760'></p>

                <h3>2. CFAR 为什么出现</h3>
                <p>CFAR 的核心思想是用待检测单元周围的训练单元估计局部背景,再设置相对门限。它不是直接问能量是否超过固定数字,而是问它是否明显高于附近环境。</p>
                <p>训练单元、保护单元和门限因子共同决定检测行为。CFAR 输出仍是候选目标,不会自动区分人体和杂波。</p>
                <p style='text-align:center;'><img src='images/chapter05/02_cfar_neighborhood.png' width='760'></p>

                <h3>3. 目标路线和特征路线</h3>
                <p>Presence 可以从目标路线进入:先检测候选,再估计距离、速度、方向、目标簇或航迹。也可以从特征路线进入:直接在距离门内计算运动能量、微动能量、相位质量和持续时间。</p>
                <p>两条路线都只能提供证据,不能单独保证目标一定是人。</p>
                <p style='text-align:center;'><img src='images/chapter05/04_target_feature_routes.png' width='760'></p>

                <h3>4. 从瞬时证据到稳定状态</h3>
                <p>单帧证据容易抖动,因此产品状态通常需要连续确认、滞回和 Hold Time。无人进入有人需要较强且连续的证据;已经有人时,短时间证据减弱不应立刻释放。</p>
                <p>Hold Time 可以保护静坐或短暂停顿,但会增加离场后的释放延迟。</p>
                <p style='text-align:center;'><img src='images/chapter05/05_state_timeline.png' width='760'></p>

                <h3>5. 真实场景问题</h3>
                <p>风扇误报、静坐漏检、距离门边界、短暂穿越、安装方向、多人遮挡、宠物和雷达互扰,都需要追踪错误从哪个数据层开始。</p>
                <p>评估时要区分帧级指标和事件级指标。单个 CUT 的虚警率、每帧误报、每小时误报事件数和最终用户体验不是同一层问题。</p>
                <p style='text-align:center;'><img src='images/chapter05/06_frame_event_evaluation.png' width='760'></p>

                <h3>6. 本节结论</h3>
                <p><b>Presence 不是某一个峰值的直接翻译,而是目标、特征、时间确认和状态机共同形成的产品状态。</b></p>
                <p>理解这一层后,才能把仿真处理链和真实模块输出连接起来,判断当前数据能证明什么、不能证明什么。</p>
            """,
            "雷达参考参数": """
                <h2>雷达参考参数</h2>
                <p>进入核心流程之前,先固定一组参考参数。后面的 ADC/IQ、Range FFT、Doppler FFT、Range-Doppler 和 Presence 示例都以这组参数作为共同坐标系。</p>
                <p><i>这些参数用于教学和流程验证,不代表某一款真实雷达模组的默认配置或性能承诺。</i></p>

                <h3>1. 基础配置</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>参数</th><th align='left'>符号或配置</th><th align='left'>参考值</th><th align='left'>影响环节</th></tr>
                    <tr><td>载波频率</td><td>f<sub>c</sub></td><td>24 GHz</td><td>决定波长和速度换算</td></tr>
                    <tr><td>波长</td><td>λ</td><td>0.0125 m</td><td>决定相位位移关系和 Doppler 速度刻度</td></tr>
                    <tr><td>Chirp 斜率</td><td>S</td><td>10 MHz/us</td><td>将传播延迟映射为拍频</td></tr>
                    <tr><td>ADC 采样率</td><td>f<sub>s</sub></td><td>2 MHz</td><td>决定快时间采样间隔和可观测 IF 范围</td></tr>
                    <tr><td>每 Chirp 采样数</td><td>N<sub>s</sub></td><td>128</td><td>决定 Range FFT 输入长度</td></tr>
                    <tr><td>每帧 Chirp 数</td><td>N<sub>c</sub></td><td>64</td><td>决定 Doppler FFT 输入长度</td></tr>
                    <tr><td>Chirp 重复间隔</td><td>T<sub>r</sub></td><td>1 ms</td><td>决定慢时间采样间隔和无模糊速度范围</td></tr>
                    <tr><td>天线配置</td><td>TX / RX</td><td>1 TX / 1 RX</td><td>本阶段只验证距离和速度,不验证角度维</td></tr>
                </table>

                <h3>2. 数据形状</h3>
                <table width='100%' cellspacing='8' cellpadding='10'>
                    <tr>
                        <td bgcolor='#eef7f1' width='32%' align='center'><b>一帧 ADC/IQ</b><br>64 × 128 complex samples<br><font color='#6d675d'>Chirp × ADC sample</font></td>
                        <td align='center' width='2%'>→</td>
                        <td bgcolor='#edf7ef' width='32%' align='center'><b>Range FFT 后</b><br>64 × 128 complex range bins<br><font color='#6d675d'>Chirp × Range bin</font></td>
                        <td align='center' width='2%'>→</td>
                        <td bgcolor='#fff4df' width='32%' align='center'><b>Doppler FFT 后</b><br>64 × 128 complex R-D bins<br><font color='#6d675d'>Doppler bin × Range bin</font></td>
                    </tr>
                </table>

                <h3>3. 派生刻度</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>刻度</th><th align='left'>参考值</th><th align='left'>怎么使用</th></tr>
                    <tr><td>Range bin 间隔</td><td>0.234375 m</td><td>用于把 Range FFT bin 映射到距离位置</td></tr>
                    <tr><td>Doppler 速度 bin 间隔</td><td>0.09765625 m/s</td><td>用于把 Doppler bin 映射到径向速度</td></tr>
                    <tr><td>最大无模糊速度</td><td>约 ±3.125 m/s</td><td>用于判断速度轴能覆盖的径向运动范围</td></tr>
                    <tr><td>一帧慢时间长度</td><td>64 ms</td><td>用于理解 Doppler 观察时间和响应延迟</td></tr>
                </table>

                <h3>4. 为什么先看参数</h3>
                <p>参数决定坐标轴,坐标轴决定每一层输出怎样解释。比如 Range FFT 的峰值位置不能只说"第 8 个 bin",还要知道每个 bin 对应多少米;Doppler FFT 的结果也不能只说"第 5 个速度 bin",还要知道速度刻度和正负方向约定。</p>
                <p>因此,后续每个小节都可以按同一个问题检查:当前模块使用了哪些参数,输入数据形状是什么,输出坐标轴是什么,哪些结论是这组参数下可验证的。</p>
            """,
            "可调参数观察": """
                <h2>可调参数观察</h2>
                <p>当前只保留一个可调主题:<b>窗函数</b>。它分别作用在 Range FFT 的快时间轴和 Doppler FFT 的慢时间轴上,用户可以观察加窗怎样改变 Range Profile、Doppler Profile 和 Range-Doppler Map 的峰值外观。</p>
                <p><b>注意:</b> 本页使用内置教学复数信号演示窗函数效果,不是从完整 CSV 数据重新运行整条处理链。完整 CSV 用于核心流程和演示示例的数据追溯;窗函数页只用于隔离观察“加窗/不加窗”对频谱泄漏的影响。</p>
                <p>其它参数,例如 FFT 长度、候选门限、距离门、Presence 门限和 Hold Time,当前不放入核心流程交互,避免把重点从"FFT 为什么要加窗"分散出去。</p>

                <h3>1. 只展示窗函数</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>可调项</th><th align='left'>作用位置</th><th align='left'>观察结果</th><th align='left'>建议控件</th></tr>
                    <tr><td><b>Range FFT 窗函数</b></td><td>每个 Chirp 内的 128 点快时间样本</td><td>Range Profile 的主瓣宽度、旁瓣泄漏和距离峰外观</td><td>下拉选择:Rect / Hann / Hamming</td></tr>
                    <tr><td><b>Doppler FFT 窗函数</b></td><td>每个 Range bin 跨 64 个 Chirp 的慢时间序列</td><td>Doppler Profile 的速度峰宽度、旁瓣泄漏和 Range-Doppler 图上的能量扩散</td><td>下拉选择:Rect / Hann / Hamming</td></tr>
                </table>

                <h3>2. 可以比较哪些窗</h3>
                <p>先保留三种最容易解释的选择:</p>
                <ul>
                    <li><b>Rect 矩形窗:</b>主瓣较窄,但旁瓣泄漏更明显。</li>
                    <li><b>Hann 窗:</b>旁瓣更低,弱目标附近更干净,但主瓣变宽。</li>
                    <li><b>Hamming 窗:</b>也是旁瓣抑制方案,但主瓣和旁瓣取舍不同。</li>
                </ul>
                <p>这里要明确解释:加窗不是为了让图更漂亮,而是在"峰更尖"和"旁瓣更低"之间取舍。它可能帮助弱目标不被强目标旁瓣淹没,也可能让相近目标更难分开。</p>

                <h3>3. Range FFT 中观察什么</h3>
                <p>Range FFT 的窗函数作用在每个 Chirp 的快时间样本上:</p>
                <p style='text-align:center;'><b>windowed_fast_time = adc_iq[m, :] × window(128)</b></p>
                <p>切换窗函数后,主要观察 Range Profile:</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>观察点</th><th align='left'>说明</th></tr>
                    <tr><td>距离峰是否集中</td><td>目标仍应在 k=8 附近形成主峰。</td></tr>
                    <tr><td>旁瓣高度</td><td>强峰两侧是否有明显泄漏。</td></tr>
                    <tr><td>主瓣宽度</td><td>峰是否变宽,是否更容易影响相邻距离 bin。</td></tr>
                    <tr><td>候选解释</td><td>窗函数改变峰形,但不能把 k=8 这个真值直接传给算法。</td></tr>
                </table>

                <h3>4. Doppler FFT 中观察什么</h3>
                <p>Doppler FFT 的窗函数作用在同一 Range bin 跨 Chirp 的慢时间序列上:</p>
                <p style='text-align:center;'><b>windowed_slow_time = range_fft[:, k] × window(64)</b></p>
                <p>切换窗函数后,主要观察 Doppler Profile 和 Range-Doppler Map:</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>观察点</th><th align='left'>说明</th></tr>
                    <tr><td>速度峰是否集中</td><td>目标仍应在 d=+5 附近形成主峰。</td></tr>
                    <tr><td>Doppler 旁瓣</td><td>速度峰两侧是否扩散到相邻 Doppler bin。</td></tr>
                    <tr><td>二维图扩散</td><td>Range-Doppler Map 上主峰周围是否出现更多能量拖尾。</td></tr>
                    <tr><td>速度解释</td><td>窗函数改变峰形,不改变 d=a-32 的轴映射关系。</td></tr>
                </table>

                <h3>5. 当前交互范围</h3>
                <p>当前只计划做两个控件:Range FFT 窗函数和 Doppler FFT 窗函数。每次切换后重新计算对应结果图,并在页面上说明峰值、旁瓣和主瓣变化。</p>
                <p>其它参数暂不加入,等窗函数观察闭环稳定后再考虑是否扩展。</p>
            """,
            "概览": """
                <h2>核心流程概览</h2>
                <p>本页先把完整处理链放在一张框图里。下面各小节会沿着同一条路径展开:每一步都看清楚它接收什么数据、做什么处理、输出什么结果,以及这个结果能支持哪些判断。</p>

                <table width='100%' cellspacing='8' cellpadding='10'>
                    <tr>
                        <td bgcolor='#eef7f1' width='16%' align='center'><b>ADC / I/Q</b><br><font color='#6d675d'>输入</font><br>采样序列 I/Q</td>
                        <td align='center' width='4%'>→</td>
                        <td bgcolor='#edf7ef' width='16%' align='center'><b>Range FFT</b><br><font color='#6d675d'>输出</font><br>Range Profile</td>
                        <td align='center' width='4%'>→</td>
                        <td bgcolor='#fff4df' width='16%' align='center'><b>Doppler FFT</b><br><font color='#6d675d'>输出</font><br>速度维证据</td>
                        <td align='center' width='4%'>→</td>
                        <td bgcolor='#fff8d8' width='16%' align='center'><b>Range-Doppler</b><br><font color='#6d675d'>输出</font><br>距离-速度图</td>
                    </tr>
                    <tr>
                        <td colspan='7' align='center'>↓</td>
                    </tr>
                    <tr>
                        <td bgcolor='#fbf7ee' align='center'><b>原始证据</b><br><font color='#6d675d'>幅度 / 相位 / 时间</font></td>
                        <td align='center'>→</td>
                        <td bgcolor='#fbf7ee' align='center'><b>距离证据</b><br><font color='#6d675d'>目标在哪个距离门</font></td>
                        <td align='center'>→</td>
                        <td bgcolor='#fbf7ee' align='center'><b>运动证据</b><br><font color='#6d675d'>是否有径向速度</font></td>
                        <td align='center'>→</td>
                        <td bgcolor='#fbf7ee' align='center'><b>二维候选</b><br><font color='#6d675d'>哪个距离-速度单元显著</font></td>
                    </tr>
                </table>

                <table width='100%' cellspacing='8' cellpadding='10'>
                    <tr>
                        <td bgcolor='#fef2f2' width='30%' align='center'><b>Candidate / Feature</b><br>候选目标、峰值、门限、距离门特征</td>
                        <td align='center' width='5%'>→</td>
                        <td bgcolor='#f5f3ff' width='30%' align='center'><b>Frame Evidence</b><br>单帧或短窗口证据</td>
                        <td align='center' width='5%'>→</td>
                        <td bgcolor='#ecfeff' width='30%' align='center'><b>Presence</b><br>跨帧确认、滞回、Hold Time、有人/无人状态</td>
                    </tr>
                </table>

                <h3>模块输入与输出</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>模块</th><th align='left'>输入</th><th align='left'>输出</th><th align='left'>主要作用</th></tr>
                    <tr><td><b>ADC / I/Q</b></td><td>模拟基带 I/Q</td><td>数字 I/Q 采样</td><td>保留幅度、相位和时间变化</td></tr>
                    <tr><td><b>Range FFT</b></td><td>每个 Chirp 内的快时间采样</td><td>Range Profile</td><td>把拍频转换成距离 bin</td></tr>
                    <tr><td><b>Doppler FFT</b></td><td>同一距离 bin 跨多个 Chirp 的复数序列</td><td>Doppler bins</td><td>从慢时间相位变化中提取径向速度</td></tr>
                    <tr><td><b>Range-Doppler</b></td><td>距离维和速度维 FFT 结果</td><td>二维距离-速度能量图</td><td>定位候选目标所在的距离和速度单元</td></tr>
                    <tr><td><b>Candidate / Feature</b></td><td>Range-Doppler、Range Profile 或距离门序列</td><td>候选目标、峰值、能量、微动特征</td><td>形成可被状态机使用的局部证据</td></tr>
                    <tr><td><b>Presence</b></td><td>逐帧证据和历史状态</td><td>有人 / 无人 / 保持状态</td><td>通过连续确认、滞回和保持时间得到稳定状态</td></tr>
                </table>

                <h3>阅读方式</h3>
                <p>后续小节可以按这张图向下读:当前看到的是哪一层数据,它来自哪里,又会交给下一层形成什么证据。这样在看 ADC、Range FFT 或 Presence 时,不会丢掉它在完整链路中的位置。</p>
            """,
            "ADC/IQ": """
                <h2>ADC / I/Q:完整一帧原始输入</h2>
                <p>这里使用一个可控的单目标整数 bin 场景作为参考输入。目标距离为 <b>1.875 m</b>,径向速度为 <b>+0.48828125 m/s</b>,对应真值 Range bin 为 <b>8</b>,Doppler bin 为 <b>+5</b>。这些真值只用于生成和事后核对,处理链真正读取的是完整一帧 ADC/IQ 数据。</p>

                <h3>1. 输入是什么</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>数据</th><th align='left'>形状</th><th align='left'>含义</th></tr>
                    <tr><td><b>adc_iq[m,n]</b></td><td>64 × 128 complex</td><td>64 个 Chirp,每个 Chirp 128 个复数 ADC/IQ 样本</td></tr>
                    <tr><td>m</td><td>0...63</td><td>慢时间:一帧中的 Chirp 编号</td></tr>
                    <tr><td>n</td><td>0...127</td><td>快时间:单个 Chirp 内的 ADC 采样点</td></tr>
                    <tr><td>每个元素</td><td>I + jQ</td><td>同一时刻的正交基带复数样本</td></tr>
                </table>

                <h3>2. 这帧数据怎样生成</h3>
                <p>在整数 bin 参考场景中,每个矩阵位置的相位为:</p>
                <p style='text-align:center;'><b>θ[m,n] = 2π(8n/128 + 5m/64)</b></p>
                <p>然后生成 I/Q:</p>
                <p style='text-align:center;'><b>I[m,n] = A cos θ[m,n] + w<sub>I</sub>[m,n]</b></p>
                <p style='text-align:center;'><b>Q[m,n] = A sin θ[m,n] + w<sub>Q</sub>[m,n]</b></p>
                <p style='text-align:center;'><b>adc_iq[m,n] = I[m,n] + jQ[m,n]</b></p>
                <p>其中 A=1.0,噪声由固定随机种子产生,保证每次结果可重复。这里的 8 和 5 是生成场景的真值,不是后续 FFT 检测时偷偷传入的答案。</p>

                <h3>3. 数据片段展示</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>adc_iq[m,n]</th><th align='left'>n=0</th><th align='left'>n=1</th><th align='left'>n=2</th><th align='left'>...</th><th align='left'>n=126</th><th align='left'>n=127</th></tr>
                    <tr><td>m=0</td><td>+1.0455-0.0347j</td><td>+0.8857+0.3677j</td><td>+0.7310+0.7109j</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>m=1</td><td>+0.9257+0.4725j</td><td>+0.6571+0.7225j</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>m=63</td><td>...</td><td>...</td><td>...</td><td>...</td><td>+0.2892-0.9277j</td><td>+0.5982-0.8234j</td></tr>
                </table>
                <p style='text-align:center;'><img src='images/chapter06/01_adc_iq_slice.png' width='760'></p>

                <h3>4. 本层能证明什么</h3>
                <p>ADC/IQ 层能证明:处理链的原始输入是一帧完整复数矩阵,而不是单个幅度值或最终状态。图中只展示一个 Chirp 的局部切片,完整的 64 × 128 数据仍全部参与后续 FFT。</p>
                <p><b>边界:</b>这一层还不能直接给出距离和速度。距离来自快时间拍频,速度来自跨 Chirp 的慢时间相位变化。</p>
            """,
            "Range FFT": """
                <h2>Range FFT:从快时间拍频得到距离</h2>
                <p>Range FFT 接收完整 ADC/IQ 矩阵的每一行,也就是每个 Chirp 内的 128 个复数快时间样本。它沿快时间轴计算 FFT,把"一个 Chirp 内的拍频"变成"距离 bin"。</p>
                <p>这一节引入三个新对象:<b>快时间窗</b>、<b>range_fft[m,k]</b> 和 <b>距离候选分数 S<sub>R</sub>[k]</b>。它们分别回答:如何准备一个 Chirp、FFT 后矩阵长什么样、怎样从完整矩阵里找出目标距离。</p>

                <h3>1. 输入与输出</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>阶段</th><th align='left'>数据形状</th><th align='left'>第二个轴的含义</th></tr>
                    <tr><td>输入 adc_iq[m,n]</td><td>64 × 128 complex</td><td>ADC sample / 快时间</td></tr>
                    <tr><td>输出 range_fft[m,k]</td><td>64 × 128 complex</td><td>Range bin / 距离单元</td></tr>
                </table>
                <p>注意这里不是只处理一个 Chirp,也不是只保留一个距离点。处理链会对 <b>64 行 Chirp</b> 逐行执行同样的操作,所以输出仍然是一整个 64 × 128 复数矩阵。变化的是第二个轴:原来列 n 表示 ADC 采样时刻,处理后列 k 表示距离 bin。</p>

                <h3>2. 为什么先要引入快时间窗</h3>
                <p>FFT 只能处理有限长度的数据。每个 Chirp 只有 128 个采样点,直接截取会带来频谱泄漏。当前参考处理先对每行快时间数据乘以 128 点 Hann 窗,再做 Range FFT:</p>
                <p style='text-align:center;'><b>windowed_fast_time = adc_iq[m, :] × hann(128)</b></p>
                <p>Hann 窗的作用是降低距离旁瓣,让强峰附近的泄漏更可控。它不会改变样本数量,也不会替算法预先选择目标位置。</p>

                <h3>3. Range FFT 矩阵展示</h3>
                <p>对每一行做 Range FFT 后,得到 range_fft[m,k]。下面的表格展示了这个复数矩阵的一部分。省略号表示中间行列仍然存在,并没有被删除。</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>range_fft[m,k]</th><th align='left'>k=0</th><th align='left'>k=7</th><th align='left'>k=8</th><th align='left'>k=9</th><th align='left'>...</th><th align='left'>k=127</th></tr>
                    <tr><td>m=0</td><td>-0.1924+0.3305j</td><td>-31.8023+1.1797j</td><td><b>+63.2340-0.4811j</b></td><td>-31.9969-0.5525j</td><td>...</td><td>+0.2972-0.4103j</td></tr>
                    <tr><td>m=1</td><td>...</td><td>...</td><td><b>+55.9358+29.8543j</b></td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>m=2</td><td>...</td><td>...</td><td><b>+35.5376+52.4216j</b></td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>m=63</td><td>+0.0167+0.3493j</td><td>-27.7318+15.8685j</td><td><b>+55.9341-29.9642j</b></td><td>-28.7658+14.5818j</td><td>...</td><td>+0.0030-0.1095j</td></tr>
                </table>
                <p>表中 k=8 的复数值明显更强,但它此时还只是矩阵中的一列。它成为候选距离,是后面扫描全部 128 个 Range bin 后得到的结果。</p>

                <h3>4. 怎样从矩阵变成距离候选</h3>
                <p>Range FFT 后,对每个距离 bin 计算功率:</p>
                <p style='text-align:center;'><b>P<sub>R</sub>[m,k] = |range_fft[m,k]|²</b></p>
                <p>再跨 64 个 Chirp 取最大功率分数:</p>
                <p style='text-align:center;'><b>S<sub>R</sub>[k] = max<sub>m</sub> P<sub>R</sub>[m,k]</b></p>
                <p>这里引入 S<sub>R</sub>[k] 是为了把 64 × 128 的 Range FFT 复数矩阵压缩成一条"距离方向扫描曲线"。它不是新的传感器数据,而是从完整 Range FFT 矩阵计算出的距离候选分数。</p>
                <p>扫描全部 128 个 Range bin 后,最大峰落在 <b>k=8</b>。根据参考参数,Range bin 间隔为 0.234375 m,因此该候选距离为:</p>
                <p style='text-align:center;'><b>R = 8 × 0.234375 m = 1.875 m</b></p>

                <h3>5. 结果图</h3>
                <p style='text-align:center;'><img src='images/chapter06/02_range_profile.png' width='760'></p>
                <p>图中单个 Chirp 的 Range Profile 在 bin 8 附近出现明显峰值,与预设目标距离一致。这里显示的是幅度,实际后续处理仍保留复数 Range FFT 值。</p>

                <h3>6. 闭环检查</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>检查点</th><th align='left'>结果</th><th align='left'>说明</th></tr>
                    <tr><td>输入是否完整</td><td>64 × 128 complex ADC/IQ</td><td>完整一帧参与处理,不是局部图像参与处理</td></tr>
                    <tr><td>轴是否正确变化</td><td>n → k</td><td>第二个轴从 ADC sample 变成 Range bin</td></tr>
                    <tr><td>候选距离</td><td>k=8 → 1.875 m</td><td>与受控场景真值一致</td></tr>
                    <tr><td>相位是否保留</td><td>保留 range_fft 复数值</td><td>为后续 Doppler FFT 提供慢时间相位</td></tr>
                </table>

                <h3>7. 本层能证明什么</h3>
                <p>Range FFT 能证明:快时间拍频已经被正确映射到距离轴,目标距离候选来自完整距离扫描。</p>
                <p><b>边界:</b>Range FFT 本身还没有完成速度估计。若此时只保存 |range_fft|,跨 Chirp 相位会丢失,后续 Doppler 处理就失去关键输入。</p>
            """,
            "Doppler / R-D": """
                <h2>Doppler / Range-Doppler:从慢时间相位得到速度</h2>
                <p>Range FFT 之后,数据变成 range_fft[m,k]。固定某个 Range bin,沿 64 个 Chirp 方向观察,就得到一条慢时间复数序列。运动目标会让这条序列的相位随 Chirp 编号持续转动。</p>
                <p>这一节引入四个新对象:<b>slow_time</b>、<b>Doppler FFT</b>、<b>range_doppler_complex[a,k]</b> 和 <b>range_doppler_power[a,k]</b>。它们分别回答:拿哪条序列测速度、怎样分离相位旋转速度、二维复数矩阵长什么样、怎样从二维功率图找到候选目标。</p>

                <h3>1. Doppler FFT 的输入与输出</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>阶段</th><th align='left'>数据形状</th><th align='left'>含义</th></tr>
                    <tr><td>输入 range_fft[m,k]</td><td>64 × 128 complex</td><td>Chirp × Range bin</td></tr>
                    <tr><td>沿 m 轴做 Doppler FFT</td><td>每个 k 都处理一条 64 点慢时间序列</td><td>分离同一距离内的相位旋转速度</td></tr>
                    <tr><td>输出 range_doppler_complex[a,k]</td><td>64 × 128 complex</td><td>Doppler bin × Range bin</td></tr>
                </table>
                <p>这里的关键是:Doppler FFT 不是只对 k=8 做一次。完整处理会对全部 128 个距离 bin 分别取出慢时间序列并做 64 点 FFT,所以输出仍然是 64 × 128 的二维矩阵。</p>

                <h3>2. 慢时间序列从哪里来</h3>
                <p>Range FFT 输出矩阵中,一列 range_fft[:, k] 表示同一个距离 bin 在 64 个 Chirp 中的复数值。对于候选距离 k=8,可以取出:</p>
                <p style='text-align:center;'><b>slow_time = range_fft[:, 8]</b></p>
                <p>这条序列仍然是复数。它的幅度表示该距离单元的回波强弱,相位随 Chirp 编号的变化则包含径向速度信息。当前处理对每条 slow_time 乘以 64 点 Hann 窗,再做 Doppler FFT:</p>
                <p style='text-align:center;'><b>range_doppler_complex[:, k] = FFT(slow_time × hann(64))</b></p>

                <h3>3. Doppler FFT 矩阵展示</h3>
                <p>Doppler FFT 后,矩阵第一维不再是 Chirp 编号,而是居中后的 Doppler 数组行 a;第二维仍然是 Range bin k。下面展示二维结果矩阵的一部分。</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>range_doppler_complex[a,k]</th><th align='left'>k=0</th><th align='left'>k=1</th><th align='left'>k=2</th><th align='left'>...</th><th align='left'>k=8</th><th align='left'>...</th><th align='left'>k=127</th></tr>
                    <tr><td>a=0, d=-32</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>a=1, d=-31</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>a=36, d=+4</td><td>...</td><td>...</td><td>...</td><td>...</td><td>旁瓣/邻近能量</td><td>...</td><td>...</td></tr>
                    <tr><td><b>a=37, d=+5</b></td><td>...</td><td>...</td><td>...</td><td>...</td><td><b>主峰:k=8</b></td><td>...</td><td>...</td></tr>
                    <tr><td>a=38, d=+6</td><td>...</td><td>...</td><td>...</td><td>...</td><td>旁瓣/邻近能量</td><td>...</td><td>...</td></tr>
                    <tr><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                    <tr><td>a=63, d=+31</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>
                </table>
                <p>这个表格说明:Range-Doppler Map 不是另一种独立数据源,而是 range_doppler_complex[a,k] 或其功率 |·|² 的二维显示。</p>

                <h3>4. 为什么 a=37 对应 d=+5</h3>
                <p>Doppler FFT 后执行 fftshift,把零 Doppler 放到中间。64 点 Doppler 轴中,居中后的数组行 a 与有符号 Doppler bin d 的关系为:</p>
                <p style='text-align:center;'><b>d = a - 32</b></p>
                <p>扫描结果位于数组行 <b>a=37</b>,因此:</p>
                <p style='text-align:center;'><b>d = 37 - 32 = +5</b></p>
                <p>速度 bin 间隔为 0.09765625 m/s,所以:</p>
                <p style='text-align:center;'><b>v = 5 × 0.09765625 m/s = 0.48828125 m/s</b></p>

                <h3>5. Doppler Profile 与 Range-Doppler Map</h3>
                <p>定位到 k=8 后,取出 range_fft[:, 8] 作为 Doppler FFT 的输入慢时间序列;对应输出 range_doppler_complex[:, 8] 的功率曲线就是 Doppler Profile。</p>
                <p style='text-align:center;'><img src='images/chapter06/03_doppler_profile.png' width='760'></p>
                <p>把全部距离 bin 的 Doppler Profile 按二维坐标组织起来,就是 Range-Doppler Map。</p>
                <p style='text-align:center;'><img src='images/chapter06/04_range_doppler_map.png' width='760'></p>

                <h3>6. 从二维矩阵到功率扫描</h3>
                <p>候选检测通常不直接比较复数本身,而是比较功率:</p>
                <p style='text-align:center;'><b>P<sub>RD</sub>[a,k] = |range_doppler_complex[a,k]|²</b></p>
                <p>当前参考链先由 Range FFT 得到 candidate_range_bins,再在这些候选距离列中扫描全部 Doppler 行。这样可以把"距离候选"和"速度候选"连成闭环:</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>步骤</th><th align='left'>输入</th><th align='left'>输出</th><th align='left'>解释</th></tr>
                    <tr><td>Range 扫描</td><td>range_fft[m,k]</td><td>k=8</td><td>目标距离候选为 1.875 m</td></tr>
                    <tr><td>Doppler 扫描</td><td>range_doppler_power[:, 8]</td><td>a=37, d=+5</td><td>目标速度候选为 0.48828125 m/s</td></tr>
                    <tr><td>二维闭环</td><td>P<sub>RD</sub>[a,k]</td><td>(a=37, k=8)</td><td>同一个目标在距离-速度图中形成主峰</td></tr>
                </table>

                <h3>7. 本层能证明什么</h3>
                <p>Doppler / Range-Doppler 层能证明:同一距离 bin 的跨 Chirp 相位变化已经被正确映射到速度轴,二维主峰落在 <b>Range bin 8</b> 和 <b>Doppler bin +5</b>。</p>
                <p><b>边界:</b>Range-Doppler Map 是距离-速度能量证据,不是人体身份标签,也不包含角度维。正负速度方向还依赖系统的 I/Q 和 FFT 符号约定。</p>
            """,
            "Candidate / Feature": """
                <h2>Candidate / Feature:从二维结果进入证据路线</h2>
                <p>完成 Range-Doppler 后,处理链已经得到完整二维功率矩阵。下一步不是直接输出 Presence,而是把二维能量整理成候选目标或距离门特征。</p>

                <h3>1. 候选目标路线</h3>
                <p>当前参考脚本先用 Range 扫描得到 candidate_range_bins,再只在这些候选距离列中扫描 Doppler 峰。也就是说,候选不是由真值直接指定,而是由数据中的功率峰逐步筛出来。</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>步骤</th><th align='left'>输入</th><th align='left'>输出</th></tr>
                    <tr><td>距离候选</td><td>S<sub>R</sub>[k] = max<sub>m</sub>|range_fft[m,k]|²</td><td>candidate_range_bins,例如 k=8</td></tr>
                    <tr><td>二维候选</td><td>range_doppler_power[:, candidate_range_bins]</td><td>主峰 a=37, k=8</td></tr>
                    <tr><td>坐标换算</td><td>k=8, d=+5</td><td>R=1.875 m, v=0.48828125 m/s</td></tr>
                </table>

                <h3>2. 距离门特征路线</h3>
                <p>除了完整二维候选,也可以固定目标附近距离门,统计非零 Doppler 能量、正负速度比例、跨帧变化或微动特征。这条路线更接近某些低功耗 Presence 模组的输出方式:它们不一定给完整 Range-Doppler Map,而是给每个距离门的运动能量或存在能量。</p>

                <h3>3. 结果如何理解</h3>
                <p style='text-align:center;'><img src='images/chapter06/01_integer_bin_reference_pipeline.png' width='760'></p>
                <p>在整数 bin 基准场景中,候选路线恢复出 k=8 和 d=+5,与已知真值一致。这说明参考处理链的坐标映射和候选扫描在该受控场景下是闭合的。</p>

                <h3>4. 本层能证明什么</h3>
                <p>Candidate / Feature 层能证明:处理结果可以被整理成应用层可用的局部证据,例如目标距离、速度、能量,或距离门运动/微动特征。</p>
                <p><b>边界:</b>候选仍然不是最终 Presence。候选可能来自人体,也可能来自机械干扰、强背景、旁瓣或噪声。是否宣布有人,需要跨帧状态逻辑。</p>
            """,
            "Presence": """
                <h2>Presence:从单帧证据到稳定状态</h2>
                <p>核心流程先验证单帧参考链:ADC/IQ 能否经过 Range FFT、Doppler FFT 和候选扫描,恢复已知目标的距离与速度。Presence 是下一层应用状态,它不能由单帧主峰直接翻译得到。</p>

                <h3>1. 输入是什么</h3>
                <p>Presence 接收的不是原始 ADC,而是前面处理后形成的逐帧证据:</p>
                <ul>
                    <li>候选目标:距离、速度、能量、持续性。</li>
                    <li>距离门特征:运动能量、微动能量、相位质量、背景变化。</li>
                    <li>数据质量:丢帧、饱和、低 SNR、异常时间戳。</li>
                </ul>

                <h3>2. 状态机为什么必要</h3>
                <p>单帧候选可能来自噪声或短时干扰,也可能在人体静坐时暂时消失。因此产品通常需要连续确认、进入/退出滞回和 Hold Time。</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>机制</th><th align='left'>作用</th><th align='left'>代价</th></tr>
                    <tr><td>连续确认</td><td>避免单帧噪声直接触发有人</td><td>增加进入响应延迟</td></tr>
                    <tr><td>滞回</td><td>进入和退出使用不同条件,减少抖动</td><td>参数不当会漏检或误保持</td></tr>
                    <tr><td>Hold Time</td><td>保护静坐、短暂停顿和微动变弱阶段</td><td>增加离场释放延迟</td></tr>
                </table>

                <h3>3. 与基准流程的关系</h3>
                <p>基准流程证明的是:在受控单目标、整数 bin、低噪声条件下,处理链能把已知目标恢复到正确的 Range-Doppler 单元。这个结果可以作为 Presence 的输入证据,但还不是 Presence 评估本身。</p>
                <p>真正的 Presence 需要跨多帧场景验证:人进入、持续运动、坐下微动、离开,以及风扇、背景和弱目标干扰。后续演示会继续把这些复杂场景拆开验证。</p>

                <h3>4. 本层能证明什么</h3>
                <p>Presence 层能证明:逐帧证据经过时间逻辑后,是否形成稳定、符合产品语义的有人/无人状态。</p>
                <p><b>边界:</b>如果只看到最终 Presence,无法反推内部错误一定发生在 ADC、Range FFT、Doppler FFT、候选检测还是状态机。必须结合可获得的数据层判断。</p>
            """,
            "非整数 bin 峰值估计": """
                <h2>流程演示示例 1:非整数 bin 与峰值估计</h2>
                <p>整数 bin 基准场景用于检查处理链坐标是否正确;本演示把目标故意放到非整数 Range/Doppler bin 上,用来观察频谱泄漏、整数峰偏差和连续峰值估计。</p>

                <h3>本示例输入数据</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>数据文件</th><th align='left'>形状</th><th align='left'>如何使用</th></tr>
                    <tr><td><code>knowledge/data/noninteger_bin_demo_adc_iq.csv</code></td><td>64 × 128 complex</td><td>按 <code>chirp_m</code> 和 <code>sample_n</code> 还原为 <code>adc_iq[m,n] = i + jq</code></td></tr>
                </table>
                <p>本页中的 Range 峰扩散图和 Doppler 峰扩散图都从这份完整 ADC/IQ 矩阵推导:先沿快时间做 Range FFT,再取候选距离列沿慢时间做 Doppler FFT。场景真值只用于最后核对,不参与峰值搜索。</p>

                <h3>1. 场景设定</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>场景量</th><th align='left'>设定值</th><th align='left'>说明</th></tr>
                    <tr><td>目标距离</td><td>1.95703125 m</td><td>对应非整数 Range bin 8.35</td></tr>
                    <tr><td>径向速度</td><td>+0.52734375 m/s</td><td>对应非整数 Doppler bin +5.4</td></tr>
                    <tr><td>目标幅度</td><td>1.0</td><td>教学归一化幅度</td></tr>
                    <tr><td>复噪声标准差</td><td>0.03</td><td>固定随机种子,可重复</td></tr>
                </table>

                <h3>2. 为什么非整数 bin 会扩散</h3>
                <p>目标位于整数 bin 时,能量更集中;目标位于 8.35 或 +5.4 这类非整数位置时,有限长度 FFT 的离散频率格无法正好对齐目标频率,能量会扩散到相邻 bin。这个扩散不是多个目标,而是有限观测和离散 FFT 造成的峰形。</p>
                <p>因此处理链不能只说"最大整数 bin 是答案",还要观察最大峰附近的功率形状,并在必要时做局部峰值估计。</p>

                <h3>3. Range 方向结果</h3>
                <p>Range 扫描结果中,整数峰位于 k=8,但 k=9 仍有明显能量,说明真实目标在两个 bin 之间。</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>Range bin</th><th align='left'>相对最大值</th><th align='left'>解释</th></tr>
                    <tr><td>k=7</td><td>0.082</td><td>主瓣边缘或旁瓣</td></tr>
                    <tr><td>k=8</td><td>1.000</td><td>最大整数峰</td></tr>
                    <tr><td>k=9</td><td>0.683</td><td>非整数目标造成的相邻 bin 能量</td></tr>
                    <tr><td>k=10</td><td>0.014</td><td>远离主峰后明显降低</td></tr>
                </table>
                <p style='text-align:center;'><img src='images/chapter07/01_noninteger_range_peak.png' width='760'></p>

                <h3>4. Doppler 方向结果</h3>
                <p>Doppler 扫描中,整数峰位于 d=+5,但 d=+6 仍接近主峰,说明真实速度位于两个 Doppler bin 之间。</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>Doppler bin</th><th align='left'>相对最大值</th><th align='left'>解释</th></tr>
                    <tr><td>d=+4</td><td>0.069</td><td>主峰左侧能量</td></tr>
                    <tr><td>d=+5</td><td>1.000</td><td>最大整数峰</td></tr>
                    <tr><td>d=+6</td><td>0.774</td><td>非整数速度造成的相邻 bin 能量</td></tr>
                    <tr><td>d=+7</td><td>0.022</td><td>远离主峰后降低</td></tr>
                </table>
                <p style='text-align:center;'><img src='images/chapter07/02_noninteger_doppler_peak.png' width='760'></p>

                <h3>5. 闭环结果</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>量</th><th align='left'>数据处理得到</th><th align='left'>场景真值</th><th align='left'>说明</th></tr>
                    <tr><td>Range bin</td><td>k_hat = 8.3674</td><td>8.35</td><td>由局部功率形状估计连续位置</td></tr>
                    <tr><td>距离</td><td>1.9611 m</td><td>1.95703125 m</td><td>误差来自噪声、窗函数和离散采样</td></tr>
                    <tr><td>Doppler bin</td><td>d_hat = +5.4126</td><td>+5.4</td><td>由局部 Doppler 峰形估计连续位置</td></tr>
                    <tr><td>速度</td><td>+0.5286 m/s</td><td>+0.52734375 m/s</td><td>与真值接近</td></tr>
                </table>

                <h3>6. 本示例说明什么</h3>
                <p><b>整数 bin 基准验证处理链坐标,非整数 bin 演示说明真实目标不一定落在整数 FFT 格点上。</b> 因此需要观察泄漏、主瓣形状和局部估计,而不是把最大整数 bin 当作唯一距离或速度。</p>
            """,
            "强背景下的弱动态目标": """
                <h2>流程演示示例 2:强背景下的弱目标</h2>
                <p>示例 1 中目标是主要能量峰;真实房间里,墙面、家具和固定反射可能比人体更强。这个示例展示:最大 Range 峰不一定是我们关心的人体目标,候选路线和距离门动态特征路线可能给出不同证据。</p>

                <h3>本示例输入数据</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>数据文件</th><th align='left'>包含场景</th><th align='left'>如何使用</th></tr>
                    <tr><td><code>knowledge/data/background_weak_target_adc_iq.csv</code></td><td><code>background_only</code> 和 <code>background_plus_weak_target</code>,每组 64 × 128 complex</td><td>分别还原为 ADC/IQ 矩阵后运行同一条 Range FFT → Doppler FFT → Range-Doppler 处理链</td></tr>
                </table>
                <p>背景-only 数据用于对照;加入弱目标后的混合数据用于候选路线和动态距离门特征路线。两份数据共用同一背景和噪声,差异主要来自叠加的弱运动目标。</p>

                <h3>1. 场景设定</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>成分</th><th align='left'>Range bin</th><th align='left'>Doppler bin</th><th align='left'>幅度</th><th align='left'>说明</th></tr>
                    <tr><td>静态背景 1</td><td>4.0</td><td>0.0</td><td>0.55</td><td>强静态反射</td></tr>
                    <tr><td>静态背景 2</td><td>12.0</td><td>0.0</td><td>0.32</td><td>较弱静态反射</td></tr>
                    <tr><td>弱运动目标</td><td>8.35</td><td>+2.4</td><td>0.16</td><td>低于最强背景,但有非零 Doppler</td></tr>
                    <tr><td>噪声</td><td>-</td><td>-</td><td>0.055</td><td>复高斯噪声</td></tr>
                </table>

                <h3>2. 候选路线为什么会偏向强背景</h3>
                <p>候选路线先看 Range 方向最大功率。当前相对门限下,背景-only 和加入弱目标后的最大 Range 峰都在 k=4,因此候选 Range bin 为 [4]。如果后续只在候选距离列继续扫 Doppler,就不会主动发现未进入候选集合的 k=8/k=9。</p>
                <p style='text-align:center;'><img src='images/chapter07/03_background_range_candidate.png' width='760'></p>
                <p>这说明"最强反射"不等于"人体目标"。k=4 是真实静态反射,但对 Presence 来说,它可能不是我们关心的动态人体证据。</p>

                <h3>3. 距离门动态特征路线</h3>
                <p>另一条路线遍历完整 Range-Doppler 功率矩阵,排除近零 Doppler 后,统计每个距离门的动态能量:</p>
                <p style='text-align:center;'><b>F_dyn[k] = Σ P_RD[a,k], 其中 |d(a)| &gt; 1</b></p>
                <p>这样做不是寻找总功率最强的距离门,而是寻找非零 Doppler 区域更活跃的距离门。当前结果中,动态特征峰出现在 k=8,候选距离门为 [8, 9]。</p>
                <p style='text-align:center;'><img src='images/chapter07/04_dynamic_range_gate_feature.png' width='760'></p>

                <h3>4. 二维图中的证据</h3>
                <p>Range-Doppler 图可以同时看到两类结构:k=4 的强背景主要集中在零 Doppler 附近;k=8 附近的弱目标虽然总功率不如背景,但在非零 Doppler 区域形成动态能量。</p>
                <p style='text-align:center;'><img src='images/chapter07/05_background_weak_range_doppler.png' width='760'></p>

                <h3>5. 两条路线如何比较</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>距离门</th><th align='left'>Range 强度证据</th><th align='left'>非零 Doppler 证据</th><th align='left'>当前解释</th></tr>
                    <tr><td>k=4</td><td>强,进入 Range 候选</td><td>弱,主要是零 Doppler</td><td>强静态背景</td></tr>
                    <tr><td>k=8</td><td>弱,未进入普通 Range 候选</td><td>强,动态特征峰</td><td>弱运动目标主要候选</td></tr>
                    <tr><td>k=9</td><td>弱,可能来自主瓣扩散</td><td>较强,超过动态特征门限</td><td>k=8 附近相邻候选,不一定是第二目标</td></tr>
                </table>

                <h3>6. 本示例说明什么</h3>
                <p><b>候选路线和特征路线关注的物理量不同。</b> 前者偏向强反射,后者偏向动态能量。Presence 系统需要知道自己用的是哪条证据路线,不能把"最亮峰"直接等同于"人体"。</p>
            """,
            "逐帧证据到 Presence 状态": """
                <h2>逐帧证据到 Presence 状态</h2>
                <p>前面的演示得到的是单帧频谱、候选或特征；本示例进一步说明这些结果怎样变成跨帧的稳定产品状态。这里不再从 ADC/IQ 开始，而是明确从逐帧运动证据和微动证据开始验证状态机。</p>

                <h3>0. 输入数据是什么</h3>
                <p>本示例的输入不是完整 ADC/IQ，而是一组 140 帧的应用层证据序列。每帧间隔 0.1 s，共 13.9 s。字段如下：</p>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>字段</th><th align='left'>含义</th><th align='left'>来源边界</th></tr>
                    <tr><td><code>time_s</code></td><td>当前帧时间</td><td>帧时间轴</td></tr>
                    <tr><td><code>motion_evidence[t]</code></td><td>明显运动证据</td><td>可由动态 Doppler、目标候选或运动 Energy 提取</td></tr>
                    <tr><td><code>micro_motion_evidence[t]</code></td><td>微动/持续存在证据</td><td>可由低速特征、相位变化或 presence Energy 提取</td></tr>
                    <tr><td><code>presence_score[t]</code></td><td>单帧融合分数</td><td><code>max(motion, micro_motion)</code></td></tr>
                    <tr><td><code>product_state[t]</code></td><td>状态机输出</td><td>ABSENT / PRESENT</td></tr>
                </table>
                <p><b>关键边界：</b>这组数据验证的是“证据到状态”的应用层闭环，不证明底层 ADC/IQ、Range FFT 或 Doppler FFT 的真实硬件表现。</p>

                <h3>1. 输入证据</h3>
                <p>场景以 0.1 s 为一帧,共 140 帧,持续 13.9 s。每帧包含两类归一化证据:</p>
                <ul>
                    <li><b>E_motion[t]</b>:进入、离开、明显动作时升高。</li>
                    <li><b>E_micro[t]</b>:目标稳定停留后,由呼吸或微动维持。</li>
                </ul>
                <p>瞬时 Presence 分数取二者较大值:</p>
                <p style='text-align:center;'><b>S[t] = max(E_motion[t], E_micro[t])</b></p>

                <h3>2. 状态机规则</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>状态</th><th align='left'>条件</th><th align='left'>结果</th></tr>
                    <tr><td>ABSENT</td><td>连续 3 帧 S[t] ≥ T_enter</td><td>切换为 PRESENT</td></tr>
                    <tr><td>PRESENT</td><td>连续 5 帧 S[t] &lt; T_exit</td><td>启动 Hold-on 计时</td></tr>
                    <tr><td>PRESENT + Hold</td><td>证据恢复</td><td>继续保持 PRESENT</td></tr>
                    <tr><td>PRESENT + Hold</td><td>Hold Time 到期</td><td>释放为 ABSENT</td></tr>
                </table>

                <h3>3. 状态时间线</h3>
                <p style='text-align:center;'><img src='images/chapter07/09_presence_state_timeline.png' width='760'></p>
                <p>图上方是运动和微动证据,下方是产品状态。证据下降后,系统不会立刻释放,而是在 PRESENT 内部执行 Hold-on 计时;证据恢复则继续保持 PRESENT。</p>

                <h3>4. 关键事件</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>帧号</th><th align='left'>时间</th><th align='left'>状态变化</th><th align='left'>触发依据</th></tr>
                    <tr><td>19</td><td>1.9 s</td><td>ABSENT → PRESENT</td><td>连续 3 帧达到进入门限</td></tr>
                    <tr><td>82</td><td>8.2 s</td><td>PRESENT 开始 Hold-on</td><td>连续 5 帧低于退出门限</td></tr>
                    <tr><td>83</td><td>8.3 s</td><td>PRESENT 继续保持</td><td>证据恢复到退出门限以上</td></tr>
                    <tr><td>106</td><td>10.6 s</td><td>PRESENT 开始 Hold-on</td><td>离开动作后证据持续不足</td></tr>
                    <tr><td>126</td><td>12.6 s</td><td>PRESENT → ABSENT</td><td>Hold Time 到期</td></tr>
                </table>

                <h3>5. 本示例说明什么</h3>
                <p><b>Presence 分数不是产品状态。</b> 分数是逐帧证据;产品状态需要连续确认、退出确认和 Hold Time。这样可以减少单帧噪声触发,也可以保护静坐或短暂停顿,但会带来进入和离场延迟。</p>
            """,
            "真实流程入口": """
                <h2>真实流程入口：先判断模组开放哪一层数据</h2>
                <p>真实模组不同于可控仿真。仿真可以保存每一层中间数据并知道真值；真实模组通常只向应用 MCU 开放某一层或几层输出。因此真实流程的第一步不是直接跑算法，而是确认：当前拿到的数据位于处理链的哪一层。</p>

                <h3>0. 真实流程先问三个问题</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>问题</th><th align='left'>为什么重要</th></tr>
                    <tr><td>拿到的是哪一层数据？</td><td>决定可以从 ADC/IQ、FFT 后结果、目标列表、Energy 特征还是最终状态开始分析。</td></tr>
                    <tr><td>数据有没有参数和坐标说明？</td><td>没有采样率、FFT、bin 间隔和方向约定，就无法把数组解释成距离、速度或时间。</td></tr>
                    <tr><td>数据有没有时间和场景真值？</td><td>没有帧号、时间戳和人工记录，就很难评估误报、漏报、进入延迟和释放延迟。</td></tr>
                </table>

                <h3>1. 数据入口决定能验证到哪里</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>数据层</th><th align='left'>MCU 可以做什么</th><th align='left'>主要限制</th></tr>
                    <tr><td>ADC/IQ</td><td>完整 Range/Doppler 处理、偏置、饱和、相位和微动分析</td><td>数据率和计算压力最高</td></tr>
                    <tr><td>Range FFT 复数</td><td>慢时间 Doppler、距离门相位、微动和特征</td><td>不能重做 Range FFT 前处理</td></tr>
                    <tr><td>Range-Doppler 复数/功率</td><td>候选、距离门动态特征、Tracking、Presence 证据</td><td>功率图缺少复数相位;复数图也不能重做 Doppler FFT 前处理</td></tr>
                    <tr><td>目标列表/点云</td><td>区域规则、目标连续性、业务状态</td><td>底层检测、合并和跟踪策略已由厂商固定</td></tr>
                    <tr><td>motion/presence energy 或状态</td><td>门限、滞回、Hold Time、误报漏报评估</td><td>难以定位底层原因</td></tr>
                </table>

                <h3>2. 只有数据还不够</h3>
                <p>真实接口还必须说明雷达参数、时间、通道、标定和数值格式。否则一个 bin 无法可靠换算为距离、速度或角度,也无法判断某次变化来自目标、配置变化还是数据异常。</p>
                <ul>
                    <li>射频和 Chirp:载波频率、带宽、Chirp slope、Chirp 周期。</li>
                    <li>采样和 FFT:ADC 采样率、采样点数、FFT 长度、窗函数、缩放规则。</li>
                    <li>坐标约定:Range 起点、Doppler 是否 fftshift、速度正方向。</li>
                    <li>时间信息:帧号、时间戳、丢帧、实际帧间隔。</li>
                    <li>标定状态:通道相位、增益、IQ 校正、背景更新状态。</li>
                </ul>

                <h3>3. 真实数据分析入口</h3>
                <p>后续真实数据章节应先说明拿到的数据层,再按可验证边界展开。比如只拿到 Presence 状态,就只能评估触发、保持、抖动和延迟;拿到 Range-Doppler 功率,才能继续分析距离-速度结构和候选来源;拿到 ADC/IQ,才可能重做完整处理链。</p>
                <p><b>本节当前作为入口框架。</b> 真实数据示例后续按实际保存的数据类型补充,避免先假设一定拥有完整 ADC/IQ 或 Range-Doppler。</p>
            """,
            "从 ADC/IQ 开始（TBD）": """
                <h2>从 ADC/IQ 开始（TBD）</h2>
                <p>当真实模组开放原始 ADC/IQ 时，分析可以从最底层重新走完整处理链。这是诊断能力最强的入口，但也需要最多的数据说明和计算资源。</p>

                <h3>需要准备的数据</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>内容</th><th align='left'>说明</th></tr>
                    <tr><td>原始 I/Q 矩阵</td><td><code>adc_iq[rx, chirp, sample]</code> 或 <code>adc_iq[tx, rx, chirp, sample]</code></td></tr>
                    <tr><td>采样与 Chirp 参数</td><td>采样率、每 Chirp 采样点数、Chirp slope、Chirp 周期、帧周期。</td></tr>
                    <tr><td>通道说明</td><td>RX/TX 顺序、虚拟通道映射、I/Q 排列、字节序、Q 格式或缩放。</td></tr>
                    <tr><td>质量标记</td><td>丢帧、饱和、AGC、配置切换、时间戳异常。</td></tr>
                    <tr><td>场景真值</td><td>无人、进入、走动、静坐、离开、风扇、遮挡等人工记录。</td></tr>
                </table>

                <h3>分析路线</h3>
                <p><b>ADC/IQ → 数据质量检查 → 去偏置/校正 → Range FFT → Doppler FFT → 候选/特征 → Presence。</b></p>
                <p>这个入口可以验证偏置、饱和、I/Q 失配、采样异常、窗函数、FFT 参数、Range-Doppler 结构和后续状态逻辑。</p>

                <h3>当前状态</h3>
                <p>TBD。后续拿到真实 ADC/IQ 录制包后，在这里展示完整数据表、局部波形、Range FFT、Doppler FFT、Range-Doppler 和事件级状态分析。</p>
            """,
            "从 Doppler FFT 开始（TBD）": """
                <h2>从 Doppler FFT 开始（TBD）</h2>
                <p>当真实模组已经完成 Range FFT 和 Doppler FFT，并开放 Range-Doppler 复数或功率图时，应用侧可以从距离-速度结构开始分析。</p>

                <h3>需要准备的数据</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>内容</th><th align='left'>说明</th></tr>
                    <tr><td>Range-Doppler 数据</td><td><code>range_doppler_complex[channel, doppler, range]</code> 或 <code>range_doppler_power[doppler, range]</code></td></tr>
                    <tr><td>坐标说明</td><td>Range bin 间隔、Doppler bin 间隔、是否 fftshift、速度正负方向。</td></tr>
                    <tr><td>FFT 处理说明</td><td>窗函数、FFT 长度、缩放、是否保留复数相位。</td></tr>
                    <tr><td>时间信息</td><td>帧号、帧周期、丢帧、配置切换。</td></tr>
                    <tr><td>场景真值</td><td>目标位置、运动方向、是否有人、干扰物状态。</td></tr>
                </table>

                <h3>分析路线</h3>
                <p><b>Range-Doppler → 局部峰/候选 → 距离门动态特征 → 跨帧证据 → Presence。</b></p>
                <p>这个入口适合分析风扇、弱目标、同距不同速目标、候选来源、动态距离门和状态机输入，但通常不能重做 ADC/IQ、Range FFT 或 Doppler FFT 前的处理。</p>

                <h3>当前状态</h3>
                <p>TBD。后续拿到真实 Range-Doppler 或 Doppler FFT 后结果后，在这里展示二维功率图、候选表、距离门特征和状态推导。</p>
            """,
            "从 Energy 开始（TBD）": """
                <h2>从 Energy 开始（TBD）</h2>
                <p>很多成品 Presence 模组不会开放完整 ADC/IQ 或 Range-Doppler，而是直接输出运动能量、存在能量、距离门能量、置信度或 Presence 状态。这个入口用于分析这类高层特征数据。</p>

                <h3>需要准备的数据</h3>
                <table width='100%' cellspacing='0' cellpadding='8' border='1'>
                    <tr bgcolor='#e8dfcf'><th align='left'>内容</th><th align='left'>说明</th></tr>
                    <tr><td>Energy 序列</td><td><code>motion_energy</code>、<code>presence_energy</code>、<code>range_energy[k]</code> 或厂商定义特征。</td></tr>
                    <tr><td>状态输出</td><td>Presence state、GPIO、事件、置信度或目标字段。</td></tr>
                    <tr><td>参数说明</td><td>距离门范围、灵敏度、门限、保持时间、背景更新、刷新周期。</td></tr>
                    <tr><td>时间与真值</td><td>时间戳、人工进入/离开记录、风扇/窗帘/宠物等干扰标记。</td></tr>
                </table>

                <h3>分析路线</h3>
                <p><b>Energy / Score → 阈值和趋势 → 进入/退出判断 → Hold Time → 产品状态。</b></p>
                <p>这个入口适合评估触发、保持、释放、误报和漏报，但不能直接确认底层误差发生在 ADC、Range FFT、Doppler FFT 还是候选阶段。</p>

                <h3>当前状态</h3>
                <p>TBD。后续拿到真实 Energy 日志后，在这里展示时间线、距离门能量、状态变化、人工真值对齐和事件级评估。</p>
            """,
        }
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(10)

        nav_panel = QWidget()
        nav_panel.setFixedWidth(280)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        version_label = QLabel("Radar Flow Analyzer  v0.5")
        version_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #126b5a; "
            "padding: 8px 10px; background: #d8eadf; border: 1px solid #b8d5c4; border-radius: 8px;"
        )
        nav_layout.addWidget(version_label)

        nav_title = QLabel("目录")
        nav_title.setStyleSheet("font-size: 15px; font-weight: 700; padding: 6px 8px;")
        nav_layout.addWidget(nav_title)

        self._outline_nav.setAlternatingRowColors(True)
        self._outline_nav.itemClicked.connect(self._on_outline_item_clicked)
        nav_layout.addWidget(self._outline_nav)

        content_panel = QWidget()
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        content_title = QLabel("内容")
        content_title.setStyleSheet("font-size: 15px; font-weight: 700; padding: 6px 8px;")
        content_layout.addWidget(content_title)

        self._content_browser.setReadOnly(True)
        self._content_browser.setOpenExternalLinks(False)
        self._content_browser.setSearchPaths([str(ROOT / "knowledge")])
        self._content_stack.addWidget(self._content_browser)
        self._window_demo = self._build_window_demo()
        self._content_stack.addWidget(self._window_demo)
        content_layout.addWidget(self._content_stack)

        root_layout.addWidget(nav_panel)
        root_layout.addWidget(content_panel)
        self.setCentralWidget(root)

        self._rebuild_outline("工具总览")
        self._content_stack.setCurrentWidget(self._content_browser)
        self._content_browser.setHtml(self._chapter_map["工具总览"])

        ai_dock = QDockWidget("AI 助手", self)
        ai_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        ai_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        ai_dock.setMinimumWidth(340)

        ai_widget = QWidget()
        ai_widget.setMinimumHeight(0)
        ai_layout = QVBoxLayout(ai_widget)
        ai_layout.setContentsMargins(6, 6, 6, 6)
        ai_layout.setSpacing(5)

        provider_row = QWidget()
        provider_layout = QGridLayout(provider_row)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.setHorizontalSpacing(5)
        provider_layout.setVerticalSpacing(4)

        for provider, spec in PROVIDERS.items():
            self._ai_provider_combo.addItem(str(spec["label"]), provider)
        self._ai_provider_combo.currentIndexChanged.connect(self._ai_provider_changed)
        self._ai_model_combo.setEditable(True)
        self._ai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_key_input.setPlaceholderText("环境变量优先；仅当前会话有效")
        self._ai_refresh_button.clicked.connect(self._load_ai_models)
        self._ai_refresh_button.setText("刷新")

        provider_layout.addWidget(QLabel("提供商"), 0, 0)
        provider_layout.addWidget(self._ai_provider_combo, 0, 1)
        provider_layout.addWidget(QLabel("模型"), 1, 0)
        provider_layout.addWidget(self._ai_model_combo, 1, 1)
        provider_layout.addWidget(self._ai_refresh_button, 1, 2)
        provider_layout.addWidget(self._ai_key_label, 2, 0)
        provider_layout.addWidget(self._ai_key_input, 2, 1)
        ai_layout.addWidget(provider_row)

        self._ai_cloud_confirm.setChecked(False)
        ai_layout.addWidget(self._ai_cloud_confirm)

        self._ai_context_button.clicked.connect(self._show_ai_context)
        ai_layout.addWidget(self._ai_context_button)

        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)
        self._ai_input.setMinimumHeight(30)
        input_layout.addWidget(self._ai_input)
        self._ai_send_button.clicked.connect(self._send_ai_question)
        self._ai_stop_button.setEnabled(False)
        self._ai_stop_button.clicked.connect(self._stop_ai_question)
        input_layout.addWidget(self._ai_send_button)
        input_layout.addWidget(self._ai_stop_button)
        ai_layout.addWidget(input_row)

        self._ai_status.setWordWrap(True)
        self._ai_status.setMaximumHeight(40)
        ai_layout.addWidget(self._ai_status)

        self._ai_output.setReadOnly(True)
        self._ai_output.setMinimumHeight(80)
        self._ai_output.setHtml(
            "<html><body><p><b>问 AI</b>：选择模型后直接输入问题。上下文包含当前页面、数据层和窗函数设置。</p></body></html>"
        )
        ai_layout.addWidget(self._ai_output, 1)

        ai_dock.setWidget(ai_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, ai_dock)
        self._ai_provider_changed()

    def _rebuild_outline(self, expanded_chapter: str | None) -> None:
        self._outline_nav.clear()
        for chapter in self._chapters:
            marker = "-" if chapter == expanded_chapter else "+"
            chapter_item = QListWidgetItem(f"{marker} {chapter}")
            chapter_item.setData(Qt.ItemDataRole.UserRole, ("chapter", chapter))
            chapter_font = QFont()
            chapter_font.setBold(True)
            chapter_font.setPointSize(10)
            chapter_item.setFont(chapter_font)
            chapter_item.setForeground(QColor("#24352f"))
            self._outline_nav.addItem(chapter_item)
            if chapter == expanded_chapter:
                for section in self._chapter_sections.get(chapter, []):
                    section_item = QListWidgetItem(f"      {section}")
                    section_item.setData(Qt.ItemDataRole.UserRole, ("section", chapter, section))
                    section_font = QFont()
                    section_font.setPointSize(9)
                    section_item.setFont(section_font)
                    section_item.setForeground(QColor("#6d675d"))
                    self._outline_nav.addItem(section_item)

    def _on_outline_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data[0] == "chapter":
            chapter_name = data[1]
            self._expanded_chapter = None if self._expanded_chapter == chapter_name else chapter_name
            self._current_chapter = chapter_name
            self._current_section = ""
            self._rebuild_outline(self._expanded_chapter)
            self._content_stack.setCurrentWidget(self._content_browser)
            self._content_browser.setHtml(self._chapter_map.get(chapter_name, ""))
            return

        chapter_name = data[1]
        section_name = data[2]
        self._expanded_chapter = chapter_name
        self._current_chapter = chapter_name
        self._current_section = section_name
        if section_name == "可调参数观察" and self._window_demo is not None:
            self._content_stack.setCurrentWidget(self._window_demo)
            self._update_window_demo()
            return
        self._content_stack.setCurrentWidget(self._content_browser)
        if section_name == "完整 I/Q 数据":
            self._content_browser.setHtml(
                self._csv_data_page(
                    "核心流程完整 I/Q 数据",
                    ["integer_bin_reference_adc_iq.csv"],
                    "整数 bin 基准场景。完整一帧为 64 × 128 complex，共 8192 个复数样本。核心流程中的 ADC/IQ、Range FFT、Doppler FFT、Range-Doppler 和候选结果都从这份数据推导。",
                )
            )
            return
        if section_name == "演示数据来源":
            self._content_browser.setHtml(
                self._csv_data_page(
                    "流程演示示例数据来源",
                    ["noninteger_bin_demo_adc_iq.csv", "background_weak_target_adc_iq.csv"],
                    "演示场景的完整输入数据。非整数 bin 示例使用一帧 64 × 128 complex；弱目标背景示例包含 background_only 和 background_plus_weak_target 两份 64 × 128 complex。Presence 状态示例从逐帧证据开始，因此没有 ADC/IQ 输入矩阵。",
                )
            )
            return
        self._content_browser.setHtml(self._section_map.get(section_name, self._chapter_map.get(chapter_name, "")))

    def _ai_provider_changed(self) -> None:
        provider = self._ai_provider_combo.currentData()
        self._ai_model_combo.clear()
        is_ollama = provider == "ollama"
        self._ai_refresh_button.setVisible(is_ollama)
        self._ai_key_label.setVisible(not is_ollama)
        self._ai_key_input.setVisible(not is_ollama)
        self._ai_cloud_confirm.setVisible(not is_ollama)
        self._ai_send_button.setEnabled(not is_ollama)
        if is_ollama:
            self._ai_status.setText("本地请求仅发送到 http://localhost:11434。")
            self._load_ai_models()
            return

        for model in PROVIDERS[provider]["models"]:
            self._ai_model_combo.addItem(str(model), str(model))
        key = environment_key(provider)
        self._ai_key_input.setText(key)
        key_status = "已读取环境变量" if key else "未设置环境变量"
        self._ai_cloud_confirm.setChecked(False)
        self._ai_status.setText(f"云端模型：{PROVIDERS[provider]['label']}；{PROVIDERS[provider]['env']} {key_status}。")

    def _load_ai_models(self) -> None:
        if self._ai_model_loader is not None and self._ai_model_loader.isRunning():
            return
        self._ai_model_combo.clear()
        self._ai_model_combo.addItem("正在读取本地模型……", "")
        self._ai_send_button.setEnabled(False)
        self._ai_model_loader = ModelLoader(self)
        self._ai_model_loader.loaded.connect(self._ai_models_loaded)
        self._ai_model_loader.failed.connect(self._ai_models_failed)
        self._ai_model_loader.start()

    def _ai_models_loaded(self, models: list[str]) -> None:
        self._ai_model_combo.clear()
        for model in models:
            self._ai_model_combo.addItem(model, model)
        self._ai_send_button.setEnabled(bool(models))
        self._ai_status.setText(f"已读取 {len(models)} 个本地模型。" if models else "Ollama 中没有已安装模型。")

    def _ai_models_failed(self, message: str) -> None:
        self._ai_model_combo.clear()
        self._ai_model_combo.addItem("qwen2.5:1.5b", "qwen2.5:1.5b")
        self._ai_model_combo.setEditable(True)
        self._ai_send_button.setEnabled(True)
        self._ai_status.setText(f"本地模型自动读取失败，可手动输入模型名。{message}")

    def _selected_ai_model(self) -> str:
        text = self._ai_model_combo.currentText().strip()
        index = self._ai_model_combo.currentIndex()
        if index >= 0 and text == self._ai_model_combo.itemText(index):
            model_data = self._ai_model_combo.itemData(index)
            if model_data:
                return str(model_data).strip()
        return text

    def _send_ai_question(self) -> None:
        question = self._ai_input.text().strip()
        provider = self._ai_provider_combo.currentData()
        model = self._selected_ai_model()
        if not question or not model:
            self._ai_status.setText("请选择模型并输入问题。")
            return
        if provider != "ollama" and not self._ai_cloud_confirm.isChecked():
            self._ai_status.setText("请先确认将当前上下文发送至云端模型服务。")
            return

        self._ai_output.append(f"<p><b>你：</b>{html.escape(question)}</p><p><b>AI：</b></p>")
        self._ai_input.clear()
        self._ai_send_button.setEnabled(False)
        self._ai_stop_button.setEnabled(True)
        self._ai_status.setText(f"{model} 正在生成……")
        self._ai_chat_worker = ChatWorker(
            str(provider),
            model,
            self._ai_key_input.text(),
            question,
            self._build_ai_context(),
        )
        self._ai_chat_worker.chunk_received.connect(self._append_ai_chunk)
        self._ai_chat_worker.failed.connect(self._ai_failed)
        self._ai_chat_worker.finished.connect(self._ai_finished)
        self._ai_chat_worker.start()

    def _append_ai_chunk(self, chunk: str) -> None:
        cursor = self._ai_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self._ai_output.setTextCursor(cursor)
        self._ai_output.ensureCursorVisible()

    def _ai_failed(self, message: str) -> None:
        self._ai_output.append(f"<p><b>请求失败：</b>{html.escape(message)}</p>")

    def _ai_finished(self) -> None:
        self._ai_output.append("<br>")
        self._ai_send_button.setEnabled(True)
        self._ai_stop_button.setEnabled(False)
        self._ai_status.setText("就绪")

    def _stop_ai_question(self) -> None:
        if self._ai_chat_worker is not None:
            self._ai_chat_worker.requestInterruption()

    def _build_ai_context(self) -> str:
        if self._ai_context_override is not None:
            return self._ai_context_override
        return self._build_auto_ai_context()

    def _build_auto_ai_context(self) -> str:
        title = self._current_chapter
        if self._current_section:
            title = f"{title} / {self._current_section}"
        if self._content_stack.currentWidget() is self._window_demo:
            page_text = self._window_summary.text()
        else:
            page_text = self._content_browser.toPlainText()
        data_files = []
        if self._current_section == "完整 I/Q 数据":
            data_files.append("integer_bin_reference_adc_iq.csv: 64 x 128 complex, 8192 rows")
        if self._current_section == "演示数据来源":
            data_files.append("noninteger_bin_demo_adc_iq.csv: 64 x 128 complex, 8192 rows")
            data_files.append("background_weak_target_adc_iq.csv: 2 x 64 x 128 complex, 16384 rows")
        range_window = self._range_window_combo.currentText() if self._range_window_combo is not None else "Hann"
        doppler_window = self._doppler_window_combo.currentText() if self._doppler_window_combo is not None else "Hann"
        return "\n".join(
            [
                "以下内容来自 Radar Flow Analyzer 当前界面。",
                f"当前页面: {title}",
                f"窗函数设置: Range FFT={range_window}, Doppler FFT={doppler_window}",
                "数据文件: " + ("; ".join(data_files) if data_files else "当前页未直接展开完整 CSV"),
                "",
                "[当前页面文本]",
                page_text[:12000],
            ]
        )

    def _show_ai_context(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("查看 / 编辑本次 AI 上下文")
        dialog.resize(720, 540)
        layout = QVBoxLayout(dialog)

        note = QLabel("保存后的上下文只对当前运行会话有效；恢复自动上下文后，会重新跟随当前页面和参数变化。")
        note.setWordWrap(True)
        layout.addWidget(note)

        text = QTextEdit()
        text.setPlainText(self._build_ai_context())
        layout.addWidget(text, 1)

        action_row = QHBoxLayout()
        restore_button = QPushButton("恢复自动上下文")
        save_button = QPushButton("保存本次上下文")
        close_button = QPushButton("关闭")
        action_row.addWidget(restore_button)
        action_row.addStretch()
        action_row.addWidget(save_button)
        action_row.addWidget(close_button)
        layout.addLayout(action_row)

        def restore_context() -> None:
            self._ai_context_override = None
            text.setPlainText(self._build_auto_ai_context())
            self._ai_context_button.setText("查看上下文")
            self._ai_cloud_confirm.setChecked(False)
            self._ai_status.setText("已恢复自动上下文。")

        def save_context() -> None:
            self._ai_context_override = text.toPlainText()
            self._ai_context_button.setText("查看上下文（已修改）")
            self._ai_cloud_confirm.setChecked(False)
            self._ai_status.setText("已保存本次上下文。")
            dialog.accept()

        restore_button.clicked.connect(restore_context)
        save_button.clicked.connect(save_context)
        close_button.clicked.connect(dialog.reject)
        dialog.exec()

    def _csv_data_page(self, title: str, file_names: list[str], summary: str) -> str:
        sections = [
            f"<h2>{html.escape(title)}</h2>",
            f"<p>{html.escape(summary)}</p>",
            "<p><b>字段说明：</b><code>scenario</code> 是场景名，<code>chirp_m</code> 是慢时间 Chirp 编号，<code>sample_n</code> 是快时间 ADC sample 编号，<code>i</code> 和 <code>q</code> 组成复数 <code>i + jq</code>。</p>",
            "<p>下面直接展示完整 CSV 内容。页面可滚动查看；这些文件位于工具自己的 <code>knowledge/data</code> 目录，不依赖 docs 运行。</p>",
        ]
        for file_name in file_names:
            path = DATA_PATH / file_name
            if not path.exists():
                sections.append(f"<h3>{html.escape(file_name)}</h3><p>数据文件不存在。</p>")
                continue
            text = path.read_text(encoding="utf-8")
            line_count = max(0, text.count("\n") - 1)
            sections.append(f"<h3>{html.escape(file_name)}</h3>")
            sections.append(f"<p>数据行数：{line_count}</p>")
            sections.append(
                "<pre style='font-family: Consolas, monospace; font-size: 10px; "
                "white-space: pre; background: #fbf7ee; border: 1px solid #ded8c8; "
                "padding: 10px;'>"
                f"{html.escape(text)}"
                "</pre>"
            )
        return "".join(sections)

    def _build_window_demo(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("可调参数观察:Range FFT 与 Doppler FFT 窗函数")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #24352f;")
        layout.addWidget(title)

        intro = QLabel(
            "这里只调窗函数。每张图都会同时显示不加窗 Rect 的灰色虚线和当前选择窗函数的蓝色实线,用同一组教学参考信号观察主瓣、旁瓣和能量扩散怎样变化。本页不是从完整 CSV 重算整条处理链。"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 13px; color: #6d675d;")
        layout.addWidget(intro)

        controls = QWidget()
        controls_layout = QGridLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setHorizontalSpacing(12)
        controls_layout.setVerticalSpacing(8)

        self._range_window_combo = QComboBox()
        self._doppler_window_combo = QComboBox()
        for combo in [self._range_window_combo, self._doppler_window_combo]:
            combo.addItems(["Rect", "Hann", "Hamming"])
            combo.setCurrentText("Hann")
            combo.currentTextChanged.connect(self._update_window_demo)

        controls_layout.addWidget(QLabel("Range FFT 窗函数"), 0, 0)
        controls_layout.addWidget(self._range_window_combo, 0, 1)
        controls_layout.addWidget(QLabel("作用:adc_iq[m, :] × window(128)"), 0, 2)
        controls_layout.addWidget(QLabel("Doppler FFT 窗函数"), 1, 0)
        controls_layout.addWidget(self._doppler_window_combo, 1, 1)
        controls_layout.addWidget(QLabel("作用:range_fft[:, k] × window(64)"), 1, 2)
        layout.addWidget(controls)

        self._window_summary.setWordWrap(True)
        self._window_summary.setStyleSheet(
            "background: #fffdf7; border: 1px solid #ded8c8; border-radius: 10px; padding: 10px; color: #3d4a43;"
        )
        layout.addWidget(self._window_summary)

        input_note = QLabel(
            "输入数据：本页使用教学复数信号，不读取完整 CSV，也不读取真实雷达文件。Range 演示输入为 128 个快时间复数样本，目标位于非整数 Range bin 8.35；Doppler 演示输入为 64 个慢时间复数样本，目标位于非整数 Doppler bin +5.4。"
        )
        input_note.setWordWrap(True)
        input_note.setStyleSheet(
            "background: #fbf7ee; border: 1px solid #ded8c8; border-radius: 10px; padding: 10px; color: #3d4a43;"
        )
        layout.addWidget(input_note)

        feature_note = QLabel(
            "功能说明：本演示把同一段有限长度复数信号分别乘以 Rect、Hann 或 Hamming 窗，再执行 DFT。非整数 bin 的信号在截取的 128 点或 64 点窗口内，首尾不能自然接成一个完整周期；FFT 会把这段有限数据当作周期重复的数据来看，于是首尾断点会变成额外的频率成分，这就是不加窗时的频谱泄漏。矩形窗 Rect 等于直接截断，所以灰色虚线通常主峰较窄，但远离主峰的位置仍有较高旁瓣；Hann/Hamming 会把数据段两端逐渐压低，减轻首尾断点，因此蓝色实线在远离主峰的旁瓣通常更低。这里说的“避免泄漏”更准确是“降低旁瓣泄漏”，不是让非整数 bin 的能量只落回一个 bin。代价是主瓣会变宽，相近目标可能更难分开。"
        )
        feature_note.setWordWrap(True)
        feature_note.setStyleSheet(
            "background: #fff4df; border: 1px solid #e7cfa6; border-radius: 10px; padding: 10px; color: #76513a;"
        )
        layout.addWidget(feature_note)

        self._range_plot = LinePlotWidget("Range Profile：快时间窗函数影响", "Range bin")
        self._doppler_plot = LinePlotWidget("Doppler Profile：慢时间窗函数影响", "Doppler bin")
        range_axis_note = QLabel(
            "Range 图坐标：X 轴是 Range bin，表示 Range FFT 后的距离单元索引，当前显示 0–32 bin；Y 轴是归一化幅度 dB，最大峰为 0 dB，其它 bin 表示相对最大峰的幅度差。看图时重点比较主峰 k≈8 附近之外的远处 bin：灰色虚线如果明显高于蓝色实线，就表示不加窗的旁瓣泄漏更强。"
        )
        range_axis_note.setWordWrap(True)
        range_axis_note.setStyleSheet("font-size: 12px; color: #6d675d;")
        layout.addWidget(range_axis_note)
        layout.addWidget(self._range_plot)
        doppler_axis_note = QLabel(
            "Doppler 图坐标：X 轴是 fftshift 后的有符号 Doppler bin，范围为 -32 到 +31，0 表示零 Doppler 附近；Y 轴同样是归一化幅度 dB。看图时重点比较 d≈+5 附近之外的远处 Doppler bin：灰色虚线越高，说明不加窗时速度能量泄漏到更多 Doppler bin。"
        )
        doppler_axis_note.setWordWrap(True)
        doppler_axis_note.setStyleSheet("font-size: 12px; color: #6d675d;")
        layout.addWidget(doppler_axis_note)
        layout.addWidget(self._doppler_plot)

        note = QLabel(
            "观察边界：dB 显示用于看清弱旁瓣；两条曲线都按各自最大峰归一化为 0 dB，因此比较的是峰形和旁瓣，不比较绝对幅度损失。窗函数改变有限长度 FFT 的峰形、旁瓣和主瓣宽度，不改变输入目标位置，也不会把非整数 bin 变成整数 bin。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 12px; color: #7a7368;")
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _update_window_demo(self) -> None:
        if not all([
            self._range_window_combo,
            self._doppler_window_combo,
            self._range_plot,
            self._doppler_plot,
        ]):
            return

        range_window_name = self._range_window_combo.currentText()
        doppler_window_name = self._doppler_window_combo.currentText()
        range_x, range_y, range_peak = self._compute_range_profile(range_window_name)
        _, range_rect_y, _ = self._compute_range_profile("Rect")
        doppler_x, doppler_y, doppler_peak = self._compute_doppler_profile(doppler_window_name)
        _, doppler_rect_y, _ = self._compute_doppler_profile("Rect")

        self._range_plot.set_data(
            range_x,
            range_y,
            f"peak k={range_peak}",
            comparison_y_values=range_rect_y,
            selected_label=f"当前 {range_window_name}",
        )
        self._doppler_plot.set_data(
            doppler_x,
            doppler_y,
            f"peak d={doppler_peak}",
            comparison_y_values=doppler_rect_y,
            selected_label=f"当前 {doppler_window_name}",
        )
        self._window_summary.setText(
            f"当前设置：Range FFT 使用 {range_window_name} 窗，Doppler FFT 使用 {doppler_window_name} 窗。"
            "灰色虚线是不加窗 Rect，蓝色实线是当前选择。请看主峰两侧更远的位置：灰色虚线高，表示直接截断带来的旁瓣泄漏更强；蓝色实线低，表示当前窗函数压低两端后降低了远处泄漏。教学信号故意放在非整数 bin 附近，用来让泄漏和加窗效果更容易看见；整数 bin 基准仍用于处理链闭环验证。"
        )

    def _window_values(self, name: str, length: int) -> list[float]:
        if name == "Hann":
            return [0.5 - 0.5 * math.cos(2 * math.pi * idx / (length - 1)) for idx in range(length)]
        if name == "Hamming":
            return [0.54 - 0.46 * math.cos(2 * math.pi * idx / (length - 1)) for idx in range(length)]
        return [1.0 for _ in range(length)]

    def _dft_db(self, samples: list[complex], window_name: str) -> list[float]:
        length = len(samples)
        window = self._window_values(window_name, length)
        values: list[float] = []
        for bin_index in range(length):
            total = 0j
            for sample_index, sample in enumerate(samples):
                angle = -2 * math.pi * bin_index * sample_index / length
                total += sample * window[sample_index] * cmath.exp(1j * angle)
            values.append(abs(total))
        peak = max(values) or 1.0
        return [20 * math.log10(max(value / peak, 1e-4)) for value in values]

    def _compute_range_profile(self, window_name: str) -> tuple[list[float], list[float], int]:
        sample_count = 128
        range_position = 8.35
        samples = [cmath.exp(1j * 2 * math.pi * range_position * idx / sample_count) for idx in range(sample_count)]
        db_values = self._dft_db(samples, window_name)
        visible_bins = list(range(0, 33))
        visible_values = [db_values[idx] for idx in visible_bins]
        peak_index = max(visible_bins, key=lambda idx: db_values[idx])
        return [float(idx) for idx in visible_bins], visible_values, peak_index

    def _compute_doppler_profile(self, window_name: str) -> tuple[list[float], list[float], int]:
        chirp_count = 64
        doppler_position = 5.4
        samples = [cmath.exp(1j * 2 * math.pi * doppler_position * idx / chirp_count) for idx in range(chirp_count)]
        db_values = self._dft_db(samples, window_name)
        shifted = db_values[chirp_count // 2 :] + db_values[: chirp_count // 2]
        doppler_bins = list(range(-chirp_count // 2, chirp_count // 2))
        peak_index = max(range(len(shifted)), key=shifted.__getitem__)
        return [float(idx) for idx in doppler_bins], shifted, doppler_bins[peak_index]

    def _handle_ai_question(self) -> None:
        question = self._ai_input.text().strip()
        if not question:
            return

        answer = self._answer_ai(question)
        self._ai_output.append(f"<b>Q:</b> {question}")
        self._ai_output.append(f"<b>A:</b> {answer}")
        self._ai_input.clear()

    def _answer_ai(self, question: str) -> str:
        q = question.lower()
        if "range fft" in q or ("距离" in q and "fft" in q):
            return "Range FFT 把快时间中的拍频延迟转换成距离维度;它保留了复数结果,可继续用于 Doppler 分析。"
        if "doppler" in q or "速度" in q:
            return "Doppler FFT 看的是同一距离门在多个 Chirp 中的相位变化;它恢复的是径向速度分量。"
        if "candidate" in q or "候选" in q:
            return "候选处理是在 Range-Doppler 中找明显峰值,并保留距离、速度和能量;它不等于最终 Presence。"
        if "presence" in q or "有人" in q or "无人" in q:
            return "Presence 是跨帧证据累积后的状态结论,依赖连续确认、滞回和 Hold Time。"
        if "核心流程" in q:
            return "核心流程的主链路是 ADC/IQ → Range FFT → Doppler FFT → Range-Doppler → Candidate/Feature → Presence。"
        if "示例" in q:
            return "流程演示示例聚焦非整数 bin、弱目标与候选路线、真实模组数据入口和接口边界。"
        return "这里的关键是先明确当前数据层:原始信号、Range 结果、Doppler 结果、候选特征,以及最后的状态判定。"

    def closeEvent(self, event) -> None:
        if self._ai_chat_worker is not None and self._ai_chat_worker.isRunning():
            self._ai_chat_worker.requestInterruption()
            self._ai_chat_worker.wait(2000)
        if self._ai_model_loader is not None and self._ai_model_loader.isRunning():
            self._ai_model_loader.requestInterruption()
            self._ai_model_loader.wait(5500)
        super().closeEvent(event)

def main() -> int:
    app = QApplication([])
    window = RadarFlowAnalyzerWindow()
    window.show()
    return app.exec()

