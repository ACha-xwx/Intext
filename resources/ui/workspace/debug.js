"use strict";
const query=selector=>document.querySelector(selector);
const entries=[],level=query("#level"),autoscroll=query("#autoscroll"),scroll=query("#debug-scroll"),lines=query("#log-lines");
let sequence=0,clearSequence=0,preferenceRevision=-1,historyLimit=1500,lineLimit=6000,polling=false,lastFailure=0;
const errors=new Map();
const severities=[{key:"debug",name:"DEBUG",minimum:10},{key:"info",name:"INFO",minimum:20},{key:"warning",name:"WARN",minimum:30},{key:"error",name:"ERROR",minimum:40},{key:"critical",name:"CRITICAL",minimum:50}];
const enabledSeverities=new Set(severities.map(row=>row.key)),legend=query("#log-legend"),legendButtons=new Map();
for(const severity of severities){
  const button=document.createElement("button");button.type="button";button.className="log-legend-item legend-"+severity.key;button.dataset.level=severity.key;
  const dot=document.createElement("span");dot.className="legend-dot";dot.setAttribute("aria-hidden","true");
  const name=document.createElement("span");name.textContent=severity.name;
  const count=document.createElement("span");count.className="legend-count";count.textContent="0";
  button.append(dot,name,count);button.setAttribute("aria-pressed","true");legend.append(button);legendButtons.set(severity.key,{button,count});
  button.addEventListener("click",()=>{const shown=!enabledSeverities.has(severity.key);if(shown)enabledSeverities.add(severity.key);else enabledSeverities.delete(severity.key);level.value="custom";render();diagnostic("debug","severity visibility",severity.name+" visible="+shown);});
}
function diagnostic(level,event,error){window.pywebview?.api?.diagnostic?.(level,event,error?.stack||String(error)).catch(()=>{});}
function color(level){return level>=50?"critical":level>=40?"error":level>=30?"warning":level>=20?"info":"debug";}
function applyLevelPreset(){const minimum=Number(level.value);if(!Number.isFinite(minimum))return;enabledSeverities.clear();for(const row of severities)if(row.minimum>=minimum)enabledSeverities.add(row.key);}
function updateLegend(){
  const counts={};for(const entry of entries)if(entry.id>clearSequence){const key=color(entry.level);counts[key]=(counts[key]||0)+1;}
  for(const row of severities){const {button,count}=legendButtons.get(row.key),shown=enabledSeverities.has(row.key);count.textContent=String(counts[row.key]||0);button.setAttribute("aria-pressed",String(shown));button.title=(shown?"隐藏":"显示")+row.name+" 日志";}
}
function readingAnchor(){
  const edge=scroll.getBoundingClientRect().top+scroll.clientTop;
  for(const element of lines.children){
    const box=element.getBoundingClientRect();
    if(box.bottom>edge){const height=parseFloat(getComputedStyle(element).lineHeight),row=Math.floor(Math.max(0,edge-box.top)/height);return {id:element.dataset.id,line:Number(element.dataset.firstLine)+row,offset:box.top+row*height-edge};}
  }
  return null;
}
function readingPosition(){
  const top=scroll.scrollTop,follow=autoscroll.checked&&scroll.scrollHeight-scroll.clientHeight-top<=4;
  return {top,left:scroll.scrollLeft,follow,anchor:follow?null:readingAnchor()};
}
function restorePosition({top,left,follow,anchor}){
  if(follow)scroll.scrollTop=scroll.scrollHeight;
  else{scroll.scrollTop=top;const element=anchor&&[...lines.children].find(el=>el.dataset.id===anchor.id);if(element){const row=Math.max(0,anchor.line-Number(element.dataset.firstLine)),height=parseFloat(getComputedStyle(element).lineHeight);scroll.scrollTop+=element.getBoundingClientRect().top+row*height-(scroll.getBoundingClientRect().top+scroll.clientTop)-anchor.offset;}}
  scroll.scrollLeft=left;
}
function render(position=readingPosition()){
  const fragment=document.createDocumentFragment();
  updateLegend();
  const visible=entries.filter(e=>e.id>clearSequence&&enabledSeverities.has(color(e.level)));let remaining=lineLimit,selected=[];
  for(let i=visible.length-1;i>=0&&remaining>0;i--){const e=visible[i],rows=e.text.split("\n");if(rows.length>remaining)selected.push({...e,text:rows.slice(-remaining).join("\n"),firstLine:rows.length-remaining});else selected.push(e);remaining-=rows.length;}
  for(const e of selected.reverse()){const el=document.createElement("div");el.className="log-line log-"+color(e.level);el.dataset.id=String(e.id);el.dataset.firstLine=String(e.firstLine||0);el.textContent=e.text;fragment.append(el);}
  lines.replaceChildren(fragment);
  restorePosition(position);
}
async function poll(){
  if(polling||!window.pywebview?.api)return;polling=true;
  try{
    const snapshot=await window.pywebview.api.snapshot(sequence),prefs=snapshot.preferences,root=document.documentElement;
    const theme=prefs.composer_theme||"light",fontSize=(Number(prefs.font_size)||12)*96/72+"px",count=snapshot.cached+" 条缓存日志";
    const status=snapshot.error?"保存失败："+snapshot.error:snapshot.path?`已保存 ${snapshot.saved_sequence} 条：${snapshot.path}`:"未保存；点击保存日志后写入文件。";
    const countChanged=query("#count").textContent!==count,statusChanged=query("#save-status").textContent!==status,themeChanged=root.dataset.theme!==theme,fontChanged=root.style.fontSize!==fontSize;
    const changed=snapshot.entries.length||preferenceRevision!==snapshot.preference_revision||countChanged||statusChanged||themeChanged||fontChanged;
    const position=changed?readingPosition():null;
    if(themeChanged)root.dataset.theme=theme;
    if(fontChanged){root.style.fontSize=fontSize;root.style.setProperty("--baseline",fontSize);}
    let rebuild=false;
    if(preferenceRevision!==snapshot.preference_revision){preferenceRevision=snapshot.preference_revision;level.value=({"全部":10,"INFO 及以上":20,"WARN 及以上":30,"ERROR 及以上":40,"CRITICAL":50})[prefs.debug_level]||10;applyLevelPreset();autoscroll.checked=prefs.debug_autoscroll!==false;historyLimit=prefs.debug_history||1500;lineLimit=prefs.debug_lines||6000;if(entries.length>historyLimit)entries.splice(0,entries.length-historyLimit);rebuild=true;}
    sequence=snapshot.sequence;if(snapshot.entries.length){entries.push(...snapshot.entries);if(entries.length>historyLimit)entries.splice(0,entries.length-historyLimit);rebuild=true;}
    if(countChanged)query("#count").textContent=count;if(statusChanged)query("#save-status").textContent=status;
    query("#directory").disabled=!snapshot.directory_exists;
    if(errors.has("sync")){showError("sync","");diagnostic("info","log synchronization recovered","");}
    if(rebuild)render(position);else if(position)restorePosition(position);
  }catch(error){showError("sync","日志同步暂未完成，请重试。 "+String(error));if(Date.now()-lastFailure>5000){lastFailure=Date.now();diagnostic("error","log synchronization failed",error);}}finally{polling=false;}
}
function showError(operation,text){const position=readingPosition();if(text)errors.set(operation,text);else errors.delete(operation);query("#debug-error").textContent=[...errors.values()].join("\n");query("#debug-error").hidden=!errors.size;restorePosition(position);}
level.addEventListener("change",()=>{applyLevelPreset();render();});autoscroll.addEventListener("change",()=>{if(autoscroll.checked)scroll.scrollTop=scroll.scrollHeight;});
query("#clear").addEventListener("click",()=>{clearSequence=sequence;render();});
query("#copy").addEventListener("click",async()=>{try{await navigator.clipboard.writeText(lines.innerText);showError("copy","");}catch(error){showError("copy","复制未完成，请选中文本后按 Ctrl+C。");diagnostic("warn","copy failed",error);}});
query("#save").addEventListener("click",async()=>{const b=query("#save");b.disabled=true;try{const result=await window.pywebview.api.save();showError("save",result.ok?"":result.error);await poll();}catch(error){showError("save","保存日志未完成，请重试。");diagnostic("error","save failed",error);}finally{b.disabled=false;}});
query("#directory").addEventListener("click",async()=>{try{const result=await window.pywebview.api.open_directory();showError("directory",result.ok?"":result.error);}catch(error){showError("directory","日志目录未能打开，请重试。");diagnostic("error","directory failed",error);}});
window.addEventListener("error",e=>diagnostic("error","uncaught exception",e.error||e.message));
window.addEventListener("unhandledrejection",e=>diagnostic("error","unhandled rejection",e.reason));
window.addEventListener("pywebviewready",()=>{poll();setInterval(poll,150);diagnostic("info","console ready","Chromium log view; logs remain in memory until manual save");});
window.promptsmithDebug={poll};
