"""Run: python -m unittest -v test_api.py (from backend). Uses isolated SQLite."""
import os, tempfile, unittest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
_temp=tempfile.TemporaryDirectory()
os.environ.update(APP_ENV='development',MONGODB_URI='',SQLITE_PATH=_temp.name+'/test.db',JWT_SECRET='test-only-secret-at-least-32-characters')
from main import app, store
client=TestClient(app)

def account(role,email,area='Electronic City',diet='Any',need=0):
    response=client.post('/api/register',json=dict(name=email.split('@')[0]+' organization',email=email,password='DemoPass!123',role=role,area=area,diet=diet,need=need))
    assert response.status_code==201,response.text
    data=response.json()
    return {'Authorization':'Bearer '+data['token']},data['user']

class FoodBridgeTests(unittest.TestCase):
    def test_complete_workflow(self):
        donor,du=account('donor','donor@example.test')
        ngo,nu=account('ngo','ngo@example.test',diet='Vegetarian',need=50)
        vegan,vu=account('ngo','vegan@example.test',diet='Vegan',need=100)
        other,ou=account('donor','other@example.test')
        remote,ru=account('ngo','remote@example.test',area='BTM Layout',need=60)
        self.assertEqual(client.get('/health').json()['storage'],'sqlite')
        self.assertEqual(client.get('/api/donations').status_code,401)
        self.assertEqual(client.post('/api/login',json={'email':'donor@example.test','password':'wrong'}).status_code,401)
        self.assertEqual(client.post('/api/login',json={'email':'DONOR@example.test','password':'DemoPass!123'}).status_code,200)
        self.assertEqual(client.post('/api/register',json=dict(name='duplicate',email='donor@example.test',password='DemoPass!123',role='donor',area='Electronic City')).status_code,409)
        body=dict(title='Vegetable rice',qty=25,diet='Vegetarian',deadline=(datetime.now(timezone.utc)+timedelta(hours=3)).isoformat(),note='Test only')
        self.assertEqual(client.post('/api/donations',headers=ngo,json=body).status_code,403)
        self.assertEqual(client.post('/api/donations',headers=donor,json={**body,'qty':0}).status_code,422)
        self.assertEqual(client.post('/api/donations',headers=donor,json={**body,'deadline':'2020-01-01T12:00:00Z'}).status_code,422)
        r=client.post('/api/donations',headers=donor,json=body); self.assertEqual(r.status_code,201,r.text)
        id=r.json()['id']; base='/api/donations/'+id
        self.assertEqual(client.get('/api/donations',headers=other).json(),[])
        self.assertEqual(len(client.get('/api/donations',headers=ngo).json()),1)
        matches=client.get(base+'/matches',headers=donor).json()
        self.assertEqual([n['id'] for n in matches],[nu['id'],ru['id']])
        self.assertEqual(client.get(base+'/matches',headers=vegan).json(),[])
        self.assertEqual(client.post(base+'/reserve',headers=other,json={'ngo_id':nu['id']}).status_code,403)
        self.assertEqual(client.post(base+'/reserve',headers=ngo,json={'ngo_id':ru['id']}).status_code,403)
        self.assertEqual(client.post(base+'/reserve',headers=vegan,json={'ngo_id':vu['id']}).status_code,409)
        self.assertEqual(client.post(base+'/reserve',headers=ngo,json={'ngo_id':nu['id']}).json()['status'],'Reserved')
        self.assertEqual(client.post(base+'/reserve',headers=donor,json={'ngo_id':nu['id']}).status_code,409)
        self.assertEqual(client.patch(base+'/status',headers=ngo,json={'status':'Delivered'}).status_code,409)
        self.assertEqual(client.patch(base+'/status',headers=other,json={'status':'Collected'}).status_code,403)
        self.assertEqual(client.patch(base+'/status',headers=donor,json={'status':'Available'}).json()['status'],'Available')
        self.assertEqual(client.post(base+'/reserve',headers=donor,json={'ngo_id':nu['id']}).status_code,200)
        self.assertEqual(client.patch(base+'/status',headers=donor,json={'status':'Collected'}).json()['status'],'Collected')
        self.assertEqual(client.patch(base+'/status',headers=donor,json={'status':'Delivered'}).status_code,403)
        self.assertEqual(client.patch(base+'/status',headers=ngo,json={'status':'Delivered'}).json()['status'],'Delivered')
        self.assertEqual(client.get('/api/analytics',headers=donor).json()['meals_delivered'],25)
        self.assertEqual(client.get('/api/analytics',headers=ngo).json()['meals_delivered'],25)
        self.assertNotIn('password_hash',str(client.get('/api/ngos',headers=donor).json()))
        self.assertNotIn('email',client.get('/api/me',headers=ngo).json())
        self.assertEqual(client.patch('/api/me',headers=ngo,json={'need':90,'diet':'Any'}).json()['need'],90)
        self.assertEqual(client.patch('/api/me',headers=donor,json={'need':90,'diet':'Any'}).status_code,403)
        # Expired listings disappear from the NGO marketplace, but remain visible to the donor.
        rid=client.post('/api/donations',headers=donor,json=body).json()['id']
        store.update('donations',rid,{}, {'deadline':'2020-01-01T12:00:00+00:00'})
        self.assertEqual(next(x for x in client.get('/api/donations',headers=donor).json() if x['id']==rid)['status'],'Expired')
        self.assertNotIn(rid,[x['id'] for x in client.get('/api/donations',headers=ngo).json()])
        self.assertEqual(client.post('/api/donations/'+rid+'/reserve',headers=donor,json={'ngo_id':nu['id']}).status_code,409)
    def test_cors(self):
        r=client.options('/api/login',headers={'Origin':'http://127.0.0.1:5500','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['access-control-allow-origin'],'http://127.0.0.1:5500')
        r=client.options('/api/login',headers={'Origin':'https://untrusted.example','Access-Control-Request-Method':'POST'})
        self.assertEqual(r.status_code,400)

if __name__=='__main__': unittest.main()
