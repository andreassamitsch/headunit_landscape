#!/usr/bin/env python3
from __future__ import annotations

"""Create a reproducible static-analysis reference from NavRadio+ 4.08.

This is a small DEX indexer/disassembler for documentation and interoperability
analysis. It does not recover the author's original Java/Kotlin source and its
pseudo-Smali output can be imperfect for uncommon opcodes.
"""

import argparse
import hashlib
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path

ACC = [(0x1,'public'),(0x2,'private'),(0x4,'protected'),(0x8,'static'),(0x10,'final'),(0x20,'synchronized'),(0x40,'bridge'),(0x80,'varargs'),(0x100,'native'),(0x200,'interface'),(0x400,'abstract'),(0x800,'strictfp'),(0x1000,'synthetic'),(0x10000,'constructor'),(0x20000,'declared-synchronized')]
def acc(v): return ' '.join(n for b,n in ACC if v&b)
def uleb(d,o):
 r=0;s=0
 while True:
  b=d[o];o+=1;r|=(b&0x7f)<<s
  if not b&0x80:return r,o
  s+=7

def sleb(d,o):
 r=0;s=0
 while True:
  b=d[o];o+=1;r|=(b&0x7f)<<s;s+=7
  if not b&0x80:
   if b&0x40:r|=-(1<<s)
   return r,o

def mutf8(raw): return raw.replace(b'\xc0\x80',b'\x00').decode('utf-8','replace')
def sgn(v,bits): return v-(1<<bits) if v&(1<<(bits-1)) else v

