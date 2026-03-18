# RPG Game Translator

RPG游戏翻译工具 - 支持提取、翻译和替换RPG游戏中的文本

## ✨ 功能特性

### 🎮 支持的引擎
- **RPG Maker MV/MZ** - 完整支持
- **RPG Maker VX Ace** - 基础支持
- **Wolf RPG Editor** - 基础支持
- **Unity** - 通用支持
- **Ren'Py** - 基础支持
- **通用格式** - JSON/CSV/TXT/XML/YAML/Excel

### 🔄 翻译引擎
- **Google翻译** - 免费，支持多语言
- **DeepL** - 高质量翻译（需要API密钥）
- **百度翻译** - 中文优化（需要API密钥）
- **本地AI模型** - 离线翻译，隐私保护

### 🛠️ 核心功能
- ✅ 可视化界面，操作简单
- ✅ 自动检测游戏引擎
- ✅ 批量提取游戏文本
- ✅ 实时翻译预览
- ✅ 人工编辑校对
- ✅ 自动备份原文件
- ✅ 翻译日志记录
- ✅ 多格式支持

## 🚀 快速开始

### 安装依赖

```bash
cd E:\clawqwe\翻译脚本\rpg_translator
pip install -r requirements.txt
```

### 启动GUI界面

```bash
python gui_launcher.py
```

或者

```bash
python gui_main.py
```

### 使用命令行版本

```bash
# 查看支持的格式和引擎
python cli.py info

# 翻译单个文件
python cli.py translate input.json --engine google --source en --target zh-CN

# 批量翻译目录
python cli.py batch ./game_data --extensions .json .csv

# 分析二进制文件
python analyze.py unknown_file.dat
```

## 📖 使用指南

### GUI界面使用步骤

#### 1. 加载游戏
1. 点击 **"Load Game Directory"** 按钮
2. 选择游戏的主目录（包含游戏可执行文件的文件夹）
3. 工具会自动检测游戏引擎

#### 2. 提取文本
1. 点击 **"Extract Game Text"** 按钮
2. 等待提取完成，左侧会显示提取到的文件列表
3. 双击文件可以在右侧编辑区域打开

#### 3. 翻译文本
1. 在右侧表格中查看原文和译文
2. 选择翻译引擎（Google、DeepL等）
3. 设置源语言和目标语言
4. 点击 **"Translate All"** 翻译全部，或选择行后点击 **"Translate Selected"** 翻译选中项
5. 可以手动编辑翻译结果

#### 4. 保存翻译
1. 点击 **"Save"** 保存当前文件（会自动创建备份）
2. 或点击 **"Save As..."** 保存到新位置
3. 翻译后的文件可以直接替换原游戏文件

### 配置API密钥

对于DeepL和百度翻译，需要配置API密钥：

1. 复制 `.env.example` 为 `.env`
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的API密钥：
```env
DEEPL_API_KEY=your_deepl_api_key_here
BAIDU_APP_ID=your_baidu_app_id_here
BAIDU_SECRET_KEY=your_baidu_secret_key_here
```

3. 或者在 `config.yaml` 中配置：
```yaml
apis:
  deepl:
    api_key: "your_api_key"
    free_mode: true
  baidu:
    app_id: "your_app_id"
    secret_key: "your_secret_key"
```

## 📁 项目结构

```
rpg_translator/
├── parsers/                      # 文件解析器
│   ├── json_parser.py           # JSON/JSON5
│   ├── csv_parser.py            # CSV/TSV
│   ├── xml_parser.py            # XML
│   ├── yaml_parser.py           # YAML
│   ├── excel_parser.py          # Excel
│   └── binary_parser.py         # 自定义二进制
│
├── translators/                  # 翻译引擎
│   ├── google_translator.py     # Google翻译
│   ├── deepl_translator.py      # DeepL
│   ├── baidu_translator.py      # 百度
│   └── local_translator.py      # 本地AI
│
├── core/                        # 核心模块
│   └── translator.py            # 主翻译器
│
├── game_extractors.py           # 游戏文本提取
├── gui_main.py                  # GUI主程序
├── gui_launcher.py              # GUI启动器
├── cli.py                       # 命令行工具
├── analyze.py                   # 二进制分析工具
├── config.yaml                  # 配置文件
├── requirements.txt             # 依赖列表
└── test_data/                   # 测试数据
    ├── dialogue.json
    └── items.csv
```

