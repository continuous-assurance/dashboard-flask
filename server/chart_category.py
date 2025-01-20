import plotly.express as px

def generate_executive_category_chart(RAG,df):

    q1 = (
        df.groupby(['metric_id', 'category', 'weight'])
        .agg(
            score=('totalok', lambda x: x.sum() / df.loc[x.index, 'total'].sum()),
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

    fig = px.bar(
        result.sort_values(by="score", ascending=False),
        y="category",
        x="score",
        orientation='h',
        title=f"By Category",
        text_auto=True,
        color="rag",
        color_discrete_map={
            "red": RAG['red'][0],
            "amber": RAG['amber'][0],
            "green": RAG['green'][0]
        },
    )
    fig.update_yaxes(title=None)
    fig.update_xaxes(range=[0, 1],tickformat=".0%", title=None)
    fig.update_layout(showlegend=False)

    return fig