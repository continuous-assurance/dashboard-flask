from dash import Dash, html, dcc, Input, Output, dash_table
import pandas as pd
import plotly.express as px
import yaml
import os
from chart_overview import generate_executive_overview_chart
from chart_dimension import generate_executive_dimension_chart
from chart_category import generate_executive_category_chart
from chart_metrics import generate_executive_metrics_chart

with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

filters = config['dimensions']
RAG = config['RAG']

if not os.path.exists(config['data']['summary']):
    initial_data = pd.DataFrame({
        "datestamp": pd.Series(dtype="datetime64[ns]"),
        "metric_id": pd.Series(dtype="str"),
        "total": pd.Series(dtype="float64"),
        "totalok": pd.Series(dtype="float64"),
        "slo": pd.Series(dtype="float64"),
        "slo_min": pd.Series(dtype="float64"),
        "weight": pd.Series(dtype="float64"),
        "title": pd.Series(dtype="str"),
        "category": pd.Series(dtype="str")
    })
    for d in config['dimensions']:
        initial_data[d] = pd.Series(dtype="str")

    initial_data.to_parquet(config['data']['summary'], index=False)

# Function to load the dataset
def load_summary():
    return pd.read_parquet(config['data']['summary'])

# Function to create Dash app
def create_dashboard(server):
    app = Dash(
        __name__,
        server=server,
        url_base_pathname='/',
        external_stylesheets=["/static/style.css"]
    )

    data = load_summary()
    data_latest = data[data['datestamp'] == data['datestamp'].max()]

    # Dash layout
    app.layout = html.Div(className="app-container", children=[
        html.Div(className="sidebar", children=[
            html.H2("Filters", className="sidebar-header"),
            html.Div(className="filters-container", children=[
                html.Div([
                    html.Label(f"Select a {label}:", className="dropdown-label"),
                    dcc.Dropdown(
                        id=f"{column_name}-dropdown",
                        options=[{"label": value, "value": value} for value in sorted(data_latest.get(column_name, pd.Series()).unique())],
                        value=None,
                        placeholder=f"Select a {label}",
                        className="dropdown"
                    )
                ], className="filter-item") for column_name, label in filters.items()
            ])
        ]),
        html.Div(className="main-content", children=[
            html.Div(className="header", children=[
                html.H1("Continuous Assurance", className="header-title"),
                html.P("Visualize data interactively with customizable filters.", className="header-description")
            ]),
            html.Div(className="graph-container", children=[
                dcc.Graph(id="overview-graph", className="graph overview-graph",config={"displayModeBar": False}),  # Overview graph
                html.Div(className="sub-graphs-container", children=[
                    dcc.Graph(id="dimension-graph", className="graph sub-graph",config={"displayModeBar": False}),  # First sub-graph
                    dcc.Graph(id="category-graph", className="graph sub-graph",config={"displayModeBar": False})   # Second sub-graph
                ])
            ]),
            html.Div(className="table-container", children=[
                html.Div(className="metrics-header-container", children=[
                    html.H2("Metrics", className="metrics-header")
                ]),
                html.Div(id="metrics-table", className="metrics-table")
            ])
        ])
    ])

    # Generate callback inputs dynamically
    dropdown_inputs = [Input(f"{column_name}-dropdown", "value") for column_name in filters.keys()]

    # Callback to update the bar chart based on selected filters
    @app.callback(
        [Output("overview-graph", "figure"),
         Output("dimension-graph", "figure"),
         Output("category-graph", "figure"),
         Output("metrics-table", "children")],
        dropdown_inputs
    )

    def update_charts(*selected_values):
        """Update bar charts based on selected filter values."""
        df_summary = load_summary()

        # Apply filtering dynamically based on selected values
        for selected_value, (column_name, _) in zip(selected_values, filters.items()):
            if selected_value:  # Apply filter only if the selected_value is not None
                df_summary = df_summary[df_summary[column_name] == selected_value]

        df_summary['score'] = df_summary['totalok'] / df_summary['total'] * df_summary['weight']

        # Find the latest summary data from the selected filters for the detailed graphs
        df_summary_latest = df_summary[df_summary['datestamp'] == df_summary['datestamp'].max()]

        fig_overview = generate_executive_overview_chart(RAG,df_summary)                                # == Executive Overview
        fig_dimension = generate_executive_dimension_chart(RAG,config['dimensions'],df_summary_latest)  # == Dimensional Chart
        fig_category = generate_executive_category_chart(RAG,df_summary_latest)                         # == Category Chart
        fig_metrics = generate_executive_metrics_chart(RAG,df_summary_latest)                           # == Metrics table
        
        return fig_overview, fig_dimension, fig_category, fig_metrics

    return app
