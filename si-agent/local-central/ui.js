// #632 : formulaires rendus UNE fois par onglet (jamais écrasés par le rafraîchissement), zones dynamiques
// rafraîchies toutes les 5 s, et retour visuel immédiat sur chaque clic : bouton en « ⏳ », bandeau
// (toast) « envoyé / acquitté / refusé », pastille des commandes en attente.
let S=null, sel=null, tab='poste', panelKey='';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function ago(iso){if(!iso)return '—';const d=(Date.now()-Date.parse(iso))/1000;return d<90?Math.round(d)+' s':d<5400?Math.round(d/60)+' min':Math.round(d/3600)+' h'}
function gb(n){return n==null?'?':n>=1e12?(n/1e12).toFixed(2)+' To':n>=1e9?(n/1e9).toFixed(1)+' Go':Math.round(n/1e6)+' Mo'}
function fv(id){const e=$(id);return e?(e.type==='checkbox'?e.checked:e.value):undefined}
function copy(id){navigator.clipboard&&navigator.clipboard.writeText($(id).textContent);toast('copié dans le presse-papiers','ok',3000)}
async function post(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j}

// -- toasts -------------------------------------------------------------------------
let toasts=[];
function toast(msg,kind='info',ms=8000){const t={id:Date.now()+Math.random(),msg,kind};toasts.push(t);renderToasts();if(ms)setTimeout(()=>{toasts=toasts.filter(x=>x!==t);renderToasts()},ms)}
function renderToasts(){const box=$('toasts');if(!box)return;box.innerHTML=toasts.slice(-6).map(t=>`<div class="toast ${t.kind}" onclick="toasts=toasts.filter(x=>x.id!==${t.id});renderToasts()">${esc(t.msg)}</div>`).join('')}

// -- commandes : envoi + suivi de l'acquittement -------------------------------------
const watch={};   // cid -> {label, btn, since}
function busy(btn,on){if(!btn)return;if(on){btn.dataset.orig=btn.dataset.orig||btn.textContent;btn.textContent='⏳ '+btn.dataset.orig;btn.disabled=true}else{btn.textContent=btn.dataset.orig||btn.textContent;btn.disabled=false}}
async function cmd(type,params,label,btn){
 if(!sel){toast('choisir un agent d\'abord','warn');return}
 label=label||type;busy(btn,true);
 try{const c=await post('/ui/command',{agent_id:sel,type,params});watch[c.id]={label,btn,since:Date.now()};toast(`⏳ ${label} envoyé (${c.id}) — en attente de l'agent (≤ 10 s)`,'info',6000);renderPending();load();return c}
 catch(e){busy(btn,false);toast(`❌ ${label} : ${e.message}`,'crit',0)}
}
function settleWatched(){
 for(const cid in watch){const c=(S.commands||[]).find(x=>x.id===cid);if(!c||c.status==='pending')continue;
  const w=watch[cid];delete watch[cid];busy(w.btn,false);
  const res=c.result||{};const msg=res.result?.message||res.message||(res.result?JSON.stringify(res.result).slice(0,140):'');
  if(c.status==='done')toast(`✅ ${w.label} (${cid}) : ${msg||'fait'}`,'ok',10000);else toast(`❌ ${w.label} (${cid}) : ${res.error||c.error||'refusé'}`,'crit',0)}
 renderPending();
}
function renderPending(){const p=$('pending');if(!p)return;const n=Object.keys(watch).length;p.innerHTML=n?`<span class="pill warning">⏳ ${n} commande(s) en attente : ${Object.entries(watch).map(([c,w])=>w.label+' ('+c+')').join(', ')}</span>`:''}

// -- parcours de l'arborescence -------------------------------------------------------
let br={cid:null,busy:false,res:null,agent:null}, brPaths=[];const bp=p=>{brPaths.push(p);return brPaths.length-1};
async function browse(path,btn){if(!sel)return;br={cid:null,busy:true,res:br.agent===sel?br.res:null,agent:sel};renderDyn();
 const c=await cmd('browse',path?{path}:{},'parcours '+(path||'lecteurs'),btn);if(c)br.cid=c.id;else{br.busy=false;renderDyn()}}
