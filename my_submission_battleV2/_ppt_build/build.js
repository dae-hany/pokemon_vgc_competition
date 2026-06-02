const pptxgen = require("pptxgenjs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.author = "DaehoV2";
pres.title = "DaehoV2 — VGC AI 설계 발표";

// ---- Brand palette (Slacc-inspired design system) ----
const C = {
  aubergine: "4a154b",
  press: "611f69",
  tint: "592466",
  cream: "f4ede4",
  lavender: "f9f0ff",
  ink: "1d1d1d",
  inkMute: "696969",
  link: "1264a3",
  white: "ffffff",
  mauve: "d9bdde",
  hairline: "e6e6e6",
  lightAub: "e3d3e6",
  success: "007a5a",
};
const FONT = "Inter";
const MESH = path.join(__dirname, "mesh.png");

const shadow = () => ({ type: "outer", color: "000000", blur: 11, offset: 3, angle: 90, opacity: 0.1 });

// ---------- helpers ----------
function eyebrow(slide, text, x, y, w = 3.4) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h: 0.34, fill: { color: C.cream }, line: { type: "none" }, rectRadius: 0.17,
  });
  slide.addText(text.toUpperCase(), {
    x, y, w, h: 0.34, align: "center", valign: "middle",
    fontFace: FONT, fontSize: 10.5, bold: true, color: C.aubergine, charSpacing: 2, margin: 0,
  });
}

function title(slide, text, x, y, w, size = 28, color = C.aubergine) {
  slide.addText(text, {
    x, y, w, h: 0.7, fontFace: FONT, fontSize: size, bold: true, color,
    charSpacing: -0.4, align: "left", valign: "middle", margin: 0,
  });
}

function sub(slide, text, x, y, w) {
  slide.addText(text, {
    x, y, w, h: 0.4, fontFace: FONT, fontSize: 13, color: C.inkMute,
    align: "left", valign: "middle", margin: 0,
  });
}

function pill(slide, text, x, y, w, h, fill, txt, size = 12, bold = true) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, fill: { color: fill }, line: { type: "none" }, rectRadius: h / 2,
  });
  slide.addText(text, {
    x, y, w, h, align: "center", valign: "middle",
    fontFace: FONT, fontSize: size, bold, color: txt, margin: 0,
  });
}

// vertical numbered step list
function stepList(slide, items, x, y, w, rowH) {
  const dia = 0.44;
  const cx = x + dia / 2;
  // connector line behind circles
  slide.addShape(pres.shapes.LINE, {
    x: cx, y: y + dia / 2, w: 0, h: (items.length - 1) * rowH,
    line: { color: C.lightAub, width: 2 },
  });
  items.forEach((it, i) => {
    const ry = y + i * rowH;
    slide.addShape(pres.shapes.OVAL, {
      x, y: ry, w: dia, h: dia, fill: { color: C.aubergine }, line: { type: "none" },
    });
    slide.addText(String(it.n), {
      x, y: ry, w: dia, h: dia, align: "center", valign: "middle",
      fontFace: FONT, fontSize: 13, bold: true, color: C.white, margin: 0,
    });
    slide.addText(
      [
        { text: it.title, options: { fontSize: 13.5, bold: true, color: C.ink, breakLine: true } },
        { text: it.desc, options: { fontSize: 10.8, color: C.inkMute } },
      ],
      { x: x + dia + 0.18, y: ry - 0.05, w: w - dia - 0.18, h: rowH, valign: "top", fontFace: FONT, lineSpacingMultiple: 1.05, margin: 0 }
    );
  });
}

// ============================================================
// SLIDE 1 — Cover (pastel-mesh hero)
// ============================================================
{
  const s = pres.addSlide();
  s.background = { path: MESH };
  eyebrow(s, "VGC AI Competition 2026 · 설계 발표", 0.6, 0.66, 4.0);
  s.addText("DaehoV2", {
    x: 0.55, y: 1.5, w: 8.5, h: 1.2, fontFace: FONT, fontSize: 60, bold: true,
    color: C.aubergine, charSpacing: -1, align: "left", valign: "middle", margin: 0,
  });
  s.addText("Battle · Championship 트랙 출전 AI 에이전트", {
    x: 0.6, y: 2.72, w: 8.6, h: 0.45, fontFace: FONT, fontSize: 19, bold: true,
    color: C.ink, align: "left", valign: "middle", margin: 0,
  });
  s.addText("세 개의 Policy가 공유 전략 감지 로직으로 연결된 단일 설계", {
    x: 0.6, y: 3.18, w: 8.6, h: 0.4, fontFace: FONT, fontSize: 14, color: C.inkMute,
    align: "left", valign: "middle", margin: 0,
  });
  // three policy pills (brand motif)
  const labels = ["TeamBuild Policy", "Selection Policy", "Battle Policy"];
  let px = 0.6;
  labels.forEach((l) => {
    pill(s, l, px, 4.25, 2.45, 0.5, C.aubergine, C.white, 12.5);
    px += 2.65;
  });
}

