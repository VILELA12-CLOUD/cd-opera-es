from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard de Logística - CD", page_icon="🚚", layout="wide"
)

PRECO_PADRAO_PACOTE = 1.80
FUSO_SP = ZoneInfo("America/Sao_Paulo")

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)


# --- FUNÇÕES DE BANCO DE DADOS (BANCO DE DADOS/SHEETS) ---
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


# --- INICIALIZAÇÃO DE DADOS ---
if "df_motoboys" not in st.session_state:
  st.session_state.df_motoboys = ler_tabela("motoboys")

if "df_lancamentos" not in st.session_state:
  st.session_state.df_lancamentos = ler_tabela("lancamentos")


def recarregar_dados():
  st.session_state.df_motoboys = ler_tabela("motoboys")
  st.session_state.df_lancamentos = ler_tabela("lancamentos")


# --- ESTRUTURA MÍNIMA DE COLUNAS ---
if (
    st.session_state.df_motoboys.empty
    or "nome" not in st.session_state.df_motoboys.columns
):
  st.session_state.df_motoboys = pd.DataFrame(
      columns=["id", "nome", "email", "telefone", "cnh", "placa", "ativo"]
  )

if (
    st.session_state.df_lancamentos.empty
    or "motoboy_id" not in st.session_state.df_lancamentos.columns
):
  st.session_state.df_lancamentos = pd.DataFrame(
      columns=[
          "id",
          "motoboy_id",
          "data",
          "qtd_pacotes",
          "qtd_insucesso",
          "valor_calculado",
          "valor_final",
          "observacao",
          "hora",
      ]
  )


# --- FUNÇÕES DE REGRAS DE NEGÓCIO ---
def obter_motoboys_ativos():
  df_m = st.session_state.df_motoboys
  if df_m.empty or "nome" not in df_m.columns:
    return pd.DataFrame()
  if "ativo" in df_m.columns:
    ativo_str = df_m["ativo"].astype(str).str.strip().str.lower()
    return df_m[~ativo_str.isin(["0", "false", "0.0"])]
  return df_m


def salvar_novo_motoboy(nome, email, telefone, cnh, placa):
  df_m = st.session_state.df_motoboys
  if not df_m.empty and "nome" in df_m.columns:
    if nome.strip().lower() in df_m["nome"].astype(str).str.lower().values:
      st.warning("Já existe um motoboy cadastrado com este nome.")
      return False

  novo_id = (
      1
      if df_m.empty or "id" not in df_m.columns
      else int(pd.to_numeric(df_m["id"], errors="coerce").max()) + 1
  )
  novo_registro = pd.DataFrame([{
      "id": str(novo_id),
      "nome": str(nome).strip(),
      "email": str(email).strip(),
      "telefone": str(telefone).strip(),
      "cnh": str(cnh).strip(),
      "placa": str(placa).strip().upper(),
      "ativo": "1",
  }])

  df_atualizado = pd.concat([df_m, novo_registro], ignore_index=True)
  if salvar_tabela("motoboys", df_atualizado):
    st.session_state.df_motoboys = df_atualizado
    return True
  return False


def atualizar_motoboy(mb_id, nome, email, telefone, cnh, placa, ativo):
  df_m = st.session_state.df_motoboys.copy()
  idx = df_m[df_m["id"].astype(str) == str(mb_id)].index
  if not idx.empty:
    df_m.loc[idx, "nome"] = str(nome).strip()
    df_m.loc[idx, "email"] = str(email).strip()
    df_m.loc[idx, "telefone"] = str(telefone).strip()
    df_m.loc[idx, "cnh"] = str(cnh).strip()
    df_m.loc[idx, "placa"] = str(placa).strip().upper()
    df_m.loc[idx, "ativo"] = "1" if ativo else "0"

    if salvar_tabela("motoboys", df_m):
      st.session_state.df_motoboys = df_m
      return True
  return False


def excluir_motoboy(mb_id):
  df_m = st.session_state.df_motoboys.copy()
  df_m = df_m[df_m["id"].astype(str) != str(mb_id)]
  if salvar_tabela("motoboys", df_m):
    st.session_state.df_motoboys = df_m
    return True
  return False