OP={}
def add(code,name,length,ref=None):OP[code]=(name,length,ref)
_specs='''
00 nop 1
01 move 1
02 move/from16 2
03 move/16 3
04 move-wide 1
05 move-wide/from16 2
06 move-wide/16 3
07 move-object 1
08 move-object/from16 2
09 move-object/16 3
0a move-result 1
0b move-result-wide 1
0c move-result-object 1
0d move-exception 1
0e return-void 1
0f return 1
10 return-wide 1
11 return-object 1
12 const/4 1
13 const/16 2
14 const 3
15 const/high16 2
16 const-wide/16 2
17 const-wide/32 3
18 const-wide 5
19 const-wide/high16 2
1a const-string 2 string
1b const-string/jumbo 3 string32
1c const-class 2 type
1d monitor-enter 1
1e monitor-exit 1
1f check-cast 2 type
20 instance-of 2 type
21 array-length 1
22 new-instance 2 type
23 new-array 2 type
24 filled-new-array 3 type
25 filled-new-array/range 3 type
26 fill-array-data 3
27 throw 1
28 goto 1
29 goto/16 2
2a goto/32 3
2b packed-switch 3
2c sparse-switch 3
2d cmpl-float 2
2e cmpg-float 2
2f cmpl-double 2
30 cmpg-double 2
31 cmp-long 2
32 if-eq 2
33 if-ne 2
34 if-lt 2
35 if-ge 2
36 if-gt 2
37 if-le 2
38 if-eqz 2
39 if-nez 2
3a if-ltz 2
3b if-gez 2
3c if-gtz 2
3d if-lez 2
44 aget 2
45 aget-wide 2
46 aget-object 2
47 aget-boolean 2
48 aget-byte 2
49 aget-char 2
4a aget-short 2
4b aput 2
4c aput-wide 2
4d aput-object 2
4e aput-boolean 2
4f aput-byte 2
50 aput-char 2
51 aput-short 2
52 iget 2 field
53 iget-wide 2 field
54 iget-object 2 field
55 iget-boolean 2 field
56 iget-byte 2 field
57 iget-char 2 field
58 iget-short 2 field
59 iput 2 field
5a iput-wide 2 field
5b iput-object 2 field
5c iput-boolean 2 field
5d iput-byte 2 field
5e iput-char 2 field
5f iput-short 2 field
60 sget 2 field
61 sget-wide 2 field
62 sget-object 2 field
63 sget-boolean 2 field
64 sget-byte 2 field
65 sget-char 2 field
66 sget-short 2 field
67 sput 2 field
68 sput-wide 2 field
69 sput-object 2 field
6a sput-boolean 2 field
6b sput-byte 2 field
6c sput-char 2 field
6d sput-short 2 field
6e invoke-virtual 3 method
6f invoke-super 3 method
70 invoke-direct 3 method
71 invoke-static 3 method
72 invoke-interface 3 method
74 invoke-virtual/range 3 method
75 invoke-super/range 3 method
76 invoke-direct/range 3 method
77 invoke-static/range 3 method
78 invoke-interface/range 3 method
7b neg-int 1
7c not-int 1
7d neg-long 1
7e not-long 1
7f neg-float 1
80 neg-double 1
81 int-to-long 1
82 int-to-float 1
83 int-to-double 1
84 long-to-int 1
85 long-to-float 1
86 long-to-double 1
87 float-to-int 1
88 float-to-long 1
89 float-to-double 1
8a double-to-int 1
8b double-to-long 1
8c double-to-float 1
8d int-to-byte 1
8e int-to-char 1
8f int-to-short 1
90 add-int 2
91 sub-int 2
92 mul-int 2
93 div-int 2
94 rem-int 2
95 and-int 2
96 or-int 2
97 xor-int 2
98 shl-int 2
99 shr-int 2
9a ushr-int 2
9b add-long 2
9c sub-long 2
9d mul-long 2
9e div-long 2
9f rem-long 2
a0 and-long 2
a1 or-long 2
a2 xor-long 2
a3 shl-long 2
a4 shr-long 2
a5 ushr-long 2
a6 add-float 2
a7 sub-float 2
a8 mul-float 2
a9 div-float 2
aa rem-float 2
ab add-double 2
ac sub-double 2
ad mul-double 2
ae div-double 2
af rem-double 2
b0 add-int/2addr 1
b1 sub-int/2addr 1
b2 mul-int/2addr 1
b3 div-int/2addr 1
b4 rem-int/2addr 1
b5 and-int/2addr 1
b6 or-int/2addr 1
b7 xor-int/2addr 1
b8 shl-int/2addr 1
b9 shr-int/2addr 1
ba ushr-int/2addr 1
bb add-long/2addr 1
bc sub-long/2addr 1
bd mul-long/2addr 1
be div-long/2addr 1
bf rem-long/2addr 1
c0 and-long/2addr 1
c1 or-long/2addr 1
c2 xor-long/2addr 1
c3 shl-long/2addr 1
c4 shr-long/2addr 1
c5 ushr-long/2addr 1
c6 add-float/2addr 1
c7 sub-float/2addr 1
c8 mul-float/2addr 1
c9 div-float/2addr 1
ca rem-float/2addr 1
cb add-double/2addr 1
cc sub-double/2addr 1
cd mul-double/2addr 1
ce div-double/2addr 1
cf rem-double/2addr 1
d0 add-int/lit16 2
d1 rsub-int 2
d2 mul-int/lit16 2
d3 div-int/lit16 2
d4 rem-int/lit16 2
d5 and-int/lit16 2
d6 or-int/lit16 2
d7 xor-int/lit16 2
d8 add-int/lit8 2
d9 rsub-int/lit8 2
da mul-int/lit8 2
db div-int/lit8 2
dc rem-int/lit8 2
dd and-int/lit8 2
de or-int/lit8 2
df xor-int/lit8 2
e0 shl-int/lit8 2
e1 shr-int/lit8 2
e2 ushr-int/lit8 2
fa invoke-polymorphic 4 method
fb invoke-polymorphic/range 4 method
fc invoke-custom 3 callsite
fd invoke-custom/range 3 callsite
fe const-method-handle 2 mhandle
ff const-method-type 2 proto
'''
for ln in _specs.strip().splitlines():
 p=ln.split(); add(int(p[0],16),p[1],int(p[2]),p[3] if len(p)>3 else None)

