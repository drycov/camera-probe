from hikvision_client import HikvisionHttpClient

client = HikvisionHttpClient(
    ip="10.230.50.28",
    username="admin",
    password="Mergen_2024",
)

xml = client.get("/ISAPI/System/deviceInfo")
print(xml)

client.close()
