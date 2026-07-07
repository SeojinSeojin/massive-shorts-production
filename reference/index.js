// index.js — Render.com용 Express 서버
const express = require('express');
const path = require('path');
const { execSync } = require('child_process');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// PNG 파일 정적 서빙 (Instagram API가 이미지 URL로 접근)
app.use('/png', express.static(path.join(__dirname, 'saju-png')));

// 헬스체크 (cron-job.org ping용 — 서버 슬립 방지)
app.get('/ping', (req, res) => {
  res.json({ status: 'alive', time: new Date().toISOString() });
});

// 메인 cron 엔드포인트 (cron-job.org가 매일 저녁 8시에 POST)
app.post('/run-job', async (req, res) => {
  // 간단한 인증 (cron-job.org 헤더에 설정)
  const secret = req.headers['x-job-secret'];
  if (secret !== process.env.JOB_SECRET) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // 즉시 응답 후 백그라운드에서 job 실행 (타임아웃 방지)
  res.json({ status: 'job started', time: new Date().toISOString() });

  try {
    require('./job.js');
  } catch (err) {
    console.error('Job execution error:', err);
  }
});

// 큐 상태 확인용
app.get('/status', (req, res) => {
  try {
    const queue = require('./saju-posts/queue.json');
    const pending = queue.filter(i => i.status === 'pending').length;
    const posted = queue.filter(i => i.status === 'posted').length;
    res.json({
      total: queue.length,
      pending,
      posted,
      last_posted: queue.filter(i => i.posted_date).sort((a, b) =>
        new Date(b.posted_date) - new Date(a.posted_date)
      )[0]?.topic || 'none'
    });
  } catch {
    res.json({ error: 'queue.json not found' });
  }
});

app.listen(PORT, () => {
  console.log(`\n🌙 saju.card server running on port ${PORT}`);
  console.log(`   /ping     — health check`);
  console.log(`   /status   — queue status`);
  console.log(`   /run-job  — trigger daily upload (POST)\n`);
});
