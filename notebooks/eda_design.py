"""Plotly presentation adapted from the user-selected Deloitte Data Design system.

Reference: https://claude.ai/artifact/8LsWY495eAgpPAUWCxd336 (15 October 2026).
This module changes presentation only. It does not claim Deloitte authorship.
"""

import base64
import html
import json
import os
import re
import sys
from pathlib import Path

import plotly.graph_objects as go

TOKENS = {
    'surface': '#FFFFFF', 'surface-quiet': '#E6E6E6', 'surface-brand': '#F1F6E4',
    'text': '#000000', 'text-muted': '#53565A', 'text-inverse': '#FFFFFF',
    'line': '#BBBCBC', 'chart-focus': '#86BC25', 'chart-rest': '#BBBCBC',
    'chart-focus-warning': '#DA291C',
}
GROUPS = ['#86BC25', '#046A38', '#0076A8', '#00ABAB']
SCALE = ['#F1F6E4', '#86BC25', '#3C8F2A', '#046A38', '#1C3D26']
FOCUS, REST = TOKENS['chart-focus'], TOKENS['chart-rest']
TEXT, TEXT_MUTED, LINE = TOKENS['text'], TOKENS['text-muted'], TOKENS['line']
FONT = 'Open Sans, Aptos, Segoe UI, Arial, sans-serif'
SOURCE = 'Source: Project analysis of IBM HI-Small synthetic data.'
CONFIG = {'responsive': True, 'displaylogo': False, 'scrollZoom': False,
          'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'toggleSpikelines'],
          'toImageButtonOptions': {'format': 'svg'}}
_bundle_shown = False


def _colab_output():
    return (not os.environ.get('EMBEZZLEMENT_NOTEBOOK_EXPORT')
            and ('google.colab' in sys.modules or bool(os.environ.get('COLAB_RELEASE_TAG'))))


def stylesheet():
    """Embed the licensed Open Sans Latin variable font for offline viewing."""
    assets = Path(__file__).resolve().parent / 'assets'
    encoded = base64.b64encode((assets / 'OpenSans-Latin.woff2').read_bytes()).decode('ascii')
    font_face = ("@font-face{font-family:'Open Sans';font-style:normal;font-weight:400 700;"
                 "font-display:swap;src:url(data:font/woff2;base64," + encoded + ") format('woff2');}")
    return font_face + '\n' + (Path(__file__).with_name('eda_style.css')).read_text()


def install_notebook_style():
    global _bundle_shown
    from IPython.display import HTML, display
    # Run All can reuse a module already imported by this notebook's kernel.
    _bundle_shown = False
    import plotly.io as pio
    pio.templates['embezzlement_eda'] = plotly_template()
    pio.templates.default = 'embezzlement_eda'
    if not _colab_output():
        display(HTML('<style>' + stylesheet() + '</style>'))


def plotly_template():
    return go.layout.Template(layout={
        'font': {'family': FONT, 'size': 12, 'color': TEXT},
        'paper_bgcolor': TOKENS['surface'], 'plot_bgcolor': TOKENS['surface'],
        'colorway': GROUPS,
        'xaxis': {'showgrid': False, 'zeroline': False, 'showline': False, 'ticks': ''},
        'yaxis': {'showgrid': True, 'gridcolor': LINE, 'gridwidth': 1,
                  'zeroline': False, 'showline': False, 'ticks': ''},
        'bargap': 0.5, 'bargroupgap': 0,
        'hoverlabel': {'bgcolor': TOKENS['surface'], 'bordercolor': LINE,
                       'font': {'family': FONT, 'color': TEXT}},
    })


def show_table(frame, formats=None):
    """Apply plain headers and exact caller formats without modifying source data."""
    import pandas as pd
    from IPython.display import HTML, display
    view = frame.copy()
    if not isinstance(view.index, pd.RangeIndex):
        view = view.reset_index()
    formatters = {}
    for column in view.columns:
        if pd.api.types.is_integer_dtype(view[column]):
            formatters[column] = '{:,.0f}'
        elif pd.api.types.is_float_dtype(view[column]):
            formatters[column] = '{:,.3f}'
    formatters.update(formats or {})
    styled = view.style.format(formatters, na_rep='Not available', escape='html').hide(axis='index')
    numeric = view.select_dtypes(include='number').columns
    if len(numeric):
        styled = styled.set_properties(subset=list(numeric), **{'text-align': 'right',
                                       'font-variant-numeric': 'tabular-nums'})
        styled = styled.set_table_styles([
            {'selector': 'th.col' + str(view.columns.get_loc(column)),
             'props': [('text-align', 'right')]} for column in numeric
        ])
    # Display labels change; original column keys remain available to formatters.
    labels = {column: str(column).replace('_', ' ').strip().capitalize()
              if '_' in str(column) else str(column) for column in view.columns}
    styled = styled.relabel_index([labels[c] for c in view.columns], axis='columns')
    markup = ('<div class="eda-table" tabindex="0" aria-label="Analysis table">'
              + styled.to_html() + '</div>')
    if _colab_output():
        markup = '<style>' + stylesheet() + '</style>' + markup
    display(HTML(markup))


