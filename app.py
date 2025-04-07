import yfinance as yf
import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
from flask_caching import Cache
from urllib.parse import parse_qs

# Инициализация Dash приложения
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Настройка кэширования
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'cache-directory',
    'CACHE_THRESHOLD': 100
})
cache.clear()

# Список разрешенных пользователей Telegram
ALLOWED_USERS = ["313", "@cronoq", "@avg1987", "@VictorIziumschii", "@robertcz84", "@tatifad", "@Andrey_Maryev", "@Stepanov_SV", "@martin5711", "@dkirhlarov", "@o_stmn", "@Jus_Urfin", "@IgorM215", "@Lbanki", "@artjomeif", "@ViktorAlenchikov", "@PavelZam", "@ruslan_rms", "@kserginfo", "@Yan_yog", "@IFin82", "@niqo5586", "@d200984", "@Zhenya_jons", "@Chili_palmer", "375291767178", "79122476671", "@manival515", "@isaevmike", "@ilapirova", "@rra3483", "@armen_lalaian", "@olegstamatov", "@Banderas111", "@andreymiamimoscow", "436642455545", "@gyuszijaro", "@helenauvarova", "@Rewire", "@garik_bale", "@KJurginiene", "@kiloperza", "@YLT777", "@Sea_Master_07", "380958445987", "@Yuriy_Kutafin", "@di_floww", "@dokulakov", "@travelpro5", "@yrchik91", "@euko2", "@DenisOO7", "@Wrt666", "@Galexprivate", "@DrWinsent", "@rishat11kh", "37123305995", "@Yura_Bok", "@FaidenSA", "821042646260", "79956706060", "358451881908", "4917632707543", "@jonytvester", "79160779977", "@maxpower3674", "@maxpower4566", "@maxpower7894", "@maxpower6635", "@Renat258", "@bagh0lder", "79057666666", "@Bapik_t", "@SergeyM072", "380672890848", "@Sergey_Bill", "@dmitrylan", "@Qwertyid", "@puzyatkin_kolbosyatkin", "@mrseboch", "79219625180", "@Vitrade134", "@Vaness_IB", "@iririchs", "@Natalijapan", "@ElenaRussianSirena", "@Andrey_ol1", "@Ac7777888", "@Andrii36362", "@roman43210sh", "@Kuzmitskiy_Maksim", "79281818128", "@AlexMa_freedom", "@And_084", "@outsolo", "@ZxSmith", "@Andrzej_Zm", "@Romich408", "@Maksim8022", "@Nikitin_Kirill8", "@art_kirakozov", "@davribr", "14253942333", "@Korney21", "@Andrei_Pishvanov", "@iahis", "@Aik99999", "37126548141", "@vadim_gr77", "@makoltsov", "@alexndsn", "@option2037", "@futuroid", "79852696802", "@Serge_Kost", "@iurii_serbin", "79103333226", "@Roma_pr", "@ElenaERMACK", "@Alexrut1588", "17044214938", "@canapsis", "79646560911", "@kazamerican", "@sterner2021", "@RudolfPlett", "@Nikolay_Detkovskiy", "@Geosma55", "@DmitriiDubov87", "@sergeytrotskii", "@yuryleon", "@dmitriy_kashintsev", "@Maxabr91", "@kingkrys", "@ZERHIUS", "@Aydar_Ka", "@DrKoledgio", "@holod_new", "@procarbion", "@msyarcev", "17866060066", "@DmitriiUSB", "@Jephrin", "@MdEYE", "@Deonis_14", "@Mistershur", '@MakenzyM', "@OchirMan08", "@MarkAlim8", "@v_zmitrovich", "@amsol111", "@Atomicgo18", "@djek70", "79043434519", "@iii_logrus", "@Groove12", "@sergeewpavel", "@RomaTomilov", "@Markokorp", "t_gora", "@luciusmagnus", "@AlexandrM_1976", "@shstrnn", "@nzdr15", "@DmitriiPetrenko", "@Arsen911", "@Norfolk_san"]


# Функция для преобразования тикеров
def normalize_ticker(ticker):
    index_map = {
        "SPX": "^SPX", "NDX": "^NDX", "RUT": "^RUT", "DIA": "^DIA",
        "SPY": "SPY", "QQQ": "QQQ", "DIA": "DIA", "XSP": "XSP", "IWM": "IWM", "VIX": "^VIX"
    }
    return index_map.get(ticker.upper(), ticker.upper())


# Функция получения данных по опционам с кэшированием
@cache.memoize(timeout=60)
def get_option_data(ticker, expirations):
    ticker = normalize_ticker(ticker)
    try:
        stock = yf.Ticker(ticker)
        available_dates = stock.options
        print(f"Доступные даты экспирации для {ticker}: {available_dates}")
    except Exception as e:
        print(f"Ошибка загрузки данных {ticker}: {e}")
        return None, [], None, None

    if not available_dates:
        print(f"Нет доступных дат экспирации для {ticker}")
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
        print("Нет данных по опционам")
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


# Функция для расчета статических уровней
def calculate_static_levels(options_data, spot_price):
    # Уровни сопротивления
    resistance_levels = []

    # Максимальные значения AG выше текущей цены
    ag_above_spot = options_data[options_data['strike'] > spot_price]
    if not ag_above_spot.empty:
        max_ag_strike = ag_above_spot.loc[ag_above_spot['AG'].idxmax(), 'strike']
        resistance_levels.append(('AG', max_ag_strike))

    # Максимальные положительные значения Net GEX выше текущей цены
    net_gex_above_spot = options_data[(options_data['strike'] > spot_price) & (options_data['Net GEX'] > 0)]
    if not net_gex_above_spot.empty:
        max_net_gex_strike = net_gex_above_spot.loc[net_gex_above_spot['Net GEX'].idxmax(), 'strike']
        resistance_levels.append(('Net GEX', max_net_gex_strike))

    # Уровни поддержки
    support_levels = []

    # Максимальные значения AG ниже текущей цены
    ag_below_spot = options_data[options_data['strike'] < spot_price]
    if not ag_below_spot.empty:
        max_ag_strike = ag_below_spot.loc[ag_below_spot['AG'].idxmax(), 'strike']
        support_levels.append(('AG', max_ag_strike))

    # Максимальные отрицательные значения Net GEX ниже текущей цены
    net_gex_below_spot = options_data[(options_data['strike'] < spot_price) & (options_data['Net GEX'] < 0)]
    if not net_gex_below_spot.empty:
        max_net_gex_strike = net_gex_below_spot.loc[net_gex_below_spot['Net GEX'].idxmin(), 'strike']
        support_levels.append(('Net GEX', max_net_gex_strike))

    # Объединение уровней, если они находятся близко друг к другу (в пределах 20 пунктов)
    def merge_levels(levels):
        merged = []
        for level in sorted(levels, key=lambda x: x[1]):
            if merged and abs(level[1] - merged[-1][1]) <= 20:
                merged[-1] = ('Merged', min(merged[-1][1], level[1]), max(merged[-1][1], level[1]))
            else:
                merged.append(level)
        return merged

    resistance_levels = merge_levels(resistance_levels)
    support_levels = merge_levels(support_levels)

    return resistance_levels, support_levels


# Функция для добавления статических уровней на график
def add_static_levels_to_chart(fig, resistance_levels, support_levels, market_open_time, market_close_time):
    # Параметры зон
    resistance_zone_lower_percent = -0.00045
    resistance_zone_upper_percent = 0.0002
    support_zone_lower_percent = -0.0002
    support_zone_upper_percent = 0.00045

    # Добавление зон сопротивления
    for level in resistance_levels:
        if isinstance(level[1], tuple):  # Если уровень объединен
            lower, upper = level[1]
        else:  # Если уровень одиночный
            lower = level[1] * (1 + resistance_zone_lower_percent)
            upper = level[1] * (1 + resistance_zone_upper_percent)

        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time, market_close_time, market_open_time],
            y=[lower, lower, upper, upper],
            fill="toself",
            fillcolor="rgba(0, 255, 216, 0.2)",  # Полупрозрачный синий
            line=dict(color="rgba(0, 255, 216, 0.2)"),
            mode="lines",
            name=f'Resistance Zone',
            hoverinfo="none",
        ))

    # Добавление зон поддержки
    for level in support_levels:
        if isinstance(level[1], tuple):  # Если уровень объединен
            lower, upper = level[1]
        else:  # Если уровень одиночный
            lower = level[1] * (1 + support_zone_lower_percent)
            upper = level[1] * (1 + support_zone_upper_percent)

        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time, market_close_time, market_open_time],
            y=[lower, lower, upper, upper],
            fill="toself",
            fillcolor="rgba(153, 50, 50, 0.2)",  # Полупрозрачный оранжевый
            line=dict(color="rgba(153, 50, 50, 0.5)"),
            mode="lines",
            name=f'Support Zone',
            hoverinfo="none",
        ))

    return fig


# Лейаут для страницы "Options Summary"
options_summary_page = html.Div(
    className='options-summary-page',
    children=[
        html.H1("P/C Ratio", style={'textAlign': 'center', 'color': 'white'}),

        html.Div(
            dash_table.DataTable(
                id='options-summary-table',
                columns=[
                    {'name': 'Ticker', 'id': 'Ticker'},
                    {'name': 'Price', 'id': 'Price'},
                    {'name': 'Resistance', 'id': 'Resistance'},
                    {'name': 'Support', 'id': 'Support'},
                    {'name': 'Call OI Amount', 'id': 'Call OI Amount'},
                    {'name': 'Put OI Amount', 'id': 'Put OI Amount'},
                    {'name': 'P/C Ratio', 'id': 'P/C Ratio'}
                ],
                # Основные настройки
                editable=False,
                row_selectable='none',
                cell_selectable=False,
                style_as_list_view=True,  # Убирает полосы между строками

                # Стилизация
                style_table={
                    'overflowX': 'auto',
                    'borderRadius': '12px',
                    'boxShadow': '0 4px 10px rgba(0, 0, 0, 0.3)',
                    'backgroundColor': '#1e1e1e',
                    'pointerEvents': 'none'  # Полное отключение взаимодействия
                },
                style_header={
                    'backgroundColor': '#1e1e1e',
                    'color': 'white',
                    'fontWeight': 'bold',
                    'border': 'none'
                },
                style_cell={
                    'backgroundColor': '#2d2d2d',
                    'color': 'white',
                    'padding': '10px',
                    'textAlign': 'center',
                    'border': 'none',
                    'cursor': 'default',
                    'pointerEvents': 'none'  # Отключает события мыши для ячеек
                },
                style_data={
                    'border': 'none',
                    'pointerEvents': 'none'  # Отключает события мыши для данных
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': '#252525'
                    },
                    {
                        'if': {'column_id': 'P/C Ratio'},
                        'fontWeight': 'bold'
                    }
                ],

                # Дополнительные параметры для полного отключения взаимодействия
                active_cell=None,
                selected_cells=None,

            ),
            style={'margin-bottom': '20px'}
        ),
        dcc.Location(id='summary-url', refresh=False)
    ],
    style={
        'margin-left': '10%',
        'padding': '20px',
        'color': 'white'
    }
)

