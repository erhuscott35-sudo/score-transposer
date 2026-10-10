import type {Score} from './music';

export function reviewPages(score:Score) {
  const numbers=Array.from(new Set(score.measures.map(m=>m.sourcePage??1))).sort((a,b)=>a-b);
  return numbers.map(page=>{
    const indices=score.measures.map((m,i)=>(m.sourcePage??1)===page?i:-1).filter(i=>i>=0);
    const first=indices[0],last=indices[indices.length-1];
    return {
      page, firstMeasure:score.measures[first].number,lastMeasure:score.measures[last].number,
      // Include adjacent notes so edits affecting a cross-page tie invalidate both pages.
      fingerprint:JSON.stringify([score.key,score.meter,indices.map(i=>score.measures[i]),
        score.measures[first-1]?.notes.at(-1),score.measures[last+1]?.notes[0]])
    };
  });
}

export function paginateSystems(systems:{width:number;height:number}[]) {
  let page=1,y=12;
  return systems.map(({width,height})=>{
    if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)
      throw Error('無法取得樂譜行尺寸');
    const scale=Math.min(186/width,260/height),w=width*scale,h=height*scale;
    if(y+h>277){page++;y=12;}
    const placement={page,x:(210-w)/2,y,width:w,height:h};
    y+=h;
    return placement;
  });
}
