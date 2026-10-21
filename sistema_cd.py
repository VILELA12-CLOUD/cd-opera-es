import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão de Logística & Motoboys", page_icon="🚚", layout="wide"
)

PRECO_PADRAO_PACOTE = 1.80


# --- BANCO DE DADOS (SQLite Local com atualização automática de schema) ---
def init_db():
  conn = sqlite3.connect("logistica_cd.db")
  cursor = conn.cursor()

  # Tabela de Motoboys
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS motoboys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            email TEXT,
            telefone TEXT,
            cnh TEXT,
            placa TEXT,
            ativo INTEGER DEFAULT 1
        )
    """)

  # Tabela de Lançamentos por Rota
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            motoboy_id INTEGER,
            data TEXT,
            qtd_pacotes INTEGER,
            valor_calculado REAL,
            valor_final REAL,
            observacao TEXT,
            hora TEXT,
            FOREIGN KEY (motoboy_id) REFERENCES motoboys (id)
        )
    """)

  # Tenta adicionar a coluna 'hora' caso o banco venha da versão anterior
  try:
    cursor.execute("ALTER TABLE lancamentos ADD COLUMN hora TEXT")
  except sqlite3.OperationalError:
    pass  # A coluna já existe, ignora o erro

  conn.commit()
  conn.close()


init_db()


# --- FUNÇÕES DE SUPORTE ---
def obter_motoboys(apenas_ativos=True):
  conn = sqlite3.connect("logistica_cd.db")
  query = (
      "SELECT id, nome, email, telefone, cnh, placa FROM motoboys WHERE ativo = 1"
      if apenas_ativos
      else "SELECT id, nome, email, telefone, cnh, placa, ativo FROM motoboys"
  )
  df = pd.read_sql_query(query, conn)
  conn.close()
  return df


def salvar_motoboy(nome, email, telefone, cnh, placa):
  conn = sqlite3.connect("logistica_cd.db")
  cursor = conn.cursor()
  try:
    cursor.execute(
        """
            INSERT INTO motoboys (nome, email, telefone, cnh, placa)
            VALUES (?, ?, ?, ?, ?)
        """,
        (nome, email, telefone, cnh, placa),
    )
    conn.commit()
    sucesso = True
  except sqlite3.IntegrityError:
    sucesso = False
  conn.close()
  return sucesso


def obter_totais_dia_motoboy(motoboy_id, data_str):
  conn = sqlite3.connect("logistica_cd.db")
  cursor = conn.cursor()
  cursor.execute(
      """
        SELECT SUM(qtd_pacotes), SUM(valor_final), COUNT(id)
        FROM lancamentos 
        WHERE motoboy_id = ? AND data = ?
    """,
      (motoboy_id, data_str),
  )
  res = cursor.fetchone()
  conn.close()
  total_pacotes = res[0] if res[0] is not None else 0
  total_valor = res[1] if res[1] is not None else 0.0
  total_rotas = res[2] if res[2] is not None else 0
  return total_pacotes, total_valor, total_rotas