# Лейаут для страницы "How to use GEX"
how_to_use_gex_page = html.Div(
    className='how-to-use-gex-page',
    children=[
        html.H1("Как использовать GEX", style={'textAlign': 'center', 'color': 'white'}),

        # Видео раздел
        html.Div([
            html.H2("", style={'color': '#00ffcc', 'textAlign': 'center', 'margin-bottom': '30px'}),

            # Первое видео
            html.Div([
                dcc.Markdown(
                    """
                    <div style="width:100%; height:500px; margin-bottom:10px; border-radius:10px; overflow:hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.3)">
                        <iframe 
                            src="https://www.youtube.com/embed/leCrLFoL51Y" 
                            width="100%" 
                            height="100%" 
                            frameborder="0" 
                            style="border:none;"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                            allowfullscreen>
                        </iframe>
                    </div>
                    """,
                    dangerously_allow_html=True
                ),
                html.P("Сигнал на Long/Short",
                       style={'textAlign': 'center', 'color': 'white', 'font-size': '18px'})
            ], style={'margin-bottom': '40px', 'background-color': '#252525', 'padding': '20px',
                      'border-radius': '10px'}),
            # Первое видео
            html.Div([
                dcc.Markdown(
                    """
                    <div style="width:100%; height:500px; margin-bottom:10px; border-radius:10px; overflow:hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.3)">
                        <iframe 
                            src="https://www.youtube.com/embed/bgunK-z1gD0" 
                            width="100%" 
                            height="100%" 
                            frameborder="0" 
                            style="border:none;"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                            allowfullscreen>
                        </iframe>
                    </div>
                    """,
                    dangerously_allow_html=True
                ),
                html.P("Сигнал на пробой уровня",
                       style={'textAlign': 'center', 'color': 'white', 'font-size': '18px'})
            ], style={'margin-bottom': '40px', 'background-color': '#252525', 'padding': '20px',
                      'border-radius': '10px'}),
            # Первое видео
            html.Div([
                dcc.Markdown(
                    """
                    <div style="width:100%; height:500px; margin-bottom:10px; border-radius:10px; overflow:hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.3)">
                        <iframe 
                            src="https://www.youtube.com/embed/leCrLFoL51Y" 
                            width="100%" 
                            height="100%" 
                            frameborder="0" 
                            style="border:none;"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                            allowfullscreen>
                        </iframe>
                    </div>
                    """,
                    dangerously_allow_html=True
                ),
                html.P("Understanding Gamma Exposure Basics",
                       style={'textAlign': 'center', 'color': 'white', 'font-size': '18px'})
            ], style={'margin-bottom': '40px', 'background-color': '#252525', 'padding': '20px',
                      'border-radius': '10px'}),

            # Второе видео
            html.Div([
                dcc.Markdown(
                    """
                    <div style="width:100%; height:500px; margin-bottom:10px; border-radius:10px; overflow:hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.3)">
                        <iframe 
                            src="https://www.youtube.com/embed/bgunK-z1gD0" 
                            width="100%" 
                            height="100%" 
                            frameborder="0" 
                            style="border:none;"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                            allowfullscreen>
                        </iframe>
                    </div>
                    """,
                    dangerously_allow_html=True
                ),
                html.P("Advanced GEX Trading Strategies",
                       style={'textAlign': 'center', 'color': 'white', 'font-size': '18px'})
            ], style={'margin-bottom': '40px', 'background-color': '#252525', 'padding': '20px',
                      'border-radius': '10px'})
        ], style={'max-width': '900px', 'margin': '0 auto', 'margin-bottom': '50px'}),

        html.Div([
            html.H2("Gamma Exposure (GEX)", style={'color': '#00ffcc'}),
            html.P(
                "Gamma Exposure (GEX) измеряет, насколько маркет-мейкерам необходимо хеджировать свои позиции по опционам. Положительный GEX означает, что маркет-мейкеры придерживаются длинных позиций по гамме и стремятся стабилизировать рынок, покупая на падениях и продавая на подъеме. Отрицательный GEX означает, что у них короткая гамма и они могут усугубить движение рынка."),

            html.H3("Ключевые понятия:", style={'color': '#00ffcc'}),
            html.Ul([
                html.Li(html.Strong("Positive GEX:"), " Market makers are stabilizing forces (buy low, sell high)"),
                html.Li(html.Strong("Negative GEX:"), " Market makers amplify moves (buy high, sell low)"),
                html.Li(html.Strong("GEX Flip Zones:"), " Where gamma changes from positive to negative or vice versa"),
                html.Li(html.Strong("OI, Volume:"),
                        " Price where most options expire worthless (often acts as magnet)"),
                html.Li(html.Strong("AG (Absolute Gamma):"), " Total gamma regardless of direction (shows key levels)")
            ], style={'color': 'white'}),

            html.H2("Базовые рекомендации", style={'color': '#00ffcc'}),

            html.H3("1. Positive GEX", style={'color': '#ab47bc'}),
            html.P("Когда GEX сильно позитивен:"),
            html.Ul([
                html.Li("Ожидается выкуп просадок и продажи у сопротивлений"),
                html.Li("Ищите поддержку на AG, High Put Volume, High Put OI strikes"),
                html.Li(
                    "Сопртивлением часто выступает Max Positive GEX, High Call Volume strikes, High Call OI strikes"),
                html.Li("VWAP имеет тенденцию выступать в качестве сильной поддержки / сопротивления")
            ], style={'color': 'white'}),

            html.H3("2. Negative GEX", style={'color': '#ab47bc'}),
            html.P("Когда GEX сильно негативен:"),
            html.Ul([
                html.Li("Ожидайте движений, следующих за трендом (momentum)"),
                html.Li("Прорывы вниз, скорее всего, продолжатся"),
                html.Li("Следите за усиливающимися действиями дилеров по хеджированию"),
                html.Li("Следите за VIX. Уход выше 30 может свидетельствовать о панике")
            ], style={'color': 'white'}),

            html.H3("3. GEX Flip Zones", style={'color': '#ab47bc'}),
            html.P("Это критические уровни, на которых гамма меняет значения:"),
            html.Ul([
                html.Li("Этот уровень всегда является мощной поддержкой / сопротивлением"),
                html.Li(
                    "Если происходит пробой, то в основном он не будет ложным и движение может ускориться в направлении пробоя"),
            ], style={'color': 'white'}),

            html.H2("Практические советы по торговле", style={'color': '#00ffcc'}),
            html.Ol([
                html.Li("Сочетайте GEX с VWAP - лонги от VWAP в позитивной среде GEX имеют высокую вероятность"),
                html.Li(
                    "Следите за сочетанием уровней - когда несколько индикаторов указывают на один и тот же уровень (GEX + OI + объем + AG), это усиливает его, делая либо магнитом, либо мощной поддержкой / сопротивлением"),
                html.Li(
                    "При положительном GEX старайтесь продавать на подъеме у сопротивления, покупать на падении у поддержки"),
                html.Li(
                    "При отрицательном GEX работайте в направлении нисходящего импульса, но будьте готовы к быстрому выходу"),
                html.Li("Следите за изменениями GEX в течение дня, особенно вокруг ключевых технических уровней")
            ], style={'color': 'white'}),

            html.H2("Распространенные ошибки", style={'color': '#00ffcc'}),
            html.Ul([
                html.Li(
                    "Торговля против гаммы (например, покупка при отрицательном GEX). Тут, для лонгов, нужно дожидаться окончания снижения и минимум возврат цены выше VWAP. Помните: при отрицательном GEX маркет-мейкеры продают в падающий рынок и если паника усиливается, то даже крепкие поддержки (High Put Vol, High AG и т.д) могут не удержать цену"),
                html.Li("Игнорирование G-Flip zone, когда она совпадает с техническими уровнями"),
                html.Li(
                    "Игнорирование внешнего фона / фундаментала / ключевых событий (Даже если цена находится в положительном GEX в начале / середине дня, это не означает, что к концу дня не может поступить негативный фундаментальный / новостной триггер)"),
                html.Li(
                    "Игнорирование прочего фундаментального / технического анализа. Например, если падение идет несколько дней, а цена находится в глубоких отрицательных значениях GEX - это не повод шортить на всё, т.к. критическая перепроданность RSI или S5FI и т.д. могут остановить от дальнейшего падения")
            ], style={'color': 'white'}),

            html.Div([
                html.H3("Пример простой сделки", style={'color': '#00ffcc'}),
                html.P(
                    "Сценарий: SPX в сильной положительной среде GEX: Лонг от VWAP, либо от поддержки на уровне max AG:"),
                html.Ul([
                    html.Li("Вход: Покупка на уровне VWAP или поддержки AG"),
                    html.Li("Стоп: Ниже ближайшего кластера Put OI, либо кластера Put Vol"),
                    html.Li("Цель: Следующий уровень сопротивления"),
                    html.Li(
                        "Управление: Масштабирование (сокращение) позиции по мере приближения цены к уровню сопротивления")
                ], style={'color': 'white'})
            ], style={'margin-top': '20px', 'padding': '15px', 'background-color': '#252525', 'border-radius': '10px'}),

            html.Div([
                html.H3("Ключевые показатели, за которыми следует следить", style={'color': '#00ffcc'}),
                html.Table([
                    html.Tr([
                        html.Th("Indicator", style={'text-align': 'left'}),
                        html.Th("Bullish Signal", style={'text-align': 'left'}),
                        html.Th("Bearish Signal", style={'text-align': 'left'})
                    ]),
                    html.Tr([
                        html.Td("Net GEX"),
                        html.Td("Преобладают положительные значения"),
                        html.Td("Преобладают отрицательные значения")
                    ]),
                    html.Tr([
                        html.Td("AG"),
                        html.Td("Преобладает выше цены"),
                        html.Td("Преобладает ниже цены")
                    ]),
                    html.Tr([
                        html.Td("P/C Ratio"),
                        html.Td("Ниже 0.8"),
                        html.Td("Выше 1.2")
                    ]),
                    html.Tr([
                        html.Td("Call Volume"),
                        html.Td("Call Vol больше Put Vol"),
                        html.Td("Call Vol меньше Put Vol")
                    ]),
                    html.Tr([
                        html.Td("Put Volume"),
                        html.Td("Put Vol меньше Call Vol"),
                        html.Td("Put Vol больше Call Vol")
                    ])
                ], style={'width': '100%', 'border-collapse': 'collapse', 'margin-top': '15px'})
            ], style={'margin-top': '30px'}),

            html.Div([
                html.H3("Помните:", style={'color': '#00ffcc'}),
                html.P("GEX - это всего лишь один из инструментов в вашем арсенале. Всегда сочетайте его с:"),
                html.Ul([
                    html.Li("Анализом динамики цен"),
                    html.Li("Профилем объемов"),
                    html.Li("Рыночным контекстом"),
                    html.Li("Управлением рисками")
                ], style={'color': 'white'})
            ], style={'margin-top': '30px', 'padding': '15px', 'background-color': '#252525', 'border-radius': '10px'})
        ], style={
            'max-width': '900px',
            'margin': '0 auto',
            'padding': '20px',
            'color': 'white',
            'line-height': '1.6'
        })
    ],
    style={
        'margin-left': '10%',
        'padding': '20px',
        'color': 'white'
    }
)

