"""Inventario de datos de prueba — SOLO LECTURA (auditoría 8/10).

Uso (con MONGO_URL y DB_NAME del entorno, nunca escritos aquí):
    python scripts/test_data_inventory.py
Imprime las personas e invasiones candidatas a «de prueba». No escribe nada: para marcarlas
use la pantalla «Datos de prueba» del panel (marca reversible, queda en el historial)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from test_data import inventory
    data = await inventory()
    print(f"Personas candidatas: {data['counts']['people']} (ya marcadas: {data['counts']['people_marked']})")
    for row in data["people"]:
        print(f"  {'[marcada] ' if row['is_test'] else ''}{row['name']} · {row['person_id']} · {', '.join(row['reasons'])}")
    print(f"Invasiones candidatas: {data['counts']['campaigns']} (ya marcadas: {data['counts']['campaigns_marked']})")
    for row in data["campaigns"]:
        print(f"  {'[marcada] ' if row['is_test'] else ''}{'[archivada] ' if row['archived'] else ''}{row['name']} · {row['campaign_id']}")
    print(f"Registros de visitantes marcados como prueba: {data['visitor_registrations_marked']}")


if __name__ == "__main__":
    asyncio.run(main())