class Dex:
 def __init__(self,data:bytes):
  self.d=data
  if data[:4]!=b'dex\n': raise ValueError('not dex')
  vals=struct.unpack_from('<14I',data,0x38)
  (self.n_str,self.off_str,self.n_type,self.off_type,self.n_proto,self.off_proto,self.n_field,self.off_field,self.n_method,self.off_method,self.n_class,self.off_class,self.data_size,self.data_off)=vals
  self.sc={};self._methods=None;self._classes=None
 def string(self,i):
  if i in self.sc:return self.sc[i]
  o=struct.unpack_from('<I',self.d,self.off_str+4*i)[0];_,o=uleb(self.d,o);e=self.d.index(0,o);s=mutf8(self.d[o:e]);self.sc[i]=s;return s
 def type(self,i): return self.string(struct.unpack_from('<I',self.d,self.off_type+4*i)[0])
 def proto(self,i):
  _,ret,po=struct.unpack_from('<III',self.d,self.off_proto+12*i);ps=[]
  if po:
   n=struct.unpack_from('<I',self.d,po)[0]
   ps=[self.type(struct.unpack_from('<H',self.d,po+4+2*k)[0]) for k in range(n)]
  return '('+''.join(ps)+')'+self.type(ret)
 def method_ref(self,i):
  c,p,n=struct.unpack_from('<HHI',self.d,self.off_method+8*i);return self.type(c),self.string(n),self.proto(p)
 def field_ref(self,i):
  c,t,n=struct.unpack_from('<HHI',self.d,self.off_field+8*i);return self.type(c),self.string(n),self.type(t)
 def classes(self):
  if self._classes is not None:return self._classes
  out=[]
  for i in range(self.n_class):
   ci,ac,su,io,src,an,cd,sv=struct.unpack_from('<8I',self.d,self.off_class+32*i)
   interfaces=[]
   if io:
    n=struct.unpack_from('<I',self.d,io)[0];interfaces=[self.type(struct.unpack_from('<H',self.d,io+4+2*k)[0]) for k in range(n)]
   out.append({'idx':i,'name':self.type(ci),'access':ac,'super':None if su==0xffffffff else self.type(su),'interfaces':interfaces,'source':None if src==0xffffffff else self.string(src),'cdata':cd})
  self._classes=out;return out
 def class_methods(self,c):
  off=c['cdata'];out=[]
  if not off:return out
  sf,off=uleb(self.d,off);inf,off=uleb(self.d,off);dm,off=uleb(self.d,off);vm,off=uleb(self.d,off)
  for _ in range(sf+inf):_,off=uleb(self.d,off);_,off=uleb(self.d,off)
  for kind,count in [('direct',dm),('virtual',vm)]:
   mi=0
   for _ in range(count):
    di,off=uleb(self.d,off);a,off=uleb(self.d,off);co,off=uleb(self.d,off);mi+=di
    cl,n,p=self.method_ref(mi);out.append({'idx':mi,'class':cl,'name':n,'proto':p,'access':a,'code':co,'kind':kind})
  return out
 def all_methods(self):
  if self._methods is None:self._methods=[m for c in self.classes() for m in self.class_methods(c)]
  return self._methods
 def code_words(self,m):
  if not m['code']:return None
  regs,ins,outs,tries,dbg,n=struct.unpack_from('<HHHHII',self.d,m['code']);off=m['code']+16
  return {'regs':regs,'ins':ins,'outs':outs,'tries':tries,'debug':dbg,'size':n,'words':list(struct.unpack_from('<%dH'%n,self.d,off))}
 def ref(self,kind,i):
  try:
   if kind in ('string','string32'):return json.dumps(self.string(i),ensure_ascii=False)
   if kind=='type':return self.type(i)
   if kind=='field':c,n,t=self.field_ref(i);return f'{c}->{n}:{t}'
   if kind=='method':c,n,p=self.method_ref(i);return f'{c}->{n}{p}'
   if kind=='proto':return self.proto(i)
  except Exception as e:return f'<bad-{kind}-{i}:{e}>'
  return f'@{kind}:{i}'
 def insns(self,m):
  ci=self.code_words(m)
  if not ci:return []
  w=ci['words'];p=0;out=[]
  while p<len(w):
   w0=w[p];op=w0&0xff
   if op==0 and (w0>>8):
    ident=w0>>8
    if ident==1 and p+1<len(w):ln=4+2*w[p+1];txt=f'.packed-switch-payload size={w[p+1]}'
    elif ident==2 and p+1<len(w):ln=2+4*w[p+1];txt=f'.sparse-switch-payload size={w[p+1]}'
    elif ident==3 and p+3<len(w):sz=w[p+2]|(w[p+3]<<16);ln=4+(sz*w[p+1]+1)//2;txt=f'.array-data-payload width={w[p+1]} size={sz}'
    else:ln=1;txt=f'.unknown-payload {ident}'
    out.append({'off':p,'op':op,'name':txt,'len':ln,'ref':None,'text':txt});p+=max(1,ln);continue
   name,ln,kind=OP.get(op,(f'op_{op:02x}',1,None))
   if p+ln>len(w):ln=1
   AA=(w0>>8)&0xff;A=(w0>>8)&0xf;B=(w0>>12)&0xf
   refi=None;extra=''
   if kind:
    if kind=='string32' and p+2<len(w):refi=w[p+1]|(w[p+2]<<16)
    elif p+1<len(w):refi=w[p+1]
   if op==0x1a: extra=f'v{AA}, {self.ref(kind,refi)}'
   elif op==0x1b:extra=f'v{AA}, {self.ref(kind,refi)}'
   elif op in (0x1c,0x22):extra=f'v{AA}, {self.ref(kind,refi)}'
   elif op in range(0x52,0x60):extra=f'v{A}, v{B}, {self.ref(kind,refi)}'
   elif op in range(0x60,0x6e):extra=f'v{AA}, {self.ref(kind,refi)}'
   elif op in range(0x6e,0x73) and p+2<len(w):
    count=(w0>>12)&0xf;g=(w0>>8)&0xf;regsword=w[p+2];regs=[regsword&0xf,(regsword>>4)&0xf,(regsword>>8)&0xf,(regsword>>12)&0xf,g][:count];extra='{'+', '.join('v%d'%r for r in regs)+'}, '+self.ref(kind,refi)
   elif op in range(0x74,0x79) and p+2<len(w):extra=f'{{v{w[p+2]} .. v{w[p+2]+AA-1}}}, {self.ref(kind,refi)}'
   elif op==0x12:extra=f'v{A}, #{sgn(B,4)}'
   elif op in (0x13,0x16):extra=f'v{AA}, #{sgn(w[p+1],16)}'
   elif op in (0x14,0x17) and p+2<len(w):extra=f'v{AA}, #{sgn(w[p+1]|(w[p+2]<<16),32)}'
   elif op==0x0e:extra=''
   elif op in (0x0f,0x10,0x11,0x0a,0x0b,0x0c,0x0d,0x27):extra=f'v{AA}'
   elif op==0x28:extra=f':{p+sgn(AA,8):04x}'
   elif op==0x29:extra=f':{p+sgn(w[p+1],16):04x}'
   elif op==0x2a and p+2<len(w):extra=f':{p+sgn(w[p+1]|(w[p+2]<<16),32):04x}'
   elif op in range(0x32,0x38):extra=f'v{A}, v{B}, :{p+sgn(w[p+1],16):04x}'
   elif op in range(0x38,0x3e):extra=f'v{AA}, :{p+sgn(w[p+1],16):04x}'
   elif op in (0x2b,0x2c,0x26) and p+2<len(w):extra=f'v{AA}, :{p+sgn(w[p+1]|(w[p+2]<<16),32):04x}'
   elif ln==1 and op not in (0,):extra=f'0x{w0:04x}'
   else:extra=' '.join(f'{x:04x}' for x in w[p:p+ln])
   txt=name+(' '+extra if extra else '')
   out.append({'off':p,'op':op,'name':name,'len':ln,'ref':self.ref(kind,refi) if kind and refi is not None else None,'ref_idx':refi,'text':txt})
   p+=ln
  return out

