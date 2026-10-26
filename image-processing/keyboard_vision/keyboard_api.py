"""Start with: python -m keyboard_vision.keyboard_api --port 8001."""
import argparse, json, os, re, socket, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import cv2, numpy as np
from defect_vision.image_io import decode_upright_rgb
from .config import CONFIG
from .pipeline import ContourKeyboardLocalizer, ContourKeyDetector, cluster_rows, geometry_defects, quality
ROOT=Path(__file__).resolve().parent / 'assets'
class Server(ThreadingHTTPServer):
    allow_reuse_address=os.name!='nt'
    def server_bind(self):
        if os.name=='nt': self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()
def result(inspection_id, image, status='insufficient_evidence', reasons=None, keyboard=None, defects=None, assets=None, elapsed=0):
    h,w=image.shape[:2]; reasons=reasons or []; keyboard=keyboard or {'detected':False,'confidence':0.0,'layoutType':'unknown','rowsDetected':0,'keysExpected':None,'keysDetected':0,'referenceMode':'none','quality':quality(image)}
    defects=defects or []
    return {'inspectionId':inspection_id,'success':status!='processing_error','status':status,'hasDefect':bool(defects),'sourceImage':{'url':f'/api/keyboard-assets/{inspection_id}/source.png','width':w,'height':h,'coordinateSpace':'source'},'displayImage':{'url':f'/api/keyboard-assets/{inspection_id}/annotated.png','width':w,'height':h,'coordinateSpace':'processed'},'keyboard':keyboard,'defects':defects,'summary':{'defectCount':len(defects),'needsReview':status!='completed','reasons':reasons},'processing':{'preprocessingMs':0,'inferenceMs':0,'postprocessingMs':0,'totalMs':round(elapsed,2)},'assets':assets or {'annotatedImage':f'/api/keyboard-assets/{inspection_id}/annotated.png','rectifiedKeyboardImage':None,'keyGridDebugImage':None}}
def analyze(body):
    started=time.perf_counter(); image=cv2.cvtColor(decode_upright_rgb(body),cv2.COLOR_RGB2BGR)
    iid=str(uuid.uuid4()); folder=ROOT/iid; folder.mkdir(parents=True,exist_ok=False); cv2.imwrite(str(folder/'source.png'),image)
    q=quality(image)
    if q['status']!='acceptable':
        cv2.imwrite(str(folder/'annotated.png'),image); return result(iid,image,reasons=q['reasons'],elapsed=(time.perf_counter()-started)*1000)
    roi, confidence, origin=ContourKeyboardLocalizer().localize(image)
    if roi is None:
        cv2.imwrite(str(folder/'annotated.png'),image); return result(iid,image,reasons=['Không tìm đủ vùng bàn phím để kết luận.'],elapsed=(time.perf_counter()-started)*1000)
    keys=ContourKeyDetector().detect(roi); rows=cluster_rows(keys)
    if len(keys)<8 or len(rows)<2:
        cv2.imwrite(str(folder/'annotated.png'),image); return result(iid,image,reasons=['Không phát hiện đủ lưới phím đáng tin cậy.'],keyboard={'detected':True,'confidence':confidence,'layoutType':'unknown','rowsDetected':len(rows),'keysExpected':None,'keysDetected':len(keys),'referenceMode':'none','quality':q},elapsed=(time.perf_counter()-started)*1000)
    defects=geometry_defects(rows); annotated=image.copy()
    for d in defects:
        b=d['bbox']; b['x1']+=origin[0]; b['x2']+=origin[0]; b['y1']+=origin[1]; b['y2']+=origin[1]
        cv2.rectangle(annotated,(b['x1'],b['y1']),(b['x2'],b['y2']),(0,0,255),2)
    cv2.imwrite(str(folder/'annotated.png'),annotated); cv2.imwrite(str(folder/'rectified.png'),roi)
    keyboard={'detected':True,'confidence':round(confidence,2),'layoutType':'custom','rowsDetected':len(rows),'keysExpected':None,'keysDetected':len(keys),'referenceMode':'none','quality':q}
    return result(iid,image,'completed',keyboard=keyboard,defects=defects,assets={'annotatedImage':f'/api/keyboard-assets/{iid}/annotated.png','rectifiedKeyboardImage':f'/api/keyboard-assets/{iid}/rectified.png','keyGridDebugImage':None},elapsed=(time.perf_counter()-started)*1000)
def handler():
 class H(BaseHTTPRequestHandler):
  def json(self,code,value):
   data=json.dumps(value,ensure_ascii=False,allow_nan=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
  def do_GET(self):
   path=urlparse(self.path).path
   if path=='/health': return self.json(200,{'status':'ready','configVersion':CONFIG['version']})
   match=re.fullmatch(r'/api/keyboard-assets/([0-9a-f-]{36})/([a-z_]+\.png)',path)
   if match and (file:=ROOT/match[1]/match[2]).is_file():
    data=file.read_bytes(); self.send_response(200); self.send_header('Content-Type','image/png'); self.send_header('Content-Length',str(len(data))); self.end_headers(); return self.wfile.write(data)
   self.json(404,{'error':'not_found'})
  def do_POST(self):
   if urlparse(self.path).path!='/analyze': return self.json(404,{'error':'not_found'})
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=CONFIG['max_upload_bytes']: return self.json(413,{'error':'invalid_upload_size'})
    self.json(200,analyze(self.rfile.read(length)))
   except ValueError as e: self.json(422,{'status':'insufficient_evidence','error':str(e)})
   except Exception as e: self.json(500,{'status':'processing_error','error':'Keyboard worker processing failed.'})
 return H
def main():
 p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8001);a=p.parse_args();Server((a.host,a.port),handler()).serve_forever()
if __name__=='__main__': main()
