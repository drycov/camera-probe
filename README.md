
---

# 📷 camera-probe

**camera-probe** — это асинхронная Python-библиотека и CLI-утилита для
**обнаружения, идентификации и диагностики IP-камер** (CCTV, NVR, PTZ).

Проект спроектирован по принципам **Clean Architecture** и подходит как для:

* автоматизированного inventory,
* мониторинга камер,
* интеграции в ERP / NMS / SOC,
* массового сканирования сетей.

---

## ✨ Возможности

* 🔍 **Автоопределение вендора** (Hikvision, Dahua, Axis, …)
* 📡 **RTSP / HTTP / ISAPI / CGI probing**
* 🌐 Получение **сетевой конфигурации** (IP, mask, gateway, MAC)
* ⏱️ Проверка **NTP**
* 📊 **Confidence score** (насколько уверенно определена камера)
* ⚡ Асинхронное **сканирование CIDR**
* 🧩 Расширяемая архитектура (adapters / extractors / fingerprints)
* 🧱 Один код для **CLI и библиотеки**

---

## 📦 Установка

```bash
pip install camera-probe
```

Или из исходников:

```bash
git clone https://github.com/your-org/camera-probe.git
cd camera-probe
pip install -e .
```

---

## 🚀 Быстрый старт (как библиотека)

### Probe одного IP

```python
import asyncio
from camera_probe import probe


async def main():
    result = await probe(
        ip="192.168.1.64",
        username="admin",
        password="12345",
    )

    print("IP:", result.ip)
    print("Vendor:", result.vendor)
    print("Model:", result.model)
    print("Confidence:", result.confidence)


if __name__ == "__main__":
    asyncio.run(main())
```

---

### Scan CIDR (асинхронно)

```python
import asyncio
from camera_probe import scan


async def main():
    async for result in scan(
        cidr="10.165.64.0/24",
        username="admin",
        password="12345",
        concurrency=20,
    ):
        print(
            f"{result.ip:15} "
            f"{result.vendor or '-':10} "
            f"{result.confidence:.2f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧩 Публичный API

Поддерживаются **только** следующие импорты:

```python
from camera_probe import (
    probe,
    scan,
    ProbeResult,
    NetworkInfo,
    NtpInfo,
)
```

### `probe(...) → ProbeResult`

```python
await probe(
    ip: str,
    username: str | None = None,
    password: str | None = None,
    timeout: float = 5.0,
    force: bool = False,
    prefer_force: bool = False,
)
```

### `scan(...) → AsyncIterator[ProbeResult]`

```python
async for result in scan(
    cidr: str,
    username: str | None = None,
    password: str | None = None,
    timeout: float = 5.0,
    concurrency: int = 20,
):
    ...
```

❗ **Всё остальное (`application/*`, `infrastructure/*`) — не является публичным API**
и может меняться без предупреждения.

---

## 🖥️ Использование CLI

### Probe камеры

```bash
camera-probe probe --ip 192.168.1.64 --user admin --password 12345
```

### JSON-вывод

```bash
camera-probe probe --ip 192.168.1.64 --json
```

### Scan сети

```bash
camera-probe scan 10.165.64.0/24 --user admin --password 12345
```

---

## 📄 Пример вывода (human)

```
IP:         10.165.64.10
Vendor:     Dahua
Model:      DH-SD49225T-HN-150IR
Serial:     4L067E8PAJ435EC
MAC:        9C:14:63:49:86:8E
Firmware:   2.800.0000000.7.R
Network:
  IP:       10.165.64.10
  Gateway:  10.165.64.9
  Netmask:  255.255.255.248
```

---

## 🧠 Архитектура

Проект построен по **Clean Architecture**:

```
CLI / Public API
        ↓
Application (Use Cases)
        ↓
Domain (Models, Ports)
        ↓
Infrastructure (Adapters, Clients)
```

### Ключевые принципы

* CLI и библиотека используют **один и тот же API**
* Вендор-специфика изолирована
* Domain ничего не знает про HTTP / RTSP
* Лёгкое добавление новых камер и протоколов

---

## 🧪 Надёжность и ошибки

Возможные исключения:

* `TimeoutError` — камера не ответила
* `ConnectionError` — сетевая ошибка
* `ValueError` — некорректные параметры
* `RuntimeError` — внутренняя ошибка (bug)

Рекомендуется оборачивать вызовы в `try/except`.

---

## 📌 Версионирование

Используется **Semantic Versioning (SemVer)**:

* `MAJOR` — breaking changes в public API
* `MINOR` — новые возможности
* `PATCH` — исправления

Текущая версия доступна как:

```python
from camera_probe import __version__
```

---

## 🛣️ Roadmap

* [ ] `probe_sync()` / `scan_sync()`
* [ ] Расширение fingerprint’ов
* [ ] Экспорт в Prometheus / JSON Schema
* [ ] Axis / ONVIF deep-support
* [ ] Metrics & health-checks

---

## 🤝 Вклад

Pull requests приветствуются.
Перед крупными изменениями — открой issue для обсуждения.

---

## 📜 Лицензия

MIT License © Denis Rykov

---

