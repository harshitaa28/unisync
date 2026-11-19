const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const crypto = require('crypto');

const PORT = process.env.PORT || 3000;
const ROOT = __dirname;
const PUBLIC_DIR = path.join(ROOT, 'public');
const UPLOAD_DIR = path.join(ROOT, 'uploads');

if (!fs.existsSync(PUBLIC_DIR)) fs.mkdirSync(PUBLIC_DIR, { recursive: true });
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });

function findPythonBin() {
  for (const cmd of ['python3', 'python', 'py']) {
    const res = spawnSync(cmd, ['--version'], { stdio: 'ignore' });
    if (!res.error && res.status === 0) return cmd;
  }
  console.error('Error: Python 3 is not installed or not in PATH. Install Python 3 from https://www.python.org/downloads/ and check "Add python.exe to PATH".');
  process.exit(1);
}

// Persistent Python SQLite Worker
const pyWorker = spawn(findPythonBin(), ['-u', path.join(ROOT, 'db_worker.py')], {
  stdio: ['pipe', 'pipe', 'inherit'],
});

let rpcCounter = 0;
const pendingRpc = new Map();
let stdoutBuf = '';

pyWorker.stdout.on('data', (chunk) => {
  stdoutBuf += chunk.toString();
  let idx;
  while ((idx = stdoutBuf.indexOf('\n')) !== -1) {
    const line = stdoutBuf.slice(0, idx).trim();
    stdoutBuf = stdoutBuf.slice(idx + 1);
    if (!line) continue;
    try {
      const msg = JSON.parse(line);
      const resolver = pendingRpc.get(msg.id);
      if (resolver) {
        pendingRpc.delete(msg.id);
        if (msg.error) resolver.reject(new Error(msg.error));
        else resolver.resolve(msg.result);
      }
    } catch (err) {
      console.error('RPC parse error:', err);
    }
  }
});

function dbCall(op, userId, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++rpcCounter;
    pendingRpc.set(id, { resolve, reject });
    pyWorker.stdin.write(JSON.stringify({ id, op, userId, params }) + '\n');
  });
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk.toString();
      if (body.length > 10 * 1024 * 1024) {
        reject(new Error('Payload too large'));
      }
    });
    req.on('end', () => {
      if (!body) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (e) {
        reject(new Error('Invalid JSON'));
      }
    });
  });
}

