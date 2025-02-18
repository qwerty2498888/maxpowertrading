import yfinance as yf
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta

# Инициализация Dash приложения
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Список разрешенных пользователей Telegram
ALLOWED_USERS = ["@MaxPower212", "212", "@AnotherUser", "@cronoq", "@avg1987", "@VictorIziumschii", " @robertcz84", "@tatifad", "@Andrey_Maryev", "@Stepanov_SV", "@martin5711", "@dkirhlarov", "@o_stmn", "@Jus_Urfin", "@AlexandrM_1976", "@Natalijapan", "@IgorM215", "@OchirMan08", "@bayun_333", "@paveldems", "@Lbanki", "@artjomeif", "@Nikitin_Kirill8", "@impulsiveness", "@ViktorAlenchikov", "@PavelZam", "@ruslan_rms", "@Dmitry_BA", "@kserginfo", "@lepsagog", "@eugeneenovikov", "@KyotoDzen", "@vardb", "@Alex_Investment_com", "@STAR_Serg", "@Intrigo7", "@sergeewpavel", "@Yan_yog", "@yuryleon", "@sani821305", "@bagh0lder", "@avgust_avgustt", "@IFin82", "@niqo5586", "Markokorp", "@d200984", "@Zhenya_jons", "@Chili_palmer", "@vadim_gr77", "375291767178", "79122476671", "@By_Debor", "@NoName999887", "manival515", "@Valerij_Cy", "@djek70", "@isaevmike", "@ilapirova", "Sergey_Bill", "@rra3483", "@bezzubcev", "@armen_lalaian", "@olegstamatov", "@LeonidShoggot", "@afonin900", "@Banderas111", "@DmitriiPetrenko", "@hyperil0", "@ViacheslavPar", "@Ramilguns", "@andreymiamimoscow", "Bapik_t", "436642455545", "@gyuszijaro", "@helenauvarova", "@Rewire", "@kommm_ko", "@DenisTrubnik", "@MdEYE", "@garik_bale", "@KJurginiene", "@svvalkiria", "@kiloperza", "@MakenzyM", "@YLT777", "@sunfire_08", "@igorartem", "@StepanenkoP", "@Sea_Master_07", "380958445987", "@Alex_Grii", "@Yuriy_Kutafin", "@MazurenkoYaroslav", "@gvejalis", "@di_floww", "@dokulakov", "@travelpro5", "@yrchik91", "@rom0788", "@euko2", "@AleksBroBob", "@KirillTroshinM", "@DenisOO7", "@eiler_b", "@Wrt666", "@sergey_deko", "@Galexprivate", "@DrWinsent", "@rishat11kh", "@Jephrin", "37123305995"  ]

# Функция для преобразования тикеров
def normalize_ticker(ticker):
    index_map = {
        "SPX": "^SPX", "NDX": "^NDX", "RUT": "^RUT", "DIA": "^DIA",
        "SPY": "SPY", "QQQ": "QQQ", "DIA": "DIA", "XSP": "XSP", "IWM": "IWM"
    }
    return index_map.get(ticker.upper(), ticker.upper())

