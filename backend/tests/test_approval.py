def test_review_permissions_transitions_and_release(client, database, headers):
    _, start = database
    payload = {'patient_id':1,'service_id':1,'start_at':start.isoformat()}
    result = client.post('/appointments/', headers=headers(), json=payload)
    assert result.status_code == 201, result.text
    assert result.json()['status'] == 'requested'
    appointment_id = result.json()['appointment_id']
    path = f'/appointments/{appointment_id}'
    assert client.post(path+'/approve', headers=headers()).status_code == 403
    assert client.post(path+'/approve', headers=headers(2,'nurse')).status_code == 403
    assert client.post(path+'/approve', headers=headers(6,'doctor')).status_code == 403
    accepted = client.post(path+'/approve', headers=headers(1,'doctor'))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['status'] == 'confirmed'
    assert client.post(path+'/reject', headers=headers(4,'receptionist')).status_code == 409
    client.post(path+'/cancel', headers=headers())
    second = client.post('/appointments/', headers=headers(), json=payload).json()
    rejected = client.post(f"/appointments/{second['appointment_id']}/reject", headers=headers(4,'receptionist'))
    assert rejected.status_code == 200
    assert rejected.json()['status'] == 'cancelled'
    assert client.post('/appointments/', headers=headers(), json=payload).status_code == 201
