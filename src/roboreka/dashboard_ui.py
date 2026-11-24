"""Self-contained Scratch-like block editor and step-by-step web UI for Roboreka."""

from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Roboreka — Scratch Arm Studio</title>
<style>
:root{
  --bg:#e9eef5;
  --surface:#ffffff;
  --surface-alt:#f4f7fb;
  --workspace-bg:#f9fafc;
  --dot:#d7e0ec;
  --line:#d5dde8;
  --text:#25313f;
  --muted:#607085;
  --scratch-blue:#4D97FF;
  --scratch-blue-dark:#3373CC;
  --events:#FFBF00;
  --events-border:#CC9900;
  --motion:#4C97FF;
  --motion-border:#3373CC;
  --control:#FFAB19;
  --control-border:#CF8B17;
  --presets:#9966FF;
  --presets-border:#774DCB;
  --ok:#0FBD8C;
  --ok-dark:#0B8E69;
  --danger:#FF6680;
  --danger-dark:#D94B64;
  --running-glow:#FFE600;
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  background:var(--bg);
  color:var(--text);
  font:14px/1.45 "Segoe UI",system-ui,-apple-system,sans-serif;
}
button,input,select,textarea{font:inherit}

/* Top Bar */
.topbar{
  background:var(--scratch-blue);
  color:#fff;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  padding:8px 16px;
  box-shadow:0 2px 6px rgba(25,52,94,.18);
  flex-wrap:wrap;
  position:sticky;
  top:0;
  z-index:30;
}
.brand{
  display:flex;
  align-items:center;
  gap:10px;
}
.brand-logo{
  width:30px;height:30px;
  border-radius:8px;
  background:rgba(255,255,255,.22);
  display:grid;place-items:center;
  font-weight:800;font-size:16px;
  border:1px solid rgba(255,255,255,.35);
}
.brand h1{margin:0;font-size:1.1rem;font-weight:800;letter-spacing:.2px}
.brand-badge{
  font-size:.75rem;font-weight:700;
  background:rgba(255,255,255,.2);
  padding:2px 8px;border-radius:999px;
  border:1px solid rgba(255,255,255,.3);
}
.nav-tabs{
  display:flex;
  gap:6px;
  background:rgba(0,0,0,.12);
  padding:3px;
  border-radius:10px;
}
.nav-tab{
  background:transparent;
  color:rgba(255,255,255,.9);
  border:0;
  border-radius:8px;
  padding:6px 13px;
  font-weight:700;
  cursor:pointer;
}
.nav-tab:hover{background:rgba(255,255,255,.15)}
.nav-tab.active{
  background:#fff;
  color:var(--scratch-blue-dark);
  box-shadow:0 1px 3px rgba(0,0,0,.14);
}
.topbar-right{
  display:flex;
  align-items:center;
  gap:8px;
  flex-wrap:wrap;
}
.status-pill{
  font-size:.78rem;font-weight:700;
  background:rgba(255,255,255,.18);
  border:1px solid rgba(255,255,255,.28);
  border-radius:999px;
  padding:4px 10px;
  white-space:nowrap;
}
.status-pill.ok{background:rgba(15,189,140,.28);border-color:rgba(255,255,255,.45)}
.status-pill.warn{background:rgba(255,102,128,.35);border-color:rgba(255,255,255,.45)}
.guide-toggle{
  background:#fff;
  color:var(--scratch-blue-dark);
  border:0;
  border-radius:8px;
  padding:6px 12px;
  font-weight:700;
  cursor:pointer;
}
.guide-toggle:hover{background:#f0f6ff}

/* Main container */
.app-shell{
  max-width:1460px;
  margin:0 auto;
  padding:12px 14px 20px;
}
.tab-panel{display:none}
.tab-panel.active{display:block}

/* Step-by-step Instructions Card */
.guide-card{
  background:var(--surface);
  border:2px solid #b9d4ff;
  border-radius:12px;
  padding:12px 16px;
  margin-bottom:12px;
  box-shadow:0 2px 8px rgba(45,85,140,.08);
}
.guide-card.hidden{display:none}
.guide-header{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  flex-wrap:wrap;
  margin-bottom:8px;
}
.guide-title-wrap{
  display:flex;
  align-items:center;
  gap:10px;
  flex-wrap:wrap;
}
.guide-title{margin:0;font-size:1rem;font-weight:800;color:var(--scratch-blue-dark)}
.guide-step-counter{
  font-size:.8rem;font-weight:700;
  color:var(--muted);
  background:var(--surface-alt);
  border:1px solid var(--line);
  padding:2px 9px;border-radius:999px;
}
.guide-done-badge{
  font-size:.78rem;font-weight:800;
  color:#fff;
  background:var(--ok);
  padding:2px 9px;border-radius:999px;
  display:none;
}
.guide-done-badge.visible{display:inline-block}
.guide-dots{
  display:flex;
  align-items:center;
  gap:6px;
}
.guide-dot{
  width:24px;height:24px;
  border-radius:50%;
  border:2px solid var(--line);
  background:var(--surface-alt);
  color:var(--muted);
  font-size:.75rem;font-weight:800;
  cursor:pointer;
  display:grid;place-items:center;
  padding:0;
}
.guide-dot.active{
  border-color:var(--scratch-blue);
  background:var(--scratch-blue);
  color:#fff;
}
.guide-dot.completed:not(.active){
  border-color:var(--ok);
  background:#e7fbf4;
  color:var(--ok-dark);
}
.guide-body{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  flex-wrap:wrap;
}
.guide-copy{flex:1;min-width:240px}
.guide-step-heading{font-weight:800;font-size:.98rem;margin-bottom:3px}
.guide-step-desc{color:var(--muted);font-size:.9rem}
.guide-actions{
  display:flex;
  align-items:center;
  gap:8px;
  flex-wrap:wrap;
}

/* Generic buttons */
.btn{
  border:1px solid var(--line);
  background:var(--surface);
  color:var(--text);
  border-radius:8px;
  padding:6px 12px;
  font-weight:700;
  cursor:pointer;
  transition:transform .06s ease, background .12s ease;
}
.btn:hover:not(:disabled){background:var(--surface-alt)}
.btn:active:not(:disabled){transform:translateY(1px)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-primary{
  background:var(--scratch-blue);
  border-color:var(--scratch-blue-dark);
  color:#fff;
}
.btn-primary:hover:not(:disabled){background:var(--scratch-blue-dark)}
.btn-success{
  background:var(--ok);
  border-color:var(--ok-dark);
  color:#fff;
}
.btn-success:hover:not(:disabled){background:var(--ok-dark)}
.btn-warn{
  background:var(--control);
  border-color:var(--control-border);
  color:#fff;
}
.btn-warn:hover:not(:disabled){background:var(--control-border)}
.btn-danger{
  background:var(--danger);
  border-color:var(--danger-dark);
  color:#fff;
}
.btn-danger:hover:not(:disabled){background:var(--danger-dark)}
.btn-sm{padding:4px 9px;font-size:.82rem;border-radius:6px}

/* 3-Column Scratch Studio Layout */
.studio-grid{
  display:grid;
  grid-template-columns:276px 1fr 370px;
  gap:12px;
  align-items:start;
}
.pane{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:12px;
  overflow:hidden;
  box-shadow:0 2px 8px rgba(32,52,79,.06);
}
.pane-header{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  padding:10px 12px;
  background:var(--surface-alt);
  border-bottom:1px solid var(--line);
}
.pane-header h2{margin:0;font-size:.95rem;font-weight:800}

/* Left Pane: Palette */
.palette-body{
  display:grid;
  grid-template-columns:72px 1fr;
  min-height:580px;
}
.category-rail{
  background:var(--surface-alt);
  border-right:1px solid var(--line);
  padding:8px 4px;
  display:flex;
  flex-direction:column;
  gap:6px;
}
.cat-btn{
  border:0;
  background:transparent;
  border-radius:8px;
  padding:8px 4px;
  cursor:pointer;
  display:flex;
  flex-direction:column;
  align-items:center;
  gap:4px;
  font-size:.74rem;
  font-weight:700;
  color:var(--muted);
}
.cat-btn:hover{background:#e9eff7;color:var(--text)}
.cat-btn.active{background:#dce9fc;color:var(--scratch-blue-dark)}
.cat-dot{
  width:20px;height:20px;
  border-radius:50%;
  border:2px solid rgba(0,0,0,.15);
}
.palette-drawer{
  padding:10px;
  display:flex;
  flex-direction:column;
  gap:10px;
  max-height:680px;
  overflow-y:auto;
}
.palette-group-title{
  font-size:.75rem;
  font-weight:800;
  text-transform:uppercase;
  letter-spacing:.5px;
  color:var(--muted);
  margin:2px 0 0;
}
.palette-item{
  border-radius:8px;
  padding:9px 10px;
  color:#fff;
  font-weight:700;
  font-size:.84rem;
  cursor:grab;
  user-select:none;
  box-shadow:0 2px 0 rgba(0,0,0,.18);
  border:1px solid rgba(0,0,0,.15);
  display:flex;
  flex-direction:column;
  gap:3px;
  transition:transform .08s ease, box-shadow .08s ease;
}
.palette-item:hover{transform:translateY(-1px);box-shadow:0 3px 6px rgba(0,0,0,.18)}
.palette-item:active{cursor:grabbing}
.palette-item small{font-weight:600;opacity:.92;font-size:.75rem}
.palette-item.cat-events{background:var(--events);border-color:var(--events-border);color:#3b2c00}
.palette-item.cat-motion{background:var(--motion);border-color:var(--motion-border)}
.palette-item.cat-control{background:var(--control);border-color:var(--control-border)}
.palette-item.cat-presets{background:var(--presets);border-color:var(--presets-border)}

/* Center Pane: Script Workspace */
.workspace-toolbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  padding:10px 12px;
  background:var(--surface-alt);
  border-bottom:1px solid var(--line);
  flex-wrap:wrap;
}
.workspace-title-group{
  display:flex;
  align-items:center;
  gap:8px;
  flex-wrap:wrap;
}
.workspace-title-group h2{margin:0;font-size:.98rem;font-weight:800}
.workspace-meta{
  font-size:.78rem;font-weight:700;
  color:var(--muted);
  background:#fff;
  border:1px solid var(--line);
  padding:2px 8px;border-radius:999px;
}
.dirty-dot{
  width:8px;height:8px;border-radius:50%;
  background:var(--control);
  display:none;
}
.dirty-dot.visible{display:inline-block}
.workspace-actions{
  display:flex;
  align-items:center;
  gap:6px;
  flex-wrap:wrap;
}
.workspace-status{
  padding:6px 12px;
  background:#f8fbff;
  border-bottom:1px solid var(--line);
  font-size:.84rem;
  color:var(--muted);
  min-height:30px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
}
#sequence-message{font-weight:700;color:var(--scratch-blue-dark)}
#sequence-message.error{color:var(--danger-dark)}

.canvas-area{
  background-color:var(--workspace-bg);
  background-image:radial-gradient(var(--dot) 1.3px, transparent 1.3px);
  background-size:18px 18px;
  padding:18px 16px 28px;
  min-height:540px;
}
.script-column{
  max-width:640px;
}

/* Scratch Hat Block */
.hat-block{
  position:relative;
  background:var(--events);
  border:1.5px solid var(--events-border);
  color:#3b2c00;
  border-radius:22px 22px 6px 6px;
  padding:11px 14px;
  font-weight:800;
  font-size:.95rem;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  box-shadow:0 2px 0 rgba(0,0,0,.14);
  margin-bottom:0;
  z-index:2;
}
.hat-block.pulse{
  box-shadow:0 0 0 4px var(--running-glow), 0 4px 12px rgba(0,0,0,.16);
}
.hat-block::after{
  content:"";
  position:absolute;
  left:22px;
  bottom:-7px;
  width:28px;
  height:7px;
  background:var(--events);
  border-left:1.5px solid var(--events-border);
  border-right:1.5px solid var(--events-border);
  border-bottom:1.5px solid var(--events-border);
  border-radius:0 0 5px 5px;
}
.hat-label{display:flex;align-items:center;gap:8px}

/* Block Stack & Puzzle Pieces */
.block-list{
  display:flex;
  flex-direction:column;
  padding-top:4px;
  min-height:84px;
}
.drop-slot{
  height:6px;
  border-radius:4px;
  transition:height .1s ease, background .1s ease;
}
.drop-slot.active{
  height:14px;
  background:rgba(77,151,255,.35);
  border:2px dashed var(--scratch-blue-dark);
  margin:3px 0;
}
.empty-dropzone{
  margin:12px 0;
  padding:22px 16px;
  border:2px dashed #9fb7d6;
  border-radius:10px;
  background:rgba(255,255,255,.8);
  text-align:center;
  color:var(--muted);
}
.empty-dropzone.drag-over{
  border-color:var(--scratch-blue);
  background:#eaf3ff;
  color:var(--scratch-blue-dark);
}

.scratch-block{
  position:relative;
  border-radius:7px;
  padding:10px 12px 11px;
  color:#fff;
  cursor:grab;
  border:1.5px solid rgba(0,0,0,.2);
  box-shadow:0 2px 0 rgba(0,0,0,.16);
  margin-top:-1px;
  transition:box-shadow .12s ease, opacity .12s ease;
}
.scratch-block.type-move_joint,
.scratch-block.type-nudge_joint,
.scratch-block.type-move_pose,
.scratch-block.type-home{
  background:var(--motion);
  border-color:var(--motion-border);
}
.scratch-block.type-wait{
  background:var(--control);
  border-color:var(--control-border);
}
/* Interlocking notch & tab */
.scratch-block::before{
  content:"";
  position:absolute;
  top:-1.5px;
  left:22px;
  width:28px;
  height:6px;
  background:rgba(0,0,0,.15);
  border-radius:0 0 4px 4px;
}
.scratch-block::after{
  content:"";
  position:absolute;
  left:22px;
  bottom:-7px;
  width:28px;
  height:6px;
  background:inherit;
  border-left:1.5px solid rgba(0,0,0,.2);
  border-right:1.5px solid rgba(0,0,0,.2);
  border-bottom:1.5px solid rgba(0,0,0,.2);
  border-radius:0 0 5px 5px;
  z-index:2;
}
.scratch-block.dragging{opacity:.42}
.scratch-block.is-running{
  box-shadow:0 0 0 4px var(--running-glow), 0 6px 16px rgba(0,0,0,.25);
  z-index:5;
}
.scratch-block.is-next{
  box-shadow:0 0 0 3px #fff, 0 0 0 5px var(--ok);
  z-index:4;
}

.block-row{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  flex-wrap:wrap;
}
.block-main{
  display:flex;
  align-items:center;
  gap:7px;
  flex-wrap:wrap;
  flex:1;
  font-weight:700;
}
.step-badge{
  min-width:24px;height:24px;
  padding:0 6px;
  border-radius:999px;
  background:rgba(0,0,0,.22);
  display:inline-flex;
  align-items:center;
  justify-content:center;
  font-size:.76rem;
  font-weight:800;
}
.step-badge.done{background:var(--ok)}
.next-tag{
  font-size:.7rem;
  font-weight:800;
  background:#fff;
  color:var(--ok-dark);
  padding:1px 6px;
  border-radius:999px;
  text-transform:uppercase;
}
.pill-select,.pill-input{
  background:#fff;
  color:var(--text);
  border:1px solid rgba(0,0,0,.22);
  border-radius:999px;
  padding:3px 9px;
  font-weight:700;
  font-size:.86rem;
}
.pill-input{width:72px;text-align:center}
.block-range{
  width:110px;
  accent-color:#fff;
  cursor:pointer;
}
.block-actions{
  display:flex;
  align-items:center;
  gap:4px;
}
.blk-btn{
  border:0;
  background:rgba(0,0,0,.18);
  color:#fff;
  border-radius:6px;
  padding:4px 7px;
  font-weight:800;
  font-size:.78rem;
  cursor:pointer;
}
.blk-btn:hover:not(:disabled){background:rgba(0,0,0,.32)}
.blk-btn:disabled{opacity:.38;cursor:not-allowed}

/* Pose joint matrix inside move_pose block */
.pose-joints-box{
  margin-top:8px;
  background:rgba(0,0,0,.14);
  border-radius:8px;
  padding:7px 9px;
  display:grid;
  gap:5px;
}
.pose-joint-row{
  display:grid;
  grid-template-columns:auto minmax(74px,1fr) 1.5fr 68px;
  align-items:center;
  gap:7px;
  font-size:.82rem;
}
.pose-joint-row input[type=checkbox]{width:15px;height:15px;accent-color:#fff;cursor:pointer}
.pose-joint-row input[type=range]{width:100%;accent-color:#fff;cursor:pointer}
.pose-joint-row input[type=number]{
  width:100%;
  background:#fff;color:var(--text);
  border:1px solid rgba(0,0,0,.2);
  border-radius:999px;padding:2px 7px;text-align:center;font-weight:700;
}
.pose-joint-row.unchecked{opacity:.6}

/* Bottom Cap Block */
.cap-block{
  margin-top:5px;
  background:#5c6c80;
  border:1.5px solid #445263;
  color:#fff;
  border-radius:6px 6px 16px 16px;
  padding:9px 14px;
  font-weight:700;
  font-size:.86rem;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  flex-wrap:wrap;
  position:relative;
}
.cap-block::before{
  content:"";
  position:absolute;
  top:-1.5px;left:22px;
  width:28px;height:6px;
  background:rgba(0,0,0,.18);
  border-radius:0 0 4px 4px;
}
.cap-toggle{
  display:flex;align-items:center;gap:6px;
  font-size:.8rem;font-weight:600;cursor:pointer;
}

/* Right Pane: Stage & Live Control */
.right-stack{
  display:flex;
  flex-direction:column;
  gap:12px;
}
.stage-controls{
  display:flex;
  align-items:center;
  gap:6px;
  flex-wrap:wrap;
}
.stage-status-bar{
  padding:6px 12px;
  font-size:.82rem;
  font-weight:700;
  color:var(--muted);
  background:#f8fafd;
  border-bottom:1px solid var(--line);
  min-height:28px;
}
.stage-canvas-wrap{
  padding:10px 12px 6px;
  background:linear-gradient(180deg,#f5f9ff 0%,#eef3fa 100%);
  position:relative;
}
#arm-stage-svg{
  width:100%;
  height:auto;
  display:block;
  border-radius:8px;
  background:#ffffff;
  border:1px solid var(--line);
}
.stage-joints{
  padding:10px 12px 12px;
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:8px;
}
.joint-chip{
  background:var(--surface-alt);
  border:1px solid var(--line);
  border-radius:8px;
  padding:7px 9px;
}
.joint-chip-head{
  display:flex;justify-content:space-between;align-items:center;
  font-size:.8rem;font-weight:800;margin-bottom:4px;
}
.joint-chip-bar{
  height:6px;border-radius:999px;
  background:#dce5f0;overflow:hidden;
}
.joint-chip-fill{
  height:100%;
  background:var(--scratch-blue);
  transition:width .15s ease;
}
.joint-chip-sub{font-size:.72rem;color:var(--muted);margin-top:3px}

/* Live arm control card */
.live-body{padding:12px}
.joint-control{
  display:grid;
  grid-template-columns:68px 1fr 68px;
  align-items:center;
  gap:8px;
  margin-bottom:10px;
}
.joint-control label{font-weight:700;font-size:.84rem;color:var(--muted)}
.joint-control select,.joint-control input[type=number]{
  width:100%;
  background:#fff;
  color:var(--text);
  border:1px solid var(--line);
  border-radius:8px;
  padding:6px 8px;
  font-weight:700;
}
.joint-control input[type=range]{width:100%;accent-color:var(--scratch-blue)}
.builder-actions{
  display:flex;
  gap:6px;
  flex-wrap:wrap;
  align-items:center;
}
.hint{color:var(--muted);font-size:.82rem}
#control-message{display:block;margin-top:8px;min-height:1.3em;font-weight:700;color:var(--scratch-blue-dark)}

/* Tab 2 & Tab 3 */
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
  gap:12px;
  margin-bottom:14px;
}
.card{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:12px;
  padding:14px 16px;
}
.card .label{color:var(--muted);font-size:.84rem;font-weight:700}
.card .value{font-size:1.3rem;font-weight:800;margin-top:4px}
.panel-section{
  background:var(--surface);
  border:1px solid var(--line);
  border-radius:12px;
  padding:16px;
  margin-bottom:14px;
}
.panel-section h2{margin:0 0 10px;font-size:1.05rem}
.joint{
  display:grid;
  grid-template-columns:1fr 1fr 1fr;
  gap:10px;
  padding:8px 0;
  border-bottom:1px solid var(--line);
}
.joint:last-child{border:0}
textarea#config{
  width:100%;
  min-height:340px;
  background:#0f1722;
  color:#e6f1fa;
  border:1px solid var(--line);
  border-radius:8px;
  padding:12px;
  font:13px/1.5 ui-monospace,Consolas,monospace;
  resize:vertical;
}
#message{min-height:1.4em;margin-top:8px;font-weight:700;color:var(--scratch-blue-dark)}
pre#logs{
  white-space:pre-wrap;
  overflow-wrap:anywhere;
  max-height:560px;
  overflow:auto;
  background:#0f1722;
  color:#d9e8f5;
  padding:12px;
  border-radius:8px;
  font:12px/1.5 ui-monospace,Consolas,monospace;
}

@media(max-width:1120px){
  .studio-grid{grid-template-columns:250px 1fr}
  .right-stack{grid-column:1 / -1;display:grid;grid-template-columns:1fr 1fr}
}
@media(max-width:760px){
  .studio-grid{grid-template-columns:1fr}
  .right-stack{grid-template-columns:1fr}
  .palette-body{min-height:auto}
  .stage-joints{grid-template-columns:1fr}
  .joint{grid-template-columns:1fr}
}
</style>
</head>
<body>
<header class="topbar">
  <div class="brand">
    <div class="brand-logo" aria-hidden="true">R</div>
    <h1>Roboreka</h1>
    <span class="brand-badge">Scratch Arm Studio</span>
  </div>
  <nav class="nav-tabs" aria-label="Workspace views">
    <button id="tab-btn-blocks" class="nav-tab active" type="button" data-tab="blocks">Blocks</button>
    <button id="tab-btn-config" class="nav-tab" type="button" data-tab="config">Config &amp; Stats</button>
    <button id="tab-btn-logs" class="nav-tab" type="button" data-tab="logs">Logs</button>
  </nav>
  <div class="topbar-right">
    <span id="pill-service" class="status-pill">Connecting…</span>
    <span id="pill-calls" class="status-pill">Calls: 0 / 1</span>
    <span id="pill-i2c" class="status-pill">I²C: …</span>
    <span id="pill-uptime" class="status-pill">0h 0m</span>
    <button id="toggle-guide" class="guide-toggle" type="button">Hide guide</button>
  </div>
</header>

<main class="app-shell">
  <!-- TAB 1: SCRATCH BLOCK EDITOR -->
  <div id="tab-blocks" class="tab-panel active">
    <section id="guide-card" class="guide-card" aria-label="Step-by-step instructions">
      <div class="guide-header">
        <div class="guide-title-wrap">
          <h2 class="guide-title">Step-by-step instructions</h2>
          <span id="guide-counter" class="guide-step-counter">Step 1 of 6</span>
          <span id="guide-done" class="guide-done-badge">✓ Completed</span>
        </div>
        <div id="guide-dots" class="guide-dots" aria-label="Tutorial steps"></div>
      </div>
      <div class="guide-body">
        <div class="guide-copy">
          <div id="guide-heading" class="guide-step-heading"></div>
          <div id="guide-desc" class="guide-step-desc"></div>
        </div>
        <div class="guide-actions">
          <button id="guide-helper" class="btn btn-primary btn-sm" type="button"></button>
          <button id="guide-prev" class="btn btn-sm" type="button">Prev</button>
          <button id="guide-next" class="btn btn-sm" type="button">Next</button>
          <button id="guide-hide" class="btn btn-sm" type="button">Hide</button>
        </div>
      </div>
    </section>

    <div class="studio-grid">
      <!-- LEFT PANE: BLOCK PALETTE -->
      <section class="pane" aria-label="Block palette">
        <div class="pane-header">
          <h2>Block palette</h2>
          <span class="hint">Click or drag</span>
        </div>
        <div class="palette-body">
          <div class="category-rail" role="tablist" aria-label="Block categories">
            <button class="cat-btn" type="button" data-cat="events">
              <span class="cat-dot" style="background:#FFBF00"></span>Events
            </button>
            <button class="cat-btn active" type="button" data-cat="motion">
              <span class="cat-dot" style="background:#4C97FF"></span>Motion
            </button>
            <button class="cat-btn" type="button" data-cat="control">
              <span class="cat-dot" style="background:#FFAB19"></span>Control
            </button>
            <button class="cat-btn" type="button" data-cat="presets">
              <span class="cat-dot" style="background:#9966FF"></span>Presets
            </button>
          </div>
          <div id="palette-drawer" class="palette-drawer"></div>
        </div>
      </section>

      <!-- CENTER PANE: WORKSPACE -->
      <section class="pane" aria-label="Script workspace">
        <div class="workspace-toolbar">
          <div class="workspace-title-group">
            <h2>Call action blocks</h2>
            <span id="dirty-dot" class="dirty-dot" title="Unsaved changes"></span>
            <span id="workspace-summary" class="workspace-meta">0 blocks · 0.0s wait</span>
          </div>
          <div class="workspace-actions">
            <button id="btn-undo" class="btn btn-sm" type="button" title="Undo">Undo</button>
            <button id="btn-redo" class="btn btn-sm" type="button" title="Redo">Redo</button>
            <button id="btn-clear" class="btn btn-sm" type="button" title="Clear blocks">Clear</button>
            <button id="save-sequence" class="btn btn-success btn-sm" type="button">Save call action</button>
          </div>
        </div>
        <div class="workspace-status">
          <span id="sequence-message" role="status">Drag blocks here or click a block in the palette to snap it below.</span>
          <span class="hint">Runs when a SIP call connects</span>
        </div>
        <div class="canvas-area">
          <div class="script-column">
            <div id="hat-block" class="hat-block">
              <span class="hat-label">📞 When call connects</span>
              <button id="hat-run" class="btn btn-sm" type="button">▶ Test</button>
            </div>
            <div id="pose-blocks" class="block-list"></div>
            <div class="cap-block">
              <span>🏠 End — return all joints to home</span>
              <label class="cap-toggle">
                <input id="run-return-home" type="checkbox" checked>
                Return home on test run
              </label>
            </div>
          </div>
        </div>
      </section>

      <!-- RIGHT PANE: STAGE & LIVE CONTROL -->
      <div class="right-stack">
        <section class="pane" aria-label="Robot arm stage">
          <div class="pane-header">
            <h2>Stage</h2>
            <div class="stage-controls">
              <button id="btn-run" class="btn btn-success btn-sm" type="button" title="Run all blocks from the top">🚩 Run</button>
              <button id="btn-step" class="btn btn-primary btn-sm" type="button" title="Run one step at a time">⏭ Step</button>
              <button id="btn-reset-steps" class="btn btn-sm" type="button" title="Reset step cursor">↺</button>
              <button id="btn-stop" class="btn btn-danger btn-sm" type="button" title="Stop script and arm motion">🛑 Stop</button>
            </div>
          </div>
          <div id="stage-status" class="stage-status-bar" role="status">Ready — click Run or Step to test your blocks.</div>
          <div class="stage-canvas-wrap">
            <svg id="arm-stage-svg" viewBox="0 0 340 215" role="img" aria-label="Live 2D robot arm position preview">
              <defs>
                <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#f7fbff"/>
                  <stop offset="100%" stop-color="#eaf1fa"/>
                </linearGradient>
              </defs>
              <rect x="0" y="0" width="340" height="215" fill="url(#skyGrad)"/>
              <line x1="16" y1="184" x2="324" y2="184" stroke="#b9c8db" stroke-width="3" stroke-linecap="round"/>
              <!-- Base rotation compass dial -->
              <g transform="translate(52,46)">
                <circle cx="0" cy="0" r="28" fill="#ffffff" stroke="#c3d2e6" stroke-width="2"/>
                <path d="M -22 0 A 22 22 0 0 1 22 0" fill="none" stroke="#dbe6f4" stroke-width="4" stroke-linecap="round"/>
                <text x="0" y="-33" text-anchor="middle" font-size="9" font-weight="700" fill="#607085">BASE</text>
                <g id="svg-base-needle" transform="rotate(0)">
                  <line x1="0" y1="4" x2="0" y2="-21" stroke="#4D97FF" stroke-width="3.5" stroke-linecap="round"/>
                  <circle cx="0" cy="-21" r="3" fill="#FFAB19"/>
                </g>
                <circle cx="0" cy="0" r="4" fill="#3b4d63"/>
                <text id="svg-base-label" x="0" y="18" text-anchor="middle" font-size="9" font-weight="800" fill="#25313f">90°</text>
              </g>
              <!-- Pedestal -->
              <rect x="144" y="164" width="52" height="20" rx="5" fill="#4f647d"/>
              <rect x="157" y="148" width="26" height="18" rx="4" fill="#677f9b"/>
              <!-- Articulated arm links updated by JS -->
              <g id="svg-arm-group">
                <line id="svg-link-upper" x1="170" y1="148" x2="170" y2="86" stroke="#4D97FF" stroke-width="11" stroke-linecap="round"/>
                <line id="svg-link-fore" x1="170" y1="86" x2="232" y2="86" stroke="#3373CC" stroke-width="9" stroke-linecap="round"/>
                <g id="svg-gripper" transform="translate(232,86) rotate(0)">
                  <rect x="-4" y="-5" width="10" height="10" rx="3" fill="#3b4d63"/>
                  <path id="svg-jaw-top" d="M 6 -3 L 20 -9 L 23 -5" fill="none" stroke="#FFAB19" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path id="svg-jaw-bot" d="M 6 3 L 20 9 L 23 5" fill="none" stroke="#FFAB19" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
                </g>
                <circle id="svg-joint-shoulder" cx="170" cy="148" r="7" fill="#fff" stroke="#3373CC" stroke-width="3"/>
                <circle id="svg-joint-elbow" cx="170" cy="86" r="6" fill="#fff" stroke="#3373CC" stroke-width="3"/>
              </g>
              <rect x="218" y="10" width="112" height="22" rx="11" fill="#ffffff" stroke="#d5dde8"/>
              <text id="svg-stage-badge" x="274" y="25" text-anchor="middle" font-size="10" font-weight="800" fill="#3373CC">IDLE</text>
            </svg>
          </div>
          <div id="stage-joints" class="stage-joints"></div>
        </section>

        <section class="pane" aria-label="Live arm control">
          <div class="pane-header">
            <h2>Live arm control</h2>
            <button id="capture-pose" class="btn btn-primary btn-sm" type="button">Capture pose</button>
          </div>
          <div class="live-body">
            <div class="joint-control">
              <label for="control-joint">Servo</label>
              <select id="control-joint"></select>
              <span id="control-range" class="hint"></span>
            </div>
            <div class="joint-control">
              <label for="control-angle">Rotation</label>
              <input id="control-angle" type="range">
              <input id="control-angle-number" type="number" aria-label="Target rotation in degrees">
            </div>
            <div class="builder-actions">
              <button id="move-joint" class="btn btn-primary btn-sm" type="button">Move joint</button>
              <button id="home-arm" class="btn btn-sm" type="button">Home all</button>
              <button id="stop-arm" class="btn btn-warn btn-sm" type="button">Stop motion</button>
              <button id="release-arm" class="btn btn-danger btn-sm" type="button">Release servos</button>
            </div>
            <span id="control-message" class="hint" role="status"></span>
          </div>
        </section>
      </div>
    </div>
  </div>

  <!-- TAB 2: CONFIG & STATS -->
  <div id="tab-config" class="tab-panel">
    <div id="stats" class="grid" aria-live="polite"></div>
    <section class="panel-section">
      <h2>Configuration stats</h2>
      <div id="configuration" class="hint">Loading…</div>
      <div id="joints"></div>
    </section>
    <section class="panel-section">
      <h2>Configuration file</h2>
      <p class="hint">Set each servo output in its <code>[[arm.joints]]</code> block with <code>channel = 0</code> through <code>15</code>. Each servo must use a different channel. Changes to <code>[[arm.call_sequence]]</code> are also updated automatically when you click <strong>Save call action</strong> in the Blocks tab. Restart Roboreka after saving configuration changes.</p>
      <textarea id="config" spellcheck="false" aria-label="Roboreka TOML configuration"></textarea><br>
      <button id="save" class="btn btn-primary" type="button">Save configuration</button>
      <div id="message" role="status"></div>
    </section>
  </div>

  <!-- TAB 3: LOGS -->
  <div id="tab-logs" class="tab-panel">
    <section class="panel-section">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px">
        <h2 style="margin:0">Recent logs</h2>
        <button id="refresh-logs-btn" class="btn btn-sm" type="button">Refresh logs</button>
      </div>
      <div class="hint" style="margin-bottom:8px">In-memory application logs from the arm controller process</div>
      <pre id="logs">Loading…</pre>
    </section>
  </div>
</main>

<script>
const $ = id => document.getElementById(id);

let jointInfo = [];
let blocks = [];
let undoStack = [];
let redoStack = [];
let dirty = false;
let editableConfig = true;
let controlReady = false;
let activeCategory = 'motion';
let draggedBlockIndex = null;
let draggedPaletteKind = null;
let suppressDrag = false;
let currentStatus = null;

// Step-by-step execution state
let nextStepIndex = 0;
let completedSteps = new Set();
let runningBlockIndex = null;
let isExecuting = false;
let stopRequested = false;
let activeWaitCancel = null;
let statusPollTimer = null;

// Guided tutorial state
let guideStep = 0;
let guideVisible = true;
const tutorialProgress = {
  movedArm: false,
  addedMotion: false,
  editedOrCaptured: false,
  addedWaitAndSecond: false,
  executedStepOrRun: false,
  savedSequence: false,
};

const TUTORIAL_STEPS = [
  {
    title: '1. Meet your robot arm',
    desc: 'Watch the live 2D robot arm on the Stage. Try moving a servo in Live arm control or click Home all.',
    check: () => tutorialProgress.movedArm,
    helperLabel: 'Home all joints',
    helperAction: () => sendArmCommand('/api/arm/home', {}, 'Homing all joints…'),
  },
  {
    title: '2. Snap your first motion block',
    desc: 'Click or drag a blue Motion block (like Turn joint or Move pose) into the workspace under "When call connects".',
    check: () => tutorialProgress.addedMotion || blocks.some(b => b.type !== 'wait'),
    helperLabel: 'Add sample Turn block',
    helperAction: () => addPaletteBlock('move_joint'),
  },
  {
    title: '3. Tune angles or capture a live pose',
    desc: 'Change an angle pill inside a block, or pose the arm in Live arm control and click "Capture pose".',
    check: () => tutorialProgress.editedOrCaptured,
    helperLabel: 'Capture live pose',
    helperAction: () => captureLivePose(),
  },
  {
    title: '4. Add a Wait block & a second step',
    desc: 'Switch to the orange Control category to snap a Wait block, then add a second motion block after it.',
    check: () => tutorialProgress.addedWaitAndSecond || (blocks.some(b => b.type === 'wait') && blocks.length >= 2),
    helperLabel: 'Add Wait + Motion',
    helperAction: () => {
      pushUndo();
      blocks.push(createBlock('wait'));
      blocks.push(createBlock('move_joint'));
      markDirty();
      renderBlocks();
      evaluateTutorial();
    },
  },
  {
    title: '5. Run step-by-step on the Stage',
    desc: 'Click "Step" (⏭) on the Stage to execute one block at a time with yellow highlighting, or "Run" (🚩) to play all steps.',
    check: () => tutorialProgress.executedStepOrRun,
    helperLabel: 'Step next block',
    helperAction: () => stepNextBlock(),
  },
  {
    title: '6. Save as Call Action',
    desc: 'Click "Save call action" to write your blocks into config.toml so they run automatically when a SIP call connects.',
    check: () => tutorialProgress.savedSequence,
    helperLabel: 'Save call action',
    helperAction: () => $('save-sequence').click(),
  },
];

async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

function defaultJoint() {
  return jointInfo[0] || { name: 'base', channel: 0, min_angle: 0, max_angle: 180, home_angle: 90 };
}

function getJoint(name) {
  return jointInfo.find(j => j.name === name) || defaultJoint();
}

function snapshotBlocks(list) {
  return JSON.parse(JSON.stringify(list));
}

function pushUndo() {
  undoStack.push(snapshotBlocks(blocks));
  if (undoStack.length > 50) undoStack.shift();
  redoStack = [];
  updateUndoButtons();
}

function updateUndoButtons() {
  $('btn-undo').disabled = undoStack.length === 0 || isExecuting;
  $('btn-redo').disabled = redoStack.length === 0 || isExecuting;
  $('btn-clear').disabled = blocks.length === 0 || isExecuting;
}

function markDirty(isDirty = true) {
  dirty = isDirty;
  $('dirty-dot').classList.toggle('visible', dirty);
}

function createBlock(kind, data) {
  const dj = defaultJoint();
  if (kind === 'move_joint') {
    const j = data?.joint ? getJoint(data.joint) : dj;
    const angle = Number.isFinite(data?.angle) ? data.angle : j.home_angle;
    return { type: 'move_joint', joint: j.name, angle: clamp(Math.round(angle), j.min_angle, j.max_angle) };
  }
  if (kind === 'nudge_joint') {
    const j = data?.joint ? getJoint(data.joint) : dj;
    const delta = Number.isFinite(data?.delta) ? data.delta : 15;
    return { type: 'nudge_joint', joint: j.name, delta };
  }
  if (kind === 'move_pose') {
    const angles = {};
    const enabled = {};
    for (const j of jointInfo) {
      const has = data?.angles && Object.prototype.hasOwnProperty.call(data.angles, j.name);
      enabled[j.name] = data?.angles ? has : true;
      angles[j.name] = has ? clamp(data.angles[j.name], j.min_angle, j.max_angle) : j.home_angle;
    }
    return { type: 'move_pose', angles, enabled };
  }
  if (kind === 'home') {
    return { type: 'home' };
  }
  if (kind === 'wait') {
    const seconds = Number.isFinite(data?.seconds) ? data.seconds : 0.5;
    return { type: 'wait', seconds: clamp(seconds, 0, 60) };
  }
  return { type: 'home' };
}

function posesToBlocks(poses) {
  const result = [];
  for (const pose of poses || []) {
    const entries = Object.entries(pose.angles || {});
    if (entries.length === 1) {
      const [joint, angle] = entries[0];
      result.push(createBlock('move_joint', { joint, angle }));
    } else if (entries.length > 1) {
      const isFullHome = jointInfo.length > 0 && entries.length === jointInfo.length &&
        jointInfo.every(j => Math.abs((pose.angles[j.name] ?? NaN) - j.home_angle) < 1e-6);
      if (isFullHome) {
        result.push(createBlock('home'));
      } else {
        result.push(createBlock('move_pose', { angles: pose.angles }));
      }
    }
    if ((pose.hold_s || 0) > 0) {
      result.push(createBlock('wait', { seconds: Number(pose.hold_s) }));
    }
  }
  return result;
}

function blocksToPoses() {
  const virtualAngles = Object.fromEntries(jointInfo.map(j => [j.name, j.home_angle]));
  const poses = [];
  for (const blk of blocks) {
    if (blk.type === 'move_joint') {
      const j = getJoint(blk.joint);
      const angle = clamp(Number(blk.angle) || 0, j.min_angle, j.max_angle);
      virtualAngles[j.name] = angle;
      poses.push({ angles: { [j.name]: angle }, hold_s: 0 });
    } else if (blk.type === 'nudge_joint') {
      const j = getJoint(blk.joint);
      const base = virtualAngles[j.name] ?? j.home_angle;
      const next = clamp(base + (Number(blk.delta) || 0), j.min_angle, j.max_angle);
      virtualAngles[j.name] = next;
      poses.push({ angles: { [j.name]: next }, hold_s: 0 });
    } else if (blk.type === 'move_pose') {
      const angles = {};
      for (const j of jointInfo) {
        if (blk.enabled?.[j.name]) {
          const val = clamp(Number(blk.angles?.[j.name] ?? j.home_angle), j.min_angle, j.max_angle);
          angles[j.name] = val;
          virtualAngles[j.name] = val;
        }
      }
      if (Object.keys(angles).length > 0) {
        poses.push({ angles, hold_s: 0 });
      }
    } else if (blk.type === 'home') {
      const angles = {};
      for (const j of jointInfo) {
        angles[j.name] = j.home_angle;
        virtualAngles[j.name] = j.home_angle;
      }
      if (Object.keys(angles).length > 0) {
        poses.push({ angles, hold_s: 0 });
      }
    } else if (blk.type === 'wait') {
      const sec = clamp(Number(blk.seconds) || 0, 0, 60);
      if (sec > 0) {
        if (poses.length > 0 && poses[poses.length - 1].hold_s === 0) {
          poses[poses.length - 1].hold_s = sec;
        } else {
          poses.push({ angles: {}, hold_s: sec });
        }
      }
    }
  }
  return poses;
}

function buildPresetBlocks(presetId) {
  const byName = Object.fromEntries(jointInfo.map(j => [j.name, j]));
  const base = byName.base || defaultJoint();
  const shoulder = byName.shoulder || base;
  const elbow = byName.elbow || shoulder;
  const gripper = byName.gripper || elbow;
  const safeOffset = (j, delta) => clamp(Math.round(j.home_angle + delta), j.min_angle, j.max_angle);

  if (presetId === 'wave') {
    return [
      createBlock('move_pose', {
        angles: {
          [shoulder.name]: safeOffset(shoulder, 25),
          [elbow.name]: safeOffset(elbow, -25),
        },
      }),
      createBlock('move_joint', { joint: base.name, angle: safeOffset(base, -25) }),
      createBlock('wait', { seconds: 0.3 }),
      createBlock('move_joint', { joint: base.name, angle: safeOffset(base, 25) }),
      createBlock('wait', { seconds: 0.3 }),
      createBlock('move_joint', { joint: base.name, angle: safeOffset(base, -20) }),
      createBlock('home'),
    ];
  }
  if (presetId === 'sweep') {
    return [
      createBlock('move_joint', { joint: base.name, angle: safeOffset(base, -40) }),
      createBlock('wait', { seconds: 0.4 }),
      createBlock('move_joint', { joint: base.name, angle: safeOffset(base, 40) }),
      createBlock('wait', { seconds: 0.4 }),
      createBlock('home'),
    ];
  }
  if (presetId === 'reach') {
    return [
      createBlock('move_pose', {
        angles: {
          [shoulder.name]: safeOffset(shoulder, -20),
          [elbow.name]: safeOffset(elbow, 20),
          [gripper.name]: safeOffset(gripper, 25),
        },
      }),
      createBlock('wait', { seconds: 0.4 }),
      createBlock('move_joint', { joint: gripper.name, angle: safeOffset(gripper, -25) }),
      createBlock('wait', { seconds: 0.5 }),
      createBlock('home'),
    ];
  }
  return [];
}

function captureLivePose(insertAt = null) {
  if (!jointInfo.length) return;
  const angles = Object.fromEntries(jointInfo.map(j => [j.name, Math.round(j.current_angle ?? j.home_angle)]));
  pushUndo();
  const blk = createBlock('move_pose', { angles });
  if (insertAt === null || insertAt < 0 || insertAt > blocks.length) {
    blocks.push(blk);
  } else {
    blocks.splice(insertAt, 0, blk);
  }
  tutorialProgress.addedMotion = true;
  tutorialProgress.editedOrCaptured = true;
  markDirty();
  resetStepCursor();
  renderBlocks();
  evaluateTutorial();
  setSequenceMessage('Captured live joint angles as a Move pose block.');
}

function addPaletteBlock(kind, insertAt = null) {
  if (kind === 'hat_focus') {
    const hat = $('hat-block');
    hat.classList.add('pulse');
    setTimeout(() => hat.classList.remove('pulse'), 900);
    return;
  }
  if (kind === 'capture_live') {
    captureLivePose(insertAt);
    return;
  }
  if (kind.startsWith('preset:')) {
    const presetName = kind.slice(7);
    const items = buildPresetBlocks(presetName);
    if (!items.length) return;
    pushUndo();
    if (insertAt === null || insertAt < 0 || insertAt > blocks.length) {
      blocks.push(...items);
    } else {
      blocks.splice(insertAt, 0, ...items);
    }
    tutorialProgress.addedMotion = true;
    markDirty();
    resetStepCursor();
    renderBlocks();
    evaluateTutorial();
    setSequenceMessage(`Added "${presetName}" blocks (${items.length} steps).`);
    return;
  }

  pushUndo();
  const blk = createBlock(kind);
  if (insertAt === null || insertAt < 0 || insertAt > blocks.length) {
    blocks.push(blk);
  } else {
    blocks.splice(insertAt, 0, blk);
  }
  if (blk.type === 'wait') {
    if (blocks.length >= 2) tutorialProgress.addedWaitAndSecond = true;
  } else {
    tutorialProgress.addedMotion = true;
  }
  markDirty();
  resetStepCursor();
  renderBlocks();
  evaluateTutorial();
}

function renderPalette() {
  const drawer = $('palette-drawer');
  drawer.replaceChildren();

  const itemsByCategory = {
    events: [
      { kind: 'hat_focus', cls: 'cat-events', label: 'When 📞 call connects', sub: 'Hat block at top of workspace', draggable: false },
    ],
    motion: [
      { kind: 'move_joint', cls: 'cat-motion', label: 'Turn [joint] to (angle)°', sub: 'Move one servo smoothly' },
      { kind: 'nudge_joint', cls: 'cat-motion', label: 'Nudge [joint] by (+15)°', sub: 'Relative step turn' },
      { kind: 'move_pose', cls: 'cat-motion', label: 'Move pose (multi-joint)', sub: 'Move selected servos together' },
      { kind: 'home', cls: 'cat-motion', label: 'Return all joints to home', sub: 'Center every joint cleanly' },
    ],
    control: [
      { kind: 'wait', cls: 'cat-control', label: 'Wait (0.5) seconds', sub: 'Hold position before next block' },
    ],
    presets: [
      { kind: 'capture_live', cls: 'cat-presets', label: 'Capture live pose', sub: 'Snapshot Stage angles into a block' },
      { kind: 'preset:wave', cls: 'cat-presets', label: 'Preset: Wave hello', sub: 'Friendly multi-step wave' },
      { kind: 'preset:sweep', cls: 'cat-presets', label: 'Preset: Sweep base', sub: 'Left-right scan + home' },
      { kind: 'preset:reach', cls: 'cat-presets', label: 'Preset: Reach & grip', sub: 'Extend arm, close gripper, home' },
    ],
  };

  const titles = {
    events: 'Events',
    motion: 'Motion',
    control: 'Control',
    presets: 'Presets & Live Capture',
  };

  const heading = document.createElement('div');
  heading.className = 'palette-group-title';
  heading.textContent = titles[activeCategory];
  drawer.append(heading);

  for (const item of itemsByCategory[activeCategory]) {
    const el = document.createElement('div');
    el.className = `palette-item ${item.cls}`;
    el.tabIndex = 0;
    const isDraggable = item.draggable !== false;
    el.draggable = isDraggable;

    const title = document.createElement('span');
    title.textContent = item.label;
    const sub = document.createElement('small');
    sub.textContent = item.sub;
    el.append(title, sub);

    if (isDraggable) {
      el.addEventListener('dragstart', e => {
        draggedPaletteKind = item.kind;
        draggedBlockIndex = null;
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = 'copy';
          e.dataTransfer.setData('text/plain', item.kind);
        }
      });
      el.addEventListener('dragend', () => {
        draggedPaletteKind = null;
        clearSlotHighlights();
      });
    }
    el.addEventListener('click', () => addPaletteBlock(item.kind));
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        addPaletteBlock(item.kind);
      }
    });
    drawer.append(el);
  }
}

