// Generates the brand "pastel-mesh gradient" hero backdrop as a PNG.
// Peach + lavender + dusty-green stops blurred over a cream-lavender base.
const sharp = require("sharp");

const W = 1920, H = 1080;

const svg = `
<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="g1" cx="18%" cy="22%" r="55%">
      <stop offset="0%"  stop-color="#ffe6d2" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#ffe6d2" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="g2" cx="82%" cy="20%" r="60%">
      <stop offset="0%"  stop-color="#e9d8ff" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#e9d8ff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="g3" cx="72%" cy="88%" r="60%">
      <stop offset="0%"  stop-color="#d6e8d2" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#d6e8d2" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="g4" cx="30%" cy="85%" r="55%">
      <stop offset="0%"  stop-color="#f9f0ff" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#f9f0ff" stop-opacity="0"/>
    </radialGradient>
    <filter id="soft"><feGaussianBlur stdDeviation="60"/></filter>
  </defs>
  <rect width="${W}" height="${H}" fill="#f7f0fa"/>
  <g filter="url(#soft)">
    <rect width="${W}" height="${H}" fill="url(#g1)"/>
    <rect width="${W}" height="${H}" fill="url(#g2)"/>
    <rect width="${W}" height="${H}" fill="url(#g3)"/>
    <rect width="${W}" height="${H}" fill="url(#g4)"/>
  </g>
</svg>`;

sharp(Buffer.from(svg)).png().toFile("mesh.png")
  .then(() => console.log("mesh.png written"))
  .catch((e) => { console.error(e); process.exit(1); });
