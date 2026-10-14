"use strict";
// A local presentation gate. Tutorial completion remains a saved backend state.
window.promptsmithStartup=(()=>{
  const hero=document.querySelector("#startup-hero"),loader=hero.querySelector(".startup-loader"),start=hero.querySelector(".startup-start");
  const wordmark=hero.querySelector(".startup-wordmark");
  const surfaces=["#sidebar","#workspace-shell","#popup-layer"].map(selector=>document.querySelector(selector));
  const reduced=matchMedia("(prefers-reduced-motion: reduce)");
  const shownAt=performance.now();
  let snapshot=null,ready=false,entering=false,entered=false,delay=null,shader=null,burst=null,hovered=false,assetReady=false;
  let wordmarkError=null,assetReported=false;
  const metal=document.createElement("div");metal.className="startup-metal";metal.setAttribute("aria-hidden","true");start.prepend(metal);
  function speed(value){shader?.setSpeed(reduced.matches?0:value);}
  function release(){
    clearTimeout(delay);clearTimeout(burst);delay=burst=null;
    shader?.dispose();shader=null;metal.replaceChildren();
  }
  function mountMetal(){
    try{
      if(!window.intextLiquidMetal)throw new Error("Local liquid metal resource is unavailable");
      shader=window.intextLiquidMetal.mount(metal,reduced.matches?0:0.6);
      diagnostic("debug","启动按钮动画已就绪","engine=WebGL2");
    }catch(error){
      metal.replaceChildren();diagnostic("warn","启动按钮使用静态银边",error?.stack||String(error));
    }
  }
  function update(next){
    snapshot=next;
    if(entered||entering||ready)return;
    if(!next.stamp||!assetReady)return;
    if(!assetReported){
      diagnostic(wordmarkError?"warn":"debug",wordmarkError?"启动标题使用文字回退":"启动标题已就绪",wordmarkError||"source=local-svg");
      assetReported=true;
    }
    // Legacy snapshots have no tutorial contract and must not start a tutorial.
    const wait=next.tutorial_status&&!reduced.matches?Math.max(0,800-(performance.now()-shownAt)):0;
    if(delay===null)delay=setTimeout(finishLoading,wait);
  }
  function finishLoading(){
    delay=null;if(entered||entering||ready||!snapshot)return;
    ready=true;loader.hidden=true;
    diagnostic("info","启动页加载完成","tutorial_status="+(snapshot.tutorial_status||"legacy"));
    if(snapshot.tutorial_status==="not_started"){
      start.hidden=false;mountMetal();start.focus({preventScroll:true});
      diagnostic("debug","启动页等待开始","tutorial_pending=true");
    }else enter(false);
  }
  async function enter(beginTutorial){
    if(!ready||entered||entering)return;
    entering=true;start.disabled=true;hero.classList.add("leaving");
    if(!reduced.matches)await new Promise(resolve=>setTimeout(resolve,260));
    release();hero.hidden=true;entered=true;entering=false;
    document.body.classList.remove("startup-active");
    for(const surface of surfaces){surface.inert=false;surface.removeAttribute("aria-hidden");}
    diagnostic("info","进入工作区","tutorial="+beginTutorial);
    if(beginTutorial)window.promptsmithTutorial?.open("hero");
    else document.querySelector("#message")?.focus({preventScroll:true});
  }
  start.addEventListener("pointerenter",()=>{hovered=true;speed(1);});
  start.addEventListener("pointerleave",()=>{hovered=false;speed(0.6);});
  start.addEventListener("click",event=>{
    if(entering||entered)return;
    speed(2.4);clearTimeout(burst);burst=setTimeout(()=>speed(hovered?1:0.6),300);
    if(!reduced.matches){
      const rect=start.getBoundingClientRect(),ripple=document.createElement("span");ripple.className="startup-ripple";
      ripple.style.left=(event.detail?event.clientX-rect.left:rect.width/2)+"px";
      ripple.style.top=(event.detail?event.clientY-rect.top:rect.height/2)+"px";
      ripple.addEventListener("animationend",()=>ripple.remove(),{once:true});start.append(ripple);
    }
    enter(snapshot?.tutorial_status==="not_started");
  });
  reduced.addEventListener("change",()=>speed(hovered?1:0.6));
  window.addEventListener("pagehide",release,{once:true});
  document.addEventListener("keydown",event=>{
    if(!entered&&(event.ctrlKey||event.metaKey)&&["s","k"].includes(event.key.toLowerCase())){
      event.preventDefault();event.stopImmediatePropagation();
    }
  },true);
  wordmark.decode().then(()=>{
    assetReady=true;
    if(snapshot)update(snapshot);
  }).catch(error=>{
    wordmarkError=error?.stack||String(error);assetReady=true;
    const title=wordmark.parentElement;title.classList.add("wordmark-fallback");title.textContent="意织 · Intext";
    if(snapshot)update(snapshot);
  });
  return {update,get entered(){return entered;}};
})();
