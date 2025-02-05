import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import plotly.io as pio
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Initialize data
start_time = datetime.now()
data = pd.DataFrame({'Time': [start_time], 'HeartRate': [0], 'SpO2': [95], 'StressLevel': [0]})

is_monitoring = False


# Functions
def calculate_hrv(heart_rates):
    if len(heart_rates) < 2:
        return np.array([])
    differences = np.diff(heart_rates)
    return differences if len(differences) > 0 else np.array([0])


def save_pdf(current_heart_rate, current_spo2, status, hrv, current_stress, date_time):
    filename = f"heart_rate_report_{date_time}.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, "Heart Rate Monitoring Report")
    c.drawString(100, 730, f"Date and Time: {date_time}")
    c.drawString(100, 710, f"Current Heart Rate: {current_heart_rate:.1f} BPM")
    c.drawString(100, 690, f"Current SpO2: {current_spo2:.1f}%")
    c.drawString(100, 670, f"Status: {status}")
    c.drawString(100, 650, f"Current Stress Level: {current_stress:.1f}")

    if current_heart_rate > 125:
        c.drawString(100, 630, "CRITICAL ALERT: Immediate medical attention is advised.")
    else:
        c.drawString(100, 630, "Your heart rate is within a manageable range.")

    c.drawString(100, 610, "Heart Health Analysis and Recommendations")

    c.save()


def plot_historical_data(time_range):
    if time_range == 'daily':
        resampled_data = data.resample('D', on='Time').mean()
    elif time_range == 'weekly':
        resampled_data = data.resample('W', on='Time').mean()
    elif time_range == 'monthly':
        resampled_data = data.resample('M', on='Time').mean()
    else:
        resampled_data = data.copy()

    historical_fig = go.Figure()
    historical_fig.add_trace(go.Scatter(x=resampled_data.index, y=resampled_data['HeartRate'], mode='lines+markers',
                                        name='Avg Heart Rate'))
    historical_fig.add_trace(go.Scatter(x=resampled_data.index, y=resampled_data['SpO2'], mode='lines+markers',
                                        name='Avg SpO2'))
    historical_fig.update_layout(title=f'Historical Heart Rate and SpO2 ({time_range.capitalize()})',
                                 xaxis_title='Time', yaxis_title='Heart Rate (BPM) / SpO2 (%)')
    return historical_fig


def get_theme_style(theme):
    if theme == 'dark':
        return {'backgroundColor': '#343a40', 'color': '#ffffff'}
    else:
        return {'backgroundColor': '#f8f9fa', 'color': '#000000'}


# Layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Heart Rate and SpO2 Monitoring Dashboard"), className="text-center mb-4")
    ]),
    dbc.Row([
        dbc.Col([
            dcc.RadioItems(
                id='theme-toggle',
                options=[
                    {'label': 'Light Mode', 'value': 'light'},
                    {'label': 'Dark Mode', 'value': 'dark'}
                ],
                value='light',
                inline=True,
                style={'margin': '10px'}
            ),
            html.H3("Current Heart Rate"),
            html.Div(id='current-heart-rate', style={'fontSize': '2em', 'color': 'green'}),
            html.Div(id='heart-rate-status', style={'fontSize': '1.2em'}),
            html.Div(id='threshold-alert', style={'fontSize': '1.2em', 'color': 'red'}),
            html.H3("Current SpO2"),
            html.Div(id='current-spo2', style={'fontSize': '2em', 'color': 'blue'}),
            html.Div(id='spo2-status', style={'fontSize': '1.2em'}),
            dbc.Button("Start", id="start-button", color="success", className="mr-2 mt-3"),
            dbc.Button("Stop", id="stop-button", color="danger", className="ml-2 mt-3"),
            dbc.Button("Save as PDF", id="save-pdf-button", color="primary", className="mt-3"),
            dcc.ConfirmDialog(id='confirm-pdf-save', message='PDF report saved successfully!', displayed=False),
            dcc.Dropdown(
                id='time-range-dropdown',
                options=[
                    {'label': 'Daily', 'value': 'daily'},
                    {'label': 'Weekly', 'value': 'weekly'},
                    {'label': 'Monthly', 'value': 'monthly'}
                ],
                value='daily',
                clearable=False,
                style={'marginTop': '20px'}
            ),
            dcc.Graph(id='historical-data', style={'marginTop': '20px'}),
            html.H4("Analysis"),
            html.Ul(id="analysis-output", style={'marginTop': '10px'})
        ], width=4),
        dbc.Col([
            dcc.Graph(id='heart-rate-history'),
            dcc.Graph(id='spo2-history', style={'marginTop': '20px'}),
            dcc.Graph(id='stress-level-trend', style={'marginTop': '20px'})
        ], width=8)
    ]),
    dcc.Interval(id='interval-component', interval=1 * 1000, n_intervals=0, disabled=True)
], id='main-container', style={'backgroundColor': '#f8f9fa', 'padding': '20px'})

