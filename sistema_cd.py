from datetime import datetime
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão de Logística & Motoboys", page_icon="🚚", layout="wide"
)

PRECO_PADRAO_PACOTE = 1.80

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)


# --- FUNÇÕES DE LEITURA E ESCRITA NO GOOGLE SHEETS ---
def ler_tabela(nome_aba):
  try:
    df = conn.read(worksheet=nome_aba, ttl=5)
    return df.dropna(how="all")
  except Exception:
    return pd.DataFrame()


def salvar_tabela(nome_aba, df):
    try:
        conn.update(worksheet=nome_aba, data=df)
    except Exception:
        conn.create(worksheet=nome_aba, data=df)

# --- CARREGAR DADOS ---
df_motoboys = ler_tabela("motoboys")
df_lancamentos = ler_tabela("lancamentos")

# Garantir colunas mínimas caso esteja vazia
if df_motoboys.empty:
  df_motoboys = pd.DataFrame(
      columns=["id", "nome", "email", "telefone", "cnh", "placa", "ativo"]
  )

if df_lancamentos.empty:
  df_lancamentos = pd.DataFrame(
      columns=[
          "id",
          "motoboy_id",
          "data",
          "qtd_pacotes",
          "valor_calculado",
          "valor_final",
          "observacao",
          "hora",
      ]
  )


# --- FUNÇÕES DE SUPORTE ---
def obter_motoboys(apenas_ativos=True):
  if df_motoboys.empty:
    return pd.DataFrame()
  if apenas_ativos:
    return df_motoboys[df_motoboys["ativo"] == 1]
  return df_motoboys


def salvar_motoboy(nome, email, telefone, cnh, placa):
  global df_motoboys
  if not df_motoboys.empty and nome in df_motoboys["nome"].values:
    return False

  novo_id = (
      1
      if df_motoboys.empty
      else int(pd.to_numeric(df_motoboys["id"]).max()) + 1
  )
  novo_registro = pd.DataFrame([{
      "id": novo_id,
      "nome": nome,
      "email": email,
      "telefone": telefone,
      "cnh": cnh,
      "placa": placa,
      "ativo": 1,
  }])

  df_motoboys = pd.concat([df_motoboys, novo_registro], ignore_index=True)
  salvar_tabela("motoboys", df_motoboys)
  return True


def obter_totais_dia_motoboy(motoboy_id, data_str):
  if df_lancamentos.empty:
    return 0, 0.0, 0

  df_filtrado = df_lancamentos[
      (df_lancamentos["motoboy_id"].astype(str) == str(motoboy_id))
      & (df_lancamentos["data"] == data_str)
  ]

  if df_filtrado.empty:
    return 0, 0.0, 0

  total_pacotes = int(
      pd.to_numeric(df_filtrado["qtd_pacotes"], errors="coerce").sum()
  )
  total_valor = float(
      pd.to_numeric(df_filtrado["valor_final"], errors="coerce").sum()
  )
  total_rotas = len(df_filtrado)

  return total_pacotes, total_valor, total_rotas


def adicionar_rota(
    motoboy_id, data_str, qtd_pacotes_nova_rota, valor_final_nova_rota, obs=""
):
  global df_lancamentos
  novo_id = (
      1
      if df_lancamentos.empty
      else int(pd.to_numeric(df_lancamentos["id"]).max()) + 1
  )
  valor_calc = qtd_pacotes_nova_rota * PRECO_PADRAO_PACOTE
  hora_atual = datetime.now().strftime("%H:%M:%S")

  nova_rota = pd.DataFrame([{
      "id": novo_id,
      "motoboy_id": motoboy_id,
      "data": data_str,
      "qtd_pacotes": qtd_pacotes_nova_rota,
      "valor_calculado": valor_calc,
      "valor_final": valor_final_nova_rota,
      "observacao": obs,
      "hora": hora_atual,
  }])

  df_lancamentos = pd.concat([df_lancamentos, nova_rota], ignore_index=True)
  salvar_tabela("lancamentos", df_lancamentos)


def deletar_rota(rota_id):
  global df_lancamentos
  df_lancamentos = df_lancamentos[
      df_lancamentos["id"].astype(str) != str(rota_id)
  ]
  salvar_tabela("lancamentos", df_lancamentos)


# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Controle de Entregas e Motoboys - CD")

aba_lancamento, aba_cadastro, aba_progresso, aba_fechamento = st.tabs([
    "📝 Lançamento do Dia (CD)",
    "🏍️ Cadastro de Motoboys",
    "📊 Progresso & Comparativos",
    "📅 Fechamento do Mês",
])