// ============================================================
// SLIDE 2 — Team Build Policy
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  eyebrow(s, "Team Build Policy", 0.6, 0.5, 2.8);
  title(s, "팀빌딩 — SmartTeamBuildPolicy", 0.6, 0.98, 9, 28);
  sub(s, "50마리 로스터 → 6마리 선발, EV·성격·기술 자동 배정 · 컨셉: Bulk-First", 0.6, 1.62, 9);

  // Left: scoring formula card
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.6, y: 2.2, w: 3.65, h: 2.9, fill: { color: C.cream }, line: { type: "none" },
    rectRadius: 0.16, shadow: shadow(),
  });
  s.addText("선택 점수 (속도 제외)", {
    x: 0.9, y: 2.45, w: 3.1, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: C.aubergine, margin: 0,
  });
  s.addText([
    { text: "base_score =", options: { color: C.ink, bold: true, breakLine: true } },
    { text: "  화력(firepower)", options: { color: C.ink, breakLine: true } },
    { text: "  + 내구(bulk)", options: { color: C.ink, breakLine: true } },
    { text: "  + 0.5 × HP 보너스", options: { color: C.ink } },
  ], { x: 0.9, y: 2.85, w: 3.1, h: 1.1, fontFace: FONT, fontSize: 13.5, lineSpacingMultiple: 1.15, margin: 0 });
  s.addText("화력·내구를 동일 가중. 속도는 의도적으로 제외 — 선발 단계에서 처리한다.", {
    x: 0.9, y: 4.05, w: 3.1, h: 0.95, fontFace: FONT, fontSize: 11.5, color: C.inkMute,
    lineSpacingMultiple: 1.15, valign: "top", margin: 0,
  });

  // Right: 4-step process
  stepList(s, [
    { n: 1, title: "50×50 데미지 매트릭스", desc: "STAB × 타입상성 × 공·방 스탯 비율로 모든 매치업 계산" },
    { n: 2, title: "Bulk-First 점수화", desc: "화력 + 내구 + HP 보너스로 후보 평가" },
    { n: 3, title: "Greedy + 공유 약점 패널티 (P4)", desc: "커버리지 최적 + 타입 편중 억제 (−0.2 × 공유약점)" },
    { n: 4, title: "로컬 스왑 개선", desc: "지역 최적까지 멤버 1명씩 교체 반복" },
  ], 4.7, 2.28, 4.7, 0.74);
}