def adicionar_rota(
    motoboy_id,
    data_str,
    qtd_pacotes,
    qtd_insucesso,
    valor_final_manual,
    obs="",
):
  df_l = st.session_state.df_lancamentos
  novo_id = (
      1
      if df_l.empty or "id" not in df_l.columns
      else int(pd.to_numeric(df_l["id"], errors="coerce").max()) + 1
  )

  pacotes_entregues = max(0, qtd_pacotes - qtd_insucesso)
  valor_calc = round(pacotes_entregues * PRECO_PADRAO_PACOTE, 2)
  valor_final = (
      round(valor_final_manual, 2)
      if valor_final_manual > 0
      else round(valor_calc, 2)
  )

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
  if salvar_tabela("lancamentos", df_atualizado):
    st.session_state.df_lancamentos = df_atualizado
    return True
  return False


def deletar_rota(rota_id):
  df_l = st.session_state.df_lancamentos.copy()
  df_atualizado = df_l[df_l["id"].astype(str) != str(rota_id)]
  if salvar_tabela("lancamentos", df_atualizado):
    st.session_state.df_lancamentos = df_atualizado
    return True
  return False


# --- HEADER DO DASHBOARD ---
st.title("🚚 Dashboard de Operações & Logística do CD")
if st.button("🔄 Sincronizar / Atualizar Dados da Planilha"):
  recarregar_dados()
  st.toast("Dados atualizados!")
  st.rerun()

st.divider()

# --- NAVEGAÇÃO POR ABAS ---
aba_lancamentos, aba_cadastro, aba_fechamento_dia, aba_periodos = st.tabs([
    "📝 Lançamento de Rotas",
    "🏍️ Gestão de Motoboys",
    "📋 Fechamento Diário",
    "📊 Relatórios Semanal & Mensal",
])

# -------------------------------------------------------------
# ABA 1: LANÇAMENTO DE ROTAS
# -------------------------------------------------------------
with aba_lancamentos:
  st.subheader("Lançamento de Volumes por Rota")

  data_operacao = st.date_input(
      "Data da Operação", datetime.now(FUSO_SP).date()
  )
  data_str = str(data_operacao)
  data_br = data_operacao.strftime("%d/%m/%Y")

  df_m_ativos = obter_motoboys_ativos()

  if df_m_ativos.empty:
    st.warning(
        "Nenhum motoboy ativo encontrado. Cadastre um motorista na aba 'Gestão"
        " de Motoboys'."
    )
  else:
    motoboy_selecionado = st.selectbox(
        "Selecione o Motoboy", df_m_ativos["nome"].tolist()
    )
    motoboy_id = df_m_ativos[df_m_ativos["nome"] == motoboy_selecionado][
        "id"
    ].values[0]

    # Verificar acumulado do dia
    df_l = st.session_state.df_lancamentos
    df_mot_hoje = df_l[
        (df_l["motoboy_id"].astype(str) == str(motoboy_id))
        & (df_l["data"].astype(str) == data_str)
    ]

    rotas_hoje = len(df_mot_hoje)
    pacotes_hoje = (
        pd.to_numeric(df_mot_hoje.get("qtd_pacotes", 0), errors="coerce")
        .sum()
        if not df_mot_hoje.empty
        else 0
    )
    insucesso_hoje = (
        pd.to_numeric(df_mot_hoje.get("qtd_insucesso", 0), errors="coerce")
        .sum()
        if not df_mot_hoje.empty
        else 0
    )
    valor_hoje = (
        pd.to_numeric(df_mot_hoje.get("valor_final", 0), errors="coerce").sum()
        if not df_mot_hoje.empty
        else 0.0
    )

    if rotas_hoje > 0:
      st.info(
          f"📌 **{motoboy_selecionado}** já realizou **{rotas_hoje} rota(s)**"
          f" hoje ({data_br}). Acumulado: **{int(pacotes_hoje)} pacotes** |"
          f" Devoluções: **{int(insucesso_hoje)}** | Total a pagar:"
          f" **R$ {valor_hoje:.2f}**"
      )

    st.write("---")
    st.markdown("#### ➕ Registrar Nova Saída")

    with st.form("form_nova_rota", clear_on_submit=True):
      col1, col2, col3, col4 = st.columns(4)
      with col1:
        qtd_saida = st.number_input(
            "Pacotes de Saída", min_value=1, value=1, step=1
        )
      with col2:
        qtd_insuc = st.number_input(
            "Insucessos / Retorno", min_value=0, value=0, step=1
        )
      with col3:
        pct_entregues = max(0, qtd_saida - qtd_insuc)
        val_sugerido = round(pct_entregues * PRECO_PADRAO_PACOTE, 2)
        st.metric(
            f"Calculado ({pct_entregues} pct)", f"R$ {val_sugerido:.2f}"
        )
      with col4:
        valor_final_input = st.number_input(
            "Valor Final (Editável)",
            min_value=0.0,
            value=float(val_sugerido),
            format="%.2f",
        )

      obs_input = st.text_input(
          "Observação da Rota (Ex: Rota 2 Zona Norte, Bônus, Chuva, etc.)"
      )
      btn_salvar = st.form_submit_button("💾 Salvar Rota")

      if btn_salvar:
        if adicionar_rota(
            motoboy_id,
            data_str,
            qtd_saida,
            qtd_insuc,
            valor_final_input,
            obs_input,
        ):
          st.toast(
              f"✅ Rota salva com sucesso para {motoboy_selecionado}!"
          )
          st.rerun()

