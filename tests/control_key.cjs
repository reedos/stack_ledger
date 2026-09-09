const test=require('node:test');const assert=require('node:assert');
// control.js references browser globals at load time; evaluate only the pure helper it exports.
const src=require('fs').readFileSync(require('path').join(__dirname,'..','tools','research-control','control.js'),'utf8');
const fn=new Function(src.slice(src.indexOf('function sessionKeyFromPath'),src.indexOf('const sessionKey='))+'return sessionKeyFromPath;')();
test('loopback path yields the token',()=>assert.strictEqual(fn('/abcDEF123_-tokentokentokentokentokentoken/'),'abcDEF123_-tokentokentokentokentokentoken'));
test('serve mount path yields the token, not the mount',()=>assert.strictEqual(fn('/research/abcDEF123_-tokentokentokentokentokentoken/'),'abcDEF123_-tokentokentokentokentokentoken'));
test('empty path yields empty key',()=>assert.strictEqual(fn('/'),''));
