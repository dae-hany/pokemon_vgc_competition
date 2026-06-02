// Faithful SVG proxy renderer mirroring build.js coordinates, for visual QA only.
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const DPI = 96;
const IN = (v) => v * DPI;           // inches -> px
const PT = (v) => v * 96 / 72;       // points -> px
const C = {
  aubergine: "#4a154b", press: "#611f69", tint: "#592466", cream: "#f4ede4",
  lavender: "#f9f0ff", ink: "#1d1d1d", inkMute: "#696969", white: "#ffffff",
  mauve: "#d9bdde", hairline: "#e6e6e6", lightAub: "#e3d3e6",
};
const FF = "Inter, 'Malgun Gothic', sans-serif";
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// approximate glyph width in px
function charW(ch, fs) {
  const c = ch.codePointAt(0);
  if (c >= 0x1100 && c <= 0xFFE6 && !(c >= 0x2018 && c <= 0x2192)) return fs * 1.0; // CJK/Hangul
  if (ch === " ") return fs * 0.28;
  if (/[.,·:()%×—\-]/.test(ch)) return fs * 0.4;
  if (/[A-Z]/.test(ch)) return fs * 0.62;
  return fs * 0.52;
}
function strW(s, fs) { let w = 0; for (const ch of s) w += charW(ch, fs); return w; }

function wrap(text, fsPx, maxW) {
  const words = text.split(/(\s+)/); // keep spaces
  const lines = []; let cur = "";
  for (const tok of words) {
    if (strW(cur + tok, fsPx) <= maxW) { cur += tok; continue; }
    // token too long or overflow: try char-level for CJK
    if (strW(tok, fsPx) > maxW) {
      let chunk = cur;
      for (const ch of tok) {
        if (strW(chunk + ch, fsPx) > maxW) { lines.push(chunk); chunk = ch; }
        else chunk += ch;
      }
      cur = chunk;
    } else { lines.push(cur.replace(/\s+$/,"")); cur = tok.replace(/^\s+/,""); }
  }
  if (cur.trim()) lines.push(cur);
  return lines.length ? lines : [""];
}

class Slide {
  constructor() { this.el = []; }
  bg(color) { this.el.unshift(`<rect width="${IN(10)}" height="${IN(5.625)}" fill="${color}"/>`); }
  bgImg(b64) { this.el.unshift(`<image href="data:image/png;base64,${b64}" x="0" y="0" width="${IN(10)}" height="${IN(5.625)}"/>`); }
  rrect(x, y, w, h, fill, r, stroke) {
    this.el.push(`<rect x="${IN(x)}" y="${IN(y)}" width="${IN(w)}" height="${IN(h)}" rx="${IN(r)}" ry="${IN(r)}" fill="${fill}" ${stroke ? `stroke="${stroke}" stroke-width="1"` : ""}/>`);
  }
  oval(x, y, w, h, fill) {
    this.el.push(`<ellipse cx="${IN(x + w/2)}" cy="${IN(y + h/2)}" rx="${IN(w/2)}" ry="${IN(h/2)}" fill="${fill}"/>`);
  }
  line(x, y, w, h, color) {
    this.el.push(`<line x1="${IN(x)}" y1="${IN(y)}" x2="${IN(x + w)}" y2="${IN(y + h)}" stroke="${color}" stroke-width="1.5"/>`);
  }
  // box-aware text with wrap + valign
  text(x, y, w, h, str, { fs = 13, bold = false, color = C.ink, align = "left", valign = "top", wrapText = true, lineH = 1.25, pad = 0.05 } = {}) {
    const fsPx = PT(fs);
    const lh = fsPx * lineH;
    const maxW = IN(w - pad * 2);
    const lines = wrapText ? str.split("\n").flatMap(s => wrap(s, fsPx, maxW)) : [str];
    const blockH = lines.length * lh;
    let startY;
    if (valign === "middle") startY = IN(y) + (IN(h) - blockH) / 2 + fsPx * 0.82;
    else if (valign === "bottom") startY = IN(y) + IN(h) - blockH + fsPx * 0.82;
    else startY = IN(y) + IN(pad) + fsPx * 0.82;
    let anchor = "start", tx = IN(x + pad);
    if (align === "center") { anchor = "middle"; tx = IN(x + w/2); }
    else if (align === "right") { anchor = "end"; tx = IN(x + w - pad); }
    const out = lines.map((ln, i) =>
      `<text x="${tx}" y="${startY + i * lh}" font-family="${FF}" font-size="${fsPx}" font-weight="${bold ? 700 : 400}" fill="${color}" text-anchor="${anchor}">${esc(ln)}</text>`
    ).join("");
    this.el.push(out);
    return lines.length;
  }
  svg() {
    return `<svg width="${IN(10)}" height="${IN(5.625)}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><rect width="${IN(10)}" height="${IN(5.625)}" fill="#ffffff"/>${this.el.join("")}</svg>`;
  }
}

