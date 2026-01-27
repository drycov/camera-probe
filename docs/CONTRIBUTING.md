
---

# 🤝 Contributing to camera-probe

Спасибо за интерес к проекту **camera-probe** 🎉
Этот документ описывает **правила и принципы участия в разработке**, чтобы кодовая база оставалась устойчивой, расширяемой и предсказуемой.

Проект ориентирован на:

* production-использование
* долгосрочную поддержку
* аккуратную архитектуру

---

## 🧭 Основные принципы

Перед любым вкладом убедитесь, что вы разделяете следующие принципы:

* **Clean Architecture**
* **Явное лучше неявного**
* **Domain > Infrastructure**
* **Public API — священен**
* **Никаких shortcut’ов ради “быстрее”**

Если изменение ломает архитектуру — оно не будет принято.

---

## 🧱 Архитектурные правила (обязательно)

### 1️⃣ Направление зависимостей

Допустимо:

```
api / cli
  ↓
application
  ↓
domain
  ↓
infrastructure
```

❌ Запрещено:

* `domain` → `infrastructure`
* `application` → `infrastructure.http`
* `domain` → `xml / http / rtsp`

---

### 2️⃣ Domain слой

**Domain — чистый и изолированный.**

Разрешено:

* dataclasses / pydantic models
* enums
* Protocol / ABC
* business-смысл

Запрещено:

* logging
* requests / httpx
* xml / json parsing
* vendor-специфичный код

---

### 3️⃣ Application слой

Application:

* оркестрирует use-case
* принимает решения
* обрабатывает fallback / confidence

Запрещено:

* прямое обращение к HTTP / RTSP
* парсинг XML / CGI
* vendor-specific логика

---

### 4️⃣ Infrastructure слой

Infrastructure — **единственное место**, где разрешено:

* HTTP / RTSP
* CGI / ISAPI
* XML parsing
* vendor-специфичные хаки

Но даже здесь:

* не смешивать transport и parsing
* использовать extractors
* регистрировать через registry

---

## 🧩 Добавление нового вендора

### Минимальный чек-лист

1. **Client**

   * transport-only
   * возвращает RAW данные

2. **Adapter**

   * собирает данные
   * возвращает `ProbeResult`

3. **Extractors**

   * DeviceExtractor (OPTIONAL)
   * NetworkExtractor (STRICT)
   * NtpExtractor (OPTIONAL)

4. **Fingerprint**

   * если возможно
   * с реальными признаками

❌ Не править `ProbeService`

---

## 🧬 Регистрация компонентов

Используйте **только декораторы**:

```python
@register_adapter("vendor")
@register_device_extractor("vendor")
@register_network_extractor("vendor")
```

❌ Не использовать `if vendor == ...`

---

## 🧪 Тестирование

### Минимальные требования

* новый код **не ломает probe**
* CLI продолжает работать
* scan работает инкрементально

Рекомендуется:

* тестировать на **реальных камерах**
* сохранять RAW ответы (обезличенные)

---

## 🧹 Стиль кода

### Форматирование

Проект использует:

* `ruff`
* `black` (совместимый стиль)

Обязательно перед PR:

```bash
ruff check .
ruff check . --select=F401,F841
```

> `F401`, `F841` — мгновенно находят мёртвый код

---

### Импорты

* абсолютные импорты
* один import на строку
* никаких wildcard кроме `__all__`

---

## 🔒 Public API правила

❗ **Любые изменения в `camera_probe.api` требуют особого внимания.**

Запрещено:

* менять сигнатуры `probe()` / `scan()`
* менять семантику `ProbeResult`
* менять типы возвращаемых данных

Разрешено:

* добавлять новые поля с backward compatibility
* добавлять новые функции

---

## 🧠 Confidence и fingerprints

* Не увеличивать confidence без реальных оснований
* Не добавлять fingerprint «на глаз»
* Любое правило должно быть объяснимо

См.:

* `docs/CONFIDENCE.md`
* `docs/FINGERPRINTS.md`

---

## 📝 Документация

Любое значимое изменение должно сопровождаться:

* обновлением `docs/`
* либо комментарием **почему документация не требуется**

---

## 🚀 Pull Request процесс

1. Fork репозитория

2. Feature branch:

   ```
   feature/vendor-axis
   fix/network-parser
   ```

3. Чёткое описание:

   * что изменено
   * зачем
   * какие риски

4. PR без логов, ключей, паролей

---

## ❌ Что не принимается

* быстрые хаки
* vendor-specific код в application
* hardcoded IP / credentials
* “оно у меня работает”

---

## 📎 Связанные документы

* `README.md`
* `docs/ARCHITECTURE.md`
* `docs/CONFIDENCE.md`
* `docs/VENDORS.md`
* `docs/FINGERPRINTS.md`

---

## 🙌 Спасибо

camera-probe — это инженерный инструмент.
Мы ценим **аккуратность**, **обоснованность решений** и **чистую архитектуру**.

Если сомневаешься — лучше спросить перед реализацией.

---
