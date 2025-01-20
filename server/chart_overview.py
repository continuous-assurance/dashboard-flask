import plotly.express as px

def generate_executive_overview_chart(RAG,df):
    q1 = (
        df.groupby(['metric_id', 'datestamp', 'weight'])
        .agg(
            weighted_score=('totalok', lambda x: x.sum() / df.loc[x.index, 'total'].sum() * df.loc[x.index, 'weight'].iloc[0]),
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

    fig = px.bar(
        result, x="datestamp", y=["red", "amber", "green"], barmode="stack",
        color_discrete_map={
            "red"  : RAG['red'][0],
            "amber": RAG['amber'][0],
            "green": RAG['green'][0]
        },
        title="Executive Summary",
        text_auto=True
    )
    fig.update_yaxes(range=[0, 1], tickformat=".0%", title=None)
    fig.update_xaxes(title=None)
    fig.update_layout(showlegend=False)
    fig.update_layout(xaxis_type="category")

    return fig
