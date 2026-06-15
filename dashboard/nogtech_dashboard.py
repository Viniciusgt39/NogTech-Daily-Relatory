# nogtech_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# 1. Configuração de Layout da Página
st.set_page_config(page_title="NogTech Analytics", layout="wide", initial_sidebar_state="collapsed")

# Customização via CSS para estilizar os cards
st.markdown("""
    <style>
        div[data-testid="stBlock"] { padding: 0px; }
        .metric-card {
            background-color: #15161a;
            border: 1px solid #2d2f36;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .metric-title { color: #8a8d98; font-size: 11px; font-weight: bold; letter-spacing: 1px; }
        .metric-value { font-size: 28px; font-weight: bold; margin: 5px 0px; }
        .metric-sub { color: #62656e; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# 2. Carregar dados tratados do ETL
root_dir = Path(__file__).resolve().parent.parent
data_path = root_dir / "data" / "processed" / "transformado.parquet"

if not data_path.exists():
    st.error("Por favor, execute o pipeline do Airflow ou o transform.py primeiro.")
    st.stop()

df = pd.read_parquet(data_path)

# Garantir que o mês seja tratado como String/Texto para não bugar o eixo X
df["mes_referencia"] = df["mes_referencia"].astype(str)
df = df.sort_values(by="mes_referencia")

# --- HEADER E FILTROS SUPERIORES ---
st.markdown('<p style="color:#6C5CE7; font-weight:bold; margin-bottom:-5px; font-size:12px; letter-spacing:1px;">NOGTECH ANALYTICS</p>', unsafe_allow_html=True)

head_col1, head_col2 = st.columns([0.4, 0.6])

with head_col1:
    st.markdown('<h1 style="margin-top:0px; font-size:32px;">Dashboard de Vendas 2024</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#62656e; margin-top:-15px; font-size:14px;">Base tratada e anonimizada — pipeline ETL</p>', unsafe_allow_html=True)

with head_col2:
    st.write("") 
    f_col1, f_col2, f_col3 = st.columns(3)
    
    with f_col1:
        meses = ["Todos os meses"] + sorted(list(df["mes_referencia"].unique()))
        mes_sel = st.selectbox("FILTROS:", meses, label_visibility="visible")
    with f_col2:
        feriados_opts = ["Todos os dias", "Apenas Feriados", "Dias Úteis"]
        feriado_sel = st.selectbox("FILTRO CALENDÁRIO:", feriados_opts)
    with f_col3:
        estados = ["Todos os estados"] + sorted(list(df["estado"].dropna().unique()))
        estado_sel = st.selectbox("FILTRO REGIONAL:", estados)

# --- Aplicação dos Filtros no DataFrame ---
df_filtrado = df.copy()
if mes_sel != "Todos os meses":
    df_filtrado = df_filtrado[df_filtrado["mes_referencia"] == mes_sel]
if estado_sel != "Todos os estados":
    df_filtrado = df_filtrado[df_filtrado["estado"] == estado_sel]
if feriado_sel == "Apenas Feriados":
    df_filtrado = df_filtrado[df_filtrado["venda_em_feriado"] == True]
elif feriado_sel == "Dias Úteis":
    df_filtrado = df_filtrado[df_filtrado["venda_em_feriado"] == False]

# --- 3. CÁLCULO DAS MÉTRICAS ---
total_vendas = len(df_filtrado)
valor_total = df_filtrado["valor"].sum()
ticket_medio = valor_total / total_vendas if total_vendas > 0 else 0
vendas_feriado = df_filtrado["venda_em_feriado"].sum()
pct_feriado = (vendas_feriado / total_vendas * 100) if total_vendas > 0 else 0
avg_tempo = df_filtrado["tempo_plataforma_min"].mean() if total_vendas > 0 else 0

# Grid de 4 Cards Superiores
m_col1, m_col2, m_col3, m_col4 = st.columns(4)

with m_col1:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-title">TOTAL DE VENDAS</div>
        <div class="metric-value" style="color: #6C5CE7;">{total_vendas:,}</div>
        <div class="metric-sub">{vendas_feriado} em feriados ({pct_feriado:.1f}%)</div>
    </div>""", unsafe_allow_html=True)

with m_col2:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-title">VALOR TOTAL VENDIDO</div>
        <div class="metric-value" style="color: #00CEC9;">R$ {valor_total:,.0f}</div>
        <div class="metric-sub">Faturamento Bruto Tratado</div>
    </div>""", unsafe_allow_html=True)

with m_col3:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-title">TICKET MÉDIO</div>
        <div class="metric-value" style="color: #FF7675;">R$ {ticket_medio:,.2f}</div>
        <div class="metric-sub">Média por Transação</div>
    </div>""", unsafe_allow_html=True)

