// job.js — 매일 실행되는 메인 작업
// cron-job.org 또는 Render cron이 이 엔드포인트를 호출함
const fs = require('fs');
const path = require('path');
const { uploadToInstagram } = require('./upload');
const { sendEmail } = require('./mailer');
require('dotenv').config();

const QUEUE_PATH = path.join(__dirname, 'saju-posts', 'queue.json');
const CAPTIONS_PATH = path.join(__dirname, 'saju-posts', 'captions.json');
const POSTS_PER_DAY = 5;

async function runDailyJob() {
  console.log(`\n🌙 saju.card daily job started — ${new Date().toISOString()}\n`);

  // queue, captions 로드
  if (!fs.existsSync(QUEUE_PATH)) {
    await sendEmail({
      subject: '❌ 큐 파일 없음',
      text: 'queue.json을 찾을 수 없습니다. 콘텐츠 생성이 필요합니다.'
    });
    return;
  }

  const queue = JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf-8'));
  const captions = fs.existsSync(CAPTIONS_PATH)
    ? JSON.parse(fs.readFileSync(CAPTIONS_PATH, 'utf-8'))
    : [];

  // pending인 것들만 필터
  const pending = queue.filter(item => item.status === 'pending' && item.png_path);

  if (pending.length === 0) {
    await sendEmail({
      subject: '⚠️ 업로드할 콘텐츠 없음',
      text: `pending 상태인 게시물이 없습니다. 현재 큐: ${queue.length}개 (완료: ${queue.filter(i => i.status === 'posted').length}개)`
    });
    console.log('⚠️  No pending posts. Queue exhausted.');
    return;
  }

  // 오늘 올릴 5개 선택
  const toUpload = pending.slice(0, POSTS_PER_DAY);
  const results = [];

  for (const item of toUpload) {
    // 캡션 찾기
    const captionData = captions.find(c => c.id === item.id);
    const caption = captionData
      ? `${captionData.caption}\n\n${captionData.hashtags}`
      : item.topic;

    try {
      const postId = await uploadToInstagram({
        pngPath: item.png_path,
        caption
      });

      // queue 업데이트
      item.status = 'posted';
      item.posted_date = new Date().toISOString();
      item.instagram_post_id = postId;

      results.push({ topic: item.topic, status: 'success', postId });

      // 연속 업로드 간격 (인스타 제한 방지)
      await new Promise(resolve => setTimeout(resolve, 15000));

    } catch (err) {
      console.error(`  ❌ Failed: ${item.topic}`, err.message);
      results.push({ topic: item.topic, status: 'failed', error: err.message });
    }
  }

  // queue.json 저장
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(queue, null, 2));

  // 결과 요약
  const success = results.filter(r => r.status === 'success').length;
  const failed = results.filter(r => r.status === 'failed').length;
  const remaining = queue.filter(i => i.status === 'pending').length;

  const summary = `
📊 오늘의 업로드 결과

✅ 성공: ${success}개
❌ 실패: ${failed}개
📋 남은 큐: ${remaining}개

상세:
${results.map(r => `${r.status === 'success' ? '✅' : '❌'} ${r.topic}${r.error ? ` — ${r.error}` : ''}`).join('\n')}

${remaining < 10 ? '⚠️ 큐가 10개 미만입니다. 새 콘텐츠를 생성해주세요.' : ''}
  `.trim();

  console.log('\n' + summary);

  await sendEmail({
    subject: `${success}개 업로드 완료 (실패 ${failed}개)`,
    text: summary
  });
}

runDailyJob().catch(async err => {
  console.error('❌ Job crashed:', err);
  await sendEmail({
    subject: '💥 Job 크래시',
    text: `에러 내용:\n${err.stack}`
  });
  process.exit(1);
});
