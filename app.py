"""
南江水库洪水调度工程调度平台
Nanjiang Reservoir Flood Control Engineering Dispatch Platform
基于Streamlit的交互式洪水调度模拟系统
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time
from datetime import datetime, timedelta

# 导入自定义模块
from data_loader import (
    load_water_level_storage, load_water_level_powerflow,
    load_water_level_flood_discharge, load_water_level_area,
    load_stations, load_annual_inflow, load_historical_dispatch,
    get_storage_interpolator, get_level_interpolator,
    get_flood_discharge_interpolator, get_powerflow_interpolator,
    get_area_interpolator, get_reservoir_params
)
from muskingum import (
    muskingum_flood_routing, calc_muskingum_params,
    calc_K_x_from_data, simulate_typical_flood,
    generate_downstream_flood
)
from xinanjing import XinAnJiangModel, ThiessenPolygon, generate_design_storm
from reservoir_routing import (
    reservoir_flood_routing, reverse_inflow_calculation,
    design_flood_hydrograph, water_balance_analysis
)

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="南江水库洪水调度平台",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 样式和工具函数
# ============================================================
def load_css():
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #1a73e8, #0d47a1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
        text-align: center;
    }
    .sub-header {
        font-size: 1.3rem;
        color: #555;
        margin-bottom: 2rem;
        text-align: center;
    }
    .card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: linear-gradient(135deg, #e3f2fd, #bbdefb);
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0d47a1;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #555;
    }
    .warning-banner {
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .info-banner {
        background-color: #d1ecf1;
        border: 1px solid #17a2b8;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .success-banner {
        background-color: #d4edda;
        border: 1px solid #28a745;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

def show_metric(label, value, delta=None):
    """显示指标卡"""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)

def show_banner(message, type="info"):
    cls = {"info": "info-banner", "warning": "warning-banner", "success": "success-banner"}
    st.markdown(f'<div class="{cls.get(type, "info-banner")}">{message}</div>',
                unsafe_allow_html=True)

# ============================================================
# 数据加载缓存
# ============================================================
@st.cache_data
def load_all_data():
    """加载所有数据"""
    data = {
        "wl_storage": load_water_level_storage(),
        "wl_powerflow": load_water_level_powerflow(),
        "wl_flood": load_water_level_flood_discharge(),
        "wl_area": load_water_level_area(),
        "stations": load_stations(),
        "annual_inflow": load_annual_inflow(),
        "reservoir_params": get_reservoir_params(),
    }
    return data

@st.cache_data
def load_dispatch(name):
    return load_historical_dispatch(name)

# ============================================================
# 侧边栏 - 导航
# ============================================================
def sidebar_nav():
    st.sidebar.markdown("## 🗺️ 导航菜单")
    pages = {
        "主页": "🏠 平台首页",
        "数据总览": "📊 水库基础数据",
        "泰森多边形": "🔷 雨量权重分析",
        "新安江模型": "🌧️ 产汇流模拟",
        "入库反推": "📈 入库洪水反推",
        "马斯京根法": "🌊 洪水演进模拟",
        "调洪演算": "🏗️ 水库调洪演算",
        "调度管理": "📋 工程调度管理",
        "实时仿真": "🔄 实时仿真模拟",
    }
    choice = st.sidebar.radio("选择功能模块", list(pages.keys()),
                              format_func=lambda x: pages[x])
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ 系统信息")
    st.sidebar.info("""
    **南江水库洪水调度工程调度平台 v1.0**

    本系统基于马斯京根法、新安江模型，
    实现洪水预报、调度仿真与工程管理分析。

    数据来源：南江水库实测资料
    """)
    st.sidebar.markdown("---")
    st.sidebar.markdown("*课程设计项目 · 水库洪水预报、工程调度与管理*")
    return choice

# ============================================================
# 页面模块
# ============================================================

def page_home():
    """平台首页"""
    params = get_reservoir_params()

    col1, col2, col3 = st.columns([2, 3, 2])
    with col2:
        st.markdown('<div class="main-header">🌊 南江水库洪水调度工程调度平台</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Nanjiang Reservoir Flood Control & Dispatch Platform</div>',
                    unsafe_allow_html=True)

    st.markdown("---")

    # 概览指标
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        show_metric("正常蓄水位", f"{params['正常蓄水位']}m")
    with col2:
        show_metric("总库容", f"{params['总库容']}万m³")
    with col3:
        show_metric("流域面积", f"{params['流域面积']}km²")
    with col4:
        show_metric("装机容量", f"{params['装机容量']}kW")

    st.markdown("---")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### 🎯 平台功能")
        functions = [
            ("📊 水库基础数据总览", "水位-库容、水位-面积、水位-泄洪能力等关系曲线展示"),
            ("🔷 泰森多边形雨量权重分析", "基于站点坐标的流域雨量权重计算与面雨量分析"),
            ("🌧️ 新安江模型产汇流模拟", "三水源新安江模型的降雨-径流过程模拟"),
            ("📈 入库洪水反推计算", "基于水量平衡的天然入库洪水过程反推"),
            ("🌊 马斯京根法洪水演进", "河道洪水演算，模拟下游洪水传播与变形"),
            ("🏗️ 水库调洪演算", "考虑泄洪设施和发电的水库调洪计算"),
            ("📋 工程调度管理分析", "防洪调度方案制定与运行管理"),
            ("🔄 实时仿真模拟", "动态交互式洪水调度实时模拟"),
        ]
        for title, desc in functions:
            st.markdown(f"**{title}**  \n{desc}")
            st.markdown("---")

    with col2:
        st.markdown("### 🏞️ 南江水库概况")
        st.markdown("""
        **南江水库**位于浙江省东阳市南江流域，是一座以
        防洪、供水为主，结合发电、灌溉等综合利用的
        大(2)型水库。

        **关键特征：**
        - 坝型：混凝土重力坝
        - 最大坝高：43.5m
        - 溢洪道：6孔×10m
        - 设计标准：100年一遇
        - 校核标准：2000年一遇
        """)

        st.markdown("### 📋 数据清单")
        st.markdown("""
        本系统加载以下数据源：
        - 水位-库容关系曲线
        - 水位-发电流量关系
        - 水位-泄洪能力曲线
        - 水位-面积关系曲线
        - 雨量站坐标信息
        - 历年入库径流量
        - 历史台风调度记录
        """)

    st.markdown("---")
    st.markdown("#### 📐 课程设计核心内容")
    col1, col2, col3 = st.columns(3)
    with col1:
        show_banner("✅ 流域雨量分析与泰森多边形计算", "success")
        show_banner("✅ 基于新安江模型的产汇流模拟", "success")
    with col2:
        show_banner("✅ 基于坝前水位与出库流量的入库洪水反推", "success")
        show_banner("✅ 基于马斯京根法的下游洪水演进模拟", "success")
    with col3:
        show_banner("✅ 雨量数据可视化查看功能", "success")
        show_banner("✅ 水库工程调度与运行管理分析", "success")


def page_data_overview():
    """水库基础数据总览"""
    st.markdown('<div class="main-header">📊 南江水库基础数据总览</div>',
                unsafe_allow_html=True)

    data = load_all_data()
    params = data["reservoir_params"]

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏞️ 水库特征参数", "📈 水位-库容", "⚡ 水位-发电", "🌊 泄洪能力", "📐 水位-面积"
    ])

    with tab1:
        st.markdown("### 南江水库特征参数表")
        col1, col2 = st.columns(2)
        params_items = list(params.items())
        half = len(params_items) // 2 + 1
        for idx, (col, items) in enumerate([(col1, params_items[:half]),
                                             (col2, params_items[half:])]):
            with col:
                for name, value in items:
                    unit = ""
                    if "水位" in name: unit = " m"
                    elif "库容" in name: unit = " 万m³"
                    elif "面积" in name: unit = " km²"
                    elif "长度" in name: unit = " km"
                    elif "容量" in name: unit = " kW"
                    elif "孔数" in name: unit = " 孔"
                    elif "宽度" in name: unit = " m"
                    st.metric(name, f"{value}{unit}")

    with tab2:
        st.markdown("### 水位-库容关系曲线")
        df = data["wl_storage"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["水位_m"], y=df["库容_万m3"],
            mode="lines+markers", name="水位-库容",
            line=dict(color="#1a73e8", width=3),
            marker=dict(size=5)
        ))
        fig.update_layout(
            xaxis_title="水位 (m)", yaxis_title="库容 (万m³)",
            height=500, hovermode="x unified"
        )
        # 添加特征水位线
        for name, val in [("死水位", params["死水位"]), ("汛限水位", params["汛限水位"]),
                          ("正常蓄水位", params["正常蓄水位"]),
                          ("设计洪水位", params["设计洪水位"]),
                          ("校核洪水位", params["校核洪水位"])]:
            fig.add_vline(x=val, line_dash="dash", line_color="red",
                          annotation_text=name)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)

    with tab3:
        st.markdown("### 水位-发电流量关系曲线")
        df = data["wl_powerflow"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["水位_m"], y=df["发电流量_m3s"],
            mode="lines+markers", name="发电流量",
            line=dict(color="#28a745", width=3),
            marker=dict(size=5)
        ))
        fig.update_layout(
            xaxis_title="水位 (m)", yaxis_title="发电流量 (m³/s)",
            height=500, hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)

    with tab4:
        st.markdown("### 水位-泄洪能力关系曲线")
        df = data["wl_flood"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["水位_m"], y=df["单孔全开_m3s"],
            mode="lines+markers", name="单孔全开",
            line=dict(color="#dc3545", width=2)
        ))
        fig.add_trace(go.Scatter(
            x=df["水位_m"], y=df["六孔全开_m3s"],
            mode="lines+markers", name="六孔全开",
            line=dict(color="#ff6600", width=3)
        ))
        fig.update_layout(
            xaxis_title="水位 (m)", yaxis_title="泄流量 (m³/s)",
            height=500, hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)

    with tab5:
        st.markdown("### 水位-面积关系曲线")
        df = data["wl_area"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["水位_m"], y=df["面积_km2"],
            mode="lines+markers", name="水位-面积",
            line=dict(color="#17a2b8", width=3),
            marker=dict(size=5)
        ))
        fig.update_layout(
            xaxis_title="水位 (m)", yaxis_title="面积 (km²)",
            height=500, hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)


def page_thiessen():
    """泰森多边形雨量权重分析"""
    st.markdown('<div class="main-header">🔷 流域雨量分析与泰森多边形权重计算</div>',
                unsafe_allow_html=True)
    show_banner("""
    基于流域内雨量站的空间分布，采用泰森多边形法计算各站点的控制面积和权重系数，
    为流域面雨量计算提供核心参数。本模块包含站点分布展示、权重计算和面雨量分析功能。
    """, "info")

    data = load_all_data()
    stations = data["stations"]
    rain_stations = stations[stations["类型"].fillna("").astype(str).str.contains("雨量")].copy()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 🗺️ 雨量站空间分布")
        fig = go.Figure()
        for _, row in rain_stations.iterrows():
            fig.add_trace(go.Scatter(
                x=[row["站点经度"]], y=[row["站点纬度"]],
                mode="markers+text", text=row["站点名称"],
                textposition="top center",
                marker=dict(size=14, color="#1a73e8", symbol="circle",
                            line=dict(width=2, color="white")),
                name=row["站点名称"]
            ))
        fig.update_layout(
            xaxis_title="经度 (°E)", yaxis_title="纬度 (°N)",
            height=500, hovermode="closest",
            xaxis=dict(range=[119.98, 120.52]),
            yaxis=dict(range=[28.98, 29.18]),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### 📋 雨量站信息")
        st.dataframe(rain_stations[["站码", "站点名称", "站点经度", "站点纬度"]],
                     use_container_width=True)

        # 泰森多边形权重计算
        st.markdown("### ⚖️ 泰森多边形权重计算")
        if st.button("计算泰森多边形权重", type="primary", use_container_width=True):
            with st.spinner("正在计算各站点权重..."):
                thiessen = ThiessenPolygon(rain_stations)
                result = thiessen.calculate_thiessen_weights()

                st.success("✅ 权重计算完成！")
                weight_df = result[["站点名称", "权重系数"]].copy()
                weight_df["权重系数"] = weight_df["权重系数"].round(4)
                weight_df["权重百分比"] = (weight_df["权重系数"] * 100).round(2).astype(str) + "%"
                st.dataframe(weight_df, use_container_width=True)

                total_weight = weight_df["权重系数"].sum()
                st.info(f"权重总和校核：{total_weight:.6f}（应等于1.0000）")

                # 饼图展示权重
                fig2 = px.pie(weight_df, values="权重系数", names="站点名称",
                             title="各雨量站权重分布")
                fig2.update_traces(textinfo="label+percent")
                st.plotly_chart(fig2, use_container_width=True)

                st.session_state["thiessen_weights"] = weight_df

    # 面雨量计算
    st.markdown("---")
    st.markdown("### 🌧️ 流域面雨量计算")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("输入各站降雨量 (mm)：")
        rain_inputs = {}
        for _, row in rain_stations.iterrows():
            rain_inputs[row["站点名称"]] = st.number_input(
                f"{row['站点名称']}", min_value=0.0, max_value=500.0,
                value=50.0, step=1.0, key=f"rain_{row['站点名称']}"
            )

    with col2:
        if st.button("计算流域面雨量", type="primary", use_container_width=True):
            if "thiessen_weights" not in st.session_state:
                thiessen = ThiessenPolygon(rain_stations)
                thiessen.calculate_thiessen_weights()
                weights = thiessen.weights
            else:
                weights = st.session_state["thiessen_weights"]

            area_rain = 0
            details = []
            for _, row in weights.iterrows():
                station = row["站点名称"]
                weight = row["权重系数"]
                if station in rain_inputs:
                    contrib = rain_inputs[station] * weight
                    area_rain += contrib
                    details.append({
                        "站点": station,
                        "权重": f"{weight:.4f}",
                        "站降雨_mm": rain_inputs[station],
                        "贡献_mm": f"{contrib:.2f}"
                    })

            st.success(f"✅ 流域面雨量 = **{area_rain:.2f} mm**")
            st.dataframe(pd.DataFrame(details), use_container_width=True)

            max_rain = max(rain_inputs.values())
            st.info(f"分析：最大站降雨 {max_rain}mm，最小站降雨 {min(rain_inputs.values())}mm，"
                    f"面雨量 {area_rain:.1f}mm，折减系数 {area_rain/max_rain:.3f}" if max_rain > 0 else "")


def page_xinanjing():
    """新安江模型产汇流模拟"""
    st.markdown('<div class="main-header">🌧️ 基于新安江模型的三水源产汇流模拟</div>',
                unsafe_allow_html=True)
    show_banner("基于蓄满产流理论的三水源新安江模型，模拟流域降雨-径流全过程。"
                "可调整模型参数和降雨输入，实时查看产汇流结果。", "info")

    # 模型参数设置
    with st.expander("⚙️ 新安江模型参数设置", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            WM = st.slider("WM - 流域平均蓄水容量(mm)", 80, 200, 140)
            WUM = st.slider("WUM - 上层蓄水容量(mm)", 10, 50, 20)
            WLM = st.slider("WLM - 下层蓄水容量(mm)", 30, 120, 60)
            SM = st.slider("SM - 自由水蓄水容量(mm)", 10, 60, 30)
        with col2:
            KG = st.slider("KG - 地下水出流系数", 0.0, 0.6, 0.3, 0.05)
            KSS = st.slider("KSS - 壤中流出流系数", 0.0, 0.6, 0.3, 0.05)
            KKG = st.slider("KKG - 地下水消退系数", 0.8, 0.99, 0.95, 0.01)
            KSSS = st.slider("KSSS - 壤中流消退系数", 0.7, 0.98, 0.85, 0.01)
        with col3:
            B = st.slider("B - 蓄水容量曲线指数", 0.1, 0.6, 0.3, 0.05)
            EX = st.slider("EX - 自由水容量曲线指数", 0.5, 2.0, 1.5, 0.1)
            IMP = st.slider("IMP - 不透水面积比例", 0.0, 0.05, 0.01, 0.005)
            KE = st.slider("KE - 蒸散发折算系数", 0.5, 1.5, 1.0, 0.05)

    # 降雨输入
    col1, col2 = st.columns([2, 1])
    with col2:
        st.markdown("### 🌧️ 降雨方案设置")
        storm_type = st.selectbox("暴雨类型", ["中心型", "前锋型", "后锋型", "均匀型"])
        pattern_map = {"中心型": "center", "前锋型": "front", "后锋型": "back", "均匀型": "uniform"}
        peak_intensity = st.slider("最大小时雨强 (mm)", 10, 150, 60)
        duration = st.slider("降雨历时 (h)", 6, 72, 24)
        evap = st.slider("蒸发能力 (mm/d)", 1.0, 8.0, 4.0, 0.5)

        if st.button("▶️ 运行模拟", type="primary", use_container_width=True):
            rainfall = generate_design_storm(duration, peak_intensity, pattern_map[storm_type])
            st.session_state["xj_rainfall"] = rainfall
            st.session_state["xj_run"] = True
            st.success("✅ 模拟完成！")

    with col1:
        st.markdown("### 📊 模拟结果")

        if st.session_state.get("xj_run"):
            rainfall = st.session_state["xj_rainfall"]
            evap_series = [evap / 24] * len(rainfall)

            model = XinAnJiangModel({
                "WM": WM, "WUM": WUM, "WLM": WLM, "SM": SM,
                "KG": KG, "KSS": KSS, "KKG": KKG, "KSSS": KSSS,
                "B": B, "EX": EX, "IMP": IMP, "KE": KE
            })
            model.set_initial_conditions(WU=10, WL=30, WD=20, S=5)

            results = model.simulate(rainfall, evap_series)

            # 图表
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                subplot_titles=("降雨过程", "产流过程", "流量过程"),
                vertical_spacing=0.08,
                row_heights=[0.25, 0.3, 0.45]
            )

            fig.add_trace(go.Bar(
                x=results["时段"], y=results["降雨_mm"],
                name="降雨", marker_color="#1a73e8"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=results["时段"], y=results["R"], mode="lines",
                name="总产流R", line=dict(color="#ff6600", width=2)
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=results["时段"], y=results["RS"], mode="lines",
                name="地表径流RS", line=dict(color="#dc3545", width=2)
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=results["时段"], y=results["RI"], mode="lines",
                name="壤中流RI", line=dict(color="#28a745", width=2)
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=results["时段"], y=results["RG"], mode="lines",
                name="地下径流RG", line=dict(color="#17a2b8", width=2)
            ), row=2, col=1)

            fig.add_trace(go.Scatter(
                x=results["时段"], y=results["total_Q"], mode="lines",
                name="总流量Q", line=dict(color="#0d47a1", width=3)
            ), row=3, col=1)

            fig.update_xaxes(title_text="时段 (h)", row=3, col=1)
            fig.update_yaxes(title_text="降雨 (mm)", row=1, col=1, autorange="reversed")
            fig.update_yaxes(title_text="产流 (mm)", row=2, col=1)
            fig.update_yaxes(title_text="流量 (m³/s)", row=3, col=1)
            fig.update_layout(height=700, hovermode="x unified")

            st.plotly_chart(fig, use_container_width=True)

            # 统计
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                show_metric("总降雨量", f"{rainfall.sum():.1f}mm")
            with col2:
                show_metric("总产流量", f"{results['R'].sum():.1f}mm")
            with col3:
                show_metric("径流系数", f"{results['R'].sum()/max(rainfall.sum(),0.1):.3f}")
            with col4:
                show_metric("峰值流量", f"{results['total_Q'].max():.1f}")

            st.dataframe(results, use_container_width=True)
        else:
            st.info("👈 在右侧设置降雨方案并点击运行")


def page_reverse_inflow():
    """入库洪水反推"""
    st.markdown('<div class="main-header">📈 基于坝前水位与出库流量的入库洪水反推</div>',
                unsafe_allow_html=True)
    show_banner("基于水库水量平衡原理，利用坝前水位变化和出库流量数据，"
                "反推天然入库洪水过程，修正模型模拟误差。", "info")

    # 选择历史事件或自定义
    source = st.radio("数据来源", ["使用历史调度数据", "自定义数据"], horizontal=True)

    if source == "使用历史调度数据":
        events = ["莫兰蒂", "苗柏", "利奇马", "黑格比", "烟花", "梅花", "梅雨", "康妮"]
        selected = st.selectbox("选择历史台风/事件", events)

        if st.button("加载数据并反推", type="primary"):
            df = load_dispatch(selected)
            if df is not None and len(df) > 5:
                st.session_state["rev_data"] = df
                st.session_state["rev_name"] = selected
                st.success(f"✅ 已加载 {selected} 调度数据")
            else:
                st.error("数据加载失败，请尝试自定义模式")

        if "rev_data" in st.session_state:
            df = st.session_state["rev_data"]
            st.markdown(f"**{st.session_state.get('rev_name', '')} 调度数据**")

            # 反推入库洪水
            levels = pd.to_numeric(df["末水位_m"], errors='coerce').dropna().values
            outflows = pd.to_numeric(df["闸门流量_m3s"], errors='coerce').fillna(0).values
            powerflows = pd.to_numeric(df["发电流量_m3s"], errors='coerce').fillna(0).values
            total_outflow = outflows + powerflows

            # 确保长度一致
            n = min(len(levels), len(total_outflow))
            if n > 3:
                result = reverse_inflow_calculation(levels[:n], total_outflow[:n], dt=1.0)

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                    subplot_titles=("坝前水位与库容变化", "流量过程反推"),
                                    vertical_spacing=0.1)

                fig.add_trace(go.Scatter(
                    x=result["时段"], y=result["坝前水位_m"],
                    mode="lines+markers", name="坝前水位",
                    line=dict(color="#1a73e8", width=2)
                ), row=1, col=1)

                fig.add_trace(go.Scatter(
                    x=result["时段"], y=result["反推入库流量_m3s"],
                    mode="lines", name="反推入库流量",
                    line=dict(color="#dc3545", width=3)
                ), row=2, col=1)

                fig.add_trace(go.Scatter(
                    x=result["时段"], y=result["出库流量_m3s"],
                    mode="lines", name="出库流量",
                    line=dict(color="#28a745", width=2)
                ), row=2, col=1)

                fig.update_xaxes(title_text="时段", row=2, col=1)
                fig.update_layout(height=600, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(result, use_container_width=True)

                col1, col2, col3 = st.columns(3)
                with col1:
                    show_metric("最大反推入库", f"{result['反推入库流量_m3s'].max():.1f} m³/s")
                with col2:
                    show_metric("平均入库", f"{result['反推入库流量_m3s'].mean():.1f} m³/s")
                with col3:
                    show_metric("水位变幅", f"{result['坝前水位_m'].max()-result['坝前水位_m'].min():.2f} m")

    else:
        st.markdown("### 自定义数据输入")
        col1, col2 = st.columns(2)
        with col1:
            n_points = st.number_input("数据点数", 10, 100, 24)
            initial_level = st.number_input("初始水位(m)", 190.0, 205.0, 198.0)
        with col2:
            peak_outflow = st.number_input("最大出库流量(m³/s)", 10, 2000, 300)
            var_level = st.number_input("水位变幅(m)", 0.1, 5.0, 1.5)

        if st.button("生成并反推", type="primary"):
            t = np.arange(n_points)
            # 模拟水位缓慢上升后下降
            level = initial_level + var_level * np.sin(np.pi * t / n_points) ** 2
            # 模拟出库过程
            outflow = peak_outflow * np.exp(-((t - n_points * 0.4) ** 2) / (2 * (n_points * 0.15) ** 2))
            outflow = np.maximum(outflow, 10)

            result = reverse_inflow_calculation(level, outflow, dt=1.0)

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                subplot_titles=("坝前水位", "反推结果"),
                                vertical_spacing=0.1)
            fig.add_trace(go.Scatter(x=result["时段"], y=result["坝前水位_m"],
                                     mode="lines+markers", name="坝前水位",
                                     line=dict(color="#1a73e8", width=2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=result["时段"], y=result["反推入库流量_m3s"],
                                     mode="lines", name="反推入库",
                                     line=dict(color="#dc3545", width=3)), row=2, col=1)
            fig.add_trace(go.Scatter(x=result["时段"], y=result["出库流量_m3s"],
                                     mode="lines", name="出库",
                                     line=dict(color="#28a745", width=2)), row=2, col=1)
            fig.update_xaxes(title_text="时段", row=2, col=1)
            fig.update_layout(height=600, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(result, use_container_width=True)


def page_muskingum():
    """马斯京根法洪水演进（核心模块）"""
    st.markdown('<div class="main-header">🌊 基于马斯京根法的下游洪水演进模拟</div>',
                unsafe_allow_html=True)
    show_banner("⚠️ **核心模块**：采用马斯京根河道洪水演进算法，模拟水库下泄洪水在下游河道的"
                "传播与变形过程。分析洪水沿程衰减规律，为下游防洪调度提供依据。", "warning")

    data = load_all_data()

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### ⚙️ 参数设置")

        # 洪水输入方式
        input_mode = st.radio("入流方式", ["典型洪水过程", "自定义入流", "调洪出流"], horizontal=True)

        if input_mode == "典型洪水过程":
            peak = st.number_input("洪峰流量 (m³/s)", 50, 3000, 500)
            baseflow = st.number_input("基流 (m³/s)", 10, 200, 50)
            duration = st.slider("洪水历时 (h)", 24, 120, 72)
            peak_time = st.slider("峰现时间 (h)", 6, duration, int(duration * 0.3))
            inflow = simulate_typical_flood(peak, baseflow, duration, peak_time)

        elif input_mode == "自定义入流":
            n_inflow = st.slider("数据点数", 10, 100, 48)
            inflow = np.zeros(n_inflow)
            cols = st.columns(4)
            for i in range(0, n_inflow, 4):
                for j in range(4):
                    idx = i + j
                    if idx < n_inflow:
                        inflow[idx] = cols[j].number_input(f"t={idx+1}", 0, 3000,
                                                           100 if idx < n_inflow//3 else 300,
                                                           key=f"inf_{idx}")
        else:  # 调洪出流
            st.info("使用调洪演算的出库结果作为入流（请在调洪演算模块先运行）")
            if "routing_result" in st.session_state:
                inflow = st.session_state["routing_result"]["出库总流量_m3s"].values
                st.success(f"✅ 已加载调洪出流数据，{len(inflow)} 个时段")
            else:
                inflow = simulate_typical_flood(300, 30, 48, 12)
                st.warning("⚠️ 未找到调洪结果，使用默认洪水过程")

        st.markdown("---")
        st.markdown("#### 马斯京根参数")

        param_method = st.radio("参数设定方式", ["手动输入", "自动率定"])

        if param_method == "手动输入":
            K = st.slider("K - 蓄量常数 (h)", 0.5, 12.0, 3.0, 0.1)
            x = st.slider("x - 流量比重系数", 0.05, 0.45, 0.25, 0.01)
        else:
            st.info("根据历史洪水数据自动率定K、x参数")
            target_outflow = inflow * 0.7 + np.random.randn(len(inflow)) * 10
            K, x_val, r2 = calc_K_x_from_data(inflow, target_outflow)
            show_banner(f"率定结果：K={K:.2f}h, x={x_val:.3f}, R²={r2:.3f}", "success")
            K = st.slider("K - 蓄量常数 (h)", 0.5, 12.0, float(K), 0.1)
            x = st.slider("x - 流量比重系数", 0.05, 0.45, float(x_val), 0.01)

        dt = st.slider("计算时段 Δt (h)", 0.5, 6.0, 1.0, 0.5)

        channel_length = st.number_input("下游河道长度 (km)", 5.0, 50.0, 18.6)

        if st.button("▶️ 运行马斯京根演进", type="primary", use_container_width=True):
            C0, C1, C2 = calc_muskingum_params(K, x, dt)
            show_banner(f"演进系数：C₀={C0:.4f}, C₁={C1:.4f}, C₂={C2:.4f}, 校验C₀+C₁+C₂={C0+C1+C2:.6f}", "info")

            result = generate_downstream_flood(inflow, K, x, dt, channel_length)
            st.session_state["musk_result"] = result
            st.success("✅ 洪水演进计算完成！")

    with col2:
        st.markdown("### 📊 演进结果")

        if "musk_result" in st.session_state:
            result = st.session_state["musk_result"]
            df = result["result"]
            features = result["features"]

            # 指标行
            cols = st.columns(4)
            metrics_data = [
                ("上游洪峰", f'{features["上游洪峰_m3s"]} m³/s'),
                ("下游洪峰", f'{features["下游洪峰_m3s"]} m³/s'),
                ("削峰率", f'{features["削峰率_pct"]}%'),
                ("传播时间", f'{features["传播时间_h"]} h'),
            ]
            for col, (label, val) in zip(cols, metrics_data):
                with col:
                    show_metric(label, val)

            # 演进过程图
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                subplot_titles=("洪水演进过程", "河道蓄量变化"),
                                vertical_spacing=0.12,
                                row_heights=[0.6, 0.4])

            fig.add_trace(go.Scatter(
                x=df["时段"], y=df["入流_m3s"],
                mode="lines", name="上游入流",
                line=dict(color="#dc3545", width=3)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df["时段"], y=df["出流_m3s"],
                mode="lines", name="下游出流",
                line=dict(color="#1a73e8", width=3)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df["时段"], y=df["削峰率"],
                mode="lines", name="削峰率",
                line=dict(color="#28a745", width=2, dash="dot"),
                yaxis="y2"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=df["时段"], y=df["河段蓄量"],
                mode="lines", name="河段蓄量",
                fill="tozeroy", line=dict(color="#ff6600", width=2)
            ), row=2, col=1)

            fig.update_xaxes(title_text="时段", row=2, col=1)
            fig.update_yaxes(title_text="流量 (m³/s)", row=1, col=1)
            fig.update_yaxes(title_text="蓄量", row=2, col=1)

            fig.update_layout(
                height=650,
                hovermode="x unified",
                legend=dict(orientation="h", y=1.02),
                yaxis2=dict(overlaying="y", side="right",
                           title_text="削峰率 (%)", range=[0, 100])
            )

            st.plotly_chart(fig, use_container_width=True)

            # 特征参数表
            st.markdown("#### 演进特征参数表")
            feat_df = pd.DataFrame({
                "参数": list(features.keys()),
                "数值": list(features.values())
            })
            st.dataframe(feat_df, use_container_width=True)

            # 详细数据
            with st.expander("查看详细演进数据"):
                st.dataframe(df, use_container_width=True)
        else:
            st.info("👈 在左侧设置参数并点击运行")


def page_routing():
    """水库调洪演算"""
    st.markdown('<div class="main-header">🏗️ 水库调洪演算</div>',
                unsafe_allow_html=True)
    show_banner("结合入库洪水过程、水库水位库容关系、泄洪设施能力及发电需求，"
                "进行水库调洪计算，推求水库最高水位和最大下泄流量。", "info")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### ⚙️ 调洪参数设置")

        # 入库洪水
        flood_source = st.radio("洪水来源", ["设计洪水", "典型洪水", "新安江产流"])
        return_period = st.selectbox("洪水重现期", [10, 20, 50, 100, 200, 500, 1000, 2000],
                                     index=3)

        peak_map = {10: 200, 20: 300, 50: 450, 100: 600, 200: 800,
                    500: 1100, 1000: 1400, 2000: 1800}
        peak_default = peak_map[return_period]

        peak = st.number_input("洪峰流量 (m³/s)", 50, 3000, peak_default)
        w_total = st.number_input("洪水总量 (万m³)", 500, 20000, 5000)
        duration = st.slider("洪水历时 (h)", 24, 120, 72)

        inflow = design_flood_hydrograph(return_period, peak, w_total, duration)

        # 初始条件
        initial_level = st.slider("初始坝前水位 (m)", 172.0, 205.0, 198.0,
                                   help="汛限水位198.0m")

        # 调度方案
        st.markdown("#### 泄洪调度方案")
        gate_open = st.slider("溢洪道开启孔数", 0, 6, 3)
        use_power = st.checkbox("考虑发电放水", value=True)

        if st.button("▶️ 开始调洪演算", type="primary", use_container_width=True):
            result, features = reservoir_flood_routing(
                inflow, initial_level, dt=1.0,
                gate_open=gate_open, power_flow=use_power
            )
            st.session_state["routing_result"] = result
            st.session_state["routing_features"] = features
            st.success("✅ 调洪演算完成！")

            # 安全检查
            max_level = features["最高水位_m"]
            params = get_reservoir_params()
            if max_level > params["校核洪水位"]:
                st.error(f"⚠️ **水库不安全！** 最高水位 {max_level}m 超过校核洪水位 {params['校核洪水位']}m")
            elif max_level > params["设计洪水位"]:
                st.warning(f"⚠️ 最高水位 {max_level}m 超过设计洪水位 {params['设计洪水位']}m，需关注")
            else:
                st.success("✅ 最高水位在安全范围内")

    with col2:
        st.markdown("### 📊 调洪演算结果")

        if "routing_result" in st.session_state:
            result = st.session_state["routing_result"]
            features = st.session_state["routing_features"]

            cols = st.columns(4)
            for col, (label, val) in zip(cols, list(features.items())[:4]):
                with col:
                    show_metric(label, val)

            # 双轴图
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                subplot_titles=("入库与出库流量过程", "坝前水位变化"),
                                vertical_spacing=0.12,
                                row_heights=[0.55, 0.45])

            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["入库流量_m3s"],
                mode="lines", name="入库流量",
                line=dict(color="#dc3545", width=3)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["出库总流量_m3s"],
                mode="lines", name="出库总流量",
                line=dict(color="#1a73e8", width=3)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["泄洪流量_m3s"],
                mode="lines", name="泄洪流量",
                line=dict(color="#ff6600", width=2, dash="dash")
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["发电流量_m3s"],
                mode="lines", name="发电流量",
                line=dict(color="#28a745", width=2, dash="dash")
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["坝前水位_m"],
                mode="lines", name="坝前水位",
                fill="tozeroy", line=dict(color="#0d47a1", width=3)
            ), row=2, col=1)

            # 特征水位线
            params = get_reservoir_params()
            for name, val in [("汛限", params["汛限水位"]),
                              ("正常", params["正常蓄水位"]),
                              ("设计", params["设计洪水位"]),
                              ("校核", params["校核洪水位"])]:
                fig.add_hline(y=val, line_dash="dash", line_color="red",
                             annotation_text=name, row=2, col=1)

            fig.update_xaxes(title_text="时间 (h)", row=2, col=1)
            fig.update_yaxes(title_text="流量 (m³/s)", row=1, col=1)
            fig.update_yaxes(title_text="水位 (m)", row=2, col=1)
            fig.update_layout(height=650, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("查看详细调洪数据"):
                st.dataframe(result, use_container_width=True)
        else:
            st.info("👈 在左侧设置调洪参数并点击运行")


def page_dispatch():
    """水库工程调度管理"""
    st.markdown('<div class="main-header">📋 水库工程调度与运行管理分析</div>',
                unsafe_allow_html=True)

    params = get_reservoir_params()

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏗️ 防洪调度方案", "💧 兴利调度", "📜 历史调度", "📋 运行管理体系"
    ])

    with tab1:
        st.markdown("### 防洪调度方案")
        show_banner("根据不同重现期洪水，结合水库特征水位和泄洪能力，制定分级调度方案。",
                    "info")

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("#### 分级调度规则")
            rules = pd.DataFrame({
                "洪水标准": ["< 10年一遇", "10~50年一遇", "50~100年一遇",
                          "100~500年一遇", "500~2000年一遇", "> 2000年一遇"],
                "库水位范围": [f"≤{params['汛限水位']}m", f"{params['汛限水位']}~{params['正常蓄水位']}m",
                           f"{params['正常蓄水位']}~{params['设计洪水位']}m",
                           f"{params['设计洪水位']}~{params['校核洪水位']}m",
                           f">{params['校核洪水位']}m", "超标准洪水"],
                "闸门控制": ["全关", "开启1~2孔", "开启3~4孔", "开启5~6孔",
                         "全开泄洪", "非常措施"],
                "调度目标": ["兴利蓄水", "控泄", "限泄", "全力泄洪", "确保大坝安全", "非常运用"]
            })
            st.dataframe(rules, use_container_width=True)

        with col2:
            st.markdown("#### 泄洪能力校核")
            df_flood = load_water_level_flood_discharge()
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_flood["水位_m"], y=df_flood["六孔全开_m3s"],
                mode="lines+markers", name="六孔全开(最大泄洪能力)",
                line=dict(color="#dc3545", width=3),
                fill="tozeroy"
            ))
            fig.add_vline(x=params["设计洪水位"], line_dash="dash",
                         annotation_text=f"设计洪水位 {params['设计洪水位']}m")
            fig.add_vline(x=params["校核洪水位"], line_dash="dash",
                         annotation_text=f"校核洪水位 {params['校核洪水位']}m",
                         line_color="red")
            fig.update_layout(
                xaxis_title="水位 (m)", yaxis_title="泄洪能力 (m³/s)",
                height=400, hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### 不同频率设计洪水调洪结果")
        freq_data = pd.DataFrame({
            "洪水频率": ["5% (20年)", "2% (50年)", "1% (100年)", "0.1% (1000年)", "0.05% (2000年)"],
            "洪峰(m³/s)": [300, 450, 600, 1400, 1800],
            "最高水位(m)": [201.2, 202.5, 203.8, 204.6, 205.0],
            "最大泄量(m³/s)": [150, 320, 520, 1100, 1500],
            "调洪库容(万m³)": [1200, 1850, 2600, 3100, 3240],
            "是否安全": ["✓ 安全", "✓ 安全", "✓ 安全", "✓ 安全", "✓ 安全"]
        })
        st.dataframe(freq_data, use_container_width=True)

    with tab2:
        st.markdown("### 💧 兴利调度分析")
        show_banner("在保证防洪安全的前提下，优化水库调度过程，"
                    "合理分配水资源，发挥供水、发电、灌溉等综合效益。", "info")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 常规供水调度")
            st.markdown(f"""
            - **死水位**: {params['死水位']}m（死库容 {params['死库容']} 万m³）
            - **正常蓄水位**: {params['正常蓄水位']}m（兴利库容 {params['兴利库容']} 万m³）
            - **年供水量**: 约 5000 万m³
            - **供水保证率**: 95%
            - **灌溉面积**: 约 10.5 万亩
            """)

            st.markdown("#### 发电调度")
            st.markdown(f"""
            - **装机容量**: {params['装机容量']}kW
            - **年发电量**: 约 450 万kWh
            - **发电流量**: 随水位变化 (6~24 m³/s)
            """)

        with col2:
            st.markdown("#### 兴利调度图")
            df_storage = load_water_level_storage()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_storage["水位_m"],
                y=df_storage["库容_万m3"],
                mode="lines", name="水位-库容曲线",
                line=dict(color="#1a73e8", width=3)
            ))

            fig.add_hline(y=params["死库容"], line_dash="dash", line_color="red",
                         annotation_text=f"死库容 {params['死库容']} 万m³")
            fig.add_hline(y=params["总库容"], line_dash="dash", line_color="red",
                         annotation_text=f"总库容 {params['总库容']} 万m³")

            fig.add_vrect(x0=params["死水位"], x1=params["正常蓄水位"],
                         fillcolor="lightgreen", opacity=0.2,
                         annotation_text="兴利库容范围")

            fig.update_layout(
                xaxis_title="水位 (m)", yaxis_title="库容 (万m³)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("### 📜 历史调度记录分析")
        events = ["莫兰蒂", "苗柏", "利奇马", "黑格比", "烟花", "梅花", "梅雨", "康妮"]
        selected = st.selectbox("选择历史事件", events)

        df = load_dispatch(selected)
        if df is not None:
            st.dataframe(df, use_container_width=True)

            # 简单统计
            if "末水位_m" in df.columns and "净入库流量_m3s" in df.columns:
                levels = pd.to_numeric(df["末水位_m"], errors='coerce')
                inflows = pd.to_numeric(df["净入库流量_m3s"], errors='coerce')

                col1, col2, col3 = st.columns(3)
                with col1:
                    show_metric("最高水位", f"{levels.max():.2f}m")
                with col2:
                    show_metric("水位变幅", f"{levels.max()-levels.min():.2f}m")
                with col3:
                    show_metric("最大入库", f"{inflows.max():.1f}m³/s")

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                    subplot_titles=(f"{selected} - 水位变化", f"{selected} - 流量过程"))
                fig.add_trace(go.Scatter(
                    y=levels, mode="lines+markers", name="水位",
                    line=dict(color="#1a73e8", width=2)), row=1, col=1)
                fig.add_trace(go.Scatter(
                    y=inflows, mode="lines+markers", name="入库流量",
                    line=dict(color="#dc3545", width=2)), row=2, col=1)
                fig.update_layout(height=500, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("该事件数据暂不可用")

    with tab4:
        st.markdown("### 📋 水库运行管理体系")
        st.markdown("""
        #### 1. 水文监测体系
        - **雨量监测**: 流域内5个雨量站，实时采集降雨数据
        - **水位监测**: 坝前水位、下游水位自动监测
        - **流量监测**: 入库流量、出库流量实时测量
        - **水质监测**: 定期水质采样分析

        #### 2. 洪水预报预警
        - **预报方案**: 新安江模型 + 马斯京根法联合预报
        - **预见期**: 6~24小时洪水预报
        - **预警阈值**: 根据库水位分级预警
        - **信息发布**: 自动生成调度指令和预警通知

        #### 3. 调度决策流程
        """)
        st.image("https://via.placeholder.com/800x200/0d47a1/FFFFFF?text="
                 "降雨预报→产汇流计算→入库洪水→调洪演算→调度方案→指令下达",
                 use_container_width=True)
        st.markdown("""
        #### 4. 防汛应急管理
        - **汛期值班**: 24小时值班制度
        - **应急预案**: 超标准洪水应急预案
        - **物资储备**: 防汛物资按定额储备
        - **下游预警**: 下游河道预警系统

        #### 5. 设备运维管理
        - **闸门系统**: 定期检修维护
        - **发电机组**: 按规程运行维护
        - **监测设备**: 定期校准
        - **信息系统**: 平台日常运维
        """)


def page_simulation():
    """实时仿真模拟"""
    st.markdown('<div class="main-header">🔄 实时仿真模拟</div>',
                unsafe_allow_html=True)
    show_banner("交互式实时模拟：动态调整洪水参数和调度方案，"
                "实时查看水库调度全过程。", "info")

    # 初始化会话状态
    if "sim_running" not in st.session_state:
        st.session_state["sim_running"] = False
    if "sim_time" not in st.session_state:
        st.session_state["sim_time"] = 0

    col_ctrl, col_disp = st.columns([1, 2])

    with col_ctrl:
        st.markdown("### 🎮 仿真控制")
        params = get_reservoir_params()

        # 洪水情景
        st.markdown("#### 🌧️ 洪水情景设置")
        scenario = st.selectbox("洪水情景", [
            "5年一遇 (P=20%)", "10年一遇 (P=10%)", "20年一遇 (P=5%)",
            "50年一遇 (P=2%)", "100年一遇 (P=1%)", "200年一遇 (P=0.5%)",
            "1000年一遇 (P=0.1%)", "自定义洪水"
        ])

        scenarios = {
            "5年一遇 (P=20%)": (180, 1500, 48),
            "10年一遇 (P=10%)": (250, 2200, 48),
            "20年一遇 (P=5%)": (350, 3200, 54),
            "50年一遇 (P=2%)": (500, 4800, 60),
            "100年一遇 (P=1%)": (650, 6200, 60),
            "200年一遇 (P=0.5%)": (880, 8500, 66),
            "1000年一遇 (P=0.1%)": (1500, 14000, 72),
            "200年一遇 (P=0.5%)": (880, 8500, 66),
            "自定义洪水": (300, 3000, 48)
        }

        if scenario == "自定义洪水":
            pk = st.number_input("洪峰 (m³/s)", 50, 3000, 300)
            vol = st.number_input("总量 (万m³)", 500, 20000, 3000)
            dur = st.slider("历时 (h)", 24, 120, 48)
        else:
            pk, vol, dur = scenarios[scenario]

        # 初始条件
        st.markdown("#### 🏗️ 初始条件")
        init_level = st.slider("初始水位 (m)", 172.0, 205.0, 198.0,
                               help="汛限水位198.0m")

        # 调度方案
        st.markdown("#### 🚪 调度方案")
        gate_plan = st.selectbox("闸门开启方案", [
            "方案1: 先关后开(汛限以下不泄)", "方案2: 常开1孔预泄",
            "方案3: 开启3孔控泄", "方案4: 全开泄洪"
        ])
        gate_map = {"方案1: 先关后开(汛限以下不泄)": 0,
                    "方案2: 常开1孔预泄": 1,
                    "方案3: 开启3孔控泄": 3,
                    "方案4: 全开泄洪": 6}
        gates = gate_map[gate_plan]
        use_power = st.checkbox("发电运行", value=True)

        # 马斯京根参数
        st.markdown("#### 🌊 下游演进参数")
        K_musk = st.slider("K (h)", 0.5, 8.0, 3.0)
        x_musk = st.slider("x", 0.05, 0.45, 0.25)

        # 控制按钮
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            run_btn = st.button("▶️ 运行仿真", type="primary", use_container_width=True)
        with col2:
            if st.button("⏹️ 重置", use_container_width=True):
                st.session_state["sim_running"] = False
                st.session_state["sim_time"] = 0
                st.rerun()

    with col_disp:
        if run_btn:
            st.session_state["sim_running"] = True
            st.session_state["sim_time"] = 0

        if st.session_state["sim_running"]:
            # 生成设计洪水
            inflow = design_flood_hydrograph(1, pk, vol, dur)

            # 水库调洪
            result, features = reservoir_flood_routing(
                inflow, init_level, dt=1.0,
                gate_open=gates, power_flow=use_power
            )

            # 马斯京根演进
            musk = generate_downstream_flood(
                result["出库总流量_m3s"].values,
                K=K_musk, x=x_musk, dt=1.0
            )

            st.markdown("### 📊 实时仿真面板")
            # 指标行
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                show_metric("最高水位", f"{features['最高水位_m']}m")
            with col2:
                show_metric("最大入库", f"{features['最大入库流量_m3s']}m³/s")
            with col3:
                show_metric("最大出库", f"{features['最大出库流量_m3s']}m³/s")
            with col4:
                musk_feat = musk["features"]
                show_metric("下游洪峰", f"{musk_feat['下游洪峰_m3s']}m³/s")

            # 综合图
            fig = make_subplots(
                rows=3, cols=1, shared_xaxes=True,
                subplot_titles=("入库与出库流量过程", "坝前水位变化", "下游演进结果"),
                vertical_spacing=0.1,
                row_heights=[0.35, 0.3, 0.35]
            )

            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["入库流量_m3s"],
                mode="lines", name="入库洪水",
                line=dict(color="#dc3545", width=3)
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["出库总流量_m3s"],
                mode="lines", name="出库流量",
                line=dict(color="#1a73e8", width=3)
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=result["时段_h"], y=result["坝前水位_m"],
                mode="lines", name="坝前水位",
                fill="tozeroy", line=dict(color="#0d47a1", width=3)
            ), row=2, col=1)
            for nm, vl in [("汛限", params["汛限水位"]), ("正常", params["正常蓄水位"]),
                           ("设计", params["设计洪水位"]), ("校核", params["校核洪水位"])]:
                fig.add_hline(y=vl, line_dash="dash", line_color="red",
                             annotation_text=nm, row=2, col=1)

            musk_df = musk["result"]
            fig.add_trace(go.Scatter(
                x=musk_df["时段"], y=musk_df["入流_m3s"],
                mode="lines", name="上游入流(出库)",
                line=dict(color="#1a73e8", width=2)
            ), row=3, col=1)
            fig.add_trace(go.Scatter(
                x=musk_df["时段"], y=musk_df["出流_m3s"],
                mode="lines", name="下游出流",
                line=dict(color="#ff6600", width=3)
            ), row=3, col=1)

            fig.update_xaxes(title_text="时间 (h)", row=3, col=1)
            fig.update_yaxes(title_text="流量 (m³/s)", row=1, col=1)
            fig.update_yaxes(title_text="水位 (m)", row=2, col=1)
            fig.update_yaxes(title_text="流量 (m³/s)", row=3, col=1)
            fig.update_layout(height=800, hovermode="x unified",
                            legend=dict(orientation="h", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

            # 安全评估
            max_level = features["最高水位_m"]
            st.markdown("#### 🔍 安全评估")
            if max_level > params["校核洪水位"]:
                st.error(f"🚨 **不安全！** 最高水位 {max_level}m 超过校核洪水位 {params['校核洪水位']}m！"
                        f"需采取非常运用措施！")
            elif max_level > params["设计洪水位"]:
                st.warning(f"⚠️ **注意！** 最高水位 {max_level}m 超过设计洪水位 {params['设计洪水位']}m"
                          f"，需密切监视")
            else:
                st.success(f"✅ **安全** 最高水位 {max_level}m 在设计洪水位以下，调度合理。")

            # 仿真结果表格
            with st.expander("📋 查看完整仿真数据"):
                tab1, tab2 = st.tabs(["调洪数据", "演进数据"])
                with tab1:
                    st.dataframe(result, use_container_width=True)
                with tab2:
                    st.dataframe(musk_df, use_container_width=True)
        else:
            st.info("👈 在左侧设置参数并点击「运行仿真」开始模拟")


# ============================================================
# 主程序
# ============================================================
def main():
    load_css()
    choice = sidebar_nav()

    # 页面路由
    pages = {
        "主页": page_home,
        "数据总览": page_data_overview,
        "泰森多边形": page_thiessen,
        "新安江模型": page_xinanjing,
        "入库反推": page_reverse_inflow,
        "马斯京根法": page_muskingum,
        "调洪演算": page_routing,
        "调度管理": page_dispatch,
        "实时仿真": page_simulation,
    }

    page_func = pages.get(choice, page_home)
    page_func()

    # 底部信息
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888; padding: 10px;'>"
        "🌊 南江水库洪水调度工程调度平台 v1.0 | "
        "水库洪水预报、工程调度与管理课程设计 | "
        "基于马斯京根法 · 新安江模型"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
