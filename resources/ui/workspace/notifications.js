"use strict";
// Shared, text-only user feedback. Runtime log records are never toast sources.
window.promptsmithNotifications=(()=>{
  const region=document.createElement("section");region.id="notifications";
  region.className="notification-region";region.setAttribute("aria-label","消息通知");
  region.setAttribute("popover","manual");document.body.append(region);
  const cards=new Map(),observed=new Map(),dismissTimers=new Map(),startedAt=new WeakMap(),moving=new WeakMap();let sequence=0,durationMs=5000;
  function configure(seconds){const value=Number(seconds);durationMs=Number.isFinite(value)&&value>=1&&value<=30?value*1000:5000;}
  const variants={success:{title:"操作成功",paths:["m9 12 2 2 4-4"],circle:true},
    info:{title:"消息提示",paths:["M12 8h.01","M12 12v4"],circle:true},
    warning:{title:"请注意",paths:["m10.29 3.86-8.48 14.14A2 2 0 0 0 3.52 21h16.96a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0","M12 9v4","M12 17h.01"]},
    error:{title:"操作未完成",paths:["M12 8v4","M12 16h.01"],circle:true}};
  function glyph(name){
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    for(const [key,value] of Object.entries({viewBox:"0 0 24 24",fill:"none",stroke:"currentColor","stroke-width":"2","stroke-linecap":"round","stroke-linejoin":"round","aria-hidden":"true"}))svg.setAttribute(key,value);
    const spec=variants[name];if(spec?.circle){const circle=document.createElementNS(svg.namespaceURI,"circle");circle.setAttribute("cx","12");circle.setAttribute("cy","12");circle.setAttribute("r","10");svg.append(circle);}
    for(const d of spec?.paths||["M18 6 6 18","m6 6 12 12"]){const p=document.createElementNS(svg.namespaceURI,"path");p.setAttribute("d",d);svg.append(p);}return svg;
  }
  function diagnostic(event,detail){window.pywebview?.api?.diagnostic?.("debug","notification "+event,detail).catch(()=>{});}
  function host(){
    // A modal makes nodes outside it inert. Mount the notification popover
    // inside the current dialog so its close/retry controls stay operable.
    const dialogs=[...document.querySelectorAll("dialog[open],.history-dialog[aria-modal=true]")],parent=dialogs.at(-1)||document.body;
    let relocated=false;
    if(region.parentElement!==parent){if(region.matches(":popover-open"))region.hidePopover();parent.append(region);relocated=true;}
    if(cards.size&&region.showPopover&&!region.matches(":popover-open")){region.showPopover();relocated=true;}
    // Reparenting a popover restarts CSS animations. Continue the elapsed
    // countdown so opening/closing a dialog cannot refill its progress bar.
    if(relocated)for(const card of cards.values())for(const animation of card.querySelector(".notification-countdown").getAnimations())
      animation.currentTime=Math.min(Number(card.dataset.durationMs),performance.now()-startedAt.get(card));
  }
  function remove(key,animate=true,reason="removed"){
    const card=cards.get(key);if(!card)return;
    clearTimeout(dismissTimers.get(key));dismissTimers.delete(key);
    const focus=card.contains(document.activeElement);
    cards.delete(key);card.inert=true;card.setAttribute("aria-hidden","true");
    if(focus){
      const modal=region.closest("dialog[open],.history-dialog[aria-modal=true]");
      const targets=[...[...cards.values()].reverse().map(e=>e.querySelector(".notification-close")),
        ...(modal?.querySelectorAll("input:not(:disabled),textarea:not(:disabled),button:not(:disabled)")||[]),
        ...document.querySelectorAll("#message,#copy")];
      targets.find(e=>e?.getClientRects().length&&!e.closest("[inert]"))?.focus({preventScroll:true});
    }
    const finish=()=>{
      // Measure the current visual positions, including unfinished shifts,
      // then close the layout gap and animate only the remaining transforms.
      const positions=[...cards.values()].map(e=>({card:e,top:e.getBoundingClientRect().top}));
      for(const item of positions)moving.get(item.card)?.cancel();
      card.remove();
      if(!cards.size&&region.matches(":popover-open"))region.hidePopover();
      if(matchMedia("(prefers-reduced-motion: reduce)").matches)return;
      const shifts=positions.map(item=>({...item,offset:item.top-item.card.getBoundingClientRect().top}));
      for(const {card:remaining,offset} of shifts)if(Math.abs(offset)>.5)
        moving.set(remaining,remaining.animate([{transform:`translateY(${offset}px)`},{transform:"translateY(0)"}],
          {duration:240,easing:"cubic-bezier(.4,0,.2,1)",composite:"add"}));
    };
    if(animate&&!matchMedia("(prefers-reduced-motion: reduce)").matches){card.classList.add("closing");setTimeout(finish,150);}else finish();
    diagnostic("dismissed",`key=${key} reason=${reason}`);
  }
  function show(text,options={}){
    if(!text)return;
    const variant=options.variant==="warn"?"warning":options.variant||"info",spec=variants[variant]||variants.info;
    const key=options.key||"event:"+(++sequence),title=options.title||spec.title;
    remove(key,false,"replaced");
    const card=document.createElement("article");card.className="notification-card notification-"+variant;card.dataset.key=key;card.dataset.variant=variant;
    card.setAttribute("role",variant==="error"||variant==="warning"?"alert":"status");
    const symbol=glyph(variant);symbol.classList.add("notification-icon");
    const content=document.createElement("div");content.className="notification-content";
    const heading=document.createElement("strong");heading.className="notification-title";heading.textContent=title;
    const body=document.createElement("p");body.className="notification-body";body.textContent=String(text);content.append(heading,body);
    if(options.action){const action=document.createElement("button");action.type="button";action.className="notification-action";action.textContent=options.action.label;action.addEventListener("click",options.action.run);content.append(action);}
    const close=document.createElement("button");close.type="button";close.className="notification-close";close.setAttribute("aria-label","关闭通知");close.append(glyph("close"));close.addEventListener("click",()=>remove(key,true,"manual"));
    const countdown=document.createElement("div");countdown.className="notification-countdown";countdown.setAttribute("aria-hidden","true");
    const timeout=durationMs;card.dataset.durationMs=timeout;countdown.style.animationDuration=timeout+"ms";
    card.append(symbol,content,close,countdown);startedAt.set(card,performance.now());cards.set(key,card);region.append(card);host();
    dismissTimers.set(key,setTimeout(()=>{if(cards.get(key)===card)remove(key,true,"expired");},timeout));
    diagnostic("shown",`key=${key} variant=${variant} timeout_ms=${timeout}`);return key;
  }
  function sync(key,text,options={}){
    const value=String(text||"");if(observed.get(key)===value)return;
    observed.set(key,value);if(value)show(value,{...options,key});else remove(key);
  }
  new MutationObserver(host).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["open"]});
  return {show,sync,remove,host,configure};
})();