def method_sig(m):return f"{m['class']}->{m['name']}{m['proto']}"
def dump_method(d,m):
 ci=d.code_words(m);lines=[f".method {acc(m['access'])} {m['name']}{m['proto']}"]
 if not ci:return '\n'.join(lines+['    # no code','.end method'])
 lines += [f"    .registers {ci['regs']}",f"    # method_idx={m['idx']} code_off=0x{m['code']:x}"]
 lines += [f"    :{i['off']:04x}  {i['text']}" for i in d.insns(m)]
 lines.append('.end method');return '\n'.join(lines)

def sha256(path: Path) -> str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def prepare_input(source: Path, out: Path, expected_sha256: str | None):
 actual=sha256(source)
 if expected_sha256 and actual.lower()!=expected_sha256.lower():
  raise SystemExit(f"SHA-256 mismatch for {source}: expected {expected_sha256}, got {actual}")
 metadata={'input_file':source.name,'input_sha256':actual,'input_size':source.stat().st_size}
 suffix=source.suffix.lower()
 if suffix=='.dex':
  return source,metadata
 if suffix=='.apk':
  apk=source
  metadata['base_apk_sha256']=actual
 elif suffix=='.xapk':
  xdir=out/'extracted-xapk';xdir.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(source) as z:z.extractall(xdir)
  manifest_path=xdir/'manifest.json'
  if not manifest_path.exists():raise SystemExit('XAPK manifest.json missing')
  xmanifest=json.loads(manifest_path.read_text(encoding='utf-8'))
  metadata['xapk_manifest']=xmanifest
  base_name=next((x['file'] for x in xmanifest.get('split_apks',[]) if x.get('id')=='base'),None)
  if not base_name:raise SystemExit('XAPK base APK not declared')
  apk=xdir/base_name
  metadata['split_files']={x['file']:{'id':x.get('id'),'size':(xdir/x['file']).stat().st_size,'sha256':sha256(xdir/x['file'])} for x in xmanifest.get('split_apks',[])}
  metadata['base_apk_sha256']=sha256(apk)
 else:
  raise SystemExit('Input must be .xapk, .apk or classes.dex')
 adir=out/'extracted-apk';adir.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(apk) as z:
  names=[n for n in z.namelist() if re.fullmatch(r'classes(?:\d+)?\.dex',n)]
  if not names:raise SystemExit('No classes.dex found in base APK')
  if len(names)>1:metadata['warning']='Only classes.dex is analyzed; additional DEX files exist: '+', '.join(names[1:])
  dex_path=adir/'classes.dex'
  with z.open(names[0]) as src,dex_path.open('wb') as dst:shutil.copyfileobj(src,dst)
 metadata['dex_sha256']=sha256(dex_path)
 metadata['dex_size']=dex_path.stat().st_size
 return dex_path,metadata

