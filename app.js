const countries=[['PT','🇵🇹','Portugal'],['BR','🇧🇷','Brasil'],['AO','🇦🇴','Angola'],['MZ','🇲🇿','Moçambique'],['CV','🇨🇻','Cabo Verde'],['GW','🇬🇼','Guiné-Bissau'],['ST','🇸🇹','São Tomé e Príncipe'],['TL','🇹🇱','Timor-Leste']];
let books=[],sources=[];const $=s=>document.querySelector(s);

async function load(){
  if(window.__EDITORIAL_DATA__){
    books=window.__EDITORIAL_DATA__.books||[];
    sources=window.__EDITORIAL_DATA__.sources||[];
  }else{
    const [b,s]=await Promise.all([
      fetch('data/books.json').then(r=>r.json()),
      fetch('data/sources.json').then(r=>r.json())
    ]);
    books=b;sources=s;
  }
  renderFilters();renderSources();render();
}

function renderFilters(){
  const c=$('#country');
  countries.forEach(([id,f,n])=>c.insertAdjacentHTML('beforeend',`<option value="${id}">${f} ${n}</option>`));
  const gs=[...new Set(books.map(x=>x.genre).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  gs.forEach(g=>$('#genre').insertAdjacentHTML('beforeend',`<option>${esc(g)}</option>`));
  $('#countries').innerHTML=countries.map(([id,f,n])=>`<button data-country="${id}">${f} ${n}</button>`).join('');
  document.querySelectorAll('[data-country]').forEach(b=>b.onclick=()=>{$('#country').value=b.dataset.country;render()});
}

function renderSources(){
  const names={institutional:'Institucional',retailer:'Livraria/agregador',publisher:'Editora'};
  $('#sourceList').innerHTML=sources.map(s=>`<div class="source-item"><strong>${esc(s.name)}</strong><small>${esc(s.country_name)} · ${esc(names[s.type]||s.type)} · ${s.automatic?'Automática':'Referência'}</small></div>`).join('');
}

function render(){
  const q=$('#q').value.trim().toLowerCase(),c=$('#country').value,g=$('#genre').value;
  let out=books.filter(x=>
    (!q||[x.title,x.author,x.publisher,x.isbn].join(' ').toLowerCase().includes(q))&&
    (!c||x.country===c)&&(!g||x.genre===g)
  ).sort((a,b)=>(a.title||'').localeCompare(b.title||'','pt-PT'));

  $('#count').textContent=`${out.length} ${out.length===1?'livro':'livros'}`;
  $('#sectionTitle').textContent='Livros publicados em 2026';
  $('#grid').innerHTML=out.map(card).join('');
  $('#empty').classList.toggle('hidden',out.length>0);
}

function card(x){
  const c=countries.find(z=>z[0]===x.country)||['','',''];
  return `<article class="card"><div class="cover">${
    x.cover?`<img src="${esc(x.cover)}" alt="Capa de ${esc(x.title)}" loading="lazy" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="placeholder" style="display:none">${esc(x.title)}</div>`:
    `<div class="placeholder">${esc(x.title)}</div>`
  }<span class="flag">${c[1]} ${c[2]}</span><span class="badge">2026</span></div><div class="body"><h3>${esc(x.title)}</h3><div class="author">${esc(x.author||'Autor não indicado')}</div><div class="meta"><strong>${esc(x.publisher||'Editora não indicada')}</strong><br>2026 · ${esc(x.genre||'Livro')}</div><div class="source">Fonte: <a href="${esc(x.source_url)}" target="_blank" rel="noopener">${esc(x.source_name||'fonte original')}</a></div></div></article>`;
}

function esc(s=''){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
['q','country','genre'].forEach(id=>$('#'+id).addEventListener(id==='q'?'input':'change',render));
load();
