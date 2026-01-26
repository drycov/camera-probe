# camera-probe

Асинхронная библиотека и CLI-утилита для автоматической идентификации IP-камер (Hikvision, Dahua, Axis и др.), получения сетевых параметров и сервисной информации (NTP и пр.).

Проект ориентирован на **production‑использование**: инвентаризация, мониторинг, CMDB, SOC / NOC инструменты.

---

## Возможности

* 🔍 Автоопределение вендора (passive + active)
* 🔐 Аутентифицированный probe (Digest / Basic / Anonymous fallback)
* 🌐 Получение сетевых параметров (IP, mask, gateway, MAC)
* ⏱ Получение NTP конфигурации
* ⚡ Асинхронная архитектура (asyncio)
* 🧩 Расширяемая adapter‑архитектура
* 🛠 Использование как CLI и как библиотеки

Поддерживаемые вендоры:

* Hikvision (ISAPI)
* Dahua (CGI)
* Axis (VAPIX, базово)

---

## Установка

### Через pip

```bash
pip install camera-probe
```

### Из исходников

```bash
git clone https://github.com/your-org/camera-probe.git
cd camera-probe
pip install -e .
```

---

## Использование как CLI

### Простой запуск

```bash
camera-probe --ip 10.230.48.82 --user admin --password password
```

### Подробный вывод

```bash
camera-probe --ip 10.230.48.82 --user admin --password password --verbose
```

### Принудительный probe (без autodetect)

```bash
camera-probe --ip 10.230.48.82 --user admin --password password --force
```

Код возврата:

* `0` — успех
* `1` — ошибка идентификации
* `130` — прервано пользователем

---

## Использование как библиотеки

### Быстрый старт (async API)

```python
import asyncio
from camera_probe.probe import probe_camera_async

async def main():
    result = await probe_camera_async(
        ip="10.230.48.82",
        username="admin",
        password="password",
    )

    if result.success:
        print("Vendor:", result.vendor)
        print("Model:", result.model)
        print("Serial:", result.serial)
        print("MAC:", result.mac)

        if result.network:
            print("IP:", result.network.ip)
            print("Gateway:", result.network.gateway)

        if result.ntp:
            print("NTP server:", result.ntp.server)
    else:
        print("Probe failed:", result.error)

asyncio.run(main())
```

---

## Модель результата (`ProbeResult`)

```python
@dataclass
class ProbeResult:
    ip: str
    vendor: Optional[str]
    confidence: float

    model: Optional[str]
    serial: Optional[str]
    mac: Optional[str]
    firmware: Optional[str]

    network: Optional[NetworkInfo]
    ntp: Optional[NtpInfo]

    raw: Dict[str, Any]
    error: Optional[str]
```

### Проверка успеха

```python
if result.success:
    ...
```

> Успех определяется `confidence >= 0.7`, а не наличием одного поля.

---

## NetworkInfo

```python
@dataclass
class NetworkInfo:
    ip: Optional[str]
    mask: Optional[str]
    cidr: Optional[int]
    gateway: Optional[str]
    mac: Optional[str]
    gateway_in_subnet: Optional[bool]
```

Используется для:

* CMDB / inventory
* сетевой валидации
* поиска конфликтов IP

---

## NtpInfo

```python
@dataclass
class NtpInfo:
    enabled: Optional[bool]
    server: Optional[str]
    timezone: Optional[str]
    update_period: Optional[str]
    port: Optional[int]
    interval: Optional[int]
```

Поля могут быть `None` — модель мультивендорная.

---

## Управление стратегией probe

### Smart probe (рекомендуется)

```python
from camera_probe.orchestrators.smart_probe import SmartProbeOrchestrator
from camera_probe.discovery.config import DiscoveryConfig

orchestrator = SmartProbeOrchestrator(
    config=DiscoveryConfig(
        enable_rtsp_passive=True,
    )
)

result = await orchestrator.probe(
    ip="10.230.48.82",
    username="admin",
    password="password",
)
```

### Force probe

```python
from camera_probe.orchestrators.force_probe import ForceProbeOrchestrator

orchestrator = ForceProbeOrchestrator()

result = await orchestrator.probe(
    ip="10.230.48.82",
    username="admin",
    password="password",
)
```

---

## Использование адаптеров напрямую (advanced)

```python
from camera_probe.adapters.hikvision.adapter import HikvisionAdapter

adapter = HikvisionAdapter(
    ip="10.230.48.82",
    username="admin",
    password="password",
)

result = await adapter.probe_async()
```

Подходит для:

* unit / integration тестов
* vendor‑specific диагностики
* отладки ISAPI / CGI

---

## Архитектура

* `adapters/` — vendor‑specific логика
* `clients/` — HTTP / ISAPI / CGI клиенты
* `discovery/` — passive detection
* `orchestrators/` — стратегии probe
* `models/` — каноничные dataclass‑модели

Принципы:

* async‑first
* без глобального состояния
* безопасно для worker‑ов

---

## Production‑рекомендации

* Используйте `SmartProbeOrchestrator`
* Ограничивайте concurrency
* Кэшируйте `ProbeResult` (TTL 1–5 мин)
* Не вызывайте probe в request‑path API

---

## Roadmap

* ONVIF network / NTP fallback
* Batch‑scan (CIDR, inventory)
* JSON‑schema для `ProbeResult`
* Prometheus / CMDB export
* Streaming probe API

---

## Лицензия

MIT / Internal (уточняется)
