import {defineConfig} from '@playwright/test';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
// A fresh SQLite file per run, so browser tests never touch a developer's fraud.db (only used when the config starts the backend).
const database=`sqlite:///${join(tmpdir(),`finshield-e2e-${Date.now()}.db`).replaceAll('\\','/')}`;
export default defineConfig({testDir:'./tests/browser',workers:1,use:{baseURL:'http://127.0.0.1:5173',channel:'msedge',headless:true,viewport:{width:1440,height:1000}},webServer:[{command:'python -m uvicorn app.main:app --app-dir ../backend --port 8000',url:'http://127.0.0.1:8000/api/health',reuseExistingServer:true,env:{DATABASE_URL:database}},{command:'npm.cmd run dev',url:'http://127.0.0.1:5173',reuseExistingServer:true}]});
