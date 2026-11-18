import os, secrets, hashlib, hmac, re
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Literal
from pathlib import Path
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from store import SQLiteStore, MongoStore

load_dotenv(Path(__file__).with_name('.env'))
MODE=os.getenv('APP_ENV','development')
URI=os.getenv('MONGODB_URI','').strip()
SECRET=os.getenv('JWT_SECRET','')
if MODE=='production' and (not URI or len(SECRET)<32 or SECRET.startswith('replace_with_')):
    raise RuntimeError('Production requires MONGODB_URI and a JWT_SECRET of at least 32 characters.')
SECRET=SECRET or secrets.token_urlsafe(48)
store=MongoStore(URI,os.getenv('MONGODB_DATABASE','foodbridge')) if URI else SQLiteStore(os.getenv('SQLITE_PATH',str(Path(__file__).with_name('foodbridge.db'))))
app=FastAPI(title='FoodBridge API',version='1.0.0')
origins=[x.strip().rstrip('/') for x in os.getenv('CORS_ORIGINS','http://localhost:5500,http://127.0.0.1:5500').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['GET','POST','PATCH','OPTIONS'],allow_headers=['Authorization','Content-Type'])
bearer=HTTPBearer(auto_error=False)
Diet=Literal['Vegetarian','Vegan','Non-vegetarian','Any']
FoodDiet=Literal['Vegetarian','Vegan','Non-vegetarian']
AREAS=['Electronic City','BTM Layout','Koramangala','HSR Layout','Jayanagar','Other']

def now(): return datetime.now(timezone.utc)
def iso(): return now().isoformat()
def fail(code,message): raise HTTPException(code,message)
def password_hash(password):
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
    return salt+':'+digest

def verify(password, value):
    salt,digest=value.split(':')
    got=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
    return hmac.compare_digest(got,digest)

def public(u): return {k:u[k] for k in ['id','name','role','area','need','diet']}
def token(u): return jwt.encode({'sub':u['id'],'exp':now()+timedelta(hours=8),'iat':now(),'iss':'foodbridge'},SECRET,algorithm='HS256')
def current(auth:HTTPAuthorizationCredentials|None=Depends(bearer)):
    if not auth: fail(401,'Sign in first.')
    try: uid=jwt.decode(auth.credentials,SECRET,algorithms=['HS256'],issuer='foodbridge',options={'require':['exp','sub']})['sub']
    except jwt.InvalidTokenError: fail(401,'Session expired or invalid. Sign in again.')
    u=store.get('users',uid)
    if not u: fail(401,'Account not found.')
    return u

class Register(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    email:str=Field(min_length=5,max_length=254)
    password:str=Field(min_length=8,max_length=128)
    role:Literal['donor','ngo']
    area:str
    need:int=Field(default=0,ge=0,le=100000)
    diet:Diet='Any'
    @field_validator('email')
    @classmethod
    def check_email(cls,v):
        v=v.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v): raise ValueError('Enter a valid email.')
        return v
    @field_validator('name')
    @classmethod
    def check_name(cls,v):
        if len(v.strip())<2: raise ValueError('Enter an organization name.')
        return v.strip()
    @field_validator('area')
    @classmethod
    def check_area(cls,v):
        if v not in AREAS: raise ValueError('Select a supported locality.')
        return v
class Login(BaseModel):
    email:str=Field(max_length=254)
    password:str=Field(max_length=128)
class Donation(BaseModel):
    title:str=Field(min_length=2,max_length=100)
    qty:int=Field(gt=0,le=100000)
    diet:FoodDiet
    deadline:datetime
    note:str=Field(default='',max_length=500)
    @field_validator('deadline')
    @classmethod
    def check_deadline(cls,v):
        if v.tzinfo is None: raise ValueError('Deadline must include a timezone.')
        if v<=now(): raise ValueError('Deadline must be in the future.')
        if v>now()+timedelta(days=7): raise ValueError('Deadline must be within seven days.')
        return v.astimezone(timezone.utc)
    @field_validator('title')
    @classmethod
    def check_title(cls,v):
        if len(v.strip())<2: raise ValueError('Enter a food name.')
        return v.strip()
class Reserve(BaseModel):
    ngo_id:str=Field(max_length=100)
class Update(BaseModel):
    status:Literal['Available','Collected','Delivered']
class Profile(BaseModel):
    need:int=Field(ge=0,le=100000)
    diet:Diet

@app.get('/health')
def health():
    try: store.ping()
    except Exception: fail(503,'Database unavailable.')
    return {'status':'ok','storage':'mongodb' if URI else 'sqlite'}
@app.post('/api/register',status_code=201)
def register(body:Register):
    # Deterministic ID prevents duplicate registration atomically, without exposing email.
    uid=hashlib.sha256(body.email.encode()).hexdigest()
    u={**body.model_dump(exclude={'password'}),'id':uid,'password_hash':password_hash(body.password),'created_at':iso()}
    if u['role']=='donor': u.update(need=0,diet='Any')
    if not store.insert('users',u): fail(409,'Email already registered.')
    return {'token':token(u),'user':public(u)}
@app.post('/api/login')
def login(body:Login):
    uid=hashlib.sha256(body.email.strip().lower().encode()).hexdigest()
    u=store.get('users',uid)
    # Perform a comparable hash for unknown accounts, too.
    dummy='00'*16+':'+'00'*32
    valid=verify(body.password,u['password_hash'] if u else dummy)
    if not u or not valid: fail(401,'Invalid email or password.')
    return {'token':token(u),'user':public(u)}
