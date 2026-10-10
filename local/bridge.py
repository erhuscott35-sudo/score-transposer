#!/usr/bin/env python3
"""Loopback-only, single-job local OMR + static app. Never calls an LLM."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import json,os,subprocess,tempfile,zipfile,threading,shutil
from PIL import Image,ImageOps
from pypdf import PdfReader
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent.parent
APP=Path(os.environ.get('AUDIVERIS_HOME',str(ROOT/'local/engine/Audiveris.app/Contents')))
JAVA=APP/'runtime/Contents/Home/bin/java'
TESS=Path(os.environ.get('TESSDATA_PREFIX',str(ROOT/'local/engine/tessdata')))
JOBS=ROOT/'local/jobs'; JOBS.mkdir(exist_ok=True)
from jobs import JobManager, Cancelled
ORIGINS={'http://localhost:3000','http://127.0.0.1:3000','http://127.0.0.1:8765','http://localhost:8765','https://worship-score-studio.erhuscott35.chatgpt.site'}

def reply(status, data):return status,data

def recognize(data,job):
 folder=Path(tempfile.mkdtemp(dir=JOBS))
 try:
  job.progress('正在檢查檔案…')
  ext='.pdf' if data.startswith(b'%PDF-') else '.jpg' if data.startswith(b'\xff\xd8') else '.png' if data.startswith(b'\x89PNG\r\n\x1a\n') else None
  if not ext:return reply(400,{'error':'無效的 PDF/JPG/PNG 檔案'})
  source=folder/('score'+ext);source.write_bytes(data)
  page_count=1
  if ext=='.pdf':
   try:
    reader=PdfReader(source)
    if reader.is_encrypted:return reply(422,{'error':'請先移除 PDF 密碼'})
    page_count=len(reader.pages)
   except Exception:return reply(422,{'error':'PDF 無法讀取或已損壞'})
   if not 1<=page_count<=20:return reply(413,{'error':'每份 PDF 需為 1–20 頁'})
  if ext!='.pdf':
   with Image.open(source) as image:
    if image.width*image.height>25000000:return reply(413,{'error':'圖片超過 2500 萬像素，請縮小後再試'})
    image=ImageOps.exif_transpose(image).convert('RGB')
    factor=max(1,3507/image.height)
    if image.width*image.height*factor*factor>25000000:return reply(413,{'error':'圖片比例不適合，請使用清晰的直式樂譜圖片'})
    if factor>1:image=image.resize((round(image.width*factor),3507),Image.Resampling.LANCZOS)
    source=folder/'score.png';image.save(source)

  env=dict(os.environ,TESSDATA_PREFIX=str(TESS));home=ROOT/'local/java-home';home.mkdir(exist_ok=True)
  cmd=[str(JAVA),'-Xmx2g',f'-Duser.home={home}','-Djava.awt.headless=true','--add-exports=java.desktop/sun.awt.image=ALL-UNNAMED','--enable-native-access=ALL-UNNAMED','-cp',str(APP/'app/*'),'Audiveris','-batch','-export','-constant','org.audiveris.omr.text.Language.defaultSpecification=eng+chi_tra','-output',str(folder),str(source)]
  job.progress(f'正在辨識整份樂譜（共 {page_count} 頁）；完成後核對頁數')
  with open(folder/'run.log','w') as log:code=job.run_process(cmd,env=env,log=log,timeout=min(1200,150*page_count))
  job.progress('正在檢查辨識結果與頁數…')
  exports=list(folder.glob('*.mxl'))
  if len(exports)>1:return reply(422,{'error':'辨識器將此檔案分成多首樂曲，請將各首分開上傳，避免遺漏頁面'})
  mxl=exports[0] if exports else None
  if code or not mxl:return reply(422,{'error':'此譜無法完成辨識，請使用清晰、端正的樂譜'})
  with zipfile.ZipFile(mxl) as z:
   entry=next((i for i in z.infolist() if i.filename.endswith('.xml') and not i.filename.startswith('META-INF/')),None)
   if not entry or entry.file_size>8*1024*1024:return reply(422,{'error':'辨識結果過大或不完整'})
   xml=z.read(entry).decode('utf-8')
  tree=ET.fromstring(xml)
  parts=tree.findall('part')
  exported_pages=1+sum(1 for m in parts[0].findall('measure') if m.find("print[@new-page='yes']") is not None) if parts else 0
  if exported_pages!=page_count:return reply(422,{'error':f'原稿 {page_count} 頁，但結果只有 {exported_pages} 頁；未載入不完整結果，請分段處理'})
  return reply(200,{'xml':xml,'pageCount':page_count,'reviewRequired':True})
 except subprocess.TimeoutExpired:return reply(504,{'error':'辨識逾時，請裁切留白並提高影像清晰度後再試'})
 except Cancelled:raise
 except Exception as e:return reply(500,{'error':'本機辨識失敗：'+type(e).__name__})
 finally:shutil.rmtree(folder,ignore_errors=True)
MANAGER=JobManager(recognize)

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'dist/client'),**kwargs)
 def allowed(self):return self.headers.get('Host','') in {'127.0.0.1:8765','localhost:8765'} and self.headers.get('Origin') in ORIGINS|{None}
 def end_headers(self):
  origin=self.headers.get('Origin')
  if origin in ORIGINS:self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin');self.send_header('Access-Control-Allow-Private-Network','true')
  self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
 def reply(self,status,data):
  body=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_OPTIONS(self):
  if not self.allowed():return self.reply(403,{'error':'來源不允許'})
  self.send_response(204);self.send_header('Access-Control-Allow-Methods','GET, POST, DELETE, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers()
 def do_GET(self):
  if not self.allowed():return self.reply(403,{'error':'來源不允許'})
  if self.path=='/api/health':return self.reply(200,{'ready':JAVA.exists() and all((TESS/(lang+'.traineddata')).exists() for lang in ('eng','chi_tra')),'engine':'Audiveris 5.11.0','apiVersion':3,'maxPages':20})
  if self.path.startswith('/api/jobs/'):
   job=MANAGER.get(self.path.rsplit('/',1)[-1])
   return self.reply(200,job.snapshot()) if job else self.reply(404,{'error':'工作不存在或已過期'})
  if self.path in ('/','/index.html') and not (ROOT/'dist/client/index.html').exists():return self.reply(503,{'error':'請先建立網頁版本。'})
  return super().do_GET()

 def do_DELETE(self):
  if not self.allowed():return self.reply(403,{'error':'來源不允許'})
  if not self.path.startswith('/api/jobs/'):return self.reply(404,{'error':'找不到功能'})
  job=MANAGER.cancel(self.path.rsplit('/',1)[-1])
  return self.reply(200,job.snapshot()) if job else self.reply(404,{'error':'工作不存在或已過期'})
 def do_POST(self):
  if not self.allowed():return self.reply(403,{'error':'來源不允許'})
  if self.path!='/api/jobs':return self.reply(404,{'error':'請更新網頁與本機辨識器至同一版本'})
  try:length=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.reply(400,{'error':'檔案長度不正確'})
  if not 0<length<=15*1024*1024:return self.reply(413,{'error':'請上傳 15 MB 以內的檔案'})
  if not JAVA.exists() or not all((TESS/(lang+'.traineddata')).exists() for lang in ('eng','chi_tra')):
   return self.reply(503,{'error':'尚未安裝本機辨識器或英／繁中語言資料'})
  self.connection.settimeout(30)
  data=self.rfile.read(length)
  if len(data)!=length:return self.reply(400,{'error':'檔案傳輸不完整'})
  try:job=MANAGER.submit(data)
  except RuntimeError as e:return self.reply(429,{'error':str(e)})
  self.reply(202,job.snapshot())
if __name__=='__main__':
 print('樂譜工具：http://127.0.0.1:8765　關閉此視窗即可停止。',flush=True)
 ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
