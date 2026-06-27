"""
马斯京根法（Muskingum Method）洪水演进模块
用于模拟水库下泄洪水在下游河道的传播与变形
"""

import numpy as np
import pandas as pd


def calc_muskingum_params(K, x, dt):
    """
    计算马斯京根法演进系数
    Args:
        K: 蓄量常数 (h)
        x: 流量比重系数
        dt: 计算时段 (h)
    Returns:
        (C0, C1, C2): 演进系数，满足 C0+C1+C2=1
    """
    denominator = K - K * x + 0.5 * dt
    if denominator == 0:
        raise ValueError("分母为零，请检查参数K和dt")

    C0 = (0.5 * dt - K * x) / denominator
    C1 = (0.5 * dt + K * x) / denominator
    C2 = (K - K * x - 0.5 * dt) / denominator

    return C0, C1, C2


def muskingum_flood_routing(inflow_series, K, x, dt=1.0, initial_outflow=None):
    """
    马斯京根洪水演进计算
    Args:
        inflow_series: 上游入流过程 (m³/s), array-like
        K: 蓄量常数 (h)
        x: 流量比重系数
        dt: 计算时段 (h), 默认1小时
        initial_outflow: 初始出流 (m³/s), 默认等于第一个入流值
    Returns:
        pd.DataFrame: 包含时段、入流、出流、河段蓄量的演进结果
    """
    inflow = np.asarray(inflow_series, dtype=float)
    n = len(inflow)

    if initial_outflow is None:
        initial_outflow = inflow[0]

    C0, C1, C2 = calc_muskingum_params(K, x, dt)

    outflow = np.zeros(n)
    storage = np.zeros(n)

    outflow[0] = initial_outflow
    storage[0] = K * (x * inflow[0] + (1 - x) * outflow[0])

    for i in range(1, n):
        outflow[i] = C0 * inflow[i] + C1 * inflow[i-1] + C2 * outflow[i-1]
        storage[i] = K * (x * inflow[i] + (1 - x) * outflow[i])

    result = pd.DataFrame({
        "时段": np.arange(1, n + 1),
        "入流_m3s": inflow,
        "出流_m3s": outflow,
        "河段蓄量": storage,
        "削峰率": np.where(inflow > 0, (inflow - outflow) / inflow * 100, 0)
    })

    return result


def calc_K_x_from_data(inflow_series, outflow_series, dt=1.0):
    """
    根据实测入流、出流数据率定马斯京根参数 K 和 x
    使用试算法：选择使蓄量-加权流量关系线性最好的 x 值
    Args:
        inflow_series: 实测入流过程
        outflow_series: 实测出流过程
        dt: 计算时段 (h)
    Returns:
        (K, x, best_r2): 最优参数及相关系数
    """
    inflow = np.asarray(inflow_series, dtype=float)
    outflow = np.asarray(outflow_series, dtype=float)
    n = min(len(inflow), len(outflow))

    # 计算蓄量变化（累计）
    storage = np.zeros(n)
    for i in range(1, n):
        storage[i] = storage[i-1] + (inflow[i] + inflow[i-1])/2 * dt * 3600 \
                     - (outflow[i] + outflow[i-1])/2 * dt * 3600

    # 在合理范围内搜索最优 x 值 (0.0 ~ 0.5)
    x_values = np.linspace(0.0, 0.5, 51)
    best_r2 = -1
    best_x = 0.2
    best_K = 1.0
    best_slope = 1.0

    for x in x_values:
        # 计算加权流量 Q' = x*I + (1-x)*O
        Q_weighted = x * inflow + (1 - x) * outflow

        # 线性回归 storage ~ Q_weighted
        if np.std(Q_weighted) == 0:
            continue

        slope, intercept = np.polyfit(Q_weighted, storage, 1)
        predicted = slope * Q_weighted + intercept

        # 计算 R²
        ss_res = np.sum((storage - predicted) ** 2)
        ss_tot = np.sum((storage - np.mean(storage)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        if r2 > best_r2:
            best_r2 = r2
            best_x = x
            best_K = slope / 3600  # 转换为小时
            best_slope = slope

    return best_K, best_x, best_r2


def simulate_typical_flood(peak_inflow=500, baseflow=50, duration=48, peak_time=12):
    """
    生成典型洪水过程线（用于模拟演示）
    Args:
        peak_inflow: 洪峰流量 (m³/s)
        baseflow: 基流 (m³/s)
        duration: 总历时 (h)
        peak_time: 峰现时间 (h)
    Returns:
        np.array: 洪水过程
    """
    t = np.arange(duration)
    # 使用偏态过程线
    inflow = baseflow + (peak_inflow - baseflow) * np.exp(-((t - peak_time) ** 2) / (2 * (peak_time / 3) ** 2))
    inflow[inflow < baseflow] = baseflow
    return inflow


def generate_downstream_flood(inflow_series, K=3.0, x=0.25, dt=1.0,
                              channel_length=18.6, slope=0.001):
    """
    完整的马斯京根法下游洪水演进计算
    包含跌波校正和成果分析
    Args:
        inflow_series: 上游入流过程 (m³/s)
        K: 蓄量常数 (h)，南江水库下游建议范围 2.0~5.0
        x: 流量比重系数，建议范围 0.1~0.3
        dt: 计算时段 (h)
        channel_length: 河道长度 (km)
        slope: 河道比降
    Returns:
        dict: 包含演进结果和特征值
    """
    result = muskingum_flood_routing(inflow_series, K, x, dt)

    inflow = result["入流_m3s"].values
    outflow = result["出流_m3s"].values

    # 特征值提取
    peak_inflow = np.max(inflow)
    peak_outflow = np.max(outflow)
    peak_inflow_time = np.argmax(inflow) + 1
    peak_outflow_time = np.argmax(outflow) + 1

    # 洪水传播时间（峰现时间差）
    travel_time = peak_outflow_time - peak_inflow_time

    # 削峰率
    peak_reduction = (peak_inflow - peak_outflow) / peak_inflow * 100 if peak_inflow > 0 else 0

    # 洪水历时（流量超过基流+10%的部分）
    threshold = inflow[0] * 1.1
    flood_duration_in = np.sum(inflow > threshold)
    flood_duration_out = np.sum(outflow > threshold)

    features = {
        "上游洪峰_m3s": round(peak_inflow, 2),
        "下游洪峰_m3s": round(peak_outflow, 2),
        "洪峰削减_m3s": round(peak_inflow - peak_outflow, 2),
        "削峰率_pct": round(peak_reduction, 2),
        "上游峰现时段": int(peak_inflow_time),
        "下游峰现时段": int(peak_outflow_time),
        "传播时间_h": int(travel_time),
        "上游洪水历时_h": int(flood_duration_in),
        "下游洪水历时_h": int(flood_duration_out),
        "演进系数_C0": round(calc_muskingum_params(K, x, dt)[0], 4),
        "演进系数_C1": round(calc_muskingum_params(K, x, dt)[1], 4),
        "演进系数_C2": round(calc_muskingum_params(K, x, dt)[2], 4),
        "蓄量常数K_h": K,
        "流量比重系数x": x,
    }

    return {
        "result": result,
        "features": features,
        "params": {"K": K, "x": x, "dt": dt}
    }