# -------------------------------------------------------------
# ABA 1: LANÇAMENTO DO DIA
# -------------------------------------------------------------
with aba_lancamento:
  st.subheader("Registro de Pacotes por Rota")
  data_hoje = st.date_input("Data da Operação", datetime.now().date())
  data_str = str(data_hoje)
  data_br = data_hoje.strftime("%d/%m/%Y")

  df_m = obter_motoboys()

  if df_m.empty:
    st.warning(
        "Nenhum motoboy cadastrado. Acesse a aba 'Cadastro de Motoboys'"
        " primeiro."
    )
  else:
    motoboy_selecionado = st.selectbox(
        "Selecione o Motoboy", df_m["nome"].tolist()
    )
    motoboy_id = int(
        df_m[df_m["nome"] == motoboy_selecionado]["id"].values[0]
    )

    pacotes_acumulados, valor_acumulado, total_rotas = obter_totais_dia_motoboy(
        motoboy_id, data_str
    )

    if total_rotas > 0:
      st.info(
          f"📌 **{motoboy_selecionado}** já possui **{total_rotas} rota(s)**"
          f" registrada(s) hoje ({data_br}). Total acumulado:"
          f" **{pacotes_acumulados} pacotes** (R$ {valor_acumulado:.2f})."
      )

    st.write("---")
    st.write("#### ➕ Adicionar Nova Rota / Saída")

    col1, col2, col3 = st.columns(3)
    with col1:
      qtd_nova_rota = st.number_input(
          "Pacotes DESTA Rota", min_value=1, value=1, step=1
      )
    with col2:
      valor_calc_rota = qtd_nova_rota * PRECO_PADRAO_PACOTE
      st.metric(
          "Valor da Rota (R$ 1,80/pct)", f"R$ {valor_calc_rota:.2f}"
      )
    with col3:
      valor_final_rota = st.number_input(
          "Valor Final da Rota (Editável)",
          min_value=0.0,
          value=float(valor_calc_rota),
          format="%.2f",
      )

    novo_total_pacotes = pacotes_acumulados + qtd_nova_rota
    novo_total_valor = valor_acumulado + valor_final_rota
    st.caption(
        f"📊 **Acumulado do dia após esta rota:** {novo_total_pacotes} pacotes"
        f" | R$ {novo_total_valor:.2f}"
    )

    obs = st.text_input(
        "Observação / Descrição da Rota (Ex: Rota 2 - Zona Sul, Bônus, etc.)"
    )

    if st.button("💾 Adicionar Rota"):
      adicionar_rota(
          motoboy_id, data_str, qtd_nova_rota, valor_final_rota, obs
      )
      st.success(f"Rota de {qtd_nova_rota} pacotes adicionada para {motoboy_selecionado}!")
      st.rerun()

  st.divider()
  st.subheader(f"📋 Resumo Geral do Dia: {data_br}")

  if not df_lancamentos.empty:
    df_dia = df_lancamentos[df_lancamentos["data"] == data_str]
  else:
    df_dia = pd.DataFrame()

  if not df_dia.empty:
    df_merged = df_dia.merge(
        df_motoboys, left_on="motoboy_id", right_on="id", suffixes=("", "_mb")
    )
    df_merged["qtd_pacotes"] = pd.to_numeric(df_merged["qtd_pacotes"])
    df_merged["valor_final"] = pd.to_numeric(df_merged["valor_final"])
    df_merged["valor_calculado"] = pd.to_numeric(df_merged["valor_calculado"])

    df_agrupado = (
        df_merged.groupby("nome")
        .agg(
            Qtd_Rotas=("id", "count"),
            Total_Pacotes=("qtd_pacotes", "sum"),
            Valor_Padrao=("valor_calculado", "sum"),
            Valor_Total=("valor_final", "sum"),
        )
        .reset_index()
    )

    df_agrupado.columns = [
        "Motoboy",
        "Qtd. Rotas",
        "Total Pacotes",
        "Valor Padrão (R$)",
        "Valor Total (R$)",
    ]

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "📦 Total de Pacotes do Dia", int(df_agrupado["Total Pacotes"].sum())
    )
    m2.metric(
        "💰 Total a Pagar no Dia",
        f"R$ {df_agrupado['Valor Total (R$)'].sum():.2f}",
    )
    m3.metric("🛵 Motoboys Ativos Hoje", len(df_agrupado))

    st.write("##### Resumo Acumulado por Motoboy")
    st.dataframe(df_agrupado, use_container_width=True)

    with st.expander(
        "🔍 Histórico detalhado / Excluir rota lançada incorretamente"
    ):
      for idx, row in df_merged.iterrows():
        c1, c2, c3, c4, c5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
        c1.write(f"**{row['nome']}**")
        c2.write(f"🕒 {row.get('hora', '--:--')}")
        c3.write(f"📦 {row['qtd_pacotes']} pct(s)")
        c4.write(f"💰 R$ {row['valor_final']:.2f}")
        if c5.button("🗑️ Excluir", key=f"del_rota_{row['id']}"):
          deletar_rota(row["id"])
          st.success("Rota excluída!")
          st.rerun()
        st.write("---")
  else:
    st.info("Nenhum lançamento efetuado para a data selecionada.")