# Лейаут для страницы "Disclaimer"
disclaimer_page = html.Div(
    className='disclaimer-page',
    children=[
        html.H1("Disclaimer", style={'textAlign': 'center', 'color': 'white'}),

        html.Div([
            dcc.Markdown('''
            #### Информация на Max Power, содержащаяся на этом и/или связанных с ним веб-продуктах, не является индивидуальной рекомендацией, и носит исключительно информационный характер и не должна рассматриваться как предложение, либо рекомендация к инвестированию, покупке, продаже какого-либо актива, торговых операций по финансовым инструментам. 
            #### Администрация Проекта оставляет за собой право изменять и обновлять содержание материалов информационного ресурса и других документов, не уведомляя об этом пользователей.


            ### 1. Никаких рекомендаций по инвестированию
            Контент на этой платформе не предназначен и не является финансовым советом, инвестиционным советом, торговым советом или каким-либо другим советом. Предоставленная информация не должна использоваться в качестве единственной основы для принятия инвестиционных решений.

            ### 2. Информация о рисках
            Торговля и инвестирование сопряжены со значительным риском потерь и подходят не каждому инвестору. Вам следует тщательно взвесить свои инвестиционные цели, уровень опыта и склонность к риску, прежде чем принимать какие-либо инвестиционные решения.

            ### 3. Отсутствие гарантий
            Мы не гарантируем эффективность или применимость каких-либо стратегий или предоставленной информации. Прошлые результаты не являются показателем будущих результатов.

            ### 4. Сторонний контент
            Наша платформа содержит ссылки на сторонние веб-сайты или контент. Мы не подтверждаем и не несем ответственности за точность таких материалов третьих лиц. 

            ### 5. Ограничение ответственности
            Max Power не несет ответственности за какие-либо прямые, косвенные, опосредованные или случайные убытки, возникающие в результате или в связи с использованием вами этой платформы. 

            ### 6. Точность данных
            Хотя мы стремимся предоставлять точные рыночные данные, мы не можем гарантировать точность информации, полученной из сторонних источников, таких как Yahoo Finance и т.д..

            ### 7. Только для информационных целей
            Данная платформа предназначена исключительно для информационных целей и не должна рассматриваться как рекомендация к покупке или продаже какого-либо финансового инструмента. Используя эту платформу, вы подтверждаете, что прочитали, поняли и соглашаетесь соблюдать настоящий отказ от ответственности.

            Используя эту платформу, вы подтверждаете, что прочитали, поняли и соглашаетесь соблюдать настоящий отказ от ответственности.
            ''',
                         style={
                             'color': 'white',
                             'line-height': '1.6',
                             'padding': '20px',
                             'background-color': '#252525',
                             'boxShadow': '0 4px 10px rgba(0, 0, 0, 0.3)',
                             'border-radius': '10px',
                             'margin-top': '20px'
                         })
        ], style={
            'max-width': '800px',
            'margin': '0 auto',
            'padding': '20px'
        })
    ],
    style={
        'margin-left': '10%',
        'padding': '20px',
        'color': 'white'
    }
)

# Лейаут для объединенной страницы
app.layout = html.Div([
    dcc.Store(id='username-store', storage_type='local'),
    dcc.Store(id='auth-status', storage_type='local', data=False),

    # Блок для ввода имени пользователя (отображается только до авторизации)
    html.Div(id='login-container', children=[
        html.Label("Введите ваше имя пользователя Telegram:"),
        dcc.Input(id='username-input', type='text', placeholder='@username', className='dash-input'),
        html.Button('Проверить', id='submit-button', n_clicks=0, className='dash-button'),
        html.Div(id='access-message', style={'margin-top': '10px'})
    ], className='dash-container'),

    # Основной контент (отображается только после авторизации)
    html.Div(id='main-content', style={'display': 'none'}, children=[
        # Левая панель навигации
        html.Div([
            html.Div([
                dcc.Link(
                    html.H2("Max Power", style={'color': 'white', 'cursor': 'pointer'}),
                    href="/",
                    style={'text-decoration': 'none'}
                ),
                html.Hr(),
                html.Ul([
                    html.Li(dcc.Link("Key Levels", href="/key-levels",
                                     style={'color': 'white', 'text-decoration': 'none'})),
                    html.Li(style={'height': '20px'}),  # Добавляем пустой элемент для отступа
                    html.Li(dcc.Link("P/C Ratio", href="/options-summary",
                                     style={'color': 'white', 'text-decoration': 'none'})),
                    html.Li(style={'height': '20px'}),  # Добавляем пустой элемент для отступа
                    html.Li(dcc.Link("How to use GEX", href="/how-to-use-gex",
                                     style={'color': 'white', 'text-decoration': 'none'})),
                    html.Li(style={'height': '20px'}),  # Добавляем пустой элемент для отступа
                ], style={'list-style-type': 'none', 'padding': '0'}),

                # Добавляем Disclaimer внизу с дополнительным отступом
                html.Div([
                    html.Hr(),
                    html.Ul([
                        html.Li(dcc.Link("Disclaimer", href="/disclaimer",
                                         style={'color': 'gray', 'text-decoration': 'none', 'font-size': '20px'}))
                    ], style={'list-style-type': 'none', 'padding': '0', 'margin-top': '20px'})
                ], style={'position': 'absolute', 'bottom': '20px', 'width': '80%'})
            ], style={'padding': '20px', 'height': '100%', 'position': 'relative'})
        ], style={'width': '10%', 'height': '98vh', 'background-color': '#191919',
                  'position': 'fixed', 'left': '0', 'top': '0'}),

        # Основной контент страницы
        html.Div([
            dcc.Location(id='url', refresh=False),
            html.Div(id='page-content')
        ], style={'margin-left': '10%', 'padding': '20px'})
    ])
])

# Лейаут для главной страницы
index_page = html.Div([
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

    dcc.Store(id='selected-params', data=['Net GEX']),
    dcc.Store(id='options-data-store'),

    dcc.Graph(
        id='options-chart',
        style={'height': '900px', 'border-radius': '12px',
               'box-shadow': '0 4px 10px rgba(0, 0, 0, 0.3)',
               'overflow': 'hidden',
               'background-color': '#1e1e1e',
               'padding': '10px',
               'margin-bottom': '20px'},
        config={
            'displayModeBar': False,
            'scrollZoom': False,
            'dragmode': False
        }
    ),

    dcc.Graph(
        id='price-chart',
        style={'height': '950px', 'border-radius': '12px',
               'box-shadow': '0 4px 10px rgba(0, 0, 0, 0.3)',
               'overflow': 'hidden',
               'background-color': '#1e1e1e',
               'padding': '10px',
               'margin-bottom': '20px'},
        config={
            'displayModeBar': False,
            'scrollZoom': False,
            'dragmode': False
        }
    ),
    dcc.Graph(
        id='price-chart-simplified',
        style={'height': '950px', 'border-radius': '12px',
               'box-shadow': '0 4px 10px rgba(0, 0, 0, 0.3)',
               'overflow': 'hidden',
               'background-color': '#1e1e1e',
               'padding': '10px',
               'margin-bottom': '20px'},
        config={
            'displayModeBar': False,
            'scrollZoom': False,
            'dragmode': False
        }
    )
])

# Лейаут для страницы "Key Levels"
key_levels_page = html.Div(
    className='key-levels-page',
    children=[
        html.H1("Key Levels", style={'textAlign': 'center', 'color': 'white'}),

        html.Div([
            html.Label("Введите тикер актива:", style={'color': 'white'}),
            dcc.Input(id='ticker-input-key-levels', type='text', value='SPX', className='dash-input'),
        ], className='dash-container'),

        html.Div(
            dcc.Graph(
                id='key-levels-chart',
                style={'height': '900px'},
                config={
                    'displayModeBar': False,
                    'scrollZoom': False,
                    'dragmode': False
                }
            ),
            className='graph-container'
        ),

        # Добавляем блок с прогнозом
        html.Div(
            id='market-forecast',
            style={
                'box-shadow': '0 4px 10px rgba(0, 0, 0, 0.3)',
                'background-color': '#1e1e1e',
                'padding': '20px',
                'border-radius': '12px',
                'margin-top': '20px',
                'color': 'white'
            },
            children=[
                html.H3("", style={'color': 'white'}),
                html.Div(id='forecast-text', style={'margin-top': '10px'})
            ]
        )
    ]
)