with m_col4:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-title">ENGAJAMENTO MÉDIO</div>
        <div class="metric-value" style="color: #E84393;">{avg_tempo:.0f} min</div>
        <div class="metric-sub">Tempo médio em plataforma</div>
    </div>""", unsafe_allow_html=True)

# --- 4. SEÇÃO DO MEIO: VENDAS POR PERÍODO (Quantidade & Receita lado a lado) ---
with st.container(border=True):
    st.markdown('<p style="font-weight:bold; font-size:13px; color:#A4A7B1; margin-bottom:15px;">VENDAS POR PERÍODO — QUANTIDADE & RECEITA</p>', unsafe_allow_html=True)
    
    p_col1, p_col2 = st.columns(2)
    
   # Filtrando e eliminando os registros onde o mês de referência virou o texto "NaT" ou está vazio
    df_periodo = df_filtrado[
        (df_filtrado["mes_referencia"] != "NaT") & 
        (df_filtrado["mes_referencia"].notna()) & 
        (df_filtrado["mes_referencia"].str.strip() != "")
    ]
    
    # Agora sim, fazemos o agrupamento limpo
    df_periodo = df_periodo.groupby("mes_referencia").agg(
        qtd=("id_transacao", "count"),
        receita=("valor", "sum")
    ).reset_index()
    
    # Define espaçamento dinâmico: se tiver só 1 mês filtrado, deixa a barra fina e centralizada
    gap_style = 0.8 if len(df_periodo) == 1 else 0.2
    
    with p_col1:
        fig_qtd = px.bar(df_periodo, x="mes_referencia", y="qtd", text="qtd", title="Qtd. Vendas")
        fig_qtd.update_traces(marker_color="#6C5CE7", textposition="outside", cliponaxis=False)
        fig_qtd.update_layout(
            height=280, margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="", yaxis_title="", showlegend=False,
            bargap=gap_style # Controla a largura da barra
        )
        fig_qtd.update_xaxes(type='category') # CORREÇÃO: Força o eixo X a ser estritamente texto
        fig_qtd.update_yaxes(range=[0, 400])
        
        st.plotly_chart(fig_qtd, use_container_width=True, config={'displayModeBar': False})

    with p_col2:
        fig_rec = px.bar(df_periodo, x="mes_referencia", y="receita", title="Receita (R$)")
        fig_rec.update_traces(marker_color="#00CEC9", texttemplate="R$ %{y:,.0f}", textposition="outside", cliponaxis=False)
        fig_rec.update_layout(
            height=280, margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="", yaxis_title="", showlegend=False,
            bargap=gap_style # Controla a largura da barra
        )
        fig_rec.update_xaxes(type='category') # CORREÇÃO: Força o eixo X a ser estritamente texto
        fig_rec.update_yaxes(range=[0, 80000])
        
        st.plotly_chart(fig_rec, use_container_width=True, config={'displayModeBar': False})

# --- 5. SEÇÃO INFERIOR: RANKINGS E DISTRIBUIÇÃO ---
b_col1, b_col2 = st.columns(2)

with b_col1:
    with st.container(border=True):
        st.markdown('<p style="font-weight:bold; font-size:13px; color:#A4A7B1;">VENDAS POR ESTADO</p>', unsafe_allow_html=True)
        
        df_estado = df_filtrado.groupby("estado").agg(
            vendas=("id_transacao", "count"),
            faturamento=("valor", "sum")
        ).reset_index().sort_values(by="vendas", ascending=True)
        
        fig_est = px.bar(df_estado, x="vendas", y="estado", orientation="h", text="vendas")
        fig_est.update_traces(marker_color="#6C5CE7", textposition="inside")
        fig_est.update_layout(
            height=320, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="", yaxis_title=""
        )
        st.plotly_chart(fig_est, use_container_width=True, config={'displayModeBar': False})

with b_col2:
    with st.container(border=True):
        st.markdown('<p style="font-weight:bold; font-size:13px; color:#A4A7B1;">DISTRIBUIÇÃO POR CALENDÁRIO COMUM VS FERIADO</p>', unsafe_allow_html=True)
        
        if total_vendas > 0:
            df_pie = df_filtrado.groupby("venda_em_feriado").size().reset_index(name="count")
            df_pie["label"] = df_pie["venda_em_feriado"].map({True: "Feriado", False: "Dia Útil"})
            
            fig_pie = px.pie(df_pie, values="count", names="label", hole=0.6,
                             color_discrete_sequence=["#6C5CE7", "#00CEC9"])
            fig_pie.update_layout(
                height=320, margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)", showlegend=True,
                annotations=[dict(text=f"{total_vendas}<br><span style='font-size:10px;'>vendas</span>", x=0.5, y=0.5, font_size=18, showarrow=False)]
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        else:
            st.write("Sem dados para os filtros selecionados.")