# -------------------------------------------------------------
# ABA 2: GESTÃO DE MOTOBOYS (CADASTRO, EDIÇÃO E EXCLUSÃO)
# -------------------------------------------------------------
with aba_cadastro:
  st.subheader("Cadastrar / Editar Motoboys")

  sub_tab1, sub_tab2 = st.tabs(
      ["➕ Novo Motoboy", "✏️ Editar / Excluir Motoboy"]
  )

  with sub_tab1:
    with st.form("form_cad_motoboy", clear_on_submit=True):
      c1, c2 = st.columns(2)
      with c1:
        nome_mb = st.text_input("Nome Completo*")
        email_mb = st.text_input("E-mail")
        tel_mb = st.text_input("Telefone / WhatsApp")
      with c2:
        cnh_mb = st.text_input("Número da CNH")
        placa_mb = st.text_input("Placa da Moto")

      btn_cad = st.form_submit_button("💾 Salvar Motoboy")
      if btn_cad:
        if nome_mb.strip():
          if salvar_novo_motoboy(
              nome_mb, email_mb, tel_mb, cnh_mb, placa_mb
          ):
            st.toast(f"✅ {nome_mb} cadastrado com sucesso!")
            st.rerun()
        else:
          st.error("O Nome Completo é obrigatório.")

  with sub_tab2:
    df_m_todos = st.session_state.df_motoboys
    if df_m_todos.empty or "nome" not in df_m_todos.columns:
      st.info("Nenhum motoboy cadastrado para edição.")
    else:
      mb_para_editar = st.selectbox(
          "Selecione o Motoboy para alterar dados", df_m_todos["nome"].tolist()
      )
      dados_mb = df_m_todos[df_m_todos["nome"] == mb_para_editar].iloc[0]

      with st.form("form_edit_motoboy"):
        e1, e2 = st.columns(2)
        with e1:
          e_nome = st.text_input("Nome Completo", value=str(dados_mb["nome"]))
          e_email = st.text_input("E-mail", value=str(dados_mb.get("email", "")))
          e_tel = st.text_input(
              "Telefone / WhatsApp", value=str(dados_mb.get("telefone", ""))
          )
        with e2:
          e_cnh = st.text_input("CNH", value=str(dados_mb.get("cnh", "")))
          e_placa = st.text_input("Placa", value=str(dados_mb.get("placa", "")))
          e_ativo = st.checkbox(
              "Motoboy Ativo?",
              value=str(dados_mb.get("ativo", "1")).strip().lower()
              not in ["0", "false"],
          )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
          btn_atualizar = st.form_submit_button("✏️ Atualizar Dados")
        with col_btn2:
          btn_excluir = st.form_submit_button("🗑️ Excluir Motoboy")

        if btn_atualizar:
          if atualizar_motoboy(
              dados_mb["id"],
              e_nome,
              e_email,
              e_tel,
              e_cnh,
              e_placa,
              e_ativo,
          ):
            st.toast("✅ Dados atualizados com sucesso!")
            st.rerun()

        if btn_excluir:
          if excluir_motoboy(dados_mb["id"]):
            st.toast("🗑️ Motoboy removido!")
            st.rerun()

  st.divider()
  st.write("#### Lista Geral de Motoboys Cadastrados")
  st.dataframe(st.session_state.df_motoboys, width="stretch")