# Добавляем новый callback для прогноза
@app.callback(
    Output('forecast-text', 'children'),
    [Input('ticker-input-key-levels', 'value')]
)
def update_forecast(ticker):
    ticker = normalize_ticker(ticker)
    stock = yf.Ticker(ticker)

    # Получаем данные по ценам
    try:
        hist = stock.history(period='3mo', interval='1d')
        intraday_hist = stock.history(period='1d', interval='1m')
        if hist.empty or intraday_hist.empty:
            return html.Div("Нет данных для анализа", style={'color': 'white'})

        current_price = intraday_hist['Close'].iloc[-1]
        vwap = (intraday_hist['Volume'] * (
                intraday_hist['High'] + intraday_hist['Low'] + intraday_hist['Close']) / 3).sum() / intraday_hist[
                   'Volume'].sum()
        current_volume = intraday_hist['Volume'].iloc[-1]
        avg_volume = intraday_hist['Volume'].mean()
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return html.Div("Ошибка загрузки ценовых данных", style={'color': 'white'})

    # Технические индикаторы
    hist['MA20'] = hist['Close'].rolling(window=20).mean()
    hist['MA50'] = hist['Close'].rolling(window=50).mean()
    hist['MA200'] = hist['Close'].rolling(window=200).mean()

    # RSI расчет
    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    # Получаем данные по опционам
    options_data, _, spot_price, _ = get_option_data(ticker, [])
    if options_data is None or options_data.empty:
        return html.Div("Нет данных по опционам для анализа", style={'color': 'white'})

    # Рассчитываем технические уровни
    price_range = 0.02 if ticker in ["^SPX", "^NDX", "^RUT", "^DJI"] else 0.05
    lower_limit = current_price * (1 - price_range)
    upper_limit = current_price * (1 + price_range)
    filtered_data = options_data[(options_data['strike'] >= lower_limit) & (options_data['strike'] <= upper_limit)]

    if filtered_data.empty:
        return html.Div("Недостаточно данных в ценовом диапазоне", style={'color': 'white'})

    # Ключевые уровни
    max_call_vol_strike = filtered_data.loc[filtered_data['Call Volume'].idxmax(), 'strike']
    max_put_vol_strike = filtered_data.loc[filtered_data['Put Volume'].idxmax(), 'strike']
    max_neg_gex_strike = filtered_data.loc[filtered_data['Net GEX'].idxmin(), 'strike']
    max_pos_gex_strike = filtered_data.loc[filtered_data['Net GEX'].idxmax(), 'strike']
    max_ag_strike = filtered_data.loc[filtered_data['AG'].idxmax(), 'strike']
    max_call_oi_strike = filtered_data.loc[filtered_data['Call OI'].idxmax(), 'strike']
    max_put_oi_strike = filtered_data.loc[filtered_data['Put OI'].idxmax(), 'strike']

    # Находим G-Flip зону
    g_flip_zone = None
    gex_values = filtered_data['Net GEX'].values
    for i in range(len(gex_values) - 6):
        if gex_values[i] > 0 and all(gex_values[i + j] < 0 for j in range(1, 7)):
            g_flip_zone = filtered_data.iloc[i]['strike']
            break

    # Рассчитываем P/C Ratio и объемы
    total_call_oi = options_data['Call OI'].sum()
    total_put_oi = options_data['Put OI'].sum()
    pc_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else float('inf')

    call_volume = filtered_data['Call Volume'].sum()
    put_volume = filtered_data['Put Volume'].sum()
    volume_ratio = put_volume / call_volume if call_volume > 0 else float('inf')

    # Статус Net GEX
    net_gex_status = "положительный" if filtered_data['Net GEX'].sum() > 0 else "отрицательный"

    # Проверяем рыночный фон
    bullish_background = bearish_background = False
    if current_price:
        strikes_below = filtered_data[filtered_data['strike'] < current_price].sort_values('strike', ascending=False)
        strikes_above = filtered_data[filtered_data['strike'] > current_price].sort_values('strike')

        # Бычий фон (положительный GEX вокруг цены)
        pos_gex_below = sum(strikes_below['Net GEX'].head(3) > 0)
        pos_gex_above = sum(strikes_above['Net GEX'].head(3) > 0)
        bullish_background = pos_gex_below >= 3 and pos_gex_above >= 3

        # Медвежий фон (отрицательный GEX вокруг цены)
        neg_gex_below = sum(strikes_below['Net GEX'].head(3) < 0)
        neg_gex_above = sum(strikes_above['Net GEX'].head(3) < 0)
        bearish_background = neg_gex_below >= 3 and neg_gex_above >= 3

    # Функция для расчета вероятности отскока/пробоя
    def calculate_probability(strike, direction):
        factors = []
        weights = {
            'max_ag': 30,
            'max_gex': 30,
            'max_vol': 20,
            'g_flip': 20,
            'max_oi': 15,
            'vwap': 10,
            'ma': 10,
            'rsi': 5
        }

        # Проверяем технические факторы
        if abs(strike - max_ag_strike) <= 0.01 * strike:
            factors.append(('max_ag', weights['max_ag']))
        if direction == "support" and abs(strike - max_neg_gex_strike) <= 0.01 * strike:
            factors.append(('max_gex', weights['max_gex']))
        if direction == "resistance" and abs(strike - max_pos_gex_strike) <= 0.01 * strike:
            factors.append(('max_gex', weights['max_gex']))
        if direction == "support" and abs(strike - max_put_vol_strike) <= 0.01 * strike:
            factors.append(('max_vol', weights['max_vol']))
        if direction == "resistance" and abs(strike - max_call_vol_strike) <= 0.01 * strike:
            factors.append(('max_vol', weights['max_vol']))
        if g_flip_zone and abs(strike - g_flip_zone) <= 0.01 * strike:
            factors.append(('g_flip', weights['g_flip']))
        if direction == "support" and abs(strike - max_put_oi_strike) <= 0.01 * strike:
            factors.append(('max_oi', weights['max_oi']))
        if direction == "resistance" and abs(strike - max_call_oi_strike) <= 0.01 * strike:
            factors.append(('max_oi', weights['max_oi']))

        # Добавляем технические индикаторы
        if abs(strike - vwap) <= 0.005 * strike:
            factors.append(('vwap', weights['vwap']))
        for ma in [hist['MA20'].iloc[-1], hist['MA50'].iloc[-1], hist['MA200'].iloc[-1]]:
            if abs(strike - ma) <= 0.005 * strike:
                factors.append(('ma', weights['ma']))
                break

        # Учитываем RSI
        if (direction == "support" and current_rsi < 30) or (direction == "resistance" and current_rsi > 70):
            factors.append(('rsi', weights['rsi']))

        # Ограничиваем максимальную вероятность 95%
        probability = min(95, sum(f[1] for f in factors))
        return probability, factors

    # Формируем прогноз
    forecast = []

    # 1. Основные данные (обновленный заголовок)
    forecast.append(html.H4(f"📊 Расширенный анализ опционного рынка: {ticker}",
                            style={'color': '#00ffcc', 'text-align': 'left', 'margin-bottom': '15px'}))

    # Информационная панель
    info_panel = [
        html.Div([
            html.Div([
                html.P("Текущая цена:", style={'color': 'white'}),
                html.P(f"{current_price:.2f}", style={'color': 'white', 'font-weight': 'bold'})
            ], style={'display': 'flex', 'justify-content': 'space-between'}),

            html.Div([
                html.P("VWAP:", style={'color': 'white'}),
                html.P(f"{vwap:.2f}", style={'color': 'white', 'font-weight': 'bold'})
            ], style={'display': 'flex', 'justify-content': 'space-between'}),

            html.Div([
                html.P("Объем:", style={'color': 'white'}),
                html.P(f"{current_volume:,.0f} ({(current_volume / avg_volume) * 100:.0f}% от среднего)",
                       style={'color': 'green' if current_volume > avg_volume else 'red', 'font-weight': 'bold'})
            ], style={'display': 'flex', 'justify-content': 'space-between'}),

            html.Div([
                html.P("RSI (14):", style={'color': 'white'}),
                html.P(f"{current_rsi:.1f}",
                       style={'color': 'red' if current_rsi > 70 else 'green' if current_rsi < 30 else 'white',
                              'font-weight': 'bold'})
            ], style={'display': 'flex', 'justify-content': 'space-between'}),

            html.Div([
                html.P("P/C Ratio:", style={'color': 'white'}),
                html.P(f"{pc_ratio:.2f}",
                       style={'color': 'red' if pc_ratio > 1.3 else 'green' if pc_ratio < 0.7 else 'white',
                              'font-weight': 'bold'})
            ], style={'display': 'flex', 'justify-content': 'space-between'}),

            html.Div([
                html.P("Net GEX:", style={'color': 'white'}),
                html.P(f"{filtered_data['Net GEX'].sum():,.0f}",
                       style={'color': 'green' if filtered_data['Net GEX'].sum() > 0 else 'red',
                              'font-weight': 'bold'})
            ], style={'display': 'flex', 'justify-content': 'space-between'}),
        ], style={
            'background-color': '#252525',
            'padding': '15px',
            'border-radius': '10px',
            'margin-bottom': '20px'
        })
    ]

    forecast.extend(info_panel)

    # 2. Определение рыночного сценария
    market_context = []
    if bullish_background:
        market_context.append(html.Div([
            html.H4("📈 СИЛЬНЫЙ БЫЧИЙ ФОН",
                    style={'color': 'lightgreen', 'text-align': 'center', 'margin-bottom': '10px'}),
            html.P("🔹 Цена окружена положительными значениями GEX", style={'color': 'lightgreen'}),
            html.P("🔹 Маркет-мейкеры выступают стабилизаторами рынка", style={'color': 'lightgreen'}),
            html.P("🔹 Коррекции вероятно будут ограниченными", style={'color': 'lightgreen'})
        ], style={
            'background-color': 'rgba(0, 255, 0, 0.1)',
            'padding': '15px',
            'border-radius': '10px',
            'border-left': '5px solid lightgreen',
            'margin-bottom': '20px'
        }))
    elif bearish_background:
        market_context.append(html.Div([
            html.H4("📉 СИЛЬНЫЙ МЕДВЕЖИЙ ФОН",
                    style={'color': 'salmon', 'text-align': 'center', 'margin-bottom': '10px'}),
            html.P("🔹 Цена окружена отрицательными значениями GEX", style={'color': 'salmon'}),
            html.P("🔹 Маркет-мейкеры усиливают волатильность", style={'color': 'salmon'}),
            html.P("🔹 Вероятны резкие движения и проскальзывания", style={'color': 'salmon'})
        ], style={
            'background-color': 'rgba(255, 0, 0, 0.1)',
            'padding': '15px',
            'border-radius': '10px',
            'border-left': '5px solid salmon',
            'margin-bottom': '20px'
        }))
    else:
        market_context.append(html.Div([
            html.H4("🔄 НЕЙТРАЛЬНЫЙ/КОНСОЛИДАЦИОННЫЙ СЦЕНАРИЙ",
                    style={'color': 'yellow', 'text-align': 'center', 'margin-bottom': '10px'}),
            html.P("🔹 GEX не показывает четкого направления", style={'color': 'yellow'}),
            html.P("🔹 Вероятна торговля в диапазоне", style={'color': 'yellow'}),
            html.P("🔹 Ищите пробои с подтверждением объема", style={'color': 'yellow'})
        ], style={
            'background-color': 'rgba(255, 255, 0, 0.1)',
            'padding': '15px',
            'border-radius': '10px',
            'border-left': '5px solid yellow',
            'margin-bottom': '20px'
        }))

    forecast.extend(market_context)

    # 3. Анализ ключевых уровней
    levels_analysis = []

    # Определяем ключевые уровни
    support_levels = []
    resistance_levels = []

    # Уровни поддержки
    if max_put_vol_strike < current_price:
        support_levels.append(('Объем путов', max_put_vol_strike))
    if max_neg_gex_strike < current_price:
        support_levels.append(('Отриц. GEX', max_neg_gex_strike))
    if max_ag_strike < current_price:
        support_levels.append(('AG', max_ag_strike))
    if max_put_oi_strike < current_price:
        support_levels.append(('OI путов', max_put_oi_strike))

    # Уровни сопротивления
    if max_call_vol_strike > current_price:
        resistance_levels.append(('Объем коллов', max_call_vol_strike))
    if max_pos_gex_strike > current_price:
        resistance_levels.append(('Поз. GEX', max_pos_gex_strike))
    if max_ag_strike > current_price:
        resistance_levels.append(('AG', max_ag_strike))
    if max_call_oi_strike > current_price:
        resistance_levels.append(('OI коллов', max_call_oi_strike))

    # G-Flip зона
    if g_flip_zone:
        if g_flip_zone > current_price:
            resistance_levels.append(('G-Flip', g_flip_zone))
        else:
            support_levels.append(('G-Flip', g_flip_zone))

    # Группируем уровни поддержки по цене
    support_groups = {}
    for level in support_levels:
        price = level[1]
        if price not in support_groups:
            support_groups[price] = []
        support_groups[price].append(level)

    # Группируем уровни сопротивления по цене
    resistance_groups = {}
    for level in resistance_levels:
        price = level[1]
        if price not in resistance_groups:
            resistance_groups[price] = []
        resistance_groups[price].append(level)

    # Функция для форматирования уровней
    def format_level_groups(level_groups, level_type):
        formatted = []
        for price in sorted(level_groups.keys(), key=lambda x: abs(current_price - x)):
            levels = level_groups[price]
            prob, factors = calculate_probability(price, level_type)

            # Определяем цвет в зависимости от типа уровня
            if level_type == "support":
                color = '#02d432'  # Зеленый для поддержек
                prob_text = "отскока"
                level_name = "поддержка"
            else:
                color = '#f32d35'  # Красный для сопротивлений
                prob_text = "отбоя"
                level_name = "сопротивление"

            # Собираем названия параметров
            param_names = [level[0] for level in levels]

            # Определяем силу уровня
            if prob > 70:
                strength = "💪 Сильное"
                strength_desc = "Высокая вероятность"
            elif prob > 40:
                strength = "🆗 Среднее"
                strength_desc = "Умеренная вероятность"
            else:
                strength = "⚠️ Слабое"
                strength_desc = "Низкая вероятность"

            # Формируем основной текст
            main_text = f"{strength} {level_name} на {price:.2f}: {strength_desc} {prob_text} ({prob}%)"

            # Формируем список параметров
            params_text = "Подтверждается: " + ", ".join(param_names)

            # Формируем факторы
            factors_text = "📌 Ключевые факторы: " + ", ".join(sorted(list(set([f[0] for f in factors]))))

            formatted.append(html.Div([
                html.Div([
                    html.Span(main_text, style={'color': color, 'font-weight': 'bold'}),
                ], style={'margin-bottom': '5px'}),

                html.Div(params_text, style={'color': 'white', 'margin-left': '20px', 'margin-bottom': '5px'}),

                html.Div(factors_text, style={'color': 'lightblue', 'margin-left': '20px', 'margin-bottom': '15px'})
            ], style={
                'background-color': '#252525',
                'padding': '10px',
                'border-radius': '5px',
                'margin-bottom': '10px',
                'border-left': f'3px solid {color}'
            }))

        return formatted

    # Добавляем поддержки
    if support_groups:
        levels_analysis.append(html.H5("📉 КЛЮЧЕВЫЕ ПОДДЕРЖКИ:",
                                       style={'color': 'white', 'margin-top': '20px'}))
        levels_analysis.extend(format_level_groups(support_groups, "support"))

    # Добавляем сопротивления
    if resistance_groups:
        levels_analysis.append(html.H5("📈 КЛЮЧЕВЫЕ СОПРОТИВЛЕНИЯ:",
                                       style={'color': 'white', 'margin-top': '20px'}))
        levels_analysis.extend(format_level_groups(resistance_groups, "resistance"))

    forecast.extend(levels_analysis)

    # 4. Торговые идеи (обновленная логика)
    trading_ideas = []
    trading_ideas.append(html.H5("💡 ВАРИАНТЫ:", style={'color': 'white', 'margin-top': '30px'}))

    def generate_trading_idea(price, level_type, prob, confirmations):
        idea = []
        color = 'lightgreen' if level_type == "support" else 'salmon'
        emoji = "🟢" if level_type == "support" else "🔴"

        if prob > 70:  # Сильный уровень - торгуем отскок/отбой
            if level_type == "support":
                idea.append(html.P(f"{emoji} Длинные позиции на отскоке от поддержки:",
                                   style={'color': color, 'font-weight': 'bold'}))
                idea.append(html.P(f"• Покупайте при отскоке от {price:.2f} с подтверждением",
                                   style={'color': 'white'}))
            else:
                idea.append(html.P(f"{emoji} Короткие позиции на отбое от сопротивления:",
                                   style={'color': color, 'font-weight': 'bold'}))
                idea.append(html.P(f"• Продавайте при отбое от {price:.2f} с подтверждением",
                                   style={'color': 'white'}))

            idea.append(html.P(f"• Вероятность {'отскока' if level_type == 'support' else 'отбоя'}: {prob}%",
                               style={'color': color}))
            idea.append(html.P(f"• Подтверждающие факторы: {', '.join(confirmations)}",
                               style={'color': 'white'}))
            idea.append(html.P(f"• Стоп-лосс: {'ниже' if level_type == 'support' else 'выше'} уровня",
                               style={'color': 'white'}))
            idea.append(html.P(f"• Цели: ближайшие {'сопротивления' if level_type == 'support' else 'поддержки'}",
                               style={'color': 'white'}))
        else:  # Слабый уровень - торгуем пробой
            if level_type == "support":
                idea.append(html.P(f"🔴 Короткие позиции на пробое поддержки:",
                                   style={'color': 'salmon', 'font-weight': 'bold'}))
                idea.append(html.P(f"• Продавайте при пробое {price:.2f} с объемом",
                                   style={'color': 'white'}))
            else:
                idea.append(html.P(f"🟢 Длинные позиции на пробое сопротивления:",
                                   style={'color': 'lightgreen', 'font-weight': 'bold'}))
                idea.append(html.P(f"• Покупайте при пробое {price:.2f} с объемом",
                                   style={'color': 'white'}))

            idea.append(html.P(f"• Вероятность продолжения: {100 - prob}%",
                               style={'color': 'lightgreen' if level_type == 'resistance' else 'salmon'}))
            idea.append(html.P("• Ищите подтверждение на меньших таймфреймах",
                               style={'color': 'white'}))
            idea.append(
                html.P(f"• Цели: следующие уровни {'поддержки' if level_type == 'support' else 'сопротивления'}",
                       style={'color': 'white'}))

        return html.Div(idea, style={
            'background-color': f'rgba({0 if color == "lightgreen" else 255}, {255 if color == "lightgreen" else 0}, 0, 0.1)',
            'padding': '15px',
            'border-radius': '10px',
            'margin-bottom': '15px'
        })

    # Добавляем идеи для поддержек
    if support_groups:
        for price, levels in support_groups.items():
            prob, _ = calculate_probability(price, "support")
            confirmations = [level[0] for level in levels]
            trading_ideas.append(generate_trading_idea(price, "support", prob, confirmations))

    # Добавляем идеи для сопротивлений
    if resistance_groups:
        for price, levels in resistance_groups.items():
            prob, _ = calculate_probability(price, "resistance")
            confirmations = [level[0] for level in levels]
            trading_ideas.append(generate_trading_idea(price, "resistance", prob, confirmations))

    # Общие рекомендации для нейтрального рынка
    if not bullish_background and not bearish_background:
        trading_ideas.append(html.Div([
            html.P("🟡 Торговля в диапазоне:", style={'color': 'yellow', 'font-weight': 'bold'}),
            html.P("• Покупайте у подтвержденных поддержек, продавайте у подтвержденных сопротивлений",
                   style={'color': 'white'}),
            html.P("• Используйте лимитные ордера для входа в зонах уровней", style={'color': 'white'}),
            html.P("• Уменьшите размер позиции на 30-50% из-за неопределенности", style={'color': 'white'}),
            html.P("• Ищите ложные пробои для лучших входов", style={'color': 'white'})
        ], style={
            'background-color': 'rgba(255, 255, 0, 0.1)',
            'padding': '15px',
            'border-radius': '10px',
            'margin-bottom': '15px'
        }))

    forecast.extend(trading_ideas)

    # 5. Управление рисками
    risk_management = []
    risk_management.append(html.H5("⚠️ УПРАВЛЕНИЕ РИСКАМИ:", style={'color': 'white', 'margin-top': '30px'}))

    risk_management.append(html.Div([
        html.P("🔹 Размер позиции:", style={'color': 'white', 'font-weight': 'bold'}),
        html.P("• Рискуйте не более 1-2% капитала на сделку", style={'color': 'white'}),
        html.P("• Уменьшайте размер в условиях высокой волатильности", style={'color': 'white'}),

        html.P("🔹 Стоп-лосс:", style={'color': 'white', 'font-weight': 'bold', 'margin-top': '10px'}),
        html.P(f"• Для длинных позиций: ниже ближайшей поддержки ({min(support_groups.keys()):.2f} при наличии)"
               if support_groups else "• Для длинных позиций: 1-2% ниже точки входа", style={'color': 'white'}),
        html.P(
            f"• Для коротких позиций: выше ближайшего сопротивления ({min(resistance_groups.keys()):.2f} при наличии)"
            if resistance_groups else "• Для коротких позиций: 1-2% выше точки входа", style={'color': 'white'}),

        html.P("🔹 Тейк-профит:", style={'color': 'white', 'font-weight': 'bold', 'margin-top': '10px'}),
        html.P("• Фиксируйте часть прибыли у ключевых уровней", style={'color': 'white'}),
        html.P("• Используйте трейлинг-стоп после достижения первой цели", style={'color': 'white'}),

        html.P("🔹 Психология:", style={'color': 'white', 'font-weight': 'bold', 'margin-top': '10px'}),
        html.P("• Избегайте сделок под влиянием эмоций", style={'color': 'white'}),
        html.P("• Придерживайтесь торгового плана", style={'color': 'white'}),
        html.P("• Анализируйте каждую сделку", style={'color': 'white'})
    ], style={
        'background-color': '#252525',
        'padding': '15px',
        'border-radius': '10px',
        'margin-bottom': '20px'
    }))

    forecast.extend(risk_management)

    # 6. Дополнительные инсайты
    insights = []
    insights.append(html.H5("🔍 ДОПОЛНИТЕЛЬНЫЕ ИНСАЙТЫ:", style={'color': 'white', 'margin-top': '30px'}))

    # Анализ объема
    volume_analysis = ""
    if current_volume > avg_volume * 1.5:
        volume_analysis = "🔹 Высокий объем: возможен сильный импульс в направлении пробоя"
    elif current_volume < avg_volume * 0.7:
        volume_analysis = "🔹 Низкий объем: осторожность - возможны ложные пробои"
    else:
        volume_analysis = "🔹 Средний объем: подтверждайте сигналы дополнительными индикаторами"

    # Анализ RSI
    rsi_analysis = ""
    if current_rsi > 70:
        rsi_analysis = "🔹 RSI указывает на перекупленность - возможна коррекция"
    elif current_rsi < 30:
        rsi_analysis = "🔹 RSI указывает на перепроданность - возможен отскок"
    else:
        rsi_analysis = "🔹 RSI в нейтральной зоне - ищите другие подтверждения"

    # Анализ P/C Ratio
    pc_analysis = ""
    if pc_ratio > 1.3:
        pc_analysis = "🔹 Высокий P/C Ratio: рынок ожидает снижения"
    elif pc_ratio < 0.7:
        pc_analysis = "🔹 Низкий P/C Ratio: рынок ожидает роста"
    else:
        pc_analysis = "🔹 Нейтральный P/C Ratio: нет четкого сигнала"

    insights.append(html.Div([
        html.P(volume_analysis, style={'color': 'white'}),
        html.P(rsi_analysis, style={'color': 'white'}),
        html.P(pc_analysis, style={'color': 'white'})
    ], style={
        'background-color': '#252525',
        'padding': '15px',
        'border-radius': '10px',
        'margin-bottom': '20px'
    }))

    forecast.extend(insights)

    return html.Div(forecast,
                    style={'color': 'white', 'padding': '20px', 'background-color': '#1e1e1e', 'border-radius': '10px'})


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
                "Доступ разрешен.",
                {'display': 'block'},
                {'display': 'none'},
                username,
                True
            )
        else:
            return (
                "Доступ запрещен.",
                {'display': 'none'},
                {'display': 'block'},
                None,
                False
            )
    elif stored_username and stored_username in ALLOWED_USERS and auth_status:
        return (
            "",
            {'display': 'block'},
            {'display': 'none'},
            stored_username,
            True
        )
    return (
        "",
        {'display': 'none'},
        {'display': 'block'},
        stored_username,
        auth_status
    )


