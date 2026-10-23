"""Seed QA para pruebas UI/E2E de Etapa 2 (Invasiones + supervisión de rama).

Crea: líder de rama (sin insignia), sub-grupo con su propio líder, mentor en la rama
raíz, mentor en sub-rama, mentor fuera de la rama. Todos con prefijo qa.outreach.etapa2.*
(los limpia qa_demo_cleanup). Escribe los datos a /tmp/etapa2_seed.json.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import server  # noqa: E402
from test_mentorship_outreach_etapa2 import (  # noqa: E402
    PASSWORD, activate_badge, add_member, create_person, create_user, make_front_group,
)


async def main():
    leader_pid = await create_person("UILiderRama")
    sub_leader_pid = await create_person("UISubLider")
    mentor_root_pid = await create_person("UIMentorRaiz")
    mentor_sub_pid = await create_person("UIMentorSub")
    mentor_out_pid = await create_person("UIMentorFuera")
    for pid in (mentor_root_pid, mentor_sub_pid, mentor_out_pid):
        await activate_badge(pid)
    users = {}
    for key, label, role, pid in (
        ("leader", "UILiderRama", "lider", leader_pid),
        ("sub_leader", "UISubLider", "lider", sub_leader_pid),
        ("mentor_root", "UIMentorRaiz", "persona", mentor_root_pid),
        ("mentor_sub", "UIMentorSub", "persona", mentor_sub_pid),
        ("mentor_out", "UIMentorFuera", "persona", mentor_out_pid),
    ):
        user_id, email = await create_user(label, role, pid)
        users[key] = (user_id, email, pid)
    root_group = await make_front_group("QA Rama Etapa2 UI", leader_pid, users["leader"][0])
    sub_group = await make_front_group("QA SubRama Etapa2 UI", sub_leader_pid, users["sub_leader"][0], parent_id=root_group)
    await add_member(root_group, mentor_root_pid, "mentor")
    await add_member(sub_group, mentor_sub_pid, "mentor")
    out = {"password": PASSWORD, "root_group": root_group, "sub_group": sub_group}
    for key, (user_id, email, pid) in users.items():
        out[key] = {"email": email, "person_id": pid, "user_id": user_id}
    with open("/tmp/etapa2_seed.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
