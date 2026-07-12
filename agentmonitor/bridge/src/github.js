// GitHub PR CI — verify truth ที่สอง (poller ใช้ downgrade เมื่อ Hermes รายงานเขียวแต่ CI แดง)

export function parsePrUrl(url) {
  const m = String(url || '').match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/i);
  if (!m) return null;
  return { owner: m[1], repo: m[2].replace(/\.git$/, ''), pullNumber: Number(m[3]) };
}

export async function fetchPrCiStatus(prUrl, { githubToken = '', apiBase = 'https://api.github.com' } = {}) {
  const parsed = parsePrUrl(prUrl);
  if (!parsed) return { status: 'unknown', reason: 'unparseable_pr_url' };

  const headers = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'agentmonitor-bridge',
  };
  if (githubToken) headers.Authorization = `Bearer ${githubToken}`;

  const base = apiBase.replace(/\/$/, '');
  const prRes = await fetch(
    `${base}/repos/${parsed.owner}/${parsed.repo}/pulls/${parsed.pullNumber}`,
    { headers, signal: AbortSignal.timeout(12000) },
  );
  if (!prRes.ok) {
    return { status: 'unknown', reason: `pr_http_${prRes.status}`, owner: parsed.owner, repo: parsed.repo };
  }
  const pr = await prRes.json();
  const sha = pr?.head?.sha;
  if (!sha) return { status: 'unknown', reason: 'no_head_sha' };

  const statusRes = await fetch(
    `${base}/repos/${parsed.owner}/${parsed.repo}/commits/${sha}/status`,
    { headers, signal: AbortSignal.timeout(12000) },
  );
  if (!statusRes.ok) {
    return { status: 'unknown', reason: `status_http_${statusRes.status}`, sha };
  }
  const combined = await statusRes.json();
  const state = combined?.state;

  if (state === 'success') return { status: 'green', sha, state, owner: parsed.owner, repo: parsed.repo };
  if (state === 'failure' || state === 'error') return { status: 'red', sha, state, owner: parsed.owner, repo: parsed.repo };
  return { status: 'pending', sha, state, owner: parsed.owner, repo: parsed.repo };
}
