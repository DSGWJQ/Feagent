// Seed API 验证脚本 - M4.2 验证工具
// 使用: node tools/verify-seed-api.mjs
// 环境变量: SEED_API_BASE_URL (默认 http://localhost:8000)
//           PRESERVE_ON_FAILURE (失败时保留现场, 默认 false)

const BASE_URL = process.env.SEED_API_BASE_URL || 'http://localhost:8000';
const TIMEOUT_MS = Number(process.env.SEED_API_TIMEOUT_MS || 10000);
const PRESERVE_ON_FAILURE = process.env.PRESERVE_ON_FAILURE === 'true';

const REQUIRED_HEADER = { 'X-Test-Mode': 'true', 'Content-Type': 'application/json' };

function timeoutSignal(ms) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(new Error(`Timeout ${ms}ms`)), ms);
  return { signal: controller.signal, cancel: () => clearTimeout(id) };
}

async function http(method, path, { headers = {}, json } = {}) {
  const { signal, cancel } = timeoutSignal(TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
      signal,
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    return { status: res.status, data };
  } finally {
    cancel();
  }
}

function assert(cond, msg, ctx) {
  if (!cond) {
    const suffix = ctx ? ` | ctx=${JSON.stringify(ctx).slice(0, 800)}` : '';
    throw new Error(`${msg}${suffix}`);
  }
}

function assertSeedResponse(data, expectedType) {
  assert(typeof data?.workflow_id === 'string' && data.workflow_id.length > 0, 'workflow_id missing', data);
  assert(data.fixture_type === expectedType, 'fixture_type mismatch', data);
  assert(typeof data.cleanup_token === 'string' && data.cleanup_token.startsWith('cleanup_'), 'cleanup_token invalid', data);

  const m = data.metadata;
  assert(typeof m?.node_count === 'number', 'metadata.node_count missing', data);
  assert(typeof m?.edge_count === 'number', 'metadata.edge_count missing', data);
  assert(typeof m?.has_isolated_nodes === 'boolean', 'metadata.has_isolated_nodes missing', data);
  assert(Array.isArray(m?.side_effect_nodes), 'metadata.side_effect_nodes missing', data);
}

async function seedOne(fixture_type) {
  const resp = await http('POST', '/api/test/workflows/seed', {
    headers: REQUIRED_HEADER,
    json: { fixture_type, project_id: 'e2e_test_project', custom_metadata: { seed_verify: true, ts: new Date().toISOString() } },
  });
  assert(resp.status === 201, 'seed expected 201', resp);
  assertSeedResponse(resp.data, fixture_type);
  return resp.data;
}

async function cleanup(tokens) {
  if (tokens.length === 0) return { deleted_count: 0, failed: [] };
  const resp = await http('DELETE', '/api/test/workflows/cleanup', {
    headers: REQUIRED_HEADER,
    json: { cleanup_tokens: tokens },
  });
  assert(resp.status === 200, 'cleanup expected 200', resp);
  assert(typeof resp.data?.deleted_count === 'number', 'deleted_count missing', resp);
  assert(Array.isArray(resp.data?.failed), 'failed list missing', resp);
  return resp.data;
}

