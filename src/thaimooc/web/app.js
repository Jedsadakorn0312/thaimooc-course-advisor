'use strict';
const $ = (id) => document.getElementById(id);
let requestNumber = 0;
let controller;
let totalCourses = null;

function setBusy(busy) {
  $('submit').disabled = busy;
  $('button-text').textContent = busy ? 'กำลังค้นหารายวิชา…' : 'ค้นหาวิชาที่เหมาะกับฉัน';
  $('cards').setAttribute('aria-busy', String(busy));
}

async function post(path, body, signal) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal});
  if (!response.ok) throw new Error(response.status === 422 ? 'ข้อมูลการค้นหาไม่ถูกต้อง กรุณาตรวจเป้าหมายและตัวกรองอีกครั้ง' : 'ระบบค้นหาไม่พร้อมใช้งาน กรุณาลองอีกครั้ง');
  return response.json();
}

function safeSource(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && ['thaimooc.ac.th', 'www.thaimooc.ac.th', 'thaimooc.org', 'www.thaimooc.org'].includes(parsed.hostname) ? parsed.href : null;
  } catch { return null; }
}

function render(items) {
  const fragment = document.createDocumentFragment();
  items.forEach((item, index) => {
    const c = item.course;
    const card = $('course-template').content.cloneNode(true);
    card.querySelector('.category').textContent = c.category || 'ไม่ระบุหมวด';
    card.querySelector('.course-number').textContent = String(index + 1).padStart(2, '0');
    card.querySelector('.course-title').textContent = c.title;
    card.querySelector('.institution').textContent = c.institution || 'ไม่ระบุสถาบัน';
    card.querySelector('.duration').textContent = c.duration_hours == null ? 'ไม่ระบุระยะเวลา' : `${c.duration_hours} ชั่วโมง`;
    card.querySelector('.level').textContent = c.level || 'ไม่ระบุระดับ';
    card.querySelector('.description').textContent = c.description;
    if (item.reason) {
      card.querySelector('.reason-box').hidden = false;
      card.querySelector('.reason').textContent = item.reason;
    }
    const link = card.querySelector('.course-link');
    const url = safeSource(c.url);
    if (url) { link.href = url; link.setAttribute('aria-label', `ดูรายละเอียดวิชา ${c.title} บน Thai MOOC (เปิดแท็บใหม่)`); }
    else { link.remove(); }
    fragment.append(card);
  });
  $('cards').replaceChildren(fragment);
  $('results-count').textContent = `${items.length} รายวิชา`;
  $('empty').hidden = items.length > 0;
}

$('search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = $('goal').value.trim();
  if (!query) { $('goal').setCustomValidity('กรุณาบอกเป้าหมายการเรียนรู้ของคุณ'); $('goal').reportValidity(); return; }
  controller?.abort();
  controller = new AbortController();
  const activeController = controller;
  const current = ++requestNumber;
  const body = {query, top_k: 5, level: $('level').value || null, max_hours: $('hours').value ? Number($('hours').value) : null};
  $('results-section').hidden = false;
  $('error').hidden = true;
  $('empty').hidden = true;
  $('cards').replaceChildren();
  $('results-count').textContent = 'กำลังค้นหา';
  $('results-description').textContent = `สำหรับเป้าหมาย “${query}”`;
  $('status').textContent = 'กำลังค้นจากข้อมูลรายวิชา…';
  setBusy(true);
  let timeout;
  try {
    timeout = setTimeout(() => activeController.abort(), 15000);
    const response = await post('/search', body, activeController.signal);
    clearTimeout(timeout);
    if (current !== requestNumber) return;
    render(response.results);
    setBusy(false);
    $('results-heading').focus({preventScroll: true});
    $('results-section').scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'});
    if (!response.results.length) { $('status').textContent = ''; return; }
    $('status').textContent = 'แสดงรายวิชาที่ใกล้เคียงกับเป้าหมายของคุณ อาจน้อยกว่า 5 วิชา กรุณาตรวจเนื้อหาต้นทางก่อนเลือกเรียน';
  } catch (error) {
    if (current !== requestNumber) return;
    if ($('cards').children.length) {
      $('status').textContent = 'แสดงรายวิชาที่ค้นพบแล้ว กรุณาตรวจรายละเอียดต้นทางก่อนเลือกเรียน';
    } else {
      $('error').hidden = false;
      $('error').textContent = error.name === 'AbortError' ? 'การค้นหาใช้เวลานานเกินไป กรุณาลองอีกครั้ง' : error.message || 'เชื่อมต่อระบบไม่ได้ กรุณาลองอีกครั้ง';
      $('results-count').textContent = 'ยังไม่มีผลลัพธ์';
      $('status').textContent = '';
    }
  } finally {
    clearTimeout(timeout);
    if (current === requestNumber) setBusy(false);
  }
});

$('goal').addEventListener('input', () => $('goal').setCustomValidity(''));
document.querySelectorAll('[data-query]').forEach((button) => button.addEventListener('click', () => {
  $('goal').value = button.dataset.query;
  $('goal').setCustomValidity('');
  $('search-form').requestSubmit();
}));
$('reset-filters').addEventListener('click', () => { $('level').value = ''; $('hours').value = ''; $('search-form').requestSubmit(); });

async function loadCatalog() {
  try {
    const response = await fetch('/catalog', {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('catalog');
    const data = await response.json();
    totalCourses = data.count;
    $('catalog-note').textContent = totalCourses <= 3
      ? `เวอร์ชันทดลอง · มีข้อมูลสรุป ${totalCourses} วิชาจริงในหัวข้อไซเบอร์ สมุนไพร และการท่องเที่ยว ยังไม่ครอบคลุมรายวิชาทั้งหมดของ Thai MOOC`
      : `ฐานข้อมูลตัวอย่าง ${totalCourses} รายวิชา ครอบคลุม ${data.categories.length} หมวด · คัดบางส่วนจาก Thai MOOC ผลค้นหาไม่ครอบคลุมรายวิชาทั้งหมด`;
    data.levels.forEach((level) => { const option = document.createElement('option'); option.value = level; option.textContent = level; $('level').append(option); });
  } catch {
    $('catalog-note').textContent = 'ยังตรวจสอบจำนวนรายวิชาไม่ได้ กรุณาตรวจว่าเซิร์ฟเวอร์ทำงานอยู่ แล้วโหลดหน้าใหม่';
  }
}
loadCatalog();