# Callback для обновления списка дат
@app.callback(
    [Output('date-dropdown', 'options'), Output('date-dropdown', 'value')],
    [Input('ticker-input', 'value')]
)
def update_dates(ticker):
    ticker = normalize_ticker(ticker)
    _, available_dates, _, _ = get_option_data(ticker, [])
    print(f"Доступные даты: {available_dates}")
    if not available_dates:
        return [], []
    options = [{'label': date, 'value': date} for date in available_dates]
    return options, [available_dates[0]]


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


# Callback для обновления графика опционов (возвращаем оригинальную версию)
@app.callback(
    Output('options-chart', 'figure'),
    [Input('ticker-input', 'value'),
     Input('date-dropdown', 'value'),
     Input('selected-params', 'data')]
)
def update_options_chart(ticker, dates, selected_params):
    if not dates or not selected_params:
        return go.Figure()

    ticker = normalize_ticker(ticker)
    options_data, _, spot_price, max_ag_strike = get_option_data(ticker, dates)
    if options_data is None or options_data.empty:
        return go.Figure()

    fig = go.Figure()

    # Оригинальные параметры диапазона
    if ticker in ["^SPX", "^NDX", "^RUT", "^Dia"]:
        price_range = 0.023
    elif ticker in ["SPY", "QQQ", "DIA", "XSP", "IWM"]:
        price_range = 0.03
    elif ticker in ["^VIX"]:
        price_range = 0.5
    else:
        price_range = 0.12

    if spot_price:
        left_limit = spot_price - (spot_price * price_range)
        right_limit = spot_price + (spot_price * price_range)
        options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)
            ]
    else:
        left_limit = right_limit = 0

    # Оригинальная логика отображения параметров
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
                mode='lines+markers',
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#915bf8'),
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
                mode='lines+markers',
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#02d432'),
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
                mode='lines+markers',
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#f32d35'),
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
                mode='lines+markers',
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#003cfe'),
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
                mode='lines+markers',
                line=dict(shape='spline', smoothing=0.7),
                marker=dict(size=8, color='#e55f04'),
                fill='tozeroy',
                name="Put Volume",
                hovertext=hover_texts,
                hoverinfo="text",
                yaxis='y2'
            ))

    if spot_price:
        fig.add_vline(
            x=spot_price,
            line_dash="solid",
            line_color="orange",
            annotation_text=f"Price: {spot_price:.2f}",
            annotation_position="top",
            annotation_font=dict(color="orange"),
        )

    # Оригинальное оформление графика
    fig.update_layout(
        xaxis=dict(
            title="Strike",
            showgrid=False,
            zeroline=False,
            tickmode='array',
            tickvals=options_data['strike'].tolist(),
            tickformat='1',
            fixedrange=True
        ),
        yaxis=dict(
            title="Net GEX",
            side="left",
            showgrid=False,
            zeroline=False,
            fixedrange=True
        ),
        yaxis2=dict(
            title="",
            side="right",
            overlaying="y",
            showgrid=False,
            zeroline=False,
            fixedrange=True
        ),
        title="" + ticker,
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        dragmode=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Добавляем водяной знак
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        text="Max Power",
        showarrow=False,
        font=dict(size=80, color="rgba(255, 255, 255, 0.1)"),
        textangle=0,
    )

    return fig