@app.callback(
    [
        Output('interval-component', 'disabled'),
        Output('current-heart-rate', 'children'),
        Output('heart-rate-status', 'children'),
        Output('threshold-alert', 'children'),
        Output('current-spo2', 'children'),
        Output('spo2-status', 'children'),
        Output('heart-rate-history', 'figure'),
        Output('spo2-history', 'figure'),
        Output('stress-level-trend', 'figure'),
        Output('historical-data', 'figure'),
        Output('analysis-output', 'children'),
        Output('confirm-pdf-save', 'displayed'),
        Output('main-container', 'style')
    ],
    [
        Input('start-button', 'n_clicks'),
        Input('stop-button', 'n_clicks'),
        Input('interval-component', 'n_intervals'),
        Input('save-pdf-button', 'n_clicks'),
        Input('time-range-dropdown', 'value'),
        Input('theme-toggle', 'value')
    ],
    [State('interval-component', 'disabled')]
)
def update_monitoring(start_clicks, stop_clicks, n_intervals, save_clicks, time_range, theme, is_disabled):
    global data, is_monitoring

    ctx = dash.callback_context
    if ctx.triggered:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == 'start-button' and is_disabled:
            is_monitoring = True
            is_disabled = False
        elif button_id == 'stop-button' and not is_disabled:
            is_monitoring = False
            is_disabled = True

    if is_monitoring:
        new_time = data['Time'].iloc[-1] + timedelta(seconds=1)
        new_heart_rate = np.random.randint(60, 130) if n_intervals % 5 != 0 else np.random.randint(126, 140)
        new_spo2 = np.random.randint(90, 100)
        new_stress_level = new_heart_rate / 2
        new_entry = pd.DataFrame({'Time': [new_time], 'HeartRate': [new_heart_rate], 'SpO2': [new_spo2], 'StressLevel': [new_stress_level]})
        data = pd.concat([data, new_entry])

    current_heart_rate = data['HeartRate'].iloc[-1]
    current_spo2 = data['SpO2'].iloc[-1]
    current_stress = data['StressLevel'].iloc[-1]
    status = "Normal" if current_heart_rate <= 125 else "Critical: Seek immediate attention!"
    threshold_alert = "Critical Alert: Heart rate exceeds safe limits!" if current_heart_rate > 125 else ""
    spo2_status = "Normal" if current_spo2 >= 95 else "Warning: Low SpO2!"

    heart_rate_fig = go.Figure()
    heart_rate_fig.add_trace(go.Scatter(x=data['Time'], y=data['HeartRate'], mode='lines', name='Heart Rate'))
    heart_rate_fig.update_layout(title='Heart Rate Over Time', xaxis_title='Time', yaxis_title='Heart Rate (BPM)')

    spo2_fig = go.Figure()
    spo2_fig.add_trace(go.Scatter(x=data['Time'], y=data['SpO2'], mode='lines', name='SpO2'))
    spo2_fig.update_layout(title='SpO2 Over Time', xaxis_title='Time', yaxis_title='SpO2 (%)')

    stress_fig = go.Figure()
    stress_fig.add_trace(go.Scatter(x=data['Time'], y=data['StressLevel'], mode='lines', name='Stress Level'))
    stress_fig.update_layout(title='Stress Level Over Time', xaxis_title='Time', yaxis_title='Stress Level')

    historical_fig = plot_historical_data(time_range)

    analysis = [
        f"Average Heart Rate: {data['HeartRate'].mean():.1f} BPM",
        f"Average SpO2: {data['SpO2'].mean():.1f}%",
        f"Maximum Heart Rate: {data['HeartRate'].max():.1f} BPM",
        f"Maximum SpO2: {data['SpO2'].max():.1f}%",
        f"Average Stress Level: {data['StressLevel'].mean():.1f}",
    ]

    if save_clicks:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_pdf(current_heart_rate, current_spo2, status, calculate_hrv(data['HeartRate']), current_stress, timestamp)
        return is_disabled, current_heart_rate, status, threshold_alert, current_spo2, spo2_status, heart_rate_fig, spo2_fig, stress_fig, historical_fig, analysis, True, get_theme_style(theme)

    return is_disabled, current_heart_rate, status, threshold_alert, current_spo2, spo2_status, heart_rate_fig, spo2_fig, stress_fig, historical_fig, analysis, False, get_theme_style(theme)



if __name__ == '__main__':
    app.run_server(debug=True)
