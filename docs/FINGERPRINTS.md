
---

# 🧬 docs/FINGERPRINTS.md

## Fingerprints

Fingerprint — это механизм **определения вендора камеры без аутентификации**, на основе сетевых и протокольных признаков.

Fingerprint используется **только на этапе discovery**.

---

## 🎯 Задачи fingerprint

* определить вендора до vendor probe
* выбрать правильный adapter
* присвоить начальный confidence
* работать без логина/пароля

---

## 🔍 Источники fingerprint

Fingerprint анализирует:

### RTSP

* `Server` header
* SDP attributes
* vendor-specific SDP строки
* control URLs

### HTTP

* response headers
* URL patterns (`/ISAPI/`, `/cgi-bin/`)
* status codes

### TCP

* открытые порты (554, 8000, 80, 443)
* типичные комбинации портов

---

## 🧠 Fingerprint registry

Каждый fingerprint — отдельный класс:

```python
class HikvisionFingerprint(BaseFingerprint):
    vendor = "hikvision"

    def match(self, evidence) -> float | None:
        ...
```

Регистрируются автоматически.

---

## 🟦 Hikvision fingerprint

### Признаки

* RTSP SDP содержит:

  * `hikvision`
  * `Media_header:MEDIAINFO`
* HTTP probe:

  * `/ISAPI/System/deviceInfo`
* Типичные порты:

  * 80 + 554
  * 443 + 554

### Confidence

| Условие     | Confidence |
| ----------- | ---------- |
| SDP + ISAPI | ~0.97      |
| SDP markers | ~0.85      |
| Только HTTP | ~0.70      |

---

## 🟦 Dahua fingerprint

### Признаки

* RTSP:

  * Digest realm с характерным format
* SDP:

  * Dahua-типичные `appversion`
* HTTP:

  * `/cgi-bin/magicBox.cgi`

### Confidence

| Условие     | Confidence |
| ----------- | ---------- |
| RTSP + CGI  | ~0.97      |
| Только RTSP | ~0.75      |
| Только CGI  | ~0.65      |

---

## ⚠️ Ограничения fingerprint

Fingerprint **не гарантирует**:

* корректную модель
* доступность device info
* корректный firmware
* отсутствие NAT / proxy

Он отвечает только на вопрос:

> «С какой вероятностью это камера данного вендора»

---

## 🧩 Fingerprint vs Adapter

| Fingerprint | Adapter      |
| ----------- | ------------ |
| Без auth    | Требует auth |
| Быстро      | Медленнее    |
| Нет модели  | Даёт модель  |
| Эвристика   | Факты        |

Они **дополняют**, а не заменяют друг друга.

---

## 🧪 Ошибочные сценарии

* OEM-камеры (Hik-OEM, Dahua-OEM)
* Камеры с кастомной прошивкой
* RTSP proxy / NVR

В этих случаях:

* fingerprint может быть «частично верным»
* confidence будет < 0.7
* ProbeService может пойти в fallback

---

## 🧩 Добавление нового fingerprint

Минимум:

1. RTSP marker
2. HTTP path
3. Confidence mapping

❌ Не добавлять fingerprint без реальных тестов

---

## 📎 Связанные документы

* `README.md`
* `docs/ARCHITECTURE.md`
* `docs/CONTRIBUTING.md`
* `docs/CONFIDENCE.md`
* `docs/VENDORS.md`
---

