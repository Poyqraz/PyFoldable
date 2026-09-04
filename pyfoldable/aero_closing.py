"""Advance ratio / eksenel akışa bağlı aero kapanma momenti (kanonik model).

Fiziksel motivasyon: ileri (veya ters) eksenel akış, uç segment üzerinde açılmayı
geri iten bir aerodinamik moment üretir; bu da kısmi açılmaya ve verim düşüşüne yol
açar (bkz. US Patent 11667364). Bu modül tek kaynak (single source of truth)
olarak hem V1 kuazi-statik denge (``kinematics.theta_deg_moment_based``) hem de
V2 dinamik hinge moment hesabı (``dynamics.hinge_moments.compute_hinge_moments``)
tarafından kullanılır.

Proxy model (boyut analizi ``[Pa]·[m²]·[m] = N·m``)::

    q      = 0.5 * rho * V_axial²                # eksenel akış dinamik basıncı [Pa]
    A_ref  = extension * tip_segment_length_m     # kordsuz uç referans alanı [m²]
    M_close = close_moment_gain * q * A_ref * r_cg

``close_moment_gain`` boyutsuz kalibrasyon katsayısıdır (mevcut ``aero_hinge_moment_gain``
deseniyle uyumlu). Varsayılan **kapalı**: ``gain <= 0`` veya ``V_axial <= 0`` veya
``rpm <= 0`` iken moment sıfırdır, dolayısıyla mevcut V1/V2 çıktıları birebir korunur.

Kabul (explicit assumption): kuazi-statik yolda kapalı-form dengeyi korumak için
``A_ref`` theta'dan bağımsız, tam-açık uzantı (``extension = tip_segment_length_m``)
referansıyla alınır. Theta'ya bağlı geometri yalnızca V2 dinamik yolunda
(``theta_dependent=True``) kullanılır.
"""

from __future__ import annotations

from typing import Optional

from .geometry_helpers import effective_tip_cg_from_hinge_m, tip_radial_extension_from_config
from .models import FoldablePropellerConfig


def closing_moment_nm(
    rpm: float,
    theta_deg: float,
    config: FoldablePropellerConfig,
    *,
    axial_velocity_m_s: Optional[float] = None,
    rho: float = 1.225,
    theta_dependent: bool = False,
) -> float:
    """Aero kapanma momentinin büyüklüğü (N·m, pozitif = açılmaya karşı).

    ``axial_velocity_m_s`` verilmezse ``config.aero_closing.axial_velocity_m_s``
    kullanılır. Dönen değer daima ``>= 0``'dır; açılma dengesinden/çıkarımından
    çağıran taraf sorumludur (denge: ``M_open - M_close = M_resist``).
    """
    aero_closing = config.aero_closing
    gain = aero_closing.close_moment_gain
    v_axial = (
        axial_velocity_m_s
        if axial_velocity_m_s is not None
        else aero_closing.axial_velocity_m_s
    )

    if gain <= 0.0 or v_axial <= 0.0 or rpm <= 0.0:
        return 0.0

    length_m = config.geometry.tip_segment_length_m
    extension = (
        tip_radial_extension_from_config(theta_deg, config)
        if theta_dependent
        else length_m
    )
    if extension <= 0.0:
        return 0.0

    q = 0.5 * rho * v_axial**2
    a_ref = extension * length_m
    r_cg = effective_tip_cg_from_hinge_m(config.geometry)
    return gain * q * a_ref * r_cg
