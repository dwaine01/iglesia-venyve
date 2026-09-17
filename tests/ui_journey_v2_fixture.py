"""Fixture efímero para validación visual de Consolidación v2; siempre ejecutar cleanup."""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from access_control import access_defaults_for_role  # noqa: E402
from qa_demo_cleanup import delete_qa_artifacts  # noqa: E402
import server  # noqa: E402


load_dotenv('/app/backend/.env', override=False)
load_dotenv('/app/frontend/.env', override=False)
DB = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
API = os.environ['REACT_APP_BACKEND_URL']
PASSWORD = 'JourneyUI2026!'


def person(label):
    person_id = ObjectId(); now = datetime.now(timezone.utc)
    DB.persons.insert_one({'_id': person_id, 'person_number': f"VV-QA{uuid.uuid4().hex[:7].upper()}", 'nombre': 'QA', 'apellido': label, 'idempotency_key': f'qa:ui:{uuid.uuid4()}', 'version': 1, 'created_at': now, 'updated_at': now})
    return str(person_id)


def user(label, role, person_id=None):
    user_id = ObjectId(); email = f"qa.journey.ui.{uuid.uuid4().hex[:7]}@example.com"; defaults = access_defaults_for_role(role)
    document = {'_id': user_id, 'nombre': f'QA {label}', 'email': email, 'password': bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), 'rol': role, 'is_active': True, 'token_version': 1, 'created_at': datetime.now(timezone.utc), **defaults}
    if person_id: document['person_id'] = person_id
    DB.users.insert_one(document); return email


def request(method, path, token, payload=None):
    response = requests.request(method, f'{API}{path}', headers={'Authorization': f'Bearer {token}'}, json=payload, timeout=30)
    response.raise_for_status(); return response.json()


def complete_stage(token, enrollment_id, stage_key):
    detail = request('GET', f'/api/processes/consolidation/{enrollment_id}', token)
    stage = next(item for item in detail['stages'] if item['stage_key'] == stage_key)
    for task in stage['tasks']:
        if not task['completed']:
            request('PUT', f"/api/processes/enrollments/{enrollment_id}/stages/{stage_key}/tasks/{task['task_id']}", token, {'completed': True})
    request('PUT', f'/api/processes/enrollments/{enrollment_id}/stages/{stage_key}', token, {'status': 'completed'})


def setup():
    asyncio.run(delete_qa_artifacts(server.db))
    pastor_email = user('Journey UI Pastor', 'pastor')
    mentor_id = person('Mentor UI'); user('Mentor UI', 'lider', mentor_id)
    candidate_id = person('Recorrido UI')
    visitor_id = person('Visitante Pendiente UI')
    login = requests.post(f'{API}/api/auth/login', json={'email': pastor_email, 'password': PASSWORD}, timeout=30); login.raise_for_status(); token = login.json()['token']
    group = request('POST', '/api/front-groups', token, {'name': 'QA Grupo Frontal Esperanza', 'description': 'Fixture visual efímero', 'linked_structures': []})
    request('POST', f"/api/front-groups/{group['front_group_id']}/members", token, {'person_id': mentor_id, 'role': 'mentor', 'notes': 'Mentor visual'})
    request('PUT', f'/api/front-groups/mentors/{mentor_id}/qualification', token, {'front_group_id': group['front_group_id'], 'can_teach_lbs': True})
    journey = request('POST', '/api/processes/consolidation/intakes', token, {'person_id': candidate_id, 'entry_mode': 'direct_church', 'front_group_id': group['front_group_id'], 'mentor_person_id': mentor_id})
    complete_stage(token, journey['enrollment_id'], 'mcd'); complete_stage(token, journey['enrollment_id'], 'npt')
    request('POST', f"/api/processes/consolidation/{journey['enrollment_id']}/mentor/evaluate", token, {})
    request('POST', '/api/processes/consolidation/intakes', token, {'person_id': visitor_id, 'entry_mode': 'visitor_followup', 'front_group_id': group['front_group_id'], 'next_followup_at': datetime.now(timezone.utc).isoformat(), 'initial_result': 'Pendiente de respuesta'})
    print(json.dumps({'email': pastor_email, 'password': PASSWORD, 'enrollment_id': journey['enrollment_id'], 'candidate_person_id': candidate_id, 'front_group_id': group['front_group_id']}))


def cleanup():
    result = asyncio.run(delete_qa_artifacts(server.db))
    print(json.dumps({'cleanup': result, 'remaining_people': DB.persons.count_documents({'nombre': 'QA'}), 'remaining_users': DB.users.count_documents({'email': {'$regex': '^qa\\.'}})}))


if __name__ == '__main__':
    setup() if len(sys.argv) > 1 and sys.argv[1] == 'setup' else cleanup()