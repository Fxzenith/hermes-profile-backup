// Latitude SDK self-check: init -> capture boundary -> memory spans -> flush.
// Prints explicit PASS/FAIL and exits non-zero on failure so trace
// verification can be scripted without dashboard / CLI / REST access.
//
// Run from the app root so Bun auto-loads .env:
//   bun run latitude-selfcheck.ts
// Needs LATITUDE_API_KEY + LATITUDE_PROJECT_SLUG in env or .env.
//
// Why this is valid verification: latitude.flush() awaits the OTLP HTTP
// export to https://ingest.latitude.so — resolving without error means the
// spans reached the ingest endpoint (bad key / network failure rejects).
// Latitude has NO public REST read endpoint (GET /v1/traces 404s), so this
// is the cheapest deterministic proof spans can land.
import { capture, createMemoryTelemetry, Latitude } from '@latitude-data/telemetry';

const apiKey = process.env.LATITUDE_API_KEY;
const project = process.env.LATITUDE_PROJECT_SLUG;
if (!apiKey || !project) {
  console.error('FAIL: LATITUDE_API_KEY and LATITUDE_PROJECT_SLUG must be set (env or .env)');
  process.exit(1);
}

const lat = new Latitude({ apiKey, project, serviceName: 'gbrain-selfcheck' });
await lat.ready;
console.log('PASS: lat.ready resolved (SDK initialized)');

const memory = createMemoryTelemetry({ latitude: lat, storeId: 'selfcheck', captureContent: true });
await capture('selfcheck-boundary', async () => {
  await memory.search({
    query: 'selfcheck query',
    execute: async () => [],
    recordsFromResult: () => [],
  });
  await memory.upsert({
    recordId: 'selfcheck/record-1',
    records: [{ id: 'selfcheck/record-1', content: 'selfcheck content' }],
    execute: async () => {},
  });
  await new Promise((r) => setTimeout(r, 50));
  return 'done';
}, { name: 'selfcheck', tags: ['selfcheck'] });

await lat.flush();
console.log('PASS: flush resolved — spans exported to ingest endpoint without error');
process.exit(0);
