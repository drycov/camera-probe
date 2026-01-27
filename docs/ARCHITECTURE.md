
---

# 🏗️ Architecture

Этот документ описывает архитектуру проекта **camera-probe**, его слои, границы ответственности и правила расширения.

Проект спроектирован по принципам **Clean Architecture** с жёстким разделением:

* **что** делает система (domain / application),
* **как** она это делает (infrastructure),
* **как** с ней взаимодействуют (API / CLI).

---

## 🎯 Цели архитектуры

* Чёткое разделение ответственности
* Минимизация vendor lock-in
* Возможность использовать проект:

  * как библиотеку
  * как CLI
  * как backend-компонент
* Простое добавление новых вендоров и протоколов
* Предсказуемое поведение и тестируемость

---

## 🧱 Общая схема

```
┌─────────────────────────────┐
│        CLI / Public API     │
│  (camera_probe.api, CLI)   │
└───────────────▲─────────────┘
                │
┌───────────────┴─────────────┐
│        Application Layer    │
│   (ProbeService, DTO)      │
└───────────────▲─────────────┘
                │
┌───────────────┴─────────────┐
│          Domain Layer       │
│   (Models, Ports, Policy)  │
└───────────────▲─────────────┘
                │
┌───────────────┴─────────────┐
│      Infrastructure Layer  │
│ (Adapters, Clients, CGI,   │
│  ISAPI, RTSP, XML, HTTP)   │
└─────────────────────────────┘
```

**Зависимости направлены строго сверху вниз.**
Нижние слои **никогда** не импортируют верхние.

---

## 📦 Слои и ответственность

### 1️⃣ Public API / CLI

**Пакеты:**

* `camera_probe.api`
* `camera_probe.interface.cli`

**Назначение:**

* Единая точка входа для пользователей
* Стабильный контракт
* Никакой бизнес-логики

**Пример:**

```python
from camera_probe import probe, scan
```

CLI использует **тот же API**, что и библиотека.

---

### 2️⃣ Application Layer

**Пакеты:**

* `camera_probe.application.services`
* `camera_probe.application.dto`
* `camera_probe.application.policies`

**Назначение:**

* Оркестрация use-case’ов
* Управление сценариями:

  * discovery → vendor probe → fallback
* Принятие решений (confidence, force, prefer_force)

**Ключевой класс:**

```python
ProbeService
```

**Важно:**

* ❌ Нет HTTP, RTSP, XML
* ❌ Нет логирования инфраструктуры
* ❌ Нет vendor-specific кода

---

### 3️⃣ Domain Layer

**Пакеты:**

* `camera_probe.domain.models`
* `camera_probe.domain.ports`

**Назначение:**

* Чистые модели данных
* Абстрактные контракты (ports)
* Нулевая зависимость от инфраструктуры

**Примеры моделей:**

* `ProbeResult`
* `DetectResult`
* `NetworkInfo`
* `NtpInfo`

**Примеры портов:**

* `DiscoveryPort`
* `AdapterFactory`
* `DeviceExtractor`
* `NetworkExtractor`

Domain — **самый стабильный слой**.

---

### 4️⃣ Infrastructure Layer

**Пакеты:**

* `camera_probe.infrastructure.adapters`
* `camera_probe.infrastructure.clients`
* `camera_probe.infrastructure.discovery`
* `camera_probe.infrastructure.device`
* `camera_probe.infrastructure.network`
* `camera_probe.infrastructure.ntp`

**Назначение:**

* Реальная работа с камерами
* HTTP / RTSP / CGI / ISAPI
* XML / key=value / SDP parsing
* Vendor-специфичные особенности

---

## 🔌 Adapter Pattern (ключевая идея)

Каждый вендор представлен **адаптером**:

```
Adapter
 ├── Client        (transport)
 ├── DeviceExtractor
 ├── NetworkExtractor
 └── NtpExtractor
```

### Пример

```python
@register_adapter("dahua")
class DahuaAdapter(BaseCameraAdapter):
    async def probe(self) -> ProbeResult:
        ...
```

Адаптер:

* знает **только своего вендора**
* возвращает **ProbeResult**
* может быть заменён без изменения Application слоя

---

## 🧠 Extractor Policy

Экстракторы создаются через фабрику с политикой:

```python
ExtractorPolicy.STRICT
ExtractorPolicy.OPTIONAL
```

### Поведение

| Policy   | Экстрактор не найден | Ошибка |
| -------- | -------------------- | ------ |
| STRICT   | ❌ Exception          | ❌      |
| OPTIONAL | ✅ None               | ❌      |

Это позволяет:

* строго требовать network info
* мягко обрабатывать device info

---

## 🧬 Registry System

Используется **регистрационная модель**:

* `AdapterRegistry`
* `ClientRegistry`
* `DeviceExtractorRegistry`
* `NetworkExtractorRegistry`

Регистрация происходит через декораторы:

```python
@register_device_extractor("dahua")
class DahuaDeviceExtractor:
    ...
```

Преимущества:

* Нет switch/case
* Нет if vendor == ...
* Расширение без модификации ядра

---

## 🧪 Error Handling Strategy

* Infrastructure может бросать исключения
* Application слой:

  * ловит
  * решает fallback / confidence
* Public API возвращает **всегда ProbeResult**
  (кроме фатальных ошибок)

---

## 🧠 Confidence Model

`confidence` отражает **насколько надёжно** определена камера:

* fingerprint match
* RTSP / HTTP evidence
* успешность vendor probe

Используется для:

* принятия решения о fallback
* фильтрации результатов scan

---

## 🔒 Границы стабильности

### ✅ Stable API

* `camera_probe.api`
* `ProbeResult`, `NetworkInfo`, `NtpInfo`
* CLI arguments

### ⚠️ Internal (может меняться)

* `infrastructure/*`
* `application/*`
* registries / extractors

---

## 🧩 Как добавить нового вендора

1. Client (transport)
2. Adapter
3. Extractors (device / network / ntp)
4. Fingerprint (опционально)

❌ Не требуется менять `ProbeService`

---

## 📌 Принципы проекта

* Explicit > implicit
* Composition > inheritance
* Registry > conditionals
* Domain is king
* Public API is sacred

---

## 📎 Связанные документы

* `README.md`
* `docs/CONTRIBUTING.md`
* `docs/VENDORS.md`
* `docs/FINGERPRINTS.md`
* `docs/CONFIDENCE.md`

---