# -------------------------------------------------------------
# ABA 2: CADASTRO DE MOTOBOYS
# -------------------------------------------------------------
with aba_cadastro:
  st.subheader("Novo Cadastro")
  with st.form("form_motoboy", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
      nome = st.text_input("Nome Completo*")
      email = st.text_input("E-mail")
      telefone = st.text_input("Telefone / WhatsApp")
    with col2:
      cnh = st.text_input("Número da CNH")
      placa = st.text_input("Placa da Moto")

    salvar = st.form_submit_button("Cadastrar Motoboy")
    if salvar:
      if nome.strip():
        if salvar_motoboy(nome, email, telefone, cnh, placa):
          st.success(f"Motoboy {nome} cadastrado com sucesso!")
          st.rerun()
        else:
          st.error("Já existe um motoboy cadastrado com esse nome.")
      else:
        st.error("O campo Nome é obrigatório.")

  st.divider()
  st.subheader("Motoboys Cadastrados")
  st.dataframe(obter_motoboys(apenas_ativos=False), use_container_width=True)

# -------------------------------------------------------------
# ABA 3: PROGRESSO & COMPARATIVOS
# -------------------------------------------------------------
with aba_progresso:
  st.subheader("📈 Análise de Desempenho e Comparativos")
  if not df_lancamentos.empty and not df_motoboys.empty:
    df_g = df_lancamentos.merge(
        df_motoboys, left_on="motoboy_id", right_on="id"
    )
    df_g["qtd_pacotes"] = pd.to_numeric(df_g["qtd_pacotes"])
    df_g["data_formatada"] = pd.to_datetime(df_g["data"]).dt.strftime(
        "%d/%m/%Y"
    )

    df_geral = (
        df_g.groupby(["data_formatada", "nome"])["qtd_pacotes"]
        .sum()
        .reset_index()
    )
    df_geral.columns = ["Data", "Motoboy", "Pacotes"]

    st.bar_chart(df_geral, x="Data", y="Pacotes", color="Motoboy")
  else:
    st.info("Ainda não há dados suficientes para gerar gráficos.")

# -------------------------------------------------------------
# ABA 4: FECHAMENTO DO MÊS
# -------------------------------------------------------------
with aba_fechamento:
  st.subheader("🗓️ Fechamento Mensal para Pagamento")
  col_mes, col_ano = st.columns(2)
  with col_mes:
    mes = st.selectbox(
        "Mês", list(range(1, 13)), index=datetime.now().month - 1
    )
  with col_ano:
    ano = st.number_input("Ano", min_value=2024, value=datetime.now().year)

  prefixo_data = f"{ano}-{mes:02d}"

  if not df_lancamentos.empty and not df_motoboys.empty:
    df_mês = df_lancamentos[
        df_lancamentos["data"].astype(str).str.startswith(prefixo_data)
    ]
    if not df_mês.empty:
      df_f = df_mês.merge(df_motoboys, left_on="motoboy_id", right_on="id")
      df_f["qtd_pacotes"] = pd.to_numeric(df_f["qtd_pacotes"])
      df_f["valor_final"] = pd.to_numeric(df_f["valor_final"])

      df_fechamento = (
          df_f.groupby("nome")
          .agg(
              Total_Pacotes=("qtd_pacotes", "sum"),
              Total_A_Pagar=("valor_final", "sum"),
          )
          .reset_index()
      )
      df_fechamento.columns = ["Motoboy", "Total Pacotes", "Total A Pagar (R$)"]

      st.dataframe(df_fechamento, use_container_width=True)
      csv = df_fechamento.to_csv(index=False).encode("utf-8")
      st.download_button(
          "📥 Baixar Relatório em CSV/Excel",
          csv,
          f"fechamento_{prefixo_data}.csv",
          "text/csv",
      )
    else:
      st.info(f"Sem dados registrados para o mês {mes:02d}/{ano}.")
  else:
    st.info(f"Sem dados registrados para o mês {mes:02d}/{ano}.")
