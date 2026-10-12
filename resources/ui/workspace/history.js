"use strict";
// History metadata is independent of SessionState; all business progress lives in Python.
(()=>{
  let catalogue=null,signature=null,dialog=null,dialogKind=null,returnFocus=null,lastError=null;
  let draftTimer=null,draftSequence=0,draftChain=Promise.resolve();
  let collapsed=innerWidth<1000;
  try{const saved=localStorage.getItem("promptsmith.sidebar.collapsed");if(saved!==null)collapsed=saved==="true";}catch{}
  const sidebar=$("#sidebar"),list=$("#history-list"),toggle=$("#sidebar-toggle");
  const expanded=sidebar.querySelector(".sidebar-expanded"),dock=sidebar.querySelector(".sidebar-dock"),dockToggle=$("#sidebar-dock-toggle");
  $("#history-search").append(icon("search"));toggle.append(icon("sidebar"));$("#new-chat .new-chat-icon").append(icon("newchat"));
  dockToggle.append(icon("sidebar"));$("#sidebar-dock-search").append(icon("search"));$("#sidebar-dock-new").append(icon("newchat"));
  function setCollapsed(value){
    closePopup(true);
    const content=sidebar.querySelector(".sidebar-content");
    collapsed=value;document.body.classList.toggle("sidebar-collapsed",value);
    const outgoing=value?expanded:dock,incoming=value?dock:expanded;
    outgoing.inert=true;outgoing.setAttribute("aria-hidden","true");incoming.inert=false;incoming.removeAttribute("aria-hidden");content.inert=value;
    if(outgoing.contains(document.activeElement)||(value&&content.contains(document.activeElement)))(value?dockToggle:toggle).focus();
    for(const control of [toggle,dockToggle])control.setAttribute("aria-expanded",String(!value));
    try{localStorage.setItem("promptsmith.sidebar.collapsed",String(value));}catch{}
    diagnostic("debug","sidebar visibility",`expanded=${!value} motion=horizontal-header-fade reduced=${matchMedia("(prefers-reduced-motion: reduce)").matches}`);
  }
  setCollapsed(collapsed);
  toggle.addEventListener("click",()=>setCollapsed(!collapsed));
  dockToggle.addEventListener("click",()=>setCollapsed(!collapsed));
  $("#new-chat").title="开启新对话";
  for(const control of [$("#new-chat"),$("#sidebar-dock-new")])control.addEventListener("click",async()=>{closeDialog();if(await command("new"))message.focus();});

  function flushDrafts(){
    clearTimeout(draftTimer);draftTimer=null;
    if(!state||!catalogue||!window.pywebview?.api)return Promise.resolve();
    const pending=new Set(state.cards.filter(c=>c.kind==="question").map(c=>c.question.question_id));
    const payload={session:state.session,sequence:++draftSequence,message:message.value,answers:Object.fromEntries([...drafts].filter(([id])=>pending.has(id))),scroll:viewport.scrollTop};
    const stamp=state.stamp;
    draftChain=draftChain.catch(()=>{}).then(async()=>{
      const result=await window.pywebview.api.dispatch("drafts",payload,stamp);
      if(!result.ok)throw new Error(result.error||"草稿保存失败");
    });
    return draftChain;
  }
  function scheduleDraft(){clearTimeout(draftTimer);draftTimer=setTimeout(()=>flushDrafts().catch(error=>diagnostic("error","history draft failed",error.stack||String(error))),220);}
  viewport.addEventListener("scroll",scheduleDraft,{passive:true});
  window.addEventListener("blur",()=>{flushDrafts().catch(error=>diagnostic("error","history blur draft failed",String(error)));});

  function row(entry){
    const el=node("div","history-row"+(entry.id===catalogue.active?" active":""));el.dataset.id=entry.id;
    const select=button(entry.title,async()=>{closeDialog();if(await command("history_open",{id:entry.id}))message.focus();},"history-select");
    select.title=entry.title+"\n"+entry.stage;select.setAttribute("aria-current",entry.id===catalogue.active?"true":"false");
    if(entry.unavailable)select.title+="\n记录暂时无法读取，原文件保留";
    const more=button("",()=>menu(entry,more),"history-more");more.append(icon("more"));more.setAttribute("aria-label",entry.title+"的会话操作");more.setAttribute("aria-haspopup","menu");more.setAttribute("aria-expanded","false");
    el.append(select,more);return el;
  }
  function menu(entry,anchor){
    const box=makePopup("history",anchor,"history-menu");box.setAttribute("role","menu");anchor.setAttribute("aria-expanded","true");
    const rect=anchor.getBoundingClientRect();box.style.bottom="";box.style.top=Math.max(12,Math.min(innerHeight-170,rect.bottom+6))+"px";
    for(const [glyph,label,handler,danger] of [
      ["pencil","重命名",()=>rename(entry)],
      ["pin",entry.pinned?"取消置顶":"置顶",()=>command("history_pin",{id:entry.id,pinned:!entry.pinned})],
      ["trash","删除",()=>remove(entry),true]
    ]){const b=button("",()=>{anchor.setAttribute("aria-expanded","false");closePopup(true);handler();},danger?"danger":"");b.append(icon(glyph),node("span","",label));b.setAttribute("role","menuitem");box.append(b);}
    box.firstElementChild.focus();
  }
  function update(next,restored=false){
    catalogue=next;if(!catalogue){list.replaceChildren(node("p","history-empty","历史会话正在准备…"));return;}
    const key=JSON.stringify(next);if(key===signature)return;signature=key;
    if(next.error&&next.error!==lastError)toast(next.error);lastError=next.error||null;
    const scroll=list.scrollTop,focusedId=document.activeElement?.closest(".history-row")?.dataset.id;
    list.replaceChildren();
    for(const group of ["置顶","今天","昨天","七天内","30天内","更早"]){const entries=next.entries.filter(r=>r.group===group);if(!entries.length)continue;const section=node("section","history-group");section.append(node("h2","",group));for(const entry of entries)section.append(row(entry));list.append(section);}
    if(!next.entries.length)list.append(node("p","history-empty","你的对话会自动保存在这里。"));
    list.scrollTop=scroll;if(focusedId&&!restored)list.querySelector(`[data-id="${focusedId}"] .history-select`)?.focus({preventScroll:true});
    const status=$("#history-status");status.hidden=!next.error;status.replaceChildren();if(next.error){status.append(node("span","",next.error),button("重试保存",()=>command("history_retry")));}
    if(dialogKind==="search")renderSearch();
  }

  function closeDialog(){if(!dialog)return;const previous=dialog;dialog=null;dialogKind=null;previous.remove();restoreFocus(returnFocus);returnFocus=null;diagnostic("debug","history dialog closed","");}
  function makeDialog(kind,title){
    closePopup(true);closeDialog();returnFocus=captureFocus();dialogKind=kind;
    dialog=node("div","history-overlay");const box=node("section","history-dialog");box.setAttribute("role","dialog");box.setAttribute("aria-modal","true");box.setAttribute("aria-label",title);
    const bar=node("div","popup-title",title),close=button("",closeDialog,"popup-close");close.append(icon("close"));close.setAttribute("aria-label","关闭");bar.append(close);box.append(bar);dialog.append(box);document.body.append(dialog);
    dialog.addEventListener("pointerdown",event=>{if(event.target===dialog)closeDialog();});
    dialog.addEventListener("keydown",event=>{if(event.key==="Escape"){event.stopPropagation();closeDialog();}if(event.key==="Tab"){const focusable=[...box.querySelectorAll("input,button")].filter(e=>!e.disabled);if(event.shiftKey&&document.activeElement===focusable[0]){event.preventDefault();focusable.at(-1)?.focus();}else if(!event.shiftKey&&document.activeElement===focusable.at(-1)){event.preventDefault();focusable[0]?.focus();}}});
    return box;
  }
  function errorLine(box){const error=node("div","dialog-error");error.setAttribute("role","alert");box.append(error);return error;}
  function rename(entry){
    const box=makeDialog("rename","重命名会话"),input=node("input");input.value=entry.title;input.maxLength=100;input.setAttribute("aria-label","会话名称");box.append(input);
    const actions=node("div","actions"),cancel=button("取消",closeDialog),save=button("保存",async()=>{const title=input.value.trim();if(!title){error.textContent="请输入会话名称。";input.focus();return;}if(await command("history_rename",{id:entry.id,title}))closeDialog();else error.textContent="名称未保存，请重试，原名称仍然保留。";});
    actions.append(cancel,save);box.append(actions);const error=errorLine(box);sendOnEnter(input,()=>save.click());input.focus();input.select();
  }
  function remove(entry){
    const box=makeDialog("delete","删除会话"),text=node("p","",`确定删除“${entry.title}”吗？本地历史中的工作记录将被删除。`);box.append(text);
    const actions=node("div","actions"),cancel=button("取消",closeDialog),confirm=button("删除",async()=>{if(await command("history_delete",{id:entry.id}))closeDialog();else error.textContent="删除未完成，请重试。";},"danger");actions.append(cancel,confirm);box.append(actions);const error=errorLine(box);cancel.focus();
  }
  function search(){
    if(!catalogue)return;const box=makeDialog("search","搜索历史会话"),input=node("input");input.type="search";input.placeholder="搜索会话名称…";input.setAttribute("aria-label","搜索会话名称");input.id="history-search-input";box.append(input);
    const results=node("div","history-search-results");results.id="history-search-results";box.append(results);input.addEventListener("input",renderSearch);
    input.addEventListener("keydown",event=>{if(event.isComposing||event.keyCode===229)return;if(event.key==="ArrowDown"){event.preventDefault();results.querySelector("button")?.focus();}if(event.key==="Enter"){event.preventDefault();results.querySelector("button")?.click();}});
    renderSearch();input.focus();diagnostic("debug","history search opened","metadata only");
  }
  function renderSearch(){
    const input=$("#history-search-input"),results=$("#history-search-results");if(!input||!results)return;
    const query=input.value.trim().toLocaleLowerCase();const matches=catalogue.entries.filter(r=>r.title.toLocaleLowerCase().includes(query));results.replaceChildren();
    for(const entry of matches){const b=button("",async()=>{if(await command("history_open",{id:entry.id})){closeDialog();message.focus();}});b.append(node("span","",entry.title),node("small","",entry.group+" · "+entry.stage));results.append(b);}
    if(!matches.length)results.append(node("p","history-empty","没有找到匹配的会话。"));
  }
  for(const control of [$("#history-search"),$("#sidebar-dock-search")])control.addEventListener("click",search);
  document.addEventListener("keydown",event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){event.preventDefault();search();}});
  window.promptsmithHistory={update,flushDrafts,scheduleDraft,setCollapsed};
})();
