/* Self-contained Streamlit component: native drag/drop, pointer movement and SVG links. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const slots = [[40,15],[40,420],[270,25],[490,25],[270,430],[490,430],[40,150],[40,285]];
  let catalog=[], state={ids:[],positions:{}}, initial=null, evidence=[], history=[], tab="topic";
  let initialized=false, lastSent=null, matching=0, sequence=0, listMode=false, userViewChoice=false;
  let evidencePositions={};
  const clone = value => JSON.parse(JSON.stringify(value));
  const tell = (type,extra={}) => window.parent.postMessage({isStreamlitMessage:true,type,...extra},"*");
  const resize = () => requestAnimationFrame(() => tell("streamlit:setFrameHeight",{height:Math.ceil(document.body.getBoundingClientRect().height)+4}));
  const announce = message => {$("announcement").textContent=message;};
  const concept = id => catalog.find(c=>c.id===id);
  const chosen = kind => state.ids.map(concept).filter(c=>c && c.kind===kind);
  const labelKind = kind => ({topic:"Topic",question:"Question",status:"Registry status",type:"Study type",availability:"Availability",evidence:"Retrieved source"}[kind]);
  const clamp = (v,low,high) => Math.min(high,Math.max(low,v));
  function remember(previous=state){history.push(clone(previous));if(history.length>25)history.shift();}
  function invalidateEvidence(){evidence=[];evidencePositions={};$("evidence-drawer").hidden=true;}
  function emit(action="update") {
    lastSent=`${Date.now()}-${++sequence}`;
    tell("streamlit:setComponentValue",{value:{...clone(state),action,event_id:lastSent},dataType:"json"});
  }
  function el(tag,className,text){const item=document.createElement(tag);if(className)item.className=className;if(text!==undefined)item.textContent=text;return item;}
  function add(id,position) {
    if(!concept(id))return;
    if(state.ids.includes(id)){announce("That concept is already connected.");return;}
    if(state.ids.length>=8){const message="Use up to eight concepts. Remove one before adding another.";announce(message);$("selection-detail").textContent=message;return;}
    remember();
    invalidateEvidence();
    const [x,y]=slots[state.ids.length%slots.length];
    state.ids.push(id);state.positions[id]=position||{x,y};
    announce(`${concept(id).label} added to your map.`);render();emit();
  }
  function remove(id){remember();invalidateEvidence();state.ids=state.ids.filter(i=>i!==id);delete state.positions[id];announce("Concept removed.");render();emit();}
  function renderPalette(){
    $("palette").replaceChildren();
    const items=catalog.filter(c=>tab==="filters"?["status","type","availability"].includes(c.kind):c.kind===tab);
    for(const c of items){
      const button=el("button","palette-card");button.type="button";button.draggable=true;button.dataset.kind=c.kind;button.dataset.concept=c.id;
      const selected=state.ids.includes(c.id);button.classList.toggle("is-selected",selected);
      button.setAttribute("aria-label",`${selected?"Already added:":"Add"} ${c.label}`);
      button.append(el("strong","",c.label),el("small","",c.kind==="question"?"Evidence question":`${labelKind(c.kind)} · ${c.detail}`),el("span","add-symbol",selected?"✓":"+"));
      button.onclick=()=>add(c.id);
      button.ondragstart=e=>{e.dataTransfer.setData("text/plain",c.id);e.dataTransfer.effectAllowed="copy";};
      $("palette").append(button);
    }
  }
  function link(x,y,kind){
    const path=document.createElementNS("http://www.w3.org/2000/svg","path");
    const endX=447,endY=260,mid=(x+endX)/2;
    path.setAttribute("d",`M ${x} ${y} C ${mid} ${y}, ${mid} ${endY}, ${endX} ${endY}`);
    path.setAttribute("class",`connection ${["status","type","availability"].includes(kind)?"filter":kind}`);$("edges").append(path);
  }
  function drawEdges(){
    $("edges").replaceChildren();
    for(const id of state.ids){const p=state.positions[id];const c=concept(id);if(p&&c)link(p.x+100,p.y+45,c.kind);}
    evidence.slice(0,3).forEach((record,i)=>{const p=evidencePositions[record.id]||{x:700,y:100+i*120};link(p.x+90,p.y+40,"evidence");});
  }
  function node(c,isEvidence=false,list=false){
    const item=el("article",`map-node ${c.kind}`);item.dataset.node=c.id;item.tabIndex=0;
    item.setAttribute("aria-label",`${c.label}. ${isEvidence?"Open to read evidence":"Drag to move. Arrow keys move; Delete removes."}`);
    item.append(el("span","node-kind",labelKind(c.kind)),el("h4","",c.label));
    if(isEvidence){
      const button=el("button","read-evidence","Read evidence ↗");button.onclick=()=>openEvidence(c.id);item.append(button);
    }else{
      item.append(el("span","node-note",c.kind==="question"?"Search this evidence lens":c.detail));
      const close=el("button","remove","×");close.setAttribute("aria-label",`Remove ${c.label}`);close.onclick=e=>{e.stopPropagation();remove(c.id);};item.append(close);
    }
    if(!list){
      const p=isEvidence?evidencePositions[c.id]:state.positions[c.id];item.style.left=p.x+"px";item.style.top=p.y+"px";
      let drag=null;
      item.onpointerdown=e=>{
        if(e.target.closest("button")||e.button!==0)return;
        e.preventDefault();item.focus();
        const point=isEvidence?evidencePositions[c.id]:state.positions[c.id];
        drag={clientX:e.clientX,clientY:e.clientY,x:point.x,y:point.y,previous:clone(state),moved:false};
        item.setPointerCapture(e.pointerId);item.style.zIndex="5";
      };
      item.onpointermove=e=>{
        if(!drag)return;
        const dx=e.clientX-drag.clientX,dy=e.clientY-drag.clientY;
        if(Math.abs(dx)+Math.abs(dy)>3)drag.moved=true;
        const p={x:clamp(drag.x+dx,10,isEvidence?710:680),y:clamp(drag.y+dy,10,440)};
        if(isEvidence)evidencePositions[c.id]=p;else state.positions[c.id]=p;
        item.style.left=p.x+"px";item.style.top=p.y+"px";drawEdges();
      };
      const finish=e=>{
        if(!drag)return;const changed=drag.moved,previous=drag.previous;drag=null;item.style.zIndex="3";
        if(item.hasPointerCapture(e.pointerId))item.releasePointerCapture(e.pointerId);
        if(changed&&!isEvidence){remember(previous);render();emit();}
      };
      item.onpointerup=finish;item.onpointercancel=finish;
    }
    item.onkeydown=e=>{
      if(e.target!==item)return;
      if(isEvidence&&(e.key==="Enter"||e.key===" ")){e.preventDefault();openEvidence(c.id);return;}
      if(!isEvidence&&(e.key==="Delete"||e.key==="Backspace")){e.preventDefault();remove(c.id);return;}
      const moves={ArrowLeft:[-15,0],ArrowRight:[15,0],ArrowUp:[0,-15],ArrowDown:[0,15]};
      if(!list&&!isEvidence&&moves[e.key]){e.preventDefault();remember();const [dx,dy]=moves[e.key];const p=state.positions[c.id];p.x=clamp(p.x+dx,10,680);p.y=clamp(p.y+dy,10,440);item.style.left=p.x+"px";item.style.top=p.y+"px";drawEdges();emit();}
    };
    return item;
  }
  function render(){
    renderPalette();$("nodes").replaceChildren();$("selected-list").replaceChildren();
    for(const id of state.ids){const c=concept(id);if(!c)continue;if(!state.positions[id])state.positions[id]={x:65,y:95};$("nodes").append(node(c));$("selected-list").append(node(c,false,true));}
    evidence.slice(0,3).forEach((record,i)=>{
      if(!evidencePositions[record.id])evidencePositions[record.id]={x:700,y:100+i*120};
      const c={id:record.id,kind:"evidence",label:record.id};$("nodes").append(node(c,true));$("selected-list").append(node(c,true,true));
    });
    if(!state.ids.length)$("selected-list").append(el("p","list-empty","Choose a topic and a question from the concept library."));
    const topics=chosen("topic"),questions=chosen("question"),filters=chosen("status").length+chosen("type").length+chosen("availability").length;
    $("concept-count").textContent=`${state.ids.length}/8 concepts`;
    $("hub-question").textContent=topics.length?topics.map(c=>c.label).join(" or ")+" · "+(questions.map(c=>c.label).join(" + ")||"Choose a question"):"Add a topic and a question.";
    $("match-count").textContent=`${matching} matching trials`;
    $("selection-summary").textContent=`${topics.length} topic${topics.length===1?"":"s"} · ${questions.length} question${questions.length===1?"":"s"} · ${filters} study filters`;
    $("selection-detail").textContent=evidence.length?`${evidence.length} retrieved trials · first ${Math.min(3,evidence.length)} shown on map · all passages below`:"Topics use OR; filter categories use AND. No filters means all study types and statuses.";
    $("search").disabled=!(topics.length&&questions.length&&matching);
    $("search").title=matching?"Search evidence for the connected topics and questions":"No trials match this combination. Remove a filter or change topic.";
    $("undo").disabled=!history.length;
    $("board-scroll").hidden=listMode;$("selected-list").hidden=!listMode;
    $("map-view").setAttribute("aria-pressed",String(!listMode));$("list-view").setAttribute("aria-pressed",String(listMode));
    drawEdges();resize();
  }
  function openEvidence(id){
    const record=evidence.find(e=>e.id===id);if(!record)return;
    $("drawer-title").textContent=record.id;$("drawer-study").textContent=record.title;$("drawer-passages").replaceChildren();
    for(const passage of record.passages){const article=el("article");article.append(el("strong","",passage.section.replaceAll("_"," ")),el("p","",passage.text),el("small","",passage.source_id));$("drawer-passages").append(article);}
    $("drawer-source").href=record.url;$("evidence-drawer").hidden=false;resize();
    setTimeout(()=>{$("close-drawer").focus();$("evidence-drawer").scrollIntoView({block:"nearest"});},40);
  }
  document.querySelectorAll("[data-tab]").forEach(button=>{button.onclick=()=>{tab=button.dataset.tab;document.querySelectorAll("[data-tab]").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));renderPalette();resize();};});
  $("board").ondragover=e=>{e.preventDefault();e.dataTransfer.dropEffect="copy";$("board").classList.add("drag-over");};
  $("board").ondragleave=e=>{if(!$("board").contains(e.relatedTarget))$("board").classList.remove("drag-over");};
  $("board").ondrop=e=>{e.preventDefault();$("board").classList.remove("drag-over");const rect=$("board").getBoundingClientRect();add(e.dataTransfer.getData("text/plain"),{x:clamp(e.clientX-rect.left-100,10,680),y:clamp(e.clientY-rect.top-45,10,440)});};
  $("undo").onclick=()=>{if(history.length){const previous=history.pop();if([...previous.ids].sort().join()!==[...state.ids].sort().join())invalidateEvidence();state=previous;render();emit();announce("Last change undone.");}};
  $("arrange").onclick=()=>{remember();state.ids.forEach((id,i)=>{const [x,y]=slots[i%slots.length];state.positions[id]={x,y};});evidencePositions={};render();emit();};
  $("reset").onclick=()=>{remember();invalidateEvidence();state=clone(initial);render();emit();announce("Starter map restored.");};
  $("clear").onclick=()=>{remember();invalidateEvidence();state={ids:[],positions:{}};render();emit();announce("Canvas cleared. Add a topic and question to start again.");};
  $("map-view").onclick=()=>{userViewChoice=true;listMode=false;render();};$("list-view").onclick=()=>{userViewChoice=true;listMode=true;render();};
  $("search").onclick=()=>{announce("Searching your connected concepts.");emit("search");};
  $("close-drawer").onclick=()=>{$("evidence-drawer").hidden=true;resize();};
  document.addEventListener("keydown",e=>{if(e.key==="Escape"){$("evidence-drawer").hidden=true;resize();}});
  $("save").onclick=()=>{
    const data={version:1,concepts:state.ids.map(id=>({...concept(id),position:state.positions[id]})),retrieved_trial_ids:evidence.map(e=>e.id)};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));
    const a=el("a");a.href=url;a.download="ragz-research-map.json";document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),500);
  };
  window.addEventListener("message",event=>{
    if(event.source!==window.parent||event.data.type!=="streamlit:render")return;
    const args=event.data.args;
    if(initialized&&lastSent&&args.ack!==lastSent)return;
    catalog=args.catalog||[];evidence=args.evidence||[];matching=args.matching_count||0;
    if(!initialized){state=clone(args.state);initial=clone(args.initial_state||args.state);initialized=true;}
    else if(!lastSent||args.ack===lastSent){state=clone(args.state);}
    if(!evidence.some(e=>e.id===$("drawer-title").textContent))$("evidence-drawer").hidden=true;
    render();
  });
  new ResizeObserver(()=>{
    if(initialized&&!userViewChoice){const next=innerWidth<560;if(next!==listMode){listMode=next;render();}}
    resize();
  }).observe(document.querySelector(".workspace"));
  tell("streamlit:componentReady",{apiVersion:1});resize();
})();
