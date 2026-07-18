"""Plotly figure generation for simulation results."""

import pandas as pd
import plotly.graph_objects as go


def plot_production(df: pd.DataFrame) -> go.Figure:
    """
    Create production plot from summary DataFrame.

    Creates one trace per production vector present:
    - FOPR (field oil production rate)
    - FWPR (field water production rate)
    - FGPR (field gas production rate)

    Args:
        df: DataFrame from read_summary() with TIME column.

    Returns:
        Plotly Figure. Empty DataFrame yields Figure with len(fig.data) == 0.
    """
    fig = go.Figure()

    if df.empty or 'TIME' not in df.columns:
        return fig

    time = df['TIME']

    # Field production rates
    traces_added = 0

    for col, name, color in [
        ('FOPR', 'Field Oil Rate (STB/day)', '#1f77b4'),
        ('FWPR', 'Field Water Rate (STB/day)', '#ff7f0e'),
        ('FGPR', 'Field Gas Rate (MSCF/day)', '#2ca02c'),
    ]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=time,
                y=df[col],
                mode='lines',
                name=name,
                line=dict(color=color),
                hovertemplate=f'{name}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>'
            ))
            traces_added += 1

    # Also check for well-level production if no field totals
    if traces_added == 0:
        # Look for well-level rates
        for prefix, name, color in [
            ('WOPR:', 'Well Oil Rate', '#1f77b4'),
            ('WWPR:', 'Well Water Rate', '#ff7f0e'),
            ('WGPR:', 'Well Gas Rate', '#2ca02c'),
        ]:
            well_cols = [c for c in df.columns if c.startswith(prefix)]
            for wc in well_cols:
                well_name = wc.split(':')[-1]
                fig.add_trace(go.Scatter(
                    x=time,
                    y=df[wc],
                    mode='lines',
                    name=f'{name} {well_name}',
                    line=dict(color=color, dash='dot'),
                    hovertemplate=f'{name} {well_name}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>'
                ))
                traces_added += 1

    fig.update_layout(
        title='Production Rates',
        xaxis_title='Time (days)',
        yaxis_title='Rate',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        height=500,
    )

    return fig


def plot_pressure(df: pd.DataFrame) -> go.Figure:
    """
    Create bottom-hole pressure plot from summary DataFrame.

    Creates one trace per WBHP:* column present.

    Args:
        df: DataFrame from read_summary() with TIME column.

    Returns:
        Plotly Figure.
    """
    fig = go.Figure()

    if df.empty or 'TIME' not in df.columns:
        return fig

    time = df['TIME']

    # Find all WBHP columns
    wbhp_cols = [c for c in df.columns if c.startswith('WBHP:')]

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for i, col in enumerate(wbhp_cols):
        well_name = col.split(':')[-1]
        fig.add_trace(go.Scatter(
            x=time,
            y=df[col],
            mode='lines',
            name=f'BHP {well_name}',
            line=dict(color=colors[i % len(colors)]),
            hovertemplate=f'BHP {well_name}: %{{y:.1f}} psia<br>Time: %{{x:.1f}} days<extra></extra>'
        ))

    fig.update_layout(
        title='Bottom-Hole Pressure',
        xaxis_title='Time (days)',
        yaxis_title='Pressure (psia)',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        height=500,
    )

    return fig


def plot_cumulative(df: pd.DataFrame) -> go.Figure:
    """
    Create cumulative production plot.

    Args:
        df: DataFrame from read_summary().

    Returns:
        Plotly Figure.
    """
    fig = go.Figure()

    if df.empty or 'TIME' not in df.columns:
        return fig

    time = df['TIME']

    for col, name, color in [
        ('FOPT', 'Cumulative Oil (STB)', '#1f77b4'),
        ('FWPT', 'Cumulative Water (STB)', '#ff7f0e'),
        ('FGPT', 'Cumulative Gas (MSCF)', '#2ca02c'),
    ]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=time,
                y=df[col],
                mode='lines',
                name=name,
                line=dict(color=color),
                hovertemplate=f'{name}: %{{y:.0f}}<br>Time: %{{x:.1f}} days<extra></extra>'
            ))

    fig.update_layout(
        title='Cumulative Production',
        xaxis_title='Time (days)',
        yaxis_title='Cumulative Volume',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        height=500,
    )

    return fig


def plot_watercut(df: pd.DataFrame) -> go.Figure:
    """
    Create water cut plot.

    Args:
        df: DataFrame from read_summary().

    Returns:
        Plotly Figure.
    """
    fig = go.Figure()

    if df.empty or 'TIME' not in df.columns:
        return fig

    time = df['TIME']

    # Field water cut
    fopr = None
    fwpr = None
    for col in df.columns:
        if col == 'FOPR':
            fopr = col
        elif col == 'FWPR':
            fwpr = col

    if fopr and fwpr:
        liq = df[fopr] + df[fwpr]
        wc = (df[fwpr] / liq.replace(0, pd.NA)) * 100
        fig.add_trace(go.Scatter(
            x=time,
            y=wc,
            mode='lines',
            name='Field Water Cut (%)',
            line=dict(color='#ff7f0e', width=2),
            hovertemplate='Water Cut: %{y:.1f}%<br>Time: %{x:.1f} days<extra></extra>'
        ))

    # Well water cuts
    for prefix in ['WOPR:', 'WWPR:']:
        well_pairs = {}
        for col in df.columns:
            if col.startswith(prefix):
                well = col.split(':')[-1]
                if well not in well_pairs:
                    well_pairs[well] = {}
                well_pairs[well][prefix] = col

    colors = ['#1f77b4', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    for i, (well, cols) in enumerate(well_pairs.items()):
        if 'WOPR:' in cols and 'WWPR:' in cols:
            liq = df[cols['WOPR:']] + df[cols['WWPR:']]
            wc = (df[cols['WWPR:']] / liq.replace(0, pd.NA)) * 100
            fig.add_trace(go.Scatter(
                x=time,
                y=wc,
                mode='lines',
                name=f'WC {well} (%)',
                line=dict(color=colors[i % len(colors)], dash='dot'),
                hovertemplate=f'WC {well}: %{{y:.1f}}%<br>Time: %{{x:.1f}} days<extra></extra>'
            ))

    fig.update_layout(
        title='Water Cut',
        xaxis_title='Time (days)',
        yaxis_title='Water Cut (%)',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        template='plotly_white',
        height=500,
        yaxis=dict(range=[0, 100]),
    )

    return fig