@app.callback(
    Output('price-chart', 'figure'),
    [Input('ticker-input', 'value')]
)
def update_price_chart(ticker):
    ticker = normalize_ticker(ticker)
    interval = '1m'
    stock = yf.Ticker(ticker)
    data = stock.history(period='1d', interval=interval)

    if data.empty:
        return go.Figure()

    data['CumulativeVolume'] = data['Volume'].cumsum()
    data['CumulativePV'] = (data['Volume'] * (data['High'] + data['Low'] + data['Close']) / 3).cumsum()
    data['VWAP'] = data['CumulativePV'] / data['CumulativeVolume']

    options_data, _, spot_price, max_ag_strike = get_option_data(ticker, [])

    if ticker in ["^SPX", "^NDX", "^RUT", "^DJI", "SPY", "QQQ", "IWM"]:
        price_range = 0.023
    else:
        price_range = 0.05

    if spot_price:
        left_limit = spot_price - (spot_price * price_range)
        right_limit = spot_price + (spot_price * price_range)
        options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)
            ]
    else:
        left_limit = right_limit = 0

    if options_data is not None and not options_data.empty:
        visible_options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)
            ]
    else:
        visible_options_data = pd.DataFrame()

    if not visible_options_data.empty:
        max_ag_strike = visible_options_data.loc[visible_options_data['AG'].idxmax(), 'strike']

        # Проверяем наличие положительных значений Net GEX
        has_positive_gex = (visible_options_data['Net GEX'] > 0).any()
        if has_positive_gex:
            max_p1_strike = visible_options_data.loc[visible_options_data['Net GEX'].idxmax(), 'strike']
        else:
            max_p1_strike = None

        max_n1_strike = visible_options_data.loc[visible_options_data['Net GEX'].idxmin(), 'strike']
        max_call_vol_strike = visible_options_data.loc[visible_options_data['Call Volume'].idxmax(), 'strike']
        max_put_vol_strike = visible_options_data.loc[visible_options_data['Put Volume'].idxmax(), 'strike']
    else:
        max_ag_strike = None
        max_p1_strike = None
        max_n1_strike = None
        max_call_vol_strike = None
        max_put_vol_strike = None

    market_open_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_time = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
    current_time = datetime.now()

    line_widths = {
        'AG': 7,
        'P1': 5,
        'N1': 5,
        'Call Vol': 4,
        'Put Vol': 4,
        'Max Power': 3
    }

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name=""
    ))

    # Добавляем линию P1 только если есть положительные значения Net GEX
    if max_p1_strike is not None:
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time],
            y=[max_p1_strike, max_p1_strike],
            mode='lines',
            line=dict(color='#00ff00', width=line_widths['P1']),
            name=f'P1 Strike: {max_p1_strike:.2f}',
            yaxis='y'
        ))

    if max_n1_strike is not None:
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time],
            y=[max_n1_strike, max_n1_strike],
            mode='lines',
            line=dict(color='#ff0000', width=line_widths['N1']),
            name=f'N1 Strike: {max_n1_strike:.2f}',
            yaxis='y'
        ))

    if max_call_vol_strike is not None:
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time],
            y=[max_call_vol_strike, max_call_vol_strike],
            mode='lines',
            line=dict(color='#00a0ff', width=line_widths['Call Vol']),
            name=f'Call Vol Strike: {max_call_vol_strike:.2f}',
            yaxis='y'
        ))

    if max_put_vol_strike is not None:
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time],
            y=[max_put_vol_strike, max_put_vol_strike],
            mode='lines',
            line=dict(color='#ac5631', width=line_widths['Put Vol']),
            name=f'Put Vol Strike: {max_put_vol_strike:.2f}',
            yaxis='y'
        ))

    # Определяем Max Power Strike
    if current_time - market_open_time <= timedelta(minutes=45):
        max_power_strike = max_call_vol_strike if max_call_vol_strike is not None else max_put_vol_strike
    else:
        if max_ag_strike is not None:
            max_power_strike = max_ag_strike
        else:
            max_power_strike = max_call_vol_strike if max_call_vol_strike is not None else max_put_vol_strike

    if max_power_strike is not None:
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time],
            y=[max_power_strike, max_power_strike],
            mode='lines',
            line=dict(color='#ffdf00', width=line_widths['Max Power']),
            name=f'Max Power: {max_power_strike:.2f}',
            yaxis='y'
        ))

    if max_ag_strike is not None:
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time],
            y=[max_ag_strike, max_ag_strike],
            mode='lines',
            line=dict(color='#ab47bc', dash='dash', width=line_widths['AG']),
            name=f'AG Strike: {max_ag_strike:.2f}',
            yaxis='y'
        ))

    fig.update_layout(
        title=f"{ticker}",
        xaxis=dict(
            title="Время",
            type='date',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            rangeslider=dict(visible=False),
            autorange=False,
            range=[market_open_time, market_close_time],
            fixedrange=True
        ),
        yaxis=dict(
            title="Цена",
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            fixedrange=True
        ),
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        hovermode='x unified',
        margin=dict(l=50, r=50, b=50, t=50),
        dragmode=False
    )

    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        text="Max Power",
        showarrow=False,
        font=dict(size=80, color="rgba(255, 255, 255, 0.1)"),
        textangle=0,
    )

    return fig