// ============================================================
// SLIDE 3 — Selection Policy
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  eyebrow(s, "Selection Policy", 0.6, 0.5, 2.7);
  title(s, "선발 — StrategySelectionPolicy", 0.6, 0.98, 9, 28);
  sub(s, "6마리 → 4마리 선발 & 출전 순서 결정 · identify_strategy()로 전략 판별", 0.6, 1.62, 9);

  // strategy priority chips
  const chips = [
    { t: "TRICK ROOM", d: "TR + 저속 공격수" },
    { t: "WEATHER", d: "날씨 + 수혜 타입" },
    { t: "HYPER OFFENSE", d: "고속 2마리+" },
    { t: "BALANCED", d: "커버리지 최적 4" },
  ];
  const chipW = 1.92, gap = 0.32, startX = 0.62, cy = 2.25, chipH = 1.0;
  chips.forEach((c, i) => {
    const cx = startX + i * (chipW + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: cx, y: cy, w: chipW, h: chipH, fill: { color: i === 3 ? C.lavender : C.cream },
      line: { color: C.lightAub, width: 1 }, rectRadius: 0.14,
    });
    s.addText([
      { text: c.t, options: { fontSize: 12, bold: true, color: C.aubergine, breakLine: true, charSpacing: 0.5 } },
      { text: c.d, options: { fontSize: 10, color: C.inkMute } },
    ], { x: cx, y: cy, w: chipW, h: chipH, align: "center", valign: "middle", fontFace: FONT, lineSpacingMultiple: 1.1, margin: 0 });
    if (i < chips.length - 1) {
      s.addText("→", {
        x: cx + chipW, y: cy, w: gap, h: chipH, align: "center", valign: "middle",
        fontFace: FONT, fontSize: 16, bold: true, color: C.aubergine, margin: 0,
      });
    }
  });
  s.addText("위에서부터 우선순위로 판별 — 해당 없으면 BALANCED로 폴백", {
    x: 0.62, y: 3.32, w: 8.8, h: 0.32, fontFace: FONT, fontSize: 11.5, italic: true, color: C.inkMute, margin: 0,
  });

  // _score_attacker formula card (aubergine band)
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.62, y: 3.78, w: 8.76, h: 1.3, fill: { color: C.aubergine }, line: { type: "none" },
    rectRadius: 0.16, shadow: shadow(),
  });
  s.addText("공격 점수 _score_attacker", {
    x: 0.92, y: 3.95, w: 8.2, h: 0.32, fontFace: FONT, fontSize: 12.5, bold: true, color: C.mauve, margin: 0,
  });
  s.addText([
    { text: "1.07·피해합  ", options: { color: C.white, bold: true } },
    { text: "+ 0.30·내구  + 0.55·속도  ", options: { color: C.white } },
    { text: "− 0.50·방어패널티", options: { color: "f0d9f5", bold: true } },
    { text: " (P21)", options: { color: C.mauve } },
  ], { x: 0.92, y: 4.28, w: 8.2, h: 0.45, fontFace: FONT, fontSize: 16.5, margin: 0 });
  s.addText("속도를 독립 항으로 반영(선공 우위) + 잘 버티는 포켓몬 우대(P21)", {
    x: 0.92, y: 4.74, w: 8.2, h: 0.3, fontFace: FONT, fontSize: 11, color: C.mauve, margin: 0,
  });
}

// ============================================================
// SLIDE 4 — Battle Policy (1) : decision flow
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  eyebrow(s, "Battle Policy · 1 / 2", 0.6, 0.5, 2.7);
  title(s, "배틀 — 턴 의사결정 흐름", 0.6, 0.98, 9, 28);
  sub(s, "매 턴 두 슬롯의 행동을 우선순위로 결정 · 방어·컨트롤 우선", 0.6, 1.62, 9);

  // Left: vertical priority pipeline
  stepList(s, [
    { n: 1, title: "Solo KO 가능 → 공격 위임", desc: "확정 KO 슬롯은 자유 슬롯으로 남김" },
    { n: 2, title: "Protect 판단", desc: "파트너에게 KO 위임 (생존 / 전술 2종)" },
    { n: 3, title: "생존·타입 교체 (P1)", desc: "HP<25% / 4×@75% / 2×@50%" },
    { n: 4, title: "자유 슬롯 화력 배분", desc: "2슬롯 듀오 최적 · 1슬롯 단일 최적" },
  ], 0.62, 2.25, 4.55, 0.73);

  // Right: switch-candidate detail card
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.45, y: 2.2, w: 3.95, h: 2.95, fill: { color: C.cream }, line: { type: "none" },
    rectRadius: 0.16, shadow: shadow(),
  });
  s.addText("교체 후보 선별 우선순위", {
    x: 5.72, y: 2.42, w: 3.45, h: 0.34, fontFace: FONT, fontSize: 14, bold: true, color: C.aubergine, margin: 0,
  });
  s.addText([
    { text: "교체 직후 즉시 KO당하는 후보 제외", options: { bullet: { code: "2022" }, color: C.ink, breakLine: true } },
    { text: "남은 후보 중 화력 합산 최대 선택", options: { bullet: { code: "2022" }, color: C.ink, breakLine: true } },
    { text: "상대 최강기 저항 후보에 ×1.3 보너스", options: { bullet: { code: "2022" }, color: C.ink, breakLine: true } },
    { text: "즉시 KO 가능 후보 +15,000 (P7)", options: { bullet: { code: "2022" }, color: C.ink } },
  ], { x: 5.72, y: 2.85, w: 3.45, h: 1.55, fontFace: FONT, fontSize: 12, paraSpaceAfter: 7, margin: 0 });
  s.addText("버티지 않고 저항 가능한 포켓몬으로 전선을 재편한다.", {
    x: 5.72, y: 4.52, w: 3.45, h: 0.5, fontFace: FONT, fontSize: 11, italic: true, color: C.inkMute,
    lineSpacingMultiple: 1.1, valign: "top", margin: 0,
  });
}