# Функция получения данных по опционам
def get_option_data(ticker, expirations):
    ticker = normalize_ticker(ticker)  # Нормализуем тикер
    try:
        stock = yf.Ticker(ticker)
        available_dates = stock.options
        print(f"Доступные даты экспирации для {ticker}: {available_dates}")  # Отладочное сообщение
    except Exception as e:
        print(f"Ошибка загрузки данных {ticker}: {e}")
        return None, [], None, None

    if not available_dates:
        print(f"Нет доступных дат экспирации для {ticker}")  # Отладочное сообщение
        return None, [], None, None

    if not expirations:
        expirations = [available_dates[0]]

    all_options_data = []

    for expiration in expirations:
        try:
            option_chain = stock.option_chain(expiration)
            calls = option_chain.calls[['strike', 'openInterest', 'volume']].rename(
                columns={'openInterest': 'Call OI', 'volume': 'Call Volume'})
            puts = option_chain.puts[['strike', 'openInterest', 'volume']].rename(
                columns={'openInterest': 'Put OI', 'volume': 'Put Volume'})

            options_data = calls.merge(puts, on='strike', how='outer').sort_values(by='strike')
            all_options_data.append(options_data)
        except Exception as e:
            print(f"Ошибка загрузки данных для {expiration}: {e}")

    if not all_options_data:
        print("Нет данных по опционам")  # Отладочное сообщение
        return None, available_dates, None, None

    combined_data = pd.concat(all_options_data).groupby("strike", as_index=False).sum()

    if stock.history(period="1d").shape[0] > 0:
        spot_price = stock.history(period="1d")['Close'].iloc[-1]
    else:
        spot_price = None

    if spot_price:
        combined_data['Net GEX'] = (
                (combined_data['Call OI'] * spot_price / 100 * spot_price * 0.001)
                - (combined_data['Put OI'] * spot_price / 100 * spot_price * 0.001)
        ).round(1)

    combined_data['AG'] = ((combined_data['Call OI'] * spot_price / 100 * spot_price * 0.005) +
                           (combined_data['Put OI'] * spot_price / 100 * spot_price * 0.005)).round(1)

    max_ag_strike = combined_data.loc[combined_data['AG'].idxmax(), 'strike']

    return combined_data, available_dates, spot_price, max_ag_strike

# Лейаут для объединенной страницы
app.layout = html.Div([
    dcc.Store(id='username-store', storage_type='local'),  # Хранилище для имени пользователя
    dcc.Store(id='auth-status', storage_type='local', data=False),  # Хранилище для статуса авторизации

    # Блок для ввода имени пользователя (отображается только до авторизации)
    html.Div(id='login-container', children=[
        html.Label("Введите ваше имя пользователя Telegram:"),
        dcc.Input(id='username-input', type='text', placeholder='@username', className='dash-input'),
        html.Button('Проверить', id='submit-button', n_clicks=0, className='dash-button'),
        html.Div(id='access-message', style={'margin-top': '10px'})
    ], className='dash-container'),

    # Основной контент (отображается только после авторизации)
    html.Div(id='main-content', style={'display': 'none'}, children=[
        html.H1("Max Power", style={'textAlign': 'center'}),

        html.Div([
            html.Label("Введите тикер актива:"),
            dcc.Input(id='ticker-input', type='text', value='SPX', className='dash-input'),
        ], className='dash-container'),

        html.Div([
            html.Label("Выберите даты экспирации:"),
            dcc.Dropdown(id='date-dropdown', multi=True, className='dash-dropdown'),
        ], className='dash-container'),

        html.Div([
            html.Label("Выберите параметры:"),
            html.Div([
                html.Button("Net GEX", id="btn-net-gex", className="parameter-button"),
                html.Button("AG", id="btn-ag", className="parameter-button"),
                html.Button("Call OI", id="btn-call-oi", className="parameter-button"),
                html.Button("Put OI", id="btn-put-oi", className="parameter-button"),
                html.Button("Call Volume", id="btn-call-vol", className="parameter-button"),
                html.Button("Put Volume", id="btn-put-vol", className="parameter-button"),
            ], className="button-container"),
        ], className='dash-container'),

        dcc.Store(id='selected-params', data=['Net GEX']),  # Храним нажатые кнопки
        dcc.Store(id='options-data-store'),  # Хранение данных для Charts

        dcc.Graph(
            id='options-chart',
            style={'height': '900px'},  # Высота верхнего графика (оставляем как есть)
            config={'displayModeBar': False}  # Отключаем панель инструментов
        ),
        dcc.Graph(
            id='price-chart',
            style={'height': '950px'},  # Увеличиваем высоту нижнего графика
            config={'displayModeBar': False}  # Отключаем панель инструментов
        ),
        dcc.Graph(
            id='price-chart-simplified',  # Новый график
            style={'height': '950px'},  # Увеличиваем высоту нового графика
            config={'displayModeBar': False}  # Отключаем панель инструментов
        )
    ])
])

