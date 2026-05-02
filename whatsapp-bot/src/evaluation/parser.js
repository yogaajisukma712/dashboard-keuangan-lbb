const INDONESIAN_MONTHS = {
  januari: '01',
  februari: '02',
  maret: '03',
  april: '04',
  mei: '05',
  juni: '06',
  juli: '07',
  agustus: '08',
  september: '09',
  oktober: '10',
  november: '11',
  desember: '12',
};

const KNOWN_SUBJECTS = [
  'Bahasa Inggris',
  'Bahasa Indonesia',
  'Matematika',
  'IPA',
  'IPS',
  'English',
];

function normalizeWhitespace(value) {
  return String(value || '')
    .replace(/\r/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\u00a0/g, ' ')
    .trim();
}

function parseIndonesianDate(value) {
  const match = normalizeWhitespace(value).match(/(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})/);
  if (!match) return null;
  const day = match[1].padStart(2, '0');
  const month = INDONESIAN_MONTHS[match[2].toLowerCase()];
  const year = match[3];
  if (!month) return null;
  return `${year}-${month}-${day}`;
}

function parseEnglishDate(value) {
  const cleaned = normalizeWhitespace(value)
    .replace(/(\d+)(st|nd|rd|th)/gi, '$1')
    .replace(/,/g, '');
  const match = cleaned.match(/([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})/);
  if (!match) return null;
  const month = new Date(`${match[1]} 1, 2000`).getMonth() + 1;
  if (!month) return null;
  return `${match[3]}-${String(month).padStart(2, '0')}-${String(match[2]).padStart(2, '0')}`;
}

function extractTutorName(body) {
  const greetingMatch = body.match(
    /(?:Salam hangat,|Warm regards,?|Regards,?)\s*\n+([^\n]+)/i,
  );
  if (greetingMatch) return normalizeWhitespace(greetingMatch[1]);

  const msLine = body
    .split('\n')
    .map((line) => normalizeWhitespace(line))
    .find((line) => /^(mr|mrs|ms|miss)\.?\s+/i.test(line));
  return msLine || null;
}

function splitIndonesianLessonDescriptor(segment) {
  const cleaned = normalizeWhitespace(segment);
  for (const subject of KNOWN_SUBJECTS.filter((item) => item !== 'English')) {
    if (cleaned.toLowerCase().startsWith(subject.toLowerCase())) {
      const studentName = normalizeWhitespace(cleaned.slice(subject.length));
      return {
        subjectName: subject,
        studentName: studentName || null,
      };
    }
  }
  return { subjectName: null, studentName: cleaned || null };
}

