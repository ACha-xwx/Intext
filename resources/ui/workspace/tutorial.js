"use strict";
// Observe real actions and saved settings; never submit a goal for the user.
window.promptsmithTutorial=(()=>{
  const steps=[
    ["plug","打开模型设置","点击右上角高亮的「设置」。先连接一个模型，之后就能围绕你的目标开始对话。","请先打开设置页。"],
    ["sliders","配置模型服务","在「模型」分类选择服务。填写接口地址和 API Key；自定义服务还要选择模型供应商。修改自动保存，密钥不会显示在教程中。","请填写服务配置和 API Key，等待自动保存。"],
    ["search","获取可用模型","点击高亮的「获取模型」，等模型列表获取成功。已有可用列表时可以直接下一步；获取失败时检查接口和密钥后重试。","请先成功获取一个可用模型列表。"],
    ["brain","选择要使用的模型","展开高亮的「模型 ID」，选择列表中的一个模型。等待修改自动保存，配置可用后再下一步。","请选择可用模型，并等待自动保存完成。"],
    ["newchat","开始你的第一个目标","点击「返回工作区」，在底部输入目标即可开始。例如：「帮我给比赛项目写一份技术文档」。也可以直接点击「完成」，稍后再开始。",""]
  ];
  let dialog=null,track,progress,counter,back,next,closeButton,skipButton,hint,index=0,returnFocus=null;
  let status="not_started",started=false,saving=false,closing=false,targets=[];
  let spotlight=null,holes=null,spotlightFrame=0,targetObserver=null;
  let celebration=null,celebrationTimer=0,celebrationFrame=0;
  const celebrated=new Set();
  const svgNamespace="http://www.w3.org/2000/svg";
  function svgElement(name,attributes={}){
    const element=document.createElementNS(svgNamespace,name);
    for(const [key,value] of Object.entries(attributes))element.setAttribute(key,String(value));
    return element;
  }
  function openSpotlight(){
    spotlight=node("div","tutorial-spotlight");spotlight.setAttribute("popover","manual");spotlight.setAttribute("aria-hidden","true");
    const svg=svgElement("svg"),defs=svgElement("defs"),mask=svgElement("mask",{id:"tutorial-holes",maskUnits:"userSpaceOnUse"});
    holes=svgElement("g");mask.append(svgElement("rect",{width:"100%",height:"100%",fill:"white"}),holes);defs.append(mask);
    svg.append(defs,svgElement("rect",{width:"100%",height:"100%",fill:"black","fill-opacity":.25,mask:"url(#tutorial-holes)"}));
    spotlight.append(svg);document.body.append(spotlight);spotlight.showPopover();
    window.addEventListener("resize",scheduleSpotlight);document.addEventListener("scroll",scheduleSpotlight,true);
    targetObserver=new ResizeObserver(scheduleSpotlight);
  }
  function scheduleSpotlight(){if(spotlight&&!spotlightFrame)spotlightFrame=requestAnimationFrame(drawSpotlight);}
  function drawSpotlight(){
    spotlightFrame=0;if(!spotlight)return;
    const rectangles=[];
    for(const target of targets){
      const box=target.getBoundingClientRect();let left=Math.max(0,box.left-6),top=Math.max(0,box.top-6),right=Math.min(innerWidth,box.right+6),bottom=Math.min(innerHeight,box.bottom+6);
      for(let parent=target.parentElement;parent&&parent!==document.body;parent=parent.parentElement){
        const style=getComputedStyle(parent),bounds=parent.getBoundingClientRect();
        if(/auto|scroll|hidden|clip/.test(style.overflowX)){left=Math.max(left,bounds.left);right=Math.min(right,bounds.right);}
        if(/auto|scroll|hidden|clip/.test(style.overflowY)){top=Math.max(top,bounds.top);bottom=Math.min(bottom,bounds.bottom);}
      }
      if(right>left&&bottom>top)rectangles.push(svgElement("rect",{x:left,y:top,width:right-left,height:bottom-top,rx:10,fill:"black"}));
    }
    holes.replaceChildren(...rectangles);
  }
  function closeSpotlight(){
    window.removeEventListener("resize",scheduleSpotlight);document.removeEventListener("scroll",scheduleSpotlight,true);
    targetObserver?.disconnect();targetObserver=null;cancelAnimationFrame(spotlightFrame);spotlightFrame=0;
    spotlight?.remove();spotlight=null;holes=null;
  }
  function clearCelebration(){
    clearTimeout(celebrationTimer);cancelAnimationFrame(celebrationFrame);celebrationFrame=0;
    celebration?.remove();celebration=null;
  }
  function celebrate(){
    if(index===steps.length-1||celebrated.has(index))return;
    celebrated.add(index);const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
    diagnostic("debug","新手教程步骤完成","step="+(index+1)+" celebration="+!reduced);
    clearCelebration();if(reduced)return;
    const step=index;
    celebrationFrame=requestAnimationFrame(()=>{
      celebrationFrame=0;if(!dialog||closing||index!==step)return;
      const origin=dialog.querySelector('.tutorial-slide[aria-hidden="false"] .tutorial-icon').getBoundingClientRect();
      celebration=node("div","tutorial-celebration");celebration.setAttribute("popover","manual");celebration.setAttribute("aria-hidden","true");
      const colors=["#eab308","#ef4444","#22c55e","#3b82f6","#a855f7"];
      for(let i=0;i<36;i++){
        const particle=node("i"),angle=Math.PI*(.15+.7*(i/35)),distance=70+Math.random()*100;
        particle.style.left=(origin.x+origin.width/2)+"px";particle.style.top=(origin.y+origin.height/2)+"px";
        particle.style.background=colors[i%colors.length];particle.style.setProperty("--dx",Math.cos(angle)*distance+"px");
        particle.style.setProperty("--dy",-Math.sin(angle)*distance+"px");particle.style.setProperty("--spin",(Math.random()-.5)*900+"deg");
        particle.style.animationDuration=(850+Math.random()*350)+"ms";celebration.append(particle);
      }
      document.body.append(celebration);celebration.showPopover();celebrationTimer=setTimeout(clearCelebration,1250);
    });
  }
  function settled(){const settings=window.promptsmithSettings;return !settings?.saving&&!settings?.switching&&!settings?.dirty.size&&(!settings?.keyAction||settings.keyAction==="keep")&&!state?.settings?.busy&&!inFlight;}
  function ready(){
    const settings=state?.settings,connection=settings?.connection;
    if(index===0)return state?.page==="settings";
    if(index===1)return state?.page==="settings"&&settled()&&settings?.has_key&&Boolean(connection?.base_url)&&Boolean(settings.providers[connection?.provider]||connection?.model_provider);
    if(index===2)return state?.page==="settings"&&settled()&&settings?.available_models?.length>0;
    if(index===3)return state?.page==="settings"&&settled()&&settings?.confirmed&&settings.available_models?.includes(connection?.model);
    return true;
  }
  function update(snapshot){
    if(snapshot.tutorial_status)status=snapshot.tutorial_status;
    if(window.promptsmithStartup&&!window.promptsmithStartup.entered)return;
    if(status==="not_started"&&snapshot.tutorial_status&&!started&&!document.querySelector("dialog[open],.history-dialog[aria-modal=true]"))open("first_run");
    if(dialog&&!closing){render();highlight(false);}
  }
  function open(source="settings"){
    if(dialog||document.querySelector("dialog[open],.history-dialog[aria-modal=true]"))return;
    started=true;index=0;celebrated.clear();returnFocus=captureFocus(document.activeElement===document.body?$("#message"):document.activeElement);closePopup(true);
    dialog=node("section","tutorial-dialog");dialog.setAttribute("role","dialog");dialog.setAttribute("aria-label","新手入门");dialog.setAttribute("aria-modal","false");dialog.setAttribute("popover","manual");
    closeButton=button("",()=>dismiss("closed"),"tutorial-close");closeButton.append(icon("close"));closeButton.setAttribute("aria-label","关闭教程");
    const top=node("div","tutorial-header");counter=node("span");top.append(node("span","","新手入门"),counter);
    const bar=node("div","tutorial-progress");bar.setAttribute("role","progressbar");bar.setAttribute("aria-label","教程进度");bar.setAttribute("aria-valuemin","1");bar.setAttribute("aria-valuemax",String(steps.length));progress=node("div");bar.append(progress);
    const clip=node("div","tutorial-clip");track=node("div","tutorial-track");clip.append(track);
    for(const [name,title,description] of steps){const slide=node("section","tutorial-slide"),badge=node("div","tutorial-icon");badge.append(icon(name));slide.append(badge,node("h2","",title),node("p","",description));track.append(slide);}
    hint=node("p","tutorial-hint");hint.setAttribute("role","status");
    back=button("上一步",()=>move(-1));next=button("下一步",()=>index===steps.length-1?dismiss("completed"):move(1),"tutorial-next");
    const controls=node("div","tutorial-controls");controls.append(back,next);
    skipButton=button("跳过教程",()=>dismiss("skipped"),"tutorial-skip");
    dialog.append(closeButton,top,bar,clip,hint,controls,skipButton);document.body.append(dialog);document.body.classList.add("tutorial-active");
    dialog.addEventListener("keydown",event=>{if(event.key==="Escape"){event.preventDefault();dismiss("closed");}});
    openSpotlight();render();dialog.showPopover();highlight(true);diagnostic("info","打开新手教程","source="+source);
  }
  function move(delta){
    if(saving||closing||delta>0&&!ready())return;
    index=Math.max(0,Math.min(steps.length-1,index+delta));
    if(index>0&&index<steps.length-1&&window.promptsmithSettings?.open&&window.promptsmithSettings.category!=="模型")window.promptsmithSettings.selectCategory("模型");
    render();highlight(true);
    diagnostic("debug","新手教程步骤切换","step="+(index+1));
  }
  function render(){
    const complete=Boolean(ready());counter.textContent=`第 ${index+1} 步，共 ${steps.length} 步`;
    track.style.transform=`translateX(-${index*100}%)`;progress.style.width=((index+1)/steps.length*100)+"%";
    progress.parentElement.setAttribute("aria-valuenow",String(index+1));progress.parentElement.setAttribute("aria-valuetext",counter.textContent);
    for(const [i,slide] of [...track.children].entries()){slide.inert=i!==index;slide.setAttribute("aria-hidden",String(i!==index));}
    hint.textContent=complete?"":steps[index][3];hint.hidden=complete;if(complete&&!closing)celebrate();
    back.disabled=index===0||saving||closing;next.disabled=!complete||saving||closing;closeButton.disabled=saving||closing;skipButton.disabled=saving||closing;skipButton.hidden=index!==0;
    const label=index===steps.length-1?"完成":"下一步";
    if(next.dataset.label!==label){next.dataset.label=label;next.replaceChildren();if(index===steps.length-1)next.append(icon("check"));next.append(document.createTextNode(label));}
  }
  function highlight(focus){
    for(const target of targets)target.classList.remove("tutorial-target");
    const selectors=["#settings","#settings-field-connection-provider,#settings-field-connection-model-provider,#settings-field-connection-base-url,#settings-key",".settings-model-actions button:first-child","#settings-field-connection-model",state?.page==="settings"?".settings-heading button":"#message,#send"];
    targets=[...document.querySelectorAll(selectors[index])].filter(e=>e.getClientRects().length);
    targetObserver?.disconnect();for(const target of targets)targetObserver?.observe(target);
    for(const target of targets)target.classList.add("tutorial-target");
    if(focus){const target=targets.find(e=>!e.disabled);target?.scrollIntoView({block:"center",behavior:"instant"});target?.focus({preventScroll:true});}
    scheduleSpotlight();
  }
  async function dismiss(reason){
    if(!dialog||saving||closing||reason==="completed"&&!ready()||reason==="skipped"&&index!==0)return;
    if(reason!=="closed"){
      saving=true;render();
      try{
        const result=await window.pywebview.api.dispatch(reason==="completed"?"tutorial_finish":"tutorial_skip",{},state.stamp);
        if(!result.ok)throw new Error(result.error||"保存教程状态失败");status=reason;
      }catch(error){toast("教程状态未能保存，请再试一次。","error",{key:"tutorial:save"});diagnostic("error","教程状态保存失败",error?.stack||String(error));saving=false;render();return;}
      saving=false;
    }
    closing=true;render();dialog.classList.add("closing");
    if(!matchMedia("(prefers-reduced-motion: reduce)").matches)await new Promise(resolve=>setTimeout(resolve,180));
    dialog.hidePopover();dialog.remove();dialog=null;closing=false;clearCelebration();closeSpotlight();document.body.classList.remove("tutorial-active");
    for(const target of targets)target.classList.remove("tutorial-target");targets=[];
    restoreFocus(returnFocus);returnFocus=null;diagnostic("info","关闭新手教程","reason="+reason);
  }
  document.addEventListener("promptsmith-settings-state-changed",()=>{
    if(dialog&&!closing){render();highlight(false);}
  });
  return {update,open};
})();
