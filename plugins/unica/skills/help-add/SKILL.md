---
name: help-add
description: Добавить встроенную справку к объекту 1С (обработка, отчёт, справочник, документ и др.). Используй когда пользователь просит добавить справку, help, встроенную помощь к объекту
argument-hint: <ObjectName>
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# /help-add — Добавление справки

Добавляет встроенную справку к объекту: файл метаданных `Help.xml`, HTML-страницу и при необходимости обновляет метаданные форм.

## MCP routing

- Preferred path: use MCP `unica` tool `unica.help.add`; `unica` owns metadata/form writes and refreshes related workspace caches after mutations.
- Do not call internal MCP/CLI adapters directly. They are hidden behind `unica` and synchronized by the orchestrator.
- Execution path: call MCP `unica` tool `unica.help.add`; skill-local operation scripts are not part of the workflow.
- For mutating operations, pass `dryRun: false` only when the user explicitly requested the change; otherwise keep the default dry run.
- Vendor support guard runs inside `unica`; if it blocks a locked/read-only supported object, prefer CFE/release-support or an explicit support-state change plan instead of editing raw support metadata.

## Usage

```
/help-add <ObjectName> [Lang] [SrcDir]
```

| Параметр   | Обязательный | По умолчанию | Описание                            |
|------------|:------------:|--------------|-------------------------------------|
| ObjectName | да           | —            | Путь объекта относительно SrcDir (например `Catalogs/МойСправочник`, `DataProcessors/МояОбработка`) |
| Lang       | нет          | `ru`         | Код языка справки                   |
| SrcDir     | нет          | `src`        | Каталог исходников                  |

## MCP вызов

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "unica.help.add",
    "arguments": {
      "cwd": "<workspace>",
      "ObjectName": "Catalogs/МойСправочник",
      "Lang": "ru",
      "SrcDir": "src",
      "dryRun": false
    }
  }
}
```

## Что делает Unica

- Создаёт `Ext/Help.xml` и `Ext/Help/ru.html` — шаблон справки
- Если у объекта есть формы — добавляет `<IncludeHelpInContents>` в метаданные форм (если отсутствует)
- Справка **не регистрируется** в `ChildObjects` — достаточно наличия файлов

## После запуска

Отредактируй `Ext/Help/ru.html` — наполни содержимым справки (стандартный HTML: `<h1>`..`<h4>`, `<p>`, `<ul>`, `<table>` и т.д.). Кнопка справки появится автоматически через `Autofill` в AutoCommandBar формы.