def main():
 ap=argparse.ArgumentParser(description='Extract and index NavRadio+ 4.08 XAPK/APK/DEX for static reference.')
 ap.add_argument('source',help='Path to NavRadio+ .xapk, base .apk or classes.dex')
 ap.add_argument('--out',required=True,help='Output directory')
 ap.add_argument('--expected-sha256',help='Fail when the input does not match this SHA-256')
 ap.add_argument('--terms',nargs='*',default=[])
 args=ap.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 dex_path,source_meta=prepare_input(Path(args.source),out,args.expected_sha256)
 (out/'source-manifest.json').write_text(json.dumps(source_meta,indent=2,ensure_ascii=False),encoding='utf-8')
 d=Dex(dex_path.read_bytes());methods=d.all_methods();classes=d.classes()
 (out/'dex-summary.json').write_text(json.dumps({'strings':d.n_str,'types':d.n_type,'fields':d.n_field,'methods':d.n_method,'classes':d.n_class},indent=2),encoding='utf-8')
 with (out/'class-method-index.txt').open('w',encoding='utf-8') as f:
  for c in classes:
   f.write(f"CLASS {c['name']} extends {c['super']} implements {','.join(c['interfaces'])}\n")
   for m in d.class_methods(c):f.write(f"  {m['idx']:5d} {acc(m['access'])} {m['name']}{m['proto']} code=0x{m['code']:x}\n")
 terms=args.terms or ['DUDUAUTO','SC7870','uis7870','detected_DUDU7','isDUDU7','QFService','IMediaButtonListener','MEDIA_BUTTON','RadioProxy','FmService','FmNative','TWUtil','com.syu.ms','com.syu.music','com.syu.radio','nextStation','prevStation']
 term_idx={t:[] for t in terms}
 for i in range(d.n_str):
  value=d.string(i)
  for t in terms:
   if t.lower() in value.lower():term_idx[t].append({'idx':i,'value':value})
 (out/'matched-strings.json').write_text(json.dumps(term_idx,indent=2,ensure_ascii=False),encoding='utf-8')
 hits=[];callers={}
 for m in methods:
  ins=d.insns(m);mh=[]
  for x in ins:
   if x['ref'] and any(t.lower() in x['ref'].lower() for t in terms):mh.append(x)
   if x['ref'] and x['name'].startswith('invoke-'):callers.setdefault(x['ref'],[]).append(method_sig(m))
  if mh:hits.append({'method':method_sig(m),'method_idx':m['idx'],'hits':[{'off':x['off'],'instruction':x['text']} for x in mh]})
 (out/'reference-hits.json').write_text(json.dumps(hits,indent=2,ensure_ascii=False),encoding='utf-8')
 key_names={'nextStation','prevStation','onCreate','init','x','y','getMethod','onBind','handleMessage','onReceive','onMediaButtonEvent','onPlayerCommandRequest','setStation','seekNextStation','seekPrevStation','onStartCommand','m1'}
 selected={m['idx']:m for m in methods if m['name'] in key_names and any(q in m['class'] for q in ('navimods/radio','android/fmradio','syu/'))}
 for h in hits:
  mm=next((m for m in methods if m['idx']==h['method_idx']),None)
  if mm:selected[mm['idx']]=mm
 for ref,cs in callers.items():
  if any(k in ref for k in ('->nextStation','->prevStation','IMediaButtonListener','QFService','FmService','RadioService')):
   for sig in cs:
    mm=next((m for m in methods if method_sig(m)==sig),None)
    if mm:selected[mm['idx']]=mm
 smdir=out/'selected-smali';smdir.mkdir(exist_ok=True);manifest=[]
 for m in sorted(selected.values(),key=lambda x:(x['class'],x['name'],x['proto'])):
  safe=re.sub(r'[^A-Za-z0-9_.-]+','_',method_sig(m)).strip('_')[:180]
  path=smdir/(safe+'.smali.txt');path.write_text(f"# class {m['class']}\n"+dump_method(d,m)+'\n',encoding='utf-8');manifest.append({'method':method_sig(m),'method_idx':m['idx'],'file':str(path.relative_to(out))})
 (out/'selected-methods.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(json.dumps({'source':source_meta,'dex':{'classes':d.n_class,'methods':d.n_method},'hits':len(hits),'selected':len(selected)},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
