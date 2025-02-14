# Лейаут для страницы Charts
charts_layout = html.Div([
    html.H1("Charts", style={'textAlign': 'center'}),

    html.Div([
        html.Label("Введите тикер актива:"),
        dcc.Input(id='ticker-input-charts', type='text', value='AAPL', className='dash-input'),
    ], className='dash-container'),

    html.Div([
        html.Label("Выберите интервал:"),
        dcc.Dropdown(
            id='interval-dropdown',
            options=[
                {'label': '1 минута', 'value': '1'},
                {'label': '5 минут', 'value': '5'},
                {'label': '15 минут', 'value': '15'},
                {'label': '1 час', 'value': '60'},
                {'label': '1 день', 'value': 'D'},
            ],
            value='15',  # Значение по умолчанию
            className='dash-dropdown'
        ),
    ], className='dash-container'),

    # TradingView Widget
    html.Iframe(
        id='tradingview-chart',
        src="https://s.tradingview.com/widgetembed/?symbol=AAPL&interval=15&hidelegend=1&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=f1f3f6&studies=[]&hideideas=1&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides={}&overrides={}&enabled_features=[]&disabled_features=[]&locale=en&utm_source=localhost&utm_medium=widget&utm_campaign=chart&utm_term=AAPL",
        style={'height': '800px', 'width': '100%', 'border': 'none'}
    )
])