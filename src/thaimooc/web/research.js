'use strict';
function appendRow(body, cells) {
  const tr = document.createElement('tr');
  cells.forEach(value => { const td = document.createElement('td'); td.textContent = value; tr.append(td); });
  body.append(tr);
}
async function loadResearch() {
  try {
    const response = await fetch('/research/data', {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('report');
    const data = await response.json();
    document.getElementById('data-scope').textContent = `ข้อมูลรายวิชาเดียวกัน ${data.corpus_count} วิชา · รหัสชุดข้อมูล ${data.fingerprint.slice(0,10)} · ผลสองรอบประเมินคนละเกณฑ์ ห้ามนำเปอร์เซ็นต์มาปนกัน`;
    const target = document.getElementById('target-rows'); target.replaceChildren();
    for (const [key,label] of [['direct_title','ตรงชื่อวิชา'],['thai_goal','เป้าหมายภาษาไทย'],['english_goal','เป้าหมายภาษาอังกฤษ'],['all','รวม']]) {
      const group = data.target.summary[key];
      appendRow(target,[label,`${Math.round(group.tfidf.hit_at_5*group.queries)}/${group.queries}`,`${Math.round(group.semantic.hit_at_5*group.queries)}/${group.queries}`]);
    }
    const overall = data.target.summary.all;
    document.getElementById('latency-note').textContent = `เวลาค้นหาค่ากลางหลังอุ่นเครื่อง: TF-IDF ${overall.tfidf.median_query_ms.toFixed(1)} ms · Semantic ${overall.semantic.median_query_ms.toFixed(1)} ms ไม่รวมโหลดโมเดล สร้างดัชนี และเครือข่าย`;
    const pilot = document.getElementById('pilot-rows'); pilot.replaceChildren();
    for (const [grade,label] of [['2','ตรงเป้าหมายชัดเจน'],['1','เกี่ยวข้องบางส่วน'],['0','ไม่ตรงจากข้อความที่ตรวจ']]) {
      appendRow(pilot,[label,...['tfidf','semantic'].map(method=>`${data.pilot.summary[method].grade_counts[grade]}/${data.pilot.summary[method].positions}`)]);
    }
    appendRow(pilot,['Precision@5 แบบเข้ม',...['tfidf','semantic'].map(method=>`${(data.pilot.summary[method].precision_at_5_strict*100).toFixed(1)}%`)]);
  } catch {
    document.getElementById('research-error').hidden=false;
    document.getElementById('data-scope').textContent='ข้อมูลชุดทดลอง 120 วิชา · ดูตัวเลขที่บันทึกไว้จากรายงานดาวน์โหลดด้านล่าง';
    for (const id of ['target-rows','pilot-rows']) {
      const body=document.getElementById(id);body.replaceChildren();appendRow(body,['ยังโหลดตัวเลขไม่ได้','—','—']);
    }
  }
}
loadResearch();
