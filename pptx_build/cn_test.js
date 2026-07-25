const pptxgen = require('pptxgenjs');
const p = new pptxgen();
p.layout = 'LAYOUT_WIDE';
const s = p.addSlide();
s.addText('中文测试：跨境贸易情报采集', { x: 1, y: 1, w: 10, h: 1, fontSize: 32, fontFace: 'PingFang SC' });
s.addText('Test English mixed 中英混排', { x: 1, y: 3, w: 10, h: 1, fontSize: 24, fontFace: 'STHeiti' });
p.writeFile({ fileName: 'cn_test.pptx' }).then(f => console.log('wrote', f));
