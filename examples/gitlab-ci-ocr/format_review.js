#!/usr/bin/env node
// Читает JSON от `ocr review --format json` (stdin) и печатает аккуратный
// GitLab-markdown: заголовок, группировка по файлам, ```diff-блоки.
// Зачем: терминальный вывод ocr (--audience agent) содержит ANSI и «голые» строки
// диффа (+/-), которые GitLab-markdown превращает в списки/кашу. Здесь — чистый markdown.
'use strict';

function diffBlock(existing, suggestion) {
  const lines = [];
  if (existing) for (const l of existing.replace(/\r/g, '').split('\n')) lines.push('-' + l);
  if (suggestion) for (const l of suggestion.replace(/\r/g, '').split('\n')) lines.push('+' + l);
  if (!lines.length) return '';
  return '\n```diff\n' + lines.join('\n') + '\n```';
}

function main() {
  const raw = require('fs').readFileSync(0, 'utf8');
  let d;
  try { d = JSON.parse(raw); } catch (e) {
    process.stdout.write('### 🤖 AI-ревью (ocr)\n\n`не удалось разобрать JSON вывода ocr`\n');
    return;
  }
  const s = d.summary || {};
  const comments = Array.isArray(d.comments) ? d.comments : [];
  const out = [];
  out.push('### 🤖 AI-ревью кода (open-code-review)');
  let meta = 'Файлов: ' + (s.files_reviewed ?? '?') + ' · замечаний: ' + (s.comments ?? comments.length);
  if (s.total_tokens) {
    meta += ' · ~' + s.total_tokens + ' токенов';
    if (s.input_tokens != null && s.output_tokens != null) {
      meta += ' (вход ~' + s.input_tokens + ', выход ~' + s.output_tokens + ')';
    }
  }
  if (s.elapsed) meta += ' · ' + s.elapsed;
  out.push('_' + meta + '_');

  if (!comments.length) {
    out.push('\n✅ Замечаний нет.');
    process.stdout.write(out.join('\n') + '\n');
    return;
  }

  const byFile = new Map();
  for (const c of comments) {
    const filePath = c.path || '(неизвестный файл)';
    if (!byFile.has(filePath)) byFile.set(filePath, []);
    byFile.get(filePath).push(c);
  }

  for (const [path, cs] of byFile) {
    out.push('\n---\n');
    out.push('#### 📄 `' + path + '` — ' + cs.length + (cs.length === 1 ? ' замечание' : ' замечания(-ий)'));
    for (const c of cs) {
      const hasRange = c.end_line && c.end_line !== c.start_line;
      const loc = c.start_line ? 'строки ' + c.start_line + (hasRange ? '–' + c.end_line : '') : 'общее';
      out.push('\n**' + loc + '**\n');
      if (c.content) out.push(String(c.content).trim());
      const diff = diffBlock(c.existing_code, c.suggestion_code);
      if (diff) out.push(diff);
    }
  }
  process.stdout.write(out.join('\n') + '\n');
}

main();
