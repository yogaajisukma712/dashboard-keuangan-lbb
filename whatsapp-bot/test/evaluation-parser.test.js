const test = require('node:test');
const assert = require('node:assert/strict');

const {
  classifyEvaluationMessage,
  parseEvaluationMessage,
} = require('../src/evaluation/parser');

test('classifyEvaluationMessage detects Indonesian tutor evaluation report', () => {
  const body = `📄 Berikut adalah laporan evaluasi untuk sesi les Bahasa Inggris Salsa hari ini:

📅 Tanggal: 10 April 2026
🕒 Waktu: 17.00-18.00 WIB
📚 Topik: Imaginative Story and Feelings

🔍 Evaluasi:
Pada sesi hari ini, Salsa mempelajari tentang imaginative story.

Terima kasih

Salam hangat,
Ms. Dinda`;

  const result = classifyEvaluationMessage(body);

  assert.equal(result.shouldStore, true);
  assert.equal(result.reason, 'evaluation-report');
  assert.equal(result.markers.hasTitle, true);
  assert.equal(result.markers.hasParsedDate, true);
  assert.equal(result.markers.hasParsedTime, true);
  assert.equal(result.markers.hasTopic, true);
  assert.equal(result.markers.hasEvaluationBody, true);
});

test('parseEvaluationMessage extracts Indonesian student, tutor, and lesson date', () => {
  const body = `📄 Berikut adalah laporan evaluasi untuk sesi les Bahasa Inggris Salsa hari ini:

📅 Tanggal: 10 April 2026
🕒 Waktu: 17.00-18.00 WIB
📚 Topik: Imaginative Story and Feelings

🔍 Evaluasi:
Pada sesi hari ini, Salsa mempelajari tentang imaginative story.

Terima kasih

Salam hangat,
Ms. Dinda`;

  const parsed = parseEvaluationMessage(body);

  assert.equal(parsed.studentName, 'Salsa');
  assert.equal(parsed.subjectName, 'Bahasa Inggris');
  assert.equal(parsed.tutorName, 'Ms. Dinda');
  assert.equal(parsed.reportedLessonDate, '2026-04-10');
});

test('parseEvaluationMessage extracts English evaluation report data', () => {
  const body = `Good Evening Mom/Dad ✨
📄 Here is the evaluation report for Ratih’s English class:

📅 Date: April, 7th 2026
🕒 Time: 04.00 – 05.00 PM
📚 Focus Topic: “Do you ......?”

🔍 Evaluation:
Today, Ratih learned how to use “Do you” to ask about activities.`;

  const parsed = parseEvaluationMessage(body);

  assert.equal(parsed.studentName, 'Ratih');
  assert.equal(parsed.subjectName, 'English');
  assert.equal(parsed.reportedLessonDate, '2026-04-07');
  assert.equal(parsed.reportedTimeLabel, '04.00 – 05.00 PM');
  assert.equal(parsed.focusTopic, 'Do you ......?');
});

test('parseEvaluationMessage accepts varied Indonesian learning report labels', () => {
  const body = `Berikut laporan hasil belajar untuk sesi les Matematika Nadine:

📅 Hari/Tanggal: 11 April 2026
🕒 Jam: 15.00-16.00 WIB
📚 Materi: Pecahan

Hasil Belajar:
Nadine berlatih menyederhanakan pecahan, membandingkan nilai pecahan, dan menjawab soal cerita dengan runtut. Ia mulai lebih teliti saat membaca instruksi.

Best regards,
Ms. Rani`;

  const parsed = parseEvaluationMessage(body);

  assert.equal(parsed.studentName, 'Nadine');
  assert.equal(parsed.subjectName, 'Matematika');
  assert.equal(parsed.tutorName, 'Ms. Rani');
  assert.equal(parsed.reportedLessonDate, '2026-04-11');
  assert.equal(parsed.reportedTimeLabel, '15.00-16.00 WIB');
  assert.equal(parsed.focusTopic, 'Pecahan');
});

test('parseEvaluationMessage accepts English lesson report summary labels', () => {
  const body = `Good evening parents,
Lesson report for Bima’s English lesson:

Lesson Date: April 12th 2026
Class Time: 07.00 - 08.00 PM
Lesson Topic: Past Tense

Lesson Summary:
Bima practiced changing regular and irregular verbs into past tense sentences. He also answered short reading questions and explained the story sequence clearly.

Teacher,
Ms. Lia`;

  const parsed = parseEvaluationMessage(body);

  assert.equal(parsed.studentName, 'Bima');
  assert.equal(parsed.subjectName, 'English');
  assert.equal(parsed.tutorName, 'Ms. Lia');
  assert.equal(parsed.reportedLessonDate, '2026-04-12');
  assert.equal(parsed.reportedTimeLabel, '07.00 - 08.00 PM');
  assert.equal(parsed.focusTopic, 'Past Tense');
});

test('parseEvaluationMessage keeps Indonesian evaluation body and tutor signature on duplicated template', () => {
  const body = `📄 Berikut adalah laporan evaluasi untuk sesi les Bahasa Inggris Salsa hari ini:

📅 Tanggal: 10 April 2026
🕒 Waktu: 17.00-18.00 WIB
📚 Topik: Imaginative Story and Feelings

🔍 Evaluasi:
Pada sesi hari ini, Salsa mempelajari tentang imaginative story, yaitu cerita imajinatif seperti cerita The Ugly Duckling.
Great job, Salsa! 💪✨

Terima kasih 🙏

Salam hangat,
Ms. Dinda
Terima kasih 🙏

Salam hangat,
Ms. Dinda`;

  const parsed = parseEvaluationMessage(body);

  assert.equal(parsed.studentName, 'Salsa');
  assert.equal(parsed.tutorName, 'Ms. Dinda');
  assert.match(parsed.summaryText, /The Ugly Duckling/);
  assert.doesNotMatch(parsed.summaryText, /Salam hangat/i);
});

test('classifyEvaluationMessage rejects incomplete evaluation template without topic block', () => {
  const body = `Good Evening Mom/Dad ✨
📄 Here is the evaluation report for Ratih’s English class:

📅 Date: April, 7th 2026
🕒 Time: 04.00 – 05.00 PM

🔍 Evaluation:
Today, Ratih learned how to use “Do you” to ask about activities.`;

  const result = classifyEvaluationMessage(body);

  assert.equal(result.shouldStore, false);
  assert.equal(result.markers.hasTitle, true);
  assert.equal(result.markers.hasParsedDate, true);
  assert.equal(result.markers.hasParsedTime, true);
  assert.equal(result.markers.hasTopic, false);
});

test('classifyEvaluationMessage rejects casual message mentioning date and evaluation words', () => {
  const body = `Good evening Mom/Dad, evaluation report untuk Ratih nanti dikirim ya.
Date: April, 7th 2026
Time: 04.00 - 05.00 PM`;

  const result = classifyEvaluationMessage(body);

  assert.equal(result.shouldStore, false);
});

test('classifyEvaluationMessage ignores casual group chat', () => {
  const result = classifyEvaluationMessage('Besok jam 5 jadi ya kak');

  assert.equal(result.shouldStore, false);
  assert.equal(result.reason, 'irrelevant');
});