function clearSlotHighlights() {
  document.querySelectorAll('.drop-slot.active').forEach(el => el.classList.remove('active'));
  const empty = document.querySelector('.empty-dropzone.drag-over');
  if (empty) empty.classList.remove('drag-over');
}

function makeDropSlot(insertIndex) {
  const slot = document.createElement('div');
  slot.className = 'drop-slot';
  slot.addEventListener('dragover', e => {
    if (draggedBlockIndex === null && draggedPaletteKind === null) return;
    e.preventDefault();
    slot.classList.add('active');
  });
  slot.addEventListener('dragleave', () => slot.classList.remove('active'));
  slot.addEventListener('drop', e => {
    e.preventDefault();
    slot.classList.remove('active');
    handleDropAt(insertIndex);
  });
  return slot;
}

function handleDropAt(insertIndex) {
  if (isExecuting) return;
  if (draggedPaletteKind !== null) {
    const kind = draggedPaletteKind;
    draggedPaletteKind = null;
    addPaletteBlock(kind, insertIndex);
    return;
  }
  if (draggedBlockIndex !== null) {
    const from = draggedBlockIndex;
    draggedBlockIndex = null;
    if (from === insertIndex || from + 1 === insertIndex) return;
    pushUndo();
    const [moved] = blocks.splice(from, 1);
    const target = from < insertIndex ? insertIndex - 1 : insertIndex;
    blocks.splice(target, 0, moved);
    markDirty();
    resetStepCursor();
    renderBlocks();
  }
}

