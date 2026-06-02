const sharp = require("sharp");
const svg = `<svg width="600" height="160" xmlns="http://www.w3.org/2000/svg">
<rect width="600" height="160" fill="#ffffff"/>
<text x="20" y="60" font-family="Inter, 'Malgun Gothic', sans-serif" font-size="28" fill="#4a154b">한글 테스트 DaehoV2 배틀</text>
<text x="20" y="110" font-family="'Malgun Gothic', sans-serif" font-size="24" fill="#1d1d1d">팀빌딩 선발 전략 감지</text>
</svg>`;
sharp(Buffer.from(svg)).png().toFile("probe.png").then(()=>console.log("ok")).catch(e=>{console.error(e);process.exit(1);});
