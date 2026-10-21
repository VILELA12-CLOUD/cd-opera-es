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


# --- FUNÇÕES DE LEITURA E ESCRITA COM CACHE PARA EVITAR ERRO 429 ---
def ler_tabela(nome_aba):
  try:
    # ttl=5 mantém os dados atualizados a cada 5 segundos sem estourar o limite de 60 requisições/min do Google
    df = conn.read(worksheet=nome_aba, ttl=5)
    if df is not None and not df.empty:
      return df.dropna(how="all")
    return pd.DataFrame()
  except Exception:
    return pd.DataFrame()


def salvar_tabela(nome_aba, df):
  try:
    df_para_salvar = df.copy()
    for col in df_para_salvar.columns:
      df_para_salvar[col] = df_para_salvar[col].astype(str)

    conn.update(worksheet=nome_aba, data=df_para_salvar)
    st.cache_data.clear()
    return True
  except Exception as e:
    st.error(f"❌ Erro ao gravar na aba '{nome_aba}': {e}")
    return False


# --- FUNÇÃO DE SUPORTE PARA OBTER MOTOBOYS ---
def obter_motoboys(apenas_ativos=True):
  df_m = ler_tabela("motoboys")
  if df_m.empty or "nome" not in df_m.columns:
    return pd.DataFrame()

  if apenas_ativos and "ativo" in df_m.columns:
    df_m["ativo_clean"] = (
        df_m["ativo"].astype(str).str.strip().str.replace(".0", "", regex=False)
    )
    df_filtrado = df_m[df_m["ativo_clean"].isin(["1", "True"])]
    return df_filtrado.drop(columns=["ativo_clean"])

  return df_m


def salvar_motoboy(nome, email, telefone, cnh, placa):
  df_m = ler_tabela("motoboys")
  if not df_m.empty and "nome" in df_m.columns:
    if nome in df_m["nome"].values:
      st.warning("Já existe um motoboy cadastrado com este nome.")
      return False

  novo_id = (
      1
      if df_m.empty or "id" not in df_m.columns
      else int(pd.to_numeric(df_m["id"], errors="coerce").max()) + 1
  )
  novo_registro = pd.DataFrame([{
      "id": str(novo_id),
      "nome": str(nome),
      "email": str(email),
      "telefone": str(telefone),
      "cnh": str(cnh),
      "placa": str(placa),
      "ativo": "1",
  }])

  df_atualizado = pd.concat([df_m, novo_registro], ignore_index=True)
  return salvar_tabela("motoboys", df_atualizado)