# Callback для обновления нового графика цены
@app.callback(
    Output('price-chart-simplified', 'figure'),
    [Input('ticker-input', 'value')]
)
def update_price_chart_simplified(ticker):
    ticker = normalize_ticker(ticker)
    interval = '1m'
    stock = yf.Ticker(ticker)
    data = stock.history(period='1d', interval=interval)

    if data.empty:
        return go.Figure()

    data['CumulativeVolume'] = data['Volume'].cumsum()
    data['CumulativePV'] = (data['Volume'] * (data['High'] + data['Low'] + data['Close']) / 3).cumsum()
    data['VWAP'] = data['CumulativePV'] / data['CumulativeVolume']

    options_data, _, spot_price, _ = get_option_data(ticker, [])

    if options_data is None or options_data.empty:
        return go.Figure()

    if ticker in ["^SPX", "^NDX", "^RUT", "^DJI"]:
        price_range = 0.023
        resistance_zone_lower_percent = -0.0005
        resistance_zone_upper_percent = 0.0015
        support_zone_lower_percent = -0.0015
        support_zone_upper_percent = 0.0005
    elif ticker in ["SPY", "QQQ", "DIA", "XSP", "IWM"]:
        price_range = 0.022
        resistance_zone_lower_percent = -0.0005
        resistance_zone_upper_percent = 0.0015
        support_zone_lower_percent = -0.0015
        support_zone_upper_percent = 0.0005
    else:
        price_range = 0.05
        resistance_zone_lower_percent = -0.002
        resistance_zone_upper_percent = 0.0035
        support_zone_lower_percent = -0.0035
        support_zone_upper_percent = 0.002

    if spot_price:
        left_limit = spot_price - (spot_price * price_range)
        right_limit = spot_price + (spot_price * price_range)
        options_data = options_data[
            (options_data['strike'] >= left_limit) & (options_data['strike'] <= right_limit)
            ]
    else:
        left_limit = right_limit = 0

    max_call_vol_strike = options_data.loc[options_data['Call Volume'].idxmax(), 'strike']
    max_put_vol_strike = options_data.loc[options_data['Put Volume'].idxmax(), 'strike']
    max_negative_net_gex_strike = options_data.loc[options_data['Net GEX'].idxmin(), 'strike']

    resistance_zone_lower = max_call_vol_strike * (1 + resistance_zone_lower_percent)
    resistance_zone_upper = max_call_vol_strike * (1 + resistance_zone_upper_percent)

    if max_put_vol_strike < max_negative_net_gex_strike:
        support_zone_lower = max_put_vol_strike * (1 + support_zone_lower_percent)
        support_zone_upper = max_put_vol_strike * (1 + support_zone_upper_percent)
    else:
        support_zone_lower = max_negative_net_gex_strike * (1 + support_zone_lower_percent)
        support_zone_upper = max_negative_net_gex_strike * (1 + support_zone_upper_percent)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name=""
    ))

    fig.add_trace(go.Scatter(
        x=data.index,
        y=data['VWAP'],
        mode='lines',
        line=dict(color='#00ffcc', width=2),
        name='VWAP'
    ))

    market_open_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_time = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)

    fig.add_trace(go.Scatter(
        x=[market_open_time, market_close_time, market_close_time, market_open_time],
        y=[resistance_zone_lower, resistance_zone_lower, resistance_zone_upper, resistance_zone_upper],
        fill="toself",
        fillcolor="rgba(0, 160, 255, 0.2)",
        line=dict(color="rgba(0, 160, 255, 0.5)"),
        mode="lines",
        name='Resistance zone',
        hoverinfo="none",
    ))

    fig.add_trace(go.Scatter(
        x=[market_open_time, market_close_time, market_close_time, market_open_time],
        y=[support_zone_lower, support_zone_lower, support_zone_upper, support_zone_upper],
        fill="toself",
        fillcolor="rgba(172, 86, 49, 0.2)",
        line=dict(color="rgba(172, 86, 49, 0.5)"),
        mode="lines",
        name='Support zone',
        hoverinfo="none",
    ))

    fig.update_layout(
        title=f"Support / Resistance {ticker}",
        xaxis=dict(
            title="Время",
            type='date',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            rangeslider=dict(visible=False),
            autorange=False,
            range=[market_open_time, market_close_time],
            fixedrange=True
        ),
        yaxis=dict(
            title="Цена",
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            fixedrange=True
        ),
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        hovermode='x unified',
        margin=dict(l=50, r=50, b=50, t=50),
        dragmode=False
    )

    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        text="Max Power",
        showarrow=False,
        font=dict(size=80, color="rgba(255, 255, 255, 0.1)"),
        textangle=0,
    )

    return fig


# Callback для обновления страницы
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname'),
     Input('url', 'search')]
)
def display_page(pathname, search):
    if pathname == '/key-levels':
        return key_levels_page
    elif pathname == '/options-summary':
        return options_summary_page
    elif pathname == '/how-to-use-gex':
        return how_to_use_gex_page
    elif pathname == '/disclaimer':
        return disclaimer_page
    else:
        # Check if there's a ticker parameter in the URL
        ticker_value = 'SPX'  # default
        if search:
            params = parse_qs(search.lstrip('?'))
            if 'ticker' in params:
                ticker_value = params['ticker'][0]

        # Update the index page with the ticker value
        updated_index = index_page
        # Find the ticker input in the children and update its value
        for child in updated_index.children:
            if hasattr(child, 'id') and child.id == 'ticker-input':
                child.value = ticker_value
                break
        return updated_index


# Callback для обновления графика на странице "Key Levels"
@app.callback(
    Output('key-levels-chart', 'figure'),
    [Input('ticker-input-key-levels', 'value')]
)
def update_key_levels_chart_callback(ticker):
    return update_key_levels_chart(ticker)

