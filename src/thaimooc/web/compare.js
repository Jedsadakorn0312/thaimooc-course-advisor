'use strict';
const el = id => document.getElementById(id);
let savedComparison;
let activeRequest;
let sequence = 0;
let available = false;

function sourceUrl(url) {
  try { const u = new URL(url); return u.protocol === 'https:' && ['thaimooc.ac.th','www.thaimooc.ac.th','thaimooc.org','www.thaimooc.org'].includes(u.hostname) ? u.href : null; } catch { return null; }
}

function renderMethod(container, result, shared) {
  const fragment = document.createDocumentFragment();
  result.results.forEach((item, index) => {
    const card = el('rank-template').content.cloneNode(true);
    const c = item.course;
    card.querySelector('.rank-index').textContent = String(index+1).padStart(2,'0');
    card.querySelector('.rank-category').textContent = c.category || 'ไม่ระบุหมวด';
    card.querySelector('.shared-tag').hidden = !shared.has(c.course_id);
    card.querySelector('.rank-title').textContent = c.title;
    card.querySelector('.rank-institution').textContent = c.institution || 'ไม่ระบุสถาบัน';
    card.querySelector('.rank-duration').textContent = c.duration_hours == null ? 'ไม่ระบุเวลา' : `${c.duration_hours} ชั่วโมง`;
    card.querySelector('.rank-level').textContent = c.level || 'ไม่ระบุระดับ';
    card.querySelector('.rank-description').textContent = c.description;
    card.querySelector('.rank-score').textContent = `similarity ${Number(item.score).toFixed(4)}`;
    const link = card.querySelector('.rank-link'); const href = sourceUrl(c.url);
    if (href) { link.href = href; link.setAttribute('aria-label',`ดูวิชา ${c.title} (เปิดแท็บใหม่)`); } else { link.remove(); }
    fragment.append(card);
  });
  el(container).replaceChildren(fragment);
}

el('compare-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!available) return;
  const query = el('compare-query').value.trim();
  if (!query) { el('compare-query').setCustomValidity('กรุณาระบุเป้าหมายการเรียนรู้'); el('compare-query').reportValidity(); return; }
  activeRequest?.abort();
  const controller = new AbortController(); activeRequest = controller;
  const current = ++sequence;
  const payload = {query, top_k:Number(el('compare-k').value), max_hours:el('compare-hours').value ? Number(el('compare-hours').value):null, level:el('compare-level').value||null, category:el('compare-category').value||null};
  el('compare-submit').disabled = true;
  el('compare-error').hidden = true;
  el('comparison-results').hidden = true;
  savedComparison = null;
  el('compare-status').textContent = 'กำลังค้นหาด้วยทั้งสองวิธีบนรายวิชาชุดเดียวกัน…';
  const timer = setTimeout(()=>controller.abort(),60000);
  try {
    const response = await fetch('/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
    if (!response.ok) throw new Error(response.status===503 ? 'ระบบค้นหาความหมายยังไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง' : 'เปรียบเทียบไม่สำเร็จ กรุณาตรวจคำถามและลองอีกครั้ง');
    const data = await response.json();
    if (current!==sequence) return;
    savedComparison = data;
    renderMethod('tfidf-results',data.tfidf,new Set(data.overlap_ids));
    renderMethod('semantic-results',data.semantic,new Set(data.overlap_ids));
    el('tfidf-time').textContent = `${data.tfidf.elapsed_ms.toFixed(1)} ms`;
    el('semantic-time').textContent = `${data.semantic.elapsed_ms.toFixed(1)} ms`;
    el('matched-courses').textContent = `ผ่านตัวกรอง ${data.eligible_count} / ${data.corpus_count} วิชา`;
    el('overlap').textContent = `พบร่วมกัน ${data.overlap_count} วิชา`;
    el('corpus-id').textContent = `ชุดข้อมูลเดียวกัน · ${data.corpus_fingerprint.slice(0,10)}`;
    el('active-query').textContent = `“${data.query}” · Top ${data.top_k} ต่อวิธี`;
    el('comparison-empty').hidden = data.eligible_count > 0;
    el('comparison-results').hidden = false;
    el('compare-status').textContent = 'เปรียบเทียบแล้ว — ผลด้านล่างเป็นอันดับการค้นหา ยังไม่มีคะแนนตัดสินความเกี่ยวข้องจากคนตรวจ';
    el('comparison-title').focus({preventScroll:true});
    el('comparison-results').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  } catch(error) {
    if (current!==sequence) return;
    el('compare-error').hidden = false;
    el('compare-error').textContent = error.name==='AbortError' ? 'การเปรียบเทียบใช้เวลานานเกินไป กรุณาลองอีกครั้ง' : error.message;
    el('compare-status').textContent = '';
  } finally { clearTimeout(timer); if(current===sequence) el('compare-submit').disabled=!available; }
});
el('compare-query').addEventListener('input',()=>el('compare-query').setCustomValidity(''));
document.querySelectorAll('[data-example]').forEach(button=>button.addEventListener('click',()=>{
  el('compare-query').value=button.dataset.example; el('compare-query').setCustomValidity(''); el('compare-form').requestSubmit();
}));
el('download-comparison').addEventListener('click',()=>{
  if(!savedComparison) return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(savedComparison,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='thaimooc-search-comparison.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});

async function initialize() {
  try {
    const responses=await Promise.all([fetch('/catalog'),fetch('/health')]);
    if(responses.some(r=>!r.ok)) throw new Error('status');
    const [catalog,health]=await Promise.all(responses.map(r=>r.json()));
    el('dataset-summary').textContent=`${catalog.count} วิชา · ${catalog.categories.length} หมวด`;
    for(const [id,values] of [['compare-level',catalog.levels],['compare-category',catalog.categories]]) {
      values.forEach(value=>{const o=document.createElement('option');o.value=value;o.textContent=value;el(id).append(o);});
    }
    available=health.semantic_available===true;
    el('model-state').textContent=available?'ทั้งสองวิธีพร้อมทดลอง':'Semantic Search ยังไม่พร้อมใช้งาน';
    el('compare-submit').disabled=!available;
  } catch {
    el('dataset-summary').textContent='ยังตรวจสอบข้อมูลไม่ได้';
    el('model-state').textContent='เชื่อมต่อระบบไม่สำเร็จ ลองโหลดหน้าใหม่';
  }
}
initialize();