def obter_totais_dia_motoboy(df_l, motoboy_id, data_str):
  if df_l.empty or "motoboy_id" not in df_l.columns:
    return 0, 0.0, 0

  df_filtrado = df_l[
      (df_l["motoboy_id"].astype(str) == str(motoboy_id))
      & (df_l["data"].astype(str) == data_str)
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
  df_l = ler_tabela("lancamentos")
  novo_id = (
      1
      if df_l.empty or "id" not in df_l.columns
      else int(pd.to_numeric(df_l["id"], errors="coerce").max()) + 1
  )
  valor_calc = qtd_pacotes_nova_rota * PRECO_PADRAO_PACOTE
  hora_atual = datetime.now().strftime("%H:%M:%S")

  nova_rota = pd.DataFrame([{
      "id": str(novo_id),
      "motoboy_id": str(motoboy_id),
      "data": str(data_str),
      "qtd_pacotes": str(qtd_pacotes_nova_rota),
      "valor_calculado": str(valor_calc),
      "valor_final": str(valor_final_nova_rota),
      "observacao": str(obs),
      "hora": str(hora_atual),
  }])

  df_atualizado = pd.concat([df_l, nova_rota], ignore_index=True)
  return salvar_tabela("lancamentos", df_atualizado)


def deletar_rota(rota_id):
  df_l = ler_tabela("lancamentos")
  if df_l.empty or "id" not in df_l.columns:
    return False
  df_atualizado = df_l[df_l["id"].astype(str) != str(rota_id)]
  return salvar_tabela("lancamentos", df_atualizado)


# --- INTERFACE PRINCIPAL ---
st.title("📦 Sistema de Controle de Entregas e Motoboys - CD")

aba_lancamento, aba_cadastro, aba_progresso, aba_fechamento = st.tabs([
    "📝 Lançamento do Dia (CD)",
    "🏍️ Cadastro de Motoboys",
    "📊 Progresso & Comparativos",
    "📅 Fechamento do Mês",
])

# Carregamento centralizado dos dados
df_lancamentos_geral = ler_tabela("lancamentos")
df_motoboys_geral = ler_tabela("motoboys")

# -------------------------------------------------------------
# ABA 1: LANÇAMENTO DO DIA
# -------------------------------------------------------------
with aba_lancamento:
  st.subheader("Registro de Pacotes por Rota")
  data_hoje = st.date_input("Data da Operação", datetime.now().date())
  data_str = str(data_hoje)
  data_br = data_hoje.strftime("%d/%m/%Y")

  df_m = obter_motoboys(apenas_ativos=True)

  if df_m.empty:
    st.warning(
        "Nenhum motoboy cadastrado ou ativo. Acesse a aba 'Cadastro de"
        " Motoboys' primeiro."
    )
  else:
    motoboy_selecionado = st.selectbox(
        "Selecione o Motoboy", df_m["nome"].tolist()
    )
    motoboy_id = df_m[df_m["nome"] == motoboy_selecionado]["id"].values[0]

    pacotes_acumulados, valor_acumulado, total_rotas = (
        obter_totais_dia_motoboy(df_lancamentos_geral, motoboy_id, data_str)
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
      if adicionar_rota(
          motoboy_id, data_str, qtd_nova_rota, valor_final_rota, obs
      ):
        st.success(
            f"Rota de {qtd_nova_rota} pacotes adicionada para"
            f" {motoboy_selecionado}!"
        )
        st.rerun()

  st.divider()
  st.subheader(f"📋 Resumo Geral do Dia: {data_br}")

  if (
      not df_lancamentos_geral.empty
      and "data" in df_lancamentos_geral.columns
  ):
    df_dia = df_lancamentos_geral[
        df_lancamentos_geral["data"].astype(str) == data_str
    ]
  else:
    df_dia = pd.DataFrame()

  if not df_dia.empty and not df_motoboys_geral.empty:
    df_merged = df_dia.merge(
        df_motoboys_geral,
        left_on="motoboy_id",
        right_on="id",
        suffixes=("", "_mb"),
    )
    df_merged["qtd_pacotes"] = pd.to_numeric(
        df_merged["qtd_pacotes"], errors="coerce"
    )
    df_merged["valor_final"] = pd.to_numeric(
        df_merged["valor_final"], errors="coerce"
    )
    df_merged["valor_calculado"] = pd.to_numeric(
        df_merged["valor_calculado"], errors="coerce"
    )

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
    st.dataframe(df_agrupado, width="stretch")

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
          if deletar_rota(row["id"]):
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
          st.success(f"Motoboy {nome} cadastrado e salvo na planilha!")
          st.rerun()
      else:
        st.error("O campo Nome é obrigatório.")

  st.divider()
  st.subheader("Motoboys Cadastrados")
  st.dataframe(obter_motoboys(apenas_ativos=False), width="stretch")

# -------------------------------------------------------------
# ABA 3: PROGRESSO & COMPARATIVOS
# -------------------------------------------------------------
with aba_progresso:
  st.subheader("📈 Análise de Desempenho e Comparativos")
  if not df_lancamentos_geral.empty and not df_motoboys_geral.empty:
    try:
      df_g = df_lancamentos_geral.merge(
          df_motoboys_geral, left_on="motoboy_id", right_on="id"
      )
      df_g["qtd_pacotes"] = pd.to_numeric(
          df_g["qtd_pacotes"], errors="coerce"
      )
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
    except Exception:
      st.info("Aguardando lançamentos para compor gráficos.")
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

  if not df_lancamentos_geral.empty and not df_motoboys_geral.empty:
    df_mes = df_lancamentos_geral[
        df_lancamentos_geral["data"].astype(str).str.startswith(prefixo_data)
    ]
    if not df_mes.empty:
      df_f = df_mes.merge(
          df_motoboys_geral, left_on="motoboy_id", right_on="id"
      )
      df_f["qtd_pacotes"] = pd.to_numeric(
          df_f["qtd_pacotes"], errors="coerce"
      )
      df_f["valor_final"] = pd.to_numeric(
          df_f["valor_final"], errors="coerce"
      )

      df_fechamento = (
          df_f.groupby("nome")
          .agg(
              Total_Pacotes=("qtd_pacotes", "sum"),
              Total_A_Pagar=("valor_final", "sum"),
          )
          .reset_index()
      )
      df_fechamento.columns = ["Motoboy", "Total Pacotes", "Total A Pagar (R$)"]

      st.dataframe(df_fechamento, width="stretch")
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