function updateWorkspaceSummary() {
  const waitSum = blocks
    .filter(b => b.type === 'wait')
    .reduce((acc, b) => acc + (Number(b.seconds) || 0), 0);
  $('workspace-summary').textContent = `${blocks.length} block${blocks.length === 1 ? '' : 's'} · ${waitSum.toFixed(1)}s wait`;
}

function setSequenceMessage(msg, isError = false) {
  const el = $('sequence-message');
  el.textContent = msg;
  el.classList.toggle('error', isError);
}

function renderBlocks() {
  const root = $('pose-blocks');
  root.replaceChildren();
  updateWorkspaceSummary();
  updateUndoButtons();

  if (!blocks.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-dropzone';
    empty.textContent = 'No blocks snapped yet — click a Motion block on the left or drag one here!';
    empty.addEventListener('dragover', e => {
      if (draggedPaletteKind === null && draggedBlockIndex === null) return;
      e.preventDefault();
      empty.classList.add('drag-over');
    });
    empty.addEventListener('dragleave', () => empty.classList.remove('drag-over'));
    empty.addEventListener('drop', e => {
      e.preventDefault();
      empty.classList.remove('drag-over');
      handleDropAt(0);
    });
    root.append(empty);
    return;
  }

  root.append(makeDropSlot(0));

  blocks.forEach((blk, index) => {
    const card = document.createElement('div');
    card.className = `scratch-block type-${blk.type}`;
    if (runningBlockIndex === index) card.classList.add('is-running');
    if (!isExecuting && nextStepIndex === index && blocks.length > 0 && (completedSteps.size > 0 || nextStepIndex > 0)) {
      card.classList.add('is-next');
    }
    card.draggable = !isExecuting;

    card.addEventListener('pointerdown', e => {
      if (e.target && e.target.closest('input,select,button,label')) {
        suppressDrag = true;
        card.draggable = false;
      }
    });
    card.addEventListener('dragstart', e => {
      if (suppressDrag || isExecuting) {
        e.preventDefault();
        return;
      }
      draggedBlockIndex = index;
      draggedPaletteKind = null;
      card.classList.add('dragging');
      if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', String(index));
      }
    });
    card.addEventListener('dragend', () => {
      draggedBlockIndex = null;
      card.classList.remove('dragging');
      clearSlotHighlights();
    });
    card.addEventListener('dragover', e => {
      if (draggedBlockIndex === null && draggedPaletteKind === null) return;
      e.preventDefault();
    });
    card.addEventListener('drop', e => {
      e.preventDefault();
      const rect = card.getBoundingClientRect();
      const insertAfter = (e.clientY - rect.top) > rect.height / 2;
      handleDropAt(insertAfter ? index + 1 : index);
    });

    const row = document.createElement('div');
    row.className = 'block-row';

    const main = document.createElement('div');
    main.className = 'block-main';

    const badge = document.createElement('span');
    badge.className = 'step-badge' + (completedSteps.has(index) ? ' done' : '');
    badge.textContent = completedSteps.has(index) ? '✓' : String(index + 1);
    main.append(badge);

    if (!isExecuting && nextStepIndex === index && (completedSteps.size > 0 || nextStepIndex > 0)) {
      const nextPill = document.createElement('span');
      nextPill.className = 'next-tag';
      nextPill.textContent = 'next';
      main.append(nextPill);
    }

    if (blk.type === 'move_joint') {
      const t1 = document.createElement('span');
      t1.textContent = 'Turn';
      const sel = document.createElement('select');
      sel.className = 'pill-select';
      sel.setAttribute('aria-label', 'Servo joint');
      for (const j of jointInfo) {
        const opt = document.createElement('option');
        opt.value = j.name;
        opt.textContent = j.name;
        sel.append(opt);
      }
      sel.value = blk.joint;

      const t2 = document.createElement('span');
      t2.textContent = 'to';

      const jObj = getJoint(blk.joint);
      const range = document.createElement('input');
      range.type = 'range';
      range.className = 'block-range';
      range.min = jObj.min_angle;
      range.max = jObj.max_angle;
      range.step = '1';
      range.value = blk.angle;

      const num = document.createElement('input');
      num.type = 'number';
      num.className = 'pill-input';
      num.min = jObj.min_angle;
      num.max = jObj.max_angle;
      num.step = '1';
      num.value = blk.angle;
      num.setAttribute('aria-label', 'Angle in degrees');

      const unit = document.createElement('span');
      unit.textContent = '°';

      sel.addEventListener('change', () => {
        pushUndo();
        blk.joint = sel.value;
        const nj = getJoint(blk.joint);
        blk.angle = clamp(blk.angle, nj.min_angle, nj.max_angle);
        tutorialProgress.editedOrCaptured = true;
        markDirty();
        renderBlocks();
        evaluateTutorial();
      });
      range.addEventListener('input', () => {
        blk.angle = Number(range.value);
        num.value = range.value;
        tutorialProgress.editedOrCaptured = true;
        markDirty();
        evaluateTutorial();
      });
      num.addEventListener('input', () => {
        const v = Number(num.value);
        if (num.value !== '' && Number.isFinite(v)) {
          const nj = getJoint(blk.joint);
          const clamped = clamp(v, nj.min_angle, nj.max_angle);
          blk.angle = clamped;
          range.value = String(clamped);
          tutorialProgress.editedOrCaptured = true;
          markDirty();
          evaluateTutorial();
        }
      });

      main.append(t1, sel, t2, range, num, unit);
    } else if (blk.type === 'nudge_joint') {
      const t1 = document.createElement('span');
      t1.textContent = 'Nudge';
      const sel = document.createElement('select');
      sel.className = 'pill-select';
      for (const j of jointInfo) {
        const opt = document.createElement('option');
        opt.value = j.name;
        opt.textContent = j.name;
        sel.append(opt);
      }
      sel.value = blk.joint;

      const t2 = document.createElement('span');
      t2.textContent = 'by';
      const num = document.createElement('input');
      num.type = 'number';
      num.className = 'pill-input';
      num.min = '-180';
      num.max = '180';
      num.step = '5';
      num.value = blk.delta;
      const unit = document.createElement('span');
      unit.textContent = '°';

      sel.addEventListener('change', () => {
        pushUndo();
        blk.joint = sel.value;
        tutorialProgress.editedOrCaptured = true;
        markDirty();
        evaluateTutorial();
      });
      num.addEventListener('input', () => {
        const v = Number(num.value);
        if (num.value !== '' && Number.isFinite(v)) {
          blk.delta = clamp(v, -180, 180);
          tutorialProgress.editedOrCaptured = true;
          markDirty();
          evaluateTutorial();
        }
      });
      main.append(t1, sel, t2, num, unit);
    } else if (blk.type === 'move_pose') {
      const label = document.createElement('span');
      label.textContent = 'Move pose';
      const useLive = document.createElement('button');
      useLive.type = 'button';
      useLive.className = 'blk-btn';
      useLive.textContent = 'Use live';
      useLive.title = 'Fill checked joints from current Stage angles';
      useLive.addEventListener('click', () => {
        pushUndo();
        for (const j of jointInfo) {
          blk.angles[j.name] = Math.round(j.current_angle ?? j.home_angle);
          blk.enabled[j.name] = true;
        }
        tutorialProgress.editedOrCaptured = true;
        markDirty();
        renderBlocks();
        evaluateTutorial();
      });
      main.append(label, useLive);
    } else if (blk.type === 'home') {
      const label = document.createElement('span');
      label.textContent = 'Return all joints to home';
      main.append(label);
    } else if (blk.type === 'wait') {
      const t1 = document.createElement('span');
      t1.textContent = 'Wait';
      const num = document.createElement('input');
      num.type = 'number';
      num.className = 'pill-input';
      num.min = '0';
      num.max = '60';
      num.step = '0.1';
      num.value = blk.seconds;
      const t2 = document.createElement('span');
      t2.textContent = 'seconds';
      num.addEventListener('input', () => {
        const v = Number(num.value);
        if (num.value !== '' && Number.isFinite(v)) {
          blk.seconds = clamp(v, 0, 60);
          tutorialProgress.editedOrCaptured = true;
          markDirty();
          updateWorkspaceSummary();
          evaluateTutorial();
        }
      });
      main.append(t1, num, t2);
    }

    const actions = document.createElement('div');
    actions.className = 'block-actions';

    const playBtn = document.createElement('button');
    playBtn.type = 'button';
    playBtn.className = 'blk-btn';
    playBtn.textContent = '▶';
    playBtn.title = 'Run this block now';
    playBtn.disabled = isExecuting;
    playBtn.addEventListener('click', () => runSingleBlock(index));

    const upBtn = document.createElement('button');
    upBtn.type = 'button';
    upBtn.className = 'blk-btn';
    upBtn.textContent = '↑';
    upBtn.title = 'Move block up';
    upBtn.disabled = isExecuting || index === 0;
    upBtn.addEventListener('click', () => {
      pushUndo();
      [blocks[index], blocks[index - 1]] = [blocks[index - 1], blocks[index]];
      markDirty();
      resetStepCursor();
      renderBlocks();
    });

    const downBtn = document.createElement('button');
    downBtn.type = 'button';
    downBtn.className = 'blk-btn';
    downBtn.textContent = '↓';
    downBtn.title = 'Move block down';
    downBtn.disabled = isExecuting || index === blocks.length - 1;
    downBtn.addEventListener('click', () => {
      pushUndo();
      [blocks[index], blocks[index + 1]] = [blocks[index + 1], blocks[index]];
      markDirty();
      resetStepCursor();
      renderBlocks();
    });

    const dupBtn = document.createElement('button');
    dupBtn.type = 'button';
    dupBtn.className = 'blk-btn';
    dupBtn.textContent = '⧉';
    dupBtn.title = 'Duplicate block';
    dupBtn.disabled = isExecuting;
    dupBtn.addEventListener('click', () => {
      pushUndo();
      blocks.splice(index + 1, 0, snapshotBlocks(blk));
      markDirty();
      resetStepCursor();
      renderBlocks();
      evaluateTutorial();
    });

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'blk-btn';
    delBtn.textContent = '✕';
    delBtn.title = 'Remove block';
    delBtn.disabled = isExecuting;
    delBtn.addEventListener('click', () => {
      pushUndo();
      blocks.splice(index, 1);
      markDirty();
      resetStepCursor();
      renderBlocks();
      evaluateTutorial();
    });

    actions.append(playBtn, upBtn, downBtn, dupBtn, delBtn);
    row.append(main, actions);
    card.append(row);

    if (blk.type === 'move_pose') {
      const matrix = document.createElement('div');
      matrix.className = 'pose-joints-box';
      for (const j of jointInfo) {
        const jRow = document.createElement('label');
        jRow.className = 'pose-joint-row' + (blk.enabled[j.name] ? '' : ' unchecked');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = !!blk.enabled[j.name];

        const nameSpan = document.createElement('span');
        nameSpan.textContent = `${j.name} (ch ${j.channel})`;

        const slider = document.createElement('input');
        slider.type = 'range';
        slider.min = j.min_angle;
        slider.max = j.max_angle;
        slider.step = '1';
        slider.value = blk.angles[j.name] ?? j.home_angle;
        slider.disabled = !cb.checked;

        const num = document.createElement('input');
        num.type = 'number';
        num.min = j.min_angle;
        num.max = j.max_angle;
        num.step = '1';
        num.value = slider.value;
        num.disabled = !cb.checked;

        cb.addEventListener('change', () => {
          pushUndo();
          blk.enabled[j.name] = cb.checked;
          slider.disabled = !cb.checked;
          num.disabled = !cb.checked;
          jRow.classList.toggle('unchecked', !cb.checked);
          tutorialProgress.editedOrCaptured = true;
          markDirty();
        });
        slider.addEventListener('input', () => {
          blk.angles[j.name] = Number(slider.value);
          num.value = slider.value;
          tutorialProgress.editedOrCaptured = true;
          markDirty();
          evaluateTutorial();
        });
        num.addEventListener('input', () => {
          const v = Number(num.value);
          if (num.value !== '' && Number.isFinite(v)) {
            const clamped = clamp(v, j.min_angle, j.max_angle);
            blk.angles[j.name] = clamped;
            slider.value = String(clamped);
            tutorialProgress.editedOrCaptured = true;
            markDirty();
            evaluateTutorial();
          }
        });

        jRow.append(cb, nameSpan, slider, num);
        matrix.append(jRow);
      }
      card.append(matrix);
    }

    root.append(card);
    root.append(makeDropSlot(index + 1));
  });
}

