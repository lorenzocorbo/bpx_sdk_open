# 更新日志

[English](CHANGELOG.md) | **中文**

本项目所有值得关注的变更都会记录在此文件中。

本文档格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
本项目遵循[语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

## [未发布]

## [1.0.7] - 2026-07-22

### 新增

- 增加 Linux 和 Windows 一键 wheel 构建脚本，使用 `uv` 准备可复用的
  Python 3.11 环境并运行 `cibuildwheel`。
- 增加 Windows 构建选项，可在构建期间临时绕过环境变量和系统代理设置。
- 增加可选的 `BPX_SDK_BUILD_HARDWARE_TESTS` CMake 选项，以及交互式真实
  机器人测试，用于验证 Bound 步态在前进、暂停、再次前进的过程中保持选中。
- 增加仓库属性，将文本文件统一规范为 LF，并将预编译库和 wheel 包明确
  标记为二进制文件。

### 变更

- 将 SDK 版本信息以及随附的 Windows 和 Linux 库更新至 1.0.7。
- 更新仓库中的 wheel，覆盖 CPython 3.8 至 3.14、Linux x86_64、Linux
  aarch64 和 Windows AMD64。
- 在中英文文档中说明 Linux 和 Windows wheel 构建流程。
- 明确主步态和子步态取值、有符号子步态的解释方式以及 Walk 起步行为。

### 修复

- 修复随附 SDK 动态库中调用 `setVelocity()` 会导致已设置步态失效的问题。
- 修复随附 SDK 动态库中 `setPronk()` 实际设置为 Bound、`setBound()` 实际
  设置为 Pronk 的接口行为颠倒问题。

### 移除

- 移除仓库中的 1.0.6 wheel。仓库随 1.0.7 提供 Linux 和 Windows wheel；
  macOS wheel 继续由已配置的 CI 构建流程生成，不再存放于仓库的 wheelhouse。

## [1.0.6] - 2026-07-08

### 新增

- 在 C++ API 中增加按需查询机器人构建版本的接口，以及连接后缓存的版本信息。
- 向 Python 暴露缓存的机器人版本信息，并在 C++ 和 Python 示例中输出该信息。
- 在 C++ 和 Python API 中增加结构化腿部里程计，包含机身速度、世界坐标系
  位置、姿态和角速度。
- 增加适用于 Linux、Windows 和 macOS 的 CPython 3.8 至 3.14 wheel。

### 变更

- 更新随附的 SDK 库和示例，以支持机器人版本查询。

### 移除

- 移除 `getCurrentVelocityBody()` 和 `getCurrentVelocityBodyArray()`，并以
  结构化腿部里程计替代旧的仅包含速度的腿部里程计接口。

## 1.0.5 - 2026-07-07

### 新增

- 增加适用于 Linux x86_64/aarch64、Windows AMD64 和 macOS arm64 的
  release wheel 构建，并支持 CPython 3.14。
- 在示例中增加速度、腿部里程计和最大速度输出。

### 变更

- 更新 SDK 1.0.5 随附的库和 wheel。

## [1.0.4] - 2026-07-07

### 新增

- 增加原生 macOS arm64 SDK 库和 Python 包支持。
- 明确打包后的 Python 绑定支持 Python 3.8 及更高版本。

### 变更

- 扩展 CMake 和 Python 打包的架构检测，以支持 macOS arm64。
- 将 macOS 最低部署版本设为 macOS 11.0。

## 1.0.3 - 2026-06-18

### 新增

- 增加 Python 3.8+ 绑定、类型信息，以及状态查询、运动级控制和关节级控制的
  Python 示例。
- 增加 Windows x86_64 DLL 和导入库打包支持。
- 为 C++ 和 Python 示例增加可配置的命令行连接选项。
- 增加独立的英文和简体中文文档。

### 变更

- 使 CMake 示例根据当前平台和架构选择随附的 SDK 库。

### 移除

- 移除不受支持的 `setForwardFlip()` 和 `setBackFlip()` 运动接口。

## 1.0.2 - 2026-05-18

### 新增

- 增加 Walk、Running、翻转、Bipedal、倒立 Bipedal、Pronk、Pace 和 Bound
  的显式步态选择指令。
- 增加子步态反馈读取接口。

## 1.0.1 - 2026-05-07

### 新增

- 增加强类型运动状态、步态和关节索引定义。
- 在原始数值接口之外增加强类型状态和步态读取接口。
- 增加用于机器人零位准备的 `setZeroPositionsFlag()`。

### 变更

- 说明 IMU 欧拉角和四元数的分量顺序。

## 1.0.0 - 2026-04-27

### 新增

- 首次提供用于机器人状态查询、运动级控制和关节级控制的 C++ SDK。
- 首次提供 Linux x86_64 和 aarch64 共享库、CMake 配置及 C++ 示例。

[未发布]: https://github.com/mirrormerobotics/bpx_sdk_open/compare/v1.0.7...HEAD
[1.0.7]: https://github.com/mirrormerobotics/bpx_sdk_open/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/mirrormerobotics/bpx_sdk_open/releases/tag/v1.0.6
[1.0.4]: https://github.com/mirrormerobotics/bpx_sdk_open/releases/tag/v1.0.4
