from functools import lru_cache
from os.path import dirname, join
import pandas as pd
from bokeh.io import curdoc
from bokeh.layouts import row, column
from bokeh.models import ColumnDataSource, Slope
from bokeh.models.widgets import PreText, Select, TextInput, Button, Div
from bokeh.plotting import figure
import os
import numpy as np
import bokeh.palettes as bk_pal
from subprocess import call
from bokeh.embed import server_document
script = server_document("http://172.26.8.26:5000/Bokeh_Gemini")
history_dir = app.config['IBIS_HOME'] + '/historical/'
print("history_dir: ", history_dir)
print(script)

history_dir = '/home/aries/ibis/historical/'
DEFAULT_TICKERS=[]

def collect_downloaded_symbols():
    global DEFAULT_TICKERS
    symbols = []
    for root, dirs, files in os.walk(history_dir):
        for file in files:
            if file.endswith('.csv') and file.split('.')[0].isalpha():
                symbols.append(file.split('.')[0])
    DEFAULT_TICKERS = symbols
    return symbols

def download_from_ib(symbol):
    global DEFAULT_TICKERS
    print("downloading: ", symbol)
    call(["/home/aries/ibis/ibisweb/download_from_ib.py", symbol])
    DEFAULT_TICKERS = collect_downloaded_symbols()
    ticker1.options = DEFAULT_TICKERS
    ticker2.options = DEFAULT_TICKERS


def nix(val, lst):
    return [x for x in lst if x != val]

#@lru_cache()
def load_ticker(ticker):
    df = pd.read_csv(history_dir + ticker + '.csv', index_col='date', usecols=[1, 2, 3, 4, 5, 6], parse_dates=True)
    df.index = pd.to_datetime(df.index, format=('%Y-%m-%d %H:%M:%S'), box=True)
    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    def normalize(data):
        ca = (data.Close - data.Close.mean()) / (data.Close.max() - data.Close.min())
        return ca

    df['Norm'] = normalize(df)
    dff= pd.DataFrame({ticker: df.Close, ticker+'_normal': df.Norm})
    return dff


#@lru_cache()
def get_data(t1, t2):
    df1 = load_ticker(t1)
    df2 = load_ticker(t2)
    data = pd.concat([df1, df2], axis=1)
    data = data.dropna()
    data['t1'] = data[t1]
    data['t2'] = data[t2]
    data['t1_normal'] = data[t1+'_normal']
    data['t2_normal'] = data[t2+'_normal']
    data['Time'] = data.index.to_julian_date()
    cmin = data['Time'].min()
    crange = data['Time'].max() - data['Time'].min()
    cols = (data['Time'] - cmin) * 255 // crange
    data['Colors'] = np.array(bk_pal.Plasma256)[cols.astype(int).tolist()]
    return data

# set up widgets


collect_downloaded_symbols()

stats = PreText(text='', width=500)
ticker1 = Select(value=DEFAULT_TICKERS[0], options=nix(DEFAULT_TICKERS[1], collect_downloaded_symbols()), title='this is my title')
ticker2 = Select(value=DEFAULT_TICKERS[1], options=nix(DEFAULT_TICKERS[0], collect_downloaded_symbols()), title='this is my title')

tickerdownloader = TextInput(title='Type in ticker you want to download and press enter:')



# set up plots

source = ColumnDataSource(data=dict(date=[], Close=[], Norm=[], Time=[], Colors=[]))
source_static = ColumnDataSource(data=dict(date=[], Close=[], Norm=[], Time=[], Colors=[]))
tools = 'pan,wheel_zoom,xbox_select,reset'

#gradient, intercept = np.polyfit(source_static.data[ticker1.value], source_static.data[ticker2.value], 1)
gradient = 0.4
intercept=300

#residuals = (source.data[ticker2.value] - (gradient * source.data[ticker1.value] + intercept))

p2 = figure(plot_width=350, plot_height=350, tools='pan,wheel_zoom,box_select,reset')
p2.scatter(x='t1', y='t2', marker='asterisk', size=5, color='Colors', alpha=0.6,  source=source)
p2.circle('t1', 't2', size=2, source=source, selection_color="orange", alpha=0.2,  selection_alpha=0.2)

#slope = Slope(gradient=gradient, y_intercept=intercept, line_color='green', line_dash='dashed', line_width=3.5)
#p2.add_layout(slope)
p2.grid.grid_line_color = None
p2.background_fill_color = "#eedddd"

ts1 = figure(plot_width=900, plot_height=300, tools=tools, x_axis_type="datetime", active_drag="xbox_select")
ts1.title.text = 'Normalised prices'
ts1.line('date', 't1_normal', source=source_static, line_width=2, color='red', alpha=0.4)
ts1.line('date', 't2_normal', source=source_static, line_width=2, color='blue', alpha=0.4)
ts1.legend.location = "bottom_left"
ts1.circle('date', 't1_normal', size=1.5, source=source, color=None, selection_color="green")
ts1.circle('date', 't2_normal', size=1.5, source=source, color=None, selection_color="black")

ts2 = figure(plot_width=900, plot_height=300, tools=tools, x_axis_type='datetime', active_drag="xbox_select")
ts2.x_range = ts1.x_range
ts2.line('date', 't2', source=source_static)
ts2.circle('date', 't2', size=1, source=source, color=None, selection_color="orange")

# set up callbacks
def my_radio_handler(attr, old, new):
    print('downloading ticker: ' + new)
    download_from_ib(new)
    update()

tickerdownloader.on_change("value", my_radio_handler)

def ticker1_change(attrname, old, new):
    ticker2.options = nix(new, collect_downloaded_symbols())
    update()

def ticker2_change(attrname, old, new):
    ticker1.options = nix(new, collect_downloaded_symbols())
    update()

def update(selected=None):
    global DEFAULT_TICKERS
    DEFAULT_TICKERS = collect_downloaded_symbols()
    t1, t2 = ticker1.value, ticker2.value

    data = get_data(t1, t2)
    source.data = source.from_df(data[['t1', 't2', 't1_normal', 't2_normal', 'Time', 'Colors']])
    source_static.data = source.data

    update_stats(data, t1, t2)

    p2.title.text = '%s  vs. %s ' % (t1, t2)
    ts1.title.text, ts2.title.text = t1, t2
    ts1.xaxis.axis_label = t1 + ' - ' + t2


def update_stats(data, t1, t2):
    stats.text = str(data[[t1, t2, t1+'_normal', t2+'_normal']].describe())

ticker1.on_change('value', ticker1_change)
ticker2.on_change('value', ticker2_change)

def selection_change(attrname, old, new):
    t1, t2 = ticker1.value, ticker2.value
    data = get_data(t1, t2)
    selected = source.selected.indices
    if selected:
        data = data.iloc[selected, :]
    update_stats(data, t1, t2)

source.on_change('selected', selection_change)

# set up layout
div = Div(text="""Your <a href="https://en.wikipedia.org/wiki/HTML">HTML</a>-supported text is initialized with the <b>text</b> argument.  The
remaining div arguments are <b>width</b> and <b>height</b>. For this example, those values
are <i>200</i> and <i>100</i> respectively.""",
width=200, height=100)



widgets = column(row(ticker1, ticker2), row(tickerdownloader), stats)
main_row = row(p2, widgets)
series = column(ts1, ts2)
layout = column(main_row, series, div)

# initialize
update()

curdoc().add_root(layout)
curdoc().title = "Stocks"