## 🔧 配置说明

编辑 `config.yaml` 来自定义工具行为：

### 翻译设置
```yaml
translation:
  engine: "google"              # 默认翻译引擎
  source_lang: "auto"           # 源语言
  target_lang: "zh-CN"          # 目标语言
  delay_between_requests: 0.5   # API请求延迟（秒）
  max_retries: 3                # 失败重试次数
```

### 文件处理
```yaml
processing:
  min_text_length: 2            # 最小翻译文本长度
  max_text_length: 5000         # 最大翻译文本长度
  skip_patterns:               # 跳过模式（正则）
    - "^[0-9]+$"               # 纯数字
    - "^[a-zA-Z0-9_]+$"        # 变量名
  preserve_patterns:           # 保留模式（不翻译）
    - "\\{[^}]+\\}"           # {变量}
    - "<[^>]+>"                # <标签>
```

### 输出设置
```yaml
output:
  directory: "./output"         # 输出目录
  naming: "{name}_{lang}"       # 文件命名规则
  backup: true                  # 备份原文件
  log_file: "translation_log.json"  # 日志文件
```

## 🎮 实际示例

### 示例1：翻译RPG Maker MV游戏

假设游戏目录结构：
```
MyRPGGame/
├── www/
│   ├── data/
│   │   ├── Actors.json
│   │   ├── Items.json
│   │   └── Map001.json
│   └── index.html
└── Game.exe
```

操作步骤：
1. 在GUI中点击 **Load Game Directory**
2. 选择 `MyRPGGame` 文件夹
3. 点击 **Extract Game Text**
4. 双击 `Actors.json`
5. 选择引擎（Google），设置 en → zh-CN
6. 点击 **Translate All**
7. 点击 **Save** 保存翻译
8. 将翻译后的文件复制回游戏目录

### 示例2：命令行批量翻译

```bash
# 翻译整个data目录
python cli.py batch ./MyRPGGame/www/data \
  --engine google \
  --source en \
  --target zh-CN \
  --extensions .json \
  --output-dir ./translated
```

## 🔍 故障排除

### 常见问题

**1. 无法启动GUI**
```
PyQt5 is not installed!
```
解决：
```bash
pip install PyQt5
```

**2. 提取文本时出错**
- 确保选择的是游戏主目录
- 检查游戏是否被加密或打包
- 查看日志文件获取详细信息

**3. 翻译失败**
- 检查网络连接（在线API）
- 验证API密钥是否正确
- 尝试降低请求频率（增加delay）
- 切换到本地翻译引擎

**4. 编码错误**
- 工具会自动检测编码，如果失败手动指定：
```yaml
formats:
  json:
    encoding: "utf-8"
```

**5. 特殊格式不兼容**
- 使用 `analyze.py` 分析未知格式
- 在 `config.yaml` 中添加自定义解析规则
- 对于二进制文件，使用 `binary_parser.py` 自定义格式

## 📊 性能优化

### 大型游戏优化
```yaml
translation:
  batch_size: 100        # 增加批次大小
  delay_between_requests: 0.1  # 降低延迟（如果API允许）
  
processing:
  max_text_length: 10000  # 增加最大文本长度
```

### 本地模型加速
```yaml
local_model:
  enabled: true
  device: "cuda"         # 使用GPU加速（如果有）
  cache_dir: "./models"  # 模型缓存目录
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 开发环境搭建
```bash
git clone <repository>
cd rpg_translator
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发依赖
```

### 添加新功能
1. Fork项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启Pull Request

## 📄 许可证

MIT License - 详见 LICENSE 文件

## 🙏 致谢

- [Deep Translator](https://github.com/nidhaloff/deep-translator) - 翻译API库
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI框架
- [RPG Maker](https://www.rpgmakerweb.com/) - 游戏引擎

---

**提示**: 首次使用前建议先用 `test_data` 中的示例文件测试翻译流程！

**问题反馈**: 遇到问题请在GitHub提交Issue，包含错误日志和复现步骤。