@app.get('/api/me')
def me(u=Depends(current)): return public(u)
@app.patch('/api/me')
def profile(body:Profile,u=Depends(current)):
    if u['role']!='ngo': fail(403,'Only NGOs can edit meal requirements.')
    return public(store.update('users',u['id'],{},body.model_dump()))

def expired(d): return datetime.fromisoformat(d['deadline'])<=now()
def display(d):
    out=dict(d)
    if out['status']=='Available' and expired(out): out['status']='Expired'
    return out

def owns(d,u): return d['donor_id']==u['id'] or d.get('ngo_id')==u['id']
def visible(d,u): return owns(d,u) or (u['role']=='ngo' and d['status']=='Available' and not expired(d))
def get_donation(id):
    d=store.get('donations',id)
    if not d: fail(404,'Donation not found.')
    return d

def compatible(food, diet): return diet=='Any' or food==diet or (food=='Vegan' and diet=='Vegetarian')
def score(d,n,ds):
    if not compatible(d['diet'],n['diet']): return None
    committed=sum(x['qty'] for x in ds if x.get('ngo_id')==n['id'] and x['status'] in ('Reserved','Collected'))
    remaining=max(0,n['need']-committed)
    if remaining<d['qty']: return None
    local=d['area']==n['area'] and d['area']!='Other'
    fit=round(40*d['qty']/max(remaining,1))
    return {**public(n),'remaining':remaining,'score':30+(30 if local else 0)+fit,'same_area':local,'reason':f'{"Same locality" if local else "Different locality"}; dietary match; {remaining} meals remaining'}
@app.get('/api/ngos')
def ngos(u=Depends(current)):
    return [public(n) for n in store.all('users') if n['role']=='ngo']
@app.get('/api/donations')
def donations(u=Depends(current)):
    return sorted([display(d) for d in store.all('donations') if visible(d,u)],key=lambda d:d['created_at'],reverse=True)
@app.post('/api/donations',status_code=201)
def create(body:Donation,u=Depends(current)):
    if u['role']!='donor': fail(403,'Only donors can post food.')
    d={**body.model_dump(mode='json'),'deadline':body.deadline.isoformat(),'id':str(uuid4()),'donor_id':u['id'],'donor':u['name'],'area':u['area'],'status':'Available','revision':0,'ngo_id':None,'ngo':None,'created_at':iso(),'history':[{'status':'Available','at':iso()}]}
    store.insert('donations',d)
    return d
@app.get('/api/donations/{id}/matches')
def matches(id:str,u=Depends(current)):
    d=get_donation(id)
    if not visible(d,u): fail(404,'Donation not found.')
    if d['status']!='Available' or expired(d): fail(409,'Donation is not available.')
    ds=store.all('donations')
    ns=[n for n in store.all('users') if n['role']=='ngo' and (u['role']=='donor' or n['id']==u['id'])]
    return sorted([m for n in ns if (m:=score(d,n,ds))],key=lambda n:-n['score'])
@app.post('/api/donations/{id}/reserve')
def reserve(id:str,body:Reserve,u=Depends(current)):
    d=get_donation(id)
    if u['role']=='donor' and d['donor_id']!=u['id']: fail(403,'Not your donation.')
    if u['role']=='ngo' and u['id']!=body.ngo_id: fail(403,'Reserve only for your NGO.')
    if d['status']!='Available' or expired(d): fail(409,'Donation is not available.')
    n=store.get('users',body.ngo_id)
    if not n or n['role']!='ngo': fail(404,'NGO not found.')
    if not score(d,n,store.all('donations')): fail(409,'Diet or remaining demand does not match.')
    updated=store.update('donations',id,{'status':'Available','revision':d['revision']},{'status':'Reserved','revision':d['revision']+1,'ngo_id':n['id'],'ngo':n['name'],'history':d['history']+[{'status':'Reserved','at':iso()}]})
    if not updated: fail(409,'Another user already updated this donation.')
    return updated
@app.patch('/api/donations/{id}/status')
def update_status(id:str,body:Update,u=Depends(current)):
    d=get_donation(id)
    if not owns(d,u): fail(403,'You cannot update this donation.')
    target=body.status
    allowed={'Reserved':{'Available','Collected'},'Collected':{'Delivered'}}
    if target not in allowed.get(d['status'],set()): fail(409,'Invalid status transition.')
    if target=='Collected' and expired(d): fail(409,'Collection deadline passed. Release the reservation instead.')
    if target=='Delivered' and u['role']!='ngo': fail(403,'Only the assigned NGO can confirm delivery.')
    changes={'status':target,'revision':d['revision']+1,'history':d['history']+[{'status':target,'at':iso()}]}
    if target=='Available': changes.update(ngo_id=None,ngo=None)
    updated=store.update('donations',id,{'status':d['status'],'ngo_id':d['ngo_id'],'revision':d['revision']},changes)
    if not updated: fail(409,'Donation changed. Refresh and try again.')
    return display(updated)
@app.get('/api/analytics')
def analytics(u=Depends(current)):
    ds=[display(d) for d in store.all('donations') if owns(d,u)]
    counts={s:sum(d['status']==s for d in ds) for s in ['Available','Reserved','Collected','Delivered','Expired']}
    return {'total':len(ds),'counts':counts,'meals_delivered':sum(d['qty'] for d in ds if d['status']=='Delivered'),'meals_listed':sum(d['qty'] for d in ds),'ngos':sum(n['role']=='ngo' for n in store.all('users'))}
