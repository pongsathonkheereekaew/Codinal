#!/usr/bin/env node
import { execFile } from 'node:child_process';
import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

interface BenchCase {
  id: string;
  repo: string;
  setup: string;
  prompt: string;
  expect: string;
  budget_ms: number;
}

interface BenchReport {
  agent: string;
  cases: Array<{
    id: string;
    wall_ms: number;
    input_tokens?: number | null;
    output_tokens?: number | null;
    cache_read_tokens?: number | null;
    cache_write_tokens?: number | null;
    cacheReadShare?: number | null;
    pass: boolean;
    error?: string;
  }>;
}

function arg(name: string): string {
  const index = process.argv.indexOf(`--${name}`);
  if (index === -1 || !process.argv[index + 1]) {
    throw new Error(`missing --${name}`);
  }
  return process.argv[index + 1];
}

async function runCedia(workspace: string, prompt: string, root: string): Promise<{ pass: boolean; usage: Record<string, unknown>; error?: string }> {
  const cli = path.join(process.env.CEDIA_IDE_HOME ?? path.join(os.homedir(), 'cedia-ide'), 'extensions', 'cedia-agent', 'out', 'cli.js');
  const usageFile = path.join(workspace, 'usage.json');
  try {
    await execFileAsync(process.execPath, [cli, '--workspace', workspace, '--harness-home', root, '--model', 'opencode-go/deepseek-v4-flash', '--output-format', 'json', '--usage-file', usageFile, '--task', prompt], {
      cwd: workspace,
      env: { ...process.env, CEDIA_AUTO_APPROVE: '1' },
      timeout: 120_000,
      maxBuffer: 16 * 1024 * 1024,
    });
    const usage = JSON.parse(await fs.readFile(usageFile, 'utf8')) as Record<string, unknown>;
    return { pass: true, usage };
  } catch (error) {
    return { pass: false, usage: {}, error: error instanceof Error ? error.message : String(error) };
  }
}

async function runOpenCode(workspace: string, prompt: string): Promise<{ pass: boolean; usage: Record<string, unknown>; error?: string }> {
  try {
    await execFileAsync('opencode', ['run', prompt], { cwd: workspace, timeout: 120_000, maxBuffer: 16 * 1024 * 1024 });
    return { pass: true, usage: {} };
  } catch (error) {
    return { pass: false, usage: {}, error: error instanceof Error ? error.message : String(error) };
  }
}

async function main(): Promise<void> {
  const agent = arg('agent');
  const casesPath = path.resolve(arg('cases'));
  const outPath = path.resolve(arg('out'));
  const root = path.resolve(path.join(import.meta.dirname, '..', '..'));
  const cases = (JSON.parse(await fs.readFile(casesPath, 'utf8')) as { cases: BenchCase[] }).cases;
  const report: BenchReport = { agent, cases: [] };

  for (const entry of cases) {
    const workspace = await fs.mkdtemp(path.join(os.tmpdir(), `bench-${entry.id}-`));
    try {
      const fixture = path.join(root, 'harness', 'eval', entry.repo);
      await fs.cp(fixture, workspace, { recursive: true });
      if (entry.setup && entry.setup !== 'true') {
        await execFileAsync('bash', ['-lc', entry.setup], { cwd: workspace, timeout: 120_000, maxBuffer: 16 * 1024 * 1024 }).catch(() => undefined);
      }
      const started = Date.now();
      const run = agent === 'opencode' ? await runOpenCode(workspace, entry.prompt) : await runCedia(workspace, entry.prompt, root);
      const wallMs = Date.now() - started;
      const usage = run.usage as { inputTokens?: number; outputTokens?: number; cacheReadInputTokens?: number; cacheWriteInputTokens?: number };
      const cacheRead = usage.cacheReadInputTokens ?? null;
      const input = usage.inputTokens ?? null;
      report.cases.push({
        id: entry.id,
        wall_ms: wallMs,
        input_tokens: input,
        output_tokens: usage.outputTokens ?? null,
        cache_read_tokens: cacheRead,
        cache_write_tokens: usage.cacheWriteInputTokens ?? null,
        cacheReadShare: cacheRead !== null && input ? cacheRead / (cacheRead + input) : null,
        pass: run.pass,
        error: run.error,
      });
    } catch (error) {
      report.cases.push({ id: entry.id, wall_ms: 0, pass: false, error: error instanceof Error ? error.message : String(error) });
    } finally {
      await fs.rm(workspace, { recursive: true, force: true });
    }
  }
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, JSON.stringify(report, null, 2) + '\n', 'utf8');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
