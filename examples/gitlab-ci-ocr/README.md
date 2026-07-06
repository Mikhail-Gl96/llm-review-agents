# Пример-кейс: AI-ревью MR в GitLab CI (open-code-review)

Готовый, **проверенный вживую** рецепт: на каждый Merge Request GitLab CI прогоняет
[open-code-review](https://github.com/alibaba/open-code-review) по диффу MR и постит
**аккуратный markdown-коммент** с замечаниями (в ```diff-блоках, по файлам).

Это конкретный случай для **GitLab** (для локального запуска и других платформ — см.
[reviewers/open-code-review](../../reviewers/open-code-review/README.md)).

## Что внутри

| Файл | Назначение | Куда положить в своём проекте |
|---|---|---|
| [`.gitlab-ci.yml`](.gitlab-ci.yml) | джоба `ocr_review` на MR | корень репозитория |
| [`format_review.js`](format_review.js) | рендер JSON-вывода ocr → markdown | `.gitlab/format_review.js` |

## Как это выглядит

```
### 🤖 AI-ревью кода (open-code-review)
_Файлов: 3 · замечаний: 9 · 2m15s_
---
#### 📄 `app/util.py` — 2 замечания
**строки 6–7**
**Security: Command Injection**. …
​```diff
-def run_cmd(user_input):
-    os.system("echo " + user_input)
+def run_cmd(user_input: str) -> None:
+    subprocess.run(["echo", user_input], check=True)
​```
```

## Настройка (по шагам)

1. **Включить Merge Requests** в проекте: Settings → General →
   «Visibility, project features, permissions» → тумблер **Merge requests** → Save.
   *(Без этого не будет ни MR-пайплайнов, ни кнопки создания MR.)*
2. **Токен для коммента:** Settings → Access Tokens → создать **Project Access Token**,
   роль **Developer**, scope **`api`**.
3. **CI/CD-переменные** (Settings → CI/CD → Variables), обе **Masked**, **без** «Protect»
   (иначе не подхватятся на MR из обычной ветки):
   - `GITLAB_TOKEN` = токен из шага 2
   - `DEEPSEEK_KEY` = ключ провайдера (другой провайдер — правь `llm.url`/`llm.model`
     в `.gitlab-ci.yml`, см. [справочник провайдеров](../../docs/providers.md))
4. **Положить файлы:** `.gitlab-ci.yml` → в корень, `format_review.js` → в `.gitlab/`.
5. **Открыть тестовый MR** → джоба `ocr_review` в MR-пайплайне → коммент с ревью.

## Подводные камни (грабли, на которые мы реально наступили)

- **Целевой ветки нет в клоне.** GitLab в MR-пайплайне делает shallow-клон только
  исходной ветки, поэтому `--from origin/<target>` падает (`Needed a single revision`).
  Фикс — в конфиге: `GIT_DEPTH: "0"` + `git fetch origin <target>` + дифф от `merge-base`.
- **ANSI-цвета калечат markdown.** Терминальный вывод `ocr` (текст/`--audience agent`)
  содержит ANSI и «голые» `+`/`-` строки — GitLab превращает их в списки и кашу.
  Поэтому берём `--format json` и рендерим сами (`format_review.js`).
- **Merge Requests должны быть включены** — иначе события `merge_request_event` не
  возникают (джоба не триггерится), и в UI нет создания MR.
- **Protected-переменные** доступны только на защищённых ветках. Для MR из обычной
  тест-ветки снимите «Protect» у переменных.
- **Модель.** Пример на `deepseek-v4-pro`; любой OpenAI-совместимый провайдер —
  заменой `llm.url`/`llm.model`.

## Идемпотентность (по желанию)

Как есть, джоба постит **новый** коммент на каждый прогон — при повторных пушах в MR
комментарии копятся. Чтобы обновлять один коммент, добавьте перед `curl POST` удаление
прошлого коммента бота (ищем по заголовку):

```yaml
    - |
      PREV=$(curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        "$CI_API_V4_URL/projects/$CI_PROJECT_ID/merge_requests/$CI_MERGE_REQUEST_IID/notes?per_page=100" \
        | node -e 'const n=JSON.parse(require("fs").readFileSync(0,"utf8"));const h="### 🤖 AI-ревью кода";const m=n.find(x=>(x.body||"").startsWith(h));process.stdout.write(m?String(m.id):"")')
      if [ -n "$PREV" ]; then
        curl -sS --fail --request DELETE --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
          "$CI_API_V4_URL/projects/$CI_PROJECT_ID/merge_requests/$CI_MERGE_REQUEST_IID/notes/$PREV"
      fi
```

---

Наверх — [все ревьюеры](../../README.md) · [open-code-review](../../reviewers/open-code-review/README.md).