# -------------------------------------------------------------
# ABA 3: FECHAMENTO DIÁRIO E RESUMO
# -------------------------------------------------------------
with aba_fechamento_dia:
  st.subheader("📋 Fechamento da Operação do Dia")

  data_fechamento = st.date_input(
      "Selecione o Dia para Fechamento", datetime.now(FUSO_SP).date()
  )
  d_str = str(data_fechamento)
  d_br = data_fechamento.strftime("%d/%m/%Y")

  df_l_geral = st.session_state.df_lancamentos
  df_m_geral = st.session_state.df_motoboys

  if not df_l_geral.empty and "data" in df_l_geral.columns:
    df_dia = df_l_geral[df_l_geral["data"].astype(str) == d_str]
  else:
    df_dia = pd.DataFrame()

  if not df_dia.empty and not df_m_geral.empty:
    df_merged = df_dia.merge(
        df_m_geral, left_on="motoboy_id", right_on="id", suffixes=("", "_mb")
    )

    df_merged["qtd_pacotes"] = pd.to_numeric(
        df_merged["qtd_pacotes"], errors="coerce"
    ).fillna(0)
    df_merged["qtd_insucesso"] = pd.to_numeric(
        df_merged.get("qtd_insucesso", 0), errors="coerce"
    ).fillna(0)
    df_merged["valor_final"] = (
        pd.to_numeric(df_merged["valor_final"], errors="coerce")
        .fillna(0.0)
        .round(2)
    )

    df_agrupado = (
        df_merged.groupby("nome")
        .agg(
            Qtd_Rotas=("id", "count"),
            Pacotes_Saida=("qtd_pacotes", "sum"),
            Insucessos=("qtd_insucesso", "sum"),
            Valor_Total=("valor_final", "sum"),
        )
        .reset_index()
    )

    df_agrupado["Pacotes_Entregues"] = (
        df_agrupado["Pacotes_Saida"] - df_agrupado["Insucessos"]
    )
    df_agrupado.columns = [
        "Motoboy",
        "Qtd. Rotas",
        "Pacotes Saída",
        "Insucessos",
        "Valor Total (R$)",
        "Pacotes Entregues",
    ]

    # Reordenar colunas
    df_agrupado = df_agrupado[[
        "Motoboy",
        "Qtd. Rotas",
        "Pacotes Saída",
        "Insucessos",
        "Pacotes Entregues",
        "Valor Total (R$)",
    ]]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📦 Saída Total", int(df_agrupado["Pacotes Saída"].sum()))
    m2.metric("❌ Total Insucessos", int(df_agrupado["Insucessos"].sum()))
    m3.metric(
        "✅ Total Entregue", int(df_agrupado["Pacotes Entregues"].sum())
    )
    m4.metric(
        "💰 Total do Dia (R$)", f"R$ {df_agrupado['Valor Total (R$)'].sum():.2f}"
    )

    st.write("##### Resumo do Dia por Motoboy")
    st.dataframe(df_agrupado, width="stretch")

    with st.expander("🔍 Detalhes / Excluir Lançamentos Específicos"):
      for idx, row in df_merged.iterrows():
        col_a, col_b, col_c, col_d, col_e = st.columns(
            [0.25, 0.15, 0.2, 0.2, 0.2]
        )
        col_a.write(f"**{row['nome']}**")
        col_b.write(f"🕒 {row.get('hora', '--:--')}")
        col_c.write(
            f"📦 {int(row['qtd_pacotes'])} pct(s) | Retorno:"
            f" {int(row['qtd_insucesso'])}"
        )
        col_d.write(f"💰 R$ {row['valor_final']:.2f}")
        if col_e.button("🗑️ Excluir Rota", key=f"del_r_{row['id']}"):
          if deletar_rota(row["id"]):
            st.toast("Rota excluída!")
            st.rerun()
        st.write("---")
  else:
    st.info(f"Nenhum lançamento registrado para {d_br}.")