@cache.memoize(timeout=300)  # Кэшируем на 5 минут
def update_key_levels_chart(ticker):
    ticker = normalize_ticker(ticker)
    interval = '1m'
    stock = yf.Ticker(ticker)
    data = stock.history(period='1d', interval=interval)

    if data.empty:
        return go.Figure()

    data['CumulativeVolume'] = data['Volume'].cumsum()
    data['CumulativePV'] = (data['Volume'] * (data['High'] + data['Low'] + data['Close']) / 3).cumsum()
    data['VWAP'] = data['CumulativePV'] / data['CumulativeVolume']

    if not data.empty:
        open_price = data['Open'].iloc[0]
        current_price = data['Close'].iloc[-1]
    else:
        open_price = current_price = None

    # Определяем диапазон для всего графика (4% от цены открытия)
    if ticker in ["^SPX", "^NDX", "^RUT", "^DJI", "^VIX"]:
        chart_range = 0.09  # 4% для индексов
    elif ticker in ["SPY", "QQQ", "DIA", "XSP", "IWM"]:
        chart_range = 0.09  # 4% для ETF
    else:
        chart_range = 0.2  # 10% для акций

    if open_price:
        upper_limit = open_price * (1 + chart_range / 2)
        lower_limit = open_price * (1 - chart_range / 2)
    else:
        upper_limit = lower_limit = 0

    options_data, _, spot_price, _ = get_option_data(ticker, [])

    if options_data is None or options_data.empty:
        return go.Figure()

    # Фильтруем данные опционов в пределах всего диапазона графика
    options_data = options_data[
        (options_data['strike'] >= lower_limit) &
        (options_data['strike'] <= upper_limit)
        ]

    if options_data.empty:
        return go.Figure()

    # 1. Основные уровни в пределах 1% от текущей цены (ОБЯЗАТЕЛЬНЫЕ)
    if current_price:
        one_percent_range = current_price * 0.01
        one_percent_upper = current_price + one_percent_range
        one_percent_lower = current_price - one_percent_range

        # Сопротивление: максимальный объем коллов в пределах +1%
        resistance_near = options_data[
            (options_data['strike'] >= current_price) &
            (options_data['strike'] <= one_percent_upper)
            ]
        if not resistance_near.empty:
            main_resistance = resistance_near.loc[resistance_near['Call Volume'].idxmax(), 'strike']
        else:
            # Если нет данных в +1%, берем ближайший страйк выше текущей цены с максимальным объемом коллов
            resistance_above = options_data[options_data['strike'] >= current_price]
            if not resistance_above.empty:
                main_resistance = resistance_above.loc[resistance_above['Call Volume'].idxmax(), 'strike']
            else:
                main_resistance = None

        # Поддержка: максимальный объем путов в пределах -1%
        support_near = options_data[
            (options_data['strike'] <= current_price) &
            (options_data['strike'] >= one_percent_lower)
            ]
        if not support_near.empty:
            main_support = support_near.loc[support_near['Put Volume'].idxmax(), 'strike']
        else:
            # Если нет данных в -1%, берем ближайший страйк ниже текущей цены с максимальным объемом путов
            support_below = options_data[options_data['strike'] <= current_price]
            if not support_below.empty:
                main_support = support_below.loc[support_below['Put Volume'].idxmax(), 'strike']
            else:
                main_support = None
    else:
        main_resistance = main_support = None

    # 2. Глобальные уровни во всем диапазоне (дополнительные)
    max_call_vol_strike = options_data.loc[options_data['Call Volume'].idxmax(), 'strike']
    max_put_vol_strike = options_data.loc[options_data['Put Volume'].idxmax(), 'strike']
    max_negative_net_gex_strike = options_data.loc[options_data['Net GEX'].idxmin(), 'strike']
    max_ag_strike = options_data.loc[options_data['AG'].idxmax(), 'strike']
    max_positive_net_gex_strike = options_data.loc[options_data['Net GEX'].idxmax(), 'strike']

    # 3. Определяем G-Flip зону
    g_flip_zone = None
    gex_values = options_data['Net GEX'].values
    for i in range(len(gex_values) - 6):
        if gex_values[i] < 0 and all(gex_values[i + j] > 0 for j in range(1, 7)):
            g_flip_zone = options_data.iloc[i]['strike']
            break

    # Определяем шаг страйков
    strike_step = options_data['strike'].diff().dropna().min()
    if pd.isna(strike_step) or strike_step == 0:
        strike_step = 1 if ticker in ["^SPX", "^NDX"] else 0.5

    # Создаем график
    fig = go.Figure()

    # Добавляем свечной график
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name="Price"
    ))

    # Добавляем VWAP
    fig.add_trace(go.Scatter(
        x=data.index,
        y=data['VWAP'],
        mode='lines',
        line=dict(color='#00ffcc', width=2),
        name='VWAP'
    ))

    # Время открытия/закрытия рынка
    market_open_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    market_close_time = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)

    # 1. ОСНОВНЫЕ УРОВНИ (1% диапазон) - ПРИОРИТЕТНЫЕ
    if main_resistance:
        # Зона сопротивления (основная)
        res_zone_lower = main_resistance * 0.9995
        res_zone_upper = main_resistance * 1.0015
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time, market_close_time, market_open_time],
            y=[res_zone_lower, res_zone_lower, res_zone_upper, res_zone_upper],
            fill="toself",
            fillcolor="rgba(0, 100, 255, 0.3)",
            line=dict(color="rgba(0, 100, 255, 0.7)", width=2),
            mode="lines",
            name=f'Main Resistance ({main_resistance:.2f})',
            hoverinfo="none",
        ))

    if main_support:
        # Зона поддержки (основная)
        sup_zone_lower = main_support * 0.9985
        sup_zone_upper = main_support * 1.0005
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time, market_close_time, market_open_time],
            y=[sup_zone_lower, sup_zone_lower, sup_zone_upper, sup_zone_upper],
            fill="toself",
            fillcolor="rgba(255, 100, 0, 0.3)",
            line=dict(color="rgba(255, 100, 0, 0.7)", width=2),
            mode="lines",
            name=f'Main Support ({main_support:.2f})',
            hoverinfo="none",

        ))

    # 2. ДОПОЛНИТЕЛЬНЫЕ УРОВНИ (весь диапазон)
    # Глобальное сопротивление (макс объем коллов)
    fig.add_trace(go.Scatter(
        x=[market_open_time, market_close_time],
        y=[max_call_vol_strike, max_call_vol_strike],
        mode='lines',
        line=dict(color='#22b5ff', width=2, dash='dot'),
        name=f'Global Call Vol ({max_call_vol_strike:.2f})'
    ))

    # Глобальная поддержка (макс объем путов)
    fig.add_trace(go.Scatter(
        x=[market_open_time, market_close_time],
        y=[max_put_vol_strike, max_put_vol_strike],
        mode='lines',
        line=dict(color='#ff2d3d', width=2, dash='dot'),
        name=f'Global Put Vol ({max_put_vol_strike:.2f})'
    ))

    # Макс отрицательный Net GEX
    fig.add_trace(go.Scatter(
        x=[market_open_time, market_close_time],
        y=[max_negative_net_gex_strike, max_negative_net_gex_strike],
        mode='lines',
        line=dict(color='#ff0000', width=2, dash='dash'),
        name=f'Max Neg GEX ({max_negative_net_gex_strike:.2f})'
    ))

    # Макс положительный Net GEX (зеленый) - NEW
    fig.add_trace(go.Scatter(
        x=[market_open_time, market_close_time],
        y=[max_positive_net_gex_strike, max_positive_net_gex_strike],
        mode='lines',
        line=dict(color='#00ff00', width=2, dash='dash'),
        name=f'Max Pos GEX ({max_positive_net_gex_strike:.2f})'
    ))

    # Макс AG
    fig.add_trace(go.Scatter(
        x=[market_open_time, market_close_time],
        y=[max_ag_strike, max_ag_strike],
        mode='lines',
        line=dict(color='#ab47bc', width=2, dash='dash'),
        name=f'Max AG ({max_ag_strike:.2f})'
    ))

    # 3. G-FLIP ЗОНА
    if g_flip_zone:
        g_flip_lower = g_flip_zone - (strike_step / 2)
        g_flip_upper = g_flip_zone + (strike_step / 2)
        fig.add_trace(go.Scatter(
            x=[market_open_time, market_close_time, market_close_time, market_open_time],
            y=[g_flip_lower, g_flip_lower, g_flip_upper, g_flip_upper],
            fill="toself",
            fillcolor="rgba(102, 187, 106, 0.2)",
            line=dict(color="rgba(102, 187, 106, 0.5)"),
            mode="lines",
            name=f'G-Flip Zone ({g_flip_zone:.2f})',
            hoverinfo="none",
        ))

    # 4. СТАТИЧЕСКИЕ УРОВНИ (рассчитанные по всей гамме)
    resistance_levels, support_levels = calculate_static_levels(options_data, spot_price)
    fig = add_static_levels_to_chart(fig, resistance_levels, support_levels, market_open_time, market_close_time)

    # Настраиваем layout графика
    fig.update_layout(
        title=f"{ticker}",
        xaxis=dict(
            title="Time",
            type='date',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            rangeslider=dict(visible=False),
            autorange=False,
            range=[market_open_time, market_close_time],
            fixedrange=True
        ),
        yaxis=dict(
            title="Price",
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            range=[lower_limit, upper_limit],
            fixedrange=True
        ),
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        hovermode='x unified',
        margin=dict(l=50, r=50, b=50, t=80),
        dragmode=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10)
        )
    )

    # Добавляем водяной знак
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        text="Max Power",
        showarrow=False,
        font=dict(size=80, color="rgba(255, 255, 255, 0.1)"),
        textangle=0,
    )

    return fig


# Callback для обновления таблицы Options Summary
@app.callback(
    Output('options-summary-table', 'data'),
    [Input('url', 'pathname')]  # Используем изменение URL как триггер
)
def update_options_summary_table(pathname):
    if pathname == '/options-summary':
        return get_pc_ratio_data()
    return []


@cache.memoize(timeout=600)  # Кэшируем на 10 минут
def get_pc_ratio_data():
    # Определяем индексы и ETF
    indices_etfs = ["SPX", "SPY", "QQQ", "VIX", "DIA", "IWM", "RUT", "XSP"]
    # Показываем данные для всех запрошенных тикеров
    tickers = indices_etfs + [
        "NVDA", "AAPL", "TSLA", "META", "MSFT", "GOOG",
        "AMZN", "AVGO", "WMT", "JPM", "MU", "BA", "SNOW",
        "UBER", "ROKU", "PLTR", "GS", "COIN"
    ]

    table_data = []

    for ticker in tickers:
        normalized_ticker = normalize_ticker(ticker)
        stock = yf.Ticker(normalized_ticker)

        try:
            price = stock.history(period='1d')['Close'].iloc[-1]
        except:
            price = None

        options_data, _, spot_price, _ = get_option_data(normalized_ticker, [])

        if options_data is None or options_data.empty or price is None:
            continue

        # Определяем диапазон цены в зависимости от типа тикера
        if ticker in indices_etfs:
            price_range = 0.01  # 1% для индексов и ETF
        else:
            price_range = 0.05  # 5% для акций

        # Фильтруем данные опционов в пределах диапазона цены (только для Resistance и Support)
        lower_limit = price * (1 - price_range)
        upper_limit = price * (1 + price_range)
        filtered_data = options_data[
            (options_data['strike'] >= lower_limit) &
            (options_data['strike'] <= upper_limit)
            ]

        if filtered_data.empty:
            continue

        # Рассчитываем Resistance (максимальный Call Volume в пределах диапазона)
        max_call_vol_strike = filtered_data.loc[filtered_data['Call Volume'].idxmax(), 'strike']

        # Рассчитываем Support (максимальный Put Volume или минимальный Net GEX в пределах диапазона)
        max_put_vol_strike = filtered_data.loc[filtered_data['Put Volume'].idxmax(), 'strike']
        max_negative_net_gex_strike = filtered_data.loc[filtered_data['Net GEX'].idxmin(), 'strike']

        if max_put_vol_strike < max_negative_net_gex_strike:
            support_strike = max_put_vol_strike
        else:
            support_strike = max_negative_net_gex_strike

        # Суммируем Call OI и Put OI по ВСЕМ опционам (не только в пределах диапазона)
        call_oi_amount = options_data['Call OI'].sum()
        put_oi_amount = options_data['Put OI'].sum()

        # Рассчитываем P/C Ratio
        pc_ratio = put_oi_amount / call_oi_amount if call_oi_amount != 0 else float('inf')

        table_data.append({
            'Ticker': ticker,
            'Price': round(price, 2),
            'Resistance': round(max_call_vol_strike, 2),
            'Support': round(support_strike, 2),
            'Call OI Amount': f"{call_oi_amount:,.0f}",
            'Put OI Amount': f"{put_oi_amount:,.0f}",
            'P/C Ratio': f"{pc_ratio:.2f}"
        })

    return table_data


# Запуск приложения
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
