import { useState, useEffect, useRef, useCallback } from "react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Brush
} from "recharts";

// ─── Paleta de cores ────────────────────────────────────────────────────────
const C = {
  bg:    "#0c1219",
  panel: "#111b27",
  rail:  "#1e2f42",
  acc:   "#00d4ff",
  green: "#00e676",
  amber: "#ffab00",
  red:   "#ff5252",
  purple:"#b388ff",
  text:  "#e0eaf4",
  muted: "#4a7090",
  ghost: "#7aa5c0",
};

// ─── Perfis de consumidor tipo (curvas normalizadas 24h) ────────────────────
// Baseados nos perfis CTR/ANEEL: B1-Residencial, B3-Comercial BT,
// A4-Industrial MT, A3-Iluminação Pública, rural
const PERFIS_BASE = {
  "B1 - Residencial": [
    0.22,0.18,0.15,0.14,0.14,0.16,0.25,0.38,0.42,0.40,0.42,0.45,
    0.50,0.48,0.46,0.48,0.52,0.65,0.80,0.95,1.00,0.90,0.72,0.45
  ],
  "B1 - Residencial Baixa Renda": [
    0.20,0.16,0.14,0.13,0.13,0.15,0.22,0.35,0.40,0.38,0.42,0.50,
    0.55,0.52,0.50,0.52,0.58,0.75,0.92,1.00,0.98,0.85,0.65,0.38
  ],
  "B2 - Rural": [
    0.18,0.15,0.12,0.12,0.14,0.30,0.55,0.80,0.85,0.82,0.78,0.70,
    0.60,0.62,0.68,0.75,0.80,0.88,0.92,1.00,0.95,0.82,0.60,0.32
  ],
  "B3 - Comercial BT": [
    0.12,0.10,0.09,0.09,0.10,0.12,0.20,0.45,0.72,0.88,0.95,0.98,
    1.00,0.98,0.96,0.98,0.95,0.85,0.70,0.52,0.35,0.22,0.16,0.13
  ],
  "A4 - Industrial MT": [
    0.60,0.60,0.60,0.60,0.60,0.62,0.72,0.88,0.95,1.00,1.00,0.98,
    0.90,0.98,1.00,1.00,0.98,0.95,0.88,0.80,0.72,0.68,0.65,0.62
  ],
  "A3 - Industrial AT": [
    0.72,0.72,0.72,0.70,0.70,0.72,0.80,0.90,0.96,1.00,1.00,0.99,
    0.92,0.99,1.00,1.00,0.99,0.96,0.90,0.85,0.80,0.78,0.76,0.74
  ],
  "B4a - Iluminação Pública": [
    0.98,0.98,0.98,0.98,0.98,0.85,0.20,0.02,0.02,0.02,0.02,0.02,
    0.02,0.02,0.02,0.02,0.02,0.15,0.85,1.00,1.00,1.00,1.00,0.99
  ],
  "A4 - Serviços Públicos": [
    0.35,0.30,0.28,0.28,0.30,0.38,0.55,0.75,0.88,0.95,0.98,1.00,
    0.98,1.00,0.98,0.96,0.94,0.88,0.80,0.72,0.65,0.55,0.48,0.40
  ],
};

// Fator de potência típico por classe (indutivo)
const FP_TIPICO = {
  "B1 - Residencial": 0.92,
  "B1 - Residencial Baixa Renda": 0.90,
  "B2 - Rural": 0.88,
  "B3 - Comercial BT": 0.88,
  "A4 - Industrial MT": 0.85,
  "A3 - Industrial AT": 0.87,
  "B4a - Iluminação Pública": 0.97,
  "A4 - Serviços Públicos": 0.90,
};

// Variação por dia da semana (Seg-Dom) sobre perfil base
const FATOR_DIA = {
  "Dia Útil":   [1.00,1.00,1.00,1.00,1.00],
  "Sábado":     [0.88,0.88,0.88,0.85,0.82],
  "Domingo":    [0.72,0.72,0.72,0.68,0.65],
};

// Variação mensal (sazonalidade) – índice relativo ao mês de pico
const FATOR_MES = [0.88,0.85,0.90,0.88,0.92,0.95,0.98,1.00,0.97,0.93,0.90,0.92];

const HORAS = Array.from({length:24}, (_,i) => `${String(i).padStart(2,'0')}:00`);
const MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];

// ─── Cálculo dos Fatores Técnicos ───────────────────────────────────────────
function calcFactors(P, Pmax, Energ24h) {
  const media = Energ24h / 24;
  const fd  = media / Pmax;                        // Fator de Demanda = Dmáx / Dinst
  const fc  = media / Pmax;                        // Fator de Carga = Dmáx_med / Dmáx
  const fco = Energ24h / (Pmax * 24);              // Fator de Carga (energia) = E / (Dmáx × 24h)
  const Pmin = Math.min(...P);
  const fcv  = Pmin / Pmax;                        // Fator de variação de carga
  // Horas de utilização = E / Dmáx
  const hutil = Energ24h / Pmax;
  // Horas equivalentes de ponta
  const hponta = Energ24h / Pmax;
  return { fd, fc: fco, fcv, hutil, hponta, media, Pmax, Pmin, Energ24h };
}

// ─── Tooltip customizado ────────────────────────────────────────────────────
const CTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{background:C.panel,border:`1px solid ${C.rail}`,borderRadius:6,padding:"8px 12px",fontSize:11}}>
      <div style={{color:C.acc,fontWeight:700,marginBottom:4}}>{label}</div>
      {payload.map((p,i)=>(
        <div key={i} style={{color:p.color,marginBottom:2}}>
          {p.name}: <b>{typeof p.value==='number'?p.value.toFixed(3):p.value}</b> {p.unit||''}
        </div>
      ))}
    </div>
  );
};

