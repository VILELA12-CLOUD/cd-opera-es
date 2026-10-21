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
    df = conn.read(worksheet=nome_aba, ttl=0)
    if df is not None and not df.empty:
      return df.dropna(how="all")
    return pd.DataFrame()
  except Exception as e:
    st.warning(f"Aba '{nome_aba}' em inicialização ou sem dados.")
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
    st.error(
        f"❌ Erro ao gravar na aba '{nome_aba}': {e}\n\n"
        "Verifique se o e-mail do 'client_email' dos Secrets foi adicionado como"
        " EDITOR no botão Compartilhar da planilha."
    )
    return False


# --- CARREGAR DADOS ---
df_motoboys = ler_tabela("motoboys")
df_lancamentos = ler_tabela("lancamentos")

# Garantir colunas mínimas caso esteja vazia
if df_motoboys.empty or "nome" not in df_motoboys.columns:
  df_motoboys = pd.DataFrame(
      columns=["id", "nome", "email", "telefone", "cnh", "placa", "ativo"]
  )

if df_lancamentos.empty or "motoboy_id" not in df_lancamentos.columns:
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
  if apenas_ativos and "ativo" in df_motoboys.columns:
    # Aceita variações do campo ativo (1, 1.0, True) para não ocultar cadastros
    return df_motoboys[
        df_motoboys["ativo"].astype(str).str.strip().isin(["1", "1.0", "True"])
    ]
  return df_motoboys


def salvar_motoboy(nome, email, telefone, cnh, placa):
  global df_motoboys
  if not df_motoboys.empty and nome in df_motoboys["nome"].values:
    st.warning("Já existe um motoboy cadastrado com este nome.")
    return False

  novo_id = (
      1
      if df_motoboys.empty
      else int(pd.to_numeric(df_motoboys["id"], errors="coerce").max()) + 1
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

  df_motoboys = pd.concat([df_motoboys, novo_registro], ignore_index=True)
  sucesso = salvar_tabela("motoboys", df_motoboys)
  return sucesso


def obter_totais_dia_motoboy(motoboy_id, data_str):
  if df_lancamentos.empty:
    return 0, 0.0, 0

  df_filtrado = df_lancamentos[
      (df_lancamentos["motoboy_id"].astype(str) == str(motoboy_id))
      & (df_lancamentos["data"].astype(str) == data_str)
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
      else int(pd.to_numeric(df_lancamentos["id"], errors="coerce").max()) + 1
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

  df_lancamentos = pd.concat([df_lancamentos, nova_rota], ignore_index=True)
  return salvar_tabela("lancamentos", df_lancamentos)


def deletar_rota(rota_id):
  global df_lancamentos
  df_lancamentos = df_lancamentos[
      df_lancamentos["id"].astype(str) != str(rota_id)
  ]
  return salvar_tabela("lancamentos", df_lancamentos)


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
    motoboy_id = df_m[df_m["nome"] == motoboy_selecionado]["id"].values[0]

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
      if adicionar_rota(
          motoboy_id, data_str, qtd_nova_rota, valor_final_rota, obs
      ):
        st.success(
            f"Rota de {qtd_nova_rota} pacotes adicionada para"
            f" {motoboy_selecionado}!"
        )
        st.rerun()
