"""Idempotent startup for the local disposable preview only."""
import os,sys,subprocess
from sqlalchemy import create_engine,text
sys.path.insert(0,'/qa')
from serve import bootstrap
url=os.environ['QA_ADMIN_DATABASE_URL']
if url.rsplit('/',1)[-1]!='ragmatch_quality': raise RuntimeError('Banco da prévia inválido')
with create_engine(url).connect() as db:
 initialized=db.execute(text("SELECT to_regclass('public.users') IS NOT NULL")).scalar()
if not initialized:bootstrap()
else:
 env={**os.environ,'DATABASE_URL':url}
 subprocess.run([sys.executable,'scripts/migrate_database.py'],env=env,check=True)
 subprocess.run([sys.executable,'scripts/provision_app_role.py'],env=env,check=True)
os.execv(sys.executable,[sys.executable,'-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000'])