def adicionar_rota(
    motoboy_id, data_str, qtd_pacotes_nova_rota, valor_final_nova_rota, obs=""
):
  conn = sqlite3.connect("logistica_cd.db")
  cursor = conn.cursor()
  valor_calc = qtd_pacotes_nova_rota * PRECO_PADRAO_PACOTE
  hora_atual = datetime.now().strftime("%H:%M:%S")

  cursor.execute(
      """
        INSERT INTO lancamentos (motoboy_id, data, qtd_pacotes, valor_calculado, valor_final, observacao, hora)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
      (
          motoboy_id,
          data_str,
          qtd_pacotes_nova_rota,
          valor_calc,
          valor_final_nova_rota,
          obs,
          hora_atual,
      ),
  )

  conn.commit()
  conn.close()


def deletar_rota(rota_id):
  conn = sqlite3.connect("logistica_cd.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM lancamentos WHERE id = ?", (rota_id,))
  conn.commit()
  conn.close()


def relatorio_diario_agrupado(data_str):
  conn = sqlite3.connect("logistica_cd.db")
  query = """
        SELECT 
            m.nome AS Motoboy, 
            COUNT(l.id) AS "Qtd. Rotas",
            SUM(l.qtd_pacotes) AS "Total Pacotes", 
            SUM(l.valor_calculado) AS "Valor Padrão (R$)", 
            SUM(l.valor_final) AS "Valor Total (R$)"
        FROM lancamentos l
        JOIN motoboys m ON l.motoboy_id = m.id
        WHERE l.data = ?
        GROUP BY m.id
    """
  df = pd.read_sql_query(query, conn, params=(data_str,))
  conn.close()
  return df


def detalhe_rotas_dia(data_str):
  conn = sqlite3.connect("logistica_cd.db")
  query = """
        SELECT 
            l.id AS Rota_ID,
            m.nome AS Motoboy,
            COALESCE(l.hora, '--:--') AS "Hora Lançamento",
            l.qtd_pacotes AS "Pacotes na Rota",
            l.valor_final AS "Valor Rota (R$)",
            l.observacao AS "Observação"
        FROM lancamentos l
        JOIN motoboys m ON l.motoboy_id = m.id
        WHERE l.data = ?
        ORDER BY l.id DESC
    """
  df = pd.read_sql_query(query, conn, params=(data_str,))
  conn.close()
  return df


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
          f" registrada(s) hoje. Total acumulado: **{pacotes_acumulados}"
          f" pacotes** (R$ {valor_acumulado:.2f})."
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
  st.subheader(f"📋 Resumo Geral do Dia: {data_str}")

  df_dia = relatorio_diario_agrupado(data_str)

  if not df_dia.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Total de Pacotes do Dia", int(df_dia["Total Pacotes"].sum()))
    m2.metric(
        "💰 Total a Pagar no Dia", f"R$ {df_dia['Valor Total (R$)'].sum():.2f}"
    )
    m3.metric("🛵 Motoboys Ativos Hoje", len(df_dia))

    st.write("##### Resumo Acumulado por Motoboy")
    st.dataframe(df_dia, use_container_width=True)

    with st.expander("🔍 Histórico detalhado / Excluir rota lançada incorretamente"):
      df_detalhe = detalhe_rotas_dia(data_str)
      
      for idx, row in df_detalhe.iterrows():
        c1, c2, c3, c4, c5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
        c1.write(f"**{row['Motoboy']}**")
        c2.write(f"🕒 {row['Hora Lançamento']}")
        c3.write(f"📦 {row['Pacotes na Rota']} pct(s)")
        c4.write(f"💰 R$ {row['Valor Rota (R$)']:.2f}")
        if c5.button("🗑️ Excluir", key=f"del_rota_{row['Rota_ID']}"):
          deletar_rota(row['Rota_ID'])
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
  conn = sqlite3.connect("logistica_cd.db")
  df_geral = pd.read_sql_query(
      """
        SELECT l.data AS Data, m.nome AS Motoboy, SUM(l.qtd_pacotes) AS Pacotes, SUM(l.valor_final) AS Valor
        FROM lancamentos l JOIN motoboys m ON l.motoboy_id = m.id
        GROUP BY l.data, m.id
        ORDER BY l.data DESC
    """,
      conn,
  )
  conn.close()

  if not df_geral.empty:
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

  conn = sqlite3.connect("logistica_cd.db")
  df_fechamento = pd.read_sql_query(
      """
        SELECT m.nome AS Motoboy, 
               SUM(l.qtd_pacotes) AS Total_Pacotes, 
               SUM(l.valor_final) AS Total_A_Pagar
        FROM lancamentos l
        JOIN motoboys m ON l.motoboy_id = m.id
        WHERE l.data LIKE ?
        GROUP BY m.id
    """,
      conn,
      params=(f"{prefixo_data}%",),
  )
  conn.close()

  if not df_fechamento.empty:
    st.dataframe(df_fechamento, use_container_width=True)
    csv = df_fechamento.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Baixar Relatório em CSV/Excel",
        csv,
        f"fechamento_{prefixo_data}.csv",
        "text/csv",
    )
  else:
    st.info(f"Sem dados registrados para o mês {mes}/{ano}.")