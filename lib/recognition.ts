const BRIDGE='http://127.0.0.1:8765';
const pause=(ms:number)=>new Promise(resolve=>setTimeout(resolve,ms));
export async function recognizeLocal(bytes:ArrayBuffer,type:string,signal:AbortSignal,onProgress:(message:string)=>void) {
  const health=await fetch(BRIDGE+'/api/health',{signal:AbortSignal.timeout(3000)}).then(r=>r.json()).catch(()=>{
    throw Error('無法連接本機辨識器。請先啟動「啟動樂譜工具.command」，再重試。');
  });
  if(health.apiVersion!==3)throw Error('請重新啟動最新版的本機辨識器。');
  if(!health.ready)throw Error('本機辨識器或語言資料尚未安裝完成。');
  signal.throwIfAborted();
  // Do not abort creation in-flight: first obtain the job ID so cancellation can reach the server.
  const response=await fetch(BRIDGE+'/api/jobs',{method:'POST',headers:{'Content-Type':type},body:bytes,signal:AbortSignal.timeout(30000)});
  const created=await response.json();
  if(!response.ok)throw Error(created.error||'無法開始辨識');
  if(!/^[a-f0-9]{32}$/.test(created.id))throw Error('本機辨識器回傳了無效工作編號');
  const url=BRIDGE+'/api/jobs/'+created.id;
  let cancelSent=false;
  const deadline=Date.now()+1250000;
  try{
    while(Date.now()<deadline){
      if(signal.aborted&&!cancelSent){
        onProgress('正在停止本機辨識…');
        const stopped=await fetch(url,{method:'DELETE',signal:AbortSignal.timeout(5000)});
        if(!stopped.ok)throw Error('無法確認停止狀態，請關閉本機辨識器視窗。');
        cancelSent=true;
      }
      const response=await fetch(url,{signal:AbortSignal.timeout(5000)});
      const job=await response.json();
      if(!response.ok)throw Error(job.error||'無法取得辨識進度');
      if(job.state==='cancelled'||(signal.aborted&&['succeeded','failed'].includes(job.state)))
        throw new DOMException('已取消辨識','AbortError');
      if(job.state==='failed')throw Error(job.error||'辨識失敗');
      if(job.state==='succeeded')return job.result as {xml:string;pageCount:number};
      onProgress(`${job.message}（已用 ${job.elapsedSeconds} 秒）`);
      await pause(500);
    }
    throw Error('辨識等候逾時，已要求停止。');
  }finally{
    // Idempotent: completed jobs keep their result; running jobs are stopped on errors too.
    await fetch(url,{method:'DELETE',signal:AbortSignal.timeout(5000)}).catch(()=>{});
  }
}
