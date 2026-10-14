"use strict";
// A keyed view of SessionState. No business confirmations live in JavaScript.
const $ = selector => document.querySelector(selector);
const SVG_NS = "http://www.w3.org/2000/svg";
const paths = {
  send:["M12 19V5","m5 12 7-7 7 7"], stop:["M7 7h10v10H7z"], close:["m6 6 12 12","M18 6 6 18"],
  chevronDown:["m6 9 6 6 6-6"],
  check:["m5 12 4 4L19 6"], loop:["M3.286 7A9 9 0 0 1 18 5l3 3","M21 3v5h-5","M20.714 17A9 9 0 0 1 6 19l-3-3","M8 16H3v5"],
  brain:["M12 18V5","M15 13a4.17 4.17 0 0 1-3-4 4.17 4.17 0 0 1-3 4","M17.598 6.5A3 3 0 1 0 12 5a3 3 0 1 0-5.598 1.5","M17.997 5.125a4 4 0 0 1 2.526 5.77","M18 18a4 4 0 0 0 2-7.464","M19.967 17.483A4 4 0 1 1 12 18a4 4 0 1 1-7.967-.517","M6 18a4 4 0 0 1-2-7.464","M6.003 5.125a4 4 0 0 0-2.526 5.77"],
  image:["M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z","M11 8a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z","m21 15-5-5L5 21"],
  search:["M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z","m16 16 5 5"],
  file:["M6 3h8l4 4v14H6z","M14 3v5h5","M9 12h6","M9 16h6"],
  sidebar:["M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z","M9 3v18"],
  newchat:["M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z","M9 11h6","M12 8v6"],
  more:["M5 12h.01","M12 12h.01","M19 12h.01"],
  pencil:["m16 3 5 5-12 12-6 1 1-6Z","m14 5 5 5"],
  pin:["m16 3 5 5-4 1-4 4 1 4-2 2-7-7 2-2 4 1 4-4Z","m8 16-5 5"],
  trash:["M3 6h18","M9 6V3h6v3","m5 6 1 15h12l1-15","M10 10v7","M14 10v7"],
  activity:["M3 12h4l3-8 4 16 3-8h4"],plug:["M8 3v5","M16 3v5","M6 8h12v4a6 6 0 0 1-12 0Z","M12 18v3"],sliders:["M4 7h5","M13 7h7","M4 17h11","M19 17h1","M9 4v6","M15 14v6"]
};
function icon(name) {
  const svg=document.createElementNS(SVG_NS,"svg");
  svg.setAttribute("viewBox","0 0 24 24"); svg.setAttribute("fill","none");
  svg.setAttribute("stroke","currentColor"); svg.setAttribute("stroke-width","1.8");
  svg.setAttribute("stroke-linecap","round"); svg.setAttribute("stroke-linejoin","round");
  svg.setAttribute("aria-hidden","true");
  for(const d of paths[name]||paths.file) {const p=document.createElementNS(SVG_NS,"path");p.setAttribute("d",d);svg.append(p);}return svg;
}
function node(tag, cls, text) {const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function button(text, handler, cls="") {const n=node("button",cls,text);n.type="button";n.addEventListener("click",handler);return n;}
function effortMeter(){const meter=node("span","effort-indicator");meter.setAttribute("aria-hidden","true");for(let i=0;i<4;i++){const bar=node("i");bar.style.height=(5+i*2.5)+"px";meter.append(bar);}return meter;}
function actions(parent, keys, fullWidth=false) {
  const box=node("div","actions"+(fullWidth?" stage-actions":""));
  for(const key of keys) {const spec=state.buttons[key];if(!spec)continue;
    const label=key==="result_details"?"附注":spec.text;
    const b=button(fullWidth?"":label,()=>key==="back_stage"?navigatePrevious():key==="result_details"?openReview("result"):command("button",{key}),"flow-action"+(fullWidth?" glass stage-action":""));
    if(fullWidth){
      for(const layer of ["shade-veil","light-band"]){const sheen=node("span","stage-action-"+layer);sheen.setAttribute("aria-hidden","true");b.append(sheen);}
      b.append(node("span","stage-action-label",label));
    }
    b.disabled=!spec.enabled;b.dataset.action=key;b.dataset.focusKey="action:"+key;box.append(b);
  }
  if(fullWidth){box.style.setProperty("--action-count",String(box.childElementCount||1));box.dataset.count=String(box.childElementCount);diagnostic("debug","stage action row rendered","keys="+keys.filter(key=>state.buttons[key]).join(",")+" count="+box.childElementCount+" layout=equal-width");}
  parent.append(box);return box;
}
function markdown(parent,text,fold=false) {
  const lines=String(text||"").split(/\r?\n/);let destination=parent;
  for(let i=0;i<lines.length;i++) {
    let line=lines[i],match=line.match(/^\s*(#{1,6})\s+(.+?)\s*#*$/);
    if(!match&&i+1<lines.length&&/^\s*(?:={3,}|-{3,})\s*$/.test(lines[i+1])&&line.trim()) {
      match=[null,lines[i+1].includes("=")?"#":"##",line];i++;
    }
    const htmlHeading=line.match(/^\s*<h([1-6])[^>]*>(.*?)<\/h\1>\s*$/i);
    if(htmlHeading)match=[null,"#".repeat(Number(htmlHeading[1])),htmlHeading[2]];
    if(match) {
      if(fold) {const d=node("details");d.append(node("summary","",match[2]));destination=node("div","reading");d.append(destination);parent.append(d);}
      else parent.append(node("h"+Math.min(4,match[1].length),"",match[2]));
    } else {
      // Render untrusted model output as text. Never evaluate model HTML.
      destination.append(document.createTextNode(line+(i<lines.length-1?"\n":"")));
    }
  }
}

let state=null, version=0, inFlight=false, session=null;
let stopping=false, navigating=false;
let choiceRunning=false, choiceQueue=[], optimisticEffort=null;
let popup=null, popupKind=null, reviewKind=null, provider=null;
let reviewSignature=null;
let popupAnchor=null, popupObserver=null, popupLayoutFrame=null;
let popupReturnFocus=null;
let refreshModelMenu=null;
const rendered=new Map(), drafts=new Map(), traces=new Map();
const viewport=$("#viewport"), timeline=$("#timeline"), message=$("#message");
$("#send").append(icon("send"));
function toast(text,variant="info",options={}) {return window.promptsmithNotifications.show(text,{variant,...options});}
async function command(action,data={}) {
  if(!state||inFlight||window.promptsmithStartup&&!window.promptsmithStartup.entered)return false;
  const owner=state.session,stamp=state.stamp;
  inFlight=true;document.body.classList.add("pending");updateEnabled();
  try {
    if((window.promptsmithSettings?.open&&!action.startsWith("settings_"))||action==="settings_back"){
      if(!await window.promptsmithSettings.flush())return false;
    }
    await window.promptsmithHistory?.flushDrafts();
    if(state.session!==owner||state.stamp!==stamp){toast("内容已变化，请查看当前内容再操作。","warning");return false;}
    const result=await window.pywebview.api.dispatch(action,data,stamp);
    if(!result.ok) {toast(result.error||"操作未完成，请重试。","error",{key:"action:"+action});return false;}
    if(action==="send")document.dispatchEvent(new CustomEvent("promptsmith-action-completed",{detail:{action,session:owner}}));
    return result.data||true;
  } catch(error) {toast("暂时无法完成操作，请重试。","error",{key:"action:"+action});diagnostic("error","action failed: "+action,error?.stack||String(error));return false;}
  finally {inFlight=false;document.body.classList.remove("pending");updateEnabled();await poll();}
}
function sendOnEnter(textarea,send) {
  textarea.addEventListener("keydown",event=>{
    if(event.key==="Enter"&&!event.shiftKey&&!event.isComposing&&event.keyCode!==229) {event.preventDefault();send();}
  });
}
function currentQuestionViews() {
  if(!state||state.reanswer)return [];
  return state.cards.filter(card=>card.kind==="question")
    .map(card=>({id:card.question.question_id,view:rendered.get(card.key)}))
    .filter(({id,view})=>view?.kind==="question"&&view.question?.question_id===id);
}
async function submitQuestionAnswers() {
  if(!state||state.locked||inFlight)return;
  const owner=state.session;
  const answers=currentQuestionViews().map(({id,view})=>({id,text:view.input.value})).filter(row=>row.text.trim());
  if(!answers.length)return;
  const result=await command("answer",{answers});
  if(result&&state.session===owner){
    const submitted=new Set(result.submitted||answers.map(row=>row.id));
    for(const row of answers)if(submitted.has(row.id)&&drafts.get(row.id)===row.text)drafts.delete(row.id);
  }
}
function updateEnabled() {
  if(!state)return;
  const send=$("#send"),mode=state.locked?"stop":"send";
  if(send.dataset.mode!==mode){send.dataset.mode=mode;send.replaceChildren(icon(mode));
    send.classList.toggle("stop",mode==="stop");send.setAttribute("aria-label",mode==="stop"?"停止生成":"发送消息");}
  send.disabled=state.locked?stopping:inFlight||!message.value.trim();
  const questions=currentQuestionViews(),hasAnswers=questions.some(({view})=>view.input.value.trim());
  for(const {view:q} of questions) {
    q.input.disabled=state.locked||inFlight;q.send.disabled=state.locked||inFlight||!hasAnswers;q.skip.disabled=state.locked||inFlight;
  }
  for(const selector of ["#model-button","#category-button","#depth-button"])$(selector).disabled=state.locked||inFlight;
  for(const b of document.querySelectorAll(".flow-action")) b.disabled=(b.dataset.action==="back_stage"?navigating||stopping:inFlight)||!state.buttons[b.dataset.action]?.enabled;
  for(const b of document.querySelectorAll(".requirement-select"))b.disabled=inFlight||state.locked;
  for(const b of document.querySelectorAll(".skill-table-toolbar button"))b.disabled=inFlight||state.locked;
  window.promptsmithSettings?.refreshEnabled();
}
// Local model preferences animate immediately; serial writes keep backend
// confirmation/version protection without briefly greying the whole composer.
function choosePreference(action,data) {
  if(!state||state.locked||inFlight)return;
  if(action==="effort"){optimisticEffort=data.value;syncEffort();}
  choiceQueue.push({action,data,session:state.session});drainChoices();
}
async function drainChoices() {
  if(choiceRunning)return;choiceRunning=true;
  try {
    while(choiceQueue.length){const item=choiceQueue.shift();
      if(item.session!==state.session)continue;
      try{const result=await window.pywebview.api.dispatch(item.action,item.data,state.stamp);if(item.session!==state.session)continue;if(!result.ok)toast(result.error,"error",{key:"model:choice"});
        if(result.ok&&result.data){state.effort=result.data.effort;state.model=result.data.model;state.active_service=result.data.active_service;}
        await poll();syncEffort();}
      catch(error){toast("选择未应用，请重试。","error",{key:"model:choice"});diagnostic("error","model choice failed",String(error));}
    }
  }finally{optimisticEffort=null;choiceRunning=false;syncEffort();await poll();}
}
function syncEffort(){
  if(!state)return;const effort=optimisticEffort||state.effort,index=Math.max(0,["low","medium","high","max"].indexOf(effort));
  const track=document.querySelector(".thinking-track");
  if(track){track.style.setProperty("--effort-index",index);for(const b of track.querySelectorAll("button")){const active=b.dataset.effort===effort;b.setAttribute("aria-checked",String(active));b.tabIndex=active?0:-1;}}
  for(const meter of document.querySelectorAll(".effort-indicator"))for(const [i,bar] of [...meter.children].entries())bar.classList.toggle("filled",i<=index);
  for(const b of document.querySelectorAll(".model-row")){
    const selected=b.dataset.model===state.model&&(!b.dataset.service||b.dataset.service===state.active_service);b.classList.toggle("selected",selected);
    if(selected&&!b.querySelector(".check")){const check=icon("check");check.classList.add("check");b.querySelector(".model-name").append(check);}
    if(!selected)b.querySelector(".check")?.remove();
  }
}
async function sendMessage() {
  const text=message.value;if(!text.trim()||state?.locked||inFlight)return;
  if(await command("send",{text})) {if(message.value===text)message.value="";resizeMessage();updateEnabled();}
}
async function stopGeneration() {
  if(!state?.locked||stopping)return;
  const owner=state.session,scope=state.stop_scope;
  stopping=true;updateEnabled();
  try {
    // Stop bypasses draft flushing and ordinary command locks.
    const result=await window.pywebview.api.dispatch("stop",{session:owner,scope},state.stamp);
    if(owner===state.session&&!result.ok)toast(result.error||"停止未完成，请重试。","error",{key:"action:stop"});
    diagnostic(result.ok?"info":"warn","generation stop",result.ok?"cancelled; retries disabled":result.error);
  }catch(error){toast("停止未完成，请重试。","error",{key:"action:stop"});diagnostic("error","generation stop failed",error?.stack||String(error));}
  finally{stopping=false;await poll();updateEnabled();}
}
async function navigatePrevious() {
  if(!state?.navigation?.previous||navigating||stopping)return;
  const owner=state.session,scope=state.stop_scope,stage=state.navigation.stage;
  navigating=true;updateEnabled();
  try {
    // Like Stop, Back remains usable even if a queued draft write is pending.
    const answer_drafts=Object.fromEntries(currentQuestionViews().map(({id,view})=>[id,view.input.value]));
    const result=await window.pywebview.api.dispatch("navigate",{direction:"previous",session:owner,scope,stage,answer_drafts},state.stamp);
    if(owner===state.session&&!result.ok)toast(result.error||"返回未完成，请重试。","error",{key:"action:navigate"});
  }catch(error){toast("返回未完成，请重试。","error",{key:"action:navigate"});diagnostic("error","workspace navigation failed",error?.stack||String(error));}
  finally{navigating=false;await poll();updateEnabled();}
}
function resizeMessage() {message.style.height="auto";message.style.height=Math.min(message.scrollHeight,parseFloat(getComputedStyle(message).lineHeight)*6)+"px";}
message.addEventListener("input",()=>{resizeMessage();updateEnabled();window.promptsmithHistory?.scheduleDraft();});sendOnEnter(message,sendMessage);$("#send").addEventListener("click",()=>state?.locked?stopGeneration():sendMessage());

const segmenter=typeof Intl.Segmenter==="function"?new Intl.Segmenter(undefined,{granularity:"grapheme"}):null;
class TraceView {
  constructor(record) {
    this.el=node("section","trace");this.source="";this.pending="";this.last=0;this.frame=null;
    this.status=null;this.elapsedBase=0;this.elapsedAnchor=0;
    this.header=button("",()=>this.toggle(this.outer,this.header));
    const dots=node("span","dots");for(let i=0;i<9;i++){const dot=node("i");dot.style.setProperty("--i",String(i));dots.append(dot);}
    this.label=node("span");this.statusText=document.createTextNode("");this.elapsed=node("span","trace-elapsed");
    this.label.append(this.statusText,this.elapsed,document.createTextNode(" 秒 "));this.header.append(dots,this.label,node("span","chevron"));
    this.outer=node("div","reveal");
    this.outer.inert=true;this.header.setAttribute("aria-expanded","false");
    const clip=node("div","clip"),body=node("div","trace-body");
    this.thoughtButton=button("",()=>this.toggle(this.thoughtReveal,this.thoughtButton));
    this.thoughtButton.append(node("span","chevron"),node("span","","思考内容"));
    this.thoughtButton.classList.add("expanded");this.thoughtReveal=node("div","reveal open");
    this.thoughtButton.setAttribute("aria-expanded","true");
    const thoughtClip=node("div","clip");this.thought=node("div","thought");this.thought.tabIndex=0;
    this.text=document.createTextNode("");this.thought.append(this.text);thoughtClip.append(this.thought);this.thoughtReveal.append(thoughtClip);
    this.activities=node("div","activities");
    body.append(this.thoughtButton,this.thoughtReveal,this.activities);clip.append(body);this.outer.append(clip);
    this.el.append(this.header,this.outer);this.update(record);
  }
  toggle(reveal,control) {
    const open=!reveal.classList.contains("open");
    if(!open&&reveal.contains(document.activeElement))control.focus({preventScroll:true});
    reveal.inert=!open;reveal.classList.toggle("open",open);control.classList.toggle("expanded",open);control.setAttribute("aria-expanded",String(open));
    diagnostic("debug","trace disclosure",String(open));
  }
  update(record) {
    const now=performance.now(),previous=this.status;
    let elapsed=Number(record.elapsed||0);if(!Number.isFinite(elapsed)||elapsed<0)elapsed=0;
    if(previous==="working"&&record.status==="working")elapsed=Math.max(elapsed,this.elapsedAt(now));
    this.status=record.status;this.elapsedBase=elapsed;this.elapsedAnchor=now;
    this.el.classList.toggle("working",record.status==="working");
    this.statusText.data=({working:"正在处理…",done:"已完成",failed:"处理未完成",cancelled:"已取消"}[record.status]||"已完成")+" · ";
    this.updateElapsed(now);
    if(previous!==this.status&&(this.status==="working"||previous==="working"))
      diagnostic("debug",this.status==="working"?"trace clock started":"trace clock stopped",`id=${record.id} status=${this.status} elapsed=${elapsed.toFixed(3)} clock=monotonic-local`);
    const source=String(record.reasoning||"").replace(/\r\n?/g,"\n").replace(/\n[ \t]*\n(?:[ \t]*\n)*/g,"\n");
    const hasThought=source.trim().length>0;
    if(hasThought!==this.hasThought) {
      if(!hasThought&&(document.activeElement===this.thoughtButton||this.thoughtReveal.contains(document.activeElement)))this.header.focus({preventScroll:true});
      this.thoughtButton.hidden=!hasThought;this.thoughtReveal.hidden=!hasThought;
      this.hasThought=hasThought;
      diagnostic("debug","trace thinking visibility",`id=${record.id} visible=${hasThought}`);
    }
    if(this.status==="cancelled") {
      // Stop freezes an active view; restored cancelled records are readable
      // immediately without replaying the interrupted animation.
      if(previous===null)this.text.data=source;
      this.close();this.source=source;
      if(previous!==null&&previous!=="cancelled")
        diagnostic("debug","trace animation cancelled",`id=${record.id} visible=${this.text.length} received=${source.length}`);
    } else if(source!==this.source) {
      if(!source.startsWith(this.source)) {this.text.data="";this.pending=source;}
      else this.pending+=source.slice(this.source.length);
      this.source=source;
    }
    const activityKey=JSON.stringify(record.activities||[]);
    if(activityKey!==this.activityKey) {this.activityKey=activityKey;this.activities.replaceChildren();
      for(const [name,value] of record.activities||[]) {const row=node("div","activity");row.append(icon("file"),node("span","",name),node("span","",String(value)));this.activities.append(row);}
    }
    window.promptsmithNotifications.sync("trace:"+session+":"+record.id,record.error||"",{variant:"error"});
    if((this.pending||this.status==="working")&&this.frame===null)this.frame=requestAnimationFrame(t=>this.tick(t));
    else if(!this.pending&&this.status!=="working"&&this.frame!==null){cancelAnimationFrame(this.frame);this.frame=null;}
  }
  elapsedAt(now){return this.elapsedBase+(this.status==="working"?Math.max(0,now-this.elapsedAnchor)/1000:0);}
  updateElapsed(now){const value=this.elapsedAt(now).toFixed(1);if(this.elapsed.textContent!==value)this.elapsed.textContent=value;}
  tick(now) {
    this.frame=null;
    if(!this.el.isConnected){return;}
    this.updateElapsed(now);
    if(now-this.last>=16&&this.pending) {
      const speed=state?.display_preferences?.thinking_speed??1;
      let end=Math.min(this.pending.length,Math.max(1,Math.min(4096,Math.ceil(this.pending.length*speed/18))));
      if(segmenter) {
        for(const chunk of segmenter.segment(this.pending.slice(0,end+80))) {
          if(chunk.index+chunk.segment.length>=end){end=chunk.index+chunk.segment.length;break;}
        }
      } else if(end<this.pending.length&&this.pending.charCodeAt(end-1)>=0xd800&&this.pending.charCodeAt(end-1)<=0xdbff)end++;
      const follow=this.thought.scrollHeight-this.thought.scrollTop-this.thought.clientHeight<24;
      this.text.appendData(this.pending.slice(0,end));this.pending=this.pending.slice(end);this.last=now;
      if(follow&&state?.display_preferences?.thinking_autoscroll!==false)this.thought.scrollTop=this.thought.scrollHeight;
    }
    if(this.pending||this.status==="working")this.frame=requestAnimationFrame(t=>this.tick(t));
  }
  close(){if(this.frame!==null)cancelAnimationFrame(this.frame);this.frame=null;this.pending="";}
}
function renderRequirements(box) {
    if(!state.requirement_rows.length)box.append(node("p","notice","发送目标并整理后，需求会显示在这里。"));
    const table=node("table"),head=node("tr");for(const label of ["需求类型","需求内容","内容来源","确认状态"])head.append(node("th","",label));table.append(head);
    const body=node("tbody"),detail=node("div","detail","选中一行查看完整需求。");
    for(const row of state.requirement_rows){
      const tr=node("tr"),select=button(row.field,()=>chooseRow(),"requirement-select");
      select.setAttribute("aria-label","选择需求："+row.field);select.dataset.focusKey="requirement:"+row.id;
      const first=node("td");first.append(select);tr.append(first);
      for(const value of [row.text,row.kind,row.status])tr.append(node("td","",value));
      async function chooseRow(){
        if(inFlight||state.locked)return;
        if(!await command("requirement_row",{id:row.id})||!tr.isConnected)return;
        for(const r of body.children){r.classList.remove("selected");r.querySelector("button").setAttribute("aria-pressed","false");}
        tr.classList.add("selected");select.setAttribute("aria-pressed","true");detail.textContent=row.text;
        diagnostic("debug","requirement selected",row.id);
      }
      const selected=state.requirement_selection?.includes(row.id);select.setAttribute("aria-pressed",String(!!selected));
      if(selected){tr.classList.add("selected");detail.textContent=row.text;}
      tr.addEventListener("click",event=>{if(!event.target.closest("button"))select.click();});body.append(tr);
    }table.append(body);const wrap=node("div","table-wrap");wrap.append(table);box.append(wrap,detail);
    if(state.conflicts.length)box.append(node("p","notice",state.conflicts.join("\n")));
    if(state.requirement_reason)box.append(node("p","notice","确认前请处理："+state.requirement_reason));
    actions(box,["edit_requirement","remove_requirement","confirm_requirements","reanalyze_requirements"],true);
  }
function createCard(card) {
  const el=node("section","message"+(card.kind==="user"?" user":""));const view={el,kind:card.kind};
  if(["requirements","plan","skills","result"].includes(card.kind))el.classList.add("stage-message");
  if(card.kind==="user") {
    if(card.question_id&&card.can_reanswer) {const b=button("",()=>command("reanswer",{id:card.question_id}),"glass reanswer");b.title="补答这个问题";b.setAttribute("aria-label","补答这个问题");b.append(icon("loop"));el.append(b);}
    el.append(node("div","bubble",card.text));
  } else if(card.kind==="question") {
    el.append(node("div","question-title",card.question.text));
    const row=node("div","answer-row"),input=node("textarea","answer-input");input.rows=2;input.setAttribute("aria-label","回答这个问题");input.value=drafts.get(card.question.question_id)||"";
    const send=button("",submitQuestionAnswers,"send"),skip=button("跳过",()=>command("skip",{id:card.question.question_id}),"skip");send.append(icon("send"));send.setAttribute("aria-label","提交本轮已填写的回答");send.title="提交本轮已填写的回答";skip.append(icon("close"));
    input.addEventListener("input",()=>{drafts.set(card.question.question_id,input.value);updateEnabled();window.promptsmithHistory?.scheduleDraft();});sendOnEnter(input,submitQuestionAnswers);
    row.append(input,send,skip);el.append(row);Object.assign(view,{input,send,skip});
  } else if(card.kind==="navigation") {
    actions(el,["back_stage","continue_stage"]);
  } else if(card.kind==="requirements") {
    el.append(node("h2","",card.title));renderRequirements(el);
  } else if(card.kind==="plan") {
    el.append(node("h2","",card.title),node("p","notice",{draft:"待确认",confirmed:"已确认",stale:"需求已变化，旧方案已过期"}[card.status]||card.status));
    const reading=node("div","reading");markdown(reading,card.text,true);el.append(reading);
    actions(el,["edit_plan","confirm_plan","find_skills"],true);
  } else if(card.kind==="history_question") {el.append(node("div","question-title",card.text));}
  else if(card.kind==="result") {
    const reading=node("div","reading");markdown(reading,card.text);el.append(reading);
    actions(el,["copy","export","result_details"],true);
  } else if(card.kind==="skills") {
    el.append(node("p","notice","Skill 可用于具体工作；你也可以直接跳过。"));
    const progress=node("p","notice skill-search-progress",card.progress||"");progress.setAttribute("role","status");progress.setAttribute("aria-label","Skill 搜索进度");progress.hidden=!card.progress;el.append(progress);
    actions(el,["cancel_request","find_skills","find_online","integrate","direct_skills","skip_skills"],true);
    const tableBox=node("div","skill-table"),filters=node("div","skill-table-toolbar");filters.setAttribute("role","toolbar");filters.setAttribute("aria-label","Skill 表格筛选");
    const sources=node("div","skill-table-sources");for(const source of ["全部来源","本地","联网","内置","已选"]){const b=button(source,()=>command("source",{value:source}),"skill-filter");b.classList.toggle("selected",source===state.source);b.setAttribute("aria-pressed",String(source===state.source));b.disabled=state.locked||inFlight;sources.append(b);}
    const showAll=button(state.show_all?"只显示推荐":"显示全部",()=>command("show_all"),"skill-table-display");showAll.setAttribute("aria-pressed",String(state.show_all));showAll.disabled=state.locked||inFlight;filters.append(sources,showAll);tableBox.append(filters);
    const wrap=node("div","table-wrap"),table=node("table"),head=node("thead"),tr=node("tr");
    for(const label of ["Skill","来源","推荐系数","操作"])tr.append(node("th","",label));head.append(tr);table.append(head);
    const tbody=node("tbody");for(const skill of card.rows||[]) {
      const row=node("tr");row.append(node("td","",skill.name),node("td","",skill.source),node("td","",Number(skill.score).toFixed(2)));
      const cell=node("td"),b=button(skill.selected?"已选中该 Skill":"选用此 Skill",()=>command("select_skill",{id:skill.id}));b.disabled=!skill.allowed||state.locked;cell.append(b);
      if(skill.bindings.length)cell.append(button("取消选用",()=>command("remove_skill",{ids:skill.bindings})));
      row.append(cell);tbody.append(row);const detail=node("tr"),d=node("td");d.colSpan=4;const fold=node("details");fold.append(node("summary","",skill.description||"查看用途与来源"),node("div","reading",skill.details));d.append(fold);detail.append(d);tbody.append(detail);
    }table.append(tbody);wrap.append(table);tableBox.append(wrap);el.append(tableBox);
    diagnostic("debug","skill table toolbar rendered","source="+state.source+" rows="+(card.rows||[]).length+" show_all="+Boolean(state.show_all));
  } else if(card.kind==="interview_unknowns") {el.append(node("p","notice",card.text));actions(el,["continue_interview","defer_interview_unknowns"]);}
  return view;
}
function applySnapshot(next) {
  window.promptsmithNotifications.sync("workspace:sync",next.sync_error||"",{variant:"error"});
  if(!next.stamp)return;
  const priorFocus=timeline.contains(document.activeElement)?captureFocus():null;
  const follow=viewport.scrollHeight-viewport.scrollTop-viewport.clientHeight<64;
  const priorStage=state?.navigation?.stage;
  const priorRestore=state?.drafts?.answer_restore_id;
  const oldSession=session;state=next;session=state.session;
  if(oldSession!==null&&oldSession!==session) {choiceQueue=[];optimisticEffort=null;for(const t of traces.values())t.close();traces.clear();rendered.clear();drafts.clear();timeline.replaceChildren();message.value="";closePopup(true);}
  const restored=oldSession===null||oldSession!==session;
  const answersRestored=!restored&&priorRestore!==state.drafts?.answer_restore_id&&Boolean(state.drafts?.answer_restore_id);
  if(restored||answersRestored){drafts.clear();for(const [id,text] of Object.entries(state.drafts?.answers||{}))drafts.set(id,text);}
  if(restored){message.value=state.drafts?.message||"";resizeMessage();}
  document.documentElement.dataset.theme=state.theme;
  document.documentElement.style.fontSize=Number(state.font_size)*96/72*1.25+"px";
  document.documentElement.style.setProperty("--baseline",Number(state.font_size)*96/72+"px");
  document.documentElement.style.setProperty("--conversation-width",(state.display_preferences?.conversation_width??1060)+"px");
  window.promptsmithNotifications.configure(state.display_preferences?.notification_seconds??5);
  const settingsOpen=state.page==="settings";
  viewport.hidden=settingsOpen;$("footer").hidden=settingsOpen;$("#settings-page").hidden=!settingsOpen;
  for(const b of document.querySelectorAll("[data-panel]"))b.hidden=settingsOpen;
  window.promptsmithSettings?.update(state.settings,settingsOpen);
  window.promptsmithHistory?.update(state.history,restored);
  for(const notice of state.notifications||[])if(notice.id>(window.promptsmithNoticeId||0)){toast(notice.body||notice.text,notice.level,{title:notice.title,key:notice.key});window.promptsmithNoticeId=notice.id;}
  window.promptsmithEditors?.update(state.editor);
  $("#hero").hidden=state.cards[0]?.kind!=="welcome";
  const keys=new Set();let position=0;
  for(const card of state.cards) {
    if(card.kind==="welcome"||state.reanswer&&card.kind==="question")continue;
    keys.add(card.key);let view=rendered.get(card.key);
    if(card.kind==="trace") {
      if(!view){const trace=new TraceView(card.trace);traces.set(card.key,trace);view={el:trace.el,kind:"trace"};rendered.set(card.key,view);}else traces.get(card.key).update(card.trace);
    } else {
      // Progress alone must not replace the table, its open details or scroll.
      const {progress:skillProgress,...cardContent}=card;
      const signature=JSON.stringify([card.kind==="skills"?cardContent:card,state.buttons,state.source,state.show_all,...(card.kind==="requirements"?[state.requirement_rows,state.requirement_selection,state.requirement_reason,state.conflicts]:[])]);
      if(!view||view.signature!==signature||answersRestored&&card.kind==="question") {
        // Textareas retain their live draft and caret through unrelated trace updates.
        if(!answersRestored&&view?.kind==="question"&&JSON.stringify(view.question)===JSON.stringify(card.question)) {view.signature=signature;}
        else {const previous=view,openSections=[...(previous?.el.querySelectorAll("details[open] summary")||[])].map(e=>e.textContent);
          view=createCard(card);view.signature=signature;view.question=card.question;
          for(const summary of view.el.querySelectorAll("details summary"))if(openSections.includes(summary.textContent))summary.parentElement.open=true;
          if(previous)previous.el.replaceWith(view.el);rendered.set(card.key,view);}
      }
      if(card.kind==="skills"){const progress=view.el.querySelector(".skill-search-progress");const text=card.progress||"";if(progress.textContent!==text)progress.textContent=text;progress.hidden=!text;}
    }
    const existing=timeline.children[position];if(existing!==view.el)timeline.insertBefore(view.el,existing||null);position++;
  }
  for(const [key,view] of rendered)if(!keys.has(key)){view.el.remove();traces.get(key)?.close();traces.delete(key);rendered.delete(key);}
  let reanswer=$("#reanswer-context");if(state.reanswer) {if(!reanswer){reanswer=node("div","notice");reanswer.id="reanswer-context";timeline.append(reanswer);}reanswer.replaceChildren(node("p","",state.reanswer_text),button("取消补答",()=>command("cancel_reanswer")));}else reanswer?.remove();
  const model=state.model_info||state.models.find(m=>m.id===state.model),modelButton=$("#model-button"),modelSignature=JSON.stringify([state.model,state.theme,model,state.active_service]);
  if(modelButton.dataset.signature!==modelSignature){modelButton.dataset.signature=modelSignature;modelButton.replaceChildren();
    const img=providerImage(model?.provider);if(img)modelButton.append(img);modelButton.append(node("span","",model?.name||state.model||"选择模型"));
    const arrow=icon("chevronDown");arrow.classList.add("model-chevron");
    modelButton.append(effortMeter(),arrow);}
  modelButton.classList.toggle("picker-open",popupKind==="model");
  syncEffort();
  refreshModelMenu?.();
  const above=$("#composer-actions"),aboveKeys=[];
  const recovery=$("#recovery"),recoveryKeys=[];
  if(state.cards[0]?.kind!=="welcome"&&state.buttons.primary?.text!=="先输入任务"&&state.buttons.primary?.enabled&&!state.locked&&!state.cards.some(c=>c.kind==="question")&&!state.buttons.confirm_requirements&&!state.buttons.confirm_plan&&!state.buttons.copy&&!state.buttons.continue_stage)(state.buttons.primary.text==="继续整理回答"?aboveKeys:recoveryKeys).push("primary");
  const aboveSignature=JSON.stringify(aboveKeys.map(key=>[key,state.buttons[key]]));
  if(above.dataset.signature!==aboveSignature){above.dataset.signature=aboveSignature;above.replaceChildren();if(aboveKeys.length)actions(above,aboveKeys);}
  const recoverySignature=JSON.stringify(recoveryKeys.map(key=>[key,state.buttons[key]]));
  if(recovery.dataset.signature!==recoverySignature){recovery.dataset.signature=recoverySignature;recovery.replaceChildren();if(recoveryKeys.length)actions(recovery,recoveryKeys);}
  if(popupKind==="review")renderReview();
  updateEnabled();if(priorFocus?.key&&!priorFocus.element.isConnected&&!restored)restoreFocus(priorFocus);
  const stageChanged=state.navigation&&priorStage!==state.navigation.stage;
  if(answersRestored)requestAnimationFrame(()=>{
    const input=timeline.querySelector(".answer-input");
    if(input){viewport.scrollTop+=input.getBoundingClientRect().top-viewport.getBoundingClientRect().top-100;input.focus({preventScroll:true});}
  });
  else if(stageChanged&&rendered.has("navigation"))requestAnimationFrame(()=>{
    const target=rendered.get("navigation")?.el;
    if(target?.isConnected){viewport.scrollTop+=target.getBoundingClientRect().top-viewport.getBoundingClientRect().top-12;
      const focus=target.querySelector("button:not(:disabled)");focus?.focus({preventScroll:true});}
  });
  else if(restored)requestAnimationFrame(()=>{viewport.scrollTop=state.drafts?.scroll||0;});else if(follow)requestAnimationFrame(()=>{viewport.scrollTop=viewport.scrollHeight;});
  window.promptsmithStartup?.update(state);
  window.promptsmithTutorial?.update(state);
}
function providerImage(name) {const src=state?.icons?.[state.theme]?.[name];if(!src)return null;const img=node("img","provider"+(name==="DeepSeek"?" deepseek":""));img.src=src;img.alt=name;return img;}
function captureFocus(element=document.activeElement){
  return {element,id:element?.id,history:element?.closest(".history-row")?.dataset.id,
    more:element?.classList.contains("history-more"),key:element?.dataset.focusKey};
}
function restoreFocus(target){
  if(!target)return;
  let element=target.element?.isConnected?target.element:null;
  if(!element&&target.id)element=document.getElementById(target.id);
  if(!element&&target.history)element=document.querySelector(`.history-row[data-id="${CSS.escape(target.history)}"] ${target.more?".history-more":".history-select"}`);
  if(!element&&target.key)element=document.querySelector(`[data-focus-key="${CSS.escape(target.key)}"]`);
  (element||$("#history-search"))?.focus({preventScroll:true});
}
function closePopup(immediate=false) {
  refreshModelMenu=null;
  popupObserver?.disconnect();popupObserver=null;
  if(popupLayoutFrame!==null)cancelAnimationFrame(popupLayoutFrame);popupLayoutFrame=null;popupAnchor=null;
  $("#model-button").classList.remove("picker-open");
  for(const control of document.querySelectorAll('.history-more[aria-expanded="true"]'))control.setAttribute("aria-expanded","false");
  const previous=popup,target=popupReturnFocus;popupReturnFocus=null;popup=null;popupKind=null;reviewKind=null;reviewSignature=null;if(!previous)return;
  if(target?.element)target.element.setAttribute("aria-expanded","false");
  const returnNeeded=previous.contains(document.activeElement)||document.activeElement===document.body;
  previous.inert=true;
  if(immediate)previous.remove();else {previous.classList.add("closing");setTimeout(()=>previous.remove(),230);}
  if(returnNeeded)restoreFocus(target);
  diagnostic("debug","popup closed",previous.getAttribute("aria-label"));
}
function makePopup(kind,anchor,cls="") {
  const trigger=anchor||document.activeElement;closePopup(true);
  popupReturnFocus=captureFocus(trigger);trigger?.setAttribute("aria-expanded","true");
  popup=node("section","popup "+cls);popupKind=kind;popup.setAttribute("role","dialog");
  const labels={model:"选择模型",depth:"整理深度",category:"任务类型",file:"文件",history:"会话操作"};
  popup.setAttribute("aria-label",labels[kind]||"任务面板");
  if(["depth","category","file","history"].includes(kind)){
    popup.setAttribute("role","menu");
    // Children are added synchronously by the caller before this observer runs.
    const menu=popup;new MutationObserver((_,observer)=>{for(const [index,item] of [...menu.querySelectorAll("button")].entries()){item.setAttribute("role","menuitem");item.tabIndex=index===0?0:-1;}observer.disconnect();}).observe(menu,{childList:true});
    menu.addEventListener("focusin",event=>{for(const item of menu.querySelectorAll("button"))item.tabIndex=item===event.target?0:-1;});
    menu.addEventListener("keydown",event=>{
      const items=[...menu.querySelectorAll("button:not(:disabled)")],current=items.indexOf(document.activeElement);let index=null;
      if(event.key==="ArrowDown")index=(current+1)%items.length;
      else if(event.key==="ArrowUp")index=(current+items.length-1)%items.length;
      else if(event.key==="Home")index=0;else if(event.key==="End")index=items.length-1;
      if(index!==null){event.preventDefault();event.stopPropagation();items[index]?.focus();}
      if(event.key==="Tab"){restoreFocus(popupReturnFocus);closePopup();}
    });
  }
  $("#popup-layer").append(popup);
  popupAnchor=anchor;
  popupObserver=new ResizeObserver(schedulePopupLayout);popupObserver.observe(popup);
  const opened=popup;requestAnimationFrame(()=>{if(popup===opened&&!opened.contains(document.activeElement))opened.querySelector("input,button,select,[tabindex]")?.focus({preventScroll:true});});
  diagnostic("debug","popup opened",kind);
  schedulePopupLayout();return popup;
}
function schedulePopupLayout(){
  if(popupLayoutFrame!==null)return;
  popupLayoutFrame=requestAnimationFrame(()=>{popupLayoutFrame=null;positionPopup();});
}
function positionPopup(){
  if(!popup)return;
  const margin=12,available=Math.max(1,innerHeight-margin*2);
  popup.style.maxHeight=available+"px";
  const width=popup.offsetWidth,height=popup.offsetHeight,rect=popupAnchor?.getBoundingClientRect();
  const above=rect&&rect.top>innerHeight/2;
  const left=rect?rect.left:innerWidth-width-24;
  const top=rect?(above?rect.top-height-10:rect.bottom+8):68;
  popup.style.right="auto";popup.style.bottom="auto";
  popup.style.left=Math.max(margin,Math.min(innerWidth-width-margin,left))+"px";
  popup.style.top=Math.max(margin,Math.min(innerHeight-height-margin,top))+"px";
  popup.style.transformOrigin=above?"bottom left":"top right";
}
window.addEventListener("resize",schedulePopupLayout);
function openReview(kind) {
  if(reviewKind===kind){closePopup();return;}
  makePopup("review",null,"review-panel");reviewKind=kind;
  popup.setAttribute("aria-label",{summary:"当前任务摘要",result:"附注"}[kind]);
  renderReview();command("panel",{kind});
}
function renderReview() {
  if(!popup||!state)return;
  const signature=JSON.stringify([reviewKind,state.requirement_rows,state.requirement_selection,state.buttons,state.summary,state.cards.find(c=>c.kind==="plan"),state.requirement_reason,state.conflicts]);
  if(signature===reviewSignature)return;reviewSignature=signature;
  const box=popup;const scroll=box.scrollTop,focused=box.contains(document.activeElement)?captureFocus():null;
  const openSections=new Set([...box.querySelectorAll("details[open]")].map(d=>d.querySelector("summary").textContent));
  box.replaceChildren();const bar=node("div","popup-title",{summary:"当前任务摘要",result:"附注"}[reviewKind]);
  const close=button("",()=>closePopup(),"popup-close");close.dataset.focusKey="review-close";close.append(icon("close"));close.setAttribute("aria-label","关闭面板");bar.append(close);box.append(bar);
  if(reviewKind==="summary") {const reading=node("div","reading");markdown(reading,state.summary);box.append(reading);}

  if(reviewKind==="result") {
    actions(box,["add_final_note"],true);
    diagnostic("debug","final notes panel rendered","tone_control=false");
  }
  for(const d of box.querySelectorAll("details"))d.open=openSections.has(d.querySelector("summary").textContent);box.scrollTop=scroll;updateEnabled();
  if(focused){if(focused.key||focused.id)restoreFocus(focused);else close.focus({preventScroll:true});}
}
function choiceMenu(kind,anchor) {
  if(popupKind===kind){closePopup();return;}if(!state||state.locked)return;
  const box=makePopup(kind,anchor);box.style.width="360px";
  const items=kind==="category"?state.categories.map(x=>[x,x]):Object.entries(state.depths),selected=state[kind];
  for(const [value,label] of items){const b=button("",async()=>{if(await command(kind,{value}))closePopup();},"menu-row");b.append(icon("file"),node("span","",label));if(value===selected){const check=icon("check");check.classList.add("check");b.append(check);}box.append(b);}
}
function modelPicker() {
  if(popupKind==="model"){closePopup();return;}if(!state||state.locked)return;
  const box=makePopup("model",$("#model-button"),"picker"),input=node("input"),search=node("div","picker-search"),clear=button("",()=>{input.value="";renderModels();input.focus();},"clear-search");
  input.placeholder="搜索模型…";input.setAttribute("aria-label","搜索模型");input.autocomplete="off";input.spellcheck=false;clear.append(icon("close"));clear.setAttribute("aria-label","清空搜索");search.append(icon("search"),input,clear);
  $("#model-button").classList.add("picker-open");
  const layout=node("div","picker-layout"),providers=node("div","providers"),models=node("div","models"),providerIndicator=node("span","provider-indicator"),column=node("div","picker-column"),modelSurface=node("div","model-surface"),modelHeading=node("div","model-heading");
  providerIndicator.setAttribute("aria-hidden","true");providers.setAttribute("role","tablist");providers.setAttribute("aria-label","模型供应商");providers.setAttribute("aria-orientation","vertical");providers.append(providerIndicator);
  modelSurface.append(modelHeading,models);column.append(search,modelSurface);layout.append(providers,column);box.append(layout);
  provider=state.models.find(m=>m.id===state.model&&(!m.service_provider||m.service_provider===state.active_service))?.provider||state.models[0]?.provider||"OpenAI";
  const efforts=node("div","efforts"),label=node("div","thinking-label");label.append(effortMeter(),node("span","","思考强度"));efforts.append(label);const choices=node("div","thinking-track"),indicator=node("span","thinking-indicator");
  choices.setAttribute("role","radiogroup");choices.setAttribute("aria-label","思考强度");indicator.setAttribute("aria-hidden","true");choices.append(indicator);
  const levels=["low","medium","high","max"];
  for(const value of levels){const b=button(value[0].toUpperCase()+value.slice(1),()=>choosePreference("effort",{value}));b.dataset.effort=value;b.setAttribute("role","radio");
    b.addEventListener("keydown",event=>{const current=levels.indexOf(optimisticEffort||state.effort);let index=null;if(["ArrowRight","ArrowDown"].includes(event.key))index=(current+1)%4;else if(["ArrowLeft","ArrowUp"].includes(event.key))index=(current+3)%4;else if(event.key==="Home")index=0;else if(event.key==="End")index=3;if(index!==null){event.preventDefault();choosePreference("effort",{value:levels[index]});choices.querySelector(`[data-effort="${levels[index]}"]`).focus();}});
    choices.append(b);}efforts.append(choices);column.append(efforts);syncEffort();
  function renderModels(){models.replaceChildren();for(const b of providers.querySelectorAll("button")){const selected=b.dataset.provider===provider;b.classList.toggle("selected",selected);b.setAttribute("aria-selected",String(selected));b.tabIndex=selected?0:-1;}
    const selected=providers.querySelector("button.selected");if(selected){providerIndicator.style.height=selected.offsetHeight+"px";providerIndicator.style.transform=`translateY(${selected.offsetTop}px)`;}
    models.classList.remove("provider-enter");requestAnimationFrame(()=>models.classList.add("provider-enter"));
    const query=input.value.trim().toLocaleLowerCase();const list=state.models.filter(m=>(query||m.provider===provider)&&(!query||(m.name+" "+m.description).toLocaleLowerCase().includes(query)));
    modelHeading.textContent=query?`${list.length} 个结果`:provider;clear.hidden=!query;
    for(const m of list){const selected=m.id===state.model&&(!m.service_provider||m.service_provider===state.active_service);
      const b=button("",()=>{choosePreference("model",{id:m.id,...(m.service_provider?{service:m.service_provider}:{})});},"model-row"+(selected?" selected":""));b.dataset.model=m.id;b.dataset.service=m.service_provider||"";const content=node("div","model-content"),name=node("div","model-name");name.append(node("strong","",m.name));content.append(name,node("small","",m.description));
      if(m.service_provider&&m.service_provider!==m.provider)content.append(node("small","","接口："+m.service_provider));
      const tags=node("div","capabilities");for(const [name,label] of [...(m.reasoning!==false?[["brain","推理"]]:[]),...(m.image?[["image","图像"]]:[])]){const tag=node("span","capability "+name);tag.title=label;tag.setAttribute("aria-label",label);tag.append(icon(name));tags.append(tag);}b.append(content,tags);if(selected){const check=icon("check");check.classList.add("check");name.append(check);}models.append(b);}
    if(!list.length)models.append(node("p","notice",state.models.length?"没有匹配的模型。":"请先在设置中为供应商获取模型列表。"));
  }
  let directorySignature=null;
  function refreshDirectory(){
    const signature=JSON.stringify([state.models,state.active_service,state.theme]);if(signature===directorySignature)return;directorySignature=signature;
    for(const b of providers.querySelectorAll("button"))b.remove();
    const providerNames=[...new Set(state.models.map(m=>m.provider))];
    if(!providerNames.includes(provider))provider=providerNames[0]||"OpenAI";
  for(const [index,name] of providerNames.entries()){const b=button("",()=>{provider=name;input.value="";renderModels();});b.dataset.provider=name;b.title=name;b.setAttribute("aria-label",name);b.setAttribute("role","tab");
    b.addEventListener("keydown",event=>{let next=null;if(event.key==="ArrowDown")next=(index+1)%providerNames.length;else if(event.key==="ArrowUp")next=(index+providerNames.length-1)%providerNames.length;else if(event.key==="Home")next=0;else if(event.key==="End")next=providerNames.length-1;if(next!==null){event.preventDefault();provider=providerNames[next];input.value="";renderModels();providers.querySelectorAll("button")[next].focus();}});
    const img=providerImage(name);if(img)b.append(img);else b.textContent=name;providers.append(b);}
    renderModels();
  }
  refreshModelMenu=refreshDirectory;refreshDirectory();input.addEventListener("input",renderModels);
  input.addEventListener("keydown",event=>{if(event.isComposing||event.keyCode===229)return;if(event.key==="ArrowDown"){event.preventDefault();models.querySelector("button")?.focus();}else if(event.key==="Enter"){event.preventDefault();models.querySelector("button")?.click();}else if(event.key==="Escape"&&input.value){event.stopPropagation();input.value="";renderModels();}});
  renderModels();input.focus();
}
for(const b of document.querySelectorAll("[data-panel]"))b.addEventListener("click",()=>openReview(b.dataset.panel));
$("#settings").addEventListener("click",()=>{closePopup();command("settings");});
$("#depth-button").addEventListener("click",()=>choiceMenu("depth",$("#depth-button")));
$("#category-button").addEventListener("click",()=>choiceMenu("category",$("#category-button")));
$("#model-button").addEventListener("click",modelPicker);
$("#file-button").addEventListener("click",()=>{if(popupKind==="file"){closePopup();return;}const box=makePopup("file",$("#file-button"));for(const [action,label] of [["new","新建对话"],["open","打开会话…"],["save","保存会话"],["save_as","另存为…"]])box.append(button(label,()=>{closePopup();command(action);},"menu-row"));});
document.addEventListener("pointerdown",event=>{if(popup&&!popup.contains(event.target)&&!event.target.closest("header button,#model-button,#category-button,#depth-button"))closePopup();});
document.addEventListener("keydown",event=>{if(event.key==="Escape")closePopup();if(event.ctrlKey&&event.key.toLowerCase()==="s"){event.preventDefault();command(event.shiftKey?"save_as":"save");}});
let polling=false;
async function poll() {
  if(polling||!window.pywebview?.api)return;polling=true;
  try {const result=await window.pywebview.api.snapshot(version);window.promptsmithNotifications.sync("workspace:connection","");if(result?.state){version=result.version;applySnapshot(result.state);}}
  catch(error){window.promptsmithNotifications.sync("workspace:connection","页面同步暂未完成，程序会继续尝试。",{variant:"error"});diagnostic("error","workspace synchronization failed",error?.stack||String(error));}finally{polling=false;}
}
function diagnostic(level,event,detail){window.pywebview?.api?.diagnostic?.(level,event,detail).catch(()=>{});}
window.addEventListener("error",e=>{toast("页面处理出现错误，请重试。","error",{key:"workspace:exception"});diagnostic("error","uncaught exception",e.error?.stack||e.message);});
window.addEventListener("unhandledrejection",e=>{toast("页面操作未完成，请重试。","error",{key:"workspace:exception"});diagnostic("error","unhandled rejection",e.reason?.stack||String(e.reason));});
window.addEventListener("pywebviewready",()=>{
  poll();setInterval(poll,100);diagnostic("info","workspace ready","Chromium presentation and requestAnimationFrame animation enabled");
  if(typeof PerformanceObserver!=="undefined") {let last=0;
    const observer=new PerformanceObserver(list=>{const longest=Math.max(...list.getEntries().map(e=>e.duration));if(longest>80&&performance.now()-last>5000){last=performance.now();diagnostic("warn","main thread stall",`duration_ms=${longest.toFixed(1)}`);}});
    observer.observe({type:"longtask",buffered:false});
  }
});
// The narrow test seam uses exactly the same renderer and real DOM interactions.
window.promptsmithView={applySnapshot,TraceView,poll};
