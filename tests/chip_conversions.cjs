const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const cc=require(path.resolve(__dirname,'../site/assets/chip-conversions.js'));

test('grossDiePerWafer floors the reticle-die approximation for the H100-class reference die',()=>{
 assert.equal(cc.grossDiePerWafer(814,300),63);
 assert.equal(cc.grossDiePerWafer(100,300),640);
});

test('prevQuarter wraps across year boundaries',()=>{
 assert.equal(cc.prevQuarter('2025-Q1'),'2024-Q4');
 assert.equal(cc.prevQuarter('2025-Q4'),'2025-Q3');
 assert.equal(cc.prevQuarter('not-a-quarter'),null);
});

test('impliedRatios picks the latest quarter where CoWoS consumption and both cumulative series carry the prior quarter too',()=>{
 const observations=[
  // A quarter with a CoWoS reading but no prior-quarter cumulative data must be skipped.
  {metric:'epoch-nvidia-cowos-wafers-quarterly',period:'2024-Q1',value:1000},
  {metric:'epoch-nvidia-ai-chips-cumulative',period:'2024-Q1',value:2000},
  {metric:'epoch-nvidia-ai-compute-cumulative',period:'2024-Q1',value:5000},
  {metric:'epoch-nvidia-cowos-wafers-quarterly',period:'2024-Q2',value:1500},
  {metric:'epoch-nvidia-ai-chips-cumulative',period:'2024-Q2',value:3500},
  {metric:'epoch-nvidia-ai-compute-cumulative',period:'2024-Q2',value:9000},
  // Latest quarter (2025-Q1) has a CoWoS wafer reading and both cumulative series one quarter back.
  {metric:'epoch-nvidia-cowos-wafers-quarterly',period:'2025-Q1',value:2000},
  {metric:'epoch-nvidia-ai-chips-cumulative',period:'2024-Q4',value:6000},
  {metric:'epoch-nvidia-ai-chips-cumulative',period:'2025-Q1',value:8000},
  {metric:'epoch-nvidia-ai-compute-cumulative',period:'2024-Q4',value:15000},
  {metric:'epoch-nvidia-ai-compute-cumulative',period:'2025-Q1',value:23000},
  // A superseded reading in the newest quarter must not be used.
  {metric:'epoch-nvidia-cowos-wafers-quarterly',period:'2025-Q2',value:9999,superseded_by:'x'},
  {metric:'epoch-nvidia-ai-chips-cumulative-yearly',period:'Year-end 2023',value:1000},
  {metric:'epoch-nvidia-ai-chips-cumulative-yearly',period:'Year-end 2024',value:6000},
 ];
 const ratios=cc.impliedRatios(observations);
 assert.equal(ratios.quarter,'2025-Q1');
 assert.equal(ratios.acceleratorsPerCowosWafer,(8000-6000)/2000);
 assert.equal(ratios.h100ePerAccelerator,(23000-15000)/(8000-6000));
 assert.deepEqual(ratios.shipments,{year:2024,value:5000});
});

test('impliedRatios returns null when no quarter has both cumulative series and a CoWoS reading',()=>{
 assert.equal(cc.impliedRatios([{metric:'epoch-nvidia-cowos-wafers-quarterly',period:'2025-Q1',value:100}]),null);
});

test('packagingEquivalent applies the CoWoS-wafer and accelerator ratios to a monthly capacity',()=>{
 const eq=cc.packagingEquivalent(1000,{acceleratorsPerCowosWafer:10,h100ePerAccelerator:2.5});
 assert.equal(eq.acceleratorsPerYear,1000*12*10);
 assert.equal(eq.h100ePerYear,1000*12*10*2.5);
});

test('logicCeiling multiplies monthly wafer starts by die per wafer and months per year',()=>{
 assert.deepEqual(cc.logicCeiling(500,63),{diePerYear:500*12*63});
});

test('module attaches to module.exports in Node and would attach to window in a browser',()=>{
 assert.equal(typeof cc.impliedRatios,'function');
 assert.equal(typeof cc.grossDiePerWafer,'function');
 assert.equal(typeof cc.packagingEquivalent,'function');
 assert.equal(typeof cc.logicCeiling,'function');
});
