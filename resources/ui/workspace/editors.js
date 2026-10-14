"use strict";
// Browser drafts are transient; only explicit Save writes through SessionState.
window.promptsmithEditors=(()=>{
  let dialog=null,current=null,returnFocus=null,dismissed=null;
  function close(){
    if(!dialog)return;
    dialog.close();dialog.remove();dialog=null;current=null;
    restoreFocus(returnFocus);returnFocus=null;
  }
  function update(editor){
    if(!editor){dismissed=null;close();return;}
    if(editor.id===dismissed)return;
    window.promptsmithNotifications.sync("action:editor_save",editor.error||"",{variant:"error"});
    if(current?.id===editor.id){
      return;
    }
    close();returnFocus=captureFocus();closePopup(true);current=editor;
    dialog=node("dialog","editor-dialog");dialog.setAttribute("aria-label",editor.title);
    const title=node("div","popup-title",editor.title),cancel=button("",cancelEditor,"popup-close");
    cancel.append(icon("close"));cancel.setAttribute("aria-label","关闭编辑");title.append(cancel);dialog.append(title);
    if(editor.kind==="plan"){
      renderPlan(dialog,editor);
      const controls=node("div","actions");controls.append(button("完成编辑",cancelEditor));dialog.append(controls);
      show();return;
    }
    const form=node("form","editor-form"),fields=node("div","editor-fields");
    form.addEventListener("invalid",event=>{event.preventDefault();toast((event.target.getAttribute("aria-label")||"内容")+"不能为空。","warning",{key:"editor:validation"});},true);
    if(editor.message)form.append(node("p","notice",editor.message));
    for(const field of editor.fields){
      if(field.type==="choices"){
        const group=node("fieldset","editor-field editor-choices");group.dataset.key=field.key;
        group.append(node("legend","",field.label));const selected=new Set(field.value.split("\n"));
        for(const choice of field.choices){const label=node("label"),input=node("input");input.type="checkbox";input.value=choice.id;input.checked=selected.has(choice.id);label.append(input,node("span","",choice.label));group.append(label);}
        if(!field.choices.length)group.append(node("p","notice","暂无可关联项目。"));fields.append(group);
      }else{
        const label=node("label","editor-field"),input=node("textarea");
        label.append(node("span","",field.label));input.name=field.key;input.value=field.value;
        input.rows=editor.fields.length===1?6:3;input.required=!!field.required;
        input.setAttribute("aria-label",field.label);label.append(input);fields.append(label);
      }
    }
    const controls=node("div","actions");controls.append(button("取消",cancelEditor));
    const save=button(({step_delete:"删除",new:"新建",conflict:"确认可以并存"})[editor.kind]||"保存",()=>form.requestSubmit(),"editor-save");controls.append(save);
    form.append(fields,controls);dialog.append(form);
    form.addEventListener("submit",async event=>{
      event.preventDefault();const values=Object.fromEntries(new FormData(form));
      for(const group of fields.querySelectorAll(".editor-choices"))values[group.dataset.key]=[...group.querySelectorAll("input:checked")].map(input=>input.value).join("\n");
      const id=editor.id;save.disabled=true;
      try{
        if(await command("editor_save",{id,values})){dismissed=id;if(current?.id===id)close();}
      }
      finally{save.disabled=false;}
    });
    dialog.addEventListener("keydown",event=>{
      if(event.key==="Escape"){event.preventDefault();event.stopPropagation();cancelEditor();}
      if(!event.isComposing&&event.keyCode!==229&&(event.ctrlKey||event.metaKey)&&["Enter","s"].includes(event.key)){event.preventDefault();event.stopPropagation();form.requestSubmit();}
    });
    show();
  }
  function show(){
    dialog.addEventListener("cancel",event=>{event.preventDefault();cancelEditor();});
    dialog.addEventListener("keydown",event=>{
      if((event.ctrlKey||event.metaKey)&&event.key==="s"){event.preventDefault();event.stopPropagation();}
      if(event.key==="Tab"){
        const controls=[...dialog.querySelectorAll("button:not(:disabled),input:not(:disabled),textarea:not(:disabled),summary")].filter(e=>e.getClientRects().length);
        const index=controls.indexOf(document.activeElement);
        if(event.shiftKey&&index<=0){event.preventDefault();controls.at(-1)?.focus();}
        else if(!event.shiftKey&&(index===controls.length-1||index<0)){event.preventDefault();controls[0]?.focus();}
      }
    });
    document.body.append(dialog);dialog.showModal();dialog.querySelector("textarea,button")?.focus({preventScroll:true});
    diagnostic("debug","editor visible",`kind=${current.kind} id=${current.id}`);
  }
  function renderPlan(box,editor){
    const content=editor.content;
    const open=(kind,target)=>command("editor_open",{id:editor.id,kind,target});
    const goal=node("section","editor-section");goal.append(node("h2","","目标"),node("p","reading",content.goal.summary),node("p","notice","受众："+content.goal.audience+"\n范围："+content.goal.scope));
    const goalActions=node("div","actions");goalActions.append(button("编辑目标",()=>open("goal")),button("编辑受众与范围",()=>open("goal_details")));goal.append(goalActions);box.append(goal);
    const labels={title:"标题",purpose:"目的",inputs:"输入",actions:"关键行动",outputs:"输出",completion_criteria:"完成标准",depends_on_step_ids:"依赖步骤",requirement_ids:"关联需求",goal:"目标",checkpoints:"检查点",step_ids:"关联步骤",depends_on_key_work_ids:"依赖关键工作",name:"名称",description:"说明",text:"内容",impact:"影响",continuable_work:"可继续工作",confirm_by:"确认时点",reason:"理由"};
    const names=new Map([...(content.steps||[]).map(r=>[r.step_id,r.title]),...(content.key_work||[]).map(r=>[r.key_work_id,r.title]),...state.requirement_rows.filter(r=>r.id.startsWith("r:")).map(r=>[r.id.slice(2),r.text])]);
    for(const [collection,kind,idkey,label] of [["steps","step","step_id","方案步骤"],["deliverables","deliverable","deliverable_id","交付物"],["completion_criteria","criterion","criterion_id","完成标准"],["unresolved_items","unresolved","unresolved_id","未决事项"],["suggestions","suggestion","suggestion_id","建议"],["key_work","key_work","key_work_id","关键工作"]]){
      const section=node("section","editor-section");section.append(node("h2","",label));
      const rows=collection==="steps"?[...content.steps].sort((a,b)=>a.order-b.order):content[collection]||[];
      for(const [index,row] of rows.entries()){
        const fold=node("details"),heading=row.title||row.name||row.text||row.description;
        fold.append(node("summary","",heading));
        for(const [key,value] of Object.entries(row))if(labels[key])fold.append(node("p","reading",labels[key]+"："+(Array.isArray(value)?value.map(v=>names.get(v)||v).join("\n"):String(value))));
        const controls=node("div","actions"),edit=button("编辑",()=>open(kind,row[idkey]));edit.setAttribute("aria-label","编辑"+label+"："+heading);controls.append(edit);
        if(kind==="step"){
          const up=button("上移",()=>command("editor_move",{id:editor.id,target:row[idkey],offset:-1})),down=button("下移",()=>command("editor_move",{id:editor.id,target:row[idkey],offset:1}));up.disabled=index===0;down.disabled=index===rows.length-1;controls.append(up,down,button("删除",()=>open("step_delete",row[idkey])));
        }
        if(kind==="key_work"){
          const pending=editor.pending.includes(row[idkey]),review=button(pending?"标记已复核":"已复核",()=>command("editor_review",{id:editor.id,target:row[idkey]}));review.disabled=!pending;controls.append(review);
        }
        fold.append(controls);section.append(fold);
      }
      if(kind==="step")section.append(button("新增步骤",()=>open("step_new")));
      if(!rows.length)section.append(node("p","notice","暂无内容。"));box.append(section);
    }
    const coverage=node("details","editor-section");coverage.append(node("summary","","需求覆盖关系"));
    for(const row of content.requirement_coverage||[])coverage.append(node("p","reading",(names.get(row.requirement_id)||row.requirement_id)+"："+row.summary));box.append(coverage);
  }
  async function cancelEditor(){
    if(!current||inFlight)return;
    const id=current.id;
    if(await command("editor_cancel",{id})){dismissed=id;if(current?.id===id)close();}
  }
  return {update};
})();
