"use strict";
// Form state is presentation only. Python validates and persists every action.
class SettingsPage {
  constructor() {
    this.element=$("#settings-page");this.controls=new Map();this.dirty=new Set();this.current=null;this.category="模型";
    this.keyAction="keep";this.key="";this.open=false;this.schema=null;
  }
  update(settings,open) {
    if(!open){this.open=false;this.clearCredentialInput();return;}
    if(!settings)return;
    this.open=true;this.current=settings;
    const schema=JSON.stringify(settings.fields);
    if(schema!==this.schema){this.schema=schema;this.build(settings);}
    for(const [name,control] of this.controls)if(!this.dirty.has(name)) {
      const value=name.startsWith("connection.")?settings.connection[name.slice(11)]:settings.values[name];
      if(control.type==="checkbox")control.checked=Boolean(value);else if(control.value!==String(value??""))control.value=value??"";
    }
    const datalist=$("#settings-model-ids");datalist.replaceChildren();
    for(const id of settings.available_models){const option=node("option");option.value=id;datalist.append(option);}
    this.keyInput.placeholder=settings.has_key?"已配置；留空保留原密钥":"输入 API Key";
    this.keyNote.textContent=this.keyAction==="clear"?"密钥将被清空，点击保存设置后生效。":settings.has_key?"已有密钥由 Windows 加密保护；这里不会显示原值。":"尚未配置密钥。";
    this.confirmation.textContent=this.hasModelDraft()?"模型设置有修改，点击确认后用于任务。测试连接只测试接口。":settings.confirmation;
    this.savedStatus.textContent=settings.status;
    this.operationStatus.textContent=settings.operation_status;
    this.logDirectory.textContent="日志目录："+settings.log_directory+"。运行日志只在 Debug 控制台点击“保存日志”后写入文件。";
    this.refreshEnabled();
  }
  clearCredentialInput(){this.key="";this.keyAction="keep";if(this.keyInput)this.keyInput.value="";}
  hasModelDraft(){return this.keyAction!=="keep"||[...this.dirty].some(k=>k.startsWith("connection.")||this.current.fields[k]?.category==="模型");}
  refreshEnabled(){
    if(!this.current)return;
    const busy=this.current.busy||inFlight;
    for(const [name,control] of this.controls)control.disabled=name==="debug_console_enabled"?inFlight:busy;
    this.keyInput.disabled=busy;this.clearKey.disabled=busy;
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
    control.addEventListener("input",()=>{this.dirty.add(name);if(name==="connection.base_url"&&control.value!==this.current.connection.base_url){this.keyInput.value="";this.key="";this.keyAction="clear";}this.refreshEnabled();});
    return control;
  }
  choiceLabel(name,value){return ({reasoning_effort:{auto:"自动",omit:"不发送",low:"Low",medium:"Medium",high:"High",max:"Max"},composer_theme:{light:"浅色",dark:"深色"},default_thinking:{quick:"快速",standard:"标准",deep:"深入"},default_tone:{neutral:"中性",polite:"适度礼貌"}}[name]||{})[value]||value;}
  build(settings){
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
    const provider=this.field("connection.provider","服务名称",{},null),providers=node("datalist");providers.id="settings-providers";
    for(const name of Object.keys(settings.providers)){const o=node("option");o.value=name;providers.append(o);}provider.setAttribute("list",providers.id);this.element.append(providers);
    provider.addEventListener("change",()=>{
      const preset=this.current.providers[provider.value];if(preset)for(const key of ["base_url","protocol","model"]){this.controls.get("connection."+key).value=preset[key];this.dirty.add("connection."+key);}
      this.clearCredentialInput();this.keyAction="clear";this.refreshEnabled();
    });
    this.field("connection.protocol","协议",{},settings.protocols.map(p=>[p,p]));this.field("connection.base_url","接口地址");
    const model=this.field("connection.model","模型 ID"),models=node("datalist");models.id="settings-model-ids";model.setAttribute("list",models.id);this.element.append(models);
    const modelForm=this.forms.get("模型"),keyLabel=node("label","","API Key"),keyBox=node("div");
    keyLabel.htmlFor="settings-key";this.keyInput=node("input");this.keyInput.id="settings-key";this.keyInput.type="password";this.keyInput.autocomplete="off";this.keyInput.spellcheck=false;
    this.clearKey=button("清空密钥",()=>{this.keyInput.value="";this.key="";this.keyAction="clear";this.update(this.current,true);});
    const row=node("div","settings-input-row");row.append(this.keyInput,this.clearKey);this.keyNote=node("p","settings-key-note");keyBox.append(row,this.keyNote);modelForm.append(keyLabel,keyBox);
    this.keyInput.addEventListener("input",()=>{this.key=this.keyInput.value;this.keyAction=this.key?"replace":"keep";this.refreshEnabled();});
    const actions=node("div","settings-full settings-model-actions");this.modelButtons=[];
    for(const [label,action] of [["获取模型","settings_models"],["测试连接","settings_test"],["确认","settings_confirm"]]){const b=button(label,()=>this.submit(action));this.modelButtons.push(b);if(action==="settings_confirm")this.confirmButton=b;actions.append(b);}
    this.confirmation=node("p","settings-full settings-status");modelForm.append(actions,this.confirmation);
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
  }
  selectCategory(category){this.category=category;for(const [key,form] of this.forms)form.hidden=key!==category;for(const tab of this.tabs.children){const selected=tab.dataset.category===category;tab.setAttribute("aria-selected",String(selected));tab.tabIndex=selected?0:-1;}this.scroll.scrollTop=0;diagnostic("debug","settings category",category);}
  restore(){for(const [key,spec] of Object.entries(this.current.fields))if(spec.category===this.category){const c=this.controls.get(key);if(c.type==="checkbox")c.checked=spec.default;else c.value=spec.default;this.dirty.add(key);}this.refreshEnabled();}
  async submit(action){
    const connection={},values={};for(const [name,c] of this.controls){const value=c.type==="checkbox"?c.checked:c.value;if(name.startsWith("connection."))connection[name.slice(11)]=value;else values[name]=value;}
    this.errorStatus.textContent="";
    // Key is never stored in a browser snapshot, localStorage or exported data.
    const result=await command(action,{revision:this.current.revision,connection,values,key_action:this.keyAction,key:this.key});
    if(result?.settings){
      const all=action==="settings_save";
      for(const name of [...this.dirty])if(all||name.startsWith("connection.")||this.current.fields[name]?.category==="模型")this.dirty.delete(name);
      this.clearCredentialInput();this.update(result.settings,true);
    }else if(!result){this.errorStatus.textContent="设置操作未完成，请按提示修改后重试。";}
    this.refreshEnabled();
  }
}
window.promptsmithSettings=new SettingsPage();
