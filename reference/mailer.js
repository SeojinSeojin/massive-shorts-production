// mailer.js — 이메일 알림
const nodemailer = require('nodemailer');
require('dotenv').config();

const transporter = nodemailer.createTransport({
  service: 'gmail',
  auth: {
    user: process.env.GMAIL_USER,
    pass: process.env.GMAIL_APP_PASSWORD
  }
});

async function sendEmail({ subject, text }) {
  if (!process.env.GMAIL_USER || !process.env.GMAIL_APP_PASSWORD) {
    console.log('⚠️  Email not configured, skipping notification.');
    return;
  }

  try {
    await transporter.sendMail({
      from: process.env.GMAIL_USER,
      to: process.env.NOTIFY_EMAIL,
      subject: `[saju.card] ${subject}`,
      text
    });
    console.log(`📧 Email sent: ${subject}`);
  } catch (err) {
    console.error('❌ Email failed:', err.message);
  }
}

module.exports = { sendEmail };
