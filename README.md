# Radar Flow Analyzer

从 I/Q 到有人/无人判定的嵌入式雷达数据链路可视化学习工具。

当前版本：`v0.5`，如下图所示(demo.gif)：


![Radar Flow Analyzer 演示](./demo.gif)

## 功能概览

工具围绕一条可解释的数据路径组织内容：

```text
ADC / I/Q
  -> Range FFT
  -> Doppler FFT
  -> Range-Doppler
  -> Candidate / Feature
  -> Presence
```

当前提供：

- 应用主线：从电磁波、反射、I/Q、人体运动到 Presence
- 数据处理流程：完整 I/Q、Range FFT、Doppler FFT、Range-Doppler 和候选证据
- 可控数据演示：非整数 bin、频谱泄漏、强背景下的弱目标、逐帧 Presence
- 窗函数对比：Range FFT 和 Doppler FFT 的 Rect、Hann、Hamming 对比
- 完整教学数据：工具自己的 `knowledge/data` CSV 文件
- AI 助手：本地 Ollama、DeepSeek、通义千问
- 真实数据入口：从 ADC/IQ、Doppler FFT 后数据或 Energy 特征开始分析的 TBD 页面


## 安装和运行

如果使用发布目录中的程序，不需要安装 Python，直接运行：

```text
dist/RadarFlowAnalyzer_v0.5.exe

```

要求 Python 3.11 或更高版本。推荐在工作区根目录执行：

```powershell
py -3.11 -m pip install -e .
```

主要依赖：

- `PySide6`：桌面界面
- `PyYAML`：加载工具知识目录


直接运行：

```powershell
py -3.11 app.py
```

完成可编辑安装后，也可以运行：

```powershell
radar-flow-analyzer
```

## 问 AI

右侧 AI 面板支持：

- 本地 Ollama 模型发现与流式回答
- DeepSeek OpenAI 兼容接口
- 通义千问 OpenAI 兼容接口
- 当前页面、数据层和窗函数上下文
- 上下文查看、编辑和本次会话保存

云端 API Key 建议使用环境变量：

```powershell
$env:DASHSCOPE_API_KEY = "your-qwen-key"
$env:DEEPSEEK_API_KEY = "your-deepseek-key"
```
也可以在当前对话框临时输入，关闭对话框后不会保存。
云端发送前需要在界面中确认当前上下文会发送给对应服务。Key 不会写入项目文件。


## License

本项目使用 [MIT License](LICENSE)。

免责声明 [DISCLAIMER.md](DISCLAIMER.md)。

## 问题反馈

如遇到问题，请提交 Issue，或发送邮件至 [fanqiefox@foxmail.com](mailto:fanqiefox@foxmail.com)