function pick(path){const e=$('i-target');if(e)e.value=path;toast('cible : '+path,'ok',4000)}
function browserHtml(){
 if(br.agent!==sel)return '';brPaths=[];
 let h='<div class="card" style="margin-top:8px"><h2>Parcourir depuis le poste <span class="muted">(vu par le compte de l\'agent : pas les lecteurs réseau d\'une session ; taper \\\\serveur\\partage dans la cible puis Parcourir)</span></h2>';
 if(br.busy)h+='<div class="muted">⏳ attente de l\'agent (≤ 10 s)…</div>';
 const r=br.res;
 if(r){if(r.ok===false)h+=`<div class="critical">${esc(r.error)}</div>`;
  else{if(r.drives)h+='<div class="row">'+r.drives.map(d=>`<button class="sec" onclick="browse(brPaths[${bp(d.path)}],this)">${esc(d.path)} <span class="muted">${gb(d.free)} libres / ${gb(d.total)}</span></button>`).join('')+'</div>';
   if(r.path){h+=`<div><b>${esc(r.path)}</b> <span class="muted">${r.free!=null?gb(r.free)+' libres / '+gb(r.total):''}</span> <button onclick="pick(brPaths[${bp(r.path)}])">Choisir ce dossier comme cible</button> ${r.parent?`<button class="sec" onclick="browse(brPaths[${bp(r.parent)}],this)">↑ ${esc(r.parent)}</button>`:'<button class="sec" onclick="browse(null,this)">↑ lecteurs</button>'}</div>`;
    h+='<div style="max-height:220px;overflow:auto;margin-top:6px">'+(r.entries||[]).map(e=>`<div><button class="sec" style="padding:2px 8px" onclick="browse(brPaths[${bp(e.path)}],this)">📁 ${esc(e.name)}</button></div>`).join('')+(r.truncated?'<div class="muted">liste tronquée</div>':'')+((r.entries||[]).length?'':'<div class="muted">aucun sous-dossier</div>')+'</div>'}}}
 return h+'</div>';
}
function shareParam(){const u=(fv('i-sunc')||'').trim();if(!u)return undefined;const acct=(fv('i-suser')||'').trim();const m=acct.match(/^([^\\]+)\\(.+)$/);return {unc:u,user:m?m[2]:acct,domain:m?m[1]:undefined,password:fv('i-spass')||''}}
function autologonParam(){const u=(fv('p-alu')||'').trim(),p=fv('p-alp')||'';if(!u||!p)return undefined;const m=u.match(/^([^\\]+)\\(.+)$/);if(m)return {domain:m[1],user:m[2],password:p};return {user:u,password:p}}

