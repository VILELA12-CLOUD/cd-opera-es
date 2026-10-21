from datetime import datetime
import pandas as pd
import pytz
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão de Logística & Motoboys", page_icon="🚚", layout="wide"
)

PRECO_PADRAO_PACOTE = 1.80
FUSO_SP = pytz.timezone("America/Sao_Paulo")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)


# --- FUNÇÕES DE LEITURA E ESCRITA ---
def ler_tabela(nome_aba):
  try:
    df = conn.read(worksheet=nome_aba, ttl=0)
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


# --- FUNÇÕES DE SUPORTE ---
def obter_motoboys(apenas_ativos=True):
  df_m = ler_tabela("motoboys")
  if df_m.empty or "nome" not in df_m.columns:
    return pd.DataFrame()

  if apenas_ativos and "ativo" in df_m.columns:
    ativo_str = df_m["ativo"].astype(str).str.strip().str.lower()
    return df_m[~ativo_str.isin(["0", "false", "0.0"])]

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

  return total_pacotes, round(total_valor, 2), total_rotas


def adicionar_rota(
    motoboy_id,
    data_str,
    qtd_pacotes,
    qtd_insucesso,
    valor_final_manual,
    obs="",
):
  df_l = ler_tabela("lancamentos")
  novo_id = (
      1
      if df_l.empty or "id" not in df_l.columns
      else int(pd.to_numeric(df_l["id"], errors="coerce").max()) + 1
  )

  # Cálculo exato com desconto dos insucessos
  pacotes_entregues = max(0, qtd_pacotes - qtd_insucesso)
  valor_calc = round(pacotes_entregues * PRECO_PADRAO_PACOTE, 2)
  valor_final = (
      round(valor_final_manual, 2)
      if valor_final_manual > 0
      else round(valor_calc, 2)
  )

  # Ajuste do Fuso Horário para Brasília (SP)
  hora_atual = datetime.now(FUSO_SP).strftime("%H:%M:%S")

  nova_rota = pd.DataFrame([{
      "id": str(novo_id),
      "motoboy_id": str(motoboy_id),
      "data": str(data_str),
      "qtd_pacotes": str(int(qtd_pacotes)),
      "qtd_insucesso": str(int(qtd_insucesso)),
      "valor_calculado": str(round(valor_calc, 2)),
      "valor_final": str(round(valor_final, 2)),
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

# -------------------------------------------------------------
# ABA 1: LANÇAMENTO DO DIA
# -------------------------------------------------------------
with aba_lancamento:
  st.subheader("Registro de Pacotes por Rota")
  data_hoje = st.date_input(
      "Data da Operação", datetime.now(FUSO_SP).date()
  )
  data_str = str(data_hoje)
  data_br = data_hoje.strftime("%d/%m/%Y")

  df_m = obter_motoboys(apenas_ativos=True)
  df_lancamentos_geral = ler_tabela("lancamentos")

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

    with st.form("form_rota", clear_on_submit=True):
      c1, c2, c3, c4 = st.columns(4)
      with c1:
        qtd_nova_rota = st.number_input(
            "Pacotes Saída", min_value=1, value=1, step=1
        )
      with c2:
        qtd_insucesso = st.number_input(
            "Insucessos / Retorno", min_value=0, value=0, step=1
        )
      with c3:
        pacotes_liquidos = max(0, qtd_nova_rota - qtd_insucesso)
        val_sugerido = round(pacotes_liquidos * PRECO_PADRAO_PACOTE, 2)
        st.metric(
            f"Entregues ({pacotes_liquidos} pct)", f"R$ {val_sugerido:.2f}"
        )
      with c4:
        valor_final_rota = st.number_input(
            "Valor Final (Editável)",
            min_value=0.0,
            value=float(val_sugerido),
            format="%.2f",
        )

      obs = st.text_input(
          "Observação / Descrição da Rota (Ex: Rota 2 - Zona Sul, Bônus, etc.)"
      )
      btn_salvar_rota = st.form_submit_button("💾 Adicionar Rota")

      if btn_salvar_rota:
        if adicionar_rota(
            motoboy_id,
            data_str,
            qtd_nova_rota,
            qtd_insucesso,
            valor_final_rota,
            obs,
        ):
          st.toast("✅ Rota adicionada com sucesso!")
          st.rerun()

  st.divider()
  st.subheader(f"📋 Resumo Geral do Dia: {data_br}")

  df_motoboys_geral = ler_tabela("motoboys")

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

    # Tratamento rigoroso de números para evitar dízima/concatenação de string
    df_merged["qtd_pacotes"] = pd.to_numeric(
        df_merged["qtd_pacotes"], errors="coerce"
    ).fillna(0)
    df_merged["qtd_insucesso"] = (
        pd.to_numeric(df_merged.get("qtd_insucesso", 0), errors="coerce")
        .fillna(0)
        .astype(int)
    )
    df_merged["valor_final"] = (
        pd.to_numeric(df_merged["valor_final"], errors="coerce")
        .fillna(0.0)
        .round(2)
    )
    df_merged["valor_calculado"] = (
        pd.to_numeric(df_merged["valor_calculado"], errors="coerce")
        .fillna(0.0)
        .round(2)
    )

    df_agrupado = (
        df_merged.groupby("nome")
        .agg(
            Qtd_Rotas=("id", "count"),
            Total_Pacotes=("qtd_pacotes", "sum"),
            Total_Insucesso=("qtd_insucesso", "sum"),
            Valor_Total=("valor_final", "sum"),
        )
        .reset_index()
    )

    df_agrupado["Valor_Total"] = df_agrupado["Valor_Total"].round(2)
    df_agrupado.columns = [
        "Motoboy",
        "Qtd. Rotas",
        "Pacotes Saída",
        "Insucessos",
        "Valor Total (R$)",
    ]

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "📦 Total de Pacotes do Dia",
        int(df_agrupado["Pacotes Saída"].sum() - df_agrupado["Insucessos"].sum()),
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
        c1, c2, c3, c4, c5 = st.columns([0.25, 0.15, 0.2, 0.2, 0.2])
        c1.write(f"**{row['nome']}**")
        c2.write(f"🕒 {row.get('hora', '--:--')}")
        insuc_txt = (
            f" (Insucessos: {row['qtd_insucesso']})"
            if row["qtd_insucesso"] > 0
            else ""
        )
        c3.write(f"📦 {int(row['qtd_pacotes'])} pct(s){insuc_txt}")
        c4.write(f"💰 R$ {row['valor_final']:.2f}")
        if c5.button("🗑️ Excluir", key=f"del_rota_{row['id']}"):
          if deletar_rota(row["id"]):
            st.toast("🗑️ Rota excluída!")
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
          st.toast(f"✅ Motoboy {nome} cadastrado com sucesso!")
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
  df_lancamentos_geral = ler_tabela("lancamentos")
  df_motoboys_geral = ler_tabela("motoboys")

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
        "Mês", list(range(1, 13)), index=datetime.now(FUSO_SP).month - 1
    )
  with col_ano:
    ano = st.number_input(
        "Ano", min_value=2024, value=datetime.now(FUSO_SP).year
    )

  prefixo_data = f"{ano}-{mes:02d}"

  df_lancamentos_geral = ler_tabela("lancamentos")
  df_motoboys_geral = ler_tabela("motoboys")

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
      df_fechamento["Total_A_Pagar"] = df_fechamento["Total_A_Pagar"].round(2)
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