def validate_figure(fig):
    """Check authored chart specs, excluding Plotly's bundled library internals."""
    allowed = set(TOKENS.values()) | set(GROUPS) | set(SCALE)
    spec = json.loads(fig.to_json())
    for color in re.findall(r'#[0-9A-Fa-f]{6}\b', json.dumps(spec)):
        if color.upper() not in allowed:
            raise ValueError('Unexpected chart colour: ' + color)
    for trace in fig.data:
        if trace.opacity is not None and trace.opacity != 1:
            raise ValueError('Use opaque chart marks')
        marker = getattr(trace, 'marker', None)
        if marker is not None and marker.opacity is not None and marker.opacity != 1:
            raise ValueError('Use opaque markers')
    return spec


def finish_figure(fig, name, title, subtitle='', note='', height=500, output_dir=None):
    """Save an offline interactive figure and publish Plotly + HTML notebook MIME."""
    global _bundle_shown
    from IPython.display import display
    fig.update_layout(template=plotly_template(), autosize=True, width=None, height=height,
                      title={'text': '<b>' + html.escape(title) + '</b><br><sup>'
                                     + html.escape(subtitle) + '</sup>', 'x': 0,
                             'xanchor': 'left', 'font': {'size': 15, 'color': TEXT}},
                      font={'family': FONT, 'size': 12, 'color': TEXT},
                      paper_bgcolor=TOKENS['surface'], plot_bgcolor=TOKENS['surface'],
                      legend={'orientation': 'h', 'x': 0, 'y': 1.12,
                              'font': {'color': TEXT, 'size': 11},
                              'bgcolor': TOKENS['surface'], 'borderwidth': 0},
                      modebar={'bgcolor': TOKENS['surface'], 'color': TEXT_MUTED, 'activecolor': TEXT},
                      margin={'l': 88, 'r': 48, 't': 120, 'b': 80},
                      transition={'duration': 0})
    # Preserve analytical axis choices (log scales, ranges and explicit no-grid rows).
    for key in fig.layout:
        if key.startswith(('xaxis', 'yaxis')):
            axis = fig.layout[key]
            axis.update(zeroline=False, showline=False, ticks='', automargin=True,
                        separatethousands=True,
                        tickfont={'family': FONT, 'size': 11, 'color': TEXT_MUTED},
                        title_font={'family': FONT, 'size': 11, 'color': TEXT_MUTED})
            axis.showgrid = False if key.startswith('xaxis') else (axis.showgrid is not False)
            axis.gridcolor, axis.gridwidth = LINE, 1
    for annotation in fig.layout.annotations or []:
        annotation.font = {'family': FONT, 'size': 11, 'color': TEXT}
    fig.update_layout(meta={'design_reference': 'Deloitte Data Design', 'name': name,
                            'finding': title, 'subtitle': subtitle, 'note': note, 'source': SOURCE})
    spec = validate_figure(fig)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    caption = '<figcaption>'
    if note:
        caption += '<p>Note: ' + html.escape(note) + '</p>'
    caption += '<p>' + SOURCE + '</p></figcaption>'
    def wrap(fragment, include_caption=True):
        return ('<figure class="eda-figure" aria-label="' + html.escape(title, quote=True) + '">'
                + '<div class="eda-plot">' + fragment + '</div>'
                + (caption if include_caption else '') + '</figure>')
    in_colab = _colab_output()
    # Colab isolates outputs. Its official renderer also loads a versioned CDN per frame.
    fragment = fig.to_html(full_html=False, include_plotlyjs='cdn' if in_colab else not _bundle_shown,
                           config=CONFIG, div_id='eda-' + name)
    _bundle_shown = True
    standalone = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width,initial-scale=1">'
                  '<title>' + html.escape(title) + '</title><style>' + stylesheet() + '</style>'
                  '</head><body><main class="eda-document">'
                  + wrap(fig.to_html(full_html=False, include_plotlyjs=True, config=CONFIG,
                                     div_id='eda-' + name)) + '</main></body></html>')
    (output_dir / (name + '.html')).write_text(standalone, encoding='utf-8')
    (output_dir / (name + '.plotly.json')).write_text(fig.to_json(), encoding='utf-8')
    if in_colab:
        display({'text/html': '<style>' + stylesheet() + '</style>' + wrap(fragment)}, raw=True)
    else:
        display({'application/vnd.plotly.v1+json': spec,
                 'text/html': wrap(fragment, include_caption=False)}, raw=True)
        from IPython.display import HTML
        display(HTML(caption.replace('<figcaption>', '<div class="eda-caption" role="note">')
                           .replace('</figcaption>', '</div>')))
    return {'name': name, 'title': title, 'traces': len(fig.data), 'source': SOURCE}
