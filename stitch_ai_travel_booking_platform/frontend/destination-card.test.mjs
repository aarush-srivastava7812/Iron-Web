import test from 'node:test';
import assert from 'node:assert/strict';
import {destinationDetails} from './destination-card.js';

test('a missing city cannot be displayed as a zero fare',()=>{
  const html=destinationDetails({match_reasons:['For your relaxed pace: quiet trails.'],transport:{costs_complete:false,round_trip_inr:null,notice:'Starting city needed'}});
  assert.ok(html.includes('Why this fits you'));
  assert.ok(html.includes('relaxed pace'));
  assert.ok(html.includes('Starting city needed'));
  assert.ok(!html.includes('₹0'));
});

test('round-trip sample includes actual origin and party size',()=>{
  const html=destinationDetails({match_reasons:['Matches your beach interest'],transport:{costs_complete:true,round_trip_inr:14000,travelers:2,origin:'Mumbai',notice:'Sample fares; verify availability.'}});
  assert.ok(html.includes('₹14,000'));
  assert.ok(html.includes('2 travelers from Mumbai'));
  assert.ok(html.includes('sample round-trip'));
});

test('source text is escaped',()=>assert.ok(!destinationDetails({match_reasons:['<script>alert(1)</script>']}).includes('<script>')));
