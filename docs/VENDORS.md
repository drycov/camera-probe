
---

# 📷 Supported Vendors

Этот документ описывает **поддержку конкретных вендоров** в проекте **camera-probe**, особенности их API, используемые протоколы, ограничения и уровень надёжности определения.

На текущий момент официально поддерживаются:

* **Dahua**
* **Hikvision**

---

## 📌 Общая модель поддержки

Для каждого вендора система использует одинаковый пайплайн:

```
Discovery
  ├─ TCP ports
  ├─ RTSP
  └─ HTTP probe
        ↓
Fingerprint (confidence)
        ↓
Vendor Adapter
  ├─ Client (HTTP / RTSP)
  ├─ DeviceExtractor
  ├─ NetworkExtractor
  └─ NtpExtractor
```

Различия заключаются **только в инфраструктурной реализации**.

---

# 🟦 Dahua

## 🔌 Протоколы и интерфейсы

| Назначение         | Используется               |
| ------------------ | -------------------------- |
| Device info        | CGI (`magicBox.cgi`)       |
| Network config     | CGI (`configManager.cgi`)  |
| Firmware / version | CGI (`getSoftwareVersion`) |
| RTSP               | TCP 554 (Digest auth)      |
| HTTP auth          | Basic / Digest             |

---

## 📡 Используемые эндпоинты

### Device info

```
/cgi-bin/magicBox.cgi?action=getSystemInfo
/cgi-bin/main-cgi?action=getDeviceInfo   (fallback)
```

**Формат ответа:**
`key=value` (plain text)

---

### Network config

```
/cgi-bin/configManager.cgi?action=getConfig&name=Network
```

**Формат ответа:**
`table.Network.*` key-value

---

### Firmware / software

```
/cgi-bin/magicBox.cgi?action=getSoftwareVersion
```

Пример:

```
version=2.800.0000000.7.R,build:2024-07-22
```

---

## 🧠 Извлечение данных (Extractors)

### DeviceExtractor (Dahua)

Извлекаемые поля:

| Поле     | Источник key                    |
| -------- | ------------------------------- |
| model    | `deviceType`, `model`           |
| serial   | `serialNumber`, `serialNo`      |
| firmware | `version`, `softwareVersion`    |
| mac      | `mac`, `macAddress` (если есть) |

⚠️ **MAC чаще берётся из NetworkExtractor**, device-уровень используется как fallback.

---

### NetworkExtractor (Dahua)

Извлекаемые поля:

| Поле    | Источник                       |
| ------- | ------------------------------ |
| ip      | `table.Network.ethX.IPAddress` |
| mask    | `SubnetMask`                   |
| gateway | `DefaultGateway`               |
| mac     | `PhysicalAddress`              |
| subnet  | вычисляется                    |

---

## 🧪 Confidence модель (Dahua)

| Сценарий                       | Confidence |
| ------------------------------ | ---------- |
| Fingerprint + Device + Network | ~0.95      |
| Fingerprint + Network          | ~0.60      |
| Только RTSP                    | <0.50      |

Если confidence < `min_confidence`, ProbeService может перейти к fallback.

---

## ⚠️ Особенности и ограничения (Dahua)

* CGI иногда требует **forced Basic auth**
* Некоторые модели:

  * не возвращают MAC в device info
  * возвращают неполный network config
* Firmware строка **не нормализована** (vendor-specific формат)

---

# 🟥 Hikvision

## 🔌 Протоколы и интерфейсы

| Назначение     | Используется |
| -------------- | ------------ |
| Device info    | ISAPI (XML)  |
| Network config | ISAPI (XML)  |
| NTP            | ISAPI (XML)  |
| RTSP           | TCP 554      |
| HTTP auth      | Digest       |

---

## 📡 Используемые эндпоинты

### Device info

```
/ISAPI/System/deviceInfo
```

**Формат:** XML

---

### Network interfaces

```
/ISAPI/System/Network/interfaces
```

Возвращает:

* `<NetworkInterface>` — один интерфейс
* `<NetworkInterfaceList>` — несколько интерфейсов

---

## 🔀 Bridge / Multi-NIC поведение

Hikvision часто возвращает **несколько сетевых интерфейсов**, например:

* LAN1
* LAN2
* Bridge

### Текущая логика:

* используется **первый `<NetworkInterface>`**
* gateway/subnet вычисляется по нему
* остальные интерфейсы игнорируются

⚠️ Это осознанное решение для:

* предсказуемости
* совместимости с CLI / ERP

---

## 🧠 Извлечение данных (Extractors)

### NetworkExtractor (Hikvision)

Извлекаемые поля:

| Поле    | XML path                   |
| ------- | -------------------------- |
| ip      | `IPAddress/ipAddress`      |
| mask    | `IPAddress/subnetMask`     |
| gateway | `DefaultGateway/ipAddress` |
| mac     | `Link/MACAddress`          |
| subnet  | вычисляется                |

Поддерживается:

* namespace-aware XML
* `<NetworkInterfaceList>`
* `<NetworkInterface>` напрямую

---

### DeviceExtractor (Hikvision)

(может отличаться по моделям)

Извлекаемые поля:

* model
* serial
* firmware
* manufacturer

---

## 🧪 Confidence модель (Hikvision)

| Сценарий                             | Confidence |
| ------------------------------------ | ---------- |
| Fingerprint + ISAPI device + network | ~0.97      |
| Fingerprint + RTSP                   | ~0.80      |
| Только RTSP                          | <0.60      |

Hikvision имеет **самый высокий confidence** среди поддерживаемых вендоров.

---

## ⚠️ Особенности и ограничения (Hikvision)

* ISAPI **строго требует Digest auth**
* Некоторые модели:

  * скрывают часть полей без admin-доступа
  * возвращают неполный XML
* Возможны:

  * dual-NIC
  * bridge-интерфейсы
  * IPv6-only узлы (пока не поддержаны)

---

# 📊 Сравнение вендоров

| Критерий       | Dahua          | Hikvision     |
| -------------- | -------------- | ------------- |
| Device API     | CGI (text)     | ISAPI (XML)   |
| Network API    | CGI            | ISAPI         |
| Auth           | Basic / Digest | Digest        |
| Multi-NIC      | редкость       | часто         |
| Confidence max | ~0.95          | ~0.97         |
| Stability      | высокая        | очень высокая |

---

## 🧩 Добавление нового вендора

Рекомендуемый минимум:

* RTSP fingerprint
* HTTP endpoint probe
* NetworkExtractor (STRICT)
* DeviceExtractor (OPTIONAL)

---

## 📎 Связанные документы

* `README.md`
* `docs/ARCHITECTURE.md`
* `docs/CONTRIBUTING.md`
* `docs/CONFIDENCE.md`
* `docs/FINGERPRINTS.md`

---