// ============================================================
// SLIDE 5 — Battle Policy (2) : offense + results
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  eyebrow(s, "Battle Policy · 2 / 2", 0.6, 0.5, 2.7);
  title(s, "배틀 — 듀오 화력 배분 & 성과", 0.6, 0.98, 9, 28);
  sub(s, "_best_assignment: 상황에 맞는 화력 집중 방식을 선택", 0.6, 1.62, 9);

  // Two mode cards
  const cardY = 2.18, cardH = 1.52, cardW = 4.28;
  // Card A: Solo KO Split (lavender)
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.62, y: cardY, w: cardW, h: cardH, fill: { color: C.lavender }, line: { color: C.lightAub, width: 1 },
    rectRadius: 0.16, shadow: shadow(),
  });
  s.addText("Solo KO Split", { x: 0.9, y: cardY + 0.18, w: cardW - 0.5, h: 0.35, fontFace: FONT, fontSize: 15, bold: true, color: C.aubergine, margin: 0 });
  s.addText("한 쪽이 1마리를 확정 KO → 파트너는 다른 타겟으로 리다이렉트하여 2-for-2 효율 극대화", {
    x: 0.9, y: cardY + 0.58, w: cardW - 0.5, h: 0.85, fontFace: FONT, fontSize: 12, color: C.ink, lineSpacingMultiple: 1.15, valign: "top", margin: 0,
  });
  // Card B: Focus-fire (cream)
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.1, y: cardY, w: cardW, h: cardH, fill: { color: C.cream }, line: { color: C.lightAub, width: 1 },
    rectRadius: 0.16, shadow: shadow(),
  });
  s.addText("Focus-Fire", { x: 5.38, y: cardY + 0.18, w: cardW - 0.5, h: 0.35, fontFace: FONT, fontSize: 15, bold: true, color: C.aubergine, margin: 0 });
  s.addText("Solo KO 불가 시 동일 타겟 집중 + KO·Priority·위협도 보너스로 '위협 제거' 가치 반영", {
    x: 5.38, y: cardY + 0.58, w: cardW - 0.5, h: 0.85, fontFace: FONT, fontSize: 12, color: C.ink, lineSpacingMultiple: 1.15, valign: "top", margin: 0,
  });
  s.addText("유효 속도 = 기본속도 × 부스트 × 마비(0.5) · 트릭룸 시 음수로 반전 처리", {
    x: 0.62, y: 3.82, w: 8.76, h: 0.3, fontFace: FONT, fontSize: 11, italic: true, color: C.inkMute, align: "center", margin: 0,
  });

  // Results aubergine band with 3 stat callouts
  const by = 4.25, bh = 1.05;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.62, y: by, w: 8.76, h: bh, fill: { color: C.aubergine }, line: { type: "none" }, rectRadius: 0.16, shadow: shadow(),
  });
  const stats = [
    { num: "+5%p", lab: "Battle · Yamabuki  44.5 → 49.5% (P1)" },
    { num: "71.3%", lab: "Friends Championship 평균  (66 → 71.3)" },
    { num: "+23", lab: "Championship ELO  (공유약점 P4)" },
  ];
  const colW = 8.76 / 3;
  stats.forEach((st, i) => {
    const cx = 0.62 + i * colW;
    s.addText(st.num, { x: cx, y: by + 0.14, w: colW, h: 0.5, align: "center", valign: "middle", fontFace: FONT, fontSize: 27, bold: true, color: C.white, charSpacing: -0.4, margin: 0 });
    s.addText(st.lab, { x: cx + 0.1, y: by + 0.64, w: colW - 0.2, h: 0.36, align: "center", valign: "middle", fontFace: FONT, fontSize: 9.5, color: C.mauve, lineSpacingMultiple: 1.0, margin: 0 });
    if (i < 2) {
      s.addShape(pres.shapes.LINE, { x: cx + colW, y: by + 0.22, w: 0, h: bh - 0.44, line: { color: C.tint, width: 1 } });
    }
  });
}

pres.writeFile({ fileName: path.join(__dirname, "DaehoV2_design.pptx") }).then((f) => {
  console.log("written:", f);
});