/* Execution engine */
function setExecutingState(active) {
  isExecuting = active;
  $('btn-run').disabled = active;
  $('btn-step').disabled = active;
  $('hat-run').disabled = active;
  $('save-sequence').disabled = active || !editableConfig;
  setPollInterval(active ? 250 : 2000);
  renderBlocks();
}

function resetStepCursor() {
  nextStepIndex = 0;
  completedSteps.clear();
  runningBlockIndex = null;
  if (!isExecuting) {
    $('stage-status').textContent = blocks.length
      ? 'Ready — click Run or Step to test your blocks.'
      : 'Add blocks to the workspace, then run or step through them.';
    $('svg-stage-badge').textContent = 'IDLE';
  }
}

function abortableWait(seconds) {
  return new Promise(resolve => {
    const start = performance.now();
    const totalMs = Math.max(0, seconds * 1000);
    if (totalMs <= 0) {
      resolve(true);
      return;
    }
    let timer = null;
    const cancel = () => {
      if (timer !== null) clearInterval(timer);
      activeWaitCancel = null;
      resolve(false);
    };
    activeWaitCancel = cancel;
    timer = setInterval(() => {
      if (stopRequested) {
        cancel();
        return;
      }
      const elapsed = performance.now() - start;
      const remaining = Math.max(0, (totalMs - elapsed) / 1000);
      $('stage-status').textContent = `Waiting… ${remaining.toFixed(1)}s left`;
      if (elapsed >= totalMs) {
        clearInterval(timer);
        activeWaitCancel = null;
        resolve(true);
      }
    }, 100);
  });
}

