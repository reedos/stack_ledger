'use strict';
// Pure conversions for chip-project capacity quantification. No DOM. Used by expansion.js
// in the browser (window.chipConversions) and by tests/chip_conversions.cjs under node:test.
const CHIP_CONVERSION_METRICS={chipsCumulative:'epoch-nvidia-ai-chips-cumulative',computeCumulative:'epoch-nvidia-ai-compute-cumulative',cowosQuarterly:'epoch-nvidia-cowos-wafers-quarterly',chipsYearly:'epoch-nvidia-ai-chips-cumulative-yearly'};
function chipPrevQuarter(period) {
 const m=/^(\d{4})-Q([1-4])$/.exec(period);
 if(!m)return null;
 const year=Number(m[1]),q=Number(m[2]);
 return q===1?`${year-1}-Q4`:`${year}-Q${q-1}`;
}
function chipByPeriod(observations,metricId) {
 const out={};
 for(const o of observations)if(o.metric===metricId&&!o.superseded_by)out[o.period]=o.value;
 return out;
}
// Latest quarter where Nvidia CoWoS consumption and both cumulative series also carry the
// previous quarter, so a quarterly shipment figure can be derived from the cumulative diff.
function impliedRatios(observations) {
 const chips=chipByPeriod(observations,CHIP_CONVERSION_METRICS.chipsCumulative);
 const compute=chipByPeriod(observations,CHIP_CONVERSION_METRICS.computeCumulative);
 const cowos=chipByPeriod(observations,CHIP_CONVERSION_METRICS.cowosQuarterly);
 const quarters=Object.keys(cowos).filter(q=>/^\d{4}-Q[1-4]$/.test(q)).sort();
 let quarter=null;
 for(let i=quarters.length-1;i>=0;i--) {
  const q=quarters[i],prev=chipPrevQuarter(q);
  if(chips[q]!=null&&chips[prev]!=null&&compute[q]!=null&&compute[prev]!=null&&cowos[q]){quarter=q;break;}
 }
 if(!quarter)return null;
 const prev=chipPrevQuarter(quarter);
 const acceleratorsShipped=chips[quarter]-chips[prev];
 const computeShipped=compute[quarter]-compute[prev];
 const acceleratorsPerCowosWafer=acceleratorsShipped/cowos[quarter];
 const h100ePerAccelerator=computeShipped/acceleratorsShipped;
 const yearly=observations.filter(o=>o.metric===CHIP_CONVERSION_METRICS.chipsYearly&&!o.superseded_by&&/^Year-end \d{4}$/.test(o.period)).sort((a,b)=>Number(a.period.slice(-4))-Number(b.period.slice(-4)));
 let shipments=null;
 if(yearly.length) {
  const latest=yearly[yearly.length-1],year=Number(latest.period.slice(-4));
  const prior=yearly.find(o=>Number(o.period.slice(-4))===year-1);
  shipments={year,value:prior?latest.value-prior.value:latest.value};
 }
 return {quarter,acceleratorsPerCowosWafer,h100ePerAccelerator,shipments};
}
// Gross die per 300mm-class wafer: floor(pi*(d/2)^2/area - pi*d/sqrt(2*area)), the standard
// reticle-die approximation that discounts the wafer edge where no full die fits.
function grossDiePerWafer(areaMm2,diameterMm) {
 const r=diameterMm/2;
 return Math.floor((Math.PI*r*r)/areaMm2-(Math.PI*diameterMm)/Math.sqrt(2*areaMm2));
}
function packagingEquivalent(wspm,ratios) {
 const acceleratorsPerYear=wspm*12*ratios.acceleratorsPerCowosWafer;
 return {acceleratorsPerYear,h100ePerYear:acceleratorsPerYear*ratios.h100ePerAccelerator};
}
function logicCeiling(wspm,diePerWafer) {
 return {diePerYear:wspm*12*diePerWafer};
}
const chipConversions={impliedRatios,grossDiePerWafer,packagingEquivalent,logicCeiling,prevQuarter:chipPrevQuarter};
if(typeof window!=='undefined')window.chipConversions=chipConversions;
if(typeof module!=='undefined')module.exports=chipConversions;