// -- chargement / rendu ---------------------------------------------------------------
async function load(){try{S=await (await fetch('/ui/state')).json()}catch(e){toast('central injoignable : '+e.message,'crit',5000);return}render()}
function setTab(t){tab=t;render()}
function selectAgent(a){sel=a;render()}
function render(){
 $('hdr').textContent=S.base+' · site '+S.site+' · '+S.agents.length+' agent(s)'+(S.ca_sha256?' · CA '+S.ca_sha256.slice(0,16)+'…':' · HTTP clair');
 $('tok').textContent=S.token;$('ol-win').textContent=S.one_liners.windows;$('ol-lin').textContent=S.one_liners.linux;
 $('ol-manual').textContent=S.package?`cd $env:USERPROFILE\\Downloads\ncurl.exe ${S.ca_sha256?'-k ':''}-o ${S.package.name} ${S.base}/package\ntar -xzf ${S.package.name}\ncd ${S.package.name.replace(/\.tar\.gz$/,'')}\npowershell -NoProfile -ExecutionPolicy Bypass -File .\\windows\\install.ps1 -EnrollToken ${S.token} -Central ${S.base} -Site ${S.site}${S.ca_sha256?' -CaFingerprint '+S.ca_sha256:' -SystemCa'}${S.plugins.length?' -EnablePlugin '+S.plugins.join(','):''}`:'archive absente';
 $('pkg').textContent=S.package?('archive '+S.package.name+' ('+Math.round(S.package.size/1024)+' Ko)'):'archive absente (--no-archive)';
 $('agents').innerHTML=S.agents.map(a=>`<tr class="agent ${a.agent_id===sel?'sel':''}" onclick="selectAgent('${esc(a.agent_id)}')"><td><b>${esc(a.agent_id)}</b><br><span class="muted">${esc(a.platform||'')}</span></td><td>${ago(a.last_seen)}</td><td>${esc(a.ip||'')}</td><td>${esc(a.hostname||'')}</td></tr>`).join('')||'<tr><td colspan=4 class="muted">aucun</td></tr>';
 $('events').innerHTML=S.events.map(e=>`<div><span class="muted">${esc((e.at||'').replace('T',' ').slice(0,19))}</span> <span class="pill ${esc(e.severity)}">${esc(e.kind)}</span> <b>${esc(e.agent_id)}</b> ${esc(e.message)}${e.details&&Object.keys(e.details).length?` <details><summary>détails</summary><pre>${esc(JSON.stringify(e.details,null,1))}</pre></details>`:''}</div>`).join('')||'<span class="muted">aucun</span>';
 settleWatched();
 if(!sel||!S.agents.find(a=>a.agent_id===sel)){$('panel').innerHTML='<div class="card muted">Choisir un agent dans la liste (il apparaît après son enrôlement, ~1 min).</div>';panelKey='';return}
 if(br.cid){const c=S.commands.find(x=>x.id===br.cid);if(c&&c.status!=='pending'){br.res=c.result?(c.result.result||{ok:false,error:c.result.error||'sans résultat'}):{ok:false,error:'sans résultat'};br.busy=false;br.cid=null}}
 const key=sel+'|'+tab;if(key!==panelKey){panelKey=key;renderPanel()}
 renderDyn();
}
const TABS=['poste','image','système','lanceurs','watchdog','sondes','commandes'];
function renderPanel(){
 const cmds=S.commands.filter(c=>c.agent_id===sel);
 let h=`<div class="card"><h2>${esc(sel)} <span class="muted" id="agent-hdr"></span></h2><div id="pending"></div>
 <div class="tabs">${TABS.map(t=>`<button class="${t===tab?'on':''}" onclick="setTab('${t}')">${t}</button>`).join('')}</div>`;
 if(tab==='poste'){h+=`<div class="row"><button onclick="cmd('collect_now',{},'collecte',this)">Collecter maintenant</button></div>
  <h2>Alimentation</h2><div class="row"><label>action<select id="p-act"><option value="reboot">redémarrer</option><option value="shutdown">arrêter</option><option value="cancel">annuler</option></select></label>
  <label>délai (s)<input id="p-delay" value="60"></label><label>message<input id="p-msg" value="Redémarrage demandé par la supervision"></label><label><input type="checkbox" id="p-force" style="width:auto"> forcer (session ouverte)</label>
  <label>rouvrir la session après le redémarrage (une fois) : compte<input id="p-alu" placeholder="pilote ou DOMAINE\\pilote"></label><label>mot de passe<input id="p-alp" type="password" autocomplete="new-password"></label>
  <label>prochain démarrage (multi-amorçage, via UEFI)<select id="p-target"><option value="">normal</option><option value="windows">→ Windows (saute GRUB, une fois)</option><option value="linux">→ Linux / GRUB (une fois)</option><option value="firmware">→ réglages UEFI</option></select></label>
  <button onclick="cmd('power_action',{action:fv('p-act'),delay_seconds:+fv('p-delay'),message:fv('p-msg'),force:fv('p-force'),target:fv('p-target')||undefined,autologon:autologonParam()},'alimentation '+fv('p-act'),this)">Envoyer</button></div>
  <div class="muted">Réouverture de session : AutoLogonCount=1 de Winlogon (mot de passe effacé du registre par Windows après cette unique ouverture, vérifié par l'agent au démarrage suivant) ; compte local ou de domaine avec mot de passe. Le mot de passe ne fait que passer : masqué ici dès l'envoi, jamais dans les journaux.</div>
  <h2>Réveil réseau (paquet magique émis par cet agent)</h2><div class="row"><label>MAC du poste à réveiller<input id="w-mac" placeholder="AA:BB:CC:DD:EE:FF"></label><label>diffusion<input id="w-bc" value="255.255.255.255"></label>
  <button onclick="cmd('wol',{mac:fv('w-mac'),broadcast:fv('w-bc')},'réveil',this)">Réveiller</button></div>
  <h2>Banc de charge (introspection)</h2><div class="row"><label>minutes<input id="b-min" value="10"></label><label>facteur de cadence<input id="b-f" value="6"></label>
  <button onclick="cmd('bench',{minutes:+fv('b-min'),factor:+fv('b-f')},'banc',this)">Lancer</button><button class="sec" onclick="cmd('bench',{stop:true},'arrêt du banc',this)">Arrêter</button></div>
  <div id="dyn"></div>`}
 if(tab==='image'){h+=`<h2>Image complète du poste à chaud (Disk2vhd, VSS)</h2>
  <div class="row"><label>dossier cible (partage ou disque local)<input id="i-target" placeholder="\\\\nas\\images\\p2v ou D:\\images"></label><label>nom<input id="i-name" placeholder="(nom du poste)"></label>
  <label>lecteurs<input id="i-drives" value="C:"></label></div><div class="row"><label>URL de disk2vhd64.exe<input id="i-url" value="https://live.sysinternals.com/disk2vhd64.exe"></label><label>SHA-256 attendu (optionnel)<input id="i-sha"></label>
  <label><input type="checkbox" id="i-force" style="width:auto"> forcer (ignorer l'espace)</label></div>
  <div class="row"><label>partage du serveur monté par l'agent (écriture directe, sans copie locale) : UNC<input id="i-sunc" placeholder="\\\\192.168.1.178\\p2v"></label><label>compte<input id="i-suser" placeholder="p2v ou DOMAINE\\p2v"></label><label>mot de passe<input id="i-spass" type="password" autocomplete="new-password"></label></div>
  <div class="muted">Avec un partage : la cible doit être sous l'UNC (ex. <code>\\\\serveur\\p2v\\pc1</code>), Disk2vhd écrit directement dessus, l'agent monte le partage le temps de l'image puis le démonte ; le mot de passe est masqué dès l'envoi. Sans partage : image locale puis transfert par le canal de l'agent.</div>
  <div class="row"><label><input type="checkbox" id="i-transfer" style="width:auto" checked> transférer ensuite vers ce serveur (dossier <code id="i-imgdir"></code>) — ignoré avec un partage</label><label><input type="checkbox" id="i-delete" style="width:auto"> supprimer l'image du poste après transfert vérifié</label>
  <button onclick="cmd('image_host',{target:fv('i-target'),name:fv('i-name')||undefined,drives:fv('i-drives'),tool_url:fv('i-url'),tool_sha256:fv('i-sha')||undefined,force:fv('i-force'),transfer:fv('i-transfer'),delete_after:fv('i-delete'),share:shareParam()},'image',this)">Lancer l'image</button></div>
  <div class="row"><label>image déjà présente sur le poste à (re)transférer<input id="i-existing" placeholder="d:\\papa\\PC-20260926.vhdx"></label><button class="sec" onclick="cmd('image_transfer',{path:fv('i-existing'),delete_after:fv('i-delete')},'transfert',this)">Transférer / reprendre</button></div>
  <div class="row"><button class="sec" onclick="browse(fv('i-target')||null,this)">Parcourir depuis le poste…</button></div>
  <div class="muted">Refusé si BitLocker protège un volume visé, si la cible manque d'espace (utilisé × 1,1) ou si une image est déjà en cours. 30 à 60 min pour 200-300 Go en Gigabit ; le poste reste en service.</div>
  <div id="dyn"></div>`}
 if(tab==='watchdog'){const lw=cmds.find(c=>c.type==='watchdog_config'&&c.result&&c.result.result&&c.result.result.config);const apps=lw?lw.result.result.config.apps:[];
  h+=`<h2>Chien de garde applicatif</h2><div class="muted">Une application par ligne : <code>identifiant | processus attendu | commande de relance | heures HH:MM-HH:MM (optionnel)</code></div>
  <textarea id="wd-txt" rows="5" placeholder="pilotage | pilotage.exe | C:\\Apps\\pilotage.exe | 07:00-20:00">${esc(apps.map(a=>[a.id,a.process,a.command||'',a.hours||''].join(' | ')).join('\n'))}</textarea>
  <div class="row"><button onclick="cmd('watchdog_config',{apps:fv('wd-txt').split('\\n').filter(l=>l.trim()).map(l=>{const p=l.split('|').map(s=>s.trim());return {id:p[0],label:p[0],process:p[1],command:p[2]||null,hours:p[3]||null}})},'chien de garde',this)">Appliquer</button><button class="sec" onclick="cmd('watchdog_config',{apps:[]},'chien de garde (vide)',this)">Tout retirer</button></div>
  <div id="dyn"></div>`}
 if(tab==='système'){h+=`<h2>Windows Update</h2><div class="row"><button class="sec" onclick="cmd('windows_update',{action:'status'},'état des mises à jour',this)">Relever l'état</button>
  <label>KB à installer (vide = toutes)<input id="u-kbs" placeholder="KB5049624, KB5050000"></label><label><input type="checkbox" id="u-reboot" style="width:auto"> redémarrer ensuite si requis (forcé, 60 s)</label>
  <button onclick="if(confirm('Installer maintenant ? (peut durer longtemps, le poste reste en service)'))cmd('windows_update',{action:'install',kbs:fv('u-kbs'),reboot:fv('u-reboot')},'installation des mises à jour',this)">Installer maintenant</button></div>
  <div class="row"><label>installation programmée (heure du poste)<input id="u-at" type="datetime-local"></label><button class="sec" onclick="if(!fv('u-at')){toast('choisir une date-heure','warn');return}cmd('windows_update',{action:'install',kbs:fv('u-kbs'),reboot:fv('u-reboot'),at:fv('u-at')},'mises à jour programmées',this)">Programmer</button></div>
  <div class="muted">API Windows Update du poste (COM), sans module : l'état liste les mises à jour en attente et l'historique ; l'installation tourne détachée, suivie par les événements <code>update-started / update-finished</code>. Une commande programmée est conservée par l'agent et exécutée à l'heure dite (événement <code>deferred-run</code>).</div>
  <h2>Protection (pare-feu, Microsoft Defender)</h2><div class="row"><button class="sec" onclick="cmd('protection',{},'état de la protection',this)">Relever l'état</button>
  <label>profils du pare-feu<input id="f-prof" value="Domain,Private,Public"></label>
  <button class="sec" onclick="if(confirm('Désactiver le pare-feu Windows sur ces profils ?'))cmd('protection',{firewall:'off',profiles:fv('f-prof')},'pare-feu OFF',this)">Pare-feu OFF</button><button onclick="cmd('protection',{firewall:'on',profiles:fv('f-prof')},'pare-feu ON',this)">Pare-feu ON</button>
  <button class="sec" onclick="if(confirm('Désactiver la protection en temps réel de Defender ? (refusé si la protection contre les falsifications est active)'))cmd('protection',{defender:'off'},'Defender OFF',this)">Defender temps réel OFF</button><button onclick="cmd('protection',{defender:'on'},'Defender ON',this)">Defender temps réel ON</button></div>
  <div class="muted">Un antivirus tiers (AVG, ESET…) est seulement signalé : il se pilote dans sa propre console.</div>
  <h2>Bureau à distance (RDP intégré)</h2><div class="row"><button class="sec" onclick="cmd('remote_desktop',{action:'status'},'état RDP',this)">Relever l'état</button>
  <button onclick="if(confirm('Activer le Bureau à distance ? Tu te connecteras avec TES identifiants ; la NLA reste exigée.'))cmd('remote_desktop',{action:'enable'},'RDP activé',this)">Activer</button>
  <button class="sec" onclick="cmd('remote_desktop',{action:'disable'},'RDP désactivé',this)">Désactiver</button></div>
  <div class="muted">Active le service Terminal Server et la règle de pare-feu « Remote Desktop » ; aucun compte ni mot de passe n'est créé ici. Connexion depuis un client RDP avec un compte déjà autorisé sur le poste. Toute bascule est journalisée.</div>
  <h2>Mise à jour de l'agent</h2><div class="row"><span class="muted">archive du serveur : <code>${S.package?esc(S.package.version||S.package.name):'aucune'}</code></span>
  <button onclick="if(S.package&&S.package.version&&confirm('Mettre à jour cet agent vers '+S.package.version+' ? Il se réinstalle et redémarre seul (configuration et secret conservés).'))cmd('update',{version:S.package.version,sha256:S.package.sha256,url:'/package'},'mise à jour '+((S.package||{}).version||''),this)" ${S.package&&S.package.version?'':'disabled'}>Mettre à jour maintenant</button></div>
  <div class="muted">Le central pousse la version, l'agent télécharge par son propre canal (TLS + CA épinglée), vérifie le SHA-256 et relance l'installeur en <code>--upgrade</code> — sans intervention sur le poste. Suivi : événements <code>agent-update-started / agent-updated</code>.</div>
  <h2>Logiciels</h2><div class="row"><label>action<select id="s-act"><option value="install">installer</option><option value="uninstall">désinstaller</option></select></label><label>paquet (winget « Editeur.Produit », choco, apt…)<input id="s-pkg" placeholder="Mozilla.Firefox"></label><label>gestionnaire<select id="s-mgr"><option value="">auto</option><option>winget</option><option>choco</option><option>apt</option><option>dnf</option><option>brew</option></select></label>
  <button onclick="cmd('software_action',{action:fv('s-act'),package:fv('s-pkg'),manager:fv('s-mgr')||undefined},fv('s-act')+' '+fv('s-pkg'),this)">Exécuter</button></div>
  <div class="muted">Mode silencieux, paquet strictement validé, jamais de script arbitraire. Sous Windows, winget n'est pas toujours disponible pour le compte SYSTEM (application par utilisateur) : choco est alors le gestionnaire de secours.</div>
  <div id="dyn"></div>`}
 if(tab==='lanceurs'||tab==='sondes')h+='<div id="dyn"></div>';
 if(tab==='commandes'){h+=`<h2>Commande brute</h2><div class="row"><label>type<select id="r-type">${['collect_now','power_action','wol','startup_action','watchdog_config','bench','image_host','image_transfer','browse','windows_update','protection','software_action','block_all','unblock_all','update'].map(t=>`<option>${t}</option>`).join('')}</select></label><label>paramètres (JSON)<input id="r-params" value="{}"></label><button onclick="try{cmd(fv('r-type'),JSON.parse(fv('r-params')||'{}'),'commande '+fv('r-type'),this)}catch(e){toast('JSON invalide : '+e.message,'crit',0)}">Envoyer</button></div>
  <div id="dyn"></div>
  <details style="margin-top:14px"><summary>zone sensible</summary><div class="row"><button class="sec" onclick="if(confirm('Oublier cet agent ? Son secret est supprimé : il devra être réenrôlé (installeur avec -EnrollToken).'))post('/ui/forget',{agent_id:sel}).then(()=>{sel=null;toast('agent oublié','warn');load()})">Oublier cet agent</button></div></details>`}
 h+='</div>';$('panel').innerHTML=h;renderPending();
}
function renderDyn(){
 const d=$('dyn');if(!d)return;
 const m=S.measurements[sel]||{}, host=(m.host||{}).data||{}, hs=host.system||host, st=(m.startup||{}).data||{}, self=(m['agent-self']||{}).data||{}, pt=self.point||{}, wd=(m.watchdog||{}).data||{};
 const cmds=S.commands.filter(c=>c.agent_id===sel), img=S.events.filter(e=>e.agent_id===sel&&/^image-/.test(e.kind));
 const ah=$('agent-hdr');if(ah)ah.textContent=`— ${hs.hostname||''} ${typeof hs.os==='string'?hs.os:(hs.os||{}).name||''} · CPU ${(host.cpu||{}).percent??'?'} % · mémoire ${(host.memory||{}).used_percent??'?'} % · empreinte agent ${pt.cpu_core_percent??'?'} % d'un cœur / ${pt.rss_bytes?Math.round(pt.rss_bytes/1048576):'?'} Mo · vu ${ago((S.agents.find(a=>a.agent_id===sel)||{}).last_seen)}`;
 let h='';
 if(tab==='poste')h=`<details><summary>dernière collecte hôte (brut, ${ago((m.host||{}).at)})</summary><pre>${esc(JSON.stringify(host,null,1))}</pre></details><details><summary>empreinte de l'agent (brut)</summary><pre>${esc(JSON.stringify(self,null,1))}</pre></details>`;
 if(tab==='image'){const last=img[0];const idir=$('i-imgdir');if(idir)idir.textContent=S.images_dir||'';
  const up=S.events.filter(e=>e.agent_id===sel&&/^image-upload-/.test(e.kind))[0];
  h=browserHtml()+`<h2 style="margin-top:10px">Suivi</h2>${up?`<div><span class="pill ${esc(up.severity)}">${esc(up.kind)}</span> ${esc(up.message)} <span class="muted">${ago(up.at)}</span></div>`:''}${last?`<div><span class="pill ${esc(last.severity)}">${esc(last.kind)}</span> ${esc(last.message)} <span class="muted">${ago(last.at)}</span></div>`:'<div class="muted">aucune image lancée</div>'}
  ${img.slice(0,12).map(e=>`<div class="muted">${esc((e.at||'').replace('T',' ').slice(0,19))} ${esc(e.kind)} — ${esc(e.message)}</div>`).join('')}<h2 style="margin-top:10px">Images reçues sur ce serveur</h2>${(S.images||[]).filter(i=>i.agent_id===sel).map(i=>`<div>${i.complete?'✅':'⏳'} <code>${esc(i.path)}</code> <span class="muted">${gb(i.size)} · ${ago(i.at)}</span></div>`).join('')||'<div class="muted">aucune</div>'}
  <h2 style="margin-top:10px">Import Proxmox</h2><pre>${esc(S.runbook)}</pre>`}
 if(tab==='lanceurs'){const items=st.items||[];h=`<h2>Lanceurs au démarrage <span class="muted">(${items.length}, collecte ${ago((m.startup||{}).at)})</span></h2>
  <table><thead><tr><th>type</th><th>nom</th><th>commande</th><th>état</th><th></th></tr></thead><tbody>${items.map((it,i)=>`<tr><td>${esc(it.kind)}<br><span class="muted">${esc(it.scope||'')}</span></td><td>${esc(it.name)}</td><td><code>${esc((it.command||'').slice(0,120))}</code></td><td>${it.enabled===false?'<span class="warning">désactivé</span>':'<span class="ok">actif</span>'}</td>
  <td>${['run','folder','task','service'].includes(it.kind)?`<button class="sec" onclick="toggleStartup(${i},this)">${it.enabled===false?'activer':'désactiver'}</button>`:''}</td></tr>`).join('')||'<tr><td colspan=5 class="muted">pas encore collecté (Windows seulement, toutes les 30 min ou après « Collecter maintenant »)</td></tr>'}</tbody></table>`}
 if(tab==='système'){const wu=(m.winupdate||{}).data||{}, pr=(m.protection||{}).data||{}, rdp=(m.rdp||{}).data||{}, defer=S.events.filter(e=>e.agent_id===sel&&/^(deferred|update-|agent-update|command-rdp)/.test(e.kind)).slice(0,10);
  const R={0:'non démarré',1:'en cours',2:'réussi',3:'réussi avec erreurs',4:'échec',5:'annulé'};
  h=`<h2>État Windows Update <span class="muted">(${(m.winupdate||{}).at?ago((m.winupdate||{}).at):'jamais relevé'})</span></h2>`;
  if(wu.error)h+=`<div class="critical">${esc(wu.error)}</div>`;
  if(wu.pending){h+=`<div>${wu.pending.length} en attente${wu.reboot_required?' · <span class="warning">redémarrage requis</span>':''}${wu.au_level!=null?' · réglage auto : '+esc({1:'désactivé',2:'notifier',3:'télécharger',4:'planifié'}[wu.au_level]||wu.au_level):''}</div>
   <table><thead><tr><th>KB</th><th>titre</th><th>Mo</th><th>gravité</th><th></th></tr></thead><tbody>${wu.pending.map(u=>`<tr><td>${esc(u.kb)}</td><td>${esc(u.title)}</td><td>${esc(u.size_mb)}</td><td>${esc(u.severity||'')}</td><td>${u.downloaded?'téléchargée':''}${u.reboot_required?' redémarrage':''}</td></tr>`).join('')||'<tr><td colspan=5 class="muted">rien en attente</td></tr>'}</tbody></table>`;
   if(wu.install)h+=`<div style="margin-top:6px"><b>Dernière installation :</b> ${wu.install.count||0} mise(s) à jour, résultat ${esc(R[wu.install.result]??wu.install.message??'')}${wu.install.reboot_required?' · redémarrage requis':''}</div>`;
   h+=`<details><summary>historique (${(wu.history||[]).length})</summary>${(wu.history||[]).map(x=>`<div class="muted">${esc((x.date||'').replace('T',' ').slice(0,16))} ${esc(R[x.result]||x.result)} — ${esc(x.title)}</div>`).join('')}</details>`}
  h+=`<h2 style="margin-top:10px">Protection <span class="muted">(${(m.protection||{}).at?ago((m.protection||{}).at):'jamais relevée'})</span></h2>`;
  if(pr.firewall)h+=`<div>pare-feu : ${pr.firewall.map(f=>`${esc(f.profile)} <b class="${f.enabled?'ok':'critical'}">${f.enabled?'actif':'INACTIF'}</b>`).join(' · ')}</div>`;
  if(pr.defender)h+=`<div>Defender temps réel : <b class="${pr.defender.realtime?'ok':'critical'}">${pr.defender.realtime?'actif':'INACTIF'}</b>${pr.defender.tamper_protected?' · protection contre les falsifications active':''}${pr.defender.signature_age_days!=null?' · signatures : '+esc(pr.defender.signature_age_days)+' j':''}</div>`;
  if(pr.third_party&&pr.third_party.length)h+=`<div>antivirus tiers : ${pr.third_party.map(t=>esc(t.name)).join(', ')}</div>`;
  if(pr.errors&&pr.errors.length)h+=`<div class="critical">${pr.errors.map(esc).join(' ; ')}</div>`;
  h+=`<h2 style="margin-top:10px">Bureau à distance <span class="muted">(${(m.rdp||{}).at?ago((m.rdp||{}).at):'jamais relevé'})</span></h2>`;
  if(Object.keys(rdp).length)h+=`<div>RDP <b class="${rdp.enabled?'ok':''}">${rdp.enabled?'ACTIVÉ':'désactivé'}</b>${rdp.enabled?` · pare-feu <b class="${rdp.firewall_enabled?'ok':'critical'}">${rdp.firewall_enabled?'ouvert':'FERMÉ'}</b> · NLA ${rdp.nla?'exigée':'<span class="warning">désactivée</span>'} · port ${esc(rdp.port)}`:''}${rdp.rdp_users&&rdp.rdp_users.length?' · autorisés : '+rdp.rdp_users.map(esc).join(', '):''}</div>`;
  const dj=(S.agents.find(a=>a.agent_id===sel)||{});
  h+=`<h2 style="margin-top:10px">Programmées / suivi</h2>${defer.map(e=>`<div class="muted">${esc((e.at||'').replace('T',' ').slice(0,19))} <span class="pill ${esc(e.severity)}">${esc(e.kind)}</span> ${esc(e.message)}</div>`).join('')||'<div class="muted">rien</div>'}`}
 if(tab==='watchdog')h=`<details open><summary>dernier état (${ago((m.watchdog||{}).at)})</summary><pre>${esc(JSON.stringify(wd,null,1))}</pre></details>`;
 if(tab==='sondes')h=`<h2>Mesures reçues</h2>`+(Object.keys(m).sort().map(t=>`<details><summary>${esc(t)} — ${ago(m[t].at)} ${m[t].ok===false?'<span class="warning">erreur</span>':''}</summary><pre>${esc(JSON.stringify(m[t].data??m[t].error,null,1))}</pre></details>`).join('')||'<span class="muted">rien encore</span>');
 if(tab==='commandes')h=`<h2>Historique</h2><table><thead><tr><th>id</th><th>type</th><th>état</th><th>résultat</th></tr></thead><tbody>${cmds.map(c=>`<tr><td>${esc(c.id)}<br><span class="muted">${ago(c.created_at)}</span></td><td>${esc(c.type)}<br><code>${esc(JSON.stringify(c.params)).slice(0,100)}</code></td><td class="${c.status==='done'?'ok':c.status==='failed'?'critical':'warning'}">${c.status==='pending'?'⏳ en attente':esc(c.status)}</td><td><pre style="max-height:120px">${esc(c.result?JSON.stringify(c.result.result??c.result.error??c.result,null,1):'')}</pre></td></tr>`).join('')||'<tr><td colspan=4 class="muted">aucune</td></tr>'}</tbody></table>`;
 const open=new Set([...d.querySelectorAll('details[open]')].map(x=>x.querySelector('summary')?.textContent.split(' — ')[0].split(' (')[0]));
 d.innerHTML=h;
 d.querySelectorAll('details').forEach(x=>{const k=x.querySelector('summary')?.textContent.split(' — ')[0].split(' (')[0];if(open.has(k))x.open=true});
}
function toggleStartup(i,btn){const items=(((S.measurements[sel]||{}).startup||{}).data||{}).items||[];const it=items[i];if(!it)return;cmd('startup_action',{kind:it.kind,name:it.name,scope:it.scope||'machine',enable:it.enabled===false},(it.enabled===false?'activer ':'désactiver ')+it.name,btn)}
load();setInterval(load,5000);
