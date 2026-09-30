from sqlalchemy import text


def test_selected_doctor_search_and_booking(client, database, headers):
    factory, start = database
    from datetime import timedelta
    # Enough existing combinations to exceed the legacy helper limit.
    with factory() as db:
        db.execute(text("INSERT INTO users(full_name,email,password_hash,role) VALUES ('Doctor Two','doctor2@example.com','unused','doctor')"))
        doctor = db.execute(text("INSERT INTO staff(user_id,department_id,profession) SELECT user_id,1,'doctor' FROM users WHERE email='doctor2@example.com' RETURNING staff_id")).scalar_one()
        db.execute(text("INSERT INTO shifts(staff_id,department_id,start_at,end_at) VALUES (:doctor,1,:start,:end)"), {'doctor':doctor, 'start':start, 'end':start+timedelta(hours=8)})
        for n in range(12):
            db.execute(text("INSERT INTO rooms(department_id,room_name,room_type) VALUES (1,:name,'Consultation')"), {'name':f'Extra {n}'})
        db.commit()
    params = {'service_id':1,'doctor_id':doctor,'from_time':start.isoformat(),'to_time':(start+timedelta(hours=1)).isoformat()}
    slots = client.get('/appointments/availability', headers=headers(), params=params)
    assert slots.status_code == 200, slots.text
    assert slots.json() and all(row['doctor_id'] == doctor for row in slots.json())
    payload = {'patient_id':1,'service_id':1,'doctor_id':doctor,'start_at':start.isoformat()}
    booking = client.post('/appointments/', headers=headers(), json=payload)
    assert booking.status_code == 201, booking.text
    assert {'staff_id':doctor} in booking.json()['assigned_staff']
    assert client.post('/appointments/', headers=headers(), json=payload).status_code == 409
    assert client.get('/appointments/availability', headers=headers(), params={**params,'doctor_id':2}).status_code == 404
