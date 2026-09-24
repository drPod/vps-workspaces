const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {panes, groups, urlFor} = require('./layout');
const leaf = id => ({pane:{surfaces:[{id}]}});
const split = (direction, ratio, left, right) => ({direction,split:ratio,children:[left,right]});
test('mixed splits preserve proportions and pane order',()=>{
 const tree=split('horizontal',0.6,leaf('term'),split('vertical',0.3,leaf('report'),leaf('app')));
 assert.deepEqual(groups(tree,'horizontal'),[{size:0.6},{size:0.4,groups:[{size:0.3},{size:0.7}]}]);
 assert.deepEqual(panes(tree).map(p=>p.surfaces[0].id),['term','report','app']);
});
test('adjacent equal orientations flatten without changing proportions',()=>{
 const tree=split('horizontal',0.5,split('horizontal',0.2,leaf('a'),leaf('b')),leaf('c'));
 assert.deepEqual(groups(tree,'horizontal'),[{size:0.1},{size:0.4},{size:0.5}]);
});
test('explicit default port is hashed the same way as the Python gateway',()=>{
 const hash=createHash('sha256').update('http://localhost:80').digest('hex').slice(0,10);
 assert.equal(urlFor({host:'demo.example'}, {url:'http://localhost:80/report?q=1#section'}),`https://b-${hash}.demo.example/report?q=1#section`);
});
test('external pages retain their original URL',()=>{
 assert.equal(urlFor({host:'demo.example'}, {url:'https://example.com/docs'}),'https://example.com/docs');
});