# Callback для проверки имени пользователя и управления видимостью элементов
@app.callback(
    [Output('access-message', 'children'),
     Output('main-content', 'style'),
     Output('login-container', 'style'),
     Output('username-store', 'data'),
     Output('auth-status', 'data')],
    [Input('submit-button', 'n_clicks')],
    [State('username-input', 'value'),
     State('username-store', 'data'),
     State('auth-status', 'data')]
)
def check_username(n_clicks, username, stored_username, auth_status):
    if n_clicks > 0:
        if username in ALLOWED_USERS:
            return (
                "Доступ разрешен.",  # Сообщение
                {'display': 'block'},  # Основной контент виден
                {'display': 'none'},  # Поле ввода скрыто
                username,  # Сохраняем имя пользователя
                True  # Устанавливаем статус авторизации
            )
        else:
            return (
                "Доступ запрещен.",  # Сообщение
                {'display': 'none'},  # Основной контент скрыт
                {'display': 'block'},  # Поле ввода видно
                None,  # Очищаем имя пользователя
                False  # Устанавливаем статус авторизации
            )
    elif stored_username and stored_username in ALLOWED_USERS and auth_status:
        return (
            "",  # Сообщение не нужно
            {'display': 'block'},  # Основной контент виден
            {'display': 'none'},  # Поле ввода скрыто
            stored_username,  # Сохраняем имя пользователя
            True  # Устанавливаем статус авторизации
        )
    return (
        "",  # Сообщение не нужно
        {'display': 'none'},  # Основной контент скрыт
        {'display': 'block'},  # Поле ввода видно
        stored_username,  # Сохраняем имя пользователя
        auth_status  # Сохраняем статус авторизации
    )

# Callback для обновления списка дат
@app.callback(
    [Output('date-dropdown', 'options'), Output('date-dropdown', 'value')],
    [Input('ticker-input', 'value')]
)
def update_dates(ticker):
    ticker = normalize_ticker(ticker)  # Нормализуем тикер
    _, available_dates, _, _ = get_option_data(ticker, [])
    print(f"Доступные даты: {available_dates}")  # Отладочное сообщение
    if not available_dates:
        return [], []
    options = [{'label': date, 'value': date} for date in available_dates]
    return options, [available_dates[0]]  # Возвращаем список опций и первую дату по умолчанию

# Callback для обновления нажатых кнопок
@app.callback(
    [Output('selected-params', 'data'),
     Output('btn-net-gex', 'className'),
     Output('btn-ag', 'className'),
     Output('btn-call-oi', 'className'),
     Output('btn-put-oi', 'className'),
     Output('btn-call-vol', 'className'),
     Output('btn-put-vol', 'className')],
    [Input('btn-net-gex', 'n_clicks'),
     Input('btn-ag', 'n_clicks'),
     Input('btn-call-oi', 'n_clicks'),
     Input('btn-put-oi', 'n_clicks'),
     Input('btn-call-vol', 'n_clicks'),
     Input('btn-put-vol', 'n_clicks')],
    State('selected-params', 'data')
)
def update_selected_params(btn_net, btn_ag, btn_call_oi, btn_put_oi, btn_call_vol, btn_put_vol, selected_params):
    ctx = dash.callback_context
    if not ctx.triggered:
        return selected_params, "parameter-button", "parameter-button", "parameter-button", "parameter-button", "parameter-button", "parameter-button"

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    button_map = {
        "btn-net-gex": "Net GEX",
        "btn-ag": "AG",
        "btn-call-oi": "Call OI",
        "btn-put-oi": "Put OI",
        "btn-call-vol": "Call Volume",
        "btn-put-vol": "Put Volume"
    }

    param = button_map.get(button_id)

    if param:
        if param in selected_params:
            selected_params.remove(param)
        else:
            selected_params.append(param)

    # Определяем классы для кнопок
    button_classes = {
        "btn-net-gex": "active" if "Net GEX" in selected_params else "parameter-button",
        "btn-ag": "active" if "AG" in selected_params else "parameter-button",
        "btn-call-oi": "active" if "Call OI" in selected_params else "parameter-button",
        "btn-put-oi": "active" if "Put OI" in selected_params else "parameter-button",
        "btn-call-vol": "active" if "Call Volume" in selected_params else "parameter-button",
        "btn-put-vol": "active" if "Put Volume" in selected_params else "parameter-button"
    }

    return selected_params, button_classes["btn-net-gex"], button_classes["btn-ag"], button_classes["btn-call-oi"], \
    button_classes["btn-put-oi"], button_classes["btn-call-vol"], button_classes["btn-put-vol"]

