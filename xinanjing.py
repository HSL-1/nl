"""
新安江模型（三水源）产汇流模拟模块
基于蓄满产流理论，模拟流域降雨-径流过程
"""

import numpy as np
import pandas as pd


class XinAnJiangModel:
    """
    三水源新安江模型
    核心参数：
        WM: 流域平均蓄水容量 (mm)
        WUM: 上层蓄水容量 (mm)
        WLM: 下层蓄水容量 (mm)
        WDM: 深层蓄水容量 (mm)
        SM: 表层自由水蓄水容量 (mm)
        KG: 地下水出流系数
        KSS: 壤中流出流系数
        KKG: 地下水消退系数
        KSSS: 壤中流消退系数
        C: 深层蒸散发折算系数
        IMP: 不透水面积比例
        B: 蓄水容量曲线指数
        EX: 自由水容量曲线指数
        KE: 蒸散发能力折算系数
    """

    def __init__(self, params=None):
        # 南方湿润地区推荐参数
        self.params = {
            "WM": 140,      # mm
            "WUM": 20,      # mm
            "WLM": 60,      # mm
            "WDM": 60,      # mm
            "SM": 30,       # mm
            "KG": 0.3,      # (0-1)
            "KSS": 0.3,     # (0-1)
            "KKG": 0.95,    # (0-1)
            "KSSS": 0.85,   # (0-1)
            "C": 0.16,      # (0-1)
            "IMP": 0.01,    # (0-1)
            "B": 0.3,       # (0-1)
            "EX": 1.5,      # (0-2)
            "KE": 1.0,      # (0-2)
        }
        if params:
            self.params.update(params)

        # 初始化状态变量
        self.WU = 0  # 上层土壤含水量
        self.WL = 0  # 下层土壤含水量
        self.WD = 0  # 深层土壤含水量
        self.S = 0   # 自由水蓄量
        self.QG = 0  # 地下径流
        self.QSS = 0 # 壤中流
        self.QRS = 0 # 地表径流

    def set_initial_conditions(self, WU=None, WL=None, WD=None, S=None):
        """设置初始土壤含水量状态"""
        if WU is not None:
            self.WU = WU
        if WL is not None:
            self.WL = WL
        if WD is not None:
            self.WD = WD
        if S is not None:
            self.S = S

    def calculate_evapotranspiration(self, EM):
        """
        蒸散发计算（三层蒸发模式）
        Args:
            EM: 流域蒸散发能力 (mm)
        Returns:
            E: 实际蒸散发量 (mm)
        """
        params = self.params
        W = self.WU + self.WL + self.WD
        WUM = params["WUM"]
        WLM = params["WLM"]
        C = params["C"]
        KE = params["KE"]

        EM = EM * KE
        E = 0

        # 上层蒸发
        if self.WU >= EM:
            self.WU -= EM
            E = EM
        else:
            E = self.WU
            self.WU = 0
            # 下层蒸发
            EL = self.WL - (WLM - (EM - E))
            if self.WL >= EM - E:
                self.WL = self.WL - (EM - E)
                E = EM
            else:
                E += self.WL
                self.WL = 0
                # 深层蒸发
                ED = C * (EM - E)
                if self.WD >= ED:
                    self.WD -= ED
                    E += ED
                else:
                    E += self.WD
                    self.WD = 0

        return E

    def calculate_runoff(self, P, EM):
        """
        产流计算（蓄满产流机制）
        Args:
            P: 时段降雨量 (mm)
            EM: 时段蒸散发能力 (mm)
        Returns:
            dict: 各产流分量
        """
        params = self.params
        # 先计算蒸散发
        E = self.calculate_evapotranspiration(EM)

        # 扣除蒸散发后的净雨
        PE = P - E
        if PE <= 0:
            return {"R": 0, "RS": 0, "RI": 0, "RG": 0, "PE": 0}

        WM = params["WM"]
        WUM = params["WUM"]
        WLM = params["WLM"]
        SM = params["SM"]
        IMP = params["IMP"]
        B = params["B"]
        EX = params["EX"]
        KG = params["KG"]
        KSS = params["KSS"]

        W = self.WU + self.WL + self.WD
        WMM = WM * (1 + B)  # 流域最大蓄水容量

        # 计算产流量 R
        if W < WM:
            a = WMM * (1 - (1 - W / WM) ** (1 / (1 + B)))
            if PE + a < WMM:
                R = PE - (WMM - WM) + WM * (1 - (PE + a) / WMM) ** (1 + B)
            else:
                R = PE - (WM - W)
        else:
            R = PE

        # 不透水面积产流
        R = R * (1 - IMP) + PE * IMP

        # 补充土壤含水量
        delta_W = PE - R

        # 先补充上层
        if delta_W > 0:
            if self.WU + delta_W <= WUM:
                self.WU += delta_W
            else:
                delta_W_left = delta_W - (WUM - self.WU)
                self.WU = WUM
                # 再补充下层
                if self.WL + delta_W_left <= WLM:
                    self.WL += delta_W_left
                else:
                    delta_W_left -= (WLM - self.WL)
                    self.WL = WLM
                    # 补充深层
                    self.WD += delta_W_left
                    if self.WD > params["WDM"]:
                        self.WD = params["WDM"]

        # 自由水蓄水库分流（三水源划分）
        if R > 0:
            SMM = SM * (1 + EX)
            # 自由水蓄量计算
            if self.S < SM:
                AU = SMM * (1 - (1 - self.S / SM) ** (1 / (1 + EX)))
                if R + AU < SMM:
                    delta_S = R - (SM - self.S) + SM * (1 - (R + AU) / SMM) ** (1 + EX)
                else:
                    delta_S = R - (SM - self.S)
            else:
                delta_S = R

            self.S += delta_S
            if self.S > SM:
                # 超过自由水容量的部分直接成为地表径流
                RS = R - delta_S + (self.S - SM) * KG / (KG + KSS)
                self.S = SM
            else:
                RS = R - delta_S

            # 壤中流和地下径流
            RI = self.S * KSS
            RG = self.S * KG
            self.S -= (RI + RG)
        else:
            RS, RI, RG = 0, 0, 0

        # 汇流计算（坡面汇流）
        self.QRS = RS * 0.1  # 简化的单位线汇流
        self.QSS = self.QSS * params["KSSS"] + RI * (1 - params["KSSS"])
        self.QG = self.QG * params["KKG"] + RG * (1 - params["KKG"])

        total_Q = self.QRS + self.QSS + self.QG

        return {
            "R": R,
            "RS": RS,
            "RI": RI,
            "RG": RG,
            "E": E,
            "PE": PE,
            "total_Q": total_Q,
            "WU": self.WU,
            "WL": self.WL,
            "WD": self.WD,
            "S": self.S,
        }

    def simulate(self, rainfall_series, evap_series=None):
        """
        Simulate the entire rainfall-runoff process over a time series.
        Args:
            rainfall_series: list/array of rainfall depths (mm) per time step
            evap_series: list/array of ET0 (mm) per time step; default=4.0 mm/d
        Returns:
            pd.DataFrame with time series of flows and states
        """
        n = len(rainfall_series)
        if evap_series is None:
            evap_series = [4.0] * n

        results = []
        for t in range(n):
            out = self.calculate_runoff(rainfall_series[t], evap_series[t])
            out["时段"] = t + 1
            out["降雨_mm"] = rainfall_series[t]
            results.append(out)

        df = pd.DataFrame(results)
        cols = ["时段", "降雨_mm", "PE", "E", "R", "RS", "RI", "RG",
                "total_Q", "WU", "WL", "WD", "S"]
        cols = [c for c in cols if c in df.columns]
        return df[cols]


