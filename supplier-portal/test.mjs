import test from 'node:test';
import assert from 'node:assert/strict';
import {filtered,totals,format} from './data.mjs';
test('unknown reference remains unknown and zero is known',()=>{assert.equal(totals([{items:2,value:null,value_sample:0}]).value,null);assert.equal(totals([{items:1,value:0,value_sample:1}]).value,0);assert.equal(format(null),'Não disponível');});
test('filters preserve accents, category and brand boundaries',()=>{const rows=[{product:'Câmera',category:'Rede',brand:'TOR'},{product:'Câmera',category:'Vídeo',brand:'TOR'}];assert.equal(filtered(rows,'CÂM','Rede','TOR').length,1);assert.equal(filtered(rows,'Câmera','Rede','Outra').length,0);});