# Callback для обновления графика опционов
@app.callback(
    Output('options-chart', 'figure'),
    [Input('ticker-input', 'value'),
     Input('date-dropdown', 'value'),
     Input('selected-params', 'data')]
)
def update_options_chart(ticker, dates, selected_params):
    if not dates or not selected_params:
        return go.Figure()

    ticker = normalize_ticker(ticker)  # Нормализуем тикер
    options_data, _, spot_price, max_ag_strike = get_option_data(ticker, dates)
    if options_data is None or options_data.empty:
        return go.Figure()

    fig = go.Figure()

    # Определение диапазона для индексов и акций
    if ticker in ["^SPX", "^NDX", "^RUT", "^Dia"]:
        price_range = 0.010  # 1.5% для индексов
    elif ticker in ["SPY", "QQQ", "DIA", "XSP", "IWM"]:
        price_range = 0.04  # 5% для ETF (SPY, QQQ, DIA, XSP, IWM)
    else:
        price_range = 0.30  # 30% для акций

    if spot_price:
        left_limit = spot_price - (spot_price * price_range)
        right_limit = spot_price + (spot_price * price_range)
        # Фильтрация данных для индексов, чтобы они не выходили за пределы видимой области
        options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)]
    else:
        left_limit = right_limit = 0

    # Фильтрация страйков по выбранному параметру
    if "Net GEX" in selected_params:
        options_data = options_data[options_data['Net GEX'] != 0]
    elif "AG" in selected_params:
        options_data = options_data[options_data['AG'] != 0]

    # Добавление данных для выбранных параметров
    for parameter in selected_params:
        hover_texts = [
            f"Strike: {strike}<br>Call OI: {coi}<br>Put OI: {poi}<br>Call Volume: {cvol}<br>Put Volume: {pvol}<br>{parameter}: {val}"
            for strike, coi, poi, cvol, pvol, val in zip(
                options_data['strike'],
                options_data['Call OI'],
                options_data['Put OI'],
                options_data['Call Volume'],
                options_data['Put Volume'],
                options_data[parameter]
            )
        ]

        if parameter == "Net GEX":
            fig.add_trace(go.Bar(
                x=options_data['strike'],
                y=options_data['Net GEX'],
                marker_color=['#22b5ff' if v >= 0 else 'red' for v in options_data['Net GEX']],
                name="Net GEX",
                hovertext=hover_texts,
                hoverinfo="text",
                marker=dict(line=dict(width=0))
            ))

        elif parameter == "AG":
            fig.add_trace(go.Scatter(
                x=options_data['strike'],
                y=options_data['AG'],
                mode='lines+markers',  # Добавляем маркеры
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#915bf8'),  # Настройка маркеров
                fill='tozeroy',
                name="AG",
                hovertext=hover_texts,
                hoverinfo="text",
                yaxis='y2'
            ))

        elif parameter == "Call OI":
            fig.add_trace(go.Scatter(
                x=options_data['strike'],
                y=options_data['Call OI'],
                mode='lines+markers',  # Добавляем маркеры
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#02d432'),  # Настройка маркеров
                fill='tozeroy',
                name="Call OI",
                hovertext=hover_texts,
                hoverinfo="text",
                yaxis='y2'
            ))

        elif parameter == "Put OI":
            fig.add_trace(go.Scatter(
                x=options_data['strike'],
                y=options_data['Put OI'],
                mode='lines+markers',  # Добавляем маркеры
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#f32d35'),  # Настройка маркеров
                fill='tozeroy',
                name="Put OI",
                hovertext=hover_texts,
                hoverinfo="text",
                yaxis='y2'
            ))

        elif parameter == "Call Volume":
            fig.add_trace(go.Scatter(
                x=options_data['strike'],
                y=options_data['Call Volume'],
                mode='lines+markers',  # Добавляем маркеры
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#003cfe'),  # Настройка маркеров
                fill='tozeroy',
                name="Call Volume",
                hovertext=hover_texts,
                hoverinfo="text",
                yaxis='y2'
            ))

        elif parameter == "Put Volume":
            fig.add_trace(go.Scatter(
                x=options_data['strike'],
                y=options_data['Put Volume'],
                mode='lines+markers',  # Добавляем маркеры
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#e55f04'),  # Настройка маркеров
                fill='tozeroy',
                name="Put Volume",
                hovertext=hover_texts,
                hoverinfo="text",
                yaxis='y2'
            ))

    # Добавление вертикальной линии текущей цены
    if spot_price:
        fig.add_vline(
            x=spot_price,
            line_dash="solid",
            line_color="orange",
            annotation_text=f"Price: {spot_price:.2f}",
            annotation_position="top",
            annotation_font=dict(color="orange"),
        )

    # Настройка границ оси X для динамического смещения
    fig.update_layout(
        xaxis=dict(
            title="Strike",
            showgrid=False,
            zeroline=False,
            tickmode='array',  # Используем массив значений для оси X
            tickvals=options_data['strike'].tolist(),  # Реальные значения страйков
            tickformat='d',  # Округление страйков до целых чисел
        ),
        yaxis=dict(title="Net GEX", side="left", showgrid=False, zeroline=False),
        yaxis2=dict(title="", side="right", overlaying="y", showgrid=False, zeroline=False),
        title="" + ticker,
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
    )

    # Добавление водяного знака "Max Power"
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.5,  # Центр графика
        text="Max Power",
        showarrow=False,
        font=dict(size=80, color="rgba(255, 255, 255, 0.1)"),  # Полупрозрачный белый текст
        textangle=0,  # Горизонтальный текст
    )

    return fig

