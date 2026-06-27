"""
水库调洪演算与入库洪水反推模块
基于水量平衡原理，实现水库调洪计算和入库洪水反推
"""

import numpy as np
import pandas as pd
from data_loader import (get_storage_interpolator, get_level_interpolator,
                         get_flood_discharge_interpolator, get_powerflow_interpolator,
                         get_reservoir_params, load_water_level_storage)


def reservoir_flood_routing(inflow_series, initial_level, dt=1.0, gate_open=0, power_flow=True):
    """
    水库调洪演算（考虑泄洪设施和发电）
    基于水量平衡方程: I - O = dV/dt
    Args:
        inflow_series: 入库洪水过程 (m³/s)
        initial_level: 初始坝前水位 (m)
        dt: 计算时段 (h)
        gate_open: 闸门开启孔数 (0-6)
        power_flow: 是否考虑发电流量
    Returns:
        pd.DataFrame: 调洪演算结果
    """
    inflow = np.asarray(inflow_series, dtype=float)
    n = len(inflow)

    # 获取插值函数
    storage_func = get_storage_interpolator()
    level_func = get_level_interpolator()
    discharge_func = get_flood_discharge_interpolator()
    power_func = get_powerflow_interpolator()

    params = get_reservoir_params()

    # 将时段转换为秒
    dt_sec = dt * 3600

    # 初始化
    level = np.zeros(n)
    storage = np.zeros(n)  # 万m³
    outflow_total = np.zeros(n)
    outflow_spill = np.zeros(n)  # 泄洪
    outflow_power = np.zeros(n)  # 发电
    storage_change = np.zeros(n)

    # 初始条件
    level[0] = initial_level
    storage[0] = float(storage_func(initial_level))

    # 演算
    for i in range(1, n):
        # 当前泄流能力
        q_spill = float(discharge_func(level[i-1])) * (gate_open / 6.0) if gate_open > 0 else 0
        q_power = float(power_func(level[i-1])) if power_flow else 0
        outflow_prev = q_spill + q_power

        # 水量平衡迭代
        storage_target = storage[i-1] + (inflow[i-1] + inflow[i]) / 2 * dt_sec / 10000 - outflow_prev * dt_sec / 10000

        # 修正存储量（单位转换校正）
        avg_inflow = (inflow[i-1] + inflow[i]) / 2
        avg_outflow = (outflow_prev + q_spill + q_power) / 2

        # 简化一阶隐式法
        storage_target = max(storage[i-1] + (avg_inflow - outflow_prev) * dt_sec / 10000, 0)

        # 插值新水位
        try:
            new_level = float(level_func(storage_target))
            if np.isnan(new_level):
                new_level = level[i-1]
        except:
            new_level = level[i-1]

        # 根据新水位计算泄量
        q_spill_new = float(discharge_func(new_level)) * (gate_open / 6.0) if gate_open > 0 else 0
        q_power_new = float(power_func(new_level)) if power_flow else 0

        # 最终出流
        outflow_spill[i] = q_spill_new
        outflow_power[i] = q_power_new
        outflow_total[i] = q_spill_new + q_power_new
        level[i] = new_level
        storage[i] = float(storage_func(new_level))

    # 库容变化
    storage_change[1:] = np.diff(storage)

    # 验证最高水位
    max_level_idx = np.argmax(level)

    result = pd.DataFrame({
        "时段_h": np.arange(n) * dt,
        "入库流量_m3s": inflow,
        "出库总流量_m3s": outflow_total,
        "泄洪流量_m3s": outflow_spill,
        "发电流量_m3s": outflow_power,
        "坝前水位_m": level,
        "库容_万m3": storage,
        "库容变化_万m3": storage_change,
    })

    features = {
        "最高水位_m": round(np.max(level), 2),
        "最高水位出现时段": f"{int(np.argmax(level))}h",
        "最大入库流量_m3s": round(np.max(inflow), 2),
        "最大出库流量_m3s": round(np.max(outflow_total), 2),
        "调洪库容_万m3": round(np.max(storage) - storage[0], 2),
        "最高水位对应库容_万m3": round(np.max(storage), 2),
        "初始水位_m": round(initial_level, 2),
        "最终水位_m": round(level[-1], 2),
    }

    return result, features