function sendJson(res, status, data) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, X-User-Id',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
  });
  res.end(JSON.stringify(data));
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Content-Type, X-User-Id',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
    });
    return res.end();
  }

  const urlObj = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = urlObj.pathname;
  const userId = req.headers['x-user-id'] || urlObj.searchParams.get('userId') || 'u_student';

  try {
    if (pathname === '/api/health' && req.method === 'GET') {
      return sendJson(res, 200, { ok: true, service: 'UniSync Backend (Node.js + SQLite)' });
    }

    if (pathname === '/api/bootstrap' && req.method === 'GET') {
      const data = await dbCall('bootstrap', userId);
      return sendJson(res, 200, data);
    }

    if (pathname === '/api/summarize' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('summarize_notice', userId, body);
      return sendJson(res, 200, data);
    }

    if (pathname === '/api/signup' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('signup', userId, body);
      return sendJson(res, 200, data);
    }

    if (pathname === '/api/profile' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('update_profile', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    if (pathname === '/api/upload' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const safeName = (body.filename || 'document.txt').replace(/[^a-zA-Z0-9._-]/g, '_');
      const uniqueName = `${Date.now()}_${crypto.randomBytes(3).toString('hex')}_${safeName}`;
      const filePath = path.join(UPLOAD_DIR, uniqueName);
      const content = body.base64 ? Buffer.from(body.base64, 'base64') : Buffer.from(body.text || 'Uploaded document');
      fs.writeFileSync(filePath, content);
      return sendJson(res, 200, { ok: true, url: `/uploads/${uniqueName}`, filename: safeName });
    }

    if (pathname === '/api/events' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('create_event', userId, body);
      return sendJson(res, data.error ? 403 : 201, data);
    }

    const resubmitMatch = pathname.match(/^\/api\/events\/([^/]+)\/resubmit$/);
    if (resubmitMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.event_id = resubmitMatch[1];
      const data = await dbCall('edit_resubmit_event', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    const facultyMatch = pathname.match(/^\/api\/events\/([^/]+)\/faculty-review$/);
    if (facultyMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.event_id = facultyMatch[1];
      const data = await dbCall('faculty_review_club_event', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    const adminMatch = pathname.match(/^\/api\/events\/([^/]+)\/admin-verify$/);
    if (adminMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.event_id = adminMatch[1];
      const data = await dbCall('admin_verify_event', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    const ackMatch = pathname.match(/^\/api\/events\/([^/]+)\/acknowledge$/);
    if (ackMatch && req.method === 'POST') {
      const data = await dbCall('acknowledge_event', userId, { event_id: ackMatch[1] });
      return sendJson(res, 200, data);
    }

    if (pathname === '/api/tickets' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('create_ticket', userId, body);
      return sendJson(res, 201, data);
    }

    const ticketFbMatch = pathname.match(/^\/api\/tickets\/([^/]+)\/feedback$/);
    if (ticketFbMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.ticket_id = ticketFbMatch[1];
      const data = await dbCall('ticket_feedback', userId, body);
      return sendJson(res, 200, data);
    }

    if (pathname === '/api/deadlines' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('add_deadline', userId, body);
      return sendJson(res, 201, data);
    }

    const dlToggleMatch = pathname.match(/^\/api\/deadlines\/([^/]+)\/toggle$/);
    if (dlToggleMatch && req.method === 'POST') {
      const data = await dbCall('toggle_deadline', userId, { deadline_id: dlToggleMatch[1] });
      return sendJson(res, 200, data);
    }

    const remSimMatch = pathname.match(/^\/api\/reminders\/([^/]+)\/simulate$/);
    if (remSimMatch && req.method === 'POST') {
      const data = await dbCall('simulate_reminder', userId, { reminder_id: remSimMatch[1] });
      return sendJson(res, 200, data);
    }

    const joinClubMatch = pathname.match(/^\/api\/communities\/([^/]+)\/join$/);
    if (joinClubMatch && req.method === 'POST') {
      const data = await dbCall('join_community', userId, { community_id: joinClubMatch[1] });
      return sendJson(res, 200, data);
    }

    const approveMemberMatch = pathname.match(/^\/api\/community-members\/([^/]+)\/approve$/);
    if (approveMemberMatch && req.method === 'POST') {
      const data = await dbCall('approve_community_member', userId, { member_id: approveMemberMatch[1] });
      return sendJson(res, data.error ? 403 : 200, data);
    }

    if (pathname === '/api/qa' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('create_qa_post', userId, body);
      return sendJson(res, 201, data);
    }

    const qaAnsMatch = pathname.match(/^\/api\/qa\/([^/]+)\/answer$/);
    if (qaAnsMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.post_id = qaAnsMatch[1];
      const data = await dbCall('create_qa_answer', userId, body);
      return sendJson(res, 201, data);
    }

    const qaUpvoteMatch = pathname.match(/^\/api\/qa\/([^/]+)\/upvote$/);
    if (qaUpvoteMatch && req.method === 'POST') {
      const data = await dbCall('upvote_qa', userId, { post_id: qaUpvoteMatch[1] });
      return sendJson(res, 200, data);
    }

    if (pathname === '/api/admin/tags' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const data = await dbCall('admin_manage_tag', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    const adminClubMatch = pathname.match(/^\/api\/admin\/clubs\/([^/]+)$/);
    if (adminClubMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.club_id = adminClubMatch[1];
      const data = await dbCall('admin_update_club', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    const adminRouteMatch = pathname.match(/^\/api\/admin\/routes\/([^/]+)$/);
    if (adminRouteMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.category = decodeURIComponent(adminRouteMatch[1]);
      const data = await dbCall('admin_update_route', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    const cabinMatch = pathname.match(/^\/api\/cabins\/([^/]+)$/);
    if (cabinMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.cabin_id = cabinMatch[1];
      const data = await dbCall('update_cabin_status', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    const venueMatch = pathname.match(/^\/api\/venues\/([^/]+)\/toggle$/);
    if (venueMatch && req.method === 'POST') {
      const body = await readJsonBody(req);
      body.slot_id = venueMatch[1];
      const data = await dbCall('toggle_venue_slot', userId, body);
      return sendJson(res, data.error ? 403 : 200, data);
    }

    if (pathname === '/api/notifications/read' && req.method === 'POST') {
      const data = await dbCall('mark_notifications_read', userId);
      return sendJson(res, 200, data);
    }

    // Serve uploaded files
    if (pathname.startsWith('/uploads/')) {
      const safeRel = path.basename(pathname);
      const fullPath = path.join(UPLOAD_DIR, safeRel);
      if (fs.existsSync(fullPath)) {
        res.writeHead(200);
        return fs.createReadStream(fullPath).pipe(res);
      }
      res.writeHead(404);
      return res.end('File not found');
    }

    // Serve frontend
    if (pathname === '/' || pathname === '/index.html') {
      const indexPath = path.join(PUBLIC_DIR, 'index.html');
      if (fs.existsSync(indexPath)) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        return fs.createReadStream(indexPath).pipe(res);
      }
    }

    res.writeHead(404);
    res.end('Not found');
  } catch (err) {
    console.error(err);
    sendJson(res, 500, { error: err.message });
  }
});

server.listen(PORT, () => {
  console.log(`UniSync server running at http://localhost:${PORT}`);
});
