import dash
from dash import dcc, html

# Страница "Closed Trades"
def create_layout():
    return html.Div([
        html.H1("Closed Trades", style={'textAlign': 'center'}),
        # Компоненты для отображения данных о закрытых сделках
        html.Div([
            html.Table([html.Tr([html.Th("Trade ID"), html.Th("Symbol"), html.Th("Date")])])
        ])
    ])