# Callback для обновления графика цены
@app.callback(
    Output('price-chart', 'figure'),
    [Input('ticker-input', 'value')]
)
def update_price_chart(ticker):
    # Нормализуем тикер
    ticker = normalize_ticker(ticker)

    # Задаем интервал по умолчанию (например, '1m')
    interval = '1m'  # Фиксированный интервал

    # Получаем данные по тикеру
    stock = yf.Ticker(ticker)
    data = stock.history(period='1d', interval=interval)

    if data.empty:
        return go.Figure()

    # Получаем данные по опционам для расчета AG, P1, N1, Call Vol и Put Vol
    options_data, _, spot_price, max_ag_strike = get_option_data(ticker, [])

    # Определение диапазона для индексов и акций
    if ticker in ["^SPX", "^NDX", "^RUT", "^DJI", "SPY", "QQQ", "IWM"]:
        price_range = 0.01  # 1.5% для индексов
    else:
        price_range = 0.05  # 30% для акций

    if spot_price:
        left_limit = spot_price - (spot_price * price_range)
        right_limit = spot_price + (spot_price * price_range)
        # Фильтрация данных для индексов, чтобы они не выходили за пределы видимой области
        options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)
        ]
    else:
        left_limit = right_limit = 0

    # Фильтруем данные опционов в пределах видимой области
    if options_data is not None and not options_data.empty:
        visible_options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)
        ]
    else:
        visible_options_data = pd.DataFrame()

    # Находим максимальное значение AG, P1, N1, Call Vol и Put Vol в видимой области
    if not visible_options_data.empty:
        max_ag_strike = visible_options_data.loc[visible_options_data['AG'].idxmax(), 'strike']
        max_p1_strike = visible_options_data.loc[visible_options_data['Net GEX'].idxmax(), 'strike']
        max_n1_strike = visible_options_data.loc[visible_options_data['Net GEX'].idxmin(), 'strike']
        max_call_vol_strike = visible_options_data.loc[visible_options_data['Call Volume'].idxmax(), 'strike']
        max_put_vol_strike = visible_options_data.loc[visible_options_data['Put Volume'].idxmax(), 'strike']
    else:
        max_ag_strike = None
        max_p1_strike = None
        max_n1_strike = None
        max_call_vol_strike = None
        max_put_vol_strike = None

    # Определяем время открытия рынка (9:30 утра по местному времени)
    market_open_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    current_time = datetime.now()

    # Определяем, прошло ли 45 минут после открытия рынка
    if current_time - market_open_time <= timedelta(minutes=45):
        # Логика для первых 45 минут
        if max_call_vol_strike is not None and max_put_vol_strike is not None:
            if max_call_vol_strike > max_put_vol_strike:
                max_power_strike = max_call_vol_strike
            else:
                max_power_strike = max_put_vol_strike
        elif max_call_vol_strike is not None:
            max_power_strike = max_call_vol_strike
        elif max_put_vol_strike is not None:
            max_power_strike = max_put_vol_strike
        else:
            max_power_strike = None
    else:
        # Логика после 45 минут
        if max_ag_strike is not None:
            if max_ag_strike == max_p1_strike or max_ag_strike == max_n1_strike:
                max_power_strike = max_ag_strike
            else:
                if max_call_vol_strike is not None and max_put_vol_strike is not None:
                    if max_call_vol_strike > max_put_vol_strike:
                        max_power_strike = max_call_vol_strike
                    else:
                        max_power_strike = max_put_vol_strike
                elif max_call_vol_strike is not None:
                    max_power_strike = max_call_vol_strike
                elif max_put_vol_strike is not None:
                    max_power_strike = max_put_vol_strike
                else:
                    max_power_strike = None
        else:
            max_power_strike = None

    # Создаем словарь для толщины линий
    line_widths = {
        'AG': 7,  # Толщина линии AG
        'P1': 5,  # Толщина линии P1
        'N1': 5,  # Толщина линии N1
        'Call Vol': 4,  # Толщина линии Call Vol
        'Put Vol': 4,  # Толщина линии Put Vol
        'Max Power': 3  # Толщина линии Max Power
    }

    # Создаем свечной график
    fig = go.Figure()

    # Добавляем свечи
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name="Candlesticks"
    ))

    # Добавляем горизонтальную линию уровня цены, где достигается максимальное значение P1
    if max_p1_strike is not None:
        fig.add_trace(go.Scatter(
            x=[data.index[0], data.index[-1]],  # От начала до конца графика
            y=[max_p1_strike, max_p1_strike],  # Горизонтальная линия на уровне max_p1_strike
            mode='lines',
            line=dict(color='#00ff00', width=line_widths['P1']),  # Зеленая сплошная линия
            name=f'P1 Strike: {max_p1_strike:.2f}',  # Подпись линии
            yaxis='y'  # Убедимся, что линия использует ту же ось Y, что и свечи
        ))

    # Добавляем горизонтальную линию уровня цены, где достигается максимальное отрицательное значение Net GEX (N1)
    if max_n1_strike is not None:
        fig.add_trace(go.Scatter(
            x=[data.index[0], data.index[-1]],  # От начала до конца графика
            y=[max_n1_strike, max_n1_strike],  # Горизонтальная линия на уровне max_n1_strike
            mode='lines',
            line=dict(color='#ff0000', width=line_widths['N1']),  # Красная сплошная линия
            name=f'N1 Strike: {max_n1_strike:.2f}',  # Подпись линии
            yaxis='y'  # Убедимся, что линия использует ту же ось Y, что и свечи
        ))

    # Добавляем горизонтальную линию уровня цены, где достигается максимальное значение Call Volume
    if max_call_vol_strike is not None:
        fig.add_trace(go.Scatter(
            x=[data.index[0], data.index[-1]],  # От начала до конца графика
            y=[max_call_vol_strike, max_call_vol_strike],  # Горизонтальная линия на уровне max_call_vol_strike
            mode='lines',
            line=dict(color='#00a0ff', width=line_widths['Call Vol']),  # Синяя сплошная линия
            name=f'Call Vol Strike: {max_call_vol_strike:.2f}',  # Подпись линии
            yaxis='y'  # Убедимся, что линия использует ту же ось Y, что и свечи
        ))

    # Добавляем горизонтальную линию уровня цены, где достигается максимальное значение Put Volume
    if max_put_vol_strike is not None:
        fig.add_trace(go.Scatter(
            x=[data.index[0], data.index[-1]],  # От начала до конца графика
            y=[max_put_vol_strike, max_put_vol_strike],  # Горизонтальная линия на уровне max_put_vol_strike
            mode='lines',
            line=dict(color='#ac5631', width=line_widths['Put Vol']),  # Коричневая сплошная линия
            name=f'Put Vol Strike: {max_put_vol_strike:.2f}',  # Подпись линии
            yaxis='y'  # Убедимся, что линия использует ту же ось Y, что и свечи
        ))

    # Добавляем горизонтальную линию уровня цены для "Max Power"
    if max_power_strike is not None:
        fig.add_trace(go.Scatter(
            x=[data.index[0], data.index[-1]],  # От начала до конца графика
            y=[max_power_strike, max_power_strike],  # Горизонтальная линия на уровне max_power_strike
            mode='lines',
            line=dict(color='#ffdf00', width=line_widths['Max Power']),  # Желтая сплошная линия
            name=f'Max Power: {max_power_strike:.2f}',  # Подпись линии
            yaxis='y'  # Убедимся, что линия использует ту же ось Y, что и свечи
        ))

        # Добавляем горизонтальную линию уровня цены, где достигается максимальное значение AG
        if max_ag_strike is not None:
            fig.add_trace(go.Scatter(
                x=[data.index[0], data.index[-1]],  # От начала до конца графика
                y=[max_ag_strike, max_ag_strike],  # Горизонтальная линия на уровне max_ag_strike
                mode='lines',
                line=dict(color='#ab47bc', dash='dash', width=line_widths['AG']),  # Фиолетовая пунктирная линия
                name=f'AG Strike: {max_ag_strike:.2f}',  # Подпись линии
                yaxis='y'  # Убедимся, что линия использует ту же ось Y, что и свечи
            ))

    # Настройка графика
    fig.update_layout(
        title=f"{ticker}",  # Фиксированный интервал
        xaxis=dict(
            title="Время",
            type='date',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            rangeslider=dict(visible=False),
            autorange=True,  # Автоматическое расширение оси X
            fixedrange=False,  # Разрешаем динамическое изменение диапазона
        ),
        yaxis=dict(
            title="Цена",
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            fixedrange=False
        ),
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        hovermode='x unified',
        margin=dict(l=50, r=50, b=50, t=50),
        dragmode='pan'
    )

    # Добавление водяного знака "Max Power" на нижний график
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.5,  # Центр графика
        text="Max Power",
        showarrow=False,
        font=dict(size=80, color="rgba(255, 255, 255, 0.1)"),  # Полупрозрачный белый текст
        textangle=0,  # Горизонтальный текст
    )

    return fig

