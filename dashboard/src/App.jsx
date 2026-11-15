import React, { useEffect, useState } from "react";
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from "recharts";

const nf = (v, d = 1) => (v == null ? "—" : v.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (v, d = 1) => (v == null ? "—" : nf(v, d) + "%");
const brl = (v) => {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return "R$ " + nf(v / 1e9, 2) + " bi";
  if (a >= 1e6) return "R$ " + nf(v / 1e6, 0) + " mi";
  return "R$ " + nf(v, 0);
};
const SERIE = { A: "var(--series-1)", B: "var(--series-2)", C: "var(--series-3)" };
const tip = { contentStyle: { background: "var(--surface-1)", border: "1px solid var(--border-strong)", borderRadius: 4, fontSize: 13, color: "var(--text-primary)", boxShadow: "var(--shadow)" }, labelStyle: { color: "var(--text-secondary)" }, itemStyle: { color: "var(--text-primary)" } };
const axis = { tick: { fill: "var(--text-secondary)", fontSize: 12 }, axisLine: { stroke: "var(--border)" }, tickLine: false };
const NOME_CAT = { "TIC (família completa)": "Família TIC", "NUVEM+IA": "Nuvem + IA" };

export default function App() {
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState(null);
  const [versao, setVersao] = useState("com_estatais");
  useEffect(() => {
    fetch("data/dados.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(setDados).catch((e) => setErro(String(e)));
  }, []);
  if (erro) return <div className="wrap"><div className="banner warn"><b>Dados não encontrados.</b> Rode <code>python analise.py</code> na pasta <code>etl</code> para gerar <code>dashboard/public/data/dados.json</code> e recarregue a página.</div></div>;
  if (!dados) return <div className="wrap">Carregando…</div>;
  const v = dados.versoes[versao], meta = dados.meta, b = v.idt_bienio;
  return (
    <>
    <header className="masthead"><div className="masthead-in">
        <div>
          <p className="eyebrow">Contratações federais de TI · {meta.janela[0]} — {meta.janela[1]}</p>
          <h1>Índice de Dependência Tecnológica (IDT)</h1>
          <p className="sub">Contratos federais de TI, {meta.janela[0]} a {meta.janela[1]} ({nf(meta.contratos_familia_tic, 0)} contratos da família TIC). Estudo descritivo e exploratório; não mede causalidade.</p>
        </div>
        <div>
          <span className="seg-label">Estatais de TIC (Serpro, Dataprev, Telebras)</span>
          <div className="seg" role="group" aria-label="Estatais">
            <button aria-pressed={versao === "com_estatais"} onClick={() => setVersao("com_estatais")}>Com estatais</button>
            <button aria-pressed={versao === "sem_estatais"} onClick={() => setVersao("sem_estatais")}>Sem estatais</button>
          </div>
        </div>
    </div></header>
    <main className="wrap">
      {meta.sintetico && <div className="banner test"><b>DADOS DE TESTE (sintéticos).</b> Nada aqui é resultado da pesquisa. Rode <code>python analise.py</code> para gerar os dados reais.</div>}
      <div className="banner warn">As estatais concentram {pct(meta.estatais.pct_valor_tic)} do valor de TI ({meta.estatais.contratos} contratos); por isso toda leitura vem com e sem elas. “Dependente” = sócio estrangeiro na cadeia societária (B) ou marca/intermediação de hyperscaler via fornecedor nacional (C). Presença de capital não é controle nem origem da tecnologia.</div>

      <div className="kpis">
        <div className="kpi"><div className="l">IDT do biênio</div><div className="v">{pct(b.idt)}</div><div className="s">valor dependente ÷ valor total de TI</div></div>
        <div className="kpi"><div className="l">Valor dependente (B ou C)</div><div className="v">{brl(b.valor_dep)}</div><div className="s">de {brl(b.valor_tic)} em TI</div></div>
        <div className="kpi"><div className="l">Cenário W1 · W2</div><div className="v">{pct(b.idt_W1)} · {pct(b.idt_W2)}</div><div className="s">sensibilidade, pesos não calibrados</div></div>
      </div>

      <IdtMensal v={v} />
      <Categorias v={v} />
      <Fornecedores v={v} />
      <Anpd v={v} />

      <div className="card">
        <h2>Limitações</h2>
        <ul className="lim">
          <li>O QSA não informa percentual de capital; em sociedades anônimas lista administradores, não acionistas. A medida B indica presença, não controle.</li>
          <li>A medida C depende de marca no texto do objeto; revendas nacionais e o multicloud do Serpro aparecem como nacionais.</li>
          <li>O valor global do contrato entra inteiro no mês de início da vigência; a razão mensal oscila muito, e a leitura principal é a do biênio.</li>
          <li>Incidentes da ANPD misturam União, estados e municípios; com n = 24 meses só correlações fortes (|rho| ≥ ~0,55) são detectáveis.</li>
          <li>A classificação por palavras-chave foi validada em amostra de 240 contratos; as regras foram ajustadas nessa amostra.</li>
        </ul>
      </div>
      <footer>Gerado em {meta.gerado_em.replace("T", " ")}. Fonte: Compras.gov.br (contratos), Receita Federal via BrasilAPI/publica.cnpj.ws (QSA), ANPD (incidentes). Código e método: ver README do projeto.</footer>
    </main>
    </>
  );
}

function Card({ titulo, sub, children, tabela, nota }) {
  const [t, setT] = useState(false);
  return (
    <section className="card">
      <div className="head"><div><h2>{titulo}</h2>{sub && <p className="sub" style={{ marginBottom: 8 }}>{sub}</p>}</div>
        <button className="tbtn" onClick={() => setT(!t)} aria-pressed={t}>{t ? "Ver gráfico" : "Ver tabela"}</button></div>
      {t ? tabela : children}
      {nota && <p className="note">{nota}</p>}
    </section>
  );
}
const Legend = ({ items }) => <div className="legend">{items.map(([c, l]) => <span key={l}><i style={{ background: c }} />{l}</span>)}</div>;

function IdtMensal({ v }) {
  const d = v.idt_mensal.map((r) => ({ mes: r.mes, idt: r.idt }));
  const ref = v.idt_bienio.idt;
  return (
    <Card titulo="IDT por mês" sub="Valor dependente ÷ valor total de TI em cada mês (mês de início da vigência). A linha tracejada é o IDT do biênio."
      nota="Meses sem contratos aparecem como lacuna. A oscilação vem de poucos contratos grandes entrando inteiros no mês de início."
      tabela={<table><thead><tr><th>Mês</th><th>Contratos</th><th>Valor de TI</th><th>Valor dependente</th><th>IDT</th></tr></thead><tbody>
        {v.idt_mensal.map((r) => <tr key={r.mes}><td>{r.mes}</td><td>{nf(r.contratos, 0)}</td><td>{brl(r.valor_tic)}</td><td>{brl(r.valor_dep)}</td><td>{pct(r.idt)}</td></tr>)}</tbody></table>}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={d} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} /><XAxis dataKey="mes" {...axis} interval={2} /><YAxis {...axis} domain={[0, 100]} unit="%" width={44} />
          <ReferenceLine y={ref} stroke="var(--neutral)" strokeDasharray="5 4" label={{ value: `Biênio ${nf(ref)}%`, position: "insideTopRight", fill: "var(--text-secondary)", fontSize: 12 }} />
          <Tooltip {...tip} formatter={(x) => [pct(x), "IDT"]} />
          <Line type="linear" dataKey="idt" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 }} activeDot={{ r: 6 }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Categorias({ v }) {
  const d = v.categorias.map((r) => ({ cat: NOME_CAT[r.categoria] || r.categoria, A: r.pct_valor_A, B: r.pct_valor_B, C: r.pct_valor_C, n: r.contratos, valor: r.valor_total }));
  return (
    <Card titulo="Dependência por categoria e por definição" sub="Participação no valor contratado em cada categoria, segundo cada definição. B inclui A; A, B e C não se somam."
      nota="A baixa participação de A mostra que a dependência direta de hyperscalers é pequena; a de C mostra o peso da dependência indireta em nuvem e IA."
      tabela={<table><thead><tr><th>Categoria</th><th>Contratos</th><th>Valor</th><th>A</th><th>B</th><th>C</th></tr></thead><tbody>
        {d.map((r) => <tr key={r.cat}><td>{r.cat}</td><td>{nf(r.n, 0)}</td><td>{brl(r.valor)}</td><td>{pct(r.A)}</td><td>{pct(r.B)}</td><td>{pct(r.C)}</td></tr>)}</tbody></table>}>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={d} margin={{ top: 8, right: 16, bottom: 0, left: 0 }} barGap={2}>
          <CartesianGrid vertical={false} /><XAxis dataKey="cat" {...axis} /><YAxis {...axis} unit="%" width={44} />
          <Tooltip {...tip} formatter={(x, n) => [pct(x), { A: "A: fornecedor hyperscaler", B: "B: sócio estrangeiro", C: "C: marca via fornecedor nacional" }[n]]} cursor={{ fill: "var(--border)", opacity: 0.35 }} />
          <Bar dataKey="A" fill={SERIE.A} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
          <Bar dataKey="B" fill={SERIE.B} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
          <Bar dataKey="C" fill={SERIE.C} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <Legend items={[[SERIE.A, "A: fornecedor hyperscaler"], [SERIE.B, "B: sócio estrangeiro na cadeia"], [SERIE.C, "C: marca via fornecedor nacional"]]} />
    </Card>
  );
}

function Fornecedores({ v }) {
  const c = v.concentracao;
  const d = c.top.map((r) => ({ nome: r.razao_social.length > 44 ? r.razao_social.slice(0, 43) + "…" : r.razao_social, pct: r.pct_do_valor_nuvem_ia, completo: r.razao_social }));
  return (
    <Card titulo="Maiores fornecedores de nuvem e IA" sub={`Parte do valor de nuvem e IA. Os 3 maiores somam ${pct(c.top3_pct)}; HHI = ${nf(c.hhi, 0)}.`}
      tabela={<table><thead><tr><th>Fornecedor</th><th>% do valor</th></tr></thead><tbody>{d.map((r) => <tr key={r.completo}><td>{r.completo}</td><td>{pct(r.pct)}</td></tr>)}</tbody></table>}>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={d} layout="vertical" margin={{ top: 4, right: 24, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} /><XAxis type="number" {...axis} unit="%" /><YAxis type="category" dataKey="nome" {...axis} width={300} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
          <Tooltip {...tip} formatter={(x) => [pct(x), "do valor de nuvem e IA"]} labelFormatter={(_, p) => p?.[0]?.payload?.completo} cursor={{ fill: "var(--border)", opacity: 0.35 }} />
          <Bar dataKey="pct" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Anpd({ v }) {
  const a = v.anpd;
  if (!a) return <section className="card"><h2>Cruzamento com incidentes da ANPD</h2><p className="note">Sem série de incidentes carregada (preencher saida/anpd_mensal.csv e rodar o analise.py).</p></section>;
  const ic = (lo, hi) => (lo == null ? "—" : `[${nf(lo, 2)}; ${nf(hi, 2)}]`);
  const exclui0 = (lo, hi) => lo != null && hi != null && (lo > 0 || hi < 0);
  const nExcl = a.correlacoes.filter((r) => exclui0(r.ic95_inf, r.ic95_sup) || exclui0(r.ic95_dif_inf, r.ic95_dif_sup)).length;
  const nTot = a.correlacoes.length * 2;
  const nome = { pct_B_tic: "% B no gasto de TI", pct_B_ou_C_nuvem_ia: "% B ou C em nuvem e IA", valor_tic: "Valor mensal de TI" };
  return (
    <Card titulo="IDT e incidentes notificados à ANPD" sub="Dois gráficos com o mesmo eixo de tempo; escalas separadas, sem eixo duplo."
      nota={`Exploratório e sem causalidade. ${nExcl === 0 ? `Nenhum dos ${nTot} intervalos de confiança de 95% (níveis e diferenças) exclui zero` : `${nExcl} de ${nTot} intervalos de confiança de 95% excluem zero (ver tabela; 12 testes por versão, limite de Bonferroni 0,0042)`}; n = 24 meses dá poder baixo, e a série da ANPD mistura União, estados e municípios.`}
      tabela={<table><thead><tr><th>Série</th><th>Defasagem</th><th>rho (níveis) [IC 95%]</th><th>rho (diferenças) [IC 95%]</th></tr></thead><tbody>
        {a.correlacoes.map((r) => <tr key={r.serie + r.defasagem_meses}><td>{nome[r.serie]}</td><td>{r.defasagem_meses} m</td><td>{nf(r.rho, 2)} {ic(r.ic95_inf, r.ic95_sup)}</td><td>{nf(r.rho_dif, 2)} {ic(r.ic95_dif_inf, r.ic95_dif_sup)}</td></tr>)}</tbody></table>}>
      <h3 className="subhead">Incidentes por mês (setor público)</h3>
      <ResponsiveContainer width="100%" height={170}>
        <BarChart data={a.serie} syncId="anpd" margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} /><XAxis dataKey="mes" {...axis} interval={2} hide /><YAxis {...axis} width={44} />
          <Tooltip {...tip} formatter={(x) => [nf(x, 0), "Incidentes"]} cursor={{ fill: "var(--border)", opacity: 0.35 }} />
          <Bar dataKey="incidentes_publico" fill="var(--neutral)" radius={[4, 4, 0, 0]} maxBarSize={18} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <h3 className="subhead" style={{ marginTop: 14 }}>IDT mensal</h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={a.serie} syncId="anpd" margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} /><XAxis dataKey="mes" {...axis} interval={2} /><YAxis {...axis} domain={[0, 100]} unit="%" width={44} />
          <Tooltip {...tip} formatter={(x) => [pct(x), "IDT"]} />
          <Line type="linear" dataKey="idt" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 }} activeDot={{ r: 6 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