function eyebrow(s, t, x, y, w = 3.4) {
  s.rrect(x, y, w, 0.34, C.cream, 0.17);
  s.text(x, y, w, 0.34, t.toUpperCase(), { fs: 10.5, bold: true, color: C.aubergine, align: "center", valign: "middle", wrapText: false });
}
function stepList(s, items, x, y, w, rowH) {
  const dia = 0.44, cx = x + dia / 2;
  s.line(cx, y + dia / 2, 0, (items.length - 1) * rowH, C.lightAub);
  items.forEach((it, i) => {
    const ry = y + i * rowH;
    s.oval(x, ry, dia, dia, C.aubergine);
    s.text(x, ry, dia, dia, String(it.n), { fs: 13, bold: true, color: C.white, align: "center", valign: "middle", wrapText: false });
    s.text(x + dia + 0.18, ry - 0.05, w - dia - 0.18, rowH, it.title + "\n" + it.desc, { fs: 13.5, bold: false, color: C.ink, valign: "top", lineH: 1.15 });
    // (desc smaller; approximate by rendering title bold + desc — split for fidelity)
  });
}

const slides = [];

// ---- SLIDE 1
{
  const s = new Slide();
  const mesh = fs.readFileSync(path.join(__dirname, "mesh.png")).toString("base64");
  s.bgImg(mesh);
  eyebrow(s, "VGC AI Competition 2026 · 설계 발표", 0.6, 0.66, 4.0);
  s.text(0.55, 1.5, 8.5, 1.2, "DaehoV2", { fs: 60, bold: true, color: C.aubergine, valign: "middle", wrapText: false });
  s.text(0.6, 2.72, 8.6, 0.45, "Battle · Championship 트랙 출전 AI 에이전트", { fs: 19, bold: true, color: C.ink, valign: "middle", wrapText: false });
  s.text(0.6, 3.18, 8.6, 0.4, "세 개의 Policy가 공유 전략 감지 로직으로 연결된 단일 설계", { fs: 14, color: C.inkMute, valign: "middle", wrapText: false });
  ["TeamBuild Policy", "Selection Policy", "Battle Policy"].forEach((l, i) => {
    const px = 0.6 + i * 2.65;
    s.rrect(px, 4.25, 2.45, 0.5, C.aubergine, 0.25);
    s.text(px, 4.25, 2.45, 0.5, l, { fs: 12.5, bold: true, color: C.white, align: "center", valign: "middle", wrapText: false });
  });
  slides.push(s);
}
// ---- SLIDE 2
{
  const s = new Slide(); s.bg(C.white);
  eyebrow(s, "Team Build Policy", 0.6, 0.5, 2.8);
  s.text(0.6, 0.98, 9, 0.7, "팀빌딩 — SmartTeamBuildPolicy", { fs: 28, bold: true, color: C.aubergine, valign: "middle", wrapText: false });
  s.text(0.6, 1.62, 9, 0.4, "50마리 로스터 → 6마리 선발, EV·성격·기술 자동 배정 · 컨셉: Bulk-First", { fs: 13, color: C.inkMute, valign: "middle", wrapText: false });
  s.rrect(0.6, 2.2, 3.65, 2.9, C.cream, 0.16);
  s.text(0.9, 2.45, 3.1, 0.35, "선택 점수 (속도 제외)", { fs: 14, bold: true, color: C.aubergine, wrapText: false });
  s.text(0.9, 2.85, 3.1, 1.1, "base_score =\n  화력(firepower)\n  + 내구(bulk)\n  + 0.5 × HP 보너스", { fs: 13.5, color: C.ink, lineH: 1.15 });
  s.text(0.9, 4.05, 3.1, 0.95, "화력·내구를 동일 가중. 속도는 의도적으로 제외 — 선발 단계에서 처리한다.", { fs: 11.5, color: C.inkMute, lineH: 1.15 });
  stepList(s, [
    { n: 1, title: "50×50 데미지 매트릭스", desc: "STAB × 타입상성 × 공·방 스탯 비율로 모든 매치업 계산" },
    { n: 2, title: "Bulk-First 점수화", desc: "화력 + 내구 + HP 보너스로 후보 평가" },
    { n: 3, title: "Greedy + 공유 약점 패널티 (P4)", desc: "커버리지 최적 + 타입 편중 억제 (−0.2 × 공유약점)" },
    { n: 4, title: "로컬 스왑 개선", desc: "지역 최적까지 멤버 1명씩 교체 반복" },
  ], 4.7, 2.28, 4.7, 0.74);
  slides.push(s);
}
// ---- SLIDE 3
{
  const s = new Slide(); s.bg(C.white);
  eyebrow(s, "Selection Policy", 0.6, 0.5, 2.7);
  s.text(0.6, 0.98, 9, 0.7, "선발 — StrategySelectionPolicy", { fs: 28, bold: true, color: C.aubergine, valign: "middle", wrapText: false });
  s.text(0.6, 1.62, 9, 0.4, "6마리 → 4마리 선발 & 출전 순서 결정 · identify_strategy()로 전략 판별", { fs: 13, color: C.inkMute, valign: "middle", wrapText: false });
  const chips = [["TRICK ROOM","TR + 저속 공격수"],["WEATHER","날씨 + 수혜 타입"],["HYPER OFFENSE","고속 2마리+"],["BALANCED","커버리지 최적 4"]];
  const chipW=1.92, gap=0.32, startX=0.62, cy=2.25, chipH=1.0;
  chips.forEach((c,i)=>{
    const cx=startX+i*(chipW+gap);
    s.rrect(cx,cy,chipW,chipH,i===3?C.lavender:C.cream,0.14,C.lightAub);
    s.text(cx,cy,chipW,chipH,c[0]+"\n"+c[1],{fs:12,bold:true,color:C.aubergine,align:"center",valign:"middle",lineH:1.25});
    if(i<3) s.text(cx+chipW,cy,gap,chipH,"→",{fs:16,bold:true,color:C.aubergine,align:"center",valign:"middle",wrapText:false});
  });
  s.text(0.62,3.32,8.8,0.32,"위에서부터 우선순위로 판별 — 해당 없으면 BALANCED로 폴백",{fs:11.5,color:C.inkMute,wrapText:false});
  s.rrect(0.62,3.78,8.76,1.3,C.aubergine,0.16);
  s.text(0.92,3.95,8.2,0.32,"공격 점수 _score_attacker",{fs:12.5,bold:true,color:C.mauve,wrapText:false});
  s.text(0.92,4.28,8.2,0.45,"1.07·피해합  + 0.30·내구  + 0.55·속도  − 0.50·방어패널티 (P21)",{fs:16.5,bold:true,color:C.white,wrapText:false});
  s.text(0.92,4.74,8.2,0.3,"속도를 독립 항으로 반영(선공 우위) + 잘 버티는 포켓몬 우대(P21)",{fs:11,color:C.mauve,wrapText:false});
  slides.push(s);
}
// ---- SLIDE 4
{
  const s = new Slide(); s.bg(C.white);
  eyebrow(s, "Battle Policy · 1 / 2", 0.6, 0.5, 2.7);
  s.text(0.6, 0.98, 9, 0.7, "배틀 — 턴 의사결정 흐름", { fs: 28, bold: true, color: C.aubergine, valign: "middle", wrapText: false });
  s.text(0.6, 1.62, 9, 0.4, "매 턴 두 슬롯의 행동을 우선순위로 결정 · 방어·컨트롤 우선", { fs: 13, color: C.inkMute, valign: "middle", wrapText: false });
  stepList(s, [
    { n: 1, title: "Solo KO 가능 → 공격 위임", desc: "확정 KO 슬롯은 자유 슬롯으로 남김" },
    { n: 2, title: "Protect 판단", desc: "파트너에게 KO 위임 (생존 / 전술 2종)" },
    { n: 3, title: "생존·타입 교체 (P1)", desc: "HP<25% / 4×@75% / 2×@50%" },
    { n: 4, title: "자유 슬롯 화력 배분", desc: "2슬롯 듀오 최적 · 1슬롯 단일 최적" },
  ], 0.62, 2.25, 4.55, 0.73);
  s.rrect(5.45, 2.2, 3.95, 2.95, C.cream, 0.16);
  s.text(5.72, 2.42, 3.45, 0.34, "교체 후보 선별 우선순위", { fs: 14, bold: true, color: C.aubergine, wrapText: false });
  const bl = ["• 교체 직후 즉시 KO당하는 후보 제외","• 남은 후보 중 화력 합산 최대 선택","• 상대 최강기 저항 후보에 ×1.3 보너스","• 즉시 KO 가능 후보 +15,000 (P7)"];
  bl.forEach((b,i)=> s.text(5.72, 2.9+i*0.4, 3.45, 0.4, b, { fs: 12, color: C.ink, wrapText: false }));
  s.text(5.72, 4.52, 3.45, 0.5, "버티지 않고 저항 가능한 포켓몬으로 전선을 재편한다.", { fs: 11, color: C.inkMute, lineH: 1.1 });
  slides.push(s);
}
// ---- SLIDE 5
{
  const s = new Slide(); s.bg(C.white);
  eyebrow(s, "Battle Policy · 2 / 2", 0.6, 0.5, 2.7);
  s.text(0.6, 0.98, 9, 0.7, "배틀 — 듀오 화력 배분 & 성과", { fs: 28, bold: true, color: C.aubergine, valign: "middle", wrapText: false });
  s.text(0.6, 1.62, 9, 0.4, "_best_assignment: 상황에 맞는 화력 집중 방식을 선택", { fs: 13, color: C.inkMute, valign: "middle", wrapText: false });
  const cardY=2.18, cardH=1.52, cardW=4.28;
  s.rrect(0.62,cardY,cardW,cardH,C.lavender,0.16,C.lightAub);
  s.text(0.9,cardY+0.18,cardW-0.5,0.35,"Solo KO Split",{fs:15,bold:true,color:C.aubergine,wrapText:false});
  s.text(0.9,cardY+0.58,cardW-0.5,0.85,"한 쪽이 1마리를 확정 KO → 파트너는 다른 타겟으로 리다이렉트하여 2-for-2 효율 극대화",{fs:12,color:C.ink,lineH:1.15});
  s.rrect(5.1,cardY,cardW,cardH,C.cream,0.16,C.lightAub);
  s.text(5.38,cardY+0.18,cardW-0.5,0.35,"Focus-Fire",{fs:15,bold:true,color:C.aubergine,wrapText:false});
  s.text(5.38,cardY+0.58,cardW-0.5,0.85,"Solo KO 불가 시 동일 타겟 집중 + KO·Priority·위협도 보너스로 '위협 제거' 가치 반영",{fs:12,color:C.ink,lineH:1.15});
  s.text(0.62,3.82,8.76,0.3,"유효 속도 = 기본속도 × 부스트 × 마비(0.5) · 트릭룸 시 음수로 반전 처리",{fs:11,color:C.inkMute,align:"center",wrapText:false});
  const by=4.25,bh=1.05;
  s.rrect(0.62,by,8.76,bh,C.aubergine,0.16);
  const stats=[["+5%p","Battle · Yamabuki  44.5 → 49.5% (P1)"],["71.3%","Friends Championship 평균  (66 → 71.3)"],["+23","Championship ELO  (공유약점 P4)"]];
  const colW=8.76/3;
  stats.forEach((st,i)=>{
    const cx=0.62+i*colW;
    s.text(cx,by+0.14,colW,0.5,st[0],{fs:27,bold:true,color:C.white,align:"center",valign:"middle",wrapText:false});
    s.text(cx+0.1,by+0.64,colW-0.2,0.36,st[1],{fs:9.5,color:C.mauve,align:"center",valign:"middle",lineH:1.0});
    if(i<2) s.line(cx+colW,by+0.22,0,bh-0.44,C.tint);
  });
  slides.push(s);
}

(async () => {
  for (let i = 0; i < slides.length; i++) {
    await sharp(Buffer.from(slides[i].svg())).png().toFile(path.join(__dirname, `preview-${i + 1}.png`));
  }
  console.log("rendered", slides.length, "previews");
})();