# Callback для обновления нового графика цены
# Callback для обновления нового графика цены
# Callback для обновления нового графика цены
# Callback для обновления нового графика цены
@app.callback(
    Output('price-chart-simplified', 'figure'),
    [Input('ticker-input', 'value')]
)
def update_price_chart_simplified(ticker):
    # Нормализуем тикер
    ticker = normalize_ticker(ticker)

    # Задаем интервал по умолчанию (например, '1m')
    interval = '1m'  # Фиксированный интервал

    # Получаем данные по тикеру
    stock = yf.Ticker(ticker)
    data = stock.history(period='1d', interval=interval)

    if data.empty:
        return go.Figure()

    # Получаем данные по опционам для расчета AG, Call Vol и Put Vol
    options_data, _, spot_price, _ = get_option_data(ticker, [])

    if options_data is None or options_data.empty:
        return go.Figure()

    # Определяем диапазон для индексов и акций
    if ticker in ["^SPX", "^NDX", "^RUT", "^DJI", "SPY", "QQQ", "IWM"]:
        price_range = 0.01  # 1.5% для индексов
        resistance_zone_lower_percent = -0.0005  # -0.05%
        resistance_zone_upper_percent = 0.0015  # +0.15%
        support_zone_lower_percent = -0.0015  # -0.15%
        support_zone_upper_percent = 0.0005  # +0.05%
    else:
        price_range = 0.05  # 30% для акций
        resistance_zone_lower_percent = -0.002  # -0.2%
        resistance_zone_upper_percent = 0.0035  # +0.35%
        support_zone_lower_percent = -0.0035  # -0.35%
        support_zone_upper_percent = 0.002  # +0.2%

    if spot_price:
        left_limit = spot_price - (spot_price * price_range)
        right_limit = spot_price + (spot_price * price_range)
        # Фильтрация данных для индексов, чтобы они не выходили за пределы видимой области
        options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)
        ]
    else:
        left_limit = right_limit = 0

    # Находим максимальное значение Call Volume, AG и Put Volume
    max_call_vol_strike = options_data.loc[options_data['Call Volume'].idxmax(), 'strike']
    max_ag_strike = options_data.loc[options_data['AG'].idxmax(), 'strike']
    max_put_vol_strike = options_data.loc[options_data['Put Volume'].idxmax(), 'strike']

    # Определяем, какие зоны рисовать
    zones_to_draw = []

    # Логика построения зон
    if max_call_vol_strike > spot_price and max_ag_strike > spot_price and max_put_vol_strike < spot_price:
        # Если Call Volume и AG выше цены, а Put Volume ниже цены
        # Зона Resistance: от -0.05% до +0.15% (для индексов) или от -0.2% до +0.35% (для остальных)
        resistance_zone_lower = max_call_vol_strike * (1 + resistance_zone_lower_percent)
        resistance_zone_upper = max_call_vol_strike * (1 + resistance_zone_upper_percent)
        zones_to_draw.append((resistance_zone_lower, resistance_zone_upper, 'Resistance zone'))

        # Зона Support: от -0.15% до +0.05% (для индексов) или от -0.35% до +0.2% (для остальных)
        support_zone_lower = max_put_vol_strike * (1 + support_zone_lower_percent)
        support_zone_upper = max_put_vol_strike * (1 + support_zone_upper_percent)
        zones_to_draw.append((support_zone_lower, support_zone_upper, 'Support zone'))

    elif max_call_vol_strike > spot_price and max_ag_strike < spot_price and max_put_vol_strike < spot_price:
        # Если Call Volume выше цены, а AG и Put Volume ниже цены
        # Зона Resistance: от -0.05% до +0.15% (для индексов) или от -0.2% до +0.35% (для остальных)
        resistance_zone_lower = max_call_vol_strike * (1 + resistance_zone_lower_percent)
        resistance_zone_upper = max_call_vol_strike * (1 + resistance_zone_upper_percent)
        zones_to_draw.append((resistance_zone_lower, resistance_zone_upper, 'Resistance zone'))

        # Зона Support: от -0.15% до +0.05% (для индексов) или от -0.35% до +0.2% (для остальных)
        support_zone_lower = max_ag_strike * (1 + support_zone_lower_percent)
        support_zone_upper = max_ag_strike * (1 + support_zone_upper_percent)
        zones_to_draw.append((support_zone_lower, support_zone_upper, 'Support zone'))

    # Создаем свечной график
    fig = go.Figure()

    # Добавляем свечи
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name="Candlesticks"
    ))

    # Добавляем зоны
    for lower, upper, label in zones_to_draw:
        fig.add_trace(go.Scatter(
            x=[data.index[0], data.index[-1], data.index[-1], data.index[0]],  # Координаты X для прямоугольника
            y=[lower, lower, upper, upper],  # Координаты Y для прямоугольника
            fill="toself",  # Заливка области
            fillcolor="rgba(0, 160, 255, 0.2)" if label == 'Resistance zone' else "rgba(172, 86, 49, 0.2)",
            line=dict(color="rgba(0, 160, 255, 0.5)" if label == 'Resistance zone' else "rgba(172, 86, 49, 0.5)"),
            mode="lines",
            name=label,  # Подпись зоны
            hoverinfo="none",  # Отключаем всплывающие подсказки для зон
        ))

    # Настройка графика
    fig.update_layout(
        title=f"Support / Resistance {ticker}",  # Фиксированный интервал
        xaxis=dict(
            title="Время",
            type='date',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            rangeslider=dict(visible=False),
            autorange=True,  # Автоматическое расширение оси X
            fixedrange=False,  # Разрешаем динамическое изменение диапазона
        ),
        yaxis=dict(
            title="Цена",
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            fixedrange=False
        ),
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        hovermode='x unified',
        margin=dict(l=50, r=50, b=50, t=50),
        dragmode='pan'
    )

    # Добавление водяного знака "Max Power" на новый график
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.5,  # Центр графика
        text="Max Power",
        showarrow=False,
        font=dict(size=80, color="rgba(255, 255, 255, 0.1)"),  # Полупрозрачный белый текст
        textangle=0,  # Горизонтальный текст
    )

    return fig

# Запуск приложения
if __name__ == '__main__':
    app.run_server(host="0.0.0.0", port=8080)

