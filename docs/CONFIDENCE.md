---

# 📊 docs/CONFIDENCE.md

## Confidence Model

В `camera-probe` **confidence** — это числовая оценка (0.0 … 1.0), отражающая **насколько надёжно** система определила камеру и извлекла данные.

Confidence используется:

* для принятия решений в `ProbeService`
* для fallback-логики
* для фильтрации результатов при `scan`
* как сигнал качества данных для внешних систем (ERP, monitoring)

---

## 🎯 Зачем нужен confidence

В реальных сетях камеры:

* могут отвечать частично
* могут маскироваться под другой вендор
* могут быть за NAT / proxy
* могут отдавать RTSP без HTTP
* могут иметь сломанный ISAPI / CGI

Confidence позволяет:

* **не считать результат бинарным**
* отличать «точно Hikvision» от «похоже на Hikvision»
* не ломать пайплайн из-за частичного ответа

---

## 🧠 Источники confidence

Confidence формируется **поэтапно**.

### 1️⃣ Discovery phase

Используются:

* RTSP response
* SDP attributes
* HTTP headers
* vendor hints
* открытые порты

Результат:

```python
DetectResult(
    vendor="Hikvision",
    confidence=0.97,
    method="fingerprint",
)
```

⚠️ Discovery **не извлекает модель/serial**, только определяет вендора.

---

### 2️⃣ Vendor probe phase

После discovery выполняется vendor-specific adapter:

* HTTP / ISAPI / CGI
* DeviceExtractor
* NetworkExtractor
* NtpExtractor

Результат: `ProbeResult`

---

## 📐 Диапазоны confidence

### Общая шкала

| Confidence | Интерпретация             |
| ---------- | ------------------------- |
| 0.95–1.00  | Практически гарантировано |
| 0.80–0.94  | Высокая уверенность       |
| 0.60–0.79  | Частичное подтверждение   |
| 0.40–0.59  | Слабое совпадение         |
| < 0.40     | Ненадёжно                 |

---

## 🟦 Dahua: confidence модель

| Сценарий                       | Confidence |
| ------------------------------ | ---------- |
| Fingerprint + Device + Network | ~0.95      |
| Fingerprint + Network          | ~0.60      |
| Только RTSP                    | ~0.45      |
| Только TCP ports               | <0.30      |

Причины понижения:

* CGI может быть урезан
* device info часто неполный
* firmware формат нестандартизирован

---

## 🟥 Hikvision: confidence модель

| Сценарий                             | Confidence |
| ------------------------------------ | ---------- |
| Fingerprint + ISAPI device + network | ~0.97      |
| Fingerprint + RTSP                   | ~0.80      |
| Только RTSP                          | ~0.55      |

Hikvision даёт более стабильные и структурированные ответы → confidence выше.

---

## 🧩 Использование confidence в ProbeService

Упрощённо:

```python
if is_probe_success(result.confidence, min_confidence):
    return result

if prefer_force and has_creds:
    return force_probe()
```

Где:

* `min_confidence` по умолчанию = `0.7`
* `prefer_force` — пользовательское решение

---

## ⚙️ Почему confidence — это не «score»

Важно:

* confidence **не математически строгий**
* это **инженерная эвристика**
* он отражает опыт эксплуатации камер в реальных сетях

Цель:

> лучше вернуть честный `0.6`, чем ложный `1.0`

---

## 🔒 Контракт стабильности

* Диапазон `0.0–1.0` — стабилен
* Семантика уровней — стабильна
* Конкретные числа могут **немного корректироваться** между версиями

---

## 📎 Связанные документы

* `README.md`
* `docs/ARCHITECTURE.md`
* `docs/CONTRIBUTING.md`
* `docs/VENDORS.md`
* `docs/FINGERPRINTS.md`
---
