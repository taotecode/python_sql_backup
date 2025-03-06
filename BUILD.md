# MySQL备份工具构建指南

本文档提供了如何使用`build_executable.py`脚本构建MySQL备份工具可执行文件的详细说明。该构建系统支持为Windows、macOS和Linux平台生成独立可执行文件，同时支持多种CPU架构。

## 前提条件

在开始构建过程之前，确保您已安装以下软件：

1. **Python 3.10或更高版本**
2. **PyInstaller**：用于创建独立可执行文件
   ```bash
   pip install pyinstaller
   ```
3. **项目依赖项**：所有在`requirements.txt`中列出的依赖项
   ```bash
   pip install -r requirements.txt
   ```

## 构建选项

`build_executable.py`脚本提供了多种构建选项，允许您为特定平台和架构构建可执行文件。

### 基本用法

```bash
python build_executable.py [选项]
```

### 可用选项

| 选项 | 描述 |
|------|------|
| `--target-platform PLATFORM` | 目标平台 (windows, macos, linux) |
| `--target-arch ARCH` | 目标架构 (x86, x86_64, arm64) |
| `--all` | 为所有支持的平台和架构构建 |
| `--output-dir DIR` | 可执行文件输出目录（默认：dist） |
| `--verbose` | 启用详细输出 |
| `--clean` | 构建前清理构建目录 |
| `--help` | 显示帮助信息 |

## 构建示例

### 为当前平台和架构构建

```bash
python build_executable.py
```

### 为特定平台构建

```bash
python build_executable.py --target-platform windows
```

### 为特定平台和架构构建

```bash
python build_executable.py --target-platform linux --target-arch x86_64
```

### 为所有支持的平台和架构构建

```bash
python build_executable.py --all
```

### 构建并指定输出目录

```bash
python build_executable.py --output-dir /path/to/output
```

## 跨平台构建注意事项

### Windows构建

- 在Windows平台上构建Windows可执行文件效果最佳
- 如果需要在非Windows系统上构建Windows可执行文件，您可能需要安装Wine
- Windows可执行文件将具有`.exe`扩展名

### macOS构建

- 在macOS平台上构建macOS可执行文件效果最佳
- 为Intel (x86_64)和Apple Silicon (arm64)构建Universal Binary需要在macOS上进行
- macOS构建可以生成标准可执行文件或`.app`包

### Linux构建

- Linux构建通常可以在任何Linux发行版上运行，但最好在与目标系统类似的发行版上构建
- 为确保最大兼容性，可以在较旧的Linux发行版上构建

## 构建输出

构建脚本会在指定的输出目录（默认为`dist`）中创建以下结构：

```
dist/
├── windows-x86_64/
│   └── python-sql-backup.exe
├── macos-x86_64/
│   └── python-sql-backup
├── macos-arm64/
│   └── python-sql-backup
├── linux-x86_64/
│   └── python-sql-backup
└── config/
    ├── config.ini.example
    └── README.md
```

## 构建配置包

构建脚本也会创建一个配置包，其中包含示例配置文件和文档。这个配置包可以与可执行文件一起分发，让用户能够快速开始使用。

## 故障排除

### 常见问题

1. **缺少依赖项**
   
   确保您已安装所有必要的依赖项：
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. **图标文件问题**
   
   如果遇到图标相关错误，可以尝试删除或替换`resources`目录中的图标文件。

3. **跨平台构建失败**
   
   跨平台构建可能受到限制，最好在目标平台上进行本地构建。

4. **可执行文件大小过大**
   
   PyInstaller生成的可执行文件通常较大，因为它们包含了完整的Python解释器和所有依赖项。使用`--clean`选项可以删除临时文件，但不会显著减小最终可执行文件的大小。

5. **构建速度慢**
   
   构建过程可能需要几分钟时间，特别是在构建多个平台和架构时。请耐心等待。

## 高级配置

### 修改PyInstaller规范文件

如果您需要对构建过程进行更精细的控制，可以直接编辑`python_sql_backup.spec`文件。这个文件包含了PyInstaller构建配置，可以用来添加额外的资源、更改图标、设置启动选项等。

### 自定义构建脚本

您也可以修改`build_executable.py`脚本来满足特定需求，如添加新的目标平台、更改构建参数或添加post-build处理步骤。
