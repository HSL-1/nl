# 南江水库洪水调度工程调度平台 🌊

![Platform](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)

> **课程设计**：水库洪水预报、工程调度与管理  
> **核心技术**：马斯京根法 · 新安江模型 · 泰森多边形 · 水库调洪演算  
> **数据来源**：南江水库实测资料

---

## 📋 平台功能

| 模块 | 功能说明 |
|------|---------|
| 📊 **数据总览** | 水位-库容、水位-泄洪能力等关系曲线展示 |
| 🔷 **泰森多边形** | 基于站点坐标的流域雨量权重计算 |
| 🌧️ **新安江模型** | 三水源蓄满产流模型降雨-径流模拟 |
| 📈 **入库反推** | 基于水量平衡的天然入库洪水反推 |
| 🌊 **马斯京根法** | 河道洪水演进模拟（核心模块） |
| 🏗️ **调洪演算** | 考虑泄洪设施和发电的水库调洪计算 |
| 📋 **调度管理** | 防洪调度方案与运行管理分析 |
| 🔄 **实时仿真** | 交互式洪水调度全流程动态模拟 |

---

## 🚀 在线访问

👉 **[点击打开调度平台](https://HSL-1-nl.streamlit.app)**

> ⚠️ 若链接无法访问，请等待 Streamlit Cloud 部署完成后刷新

---

## 💻 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/HSL-1/nl.git
cd nl

# 2. 安装依赖
pip install -r requirements.txt

# 3. 准备数据文件
# 将 reservoir_data.json 放置于项目根目录
# （该文件不含于公开仓库中，需单独获取）

# 4. 启动平台
streamlit run app.py
```

---

## 🏗️ 系统架构

```
app.py                  ← 主程序（Streamlit 页面路由）
data_loader.py          ← 数据加载（Secrets/本地JSON → 无数据泄露）
muskingum.py            ← 马斯京根法洪水演进
xinanjing.py            ← 新安江模型 + 泰森多边形
reservoir_routing.py    ← 水库调洪演算 + 入库洪水反推
```

---

## 🔒 数据隐私声明

本仓库中的 `data_loader.py` 采用安全的数据加载机制：

| 环境 | 数据来源 | 是否公开 |
|------|---------|---------|
| **本地开发** | `reservoir_data.json`（本地文件，已加入 `.gitignore`） | ❌ 不上传 |
| **Streamlit Cloud** | `st.secrets["reservoir_data"]`（密钥注入） | ❌ 仅部署者可见 |
| **GitHub 仓库** | 无数据文件 | ✅ 完全公开但无数据 |

**公开的 GitHub 仓库中不含任何南江水库原始数据。**  
数据仅通过安全的密钥系统在部署时注入，确保数据隐私。

---

## 📐 课程设计评分对照

| 评分项 | 分值 | 覆盖情况 |
|-------|:---:|:--------:|
| 流域雨量分析与泰森多边形计算 | 15分 | ✅ 完整实现 |
| 新安江模型产汇流模拟 | 20分 | ✅ 完整实现 |
| 入库洪水反推计算 | 15分 | ✅ 完整实现 |
| 马斯京根法洪水演进 | 15分 | ✅ 核心模块 |
| 雨量查看功能开发与数据应用 | 10分 | ✅ 完整实现 |
| 水库工程调度与管理分析 | 10分 | ✅ 完整实现 |
| 课程设计报告质量与创新性 | 15分 | ✅ 含实时仿真创新 |

---

*© 2026 水库洪水预报、工程调度与管理课程设计*