# -------------------------------------------------------------
# ABA 4: RELATÓRIOS SEMANAL E MENSAL
# -------------------------------------------------------------
with aba_periodos:
  st.subheader("📊 Análise e Fechamento por Período")

  tipo_relatorio = st.radio(
      "Selecione o Tipo de Análise",
      ["Fechamento Semanal", "Fechamento Mensal"],
      horizontal=True,
  )

  df_l_periodo = st.session_state.df_lancamentos.copy()
  df_m_periodo = st.session_state.df_motoboys.copy()

  if not df_l_periodo.empty and not df_m_periodo.empty:
    df_l_periodo["data_dt"] = pd.to_datetime(
        df_l_periodo["data"], errors="coerce"
    )

    if tipo_relatorio == "Fechamento Semanal":
      st.write("##### Selecione o Período da Semana")
      dt_inicio = st.date_input(
          "Data Inicial", datetime.now(FUSO_SP).date() - timedelta(days=7)
      )
      dt_fim = st.date_input("Data Final", datetime.now(FUSO_SP).date())

      df_filtrado_p = df_l_periodo[
          (df_l_periodo["data_dt"].dt.date >= dt_inicio)
          & (df_l_periodo["data_dt"].dt.date <= dt_fim)
      ]
      nome_relatorio = f"fechamento_semanal_{dt_inicio}_a_{dt_fim}.csv"
    else:
      st.write("##### Selecione o Mês de Referência")
      col_m, col_a = st.columns(2)
      with col_m:
        mes_sel = st.selectbox(
            "Mês", list(range(1, 13)), index=datetime.now(FUSO_SP).month - 1
        )
      with col_a:
        ano_sel = st.number_input(
            "Ano", min_value=2024, value=datetime.now(FUSO_SP).year
        )

      prefixo = f"{ano_sel}-{mes_sel:02d}"
      df_filtrado_p = df_l_periodo[
          df_l_periodo["data"].astype(str).str.startswith(prefixo)
      ]
      nome_relatorio = f"fechamento_mensal_{prefixo}.csv"

    if not df_filtrado_p.empty:
      df_f_merged = df_filtrado_p.merge(
          df_m_periodo, left_on="motoboy_id", right_on="id"
      )

      df_f_merged["qtd_pacotes"] = pd.to_numeric(
          df_f_merged["qtd_pacotes"], errors="coerce"
      ).fillna(0)
      df_f_merged["qtd_insucesso"] = pd.to_numeric(
          df_f_merged.get("qtd_insucesso", 0), errors="coerce"
      ).fillna(0)
      df_f_merged["valor_final"] = (
          pd.to_numeric(df_f_merged["valor_final"], errors="coerce")
          .fillna(0.0)
          .round(2)
      )

      df_p_agrupado = (
          df_f_merged.groupby("nome")
          .agg(
              Total_Rotas=("id", "count"),
              Total_Pacotes_Saida=("qtd_pacotes", "sum"),
              Total_Insucessos=("qtd_insucesso", "sum"),
              Total_A_Pagar=("valor_final", "sum"),
          )
          .reset_index()
      )

      df_p_agrupado["Pacotes_Entregues"] = (
          df_p_agrupado["Total_Pacotes_Saida"]
          - df_p_agrupado["Total_Insucessos"]
      )
      df_p_agrupado.columns = [
          "Motoboy",
          "Total Rotas",
          "Pacotes Saída",
          "Insucessos",
          "Total A Pagar (R$)",
          "Pacotes Entregues",
      ]

      df_p_agrupado = df_p_agrupado[[
          "Motoboy",
          "Total Rotas",
          "Pacotes Saída",
          "Insucessos",
          "Pacotes Entregues",
          "Total A Pagar (R$)",
      ]]

      st.dataframe(df_p_agrupado, width="stretch")

      csv_data = df_p_agrupado.to_csv(index=False).encode("utf-8")
      st.download_button(
          "📥 Baixar Relatório do Período em CSV/Excel",
          csv_data,
          nome_relatorio,
          "text/csv",
      )
    else:
      st.info("Nenhum lançamento encontrado para o período selecionado.")
  else:
    st.info("Sem dados suficientes para gerar os relatórios do período.")