async function main() {
  const cleanupTokens = [];
  let ok = false;

  try {
    console.log('[Start] Seed API verification...');

    // Preflight: API enabled + fixture types
    console.log('[Check] Verifying Seed API is enabled...');
    const types = await http('GET', '/api/test/workflows/fixture-types', { headers: REQUIRED_HEADER });
    assert(types.status === 200, 'fixture-types expected 200 (Seed API disabled?)', types);
    const fixture_types = types.data?.fixture_types;
    assert(Array.isArray(fixture_types), 'fixture_types missing', types);

    const MUST = ['main_subgraph_only', 'with_isolated_nodes', 'side_effect_workflow', 'invalid_config'];
    MUST.forEach((t) => assert(fixture_types.includes(t), `fixture_types missing ${t}`, types.data));
    console.log('[Pass] ✅ Fixture types verified:', MUST.join(', '));

    // 4 fixtures happy path
    console.log('[Test] Testing 4 fixtures...');
    for (const t of MUST) {
      const seeded = await seedOne(t);
      cleanupTokens.push(seeded.cleanup_token);

      if (t === 'main_subgraph_only') {
        assert(seeded.metadata.node_count === 3, 'main_subgraph_only node_count != 3', seeded);
        assert(seeded.metadata.edge_count === 2, 'main_subgraph_only edge_count != 2', seeded);
        assert(seeded.metadata.has_isolated_nodes === false, 'main_subgraph_only has_isolated_nodes != false', seeded);
      }
      if (t === 'with_isolated_nodes') {
        assert(seeded.metadata.has_isolated_nodes === true, 'with_isolated_nodes has_isolated_nodes != true', seeded);
      }
      if (t === 'side_effect_workflow') {
        assert(seeded.metadata.side_effect_nodes.length > 0, 'side_effect_nodes empty', seeded);
      }
      console.log(`[Pass] ✅ ${t}: workflow_id=${seeded.workflow_id}`);
    }

    // Negative: invalid type => 400
    console.log('[Test] Testing error handling...');
    const bad = await http('POST', '/api/test/workflows/seed', {
      headers: REQUIRED_HEADER,
      json: { fixture_type: 'nonexistent_fixture' },
    });
    assert(bad.status === 400, 'invalid fixture expected 400', bad);
    assert(bad.data?.detail?.code === 'INVALID_FIXTURE_TYPE', 'invalid fixture code mismatch', bad);
    console.log('[Pass] ✅ Invalid fixture type returns 400');

    // Negative: missing header => 403
    const missingHeader = await http('POST', '/api/test/workflows/seed', {
      headers: { 'Content-Type': 'application/json' },
      json: { fixture_type: 'main_subgraph_only' },
    });
    assert(missingHeader.status === 403, 'missing header expected 403', missingHeader);
    assert(missingHeader.data?.detail?.code === 'TEST_MODE_REQUIRED', 'missing header code mismatch', missingHeader);
    console.log('[Pass] ✅ Missing X-Test-Mode header returns 403');

    // Concurrency: N parallel seeds
    console.log('[Test] Testing concurrency (10 parallel seeds)...');
    const N = 10;
    const batchTypes = Array.from({ length: N }, (_, i) => MUST[i % MUST.length]);
    const seededAll = await Promise.all(batchTypes.map(seedOne));
    seededAll.forEach((x) => cleanupTokens.push(x.cleanup_token));

    const ids = new Set(seededAll.map((x) => x.workflow_id));
    assert(ids.size === seededAll.length, 'workflow_id not unique under concurrency', seededAll);
    console.log(`[Pass] ✅ Concurrency test: ${seededAll.length} unique workflows created`);

    ok = true;
  } finally {
    const tokens = [...new Set(cleanupTokens)];
    if (!ok && PRESERVE_ON_FAILURE) {
      console.log(`[Preserve] ⚠️  PRESERVE_ON_FAILURE=true, skip cleanup. tokens=${tokens.length}`);
      console.log('[Note] Run cleanup manually or restart with PRESERVE_ON_FAILURE=false');
      return;
    }

    if (tokens.length > 0) {
      console.log(`[Cleanup] Cleaning up ${tokens.length} workflows...`);
      const result = await cleanup(tokens);
      assert(result.failed.length === 0, 'cleanup failed list not empty', result);
      console.log(`[Pass] ✅ Cleanup successful: deleted_count=${result.deleted_count}`);
    }
  }
}

main().then(
  () => {
    console.log('\n[OK] ✅ Seed API verification passed');
    process.exit(0);
  },
  (e) => {
    console.error('\n[FAIL] ❌ Verification failed:', e?.stack || e);
    process.exit(1);
  },
);
