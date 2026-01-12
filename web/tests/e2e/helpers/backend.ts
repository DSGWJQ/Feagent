import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

function parseDotenvFile(content: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

async function waitForHttpOk(url: string, timeoutMs: number): Promise<void> {
  const started = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      const res = await fetch(url, { method: 'GET' });
      if (res.status >= 200 && res.status < 500) return;
    } catch {
      // ignore
    }
    if (Date.now() - started > timeoutMs) {
      throw new Error(`Timed out waiting for ${url}`);
    }
    await new Promise((r) => setTimeout(r, 250));
  }
}

function getRepoRootFromThisFile(): string {
  // web/tests/e2e/helpers -> repo root
  const here = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(here, '..', '..', '..', '..');
}

function pickEnvFile(mode: string): string {
  switch (mode) {
    case 'fullreal':
      return '.env.fullreal';
    case 'hybrid':
      return '.env.hybrid';
    case 'deterministic':
    default:
      return '.env.test';
  }
}

export interface BackendHandle {
  pid: number;
  stop: () => Promise<void>;
}

const PID_FILE = path.resolve(process.cwd(), '.playwright-backend.pid');
const IS_MANAGED_FILE = path.resolve(process.cwd(), '.playwright-backend.managed');

export async function ensureBackendRunning(): Promise<BackendHandle | null> {
  const apiUrl = (process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  const healthUrl = `${apiUrl}/docs`;

  try {
    await waitForHttpOk(healthUrl, 1000);
    console.log(`[Backend] Already running: ${apiUrl}`);
    return null;
  } catch {
    // continue to start
  }

  const repoRoot = getRepoRootFromThisFile();
  const mode = (process.env.E2E_TEST_MODE || 'deterministic').trim();
  const envFile = path.resolve(repoRoot, pickEnvFile(mode));

  let fileEnv: Record<string, string> = {};
  if (fs.existsSync(envFile)) {
    fileEnv = parseDotenvFile(fs.readFileSync(envFile, 'utf-8'));
  } else {
    console.warn(`[Backend] Env file not found: ${envFile} (falling back to process.env)`);
  }

  const childEnv: Record<string, string> = {
    ...fileEnv,
    ...Object.fromEntries(Object.entries(process.env).filter(([, v]) => typeof v === 'string')) as Record<
      string,
      string
    >,
    PLAYWRIGHT_API_URL: apiUrl,
  };

  // Ensure seed API is enabled for deterministic E2E.
  if (!childEnv.ENABLE_TEST_SEED_API) childEnv.ENABLE_TEST_SEED_API = 'true';
  if (!childEnv.ENV) childEnv.ENV = 'test';
  if (!childEnv.E2E_TEST_MODE) childEnv.E2E_TEST_MODE = mode;

  console.log(`[Backend] Starting uvicorn (mode=${childEnv.E2E_TEST_MODE})...`);

  const proc: ChildProcessWithoutNullStreams = spawn(
    'python',
    [
      '-m',
      'uvicorn',
      'src.interfaces.api.main:app',
      '--host',
      '127.0.0.1',
      '--port',
      '8000',
    ],
    {
      cwd: repoRoot,
      env: childEnv,
      stdio: 'pipe',
    }
  );

  proc.stdout.on('data', (chunk) => process.stdout.write(`[backend] ${chunk}`));
  proc.stderr.on('data', (chunk) => process.stderr.write(`[backend] ${chunk}`));

  proc.on('exit', (code, signal) => {
    console.error(`[Backend] exited: code=${code} signal=${signal ?? ''}`);
  });

  if (!proc.pid) {
    throw new Error('Failed to start backend (no pid)');
  }

  fs.writeFileSync(PID_FILE, String(proc.pid), 'utf-8');
  fs.writeFileSync(IS_MANAGED_FILE, 'true', 'utf-8');

  await waitForHttpOk(healthUrl, 60_000);
  console.log(`[Backend] Ready: ${apiUrl} (pid=${proc.pid})`);

  return {
    pid: proc.pid,
    stop: async () => {
      try {
        proc.kill('SIGTERM');
      } catch {
        // ignore
      }
      await new Promise((r) => setTimeout(r, 500));
    },
  };
}

export async function stopManagedBackend(): Promise<void> {
  if (!fs.existsSync(IS_MANAGED_FILE) || !fs.existsSync(PID_FILE)) {
    return;
  }

  const raw = fs.readFileSync(PID_FILE, 'utf-8').trim();
  const pid = Number(raw);
  if (!Number.isFinite(pid) || pid <= 0) {
    fs.rmSync(PID_FILE, { force: true });
    fs.rmSync(IS_MANAGED_FILE, { force: true });
    return;
  }

  console.log(`[Backend] Stopping managed backend pid=${pid}...`);
  try {
    process.kill(pid, 'SIGTERM');
  } catch (err) {
    console.warn(`[Backend] Failed to SIGTERM pid=${pid}:`, err);
  }

  fs.rmSync(PID_FILE, { force: true });
  fs.rmSync(IS_MANAGED_FILE, { force: true });
}
