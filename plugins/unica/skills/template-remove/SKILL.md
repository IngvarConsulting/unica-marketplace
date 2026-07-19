---
name: template-remove
description: Удалить макет из объекта 1С (обработка, отчёт, справочник, документ и др.)
argument-hint: <ObjectName> <TemplateName>
disable-model-invocation: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# /template-remove — Удаление макета

## MCP routing

- Preferred path: use MCP `unica` tool `unica.template.remove`; `unica` owns XML/JSON DSL work and refreshes related workspace caches after mutations.
- Do not call internal MCP/CLI adapters directly. They are hidden behind `unica` and synchronized by the orchestrator.
- Execution path: call MCP `unica` tool `unica.template.remove`; skill-local operation scripts are not part of the workflow.
- For mutating operations, pass `dryRun: false` only when the user explicitly requested the change; otherwise keep the default dry run.
- Vendor support guard runs inside `unica`; if it blocks a locked/read-only supported object, prefer CFE/release-support or an explicit support-state change plan instead of editing raw support metadata.

Удаляет макет и убирает его регистрацию из корневого XML объекта.

## Usage

```
/template-remove <ObjectName> <TemplateName>
```

| Параметр     | Обязательный | По умолчанию | Описание                            |
|--------------|:------------:|--------------|-------------------------------------|
| ObjectName   | да           | —            | Имя объекта                         |
| TemplateName | да           | —            | Имя макета для удаления             |
| SrcDir       | нет          | `src`        | Каталог исходников                  |

## MCP вызов

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "unica.template.remove",
    "arguments": {
      "cwd": "<workspace>",
      "ObjectName": "ОтчетПродажи",
      "TemplateName": "СтарыйМакет",
      "SrcDir": "src/Reports",
      "dryRun": false
    }
  }
}
```

## Что удаляется

```
<SrcDir>/<ObjectName>/Templates/<TemplateName>.xml     # Метаданные макета
<SrcDir>/<ObjectName>/Templates/<TemplateName>/         # Каталог макета (рекурсивно)
```

## Что модифицируется

- `<SrcDir>/<ObjectName>.xml` — убирается `<Template>` из `ChildObjects`
- Для ExternalReport/Report: если удалённый макет был указан в `MainDataCompositionSchema` — значение очищается
