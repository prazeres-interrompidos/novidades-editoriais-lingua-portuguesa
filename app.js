const countries=[['PT','🇵🇹','Portugal'],['BR','🇧🇷','Brasil'],['AO','🇦🇴','Angola'],['MZ','🇲🇿','Moçambique'],['CV','🇨🇻','Cabo Verde'],['GW','🇬🇼','Guiné-Bissau'],['ST','🇸🇹','São Tomé e Príncipe'],['TL','🇹🇱','Timor-Leste']];
let books=[],sources=[];const $=s=>document.querySelector(s);
async function load(){
  // Em file:// o navegador bloqueia fetch() de ficheiros locais.
  // O GitHub Actions gera data/books.js e data/sources.js para permitir
  // que o catálogo também funcione quando index.html é aberto directamente.
  if (window.__EDITORIAL_DATA__) {
    books=window.__EDITORIAL_DATA__.books||[];
    sources=window.__EDITORIAL_DATA__.sources||[];
  } else {
    const [b,s]=await Promise.all([fetch('data/books.json').then(r=>r.json()),fetch('data/sources.json').then(r=>r.json())]);
    books=b;sources=s;
  }
  renderFilters();renderSources();render();
}
function renderFilters(){const c=$('#country');countries.forEach(([id,f,n])=>c.insertAdjacentHTML('beforeend',`<option value="${id}">${f} ${n}</option>`));const gs=[...new Set(books.map(x=>x.genre).filter(Boolean))].sort((a,b)=>a.localeCompare(b));gs.forEach(g=>$('#genre').insertAdjacentHTML('beforeend',`<option>${esc(g)}</option>`));$('#countries').innerHTML=countries.map(([id,f,n])=>`<button data-country="${id}">${f} ${n}</button>`).join('');document.querySelectorAll('[data-country]').forEach(b=>b.onclick=()=>{$('#country').value=b.dataset.country;render()});}
function renderSources(){const names={institutional:'Institucional',retailer:'Livraria/agregador',publisher:'Editora'};$('#sourceList').innerHTML=sources.map(s=>`<div class="source-item"><strong>${esc(s.name)}</strong><small>${esc(s.country_name)} · ${esc(names[s.type]||s.type)} · ${s.automatic?'Automatizável':'Referência'}</small></div>`).join('')}
function render(){const q=$('#q').value.trim().toLowerCase(),c=$('#country').value,st=$('#status').value,g=$('#genre').value;let out=books.filter(x=>{let ok=(!q||[x.title,x.author,x.publisher,x.isbn].join(' ').toLowerCase().includes(q))&&(!c||x.country===c)&&(!st||x.status===st)&&(!g||x.genre===g)return ok}).sort((a,b)=>(b.date||'').localeCompare(a.date||''));$('#count').textContent=`${out.length} ${out.length===1?'livro':'livros'}`;$('#sectionTitle').textContent=st==='new'?'Livros publicados':'Livros publicados';$('#grid').innerHTML=out.map(card).join('');$('#empty').classList.toggle('hidden',out.length>0)}
function card(x){const c=countries.find(z=>z[0]===x.country)||['','',''];return `<article class="card"><div class="cover">${x.cover?`<img src="${esc(x.cover)}" alt="Capa de ${esc(x.title)}" loading="lazy" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="placeholder" style="display:none">${esc(x.title)}</div>`:`<div class="placeholder">${esc(x.title)}</div>`}<span class="flag">${c[1]} ${c[2]}</span>${x.status==='upcoming'?'<span class="badge">PRÓXIMO</span>':'<span class="badge">NOVO</span>'}</div><div class="body"><h3>${esc(x.title)}</h3><div class="author">${esc(x.author||'Autor não indicado')}</div><div class="meta"><strong>${esc(x.publisher||'Editora não indicada')}</strong><br>${x.date?formatDate(x.date):'Data não indicada'} · ${esc(x.genre||'Livro')}</div><div class="source">Fonte: <a href="${esc(x.source_url)}" target="_blank" rel="noopener">${esc(x.source_name||'fonte original')}</a></div></div></article>`}
function formatDate(s){return String(s||'').match(/\b(?:19|20)\d{2}\b/)?.[0]||s||'Ano não indicado'}
function esc(s=''){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
['q','country','status','genre'].forEach(id=>$( '#'+id).addEventListener(id==='q'?'input':'change',render));
load();
