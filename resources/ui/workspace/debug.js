"use strict";
const query=selector=>document.querySelector(selector);
const entries=[],level=query("#level"),autoscroll=query("#autoscroll"),scroll=query("#debug-scroll"),lines=query("#log-lines");
let refreshMs=150,pollTimer=null,sequence=0,clearSequence=0,preferenceRevision=-1,historyLimit=1500,lineLimit=6000,polling=false,lastFailure=0,displayedEntries=[],saveStatus="";
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
    if(element.getBoundingClientRect().bottom<=edge)continue;
    const body=element.querySelector(".log-message"),text=body.firstChild;
    if(!text?.length)return {id:element.dataset.id,char:0,offset:element.getBoundingClientRect().top-edge};
    let low=0,high=text.length-1;
    while(low<high){const mid=Math.floor((low+high)/2);if(characterBox(text,mid).bottom<=edge)low=mid+1;else high=mid;}
    return {id:element.dataset.id,char:Number(element.dataset.firstChar)+low,offset:characterBox(text,low).top-edge};
  }
  return null;
}
function characterBox(text,offset){
  let start=Math.max(0,Math.min(offset,text.length-1));
  if(start>0&&/[\uDC00-\uDFFF]/.test(text.data[start])&&/[\uD800-\uDBFF]/.test(text.data[start-1]))start--;
  const range=document.createRange();range.setStart(text,start);range.setEnd(text,Math.min(text.length,start+(text.data.codePointAt(start)>0xffff?2:1)));return range.getBoundingClientRect();
}
function readingPosition(){
  const top=scroll.scrollTop,follow=autoscroll.checked&&scroll.scrollHeight-scroll.clientHeight-top<=4;
  return {top,left:scroll.scrollLeft,follow,anchor:follow?null:readingAnchor()};
}
function restorePosition({top,left,follow,anchor}){
  if(follow)scroll.scrollTop=scroll.scrollHeight;
  else{scroll.scrollTop=top;const element=anchor&&[...lines.children].find(el=>el.dataset.id===anchor.id);if(element){const text=element.querySelector(".log-message").firstChild,box=text?.length?characterBox(text,anchor.char-Number(element.dataset.firstChar)):element.getBoundingClientRect();scroll.scrollTop+=box.top-(scroll.getBoundingClientRect().top+scroll.clientTop)-anchor.offset;}}
  scroll.scrollLeft=left;
}
function render(position=readingPosition()){
  const fragment=document.createDocumentFragment();
  updateLegend();
  const visible=entries.filter(e=>e.id>clearSequence&&enabledSeverities.has(color(e.level)));let remaining=lineLimit,selected=[];
  for(let i=visible.length-1;i>=0&&remaining>0;i--){const e=visible[i],message=e.message??e.text,rows=message.split("\n");if(rows.length>remaining){const tail=rows.slice(-remaining).join("\n");selected.push({...e,message:tail,firstChar:message.length-tail.length});}else selected.push({...e,message});remaining-=rows.length;}
  displayedEntries=selected.reverse();
  for(const e of displayedEntries){
    const severity=color(e.level),el=document.createElement("div");el.className="log-line log-"+severity;el.dataset.id=String(e.id);el.dataset.firstChar=String(e.firstChar||0);
    const time=document.createElement("span");time.className="log-time";time.textContent=e.time||"";time.hidden=!e.time;
    const label=document.createElement("span");label.className="log-level";label.textContent=({debug:"DBG",info:"INF",warning:"WRN",error:"ERR",critical:"CRT"})[severity];label.setAttribute("aria-label",severities.find(s=>s.key===severity).name);
    const source=document.createElement("span");source.className="log-source";source.textContent=e.source?"["+e.source+"]":"";source.hidden=!e.source;source.title=e.source||"";
    const body=document.createElement("span");body.className="log-message";body.textContent=e.message;
    el.title=e.text.split("\n",1)[0];el.append(time,label,source,body);fragment.append(el);
  }
  lines.replaceChildren(fragment);
  restorePosition(position);
}
async function poll(){
  if(polling||!window.pywebview?.api)return;polling=true;
  try{
    const snapshot=await window.pywebview.api.snapshot(sequence),prefs=snapshot.preferences,root=document.documentElement;
    refreshMs=prefs.debug_refresh_ms||150;window.promptsmithNotifications.configure(prefs.notification_seconds??5);
    const theme=prefs.composer_theme||"light",fontSize=(Number(prefs.font_size)||12)*96/72+"px",count=snapshot.cached+" 条缓存日志";
    const status=snapshot.error?"保存失败："+snapshot.error:snapshot.path?`已保存 ${snapshot.saved_sequence} 条：${snapshot.path}`:"";
    const countChanged=query("#count").textContent!==count,themeChanged=root.dataset.theme!==theme,fontChanged=root.style.fontSize!==fontSize;
    const changed=snapshot.entries.length||preferenceRevision!==snapshot.preference_revision||countChanged||themeChanged||fontChanged;
    const position=changed?readingPosition():null;
    if(themeChanged)root.dataset.theme=theme;
    if(fontChanged){root.style.fontSize=fontSize;root.style.setProperty("--baseline",fontSize);}
    let rebuild=false;
    if(preferenceRevision!==snapshot.preference_revision){preferenceRevision=snapshot.preference_revision;level.value=({"全部":10,"INFO 及以上":20,"WARN 及以上":30,"ERROR 及以上":40,"CRITICAL":50})[prefs.debug_level]||10;applyLevelPreset();autoscroll.checked=prefs.debug_autoscroll!==false;historyLimit=prefs.debug_history||1500;lineLimit=prefs.debug_lines||6000;if(entries.length>historyLimit)entries.splice(0,entries.length-historyLimit);rebuild=true;}
    sequence=snapshot.sequence;if(snapshot.entries.length){entries.push(...snapshot.entries);if(entries.length>historyLimit)entries.splice(0,entries.length-historyLimit);rebuild=true;}
    if(countChanged)query("#count").textContent=count;
    if(status!==saveStatus){saveStatus=status;window.promptsmithNotifications.sync("debug:save",status,{variant:snapshot.error?"error":"success"});}
    query("#directory").disabled=!snapshot.directory_exists;
    if(errors.has("sync")){showError("sync","");diagnostic("info","log synchronization recovered","");}
    if(rebuild)render(position);else if(position)restorePosition(position);
  }catch(error){showError("sync","日志同步暂未完成，程序会继续尝试。");if(Date.now()-lastFailure>5000){lastFailure=Date.now();diagnostic("error","log synchronization failed",error);}}finally{polling=false;}
}
function showError(operation,text){if(text)errors.set(operation,text);else errors.delete(operation);window.promptsmithNotifications.sync("debug:"+operation,text,{variant:"error"});}
level.addEventListener("change",()=>{applyLevelPreset();render();});autoscroll.addEventListener("change",()=>{if(autoscroll.checked)scroll.scrollTop=scroll.scrollHeight;});
query("#clear").addEventListener("click",()=>{clearSequence=sequence;render();});
query("#copy").addEventListener("click",async()=>{try{await navigator.clipboard.writeText(displayedEntries.map(e=>e.firstChar?e.message:e.text).join("\n"));showError("copy","");window.promptsmithNotifications.show("已复制当前显示的日志。",{variant:"success",key:"debug:copied"});}catch(error){showError("copy","复制未完成，请选中文本后按Ctrl+C。");diagnostic("warn","copy failed",error);}});
query("#save").addEventListener("click",async()=>{const b=query("#save");b.disabled=true;try{const result=await window.pywebview.api.save();showError("save",result.ok?"":result.error);await poll();}catch(error){showError("save","保存日志未完成，请重试。");diagnostic("error","save failed",error);}finally{b.disabled=false;}});
query("#directory").addEventListener("click",async()=>{try{const result=await window.pywebview.api.open_directory();showError("directory",result.ok?"":result.error);}catch(error){showError("directory","日志目录未能打开，请重试。");diagnostic("error","directory failed",error);}});
window.addEventListener("error",e=>{showError("exception","日志页面处理出现错误，请重试。");diagnostic("error","uncaught exception",e.error||e.message);});
window.addEventListener("unhandledrejection",e=>{showError("exception","日志页面操作未完成，请重试。");diagnostic("error","unhandled rejection",e.reason);});
async function pollLoop(){await poll();pollTimer=setTimeout(pollLoop,refreshMs);}
window.addEventListener("pagehide",()=>clearTimeout(pollTimer));
window.addEventListener("pywebviewready",()=>{pollLoop();diagnostic("info","console ready","Chromium log view; logs remain in memory until manual save");});
window.promptsmithDebug={poll};
