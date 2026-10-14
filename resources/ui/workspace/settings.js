"use strict";
// Form state is presentation only. Python validates and persists every action.
class SettingsSuggestions {
  constructor(control,frame,label,values,groups=null,providerFor=null){
    this.control=control;this.frame=frame;this.values=values;this.groups=groups;this.providerFor=providerFor;this.expanded=false;this.active=-1;this.filtered=false;
    this.events=new AbortController();const listen=(element,type,handler)=>element.addEventListener(type,handler,{signal:this.events.signal});
    frame.classList.add("settings-editable-choice");
    const line=frame.querySelector(".settings-choice-line"),arrow=line.querySelector(".settings-choice-arrow");
    if(control.tagName==="BUTTON"){
      this.toggle=control;control.append(arrow);control.setAttribute("aria-label",label);
      listen(control,"click",()=>{if(this.expanded)this.close("toggle");else this.open(false);});
    }else{
      this.toggle=button("",()=>{if(this.expanded)this.close("toggle");else this.open(false);control.focus();},"settings-choice-toggle");
      this.toggle.append(arrow);this.toggle.setAttribute("aria-label",label+"预设");line.append(this.toggle);
    }
    // Keep input focus through pointer activation; Chromium can deliver the
    // focusout microtask before focusin, otherwise closing before the toggle.
    if(this.toggle!==control)listen(this.toggle,"pointerdown",event=>event.preventDefault());
    this.list=node("div","settings-suggestions");this.list.id=control.id+"-suggestions";this.list.hidden=true;
    this.list.setAttribute("popover","manual");
    this.list.setAttribute("role","listbox");this.list.setAttribute("aria-label",label+"预设");frame.append(this.list);
    control.setAttribute("role","combobox");control.setAttribute("aria-autocomplete",control.readOnly?"none":"list");control.autocomplete="off";
    for(const element of [control,this.toggle]){element.setAttribute("aria-haspopup","listbox");element.setAttribute("aria-controls",this.list.id);element.setAttribute("aria-expanded","false");}
    if(this.toggle!==control)listen(control,"click",()=>this.open(false));
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
      }else if(["Home","End"].includes(event.key)&&control.readOnly){event.preventDefault();if(!this.expanded)this.open(false);this.active=event.key==="Home"?0:this.options.length-1;this.highlight();}
      else if(event.key==="Enter"&&this.expanded&&this.active>=0){event.preventDefault();this.choose(this.options[this.active].dataset.value);}
    });
    listen(frame,"focusout",()=>queueMicrotask(()=>{if(!frame.contains(document.activeElement))this.close("blur");}));
    listen(document,"pointerdown",event=>{if(!frame.contains(event.target))this.close("outside");});
    listen(window,"resize",()=>{if(this.expanded)this.position();});
    document.addEventListener("scroll",event=>{if(this.expanded&&event.target!==this.list&&!this.list.contains(event.target))this.position();},{capture:true,signal:this.events.signal});
  }
  open(filtered){
    if(this.control.disabled)return;
    clearTimeout(this.closeTimer);this.list.classList.remove("closing");this.list.inert=false;this.list.removeAttribute("aria-hidden");
    this.filtered=filtered;this.signature=null;this.render();
    this.list.hidden=false;this.control.setAttribute("aria-expanded","true");this.toggle.setAttribute("aria-expanded","true");
    if(this.list.showPopover&&!this.list.matches(":popover-open"))this.list.showPopover();
    this.position();
    if(!this.expanded)diagnostic("debug","settings suggestions opened",this.control.id);
    this.expanded=true;
  }
  position(){
    const box=this.control.getBoundingClientRect(),height=window.innerHeight,width=window.innerWidth;
    if(box.bottom<0||box.top>height){this.close("outside");return;}
    const below=height-box.bottom-16,above=box.top-16,up=below<160&&above>below;
    this.list.style.maxHeight=Math.max(40,Math.min(260,up?above:below))+"px";
    this.list.style.width=Math.max(0,Math.min(box.width,width-24))+"px";
    this.list.style.left=Math.max(12,Math.min(box.left,width-this.list.getBoundingClientRect().width-12))+"px";
    this.list.style.top=(up?Math.max(12,box.top-this.list.getBoundingClientRect().height-8):box.bottom+8)+"px";
    this.list.style.transformOrigin=up?"bottom center":"top center";
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
      const option=button("",()=>this.choose(value),"settings-suggestion");option.id=this.list.id+"-"+this.options.length;option.tabIndex=-1;
      option.append(node("span","settings-option-label",controlLabel(this.control,value)));
      option.setAttribute("role","option");option.setAttribute("aria-selected",String(value===this.control.value));
      option.dataset.value=value;
      option.classList.add("settings-provider-option");
      const family=this.providerFor?.(value)||(this.control.id==="settings-field-connection-provider"?(groups?Object.keys(groups).find(key=>groups[key].includes(value)):value):null);
      const img=providerImage(family);if(img){img.alt="";img.setAttribute("aria-hidden","true");option.prepend(img);}
      if(value===this.control.value){const check=icon("check");check.classList.add("check");option.append(check);}
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
    const hide=()=>{if(this.list.hidePopover&&this.list.matches(":popover-open"))this.list.hidePopover();this.list.hidden=true;this.list.classList.remove("closing");};
    if(["busy","category","leave","rebuild"].includes(reason)||matchMedia("(prefers-reduced-motion: reduce)").matches)hide();
    else {this.list.classList.add("closing");this.closeTimer=setTimeout(hide,230);}
    this.control.setAttribute("aria-expanded","false");this.toggle.setAttribute("aria-expanded","false");
    diagnostic("debug","settings suggestions closed",this.control.id+" reason="+reason);
  }
  sync(){this.toggle.disabled=this.control.disabled;if(this.control.disabled)this.close("busy");else if(this.expanded){this.render();this.position();}}
  dispose(){this.close("rebuild");clearTimeout(this.closeTimer);this.events.abort();}
}
function controlLabel(control,value){return control.choiceLabels?.get(value)??value;}
class SettingsPage {
  constructor() {
    this.element=$("#settings-page");this.controls=new Map();this.dirty=new Set();this.current=null;this.category="模型";
    this.keyAction="keep";this.key="";this.open=false;this.schema=null;this.suggestions=[];this.saving=null;
  }
  update(settings,open) {
    if(!open){this.open=false;for(const choice of this.suggestions)choice.close("leave");this.renameDialog?.close();this.renameDialog?.remove();this.renameDialog=null;this.renaming=false;this.clearCredentialInput();return;}
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
    this.keyNote.textContent=this.keyAction==="clear"?"正在清空密钥。":settings.has_key?"已有密钥由 Windows 加密保护；这里不会显示原值。":"尚未配置密钥。";
    this.confirmation.textContent=settings.confirmed?"模型配置可直接使用。测试连接只检查接口。":"填写有效的模型配置后即可使用。";
    this.logDirectory.textContent="日志目录："+settings.log_directory+"。运行日志只在 Debug 控制台点击“保存日志”后写入文件。";
    this.refreshEnabled();
  }
  hideKey(){if(this.keyInput)this.keyInput.type="password";if(this.showKey){this.showKey.textContent="显示密钥";this.showKey.setAttribute("aria-pressed","false");}}
  clearCredentialInput(){this.key="";this.keyAction="keep";if(this.keyInput)this.keyInput.value="";this.hideKey();}
  hasModelDraft(){return this.keyAction!=="keep"||[...this.dirty].some(k=>(k.startsWith("connection.")&&k!=="connection.website")||this.current.fields[k]?.category==="模型");}
  refreshEnabled(){
    if(!this.current)return;
    const busy=this.current.busy||inFlight||this.switching||this.deleting||this.renaming;
    for(const [name,control] of this.controls)control.disabled=name==="debug_console_enabled"?inFlight:busy;
    const builtin=Boolean(this.current.providers[this.controls.get("connection.provider").value]);
    this.controls.get("connection.model_provider").disabled=busy||builtin;
    this.controls.get("connection.model_provider").required=!builtin;
    this.deleteProvider.hidden=builtin||!(this.current.saved_providers||[]).includes(this.current.connection.provider);this.deleteProvider.disabled=busy;
    this.renameProvider.hidden=this.deleteProvider.hidden;this.renameProvider.disabled=busy;
    for(const choice of this.suggestions)choice.sync();
    this.keyInput.disabled=busy;this.clearKey.disabled=busy;this.showKey.disabled=busy||!this.keyInput.value;
    for(const b of this.modelButtons)b.disabled=busy;
    this.restoreButton.disabled=busy;
    for(const b of this.browseButtons)b.disabled=busy;
    // Saving/switching can settle after the last desktop snapshot. Consumers
    // of form readiness must also observe these local lifecycle transitions.
    document.dispatchEvent(new Event("promptsmith-settings-state-changed"));
  }
  field(name,label,spec={},choices=null){
    const id="settings-field-"+name.replaceAll(".","-");let control;
    if(choices||spec.choices?.length){
      control=node("button","settings-select");control.type="button";control.readOnly=true;
      control.choiceLabels=new Map(choices||spec.choices.map(v=>[v,this.choiceLabel(name,v)]));
      const caption=node("span","settings-choice-caption");control.append(caption);
      Object.defineProperty(control,"value",{get(){return this.choiceValue??"";},set(value){this.choiceValue=String(value);caption.textContent=controlLabel(this,this.choiceValue);this.dataset.value=this.choiceValue;}});
    }
    else if(typeof spec.default==="boolean"){control=node("input");control.type="checkbox";}
    else if(name==="extra_skill_roots"){control=node("textarea");control.rows=3;}
    else{control=node("input");control.type=spec.minimum===null||spec.minimum===undefined?"text":"number";if(control.type==="number"){control.min=spec.minimum;control.max=spec.maximum;control.step=Number.isInteger(spec.default)?"1":"any";}}
    control.id=id;const labelNode=node("label","",label);labelNode.htmlFor=id;
    const group=this.forms.get(spec.category||"模型");group.append(labelNode,control);this.controls.set(name,control);
    if(control.readOnly){const values=()=>[...control.choiceLabels.keys()];this.editableChoice(control,label,values,null,name==="connection.model_provider"?value=>value:null);}
    control.addEventListener("input",event=>{this.dirty.add(name);if(name==="connection.base_url"&&control.value!==this.current.connection.base_url){this.keyInput.value="";this.key="";this.keyAction="clear";}this.refreshEnabled();if(!event.isComposing&&name!=="connection.provider"&&name!=="debug_console_enabled")this.scheduleSave();});
    control.addEventListener("compositionend",()=>{if(name!=="connection.provider")this.scheduleSave();});
    control.addEventListener("change",()=>{if(name==="debug_console_enabled")this.saveDebugToggle();else if(name!=="connection.provider")this.scheduleSave(0);});
    return control;
  }
  decorateChoice(control){
    const frame=node("div","settings-choice"),line=node("div","settings-choice-line"),arrow=node("span","settings-choice-arrow");
    arrow.setAttribute("aria-hidden","true");arrow.append(icon("chevronDown"));
    control.replaceWith(frame);frame.append(line);line.append(control,arrow);return frame;
  }
  editableChoice(control,label,values,groups=null,providerFor=null){
    this.suggestions.push(new SettingsSuggestions(control,this.decorateChoice(control),label,values,groups,providerFor));
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
      b.prepend(icon(({模型:"brain","Skill 搜索":"search",界面:"image","会话与导出":"file",诊断:"activity"})[category]));
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
    this.card=node("div","settings-card");this.localNav=node("aside","settings-local-nav");
    this.localTitle=node("p","settings-local-title");this.localLinks=node("nav","settings-local-links");this.localLinks.setAttribute("aria-label","本页设置分组");
    this.localNav.append(this.localTitle,this.localLinks);this.main=node("div","settings-main");this.main.append(this.scroll);this.card.append(this.localNav,this.main);
    this.element.append(this.tabs,this.card);
    const provider=this.field("connection.provider","服务名称",{},null);
    this.editableChoice(provider,"服务名称",()=>Object.keys(this.current.providers),()=>this.providerGroups());
    const providerChoice=provider.closest(".settings-choice"),providerRow=node("div","settings-service-row");
    this.renameProvider=button("重命名",()=>this.confirmRename(),"settings-rename-provider");this.renameProvider.title="重命名自定义供应商";
    providerChoice.replaceWith(providerRow);providerRow.append(providerChoice,this.renameProvider);
    provider.addEventListener("change",()=>this.switchProvider(provider.value));
    const family=this.field("connection.model_provider","模型供应商",{},[["","请选择模型供应商（必选）"],...Object.keys(settings.providers).map(name=>[name,name])]);
    family.addEventListener("change",()=>{const preset=this.current.providers[family.value];if(preset){this.controls.get("connection.protocol").value=preset.protocol;this.dirty.add("connection.protocol");}this.refreshEnabled();diagnostic("debug","custom service model provider selected",family.value);});
    this.field("connection.website","官网链接");
    this.field("connection.protocol","协议",{},settings.protocols.map(p=>[p,p]));this.field("connection.base_url","接口地址");
    const model=this.field("connection.model","模型 ID");
    this.editableChoice(model,"模型 ID",()=>this.current.available_models.filter(id=>id.toLowerCase()!=="codex-auto-review"),null,
      id=>state?.models?.find(m=>m.id===id)?.provider||this.controls.get("connection.model_provider").value);
    const modelForm=this.forms.get("模型"),keyLabel=node("label","","API Key"),keyBox=node("div");
    keyLabel.htmlFor="settings-key";this.keyInput=node("input");this.keyInput.id="settings-key";this.keyInput.type="password";this.keyInput.autocomplete="off";this.keyInput.spellcheck=false;
    this.clearKey=button("清空密钥",()=>{this.keyInput.value="";this.key="";this.keyAction="clear";this.update(this.current,true);this.scheduleSave(0);});
    this.showKey=button("显示密钥",()=>{const show=this.keyInput.type==="password";this.keyInput.type=show?"text":"password";this.showKey.textContent=show?"隐藏密钥":"显示密钥";this.showKey.setAttribute("aria-pressed",String(show));});
    this.showKey.setAttribute("aria-controls","settings-key");this.showKey.setAttribute("aria-pressed","false");
    const row=node("div","settings-input-row settings-key-row");row.append(this.keyInput,this.showKey,this.clearKey);this.keyNote=node("p","settings-key-note");keyBox.append(row,this.keyNote);modelForm.append(keyLabel,keyBox);
    this.keyInput.addEventListener("input",event=>{this.key=this.keyInput.value;this.keyAction=this.key?"replace":this.keyAction==="clear"?"clear":"keep";this.refreshEnabled();if(!event.isComposing)this.scheduleSave();});
    this.keyInput.addEventListener("compositionend",()=>this.scheduleSave());
    this.keyInput.addEventListener("change",()=>this.scheduleSave(0));
    modelForm.append(node("p","settings-full settings-profile-note","各供应商独立保存接口、密钥和模型列表。修改自动保存，密钥由 Windows 加密保护。"));
    const actions=node("div","settings-full settings-model-actions");this.modelButtons=[];
    for(const [label,action] of [["获取模型","settings_models"],["测试连接","settings_test"]]){const b=button(label,()=>this.submit(action));this.modelButtons.push(b);actions.append(b);}
    this.confirmation=node("p","settings-full settings-status");modelForm.append(actions,this.confirmation);
    const providerActions=node("div","settings-full settings-provider-actions");
    this.deleteProvider=button("删除供应商",()=>this.confirmDelete(),"settings-delete-provider");providerActions.append(this.deleteProvider);modelForm.append(providerActions);
    for(const [key,spec] of Object.entries(settings.fields)){
      const control=this.field(key,spec.label,spec);
      if(["session_directory","export_directory"].includes(key)){
        const wrap=node("div","settings-input-row"),b=button("浏览…",async()=>{if(!await this.flush())return;const result=await command("settings_browse",{revision:this.current.revision,key,initial:control.value});if(result?.path){control.value=result.path;this.dirty.add(key);this.refreshEnabled();this.scheduleSave(0);}});
        control.replaceWith(wrap);wrap.append(control,b);this.browseButtons.push(b);
      }
    }
    this.logDirectory=node("p","settings-full settings-diagnostics-note");this.forms.get("诊断").append(this.logDirectory);
    const footer=node("div","settings-footer"),buttons=node("div","actions");
    this.restoreButton=button("恢复本类默认",()=>this.restore());this.retryButton=button("重试自动保存",()=>this.dirty.has("debug_console_enabled")?this.saveDebugToggle():this.flush());this.retryButton.hidden=true;buttons.append(this.restoreButton,this.retryButton);
    footer.append(buttons);this.main.append(footer);
    this.groupFields();
    const guide=node("section","settings-section"),replay=node("div","tutorial-replay");
    guide.dataset.title="使用教程";guide.id="settings-tutorial";
    replay.append(node("p","","跟随操作引导，配置模型并发送第一个目标。"),button("重新查看教程",()=>{for(const choice of this.suggestions)choice.close("leave");window.promptsmithTutorial.open("settings");}));
    guide.append(node("h3","","使用教程"),replay);this.forms.get("界面").append(guide);
    this.selectCategory(this.category);
    diagnostic("debug","settings fields rendered","choice_arrows="+this.element.querySelectorAll(".settings-choice").length+" full_width_actions="+this.element.querySelectorAll(".settings-full.settings-model-actions,.settings-full.settings-provider-actions").length);
  }
  groupFields(){
    const descriptions={模型:"管理调用服务与模型参数。修改自动保存，有效配置即可使用。","Skill 搜索":"调整本地与联网搜索范围，以及模型筛选预算。",界面:"调整主题、字号和启动窗口。","会话与导出":"设置新会话偏好和本地保存位置。",诊断:"调整 Debug 控制台。日志由你点击保存后写入文件。"};
    for(const [category,form] of this.forms){
      const children=[...form.children];form.replaceChildren();
      const heading=node("div","settings-category-heading");heading.append(node("h2","",category),node("p","",descriptions[category]||"修改自动保存。"));form.append(heading);
      const sections=new Map();
      const section=(name)=>{if(!sections.has(name)){const el=node("section","settings-section"),grid=node("div","settings-section-grid");el.id="settings-section-"+this.forms.size+"-"+category.replaceAll(" ","-")+"-"+sections.size;el.dataset.title=name;el.append(node("h3","",name),grid);sections.set(name,{el,grid});form.append(el);}return sections.get(name).grid;};
      for(let i=0;i<children.length;i++){
        const child=children[i];let group=category==="模型"?"连接服务":"偏好设置";
        if(child.tagName==="LABEL"){
          const controlId=child.htmlFor,name=[...this.controls].find(([,c])=>c.id===controlId)?.[0];
          if(category==="模型"&&name&&!name.startsWith("connection."))group="生成参数";
          if(category==="Skill 搜索")group=["extra_skill_roots","skill_search_url","web_search_url","search_timeout","network_candidates","network_cache_seconds"].includes(name)?"检索来源":"筛选与预算";
          const box=node("div","settings-field"),content=children[++i];box.append(child,content);
          if(this.controls.get(name)?.type==="checkbox"){box.classList.add("settings-switch-row");this.controls.get(name).setAttribute("role","switch");}
          section(group).append(box);
        }else section(group).append(child);
      }
    }
  }
  selectCategory(category){
    for(const choice of this.suggestions)choice.close("category");this.category=category;
    for(const [key,form] of this.forms)form.hidden=key!==category;
    for(const tab of this.tabs.children){const selected=tab.dataset.category===category;tab.setAttribute("aria-selected",String(selected));tab.tabIndex=selected?0:-1;}
    this.localTitle.textContent=category;this.localLinks.replaceChildren();
    for(const section of this.forms.get(category).querySelectorAll(".settings-section")){
      const b=button(section.dataset.title,()=>{this.scroll.scrollTo({top:this.scroll.scrollTop+section.getBoundingClientRect().top-this.scroll.getBoundingClientRect().top-8,behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});for(const other of this.localLinks.children)other.removeAttribute("aria-current");b.setAttribute("aria-current","location");});
      b.prepend(icon(section.dataset.title==="连接服务"?"plug":"sliders"));b.setAttribute("aria-controls",section.id);this.localLinks.append(b);
    }
    this.localLinks.firstChild?.setAttribute("aria-current","location");this.scroll.scrollTop=0;diagnostic("debug","settings category",category);
  }
  restore(){for(const [key,spec] of Object.entries(this.current.fields))if(spec.category===this.category){const c=this.controls.get(key);if(c.type==="checkbox")c.checked=spec.default;else c.value=spec.default;this.dirty.add(key);}this.refreshEnabled();this.scheduleSave(0);}
  feedback(text,variant="error"){window.promptsmithNotifications.sync("action:settings_autosave",text,{variant});}
  scheduleSave(delay=450){clearTimeout(this.saveTimer);this.feedback("");this.retryButton.hidden=true;this.saveTimer=setTimeout(()=>this.flush(),delay);}
  async saveDebugToggle(){
    const control=this.controls.get("debug_console_enabled"),enabled=control.checked;
    if(this.saving)await this.saving;
    const result=await command("settings_debug",{revision:this.current.revision,enabled});
    if(result){if(control.checked===enabled)this.dirty.delete("debug_console_enabled");this.feedback("");this.retryButton.hidden=true;this.refreshEnabled();}
    else{this.retryButton.hidden=false;}
  }
  async flush(){
    clearTimeout(this.saveTimer);
    if(this.saving)return this.saving;
    this.saving=this.drainSaves();this.refreshEnabled();
    try{return await this.saving;}finally{this.saving=null;this.refreshEnabled();}
  }
  async drainSaves(){
    while([...this.dirty].some(name=>name!=="connection.provider")||this.keyAction!=="keep"){
    this.saveFailureKind=null;
    if(this.current.busy||this.deleting)return false;
    const desktop=[...this.dirty].filter(name=>this.current.fields[name]?.category!=="模型"&&!name.startsWith("connection."));
    if(desktop.length){
      if(desktop.some(name=>!this.controls.get(name).checkValidity())){this.feedback("请填写有效的设置值，修正后会自动保存。","warning");return false;}
      if(!await this.persist(desktop))return false;
      continue;
    }
    const family=this.controls.get("connection.model_provider");
    const invalid=[...this.controls.values()].find(c=>!c.checkValidity());
    if(invalid||(!this.current.providers[this.current.connection.provider]&&!family.value)){
      this.feedback(invalid?"请填写有效的设置值，修正后会自动保存。":"请选择模型供应商，选择后会自动保存。","warning");return false;
    }
    if(!await this.persist())return false;
    }
    return true;
  }
  async persist(desktop=null){
    // A typed service name is a switch draft until change/blur commits it.
    // Autosave must always keep the currently active credential identity.
    const payload=this.payload(this.current.connection.provider);payload.changed_fields=desktop||[...this.dirty].filter(name=>name!=="connection.provider");
    if(desktop){payload.key="";payload.key_action="keep";}
    const submitted=new Map(payload.changed_fields.map(name=>{const c=this.controls.get(name);return [name,c.type==="checkbox"?c.checked:c.value];}));
    this.hideKey();diagnostic("debug","settings autosave started","fields="+[...this.dirty].join(","));
    try{
      const result=await window.pywebview.api.dispatch("settings_autosave",payload,state.stamp);
      if(!result.ok){const error=new Error(result.error||"自动保存未完成。");error.kind=result.error_kind||"persistence";throw error;}
      for(const [name,value] of submitted){const c=this.controls.get(name);if((c.type==="checkbox"?c.checked:c.value)===value)this.dirty.delete(name);}
      if(!desktop&&this.key===payload.key&&this.keyAction===payload.key_action)this.clearCredentialInput();
      this.feedback("");this.retryButton.hidden=true;
      if(result.data?.settings)this.update(result.data.settings,true);
      await poll();diagnostic("debug","settings autosave completed","");return true;
    }catch(error){this.saveFailureKind=error.kind||"persistence";this.feedback(error.message||"自动保存失败，请重试。",this.saveFailureKind==="validation"?"warning":"error");this.retryButton.hidden=this.saveFailureKind==="validation";diagnostic(this.saveFailureKind==="validation"?"warn":"error","settings autosave failed",error?.stack||String(error));return false;}
  }
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
  async confirmRename(){
    if(this.current.busy||inFlight||this.switching||this.deleting||this.renaming)return;
    this.renaming=true;clearTimeout(this.saveTimer);this.refreshEnabled();
    if(!await this.flush()){this.renaming=false;this.refreshEnabled();return;}
    const target=this.current.connection.provider;
    if(this.current.providers[target]||!(this.current.saved_providers||[]).includes(target)){this.renaming=false;this.refreshEnabled();return;}
    for(const choice of this.suggestions)choice.close("category");
    const dialog=node("dialog","editor-dialog"),title=node("h2","popup-title","重命名自定义供应商");title.id="settings-rename-title";dialog.setAttribute("aria-labelledby",title.id);
    const label=node("label","","新的服务名称"),field=node("input");field.id="settings-rename-name";field.value=target;field.maxLength=4095;label.htmlFor=field.id;
    const note=node("p","notice","保留现有接口、加密密钥、模型参数和模型列表。"),buttons=node("div","actions");
    let saving=false;
    this.renameDialog=dialog;
    const close=(reason="cancel")=>{if(saving)return;dialog.close();dialog.remove();if(this.renameDialog===dialog){this.renameDialog=null;this.renaming=false;this.refreshEnabled();if(this.open)this.renameProvider.focus();diagnostic("debug","custom provider rename dialog closed",reason);}};
    const cancel=button("取消",()=>close()),save=button("确认重命名",async()=>{
      if(saving)return;
      const name=field.value.trim();
      if(!name){toast("请填写新的服务名称。","warning");field.focus();return;}
      if(name===target){close();return;}
      saving=true;field.disabled=save.disabled=cancel.disabled=true;
      try{
        const result=await command("settings_rename_provider",{revision:this.current.revision,target,name});
        if(result?.settings&&this.open&&this.renameDialog===dialog){this.clearModelDraft();this.update(result.settings,true);saving=false;close("saved");}
      }finally{saving=false;field.disabled=save.disabled=cancel.disabled=false;}
    });
    sendOnEnter(field,()=>save.click());buttons.append(cancel,save);dialog.append(title,label,field,note,buttons);this.element.append(dialog);
    dialog.addEventListener("cancel",event=>{event.preventDefault();close();});dialog.showModal();field.focus();field.select();
    diagnostic("debug","custom provider rename dialog opened","");
  }
  async confirmDelete(){
    if(this.current.busy||inFlight)return;
    this.deleting=true;clearTimeout(this.saveTimer);this.refreshEnabled();
    if(this.saving)await this.saving;
    const target=this.current.connection.provider;if(this.current.providers[target]){this.deleting=false;this.refreshEnabled();return;}
    const dialog=node("dialog","editor-dialog"),title=node("h2","popup-title","删除自定义供应商");title.id="settings-delete-title";dialog.setAttribute("aria-labelledby",title.id);
    const text=node("p","",`删除“${target}”及其保存的接口、加密密钥和模型列表？当前未保存输入也会移除。`),actions=node("div","actions");
    const close=()=>{dialog.close();dialog.remove();this.deleting=false;this.refreshEnabled();(this.deleteProvider.hidden?this.controls.get("connection.provider"):this.deleteProvider).focus();if(this.dirty.size||this.keyAction!=="keep")this.scheduleSave();};
    const cancel=button("取消",close),remove=button("删除",async()=>{remove.disabled=cancel.disabled=true;try{const result=await command("settings_delete_provider",{revision:this.current.revision,target});if(result?.settings){this.clearModelDraft();this.update(result.settings,true);close();}}finally{remove.disabled=cancel.disabled=false;}},"settings-delete-provider");
    actions.append(cancel,remove);dialog.append(title,text,actions);this.element.append(dialog);dialog.addEventListener("cancel",event=>{event.preventDefault();close();});dialog.showModal();cancel.focus();
  }
  clearModelDraft(){for(const name of [...this.dirty])if(name.startsWith("connection.")||this.current.fields[name]?.category==="模型")this.dirty.delete(name);this.clearCredentialInput();}
  async switchProvider(target){
    if(!this.current||target===this.current.connection.provider)return;
    target=target.trim();if(!target)return;
    clearTimeout(this.saveTimer);this.switching=true;this.refreshEnabled();
    // Save the source profile before applying the destination. The displayed
    // target must not accidentally become the autosave's credential identity.
    this.controls.get("connection.provider").value=this.current.connection.provider;
    this.dirty.delete("connection.provider");
    if(this.saving)await this.saving;
    const saved=await this.flush();
    // Incomplete drafts can be staged when changing services. A failed write
    // keeps the source visible so the user can retry without losing the key.
    if(!saved&&this.saveFailureKind==="persistence"){this.switching=false;this.refreshEnabled();return;}
    const data=this.payload(this.current.connection.provider);data.target=target;
    this.feedback("");
    const result=await command("settings_provider",data);
    if(result?.settings){this.clearModelDraft();this.update(result.settings,true);}
    else{this.controls.get("connection.provider").value=this.current.connection.provider;this.dirty.delete("connection.provider");}
    this.switching=false;this.refreshEnabled();
  }
  async submit(action){
    if(!await this.flush())return;
    this.feedback("");
    this.hideKey();
    const family=this.controls.get("connection.model_provider");
    if(!this.current.providers[this.controls.get("connection.provider").value]&&!family.value){this.feedback("请选择模型供应商，再保存或使用此自定义服务。");family.focus();return;}
    // Key is never stored in a browser snapshot, localStorage or exported data.
    const result=await command(action,this.payload());
    if(result?.settings){
      const all=action==="settings_save";
      for(const name of [...this.dirty])if(all||name.startsWith("connection.")||this.current.fields[name]?.category==="模型")this.dirty.delete(name);
      this.clearCredentialInput();this.update(result.settings,true);
    }
    this.refreshEnabled();
  }
}
window.promptsmithSettings=new SettingsPage();