function findTitleMatch(body) {
  const idTitle = body.match(/laporan evaluasi untuk sesi les\s+(.+?)\s+hari ini/i);
  if (idTitle) {
    return { sourceLanguage: 'id', descriptor: normalizeWhitespace(idTitle[1]) };
  }

  const enTitle = body.match(/evaluation report for\s+(.+?)[’']s\s+(.+?)\s+class/i);
  if (enTitle) {
    return {
      sourceLanguage: 'en',
      studentName: normalizeWhitespace(enTitle[1]),
      subjectName: normalizeWhitespace(enTitle[2]),
    };
  }

  return null;
}

function extractEvaluationBody(body) {
  const lines = String(body || '').replace(/\r/g, '').split('\n');
  const headerIndex = lines.findIndex((line) =>
    /(?:🔍\s*)?(?:Evaluasi|Evaluation)\s*:/i.test(line),
  );
  if (headerIndex === -1) return '';

  const chunks = [];
  const headerLine = lines[headerIndex];
  const headerContent = normalizeWhitespace(
    headerLine.replace(/.*?(?:Evaluasi|Evaluation)\s*:/i, ''),
  );
  if (headerContent) {
    chunks.push(headerContent);
  }

  for (let index = headerIndex + 1; index < lines.length; index += 1) {
    const line = normalizeWhitespace(lines[index]);
    if (!line) continue;
    if (
      /^(?:📝\s*)?Additional Notes\s*:/i.test(line) ||
      /^Terima kasih\b/i.test(line) ||
      /^(?:Salam hangat,|Warm regards,?|Regards,?)$/i.test(line)
    ) {
      break;
    }
    chunks.push(line);
  }

  return normalizeWhitespace(chunks.join(' '));
}

function hasLikelyTimeRange(value) {
  const text = normalizeWhitespace(value);
  if (!text) return false;
  return /(\d{1,2}[.:]\d{2})\s*[-–]\s*(\d{1,2}[.:]\d{2})(?:\s*(?:WIB|AM|PM))?/i.test(
    text,
  );
}

function classifyEvaluationMessage(body) {
  const text = String(body || '');
  const titleMatch = findTitleMatch(text);
  const dateMatch = text.match(/(?:Tanggal|Date)\s*:\s*([^\n]+)/i);
  const timeMatch = text.match(/(?:Waktu|Time)\s*:\s*([^\n]+)/i);
  const topicMatch = text.match(/(?:Topik|Focus Topic)\s*:\s*([^\n]+)/i);
  const evaluationBody = extractEvaluationBody(text);
  const parsedDate = dateMatch
    ? parseIndonesianDate(dateMatch[1]) || parseEnglishDate(dateMatch[1])
    : null;
  const parsedTime = timeMatch ? normalizeWhitespace(timeMatch[1]) : null;
  const parsedTopic = topicMatch
    ? normalizeWhitespace(topicMatch[1]).replace(/^[\"“]|[\"”]$/g, '')
    : null;
  const hasClosingIdentity = Boolean(extractTutorName(text));
  const hasGuardianGreeting =
    /(?:good\s+(?:morning|afternoon|evening)|hello|hi)\s+mom\/dad/i.test(text) ||
    /berikut adalah laporan evaluasi/i.test(text);

  const markers = {
    hasTitle: Boolean(titleMatch),
    hasParsedDate: Boolean(parsedDate),
    hasParsedTime: Boolean(parsedTime && hasLikelyTimeRange(parsedTime)),
    hasTopic: Boolean(parsedTopic && parsedTopic.length >= 3),
    hasEvaluationBody: Boolean(evaluationBody && evaluationBody.length >= 40),
    hasClosingIdentity,
    hasGuardianGreeting,
  };

  const requiredMarkers = [
    markers.hasTitle,
    markers.hasParsedDate,
    markers.hasParsedTime,
    markers.hasTopic,
    markers.hasEvaluationBody,
  ];

  if (requiredMarkers.every(Boolean) && (markers.hasClosingIdentity || markers.hasGuardianGreeting)) {
    return { shouldStore: true, reason: 'evaluation-report', markers };
  }
  return { shouldStore: false, reason: 'irrelevant', markers };
}

function parseEvaluationMessage(body) {
  const text = String(body || '');
  const classification = classifyEvaluationMessage(text);
  if (!classification.shouldStore) return null;

  let studentName = null;
  let subjectName = null;
  let reportedLessonDate = null;
  let reportedTimeLabel = null;
  let focusTopic = null;
  let sourceLanguage = null;

  const titleMatch = findTitleMatch(text);
  if (titleMatch && titleMatch.sourceLanguage === 'id') {
    const parsed = splitIndonesianLessonDescriptor(titleMatch.descriptor);
    studentName = parsed.studentName;
    subjectName = parsed.subjectName;
    sourceLanguage = 'id';
  }

  if (titleMatch && titleMatch.sourceLanguage === 'en') {
    studentName = titleMatch.studentName || null;
    subjectName = titleMatch.subjectName || null;
    sourceLanguage = 'en';
  }

  const dateMatch = text.match(/(?:Tanggal|Date)\s*:\s*([^\n]+)/i);
  if (dateMatch) {
    const dateText = normalizeWhitespace(dateMatch[1]);
    reportedLessonDate = parseIndonesianDate(dateText) || parseEnglishDate(dateText);
  }

  const timeMatch = text.match(/(?:Waktu|Time)\s*:\s*([^\n]+)/i);
  if (timeMatch) reportedTimeLabel = normalizeWhitespace(timeMatch[1]);

  const topicMatch = text.match(/(?:Topik|Focus Topic)\s*:\s*([^\n]+)/i);
  if (topicMatch) {
    focusTopic = normalizeWhitespace(topicMatch[1]).replace(/^[\"“]|[\"”]$/g, '');
  }

  const summaryText = extractEvaluationBody(text);
  if (!studentName || !reportedLessonDate || !reportedTimeLabel || !focusTopic || !summaryText) {
    return null;
  }

  return {
    studentName,
    subjectName,
    tutorName: extractTutorName(text),
    reportedLessonDate,
    reportedTimeLabel,
    focusTopic,
    sourceLanguage,
    summaryText,
  };
}

module.exports = {
  classifyEvaluationMessage,
  parseEvaluationMessage,
};
