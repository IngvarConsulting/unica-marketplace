---
name: cfe-patch-method
description: Генерация перехватчика метода в расширении 1С (CFE). Используй когда нужно перехватить метод заимствованного объекта — вставить код до, после или вместо оригинального
argument-hint: -ExtensionPath <path> -ModulePath "Catalog.X.ObjectModule" -MethodName "ПриЗаписи" -InterceptorType Before
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /cfe-patch-method — Генерация перехватчика метода

## MCP routing

- Preferred path: use MCP `unica` tool `unica.cfe.patch_method`; `unica` owns XML/JSON DSL work and refreshes related workspace caches after mutations.
- Do not call internal MCP/CLI adapters directly. They are hidden behind `unica` and synchronized by the orchestrator.
- Execution path: call MCP `unica` tool `unica.cfe.patch_method`; skill-local operation scripts are not part of the workflow.
- For mutating operations, pass `dryRun: false` only when the user explicitly requested the change; otherwise keep the default dry run.

Генерирует `.bsl` файл с декоратором перехвата для заимствованного объекта расширения. Создаёт файл или дописывает в существующий.

## Предусловие

Объект должен быть заимствован в расширение (`/cfe-borrow`). Скрипт читает `NamePrefix` из `Configuration.xml` расширения для формирования имени процедуры.

## Параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `ExtensionPath` | Путь к расширению (обязат.) | — |
| `ModulePath` | Путь к модулю (обязат.) | — |
| `MethodName` | Имя перехватываемого метода (обязат.) | — |
| `InterceptorType` | `Before` / `After` / `ModificationAndControl` (обязат.) | — |
| `Context` | Директива контекста | `НаСервере` |
| `IsFunction` | Метод — функция (добавит `Возврат`) | false |

## Формат ModulePath

| ModulePath | Файл |
|------------|------|
| `Catalog.X.ObjectModule` | `Catalogs/X/Ext/ObjectModule.bsl` |
| `Catalog.X.ManagerModule` | `Catalogs/X/Ext/ManagerModule.bsl` |
| `Catalog.X.Form.Y` | `Catalogs/X/Forms/Y/Ext/Form/Module.bsl` |
| `CommonModule.X` | `CommonModules/X/Ext/Module.bsl` |
| `Document.X.ObjectModule` | `Documents/X/Ext/ObjectModule.bsl` |
| `Document.X.Form.Y` | `Documents/X/Forms/Y/Ext/Form/Module.bsl` |

Аналогично для Report, DataProcessor, InformationRegister и других типов.

## Типы перехвата

| InterceptorType | Декоратор | Назначение |
|-----------------|-----------|------------|
| `Before` | `&Перед` | Код до вызова оригинального метода |
| `After` | `&После` | Код после вызова оригинального метода |
| `ModificationAndControl` | `&ИзменениеИКонтроль` | Копия тела метода с маркерами `#Вставка`/`#Удаление` |

## MCP вызов

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "unica.cfe.patch_method",
    "arguments": {
      "cwd": "<workspace>",
      "ExtensionPath": "src/extensions/MyExtension",
      "ModulePath": "Catalog.Контрагенты.ObjectModule",
      "MethodName": "ПриЗаписи",
      "InterceptorType": "Before",
      "dryRun": false
    }
  }
}
```

## Примеры

### Перехват Перед на сервере

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "unica.cfe.patch_method",
    "arguments": {
      "cwd": "<workspace>",
      "ExtensionPath": "src",
      "ModulePath": "Catalog.Контрагенты.ObjectModule",
      "MethodName": "ПриЗаписи",
      "InterceptorType": "Before",
      "dryRun": false
    }
  }
}
```

### Перехват После на клиенте

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "unica.cfe.patch_method",
    "arguments": {
      "cwd": "<workspace>",
      "ExtensionPath": "src",
      "ModulePath": "Document.Заказ.Form.ФормаДокумента",
      "MethodName": "ПослеЗаписиНаСервере",
      "InterceptorType": "After",
      "Context": "НаКлиенте",
      "dryRun": false
    }
  }
}
```

### ИзменениеИКонтроль для функции

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "unica.cfe.patch_method",
    "arguments": {
      "cwd": "<workspace>",
      "ExtensionPath": "src",
      "ModulePath": "CommonModule.ОбщийМодуль",
      "MethodName": "ПолучитьДанные",
      "InterceptorType": "ModificationAndControl",
      "IsFunction": true,
      "dryRun": false
    }
  }
}
```
## Генерируемый код (Before)

```bsl
&НаСервере
&Перед("ПриЗаписи")
Процедура Расш1_ПриЗаписи()
	// TODO: код перед вызовом оригинального метода
КонецПроцедуры
```