def reverse_inflow_calculation(level_series, outflow_series, dt=1.0, loss_rate=0):
    """
    入库洪水反推（基于水量平衡）
    根据坝前水位变化和出库流量，反推天然入库洪水
    Args:
        level_series: 坝前水位过程 (m)
        outflow_series: 出库流量过程 (m³/s)
        dt: 计算时段 (h)
        loss_rate: 损失流量 (m³/s), 包括蒸发渗漏
    Returns:
        pd.DataFrame: 反推结果
    """
    level = np.asarray(level_series, dtype=float)
    outflow = np.asarray(outflow_series, dtype=float)
    n = min(len(level), len(outflow))

    storage_func = get_storage_interpolator()

    dt_sec = dt * 3600

    inflow = np.zeros(n)
    storage = np.array([float(storage_func(l)) for l in level])

    inflow[0] = outflow[0] + loss_rate  # 初始假设

    for i in range(1, n):
        # V/Δt (单位转换: 万m³/h → m³/s)
        dV_dt = (storage[i] - storage[i-1]) * 10000 / dt_sec
        inflow[i] = dV_dt + (outflow[i] + outflow[i-1]) / 2 + loss_rate
        inflow[i] = max(inflow[i], 0)

    result = pd.DataFrame({
        "时段": np.arange(1, n + 1),
        "坝前水位_m": level[:n],
        "库容_万m3": storage[:n],
        "出库流量_m3s": outflow[:n],
        "反推入库流量_m3s": inflow,
        "库容变化_万m3": np.append(0, np.diff(storage)),
    })

    return result


def design_flood_hydrograph(return_period=100, peak=500, W_total=3000, duration=72):
    """
    生成设计洪水过程线（用于调度方案演算）
    Args:
        return_period: 洪水重现期 (年)
        peak: 洪峰流量 (m³/s)
        W_total: 洪水总量 (万m³)
        duration: 洪水总历时 (h)
    Returns:
        np.array: 设计洪水过程
    """
    t = np.linspace(0, duration, int(duration))
    # 五点概化过程线
    tp = duration * 0.3  # 涨水历时

    Q = np.zeros(len(t))
    for i, ti in enumerate(t):
        if ti <= tp:
            Q[i] = peak * (ti / tp) ** 3.5
        else:
            Q[i] = peak * np.exp(-3.0 * (ti - tp) / (duration - tp))

    # 总量校正
    actual_vol = np.trapz(Q, t) * 3600 / 10000  # 万m³
    if actual_vol > 0:
        Q = Q * (W_total / actual_vol) ** 0.3
        Q = np.minimum(Q, peak * 1.2)

    return Q


def water_balance_analysis(inflow, outflow, initial_storage, dt=1.0):
    """
    水库水量平衡分析
    验证水量平衡：ΔV = (I - O) × Δt
    Args:
        inflow: 入库流量 (m³/s)
        outflow: 出库流量 (m³/s)
        initial_storage: 初始库容 (万m³)
        dt: 时段 (h)
    Returns:
        dict: 水量平衡分析结果
    """
    inflow = np.asarray(inflow)
    outflow = np.asarray(outflow)
    dt_sec = dt * 3600

    n = min(len(inflow), len(outflow))
    storage = np.zeros(n)
    storage[0] = initial_storage

    for i in range(1, n):
        avg_in = (inflow[i] + inflow[i-1]) / 2
        avg_out = (outflow[i] + outflow[i-1]) / 2
        delta_v = (avg_in - avg_out) * dt_sec / 10000
        storage[i] = storage[i-1] + delta_v

    total_in = np.trapz(inflow, dx=dt*3600) / 10000
    total_out = np.trapz(outflow, dx=dt*3600) / 10000
    delta_storage = storage[-1] - storage[0]

    balance = total_in - total_out - delta_storage

    return {
        "总入库_万m3": round(total_in, 2),
        "总出库_万m3": round(total_out, 2),
        "库容变化_万m3": round(delta_storage, 2),
        "水量平衡差_万m3": round(balance, 4),
        "是否闭合": abs(balance) < 0.01,
        "初库容_万m3": initial_storage,
        "末库容_万m3": round(storage[-1], 2),
    }