async function executeBlockAt(index) {
  const blk = blocks[index];
  if (!blk) return;
  runningBlockIndex = index;
  renderBlocks();

  if (blk.type === 'move_joint') {
    $('stage-status').textContent = `Step ${index + 1}/${blocks.length}: Turning ${blk.joint} to ${blk.angle}°…`;
    $('svg-stage-badge').textContent = `STEP ${index + 1}`;
    await request('/api/arm/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ joint: blk.joint, angle: Number(blk.angle) }),
    });
  } else if (blk.type === 'nudge_joint') {
    const j = getJoint(blk.joint);
    const cur = Number.isFinite(j.current_angle) ? j.current_angle : j.home_angle;
    const target = clamp(cur + Number(blk.delta), j.min_angle, j.max_angle);
    $('stage-status').textContent = `Step ${index + 1}/${blocks.length}: Nudging ${blk.joint} to ${target.toFixed(0)}°…`;
    $('svg-stage-badge').textContent = `STEP ${index + 1}`;
    await request('/api/arm/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ joint: blk.joint, angle: target }),
    });
  } else if (blk.type === 'move_pose') {
    const angles = {};
    for (const j of jointInfo) {
      if (blk.enabled?.[j.name]) {
        angles[j.name] = clamp(Number(blk.angles?.[j.name] ?? j.home_angle), j.min_angle, j.max_angle);
      }
    }
    if (!Object.keys(angles).length) {
      throw new Error(`Pose block #${index + 1} has no joints checked.`);
    }
    $('stage-status').textContent = `Step ${index + 1}/${blocks.length}: Moving pose (${Object.keys(angles).length} joints)…`;
    $('svg-stage-badge').textContent = `STEP ${index + 1}`;
    await request('/api/arm/pose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ angles }),
    });
  } else if (blk.type === 'home') {
    $('stage-status').textContent = `Step ${index + 1}/${blocks.length}: Returning all joints home…`;
    $('svg-stage-badge').textContent = 'HOMING';
    await request('/api/arm/home', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
  } else if (blk.type === 'wait') {
    $('svg-stage-badge').textContent = 'WAIT';
    const ok = await abortableWait(Number(blk.seconds) || 0);
    if (!ok) throw new Error('Stopped.');
  }

  completedSteps.add(index);
  await refresh();
}

