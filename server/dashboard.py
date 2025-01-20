from dash import Dash, html, dcc, Input, Output, dash_table
import pandas as pd
import plotly.express as px
import yaml
import os

with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

filters = config['dimensions']

# tweak the RAG colour scheme
RAG = {
    'red'  : ['#FF6F61', '#000000'],
    'amber': ['#FFC107', '#FFFFFF'],
    'green': ['#4CAF50', '#000000'],
}

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

    # Load initial data to populate dropdown options
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

        # === Executive Overview
        q1 = (
            df_summary.groupby(['metric_id', 'datestamp', 'weight'])
            .agg(
                weighted_score=('totalok', lambda x: x.sum() / df_summary.loc[x.index, 'total'].sum() * df_summary.loc[x.index, 'weight'].iloc[0]),
                slo_min=('slo_min', 'mean'),
                slo=('slo', 'mean'),
            )
            .reset_index()
        )

        result = (
            q1.groupby('datestamp')
            .agg(
                score=('weighted_score', lambda x: x.sum() / q1.loc[x.index, 'weight'].sum()),
                slo_min=('slo_min', 'mean'),
                slo=('slo', 'mean'),
            )
            .reset_index()
        )

        result['green'] = result.apply(lambda row: row['score'] if row['score'] >= row['slo'] else 0, axis=1)
        result['amber'] = result.apply(lambda row: row['score'] if row['slo_min'] <= row['score'] < row['slo'] else 0, axis=1)
        result['red'] = result.apply(lambda row: row['score'] if row['score'] < row['slo_min'] else 0, axis=1)

        fig_overview = px.bar(
            result, x="datestamp", y=["red", "amber", "green"], barmode="stack",
            color_discrete_map={
                "red": RAG['red'][0],
                "amber": RAG['amber'][0],
                "green": RAG['green'][0]
            },
            title="Executive Summary",
            text_auto=True
        )
        fig_overview.update_yaxes(range=[0, 1], tickformat=".0%", title=None)
        fig_overview.update_xaxes(title=None)
        fig_overview.update_layout(showlegend=False)
        fig_overview.update_layout(xaxis_type="category")

        # == Dimensional Chart
        q1 = (
            df_summary_latest.groupby(['metric_id', next(iter(config['dimensions'].keys())), 'weight'])
            .agg(
                score=('totalok', lambda x: x.sum() / df_summary.loc[x.index, 'total'].sum()),
                slo_min=('slo_min', 'mean'),
                slo=('slo', 'mean'),
            )
            .reset_index()
        )
        result = (
            q1.groupby(next(iter(config['dimensions'].keys())))
            .agg(
                score=('score', lambda x: x.sum() / q1.loc[x.index, 'weight'].sum()),
                slo_min=('slo_min', 'mean'),
                slo=('slo', 'mean'),
            )
            .reset_index()
        )
        result['rag'] = result.apply(lambda row: "red" if row['score'] < row['slo_min'] else "amber" if row['slo_min'] <= row['score'] < row['slo'] else "green", axis = 1)

        fig_dimension = px.bar(
            result.sort_values(by="score", ascending=False),
            y=next(iter(config['dimensions'].keys())),
            x="score",
            orientation='h',
            title=f"By {next(iter(config['dimensions'].values()))}",
            text_auto=True,
            color="rag",
            color_discrete_map={
                "red": RAG['red'][0],
                "amber": RAG['amber'][0],
                "green": RAG['green'][0]
            },
        )
        fig_dimension.update_yaxes(title=None)
        fig_dimension.update_xaxes(range=[0, 1],tickformat=".0%", title=None)
        fig_dimension.update_layout(showlegend=False)

        # == Category chart
        q1 = (
            df_summary_latest.groupby(['metric_id', 'category', 'weight'])
            .agg(
                score=('totalok', lambda x: x.sum() / df_summary.loc[x.index, 'total'].sum()),
                slo_min=('slo_min', 'mean'),
                slo=('slo', 'mean'),
            )
            .reset_index()
        )
        result = (
            q1.groupby('category')
            .agg(
                score=('score', lambda x: x.sum() / q1.loc[x.index, 'weight'].sum()),
                slo_min=('slo_min', 'mean'),
                slo=('slo', 'mean'),
            )
            .reset_index()
        )
        
        result['rag'] = result.apply(lambda row: "red" if row['score'] < row['slo_min'] else "amber" if row['slo_min'] <= row['score'] < row['slo'] else "green", axis = 1)

        fig_category = px.bar(
            result.sort_values(by="score", ascending=False),
            y="category",
            x="score",
            orientation='h',
            title="By Category",
            text_auto=True,
            color="rag",
            color_discrete_map={
                "red": RAG['red'][0],
                "amber": RAG['amber'][0],
                "green": RAG['green'][0]
            },
        )
        fig_category.update_yaxes(title=None)
        fig_category.update_xaxes(range=[0, 1],tickformat=".0%", title=None)
        fig_category.update_layout(showlegend=False)
        
        # == populate the metrics table
        q1 = (
            df_summary_latest.groupby(['metric_id', 'title'])
            .agg(
                score=('totalok', lambda x: x.sum() / df_summary.loc[x.index, 'total'].sum()),
                slo_min=('slo_min', 'mean'),
                slo=('slo', 'mean'),
            )
            .reset_index()
        )

        # == generate a datatable for the metrics from q1
        q1['Score'] = (q1['score'] * 100).round(2).astype(str) + '%'

        fig_metrics = dash_table.DataTable(
            id='table',
            columns=[{"name": i, "id": i} for i in q1.columns],
            data=q1.sort_values(by="score", ascending=True).to_dict('records'),
            style_table={'height': '300px', 'overflowY': 'auto'},
            style_data_conditional=[
                {
                    'if': {
                        'column_id': 'Score',
                        'filter_query': '{score} < {slo} && {score} >= {slo_min}',
                    },
                    'backgroundColor': RAG['amber'][0],
                    'color': 'white'
                },
                {
                    'if': {
                        'column_id': 'Score',
                        'filter_query': '{score} < {slo_min}',
                    },
                    'backgroundColor': RAG['red'][0],
                    'color': 'white'
                },
                {
                    'if': {
                        'column_id': 'Score',
                        'filter_query': '{score} >= {slo}',
                    },
                    'backgroundColor': RAG['green'][0],
                    'color': 'white'
                },
                {
                    'if': {
                        'column_id': 'score',
                    },
                    'display': 'none'
                },
                {
                    'if': {
                        'column_id': 'slo',
                    },
                    'display': 'none'
                },
                {
                    'if': {
                        'column_id': 'slo_min',
                    },
                    'display': 'none'
                }
            ],
            style_header_conditional=[
                {
                    'if': {
                        'column_id': 'score',
                    },
                    'display': 'none'
                },
                {
                    'if': {
                        'column_id': 'slo',
                    },
                    'display': 'none'
                },
                {
                    'if': {
                        'column_id': 'slo_min',
                    },
                    'display': 'none'
                }
            ]
        )
        
        return fig_overview, fig_dimension, fig_category, fig_metrics

    return app
