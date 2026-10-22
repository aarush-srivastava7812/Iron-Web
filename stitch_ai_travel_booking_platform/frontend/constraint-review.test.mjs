import test from 'node:test';
import assert from 'node:assert/strict';
import {constraintReview} from './constraint-review.js';

test('review separates firm budget from optional wishes and escapes query text',()=>{
  const html=constraintReview({mode:'deterministic',facts:{budget:100000},preferences:{pace:'relaxed'},hard_constraints:['no boats'],soft_preferences:['quiet <script>hotels</script>']});
  assert.ok(html.includes('Facts & firm constraints'));
  assert.ok(html.includes('₹1,00,000 for the group'));
  assert.ok(html.includes('Guide ranking; can be traded off.'));
  assert.ok(html.includes('quiet &lt;script&gt;hotels&lt;/script&gt;'));
  assert.ok(!html.includes('<script>'));
});

test('empty draft keeps review hidden',()=>assert.equal(constraintReview({facts:{}}),''));
