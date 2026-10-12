"use strict";
// Form state is presentation only. Python validates and persists every action.
class SettingsSuggestions {
  constructor(control,frame,label,values,groups=null){
    this.control=control;this.frame=frame;this.values=values;this.groups=groups;this.expanded=false;this.active=-1;this.filtered=false;
    this.events=new AbortController();const listen=(element,type,handler)=>element.addEventListener(type,handler,{signal:this.events.signal});
    frame.classList.add("settings-editable-choice");
    const line=frame.querySelector(".settings-choice-line"),arrow=line.querySelector(".settings-choice-arrow");
    this.toggle=button("",()=>{if(this.expanded)this.close("toggle");else this.open(false);control.focus();},"settings-choice-toggle");
    this.toggle.append(arrow);this.toggle.setAttribute("aria-label",label+"预设");line.append(this.toggle);
    this.list=node("div","settings-suggestions");this.list.id=control.id+"-suggestions";this.list.hidden=true;
    this.list.setAttribute("role","listbox");this.list.setAttribute("aria-label",label+"预设");frame.append(this.list);
    control.setAttribute("role","combobox");control.setAttribute("aria-autocomplete","list");control.autocomplete="off";
    for(const element of [control,this.toggle]){element.setAttribute("aria-haspopup","listbox");element.setAttribute("aria-controls",this.list.id);element.setAttribute("aria-expanded","false");}
    listen(control,"click",()=>this.open(false));
    listen(control,"input",event=>{this.edited=true;if(!event.isComposing&&!this.selecting)this.open(true);});
    listen(control,"change",()=>{this.edited=false;});
    listen(control,"compositionend",()=>this.open(true));
    listen(frame,"keydown",event=>{
      if(event.isComposing||event.keyCode===229)return;
      if(event.key==="Escape"&&this.expanded){event.preventDefault();event.stopPropagation();this.close("escape");control.focus();}
      else if(event.key==="Tab")this.close("tab");
      else if(["ArrowDown","ArrowUp"].includes(event.key)){
        event.preventDefault();if(!this.expanded)this.open(false);
        control.focus();if(this.options.length){this.active=this.active<0?(event.key==="ArrowDown"?0:this.options.length-1):(this.active+(event.key==="ArrowDown"?1:-1)+this.options.length)%this.options.length;this.highlight();}
      }else if(event.key==="Enter"&&this.expanded&&this.active>=0){event.preventDefault();this.choose(this.options[this.active].dataset.value);}
    });
    listen(frame,"focusout",()=>queueMicrotask(()=>{if(!frame.contains(document.activeElement))this.close("blur");}));
    listen(document,"pointerdown",event=>{if(!frame.contains(event.target))this.close("outside");});
  }
  open(filtered){
    if(this.control.disabled)return;
    clearTimeout(this.closeTimer);this.list.classList.remove("closing");this.list.inert=false;this.list.removeAttribute("aria-hidden");
    this.filtered=filtered;this.signature=null;this.render();
    this.list.hidden=false;this.control.setAttribute("aria-expanded","true");this.toggle.setAttribute("aria-expanded","true");
    if(!this.expanded)diagnostic("debug","settings suggestions opened",this.control.id);
    this.expanded=true;
  }
  render(){
    const query=this.filtered?this.control.value.trim().toLocaleLowerCase():"";
    const groups=this.groups?.(),raw=this.values();
    const values=(groups?Object.values(groups).flat():raw).filter(value=>!query||value.toLocaleLowerCase().includes(query));
    const signature=JSON.stringify([values,groups,this.control.value,state?.theme]);if(signature===this.signature)return;this.signature=signature;
    this.list.replaceChildren();this.options=[];this.active=-1;this.control.removeAttribute("aria-activedescendant");
    const containers=new Map();
    if(groups)for(const [family,names] of Object.entries(groups))if(names.some(value=>values.includes(value))){
      const group=node("div","settings-provider-group");group.dataset.family=family;group.setAttribute("role","group");group.setAttribute("aria-label",family||"待选择模型供应商");
      group.append(node("div","settings-provider-group-title",({OpenAI:"OpenAI · GPT",Anthropic:"Anthropic · Claude",xAI:"xAI · Grok",Google:"Google · Gemini",DeepSeek:"DeepSeek"})[family]||"待选择模型供应商"));
      this.list.append(group);for(const name of names)containers.set(name,group);
    }
    for(const value of values){
      const option=button(value,()=>this.choose(value),"settings-suggestion");option.id=this.list.id+"-"+this.options.length;option.tabIndex=-1;
      option.setAttribute("role","option");option.setAttribute("aria-selected",String(value===this.control.value));
      option.dataset.value=value;
      if(this.control.id==="settings-field-connection-provider"){
        option.classList.add("settings-provider-option");
        const family=groups?Object.keys(groups).find(key=>groups[key].includes(value)):value;
        const img=providerImage(family);if(img){img.alt="";img.setAttribute("aria-hidden","true");option.prepend(img);}
        if(value===this.control.value){const check=icon("check");check.classList.add("check");option.append(check);}
      }
      option.addEventListener("pointerdown",event=>event.preventDefault());this.options.push(option);(containers.get(value)||this.list).append(option);
    }
    if(!values.length)this.list.append(node("p","settings-suggestions-empty","没有匹配的预设，可直接输入自定义值。"));
  }
  highlight(){
    for(const [index,option] of this.options.entries())option.classList.toggle("active",index===this.active);
    const option=this.options[this.active];if(option){this.control.setAttribute("aria-activedescendant",option.id);option.scrollIntoView({block:"nearest"});}
  }
  choose(value){
    if(this.control.disabled)return;
    const changed=this.control.value!==value,apply=changed||this.edited;this.control.value=value;
    this.close("selected");this.control.focus();
    if(apply){this.selecting=true;try{if(changed)this.control.dispatchEvent(new Event("input",{bubbles:true}));this.control.dispatchEvent(new Event("change",{bubbles:true}));}finally{this.selecting=false;}}
    diagnostic("debug","settings suggestion selected",this.control.id);
  }
  close(reason){
    if(!this.expanded)return;
    this.expanded=false;this.list.inert=true;this.list.setAttribute("aria-hidden","true");this.active=-1;this.control.removeAttribute("aria-activedescendant");
    clearTimeout(this.closeTimer);
    if(["busy","category","leave","rebuild"].includes(reason)||matchMedia("(prefers-reduced-motion: reduce)").matches)this.list.hidden=true;
    else {this.list.classList.add("closing");this.closeTimer=setTimeout(()=>{this.list.hidden=true;this.list.classList.remove("closing");},230);}
    this.control.setAttribute("aria-expanded","false");this.toggle.setAttribute("aria-expanded","false");
    diagnostic("debug","settings suggestions closed",this.control.id+" reason="+reason);
  }
  sync(){this.toggle.disabled=this.control.disabled;if(this.control.disabled)this.close("busy");else if(this.expanded)this.render();}
  dispose(){this.close("rebuild");clearTimeout(this.closeTimer);this.events.abort();}
}
class SettingsPage {
  constructor() {
    this.element=$("#settings-page");this.controls=new Map();this.dirty=new Set();this.current=null;this.category="模型";
    this.keyAction="keep";this.key="";this.open=false;this.schema=null;this.suggestions=[];
  }
  update(settings,open) {
    if(!open){this.open=false;for(const choice of this.suggestions)choice.close("leave");this.clearCredentialInput();return;}
    if(!settings)return;
    this.open=true;this.current=settings;
    const schema=JSON.stringify(settings.fields);
    if(schema!==this.schema){this.schema=schema;this.build(settings);}
    for(const [name,control] of this.controls)if(!this.dirty.has(name)) {
      let value=name.startsWith("connection.")?settings.connection[name.slice(11)]:settings.values[name];
      if(name==="connection.model_provider"&&settings.providers[settings.connection.provider])value=settings.connection.provider;
      if(control.type==="checkbox")control.checked=Boolean(value);else if(control.value!==String(value??""))control.value=value??"";
    }
    this.keyInput.placeholder=settings.has_key?"已配置；留空保留原密钥":"输入 API Key";
    const directory=JSON.stringify([settings.available_models,settings.directory_status||""]);
    if(directory!==this.modelDirectorySignature){this.modelDirectorySignature=directory;this.modelDirectory.replaceChildren();
      this.modelDirectory.append(node("p","settings-key-note",settings.available_models.length?`已获取 ${settings.available_models.length} 个模型；模型 ID 为默认使用的模型。`:"尚未获取模型，请先填写接口和密钥，再点击“获取模型”。"));
      if(settings.directory_status){const status=node("p","settings-key-note",settings.directory_status);status.setAttribute("role","status");this.modelDirectory.append(status);}
      const list=node("div","settings-model-list");for(const id of settings.available_models)list.append(node("span","settings-model-id",id));this.modelDirectory.append(list);
    }
    this.keyNote.textContent=this.keyAction==="clear"?"密钥将被清空，点击保存设置后生效。":settings.has_key?"已有密钥由 Windows 加密保护；这里不会显示原值。":"尚未配置密钥。";
    this.confirmation.textContent=this.hasModelDraft()?"模型设置有修改，点击确认后用于任务。测试连接只测试接口。":settings.confirmation;
    this.savedStatus.textContent=settings.status;
    this.operationStatus.textContent=settings.operation_status;
    this.logDirectory.textContent="日志目录："+settings.log_directory+"。运行日志只在 Debug 控制台点击“保存日志”后写入文件。";
    this.refreshEnabled();
  }
  hideKey(){if(this.keyInput)this.keyInput.type="password";if(this.showKey){this.showKey.textContent="显示密钥";this.showKey.setAttribute("aria-pressed","false");}}
  clearCredentialInput(){this.key="";this.keyAction="keep";if(this.keyInput)this.keyInput.value="";this.hideKey();}
  hasModelDraft(){return this.keyAction!=="keep"||[...this.dirty].some(k=>(k.startsWith("connection.")&&k!=="connection.website")||this.current.fields[k]?.category==="模型");}
  refreshEnabled(){
    if(!this.current)return;
    const busy=this.current.busy||inFlight;
    for(const [name,control] of this.controls)control.disabled=name==="debug_console_enabled"?inFlight:busy;
    const builtin=Boolean(this.current.providers[this.controls.get("connection.provider").value]);
    this.controls.get("connection.model_provider").disabled=busy||builtin;
    this.controls.get("connection.model_provider").required=!builtin;
    this.deleteProvider.hidden=builtin||!(this.current.saved_providers||[]).includes(this.current.connection.provider);this.deleteProvider.disabled=busy;
    for(const choice of this.suggestions)choice.sync();
    this.keyInput.disabled=busy;this.clearKey.disabled=busy;this.showKey.disabled=busy||!this.keyInput.value;
    for(const b of this.modelButtons)b.disabled=busy;
    this.confirmButton.disabled=busy||(this.current.confirmed&&!this.hasModelDraft());
    this.confirmButton.textContent=this.current.confirmed&&!this.hasModelDraft()?"已确认":"确认";
    this.saveButton.disabled=busy;this.restoreButton.disabled=busy;
    for(const b of this.browseButtons)b.disabled=busy;
    this.draftStatus.textContent=this.dirty.size||this.keyAction!=="keep"?"有未保存的设置。":"";
  }
  field(name,label,spec={},choices=null){
    const id="settings-field-"+name.replaceAll(".","-");let control;
    if(choices||spec.choices?.length){control=node("select");for(const [value,text] of choices||spec.choices.map(v=>[v,this.choiceLabel(name,v)])){const option=node("option","",text);option.value=value;control.append(option);}}
    else if(typeof spec.default==="boolean"){control=node("input");control.type="checkbox";}
    else if(name==="extra_skill_roots"){control=node("textarea");control.rows=3;}
    else{control=node("input");control.type=spec.minimum===null||spec.minimum===undefined?"text":"number";if(control.type==="number"){control.min=spec.minimum;control.max=spec.maximum;control.step=Number.isInteger(spec.default)?"1":"any";}}
    control.id=id;const labelNode=node("label","",label);labelNode.htmlFor=id;
    const group=this.forms.get(spec.category||"模型");group.append(labelNode,control);this.controls.set(name,control);
    if(control.tagName==="SELECT")this.decorateChoice(control);
    control.addEventListener("input",()=>{this.dirty.add(name);if(name==="connection.base_url"&&control.value!==this.current.connection.base_url){this.keyInput.value="";this.key="";this.keyAction="clear";}this.refreshEnabled();});
    return control;
  }
  decorateChoice(control){
    const frame=node("div","settings-choice"),line=node("div","settings-choice-line"),arrow=node("span","settings-choice-arrow");
    arrow.setAttribute("aria-hidden","true");arrow.append(icon("chevronDown"));
    control.replaceWith(frame);frame.append(line);line.append(control,arrow);return frame;
  }
  editableChoice(control,label,values,groups=null){
    this.suggestions.push(new SettingsSuggestions(control,this.decorateChoice(control),label,values,groups));
  }
  choiceLabel(name,value){return ({reasoning_effort:{auto:"自动",omit:"不发送",low:"Low",medium:"Medium",high:"High",max:"Max"},composer_theme:{light:"浅色",dark:"深色"},default_thinking:{quick:"快速",standard:"标准",deep:"深入"},default_tone:{neutral:"中性",polite:"适度礼貌"}}[name]||{})[value]||value;}
  build(settings){
    for(const choice of this.suggestions)choice.dispose();this.suggestions=[];
    this.element.replaceChildren();this.controls.clear();this.forms=new Map();this.browseButtons=[];
    const heading=node("div","settings-heading"),title=node("h1","","设置");title.id="settings-title";
    heading.append(title,button("返回工作区",()=>command("settings_back")));this.element.append(heading);
    this.tabs=node("div","settings-tabs");this.tabs.setAttribute("role","tablist");this.tabs.setAttribute("aria-label","设置分类");
    this.scroll=node("div","settings-scroll");
    for(const category of [...new Set(Object.values(settings.fields).map(f=>f.category))]){
      const b=button(category,()=>this.selectCategory(category));b.setAttribute("role","tab");b.id="settings-tab-"+this.forms.size;
      const form=node("div","settings-form");form.id="settings-category-"+this.forms.size;form.setAttribute("role","tabpanel");form.setAttribute("aria-labelledby",b.id);b.setAttribute("aria-controls",form.id);
      b.dataset.category=category;this.tabs.append(b);this.forms.set(category,form);this.scroll.append(form);
      b.addEventListener("keydown",event=>{
        const tabs=[...this.tabs.children],index=tabs.indexOf(b);let next=null;
        if(event.key==="ArrowRight")next=(index+1)%tabs.length;
        else if(event.key==="ArrowLeft")next=(index+tabs.length-1)%tabs.length;
        else if(event.key==="Home")next=0;else if(event.key==="End")next=tabs.length-1;
        if(next!==null){event.preventDefault();this.selectCategory(tabs[next].dataset.category);tabs[next].focus();}
      });
    }
    this.element.append(this.tabs,this.scroll);
    const provider=this.field("connection.provider","服务名称",{},null);
    this.editableChoice(provider,"服务名称",()=>Object.keys(this.current.providers),()=>this.providerGroups());
    provider.addEventListener("change",()=>this.switchProvider(provider.value));
    const family=this.field("connection.model_provider","模型供应商",{},[["","请选择模型供应商（必选）"],...Object.keys(settings.providers).map(name=>[name,name])]);
    family.addEventListener("change",()=>{const preset=this.current.providers[family.value];if(preset){this.controls.get("connection.protocol").value=preset.protocol;this.dirty.add("connection.protocol");}this.refreshEnabled();diagnostic("debug","custom service model provider selected",family.value);});
    this.field("connection.website","官网链接");
    this.field("connection.protocol","协议",{},settings.protocols.map(p=>[p,p]));this.field("connection.base_url","接口地址");
    const model=this.field("connection.model","模型 ID");
    this.editableChoice(model,"模型 ID",()=>this.current.available_models);
    const modelForm=this.forms.get("模型"),keyLabel=node("label","","API Key"),keyBox=node("div");
    keyLabel.htmlFor="settings-key";this.keyInput=node("input");this.keyInput.id="settings-key";this.keyInput.type="password";this.keyInput.autocomplete="off";this.keyInput.spellcheck=false;
    this.clearKey=button("清空密钥",()=>{this.keyInput.value="";this.key="";this.keyAction="clear";this.update(this.current,true);});
    this.showKey=button("显示密钥",()=>{const show=this.keyInput.type==="password";this.keyInput.type=show?"text":"password";this.showKey.textContent=show?"隐藏密钥":"显示密钥";this.showKey.setAttribute("aria-pressed",String(show));});
    this.showKey.setAttribute("aria-controls","settings-key");this.showKey.setAttribute("aria-pressed","false");
    const row=node("div","settings-input-row settings-key-row");row.append(this.keyInput,this.showKey,this.clearKey);this.keyNote=node("p","settings-key-note");keyBox.append(row,this.keyNote);modelForm.append(keyLabel,keyBox);
    this.keyInput.addEventListener("input",()=>{this.key=this.keyInput.value;this.keyAction=this.key?"replace":this.keyAction==="clear"?"clear":"keep";this.refreshEnabled();});
    modelForm.append(node("p","settings-full settings-profile-note","各供应商独立保存接口、密钥和模型列表。切换时暂存未保存输入；保存设置仅保存当前供应商。"));
    const actions=node("div","settings-full settings-model-actions");this.modelButtons=[];
    for(const [label,action] of [["获取模型","settings_models"],["测试连接","settings_test"],["确认","settings_confirm"]]){const b=button(label,()=>this.submit(action));this.modelButtons.push(b);if(action==="settings_confirm")this.confirmButton=b;actions.append(b);}
    this.confirmation=node("p","settings-full settings-status");modelForm.append(actions,this.confirmation);
    this.modelDirectory=node("section","settings-full settings-model-directory");this.modelDirectory.setAttribute("role","region");this.modelDirectory.setAttribute("aria-label","已获取模型");this.modelDirectorySignature=null;modelForm.append(this.modelDirectory);
    this.deleteProvider=button("删除供应商",()=>this.confirmDelete(),"settings-full settings-delete-provider");modelForm.append(this.deleteProvider);
    for(const [key,spec] of Object.entries(settings.fields)){
      const control=this.field(key,spec.label,spec);
      if(["session_directory","export_directory"].includes(key)){
        const wrap=node("div","settings-input-row"),b=button("浏览…",async()=>{const result=await command("settings_browse",{revision:this.current.revision,key,initial:control.value});if(result?.path){control.value=result.path;this.dirty.add(key);this.refreshEnabled();}});
        control.replaceWith(wrap);wrap.append(control,b);this.browseButtons.push(b);
      }
      if(key==="debug_console_enabled")control.addEventListener("change",async()=>{const result=await command("settings_debug",{revision:this.current.revision,enabled:control.checked});if(result){this.dirty.delete(key);await poll();}});
    }
    this.logDirectory=node("p","settings-full settings-diagnostics-note");this.forms.get("诊断").append(this.logDirectory);
    const footer=node("div","settings-footer");this.savedStatus=node("p","settings-status");this.operationStatus=node("p","settings-status");this.draftStatus=node("p","settings-status");
    this.errorStatus=node("p","settings-status settings-error");this.errorStatus.setAttribute("role","alert");const buttons=node("div","actions");
    this.restoreButton=button("恢复本类默认",()=>this.restore());this.saveButton=button("保存设置",()=>this.submit("settings_save"));buttons.append(this.restoreButton,this.saveButton);
    footer.append(this.savedStatus,this.operationStatus,this.draftStatus,this.errorStatus,buttons);this.element.append(footer);this.selectCategory(this.category);
    diagnostic("debug","settings fields rendered","choice_arrows="+this.element.querySelectorAll(".settings-choice").length+" full_width_actions="+this.element.querySelectorAll(".settings-full.settings-model-actions,.settings-full.settings-delete-provider").length);
  }
  selectCategory(category){for(const choice of this.suggestions)choice.close("category");this.category=category;for(const [key,form] of this.forms)form.hidden=key!==category;for(const tab of this.tabs.children){const selected=tab.dataset.category===category;tab.setAttribute("aria-selected",String(selected));tab.tabIndex=selected?0:-1;}this.scroll.scrollTop=0;diagnostic("debug","settings category",category);}
  restore(){for(const [key,spec] of Object.entries(this.current.fields))if(spec.category===this.category){const c=this.controls.get(key);if(c.type==="checkbox")c.checked=spec.default;else c.value=spec.default;this.dirty.add(key);}this.refreshEnabled();}
  payload(sourceProvider=null){
    const connection={},values={};for(const [name,c] of this.controls){const value=c.type==="checkbox"?c.checked:c.value;if(name.startsWith("connection."))connection[name.slice(11)]=value;else values[name]=value;}
    if(sourceProvider!==null)connection.provider=sourceProvider;
    if(this.current.providers[connection.provider])delete connection.model_provider;
    if(!connection.website)delete connection.website;
    return {revision:this.current.revision,connection,values,key_action:this.keyAction,key:this.key};
  }
  providerGroups(){
    const builtins=Object.keys(this.current.providers),saved=this.current.saved_providers||[],families=this.current.provider_families||{};
    if(!saved.some(name=>!builtins.includes(name)))return null;
    const groups=Object.fromEntries(builtins.map(name=>[name,[name]]));
    for(const name of saved)if(!builtins.includes(name)){const family=builtins.includes(families[name])?families[name]:"";(groups[family]??=[]).push(name);}
    return groups;
  }
  confirmDelete(){
    if(this.current.busy||inFlight)return;
    const target=this.current.connection.provider;if(this.current.providers[target])return;
    const dialog=node("dialog","editor-dialog"),title=node("h2","popup-title","删除自定义供应商");title.id="settings-delete-title";dialog.setAttribute("aria-labelledby",title.id);
    const text=node("p","",`删除“${target}”及其保存的接口、加密密钥和模型列表？当前未保存输入也会移除。`),actions=node("div","actions");
    const close=()=>{dialog.close();dialog.remove();(this.deleteProvider.hidden?this.controls.get("connection.provider"):this.deleteProvider).focus();};
    const cancel=button("取消",close),remove=button("删除",async()=>{remove.disabled=cancel.disabled=true;try{const result=await command("settings_delete_provider",{revision:this.current.revision,target});if(result?.settings){this.clearModelDraft();this.update(result.settings,true);close();}else{error.textContent="删除未完成，请查看提示后重试。";}}finally{remove.disabled=cancel.disabled=false;}},"settings-delete-provider");
    const error=node("p","editor-error");error.setAttribute("role","alert");actions.append(cancel,remove);dialog.append(title,text,error,actions);this.element.append(dialog);dialog.addEventListener("cancel",event=>{event.preventDefault();close();});dialog.showModal();cancel.focus();
  }
  clearModelDraft(){for(const name of [...this.dirty])if(name.startsWith("connection.")||this.current.fields[name]?.category==="模型")this.dirty.delete(name);this.clearCredentialInput();}
  async switchProvider(target){
    if(!this.current||target===this.current.connection.provider)return;
    target=target.trim();if(!target)return;
    const data=this.payload(this.current.connection.provider);data.target=target;
    this.errorStatus.textContent="";
    const result=await command("settings_provider",data);
    if(result?.settings){this.clearModelDraft();this.update(result.settings,true);}
    else{this.controls.get("connection.provider").value=this.current.connection.provider;this.dirty.delete("connection.provider");this.errorStatus.textContent="供应商未切换，输入仍保留，请重试。";}
    this.refreshEnabled();
  }
  async submit(action){
    this.errorStatus.textContent="";
    this.hideKey();
    const family=this.controls.get("connection.model_provider");
    if(!this.current.providers[this.controls.get("connection.provider").value]&&!family.value){this.errorStatus.textContent="请选择模型供应商，再保存或使用此自定义服务。";family.focus();return;}
    // Key is never stored in a browser snapshot, localStorage or exported data.
    const result=await command(action,this.payload());
    if(result?.settings){
      const all=action==="settings_save";
      for(const name of [...this.dirty])if(all||name.startsWith("connection.")||this.current.fields[name]?.category==="模型")this.dirty.delete(name);
      this.clearCredentialInput();this.update(result.settings,true);
    }else if(!result){this.errorStatus.textContent="设置操作未完成，请按提示修改后重试。";}
    this.refreshEnabled();
  }
}
window.promptsmithSettings=new SettingsPage();
