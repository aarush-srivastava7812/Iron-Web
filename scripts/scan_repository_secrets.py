"""Redacted current-tree and reachable-Git-blob secret scan. Never emits matches."""
import subprocess,pathlib,re,json,math,collections
ROOT=pathlib.Path.cwd();G=['git','-c','safe.directory='+ROOT.as_posix()];OUT=ROOT/'.scratch/finalise-20261018'
def git(*args):return subprocess.check_output(G+list(args))
patterns={
'provider credential':re.compile(rb'(?:nvapi-[A-Za-z0-9_-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9_]{25,}|github_pat_[A-Za-z0-9_]{25,}|AIza[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16})'),
'hardcoded launcher session secret':re.compile(rb'voyara-strong-auth-secret-key-[A-Za-z0-9]{20,}'),
'private key':re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
'session JWT':re.compile(rb'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}'),
'assigned secret':re.compile(rb'''(?i)(?:api_key|secret_key|client_secret|access_token|refresh_token|publish_token|source_token|viewer_token|local_dashboard_grant|local_session_secret)\s*["']?\s*[:=]\s*["']([^"'\s]{24,})''')}
def findings(data):
 out=set()
 for kind,pat in patterns.items():
  for m in pat.finditer(data):
   v=m.group(1) if m.lastindex else m.group()
   if kind=='assigned secret' and (any(s in v.lower() for s in [b'example',b'test',b'replace',b'placeholder',b'your',b'redact',b'never',b'change-me',b'os.',b'settings.',b'process.',b'getenv',b'<',b'{',b'[',b'(',b')']) or len(set(v))<8):continue
   out.add(kind)
 return sorted(out)
current=[];names=git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')
for name in filter(None,names):
 p=ROOT/name
 if p.is_file():
  kinds=findings(p.read_bytes())
  if kinds:current.append({'path':name,'kinds':kinds})
print('Current tree scan complete:',len(names),'paths;',len(current),'findings',flush=True)
objects=[]
for line in git('rev-list','--objects','--all').decode().splitlines():
 sha,_,path=line.partition(' ');objects.append((sha,path))
proc=subprocess.Popen(G+['cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
history=[];blobcount=0
for sha,path in objects:
 proc.stdin.write((sha+'\n').encode());proc.stdin.flush();head=proc.stdout.readline().decode().split();size=int(head[2]);data=proc.stdout.read(size);proc.stdout.read(1)
 if head[1]!='blob':continue
 blobcount+=1;kinds=findings(data)
 if kinds:
  commits=git('log','--all','--format=%H','--find-object='+sha).decode().splitlines()
  history.append({'path':path,'blob':sha,'commits':commits,'kinds':kinds})
proc.stdin.close();proc.wait()
sensitive=[]
for name in filter(None,git('ls-files','-z').decode().split('\0')):
 base=pathlib.PurePosixPath(name).name.lower()
 if (base.startswith('.env') and base!='.env.example') or name.startswith('.scratch/') or re.fullmatch(r'(?:storage.?state|credentials|session)\.json',base):sensitive.append(name)
report={'scope':'All tracked + nonignored untracked files and every reachable Git blob across local refs; ignored runtime/dependencies not copied','tree_paths':len(names),'history_blobs':blobcount,'current':current,'history':history,'tracked_sensitive_filenames':sensitive,'limitations':'Pattern-based scan can miss custom encodings or provider formats. Ignored active .env/session contents deliberately not copied.'}
(OUT/'secret-scan.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