class ThiessenPolygon:
    """
    泰森多边形（Thiessen Polygon）雨量权重计算
    基于雨量站坐标和流域面积，计算各站点的权重系数
    """

    def __init__(self, stations):
        """
        Args:
            stations: DataFrame with columns ["站点名称", "站点经度", "站点纬度"]
        """
        self.stations = stations.copy()
        self.weights = None

    def calculate_weights_by_area(self, basin_area=None):
        """
        基于面积比例的简化权重计算
        实际应用中应使用几何方法构建泰森多边形
        Args:
            basin_area: 流域总面积(km²)，若为None则只计算比例
        Returns:
            pd.DataFrame: 各站点的权重系数
        """
        # 使用简化的距离反比加权法(IDW)模拟泰森多边形
        n = len(self.stations)
        self.weights = pd.Series(np.ones(n) / n, index=self.stations["站点名称"])
        return self.weights

    def calculate_thiessen_weights(self, basin_area_km2=None):
        """
        泰森多边形权重计算
        基于站点空间分布，计算每个站点的控制面积比例
        Args:
            basin_area_km2: 流域总面积(km²)
        Returns:
            pd.DataFrame: 权重计算结果
        """
        stations = self.stations
        n = len(stations)

        # 使用Voronoi图的空间划分方法
        from scipy.spatial import Voronoi
        import math

        coords = stations[["站点经度", "站点纬度"]].values

        # 添加边界点使Voronoi图闭合
        x_min, x_max = coords[:, 0].min(), coords[:, 0].max()
        y_min, y_max = coords[:, 1].min(), coords[:, 1].max()

        padding = max(x_max - x_min, y_max - y_min) * 2
        border_points = np.array([
            [x_min - padding, y_min - padding],
            [x_max + padding, y_min - padding],
            [x_max + padding, y_max + padding],
            [x_min - padding, y_max + padding],
        ])

        all_points = np.vstack([coords, border_points])
        vor = Voronoi(all_points)

        # 计算每个站点的控制区域面积
        from scipy.spatial import ConvexHull
        weights = []
        areas = []

        for i in range(n):
            region_idx = vor.point_region[i]
            region = vor.regions[region_idx]

            if -1 in region or len(region) == 0:
                weights.append(0)
                areas.append(0)
                continue

            polygon = [vor.vertices[j] for j in region]
            if len(polygon) < 3:
                weights.append(0)
                areas.append(0)
                continue

            hull = ConvexHull(polygon)
            area = hull.volume
            areas.append(area)
            weights.append(area)

        total_area = sum(areas)
        if total_area > 0:
            weights = [w / total_area for w in weights]
        else:
            weights = [1.0 / n] * n

        result = stations.copy()
        result["控制面积"] = areas
        result["权重系数"] = weights

        # 校核权重总和为1
        weight_sum = sum(weights)
        if abs(weight_sum - 1.0) > 1e-6:
            result["权重系数"] = result["权重系数"] / weight_sum

        self.weights = result[["站点名称", "权重系数"]]
        return result

    def calc_area_rainfall(self, station_rainfall):
        """
        根据各站降雨量和权重计算流域面雨量
        Args:
            station_rainfall: dict {站点名称: 降雨量_mm}
        Returns:
            float: 流域面雨量 (mm)
        """
        if self.weights is None:
            self.calculate_weights_by_area()

        area_rain = 0
        for name, weight in zip(self.weights["站点名称"], self.weights["权重系数"]):
            if name in station_rainfall:
                area_rain += station_rainfall[name] * weight

        return area_rain


def generate_design_storm(duration=24, peak_intensity=50, pattern="center"):
    """
    生成设计暴雨过程
    Args:
        duration: 总历时 (h)
        peak_intensity: 最大小时雨强 (mm)
        pattern: 雨型 - "center" 中心型, "front" 前锋型, "back" 后锋型
    Returns:
        np.array: 逐时段降雨量 (mm)
    """
    t = np.arange(duration)
    if pattern == "center":
        rain = peak_intensity * np.exp(-((t - duration/2) ** 2) / (2 * (duration/6) ** 2))
    elif pattern == "front":
        rain = peak_intensity * np.exp(-(t ** 2) / (2 * (duration/8) ** 2))
    elif pattern == "back":
        rain = peak_intensity * np.exp(-((t - duration) ** 2) / (2 * (duration/8) ** 2))
    else:
        rain = peak_intensity * np.ones(duration) * 0.5

    rain[rain < 0.5] = 0
    return rain