async function runAllBlocks() {
  if (isExecuting) return;
  if (!blocks.length) {
    setSequenceMessage('Add at least one block before running.', true);
    return;
  }
  stopRequested = false;
  completedSteps.clear();
  nextStepIndex = 0;
  setExecutingState(true);
  tutorialProgress.executedStepOrRun = true;
  evaluateTutorial();

  try {
    for (let i = 0; i < blocks.length; i++) {
      if (stopRequested) break;
      await executeBlockAt(i);
      nextStepIndex = i + 1;
    }
    if (!stopRequested && $('run-return-home').checked) {
      $('stage-status').textContent = 'Returning all joints home…';
      $('svg-stage-badge').textContent = 'HOMING';
      await request('/api/arm/home', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      await refresh();
    }
    if (!stopRequested) {
      $('stage-status').textContent = `Finished all ${blocks.length} step(s)!`;
      $('svg-stage-badge').textContent = 'DONE';
      nextStepIndex = 0;
    }
  } catch (e) {
    $('stage-status').textContent = e.message;
    $('svg-stage-badge').textContent = 'IDLE';
  } finally {
    runningBlockIndex = null;
    setExecutingState(false);
  }
}

async function stepNextBlock() {
  if (isExecuting) return;
  if (!blocks.length) {
    setSequenceMessage('Add at least one block before stepping.', true);
    return;
  }
  if (nextStepIndex >= blocks.length) {
    completedSteps.clear();
    nextStepIndex = 0;
  }
  stopRequested = false;
  setExecutingState(true);
  tutorialProgress.executedStepOrRun = true;
  evaluateTutorial();

  try {
    const idx = nextStepIndex;
    await executeBlockAt(idx);
    nextStepIndex = idx + 1;
    if (nextStepIndex >= blocks.length) {
      $('stage-status').textContent = `Completed step ${idx + 1}/${blocks.length} (end of stack — click Step to restart).`;
      $('svg-stage-badge').textContent = 'DONE';
    } else {
      $('stage-status').textContent = `Completed step ${idx + 1}/${blocks.length}. Next: step ${nextStepIndex + 1}.`;
      $('svg-stage-badge').textContent = 'PAUSED';
    }
  } catch (e) {
    $('stage-status').textContent = e.message;
    $('svg-stage-badge').textContent = 'IDLE';
  } finally {
    runningBlockIndex = null;
    setExecutingState(false);
  }
}

async function runSingleBlock(index) {
  if (isExecuting) return;
  stopRequested = false;
  setExecutingState(true);
  tutorialProgress.executedStepOrRun = true;
  evaluateTutorial();
  try {
    await executeBlockAt(index);
    $('stage-status').textContent = `Ran block #${index + 1}.`;
    $('svg-stage-badge').textContent = 'IDLE';
  } catch (e) {
    $('stage-status').textContent = e.message;
    $('svg-stage-badge').textContent = 'IDLE';
  } finally {
    runningBlockIndex = null;
    setExecutingState(false);
  }
}

async function stopAllExecution() {
  stopRequested = true;
  if (activeWaitCancel) activeWaitCancel();
  try {
    const res = await request('/api/arm/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    $('stage-status').textContent = res.message;
    $('svg-stage-badge').textContent = 'STOPPED';
    await refresh();
  } catch (e) {
    $('stage-status').textContent = e.message;
  }
}

/* 2D SVG Arm Stage Rendering */
function updateArmVisualizer(joints) {
  const byName = Object.fromEntries(joints.map(j => [j.name, j]));
  const base = byName.base || joints[0];
  const shoulder = byName.shoulder || joints[1] || base;
  const elbow = byName.elbow || joints[2] || shoulder;
  const gripper = byName.gripper || joints[3] || elbow;

  if (base) {
    const needleAngle = (base.current_angle - 90) * 0.9;
    $('svg-base-needle').setAttribute('transform', `rotate(${needleAngle.toFixed(1)})`);
    $('svg-base-label').textContent = `${base.current_angle.toFixed(0)}°`;
  }

  const sx = 170, sy = 148;
  const upperLen = 62, foreLen = 58;
  const shoulderVal = shoulder ? shoulder.current_angle : 90;
  const elbowVal = elbow ? elbow.current_angle : 90;

  const shoulderRad = (-90 + (shoulderVal - 90) * 0.75) * Math.PI / 180;
  const ex = sx + upperLen * Math.cos(shoulderRad);
  const ey = sy + upperLen * Math.sin(shoulderRad);

  const foreRad = shoulderRad + (90 + (elbowVal - 90) * 0.8) * Math.PI / 180;
  const wx = ex + foreLen * Math.cos(foreRad);
  const wy = ey + foreLen * Math.sin(foreRad);

  $('svg-link-upper').setAttribute('x1', sx.toFixed(1));
  $('svg-link-upper').setAttribute('y1', sy.toFixed(1));
  $('svg-link-upper').setAttribute('x2', ex.toFixed(1));
  $('svg-link-upper').setAttribute('y2', ey.toFixed(1));

  $('svg-link-fore').setAttribute('x1', ex.toFixed(1));
  $('svg-link-fore').setAttribute('y1', ey.toFixed(1));
  $('svg-link-fore').setAttribute('x2', wx.toFixed(1));
  $('svg-link-fore').setAttribute('y2', wy.toFixed(1));

  $('svg-joint-elbow').setAttribute('cx', ex.toFixed(1));
  $('svg-joint-elbow').setAttribute('cy', ey.toFixed(1));

  const foreDeg = foreRad * 180 / Math.PI;
  $('svg-gripper').setAttribute('transform', `translate(${wx.toFixed(1)},${wy.toFixed(1)}) rotate(${foreDeg.toFixed(1)})`);

  if (gripper) {
    const span = Math.max(1, gripper.max_angle - gripper.min_angle);
    const openRatio = clamp((gripper.current_angle - gripper.min_angle) / span, 0, 1);
    const spread = 2 + openRatio * 10;
    $('svg-jaw-top').setAttribute('d', `M 6 -3 L 20 -${spread.toFixed(1)} L 24 -${(spread * 0.55).toFixed(1)}`);
    $('svg-jaw-bot').setAttribute('d', `M 6 3 L 20 ${spread.toFixed(1)} L 24 ${(spread * 0.55).toFixed(1)}`);
  }
}

function renderStageJointChips(joints) {
  const root = $('stage-joints');
  root.replaceChildren();
  for (const j of joints) {
    const chip = document.createElement('div');
    chip.className = 'joint-chip';

    const head = document.createElement('div');
    head.className = 'joint-chip-head';
    const name = document.createElement('span');
    name.textContent = j.name;
    const val = document.createElement('span');
    val.textContent = `${j.current_angle.toFixed(0)}°`;
    head.append(name, val);

    const bar = document.createElement('div');
    bar.className = 'joint-chip-bar';
    const fill = document.createElement('div');
    fill.className = 'joint-chip-fill';
    const span = Math.max(1, j.max_angle - j.min_angle);
    const pct = clamp(((j.current_angle - j.min_angle) / span) * 100, 0, 100);
    fill.style.width = `${pct.toFixed(1)}%`;
    bar.append(fill);

    const sub = document.createElement('div');
    sub.className = 'joint-chip-sub';
    sub.textContent = `ch ${j.channel} · ${j.min_angle}–${j.max_angle}°`;

    chip.append(head, bar, sub);
    root.append(chip);
  }
}

/* Guided Tutorial Rendering */
function evaluateTutorial() {
  renderTutorial();
}

function renderTutorial() {
  const step = TUTORIAL_STEPS[guideStep];
  const done = step.check();
  $('guide-counter').textContent = `Step ${guideStep + 1} of ${TUTORIAL_STEPS.length}`;
  $('guide-heading').textContent = step.title;
  $('guide-desc').textContent = step.desc;
  $('guide-done').classList.toggle('visible', done);
  $('guide-helper').textContent = step.helperLabel;
  $('guide-prev').disabled = guideStep === 0;
  $('guide-next').textContent = guideStep === TUTORIAL_STEPS.length - 1 ? 'Done' : 'Next';

  const dots = $('guide-dots');
  dots.replaceChildren();
  TUTORIAL_STEPS.forEach((s, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'guide-dot';
    if (i === guideStep) btn.classList.add('active');
    if (s.check()) btn.classList.add('completed');
    btn.textContent = s.check() && i !== guideStep ? '✓' : String(i + 1);
    btn.title = s.title;
    btn.addEventListener('click', () => {
      guideStep = i;
      renderTutorial();
    });
    dots.append(btn);
  });
}

/* Status, Live Controls, Config, and Logs */
function card(label, value) {
  const node = document.createElement('div');
  node.className = 'card';
  const l = document.createElement('div');
  l.className = 'label';
  l.textContent = label;
  const v = document.createElement('div');
  v.className = 'value';
  v.textContent = value;
  node.append(l, v);
  return node;
}

function formatUptime(seconds) {
  seconds = Math.floor(seconds);
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return days ? `${days}d ${hours}h ${minutes}m` : `${hours}h ${minutes}m`;
}

function renderStatus(s) {
  currentStatus = s;
  jointInfo = s.joints;

  // Top bar pills
  $('pill-service').textContent = s.arm.call_action_running ? 'Call action running' : 'Service Online';
  $('pill-service').className = 'status-pill ' + (s.arm.call_action_running ? 'warn' : 'ok');
  $('pill-calls').textContent = `Calls: ${s.active_calls} / ${s.max_concurrent_calls}`;
  $('pill-i2c').textContent = s.i2c.mock
    ? 'I²C: Mock'
    : `I²C-${s.i2c.bus}: ${s.i2c.device_available ? 'Ready' : 'Missing'}`;
  $('pill-uptime').textContent = formatUptime(s.uptime_seconds);

  // Stage visualizer
  updateArmVisualizer(s.joints);
  renderStageJointChips(s.joints);

  // Config & Stats tab
  $('stats').replaceChildren(
    card('Service', 'Running'),
    card('Uptime', formatUptime(s.uptime_seconds)),
    card('Active SIP calls', `${s.active_calls} / ${s.max_concurrent_calls}`),
    card('I²C', s.i2c.mock ? 'Mock bus' : `/dev/i2c-${s.i2c.bus} ${s.i2c.device_available ? 'available' : 'not found'}`),
  );
  $('configuration').textContent =
    `SIP ${s.sip.host}:${s.sip.port} · I²C address 0x${s.i2c.address.toString(16).padStart(2, '0')} · ` +
    `${s.arm.joint_count} joints · ${s.arm.call_sequence_poses} call poses · ` +
    `${s.arm.home_on_start ? 'home on start' : 'no homing on start'} · ${s.arm.speed_deg_per_sec}°/s`;

  const jointsDiv = $('joints');
  jointsDiv.replaceChildren();
  for (const j of s.joints) {
    const row = document.createElement('div');
    row.className = 'joint';
    for (const text of [
      `${j.name} (ch ${j.channel})`,
      `Current: ${j.current_angle.toFixed(1)}°`,
      `Target: ${j.target_angle.toFixed(1)}° · ${j.min_angle}–${j.max_angle}°`,
    ]) {
      const cell = document.createElement('span');
      cell.textContent = text;
      row.append(cell);
    }
    jointsDiv.append(row);
  }

  if (!controlReady) {
    const select = $('control-joint');
    select.replaceChildren();
    for (const j of jointInfo) {
      const option = document.createElement('option');
      option.value = j.name;
      option.textContent = `${j.name} (channel ${j.channel})`;
      select.append(option);
    }
    select.addEventListener('change', updateControlRange);
    $('control-angle').addEventListener('input', () => {
      $('control-angle-number').value = $('control-angle').value;
    });
    $('control-angle-number').addEventListener('input', () => {
      $('control-angle').value = $('control-angle-number').value;
    });
    $('move-joint').addEventListener('click', () =>
      sendArmCommand('/api/arm/move', { joint: select.value, angle: Number($('control-angle-number').value) }, 'Moving joint…')
    );
    $('home-arm').addEventListener('click', () => sendArmCommand('/api/arm/home', {}, 'Homing all joints…'));
    $('stop-arm').addEventListener('click', () => sendArmCommand('/api/arm/stop', {}, 'Stopping motion…'));
    $('release-arm').addEventListener('click', () => {
      if (confirm('Stop the arm and release all servos?')) {
        sendArmCommand('/api/arm/release', {}, 'Stopping and releasing servos…');
      }
    });
    controlReady = true;
    updateControlRange();
  }

  const selected = s.joints.find(j => j.name === $('control-joint').value);
  if (selected) {
    $('control-range').textContent = `${selected.current_angle.toFixed(1)}° · home ${selected.home_angle.toFixed(0)}°`;
  }
}

function updateControlRange() {
  const j = jointInfo.find(item => item.name === $('control-joint').value);
  if (!j) return;
  const slider = $('control-angle');
  slider.min = j.min_angle;
  slider.max = j.max_angle;
  slider.step = '1';
  slider.value = j.target_angle;
  const num = $('control-angle-number');
  num.min = j.min_angle;
  num.max = j.max_angle;
  num.step = '1';
  num.value = slider.value;
  $('control-range').textContent = `${j.min_angle}°–${j.max_angle}° · home ${j.home_angle}°`;
}

async function sendArmCommand(path, body, label) {
  const buttons = ['move-joint', 'home-arm', 'stop-arm', 'release-arm'].map(id => $(id));
  buttons.forEach(b => (b.disabled = true));
  $('control-message').textContent = label;
  try {
    const result = await request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    $('control-message').textContent = result.message;
    if (path === '/api/arm/move' || path === '/api/arm/home') {
      tutorialProgress.movedArm = true;
      evaluateTutorial();
    }
    await refresh();
  } catch (e) {
    $('control-message').textContent = e.message;
  } finally {
    buttons.forEach(b => (b.disabled = false));
  }
}

async function refresh() {
  try {
    renderStatus(await request('/api/status'));
  } catch (e) {
    $('pill-service').textContent = 'Offline';
    $('pill-service').className = 'status-pill warn';
    $('message').textContent = e.message;
  }
}

async function refreshLogs() {
  try {
    const data = await request('/api/logs?limit=150');
    $('logs').textContent =
      data.logs.map(l => `${l.time} ${l.level.padEnd(8)} [${l.logger}] ${l.message}`).join('\\n') || 'No logs yet.';
  } catch (e) {
    $('logs').textContent = e.message;
  }
}

async function loadConfig() {
  try {
    const data = await request('/api/config');
    $('config').value = data.content;
    $('config').readOnly = !data.editable;
    $('save').disabled = !data.editable;
    if (!data.editable) {
      $('message').textContent = data.message || 'No configuration file was supplied to the server.';
    }
  } catch (e) {
    $('message').textContent = e.message;
  }
}

async function loadSequence() {
  try {
    const data = await request('/api/action-sequence');
    jointInfo = data.joints;
    editableConfig = !!data.editable;
    blocks = posesToBlocks(data.poses);
    undoStack = [];
    redoStack = [];
    markDirty(false);
    resetStepCursor();
    $('save-sequence').disabled = !editableConfig;
    if (!editableConfig && data.message) {
      setSequenceMessage(data.message + ' You can still build and run blocks on the Stage!');
    }
    renderBlocks();
    evaluateTutorial();
  } catch (e) {
    setSequenceMessage(e.message, true);
  }
}

function setPollInterval(ms) {
  if (statusPollTimer !== null) clearInterval(statusPollTimer);
  statusPollTimer = setInterval(refresh, ms);
}

/* Wire Events */
window.addEventListener('pointerup', () => {
  if (suppressDrag) {
    suppressDrag = false;
    if (!isExecuting) {
      document.querySelectorAll('.scratch-block').forEach(el => (el.draggable = true));
    }
  }
});

document.querySelectorAll('.nav-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.nav-tab').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${tab}`));
  });
});

document.querySelectorAll('.cat-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    activeCategory = btn.dataset.cat;
    document.querySelectorAll('.cat-btn').forEach(b => b.classList.toggle('active', b === btn));
    renderPalette();
  });
});

$('toggle-guide').addEventListener('click', () => {
  guideVisible = !guideVisible;
  $('guide-card').classList.toggle('hidden', !guideVisible);
  $('toggle-guide').textContent = guideVisible ? 'Hide guide' : 'Step-by-step guide';
});
$('guide-hide').addEventListener('click', () => {
  guideVisible = false;
  $('guide-card').classList.add('hidden');
  $('toggle-guide').textContent = 'Step-by-step guide';
});
$('guide-prev').addEventListener('click', () => {
  if (guideStep > 0) {
    guideStep--;
    renderTutorial();
  }
});
$('guide-next').addEventListener('click', () => {
  if (guideStep < TUTORIAL_STEPS.length - 1) {
    guideStep++;
    renderTutorial();
  } else {
    guideVisible = false;
    $('guide-card').classList.add('hidden');
    $('toggle-guide').textContent = 'Step-by-step guide';
  }
});
$('guide-helper').addEventListener('click', () => {
  TUTORIAL_STEPS[guideStep].helperAction();
});

$('btn-undo').addEventListener('click', () => {
  if (!undoStack.length || isExecuting) return;
  redoStack.push(snapshotBlocks(blocks));
  blocks = undoStack.pop();
  markDirty();
  resetStepCursor();
  renderBlocks();
  evaluateTutorial();
});
$('btn-redo').addEventListener('click', () => {
  if (!redoStack.length || isExecuting) return;
  undoStack.push(snapshotBlocks(blocks));
  blocks = redoStack.pop();
  markDirty();
  resetStepCursor();
  renderBlocks();
  evaluateTutorial();
});
$('btn-clear').addEventListener('click', () => {
  if (!blocks.length || isExecuting) return;
  pushUndo();
  blocks = [];
  markDirty();
  resetStepCursor();
  renderBlocks();
  evaluateTutorial();
  setSequenceMessage('Cleared all blocks.');
});

$('save-sequence').addEventListener('click', async () => {
  const button = $('save-sequence');
  button.disabled = true;
  setSequenceMessage('Saving…');
  try {
    const poses = blocksToPoses();
    const result = await request('/api/action-sequence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ poses }),
    });
    $('config').value = result.config;
    markDirty(false);
    tutorialProgress.savedSequence = true;
    evaluateTutorial();
    setSequenceMessage(result.message);
    await refresh();
  } catch (e) {
    setSequenceMessage(e.message, true);
  } finally {
    button.disabled = !editableConfig || isExecuting;
  }
});

$('save').addEventListener('click', async () => {
  const button = $('save');
  button.disabled = true;
  $('message').textContent = 'Saving…';
  try {
    const data = await request('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: $('config').value }),
    });
    $('message').textContent = data.message;
    if (!isExecuting) await loadSequence();
  } catch (e) {
    $('message').textContent = e.message;
  } finally {
    button.disabled = false;
  }
});

$('btn-run').addEventListener('click', runAllBlocks);
$('hat-run').addEventListener('click', runAllBlocks);
$('btn-step').addEventListener('click', stepNextBlock);
$('btn-reset-steps').addEventListener('click', () => {
  if (isExecuting) return;
  resetStepCursor();
  renderBlocks();
});
$('btn-stop').addEventListener('click', stopAllExecution);
$('capture-pose').addEventListener('click', () => captureLivePose());
$('refresh-logs-btn').addEventListener('click', refreshLogs);

/* Initial boot */
renderPalette();
renderTutorial();
loadConfig();
loadSequence();
refresh();
refreshLogs();
setPollInterval(2000);
setInterval(refreshLogs, 2000);
</script>
</body>
</html>"""
