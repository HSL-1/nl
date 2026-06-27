"""
南江水库数据加载模块
数据来源优先级：① Streamlit Secrets → ② 本地 JSON 文件
公开的 GitHub 仓库中不含任何数据！
"""

import pandas as pd
import numpy as np
from scipy import interpolate
import json, os

# ============================================================
# 数据加载（从密钥或本地文件）
# ============================================================

def _load_data():
    """加载数据：Secrets > 本地JSON文件"""
    data_str = None

    # 方案①：从 Streamlit Cloud Secrets 读取
    try:
        import streamlit as st
        data_str = st.secrets.get("reservoir_data")
        if data_str:
            if isinstance(data_str, str):
                return json.loads(data_str)
            else:
                return data_str  # 已经是 dict
    except Exception:
        pass

    # 方案②：从本地 JSON 文件读取（开发环境）
    local_path = os.path.join(os.path.dirname(__file__), "reservoir_data.json")
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise FileNotFoundError(
        "未找到数据！请确保：\n"
        "1. 本地运行：reservoir_data.json 文件存在\n"
        "2. Streamlit Cloud：已在 Settings > Secrets 中设置 reservoir_data"
    )

# 全局数据缓存
_DATA = None

def _get_data():
    global _DATA
    if _DATA is None:
        _DATA = _load_data()
    return _DATA


# ============================================================
# 公共加载函数
# ============================================================

def load_water_level_storage():
    d = _get_data()
    return pd.DataFrame(d["wl_storage"], columns=["水位_m", "库容_万m3"])

def load_water_level_powerflow():
    d = _get_data()
    return pd.DataFrame(d["wl_powerflow"], columns=["水位_m", "发电流量_m3s"])

def load_water_level_flood_discharge():
    d = _get_data()
    return pd.DataFrame(d["wl_flood"], columns=["水位_m", "单孔全开_m3s", "六孔全开_m3s"])

def load_water_level_area():
    d = _get_data()
    return pd.DataFrame(d["wl_area"], columns=["水位_m", "面积_km2"])

def load_stations():
    d = _get_data()
    return pd.DataFrame(d["stations"], columns=["类型", "站码", "站点名称", "站点经度", "站点纬度"])

def load_annual_inflow():
    d = _get_data()
    records = []
    months = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]
    for year_str, vals in d["annual_inflow"].items():
        row = {"年份": int(year_str)}
        for i, m in enumerate(months):
            row[m] = vals[i] if i < len(vals) else 0
        records.append(row)
    return pd.DataFrame(records)

def load_historical_dispatch(event_name):
    """历史调度模拟数据（基于统计特征生成）"""
    np.random.seed(hash(event_name) % 10000)
    n = 20
    times = [f"2024-01-{d+1:02d} 00:00" for d in range(n)]
    levels = 198.5 + np.cumsum(np.random.rand(n) * 0.03 - 0.005)
    inflows = np.random.rand(n) * 30 + 10
    spills = np.random.rand(n) * 15

    df = pd.DataFrame({
        "时段": times,
        "末水位_m": np.round(levels, 2),
        "净入库流量_m3s": np.round(inflows, 1),
        "闸门流量_m3s": np.round(spills, 1),
    })
    return df


# ============================================================
# 插值函数
# ============================================================

def _build_interp(xy_pairs):
    arr = np.array(xy_pairs)
    return interpolate.interp1d(arr[:, 0], arr[:, 1], kind='linear',
                                 bounds_error=False,
                                 fill_value=(arr[0, 1], arr[-1, 1]))

def get_storage_interpolator():
    d = _get_data()
    return _build_interp(d["wl_storage"])

def get_level_interpolator():
    d = _get_data()
    return _build_interp([(y, x) for x, y in d["wl_storage"]])

def get_flood_discharge_interpolator():
    d = _get_data()
    arr = np.array(d["wl_flood"])
    return interpolate.interp1d(arr[:, 0], arr[:, 2], kind='linear',
                                 bounds_error=False, fill_value=0)

def get_powerflow_interpolator():
    d = _get_data()
    return _build_interp(d["wl_powerflow"])

def get_area_interpolator():
    d = _get_data()
    return _build_interp(d["wl_area"])


# ============================================================
# 水库参数
# ============================================================

def get_reservoir_params():
    d = _get_data()
    return dict(d["reservoir_params"])
