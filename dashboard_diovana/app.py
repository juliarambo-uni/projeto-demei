from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
FUSO = ZoneInfo("America/Sao_Paulo")
LIMITE_PAGINA = 5000
LIMITE_EXPORTACAO = 100_000

NOMES_VARIAVEIS = {
    "irradiancia": "Irradiância",
    "temperatura": "Temperatura",
    "precipitacao": "Precipitação",
    "umidade_relativa": "Umidade relativa",
    "velocidade_vento": "Velocidade do vento",
    "direcao_vento": "Direção do vento",
}

st.set_page_config(
    page_title="DEMEI | Monitoramento meteorológico",
    page_icon="☼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
      :root { --ink:#152b3b; --muted:#647789; --line:#e4ebef; --blue:#167d9a; --mint:#dff3ed; }
      html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
      .stApp { background:linear-gradient(180deg,#f6fafb 0%,#f7f9fb 42%,#f5f8fa 100%); color:var(--ink); }
      .block-container { padding-top:1.45rem; padding-bottom:2rem; max-width:1480px; }
      h1,h2,h3 { font-family:'Manrope',sans-serif; color:var(--ink); letter-spacing:-.035em; }
      h1 { font-size:2rem !important; font-weight:800 !important; }
      h2 { font-size:1.34rem !important; font-weight:750 !important; }
      [data-testid="stSidebar"] { background:#102b3c; }
      [data-testid="stSidebar"] * { color:#eef7f8 !important; }
      [data-testid="stSidebar"] [data-baseweb="select"] div { color:#183345 !important; }
      [data-testid="stMetric"] { background:white; border:1px solid var(--line); padding:16px 18px; border-radius:16px; box-shadow:0 7px 20px rgba(18,55,70,.045); }
      [data-testid="stMetricLabel"] { color:#647789; }
      [data-testid="stMetricValue"] { color:#17384a; font-family:'Manrope',sans-serif; }
      div[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border-radius:18px; border:1px solid var(--line); box-shadow:0 7px 20px rgba(18,55,70,.035); }
      .hero { background:linear-gradient(112deg,#103b50 0%,#12647a 57%,#188c91 100%); padding:25px 28px; border-radius:20px; color:#f3fbfb; margin-bottom:20px; box-shadow:0 12px 28px rgba(16,59,80,.14); }
      .hero h1 { color:#fff !important; margin:0 0 5px 0; }
      .hero p { color:#d6eeee; margin:0; font-size:1rem; }
      .eyebrow { font-size:.73rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; color:#9bd8d2; margin-bottom:8px; }
      .section-note { color:#718495; font-size:.9rem; margin-top:-8px; }
      .status-pill { display:inline-block; background:#e3f5ed; color:#147a5a; padding:5px 10px; border-radius:99px; font-weight:700; font-size:.78rem; }
      .stDownloadButton button { border-radius:10px; }
      footer { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=45, show_spinner=False)
def api_get(path: str, params: dict | None = None):
    response = requests.get(f"{API_URL}{path}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=90, show_spinner=False)
def carregar_estacoes():
    return api_get("/estacoes")


@st.cache_data(ttl=90, show_spinner=False)
def carregar_variaveis():
    return api_get("/variaveis")


@st.cache_data(ttl=60, show_spinner=False)
def carregar_cobertura():
    return api_get("/cobertura")


@st.cache_data(ttl=60, show_spinner=False)
def carregar_agregado(codigo: str, variavel: str, inicio: str, fim: str, intervalo: str):
    resposta = api_get(
        "/medicoes/agregado",
        {"estacao": codigo, "variavel": variavel, "inicio": inicio, "fim": fim, "intervalo": intervalo},
    )
    return resposta


def data_iso(valor: date, fim_do_dia: bool = False) -> str:
    horario = time.max if fim_do_dia else time.min
    return datetime.combine(valor, horario, tzinfo=FUSO).isoformat(timespec="seconds")


def rotulo_variavel(codigo: str) -> str:
    return NOMES_VARIAVEIS.get(codigo, codigo.replace("_", " ").title())


def montar_frame_agregado(resposta: dict, estacao: dict) -> pd.DataFrame:
    df = pd.DataFrame(resposta.get("dados", []))
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["estacao_nome"] = estacao.get("nome", estacao["estacao"])
    df["fonte"] = estacao.get("fonte", "")
    df["unidade"] = resposta.get("unidade", "")
    return df


def buscar_medicoes(codigo: str, variavel: str, inicio: str, fim: str) -> pd.DataFrame:
    linhas: list[dict] = []
    pagina = 1
    while True:
        resposta = api_get(
            "/medicoes",
            {
                "estacao": codigo,
                "variavel": variavel,
                "inicio": inicio,
                "fim": fim,
                "limite": LIMITE_PAGINA,
                "pagina": pagina,
            },
        )
        total = int(resposta.get("total", 0))
        if total > LIMITE_EXPORTACAO:
            raise ValueError(
                f"O período contém {total:,} registros. Reduza o intervalo para exportar; "
                f"o limite seguro é {LIMITE_EXPORTACAO:,} linhas por arquivo."
            )
        linhas.extend(resposta.get("dados", []))
        if len(linhas) >= total or not resposta.get("dados"):
            break
        pagina += 1
    return pd.DataFrame(linhas)


def moeda_numero(valor, casas=1):
    if pd.isna(valor):
        return "—"
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def criar_grafico_temporal(series: list[tuple[dict, pd.DataFrame]], variavel: str, unidade: str):
    fig = go.Figure()
    paleta = ["#0e829b", "#f08b45", "#8f6bb3"]
    for idx, (estacao, df) in enumerate(series):
        if df.empty:
            continue
        cor = paleta[idx % len(paleta)]
        label = f"{estacao.get('nome', estacao['estacao'])} · {estacao.get('fonte', '')}"
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"], y=df["media"], mode="lines+markers", name=label,
                line={"color": cor, "width": 2.6}, marker={"size": 5},
                customdata=df[["minimo", "maximo", "quantidade"]],
                hovertemplate=(
                    "%{x|%d/%m/%Y %H:%M}<br>Média: %{y:.2f} " + unidade
                    + "<br>Mín.: %{customdata[0]:.2f} · Máx.: %{customdata[1]:.2f}"
                    + "<br>Leituras: %{customdata[2]}<extra>%{fullData.name}</extra>"
                ),
            )
        )
    fig.update_layout(
        height=390, margin={"l": 10, "r": 20, "t": 22, "b": 10},
        paper_bgcolor="white", plot_bgcolor="white", hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0},
        xaxis={"title": "Data e hora", "showgrid": False, "linecolor": "#e4ebef"},
        yaxis={"title": unidade, "gridcolor": "#edf2f4", "zerolinecolor": "#edf2f4"},
        font={"family": "DM Sans", "color": "#536a7b"},
    )
    return fig


st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">DEMEI · Infraestrutura de dados meteorológicos</div>
      <h1>Monitoramento meteorológico</h1>
      <p>Explore condições ambientais, compare estações e acompanhe dados de apoio ao planejamento fotovoltaico.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    saudacao = api_get("/saude")
    estacoes_api = carregar_estacoes()
    variaveis_api = carregar_variaveis()
    cobertura_api = carregar_cobertura()
except requests.RequestException as erro:
    st.error(
        f"Não foi possível conectar à API em `{API_URL}`. Confirme se a API e o MongoDB estão ativos. "
        f"Detalhe: {erro}"
    )
    st.info("Para iniciar tudo com Docker, consulte `dashboard_diovana/README.md`.")
    st.stop()

if saudacao.get("banco") != "ok":
    st.warning("A API respondeu, mas não conseguiu conectar ao MongoDB. Verifique o serviço de banco.")

if not estacoes_api:
    st.warning("Ainda não há estações cadastradas na API. Cadastre as estações para habilitar o mapa e os filtros.")
    st.stop()

estacoes_por_codigo = {e["estacao"]: e for e in estacoes_api}
cobertura_por_par = {(item["estacao"], item["variavel"]): item for item in cobertura_api}

with st.sidebar:
    st.markdown("### Painel de filtros")
    st.caption("Escolha o recorte dos dados para atualizar os gráficos.")
    st.markdown(f'<span class="status-pill">● API {saudacao.get("api", "indisponível")}</span>', unsafe_allow_html=True)

    codes = list(estacoes_por_codigo)
    var_disponiveis = [v["variavel"] for v in variaveis_api]
    variavel = st.selectbox("Variável meteorológica", var_disponiveis, format_func=rotulo_variavel)
    compat_codes = [
        code for code in codes
        if variavel in estacoes_por_codigo[code].get("variaveis", [])
        or (code, variavel) in cobertura_por_par
    ]
    if not compat_codes:
        compat_codes = codes
    codigo_principal = st.selectbox(
        "Estação de referência", compat_codes,
        format_func=lambda code: f"{estacoes_por_codigo[code].get('nome', code)} · {estacoes_por_codigo[code].get('fonte', '')}",
    )
    alternativas = [code for code in compat_codes if code != codigo_principal]
    comparar = st.multiselect(
        "Comparar com (até 2)", alternativas,
        format_func=lambda code: f"{estacoes_por_codigo[code].get('nome', code)} · {estacoes_por_codigo[code].get('fonte', '')}",
        max_selections=2,
    )

    cobertura_atual = cobertura_por_par.get((codigo_principal, variavel))
    if cobertura_atual:
        try:
            primeira = pd.to_datetime(cobertura_atual["primeiro"]).date()
            ultima = pd.to_datetime(cobertura_atual["ultimo"]).date()
        except (KeyError, TypeError, ValueError):
            primeira, ultima = date.today() - timedelta(days=30), date.today()
    else:
        primeira, ultima = date.today() - timedelta(days=30), date.today()

    preset = st.selectbox("Período rápido", ["Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias", "Todo o histórico", "Personalizado"])
    if preset == "Últimos 7 dias":
        data_fim = ultima
        data_inicio = max(primeira, ultima - timedelta(days=6))
    elif preset == "Últimos 30 dias":
        data_fim = ultima
        data_inicio = max(primeira, ultima - timedelta(days=29))
    elif preset == "Últimos 90 dias":
        data_fim = ultima
        data_inicio = max(primeira, ultima - timedelta(days=89))
    elif preset == "Todo o histórico":
        data_inicio, data_fim = primeira, ultima
    else:
        periodo_custom = st.date_input(
            "Intervalo de datas", value=(max(primeira, ultima - timedelta(days=29)), ultima),
            min_value=primeira, max_value=ultima,
        )
        if isinstance(periodo_custom, (tuple, list)):
            if len(periodo_custom) >= 2:
                data_inicio, data_fim = periodo_custom[0], periodo_custom[1]
            elif periodo_custom:
                data_inicio, data_fim = periodo_custom[0], ultima
            else:
                data_inicio, data_fim = max(primeira, ultima - timedelta(days=29)), ultima
        else:
            data_inicio, data_fim = periodo_custom, ultima

    intervalo = st.selectbox(
        "Resolução dos gráficos", ["dia", "hora", "mes"], index=0,
        format_func={"dia": "Diária", "hora": "Horária", "mes": "Mensal"}.get,
    )
    st.divider()
    st.caption("Os dados são consultados pela API do projeto; o dashboard não acessa o banco diretamente.")

if data_inicio > data_fim:
    st.error("A data inicial deve ser anterior à data final.")
    st.stop()

inicio_iso, fim_iso = data_iso(data_inicio), data_iso(data_fim, fim_do_dia=True)
export_key = f"{codigo_principal}|{variavel}|{inicio_iso}|{fim_iso}"
series: list[tuple[dict, pd.DataFrame]] = []
erros_agregado: list[str] = []
for code in [codigo_principal, *comparar]:
    station = estacoes_por_codigo[code]
    try:
        resp = carregar_agregado(code, variavel, inicio_iso, fim_iso, intervalo)
        series.append((station, montar_frame_agregado(resp, station)))
    except requests.RequestException as erro:
        erros_agregado.append(f"{station.get('nome', code)}: {erro}")

if erros_agregado:
    st.warning("Algumas séries não puderam ser carregadas: " + "; ".join(erros_agregado))

principal_df = next((df for station, df in series if station["estacao"] == codigo_principal), pd.DataFrame())

st.markdown("### Visão geral")
st.markdown('<p class="section-note">Resumo do recorte selecionado e cobertura disponível.</p>', unsafe_allow_html=True)
met1, met2, met3, met4 = st.columns(4)
if principal_df.empty:
    met1.metric("Média no período", "—")
    met2.metric("Maior valor", "—")
    met3.metric("Menor valor", "—")
    met4.metric("Pontos agregados", "0")
else:
    medias = pd.to_numeric(principal_df["media"], errors="coerce")
    quantidades = pd.to_numeric(principal_df["quantidade"], errors="coerce").fillna(0)
    maximos = pd.to_numeric(principal_df["maximo"], errors="coerce")
    minimos = pd.to_numeric(principal_df["minimo"], errors="coerce")
    peso_total = quantidades.sum()
    media_ponderada = (medias * quantidades).sum() / peso_total if peso_total else medias.mean()
    met1.metric("Média no período", f"{moeda_numero(media_ponderada)} {principal_df['unidade'].iloc[0]}")
    met2.metric("Maior valor", f"{moeda_numero(maximos.max())} {principal_df['unidade'].iloc[0]}")
    met3.metric("Menor valor", f"{moeda_numero(minimos.min())} {principal_df['unidade'].iloc[0]}")
    met4.metric("Pontos agregados", f"{len(principal_df):,}".replace(",", "."))

st.markdown("")
col_chart, col_side = st.columns([1.75, 1], gap="large")
with col_chart:
    st.markdown("### Comparação ao longo do tempo")
    st.markdown('<p class="section-note">Média e faixa mínima/máxima por intervalo selecionado.</p>', unsafe_allow_html=True)
    if any(not df.empty for _, df in series):
        unidade = next((df["unidade"].iloc[0] for _, df in series if not df.empty), "")
        st.plotly_chart(criar_grafico_temporal(series, variavel, unidade), width="stretch")
    else:
        st.info("Não há medições para essa variável, estação e período. Tente outro intervalo ou consulte a cobertura.")

with col_side:
    st.markdown("### Cobertura dos dados")
    st.markdown('<p class="section-note">Estações e variáveis com registros cadastrados.</p>', unsafe_allow_html=True)
    if cobertura_api:
        cob_df = pd.DataFrame(cobertura_api)
        cob_df["estação"] = cob_df["estacao"].map(lambda c: estacoes_por_codigo.get(c, {}).get("nome", c))
        cob_df["variável"] = cob_df["variavel"].map(rotulo_variavel)
        cob_df["registros"] = pd.to_numeric(cob_df["registros"], errors="coerce").fillna(0).astype(int)
        visao_cob = cob_df[["estação", "variável", "registros"]].sort_values(["estação", "variável"])
        st.dataframe(visao_cob, hide_index=True, width="stretch", height=300)
    else:
        st.info("A API ainda não reporta dados carregados.")

st.markdown("### Estações no mapa")
st.markdown('<p class="section-note">Localização das estações cadastradas. A tabela identifica fonte e coordenadas.</p>', unsafe_allow_html=True)
mapa_df = pd.DataFrame(
    [{"estacao": e.get("nome", e["estacao"]), "latitude": e["latitude"], "longitude": e["longitude"]} for e in estacoes_api]
)
mapa, tabela_estacoes = st.columns([1.25, 1], gap="large")
with mapa:
    st.map(mapa_df, latitude="latitude", longitude="longitude", size=180, color="#16849a", zoom=11)
with tabela_estacoes:
    tabela = pd.DataFrame(
        [{
            "Estação": e.get("nome", e["estacao"]),
            "Fonte": e.get("fonte", "—"),
            "Latitude": e.get("latitude"),
            "Longitude": e.get("longitude"),
            "Variáveis": ", ".join(rotulo_variavel(v) for v in e.get("variaveis", [])),
        } for e in estacoes_api]
    )
    st.dataframe(tabela, hide_index=True, width="stretch", height=310)

st.markdown("### Exportar dados")
st.markdown('<p class="section-note">Baixe medições brutas da estação principal em CSV, respeitando o intervalo e os filtros ativos.</p>', unsafe_allow_html=True)
export_col, download_col = st.columns([1, 2])
with export_col:
    exportar = st.button("Preparar CSV", type="primary", width="stretch")
if exportar:
    st.session_state.pop("csv_exportacao", None)
    st.session_state.pop("csv_exportacao_key", None)
    with st.spinner("Consultando páginas da API e preparando o CSV…"):
        try:
            bruto_df = buscar_medicoes(codigo_principal, variavel, inicio_iso, fim_iso)
            if bruto_df.empty:
                st.info("Não há registros para exportar neste recorte.")
            else:
                bruto_df["timestamp"] = pd.to_datetime(bruto_df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S%z")
                bruto_df["estacao_nome"] = estacoes_por_codigo[codigo_principal].get("nome", codigo_principal)
                st.session_state["csv_exportacao"] = bruto_df.to_csv(index=False).encode("utf-8-sig")
                st.session_state["csv_linhas"] = len(bruto_df)
                st.session_state["csv_exportacao_key"] = export_key
        except (requests.RequestException, ValueError) as erro:
            st.error(f"Não foi possível preparar o arquivo: {erro}")
with download_col:
    if st.session_state.get("csv_exportacao") and st.session_state.get("csv_exportacao_key") == export_key:
        st.download_button(
            f"Baixar CSV · {st.session_state['csv_linhas']:,} linhas".replace(",", "."),
            data=st.session_state["csv_exportacao"],
            file_name=f"demei_{codigo_principal}_{variavel}_{data_inicio}_{data_fim}.csv",
            mime="text/csv",
            width="stretch",
        )

st.caption("DEMEI · Projeto Integrador — Gestão da Infraestrutura · Horário local: America/Sao_Paulo (UTC−3).")