// ─── Componente principal ───────────────────────────────────────────────────
export default function CurvaCargaMotor() {
  // ── Modo ativo ──
  const [modo, setModo] = useState("manual"); // "manual" | "aneel"

  // ── Inputs manual ──
  const [perfil, setPerfil] = useState("B1 - Residencial");
  const [demandaInst, setDemandaInst] = useState(100);     // kW
  const [fp, setFp] = useState(0.92);
  const [diatipo, setDiatico] = useState("Dia Útil");
  const [mes, setMes] = useState(7);                       // index 0-11
  const [ruido, setRuido] = useState(3);                   // % variação aleatória
  const [editando, setEditando] = useState(false);
  const [pontosEditados, setPontosEditados] = useState(null);
  const [edicaoPonto, setEdicaoPonto] = useState(null);    // index em edição

  // ── ANEEL API ──
  const [aneel, setAneel] = useState({ loading:false, data:null, error:null, filtros:{} });
  const [aneelFiltro, setAneelFiltro] = useState({ distribuidora:"", classe:"", ano:"" });

  // ── Curva computada ──
  const [curva, setCurva] = useState(null);
  const [curvaRef, setCurvaRef] = useState(null); // segunda curva para comparação

  // ── Abas ──
  const [aba, setAba] = useState("curva");

  // ─── Gerar curva manual ──────────────────────────────────────────────────
  const gerarCurvaManual = useCallback(() => {
    const base = PERFIS_BASE[perfil] || PERFIS_BASE["B1 - Residencial"];
    const fdm  = FATOR_DIA[diatico]?.[0] ?? 1.0;
    const fmes = FATOR_MES[mes];
    const dinst = demandaInst;

    let pts = pontosEditados || base.map((v, h) => {
      // variação estocástica controlada
      const r = 1 + (Math.random() - 0.5) * 2 * ruido / 100;
      return v * r;
    });

    // Normalizar
    const pmax_base = Math.max(...pts);
    pts = pts.map(v => v / pmax_base);

    const P = pts.map(v => v * dinst * fdm * fmes);
    const Q = P.map(v => v * Math.tan(Math.acos(fp)));
    const S = P.map(v => v / fp);
    const Energ = P.reduce((a,b)=>a+b, 0);
    const Pmax  = Math.max(...P);
    const factors = calcFactors(P, Pmax, Energ);

    const dados = HORAS.map((h, i) => ({
      hora: h,
      P:    +P[i].toFixed(3),
      Q:    +Q[i].toFixed(3),
      S:    +S[i].toFixed(3),
      fp:   fp,
      norm: +pts[i].toFixed(4),
    }));

    setCurva({ dados, factors, perfil, diatico, mes: MESES[mes], fp, dinst });
  }, [perfil, demandaInst, fp, diatico, mes, ruido, pontosEditados]);

  useEffect(() => { gerarCurvaManual(); }, [gerarCurvaManual]);

  // ─── Buscar dados ANEEL ──────────────────────────────────────────────────
  const buscarANEEL = async () => {
    setAneel(a => ({...a, loading:true, error:null, data:null}));
    try {
      // CKAN API — dataset consumidor tipo
      const BASE = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search";
      const rid  = "b0418edb-038d-4fde-b624-c318d376a734";
      let filters = {};
      if (aneelFiltro.distribuidora) filters["NomDistribuidora"] = aneelFiltro.distribuidora;
      if (aneelFiltro.classe)        filters["CodClasseConsumo"]  = aneelFiltro.classe;

      const url = `${BASE}?resource_id=${rid}&limit=8760&filters=${encodeURIComponent(JSON.stringify(filters))}`;
      const res = await fetch(url);
      const json = await res.json();
      if (!json.success) throw new Error(json.error?.message || "Erro na API");
      setAneel(a => ({...a, loading:false, data:json.result, error:null}));
      // Processar dados ANEEL
      processarDadosANEEL(json.result.records);
    } catch(e) {
      setAneel(a => ({...a, loading:false, error:e.message}));
    }
  };

  const processarDadosANEEL = (records) => {
    if (!records?.length) return;
    // Agregar por hora do dia (media de todos os registros)
    const por_hora = Array.from({length:24}, () => []);
    records.forEach(r => {
      const h = parseInt(r.NumHora || r.Hora || "0");
      const p = parseFloat(r.ValDemandaAtiva || r.DemandaAtiva || "0");
      if (h >= 0 && h < 24 && !isNaN(p)) por_hora[h].push(p);
    });
    const P_aneel = por_hora.map(arr => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0);
    const Pmax = Math.max(...P_aneel);
    if (Pmax === 0) return;
    const Energ = P_aneel.reduce((a,b)=>a+b,0);
    const factors = calcFactors(P_aneel, Pmax, Energ);
    const fp_a = 0.90;
    const dados = HORAS.map((h,i) => ({
      hora: h,
      P:    +P_aneel[i].toFixed(3),
      Q:    +(P_aneel[i]*Math.tan(Math.acos(fp_a))).toFixed(3),
      S:    +(P_aneel[i]/fp_a).toFixed(3),
      fp:   fp_a,
      norm: +(P_aneel[i]/Pmax).toFixed(4),
    }));
    setCurvaRef({ dados, factors, perfil:"ANEEL - Dados Reais", diatico:"Medido", mes:"—", fp:fp_a, dinst:Pmax });
    setAba("comparativo");
  };

  // ─── Edição manual de pontos ─────────────────────────────────────────────
  const iniciarEdicao = () => {
    if (curva) {
      setPontosEditados(curva.dados.map(d => d.norm));
      setEditando(true);
    }
  };
  const salvarEdicao = () => { setEditando(false); setEdicaoPonto(null); gerarCurvaManual(); };
  const editarPonto = (i, val) => {
    const np = [...(pontosEditados||[])];
    np[i] = Math.min(1, Math.max(0, parseFloat(val)||0));
    setPontosEditados(np);
  };

  // ─── Adicionar curva como referência ────────────────────────────────────
  const usarComoReferencia = () => { if (curva) setCurvaRef({...curva, perfil:curva.perfil+" (Ref)"}); };

  // ─── Exportar CSV ────────────────────────────────────────────────────────
  const exportarCSV = () => {
    if (!curva) return;
    const linhas = ["Hora,P_ativa_kW,Q_reativa_kVAr,S_aparente_kVA,FP,Norm"];
    curva.dados.forEach(d => linhas.push(`${d.hora},${d.P},${d.Q},${d.S},${d.fp},${d.norm}`));
    const blob = new Blob([linhas.join("\n")], {type:"text/csv"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `curva_carga_${curva.perfil.replace(/\s+/g,"-")}_${curva.diatico}.csv`;
    a.click();
  };

  // ─── Dados para gráfico comparativo ──────────────────────────────────────
  const dadosComp = curva ? HORAS.map((h, i) => ({
    hora: h,
    [curva.perfil]:          curva.dados[i].P,
    ...(curvaRef ? {[curvaRef.perfil]: curvaRef.dados[i].P} : {}),
  })) : [];

  // ─── Métricas de comparação ───────────────────────────────────────────────
  const metricas = curva ? [
    { label:"Demanda Máxima (Dmáx)", val:curva.factors.Pmax.toFixed(2), unit:"kW", cor:C.red },
    { label:"Demanda Mínima (Dmin)", val:curva.factors.Pmin.toFixed(2), unit:"kW", cor:C.green },
    { label:"Demanda Média (Dmed)", val:curva.factors.media.toFixed(2), unit:"kW", cor:C.acc },
    { label:"Energia 24h", val:curva.factors.Energ24h.toFixed(1), unit:"kWh", cor:C.amber },
    { label:"Fator de Carga (FC)", val:(curva.factors.fc*100).toFixed(1), unit:"%", cor:C.purple, tip:"FC = Dmédio / Dmáx" },
    { label:"Fator de Variação (FCV)", val:(curva.factors.fcv*100).toFixed(1), unit:"%", cor:C.amber, tip:"FCV = Dmin / Dmáx" },
    { label:"Horas de Utilização", val:curva.factors.hutil.toFixed(1), unit:"h/dia", cor:C.ghost, tip:"hutil = E / Dmáx" },
    { label:"Fator de Potência", val:(curva.fp*100).toFixed(1), unit:"%", cor:C.green },
  ] : [];

  // ─── Render ───────────────────────────────────────────────────────────────
  const ABAS = ["curva","potencias","fatores","comparativo","aneel","edicao"];
  const ABA_LABELS = ["📈 Curva de Carga","⚡ P·Q·S","📊 Fatores","🔀 Comparativo","🏛 ANEEL","✏️ Edição Manual"];

  return (
    <div style={{background:C.bg,minHeight:"100vh",color:C.text,fontFamily:"'Segoe UI',Arial,sans-serif",fontSize:13}}>

      {/* ── Header ── */}
      <div style={{background:C.panel,borderBottom:`1px solid ${C.rail}`,padding:"10px 20px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <div style={{background:`linear-gradient(135deg,${C.acc},${C.purple})`,borderRadius:8,width:34,height:34,display:"grid",placeItems:"center",fontSize:18}}>⚡</div>
          <div>
            <div style={{fontWeight:700,fontSize:15,letterSpacing:.3}}>Motor de Curvas de Carga Horárias</div>
            <div style={{color:C.muted,fontSize:10}}>Baseado nos conceitos OSE · Integração ANEEL CTR · NBR/ABNT</div>
          </div>
        </div>
        <div style={{display:"flex",gap:8}}>
          <button onClick={exportarCSV} style={btnStyle(C.amber)}>⬇ Exportar CSV</button>
          <button onClick={usarComoReferencia} style={btnStyle(C.purple)}>📌 Fixar como Ref</button>
          <button onClick={gerarCurvaManual} style={btnStyle(C.acc)}>▶ Recalcular</button>
        </div>
      </div>

      {/* ── Layout ── */}
      <div style={{display:"flex",minHeight:"calc(100vh - 58px)"}}>

        {/* ── Sidebar ── */}
        <aside style={{width:260,background:C.panel,borderRight:`1px solid ${C.rail}`,padding:"14px 12px",overflowY:"auto",flexShrink:0}}>

          {/* Modo */}
          <div style={sgStyle}>Fonte de Dados</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6,marginBottom:12}}>
            {[["manual","✏️ Manual"],["aneel","🏛 ANEEL"]].map(([v,l])=>(
              <button key={v} onClick={()=>setModo(v)}
                style={{padding:"6px 4px",borderRadius:5,border:`1px solid ${modo===v?C.acc:C.rail}`,
                  background:modo===v?`${C.acc}22`:"transparent",color:modo===v?C.acc:C.ghost,
                  fontSize:11,cursor:"pointer",fontWeight:modo===v?700:400}}>
                {l}
              </button>
            ))}
          </div>

          {/* Perfil de Consumidor */}
          <div style={sgStyle}>Perfil de Consumidor</div>
          <Fld label="Classe / Perfil CTR">
            <select value={perfil} onChange={e=>{setPerfil(e.target.value);setFp(FP_TIPICO[e.target.value]||0.92);setPontosEditados(null);}} style={selStyle}>
              {Object.keys(PERFIS_BASE).map(k=><option key={k}>{k}</option>)}
            </select>
          </Fld>

          {/* Parâmetros elétricos */}
          <div style={sgStyle}>Parâmetros Elétricos</div>
          <Fld label="Demanda Instalada (kW)">
            <input type="number" value={demandaInst} onChange={e=>setDemandaInst(+e.target.value)} min={1} style={inpStyle}/>
          </Fld>
          <Fld label={`Fator de Potência (cosphi=${fp})`}>
            <input type="range" min={0.70} max={1.00} step={0.01} value={fp}
              onChange={e=>setFp(+e.target.value)}
              style={{width:"100%",accentColor:C.acc}}/>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:C.muted}}>
              <span>0.70 (ind)</span><span style={{color:fp<0.92?C.red:C.green,fontWeight:700}}>{fp.toFixed(2)}</span><span>1.00</span>
            </div>
            {fp < 0.92 && <div style={{color:C.red,fontSize:10,marginTop:2}}>⚠ Abaixo do limite ANEEL (0,92)</div>}
          </Fld>

          {/* Perfil temporal */}
          <div style={sgStyle}>Perfil Temporal</div>
          <Fld label="Tipo de Dia">
            <select value={diatico} onChange={e=>setDiatico(e.target.value)} style={selStyle}>
              {Object.keys(FATOR_DIA).map(k=><option key={k}>{k}</option>)}
            </select>
          </Fld>
          <Fld label={`Mês: ${MESES[mes]}`}>
            <input type="range" min={0} max={11} step={1} value={mes}
              onChange={e=>setMes(+e.target.value)} style={{width:"100%",accentColor:C.acc}}/>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:C.muted}}>
              {MESES.map((m,i)=><span key={i} style={{color:i===mes?C.acc:C.muted}}>{m.slice(0,1)}</span>)}
            </div>
          </Fld>
          <Fld label={`Variação Aleatória: ±${ruido}%`}>
            <input type="range" min={0} max={15} step={1} value={ruido}
              onChange={e=>setRuido(+e.target.value)} style={{width:"100%",accentColor:C.amber}}/>
          </Fld>

          {/* Fatores rápidos */}
          {curva && <>
            <div style={sgStyle}>Indicadores Rápidos</div>
            {[
              ["FC", (curva.factors.fc*100).toFixed(1)+"%", "Fator de Carga"],
              ["FCV",(curva.factors.fcv*100).toFixed(1)+"%","Fator de Variação"],
              ["Emáx",curva.factors.Pmax.toFixed(0)+" kW","Demanda de Ponta"],
              ["Emed",curva.factors.media.toFixed(0)+" kW","Demanda Média"],
            ].map(([k,v,tt])=>(
              <div key={k} title={tt} style={{display:"flex",justifyContent:"space-between",padding:"5px 0",borderBottom:`1px solid ${C.rail}`,fontSize:11}}>
                <span style={{color:C.ghost}}>{k}</span>
                <span style={{fontFamily:"monospace",color:C.acc,fontWeight:700}}>{v}</span>
              </div>
            ))}
          </>}

          {/* ANEEL panel */}
          {modo==="aneel" && <>
            <div style={sgStyle}>Filtros ANEEL CTR</div>
            <Fld label="Distribuidora (nome parcial)">
              <input value={aneelFiltro.distribuidora} onChange={e=>setAneelFiltro(f=>({...f,distribuidora:e.target.value}))} style={inpStyle} placeholder="ex: CEMIG"/>
            </Fld>
            <Fld label="Código Classe de Consumo">
              <select value={aneelFiltro.classe} onChange={e=>setAneelFiltro(f=>({...f,classe:e.target.value}))} style={selStyle}>
                <option value="">Todas</option>
                <option value="B1">B1 - Residencial</option>
                <option value="B2">B2 - Rural</option>
                <option value="B3">B3 - Comercial</option>
                <option value="A4">A4 - Industrial MT</option>
                <option value="A3">A3 - Industrial AT</option>
                <option value="B4">B4 - Iluminação Pública</option>
              </select>
            </Fld>
            <button onClick={buscarANEEL} disabled={aneel.loading}
              style={{...btnStyle(C.acc),width:"100%",marginTop:6}}>
              {aneel.loading ? "⏳ Buscando..." : "🔍 Buscar Dados ANEEL"}
            </button>
            {aneel.error && <div style={{color:C.red,fontSize:10,marginTop:6}}>⚠ {aneel.error}</div>}
            {aneel.data && <div style={{color:C.green,fontSize:10,marginTop:6}}>✓ {aneel.data.total} registros carregados</div>}
            <div style={{marginTop:8,padding:8,background:C.rail,borderRadius:6,fontSize:10,color:C.ghost,lineHeight:1.5}}>
              Os dados são carregados diretamente da API pública da ANEEL (CTR - Curvas de Carga das Revisões Tarifárias). Licença ODbL.
            </div>
          </>}
        </aside>

        {/* ── Conteúdo ── */}
        <main style={{flex:1,overflow:"auto",display:"flex",flexDirection:"column"}}>

          {/* Abas */}
          <div style={{background:C.panel,borderBottom:`1px solid ${C.rail}`,display:"flex",padding:"0 8px",overflowX:"auto",flexShrink:0}}>
            {ABAS.map((a,i)=>(
              <button key={a} onClick={()=>setAba(a)}
                style={{padding:"10px 14px",border:"none",borderBottom:`2px solid ${aba===a?C.acc:"transparent"}`,
                  background:"transparent",color:aba===a?C.acc:C.ghost,fontSize:11,cursor:"pointer",
                  whiteSpace:"nowrap",fontWeight:aba===a?700:400}}>
                {ABA_LABELS[i]}
              </button>
            ))}
          </div>

          <div style={{flex:1,padding:14,overflowY:"auto"}}>

            {/* ── ABA: CURVA ── */}
            {aba==="curva" && curva && (
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                {/* Cabeçalho da curva */}
                <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
                  {metricas.slice(0,4).map(m=>(
                    <KpiCard key={m.label} {...m}/>
                  ))}
                </div>

                {/* Gráfico principal: Potência Ativa */}
                <Card title={`Curva de Carga — ${curva.perfil} · ${curva.diatico} · ${curva.mes}`} right={`D_inst=${curva.dinst} kW`}>
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={curva.dados} margin={{top:5,right:20,bottom:5,left:0}}>
                      <defs>
                        <linearGradient id="gradP" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={C.acc} stopOpacity={0.4}/>
                          <stop offset="95%" stopColor={C.acc} stopOpacity={0.02}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
                      <XAxis dataKey="hora" tick={{fontSize:9,fill:C.muted}} interval={2}/>
                      <YAxis tick={{fontSize:9,fill:C.muted}} unit=" kW"/>
                      <Tooltip content={<CTooltip/>}/>
                      <ReferenceLine y={curva.factors.media} stroke={C.amber} strokeDasharray="4 4"
                        label={{value:`Dméd=${curva.factors.media.toFixed(0)}kW`,fill:C.amber,fontSize:9,position:"right"}}/>
                      <Area type="monotone" dataKey="P" name="P Ativa" unit=" kW"
                        stroke={C.acc} fill="url(#gradP)" strokeWidth={2} dot={false}/>
                      {curvaRef && (
                        <Area type="monotone" data={curvaRef.dados} dataKey="P" name={curvaRef.perfil}
                          stroke={C.purple} fill="none" strokeWidth={1.5} strokeDasharray="5 3" dot={false}/>
                      )}
                    </AreaChart>
                  </ResponsiveContainer>
                </Card>

                {/* Normalizada */}
                <Card title="Curva Normalizada (p.u.)" right="Dmáx = 1.0 p.u.">
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={curva.dados} margin={{top:5,right:20,bottom:5,left:0}}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
                      <XAxis dataKey="hora" tick={{fontSize:9,fill:C.muted}} interval={2}/>
                      <YAxis domain={[0,1.05]} tick={{fontSize:9,fill:C.muted}}/>
                      <Tooltip content={<CTooltip/>}/>
                      <ReferenceLine y={curva.factors.fc} stroke={C.amber} strokeDasharray="4 4"
                        label={{value:`FC=${(curva.factors.fc*100).toFixed(0)}%`,fill:C.amber,fontSize:9}}/>
                      <Line type="monotone" dataKey="norm" name="Carga (p.u.)" stroke={C.green} dot={false} strokeWidth={2}/>
                    </LineChart>
                  </ResponsiveContainer>
                </Card>

                {/* Histograma de duração de carga */}
                <Card title="Histograma de Duração de Carga" right="Frequência por faixa de demanda">
                  <HistogramaDuracao dados={curva.dados} Pmax={curva.factors.Pmax}/>
                </Card>
              </div>
            )}

            {/* ── ABA: POTÊNCIAS ── */}
            {aba==="potencias" && curva && (
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                <Card title="Triângulo de Potências — P · Q · S por hora" right={`FP = ${curva.fp}`}>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={curva.dados} margin={{top:5,right:20,bottom:5,left:0}}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
                      <XAxis dataKey="hora" tick={{fontSize:9,fill:C.muted}} interval={2}/>
                      <YAxis tick={{fontSize:9,fill:C.muted}}/>
                      <Tooltip content={<CTooltip/>}/>
                      <Legend wrapperStyle={{fontSize:10}}/>
                      <Line type="monotone" dataKey="P" name="P Ativa (kW)" stroke={C.acc} dot={false} strokeWidth={2}/>
                      <Line type="monotone" dataKey="Q" name="Q Reativa (kVAr)" stroke={C.amber} dot={false} strokeWidth={1.5} strokeDasharray="5 3"/>
                      <Line type="monotone" dataKey="S" name="S Aparente (kVA)" stroke={C.purple} dot={false} strokeWidth={1.5}/>
                    </LineChart>
                  </ResponsiveContainer>
                </Card>

                {/* FP ao longo do dia */}
                <Card title="Variação de FP sob Carga Baixa" right="Regime de carga parcial">
                  <FPBaixaCarga dados={curva.dados} fp={curva.fp}/>
                </Card>

                {/* Tabela P·Q·S */}
                <Card title="Tabela Horária — P · Q · S · FP">
                  <div style={{overflowX:"auto",maxHeight:340,overflowY:"auto"}}>
                    <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                      <thead>
                        <tr style={{background:C.rail}}>
                          {["Hora","P (kW)","Q (kVAr)","S (kVA)","FP","P norm."].map(h=>(
                            <th key={h} style={{padding:"5px 8px",textAlign:"right",color:C.ghost,fontFamily:"monospace",fontSize:9,letterSpacing:.06}}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {curva.dados.map((d,i)=>(
                          <tr key={i} style={{borderBottom:`1px solid ${C.rail}`,background:d.P===curva.factors.Pmax?`${C.red}18`:i%2===0?"transparent":"rgba(255,255,255,.02)"}}>
                            <td style={{padding:"4px 8px",fontFamily:"monospace",color:C.muted,textAlign:"right"}}>{d.hora}</td>
                            <td style={{padding:"4px 8px",fontFamily:"monospace",color:C.acc,fontWeight:d.P===curva.factors.Pmax?700:400,textAlign:"right"}}>{d.P.toFixed(2)}</td>
                            <td style={{padding:"4px 8px",fontFamily:"monospace",color:C.amber,textAlign:"right"}}>{d.Q.toFixed(2)}</td>
                            <td style={{padding:"4px 8px",fontFamily:"monospace",color:C.purple,textAlign:"right"}}>{d.S.toFixed(2)}</td>
                            <td style={{padding:"4px 8px",fontFamily:"monospace",color:d.fp<0.92?C.red:C.green,textAlign:"right"}}>{d.fp.toFixed(3)}</td>
                            <td style={{padding:"4px 8px",fontFamily:"monospace",color:C.ghost,textAlign:"right"}}>{d.norm.toFixed(4)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>
            )}

            {/* ── ABA: FATORES ── */}
            {aba==="fatores" && curva && (
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:10}}>
                  {metricas.map(m=><KpiCard key={m.label} {...m}/>)}
                </div>

                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
                  {/* Fórmulas */}
                  <Card title="Definição dos Fatores — OSE/Starosta">
                    <FormulasPanel factors={curva.factors} fp={curva.fp}/>
                  </Card>

                  {/* Variação por mês */}
                  <Card title="Sazonalidade — Fator Mensal (perfil típico)">
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={MESES.map((m,i)=>({mes:m,fator:FATOR_MES[i],pico:FATOR_MES[i]*curva.dinst}))} margin={{top:5,right:10,bottom:5,left:0}}>
                        <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
                        <XAxis dataKey="mes" tick={{fontSize:9,fill:C.muted}}/>
                        <YAxis tick={{fontSize:9,fill:C.muted}} unit=" kW" yAxisId="kw"/>
                        <Tooltip content={<CTooltip/>}/>
                        <Bar dataKey="pico" name="Demanda estimada" fill={C.acc} opacity={0.8} yAxisId="kw"
                          label={{position:"top",fill:C.muted,fontSize:8,formatter:v=>v.toFixed(0)}}/>
                        <ReferenceLine y={curva.dinst} stroke={C.red} strokeDasharray="4 3" yAxisId="kw"
                          label={{value:"D_inst",fill:C.red,fontSize:9}}/>
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                </div>

                {/* Curva de duração de carga (LDC) */}
                <Card title="Curva de Duração de Carga (LDC — Load Duration Curve)" right="Horas × Demanda">
                  <LDCChart dados={curva.dados}/>
                </Card>
              </div>
            )}

            {/* ── ABA: COMPARATIVO ── */}
            {aba==="comparativo" && (
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                {(!curva && !curvaRef) && (
                  <div style={{textAlign:"center",color:C.muted,padding:40}}>
                    Gere uma curva manual e clique em "Fixar como Ref", ou busque dados ANEEL para comparar.
                  </div>
                )}
                {(curva || curvaRef) && (
                  <>
                    <Card title="Comparativo de Curvas de Carga" right="kW">
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={dadosComp} margin={{top:5,right:20,bottom:5,left:0}}>
                          <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
                          <XAxis dataKey="hora" tick={{fontSize:9,fill:C.muted}} interval={2}/>
                          <YAxis tick={{fontSize:9,fill:C.muted}} unit=" kW"/>
                          <Tooltip content={<CTooltip/>}/>
                          <Legend wrapperStyle={{fontSize:10}}/>
                          {curva && <Line type="monotone" dataKey={curva.perfil} stroke={C.acc} dot={false} strokeWidth={2}/>}
                          {curvaRef && <Line type="monotone" dataKey={curvaRef.perfil} stroke={C.purple} dot={false} strokeWidth={2} strokeDasharray="5 3"/>}
                        </LineChart>
                      </ResponsiveContainer>
                    </Card>

                    {/* Tabela comparativa de fatores */}
                    {curva && curvaRef && (
                      <Card title="Comparativo de Indicadores">
                        <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
                          <thead>
                            <tr style={{background:C.rail}}>
                              <th style={thStyle}>Indicador</th>
                              <th style={thStyle}>{curva.perfil}</th>
                              <th style={thStyle}>{curvaRef.perfil}</th>
                              <th style={thStyle}>Δ</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[
                              ["Dmáx (kW)", curva.factors.Pmax, curvaRef.factors.Pmax],
                              ["Dmin (kW)", curva.factors.Pmin, curvaRef.factors.Pmin],
                              ["Dmed (kW)", curva.factors.media, curvaRef.factors.media],
                              ["FC (%)", curva.factors.fc*100, curvaRef.factors.fc*100],
                              ["FCV (%)", curva.factors.fcv*100, curvaRef.factors.fcv*100],
                              ["E 24h (kWh)", curva.factors.Energ24h, curvaRef.factors.Energ24h],
                              ["Horas utiliz. (h)", curva.factors.hutil, curvaRef.factors.hutil],
                            ].map(([label,a,b])=>{
                              const delta=b-a;
                              const cor=delta>0?C.green:delta<0?C.red:C.ghost;
                              return (
                                <tr key={label} style={{borderBottom:`1px solid ${C.rail}`}}>
                                  <td style={{padding:"5px 8px",color:C.ghost}}>{label}</td>
                                  <td style={{padding:"5px 8px",fontFamily:"monospace",color:C.acc,textAlign:"right"}}>{a.toFixed(2)}</td>
                                  <td style={{padding:"5px 8px",fontFamily:"monospace",color:C.purple,textAlign:"right"}}>{b.toFixed(2)}</td>
                                  <td style={{padding:"5px 8px",fontFamily:"monospace",color:cor,textAlign:"right"}}>{delta>0?"+":""}{delta.toFixed(2)}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </Card>
                    )}
                  </>
                )}
              </div>
            )}

            {/* ── ABA: ANEEL ── */}
            {aba==="aneel" && (
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                <Card title="🏛 Dados Abertos ANEEL — CTR Curva de Carga">
                  <div style={{color:C.ghost,fontSize:12,lineHeight:1.7,marginBottom:14}}>
                    O dataset <b style={{color:C.acc}}>CTR - Curva de Carga</b> contém as curvas de demanda dos consumidores tipo e redes tipo
                    utilizadas nas revisões tarifárias periódicas das distribuidoras. Licença ODbL.
                    <br/><br/>
                    <b>Recursos disponíveis:</b><br/>
                    • <span style={{color:C.amber}}>ctr-curvas-carga-consumidor-tipo.csv</span> — curvas horárias por classe de consumo<br/>
                    • <span style={{color:C.amber}}>ctr-curvas-carga-redes-tipo.csv</span> — curvas das redes de distribuição
                    <br/><br/>
                    Use o painel esquerdo (modo ANEEL) para filtrar por distribuidora e classe e carregar os dados diretamente.
                  </div>
                  <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10}}>
                    {[
                      ["Endpoint API",`https://dadosabertos.aneel.gov.br/api/3/action/datastore_search`,"Dataset CKAN público"],
                      ["Resource ID","b0418edb-038d-4fde-b624-c318d376a734","Consumidor Tipo"],
                      ["Resource ID","a77cacce-6a49-44c7-af20-508aecd4539d","Redes Tipo"],
                      ["Cobertura","A partir de 2012","Revisões tarifárias"],
                      ["Frequência","Conforme calendário RTP","Distribuidoras"],
                      ["Licença","ODbL","Dados Abertos"],
                    ].map(([k,v,d])=>(
                      <div key={k} style={{background:C.rail,borderRadius:6,padding:"10px 12px"}}>
                        <div style={{color:C.muted,fontSize:10}}>{k}</div>
                        <div style={{fontFamily:"monospace",color:C.acc,fontSize:11,marginTop:3,wordBreak:"break-all"}}>{v}</div>
                        <div style={{color:C.ghost,fontSize:10,marginTop:2}}>{d}</div>
                      </div>
                    ))}
                  </div>
                  {aneel.data && (
                    <div style={{marginTop:14}}>
                      <div style={{color:C.green,fontWeight:700,marginBottom:8}}>✓ {aneel.data.total} registros carregados · {aneel.data.records?.length} exibidos</div>
                      <div style={{overflowX:"auto",maxHeight:300,overflowY:"auto"}}>
                        <table style={{width:"100%",borderCollapse:"collapse",fontSize:10}}>
                          <thead>
                            <tr style={{background:C.rail}}>
                              {aneel.data.fields?.map(f=>(
                                <th key={f.id} style={{padding:"4px 6px",textAlign:"left",color:C.ghost,whiteSpace:"nowrap"}}>{f.id}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {aneel.data.records?.slice(0,50).map((r,i)=>(
                              <tr key={i} style={{borderBottom:`1px solid ${C.rail}`,background:i%2===0?"transparent":"rgba(255,255,255,.02)"}}>
                                {aneel.data.fields?.map(f=>(
                                  <td key={f.id} style={{padding:"3px 6px",fontFamily:"monospace",color:C.text,whiteSpace:"nowrap"}}>{r[f.id]??"-"}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </Card>
              </div>
            )}

            {/* ── ABA: EDIÇÃO MANUAL ── */}
            {aba==="edicao" && curva && (
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                <Card title="✏️ Edição Manual da Curva de Carga" right="Ajuste ponto a ponto (p.u.)">
                  <div style={{marginBottom:10,display:"flex",gap:8}}>
                    {!editando
                      ? <button onClick={iniciarEdicao} style={btnStyle(C.amber)}>✏️ Iniciar Edição</button>
                      : <>
                          <button onClick={salvarEdicao} style={btnStyle(C.green)}>✓ Salvar</button>
                          <button onClick={()=>{setPontosEditados(null);setEditando(false);}} style={btnStyle(C.red)}>✕ Cancelar</button>
                        </>
                    }
                    <button onClick={()=>{setPontosEditados(null);gerarCurvaManual();}} style={btnStyle(C.purple)}>↺ Reset ao Perfil Padrão</button>
                  </div>
                  <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:6}}>
                    {HORAS.map((h,i)=>(
                      <div key={i} style={{background:C.rail,borderRadius:5,padding:"6px 8px",textAlign:"center"}}>
                        <div style={{color:C.muted,fontSize:9,marginBottom:3}}>{h}</div>
                        {editando
                          ? <input type="number" min={0} max={1} step={0.01}
                              value={(pontosEditados||curva.dados.map(d=>d.norm))[i]?.toFixed(3)}
                              onChange={e=>editarPonto(i, e.target.value)}
                              style={{...inpStyle,width:"100%",textAlign:"center",fontSize:11}}/>
                          : <div style={{fontFamily:"monospace",color:C.acc,fontSize:12,fontWeight:700}}>
                              {curva.dados[i].norm.toFixed(3)}
                            </div>
                        }
                        <div style={{fontSize:8,color:C.ghost,marginTop:2}}>{curva.dados[i].P.toFixed(0)} kW</div>
                      </div>
                    ))}
                  </div>
                </Card>

                {/* Visualização da edição */}
                {editando && pontosEditados && (
                  <Card title="Pré-visualização em Tempo Real">
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart data={pontosEditados.map((v,i)=>({hora:HORAS[i],norm:v,P:v*curva.dinst}))} margin={{top:5,right:10,bottom:5,left:0}}>
                        <defs>
                          <linearGradient id="gradE" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={C.amber} stopOpacity={0.5}/>
                            <stop offset="95%" stopColor={C.amber} stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
                        <XAxis dataKey="hora" tick={{fontSize:9,fill:C.muted}} interval={3}/>
                        <YAxis domain={[0,1.05]} tick={{fontSize:9,fill:C.muted}}/>
                        <Tooltip content={<CTooltip/>}/>
                        <Area type="monotone" dataKey="norm" name="Carga (p.u.)" stroke={C.amber} fill="url(#gradE)" dot={{r:3,fill:C.amber}} strokeWidth={2}/>
                      </AreaChart>
                    </ResponsiveContainer>
                  </Card>
                )}
              </div>
            )}

          </div>
        </main>
      </div>
    </div>
  );
}

// ─── Subcomponentes ──────────────────────────────────────────────────────────

function KpiCard({label,val,unit,cor,tip}){
  return (
    <div title={tip||""} style={{background:C.panel,border:`1px solid ${C.rail}`,borderRadius:7,padding:"11px 14px",borderTop:`3px solid ${cor}`,minWidth:120}}>
      <div style={{fontSize:9,color:C.ghost,textTransform:"uppercase",letterSpacing:.06,marginBottom:5}}>{label}</div>
      <div style={{fontFamily:"monospace",fontSize:22,fontWeight:700,color:cor,lineHeight:1}}>{val}</div>
      <div style={{fontSize:9,color:C.muted,marginTop:3}}>{unit}</div>
    </div>
  );
}

function Card({title,right,children}){
  return (
    <div style={{background:C.panel,border:`1px solid ${C.rail}`,borderRadius:8,padding:14}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
        <div style={{fontFamily:"monospace",fontSize:9,textTransform:"uppercase",letterSpacing:.1,color:C.ghost}}>{title}</div>
        {right && <div style={{fontFamily:"monospace",fontSize:9,color:C.acc}}>{right}</div>}
      </div>
      {children}
    </div>
  );
}

function Fld({label,children}){
  return (
    <div style={{marginBottom:10}}>
      <label style={{display:"block",fontSize:10,color:C.ghost,marginBottom:3}}>{label}</label>
      {children}
    </div>
  );
}

// Histograma de duração (load histogram)
function HistogramaDuracao({dados,Pmax}){
  const N=10;
  const step=Pmax/N;
  const bins=Array.from({length:N},(_,i)=>({
    range:`${(i*step).toFixed(0)}-${((i+1)*step).toFixed(0)}`,
    horas:dados.filter(d=>d.P>=i*step && d.P<(i+1)*step).length,
  }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={bins} margin={{top:5,right:10,bottom:20,left:0}}>
        <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
        <XAxis dataKey="range" tick={{fontSize:8,fill:C.muted}} angle={-30} textAnchor="end"/>
        <YAxis tick={{fontSize:9,fill:C.muted}} unit="h"/>
        <Tooltip content={<CTooltip/>}/>
        <Bar dataKey="horas" name="Horas" fill={C.purple} opacity={0.85}
          label={{position:"top",fill:C.muted,fontSize:8}}/>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Load Duration Curve
function LDCChart({dados}){
  const sorted=[...dados].sort((a,b)=>b.P-a.P).map((d,i)=>({hora:i+1,P:d.P}));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={sorted} margin={{top:5,right:20,bottom:5,left:0}}>
        <defs>
          <linearGradient id="gradLDC" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={C.purple} stopOpacity={0.4}/>
            <stop offset="95%" stopColor={C.purple} stopOpacity={0.02}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
        <XAxis dataKey="hora" tick={{fontSize:9,fill:C.muted}} label={{value:"Horas (ordenadas)",position:"insideBottom",fill:C.muted,fontSize:9,offset:-2}}/>
        <YAxis tick={{fontSize:9,fill:C.muted}} unit=" kW"/>
        <Tooltip content={<CTooltip/>}/>
        <Area type="stepAfter" dataKey="P" name="Demanda" unit=" kW" stroke={C.purple} fill="url(#gradLDC)" strokeWidth={2} dot={false}/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Painel de fórmulas
function FormulasPanel({factors,fp}){
  const rows=[
    ["Fator de Carga (FC)","FC = D_med / D_máx","Indica aproveitamento da infraestrutura",`${(factors.fc*100).toFixed(1)}%`],
    ["Fator de Variação (FCV)","FCV = D_min / D_máx","Quanto a carga oscila durante o período",`${(factors.fcv*100).toFixed(1)}%`],
    ["Fator de Demanda (FD)","FD = D_máx / D_inst","Relação entre pico e potência instalada",`${(factors.Pmax/(factors.Pmax/factors.fcv||1)*100).toFixed(0)}%`],
    ["Horas de Utilização","h_util = E / D_máx","Equivalente em horas a plena carga",`${factors.hutil.toFixed(1)} h`],
    ["Perda Reativa","Q = P × tan(φ)","Potência reativa necessária",`φ = ${(Math.acos(fp)*180/Math.PI).toFixed(1)}°`],
    ["Potência Aparente","S = P / FP","Dimensiona transformadores e cabos","S = P/"+fp],
  ];
  return (
    <div>
      {rows.map(([nome,formula,desc,val])=>(
        <div key={nome} style={{padding:"7px 0",borderBottom:`1px solid ${C.rail}`}}>
          <div style={{display:"flex",justifyContent:"space-between"}}>
            <span style={{color:C.text,fontWeight:600,fontSize:11}}>{nome}</span>
            <span style={{fontFamily:"monospace",color:C.acc,fontSize:11}}>{val}</span>
          </div>
          <div style={{fontFamily:"monospace",color:C.amber,fontSize:10,marginTop:2}}>{formula}</div>
          <div style={{color:C.muted,fontSize:10,marginTop:1}}>{desc}</div>
        </div>
      ))}
    </div>
  );
}

// FP sob carga baixa — conceito dos artigos OSE
function FPBaixaCarga({dados,fp}){
  // Modelagem do FP em regime de carga parcial
  // Em baixa carga, motores e reatores operam com FP pior
  // fp_real(P) ≈ fp_nominal × (P/Pmax)^α, α ≈ 0.15 para cargas mistas
  const Pmax=Math.max(...dados.map(d=>d.P));
  const enriched=dados.map(d=>{
    const ratio=d.P/Pmax;
    const fp_baixa=fp*Math.pow(ratio,0.12); // degradação em carga parcial
    const fp_ind=fp*Math.pow(ratio,0.08);
    return {...d, fp_real:+fp_baixa.toFixed(4), fp_ind:+fp_ind.toFixed(4), ratio:+ratio.toFixed(3)};
  });
  return (
    <div>
      <div style={{color:C.ghost,fontSize:10,marginBottom:8,lineHeight:1.5}}>
        Em regime de carga baixa, o fator de potência se degrada devido ao comportamento indutivo de transformadores,
        motores em vazio e reatores. Conforme Starosta (OSE), abaixo de 40% da carga nominal,
        o FP pode cair significativamente aumentando a corrente de circulação.
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={enriched} margin={{top:5,right:20,bottom:5,left:0}}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.rail}/>
          <XAxis dataKey="hora" tick={{fontSize:9,fill:C.muted}} interval={2}/>
          <YAxis domain={[0.5,1.0]} tick={{fontSize:9,fill:C.muted}}/>
          <Tooltip content={<CTooltip/>}/>
          <ReferenceLine y={0.92} stroke={C.red} strokeDasharray="4 3"
            label={{value:"Limite ANEEL 0,92",fill:C.red,fontSize:9,position:"right"}}/>
          <Line type="monotone" dataKey="fp_real" name="FP Real (c.parcial)" stroke={C.amber} dot={false} strokeWidth={2}/>
          <Line type="monotone" dataKey="fp_ind" name="FP Indutivo" stroke={C.red} dot={false} strokeWidth={1.5} strokeDasharray="4 2"/>
          <ReferenceLine y={fp} stroke={C.green} strokeDasharray="5 3"
            label={{value:`FP nominal=${fp}`,fill:C.green,fontSize:9}}/>
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Estilos utilitários ─────────────────────────────────────────────────────
const sgStyle={fontFamily:"monospace",fontSize:9,letterSpacing:.1,textTransform:"uppercase",
  color:C.acc,marginTop:16,marginBottom:8,paddingBottom:4,borderBottom:`1px solid ${C.rail}`};
const inpStyle={width:"100%",background:C.rail,border:`1px solid #243448`,borderRadius:4,
  color:C.text,padding:"5px 8px",fontFamily:"monospace",fontSize:11,outline:"none"};
const selStyle={...{},width:"100%",background:C.rail,border:`1px solid #243448`,borderRadius:4,
  color:C.text,padding:"5px 8px",fontFamily:"monospace",fontSize:11,outline:"none"};
const thStyle={padding:"5px 8px",textAlign:"right",color:C.ghost,fontFamily:"monospace",
  fontSize:9,letterSpacing:.06,textTransform:"uppercase"};
function btnStyle(col){
  return {background:`${col}22`,border:`1px solid ${col}`,color:col,borderRadius:5,
    padding:"5px 12px",fontSize:11,cursor:"pointer",fontWeight:600};
}
